#!/usr/bin/env python3
import asyncio
import binascii
import json

from fastapi import APIRouter, HTTPException, Request
from nacl.signing import SigningKey, VerifyKey

from app.services.qq_api import qq_api_service
from biz import album_info, album_send, help, search
from utils.command_parser import (
    AlbumInfoCommand,
    AlbumSendCommand,
    HelpCommand,
    SearchCommand,
    parse_command,
)


router = APIRouter()
ACTIVE_TASKS: dict[tuple[str, str, str], asyncio.Task] = {}


def build_seed(secret: str) -> bytes:
    seed = secret
    while len(seed) < 32:
        seed = seed * 2
    return seed[:32].encode("utf-8")


def qq_secret() -> str:
    from app.config import settings

    if not settings.qq_bot_secret:
        raise RuntimeError("Missing QQ_BOT_SECRET")
    return settings.qq_bot_secret


def sign_validation(event_ts: str, plain_token: str) -> str:
    signing_key = SigningKey(build_seed(qq_secret()))
    msg = f"{event_ts}{plain_token}".encode("utf-8")
    return signing_key.sign(msg).signature.hex()


def verify_callback_signature(timestamp: str, body: bytes, signature_hex: str) -> bool:
    try:
        signature = binascii.unhexlify(signature_hex)
    except binascii.Error:
        return False

    verify_key = VerifyKey(bytes(SigningKey(build_seed(qq_secret())).verify_key))
    msg = timestamp.encode("utf-8") + body
    try:
        verify_key.verify(msg, signature)
        return True
    except Exception:
        return False


def get_public_base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


def command_key(command, user_openid: str):
    if isinstance(command, AlbumSendCommand):
        return album_send.dedupe_key(command, user_openid)
    if isinstance(command, AlbumInfoCommand):
        return album_info.dedupe_key(command, user_openid)
    if isinstance(command, HelpCommand):
        return help.dedupe_key(command, user_openid)
    if isinstance(command, SearchCommand):
        return search.dedupe_key(command, user_openid)
    raise TypeError(f"Unsupported command: {type(command)}")


def schedule_command(command, user_openid: str, msg_id: str, public_base_url: str | None = None) -> None:
    key = command_key(command, user_openid)
    running = ACTIVE_TASKS.get(key)
    if running is not None and not running.done():
        async def notify_duplicate() -> None:
            await qq_api_service.send_text(user_openid, msg_id, "相同任务已在处理中，请稍候")

        asyncio.create_task(notify_duplicate())
        return

    async def runner() -> None:
        try:
            if isinstance(command, AlbumSendCommand):
                await album_send.handle(command, user_openid, msg_id, public_base_url or "")
            elif isinstance(command, AlbumInfoCommand):
                await album_info.handle(command, user_openid, msg_id)
            elif isinstance(command, HelpCommand):
                await help.handle(command, user_openid, msg_id)
            elif isinstance(command, SearchCommand):
                await search.handle(command, user_openid, msg_id)
        finally:
            ACTIVE_TASKS.pop(key, None)

    ACTIVE_TASKS[key] = asyncio.create_task(runner())


@router.get("/qq/callback")
async def health() -> dict[str, bool]:
    return {"ok": True}


@router.post("/qq/callback")
async def callback(request: Request):
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    op = payload.get("op")
    data = payload.get("d") or {}

    if op == 13:
        plain_token = data.get("plain_token", "")
        event_ts = data.get("event_ts", "")
        if not plain_token or not event_ts:
            raise HTTPException(status_code=400, detail="Missing plain_token or event_ts")
        return {"plain_token": plain_token, "signature": sign_validation(event_ts, plain_token)}

    timestamp = request.headers.get("X-Signature-Timestamp", "")
    signature = request.headers.get("X-Signature-Ed25519", "")
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing signature headers")
    if not verify_callback_signature(timestamp, body, signature):
        raise HTTPException(status_code=401, detail="Invalid callback signature")

    if payload.get("t") == "C2C_MESSAGE_CREATE":
        message = payload.get("d") or {}
        content = (message.get("content") or "").strip()
        user_openid = ((message.get("author") or {}).get("user_openid") or "").strip()
        msg_id = (message.get("id") or "").strip()
        command = parse_command(content)
        if command is not None and user_openid and msg_id:
            schedule_command(command, user_openid, msg_id, get_public_base_url(request))

    return {"op": 12}
