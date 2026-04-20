#!/usr/bin/env python3
import asyncio

from app.services.cache_service import log_album_command, touch_album
from app.services.jm_service import get_album_info_payload
from app.services.qq_api import qq_api_service
from utils.command_parser import AlbumInfoCommand


async def handle(command: AlbumInfoCommand, user_openid: str, msg_id: str) -> None:
    touch_album(command.album_id)
    if command.source == "filter":
        await qq_api_service.send_text(user_openid, msg_id, f"已过滤提取编号 {command.album_id}，正在查询简介信息")
    else:
        await qq_api_service.send_text(user_openid, msg_id, f"收到编号 {command.album_id}，正在查询简介信息")
    try:
        album, page_count = await asyncio.to_thread(get_album_info_payload, command.album_id)
    except Exception as exc:
        await qq_api_service.send_text(user_openid, msg_id, f"简介查询失败：{exc}")
        return

    await asyncio.to_thread(
        log_album_command,
        command.album_id,
        getattr(album, "name", "") or command.album_id,
        "info",
        _command_text(command),
    )

    authors = " / ".join(album.authors[:5]) if album.authors else "未知"
    tags = "、".join(album.tags[:12]) if album.tags else "无"
    description = album.description.strip() if album.description else "无"
    if len(description) > 300:
        description = description[:300] + "..."

    await qq_api_service.send_text(
        user_openid,
        msg_id,
        "\n".join(
            [
                f"标题：{album.name}",
                f"作者：{authors}",
                f"页数：{page_count}",
                f"标签：{tags}",
                f"简介：{description}",
            ]
        ),
    )


def dedupe_key(command: AlbumInfoCommand, user_openid: str) -> tuple[str, str, str]:
    return user_openid, command.album_id, "info"


def _command_text(command: AlbumInfoCommand) -> str:
    if command.source == "filter":
        return f"filter {command.original_text}"
    return f"{command.album_id} info"
