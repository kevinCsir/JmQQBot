#!/usr/bin/env python3
import asyncio

from app.services.jm_service import search_random
from app.services.qq_api import qq_api_service
from utils.command_parser import SearchCommand


SEARCH_MODE_LABELS = {
    "site": "通用",
    "tag": "标签",
    "author": "作者",
    "work": "作品",
    "actor": "角色",
}


async def handle(command: SearchCommand, user_openid: str, msg_id: str) -> None:
    mode_label = SEARCH_MODE_LABELS.get(command.mode, command.mode)
    await qq_api_service.send_text(user_openid, msg_id, f"正在搜索{mode_label}：{command.query}")
    try:
        results, sampled_pages = await asyncio.to_thread(search_random, command.query, command.mode)
    except Exception as exc:
        await qq_api_service.send_text(user_openid, msg_id, f"{mode_label}搜索失败：{exc}")
        return

    if not results:
        await qq_api_service.send_text(user_openid, msg_id, f"{mode_label} {command.query} 没有搜索到结果")
        return

    page_text = "、".join(str(page) for page in sampled_pages)
    lines = [f"{mode_label} {command.query} 的随机结果（采样页：{page_text}）："]
    for index, (album_id, title, tags) in enumerate(results, start=1):
        tag_text = "、".join(tags[:6]) if tags else "无"
        lines.append(f"{index}. [{album_id}] {title}")
        lines.append(f"标签：{tag_text}")

    await qq_api_service.send_text(user_openid, msg_id, "\n".join(lines))


def dedupe_key(command: SearchCommand, user_openid: str) -> tuple[str, str, str]:
    return user_openid, f"search:{command.mode}:{command.query}", "search"
