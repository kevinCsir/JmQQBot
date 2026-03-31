#!/usr/bin/env python3
import asyncio

from app.services.cache_service import clear_all_cached_media
from app.services.qq_api import qq_api_service
from utils.command_parser import RemoveCacheCommand


async def handle(command: RemoveCacheCommand, user_openid: str, msg_id: str) -> None:
    del command
    await qq_api_service.send_text(user_openid, msg_id, "开始清空本地图片缓存，请稍候")
    try:
        summary = await asyncio.to_thread(clear_all_cached_media)
    except Exception as exc:
        await qq_api_service.send_text(user_openid, msg_id, f"清空失败：{exc}")
        return

    await qq_api_service.send_text(
        user_openid,
        msg_id,
        (
            "本地图片缓存已清空："
            f"删除 {summary['album_count']} 个作品目录，"
            f"{summary['file_count']} 个文件，"
            f"约释放 {summary['freed_size_text']}。"
            "原图、长图、PDF 和缓存记录都已清掉"
        ),
    )


def dedupe_key(command: RemoveCacheCommand, user_openid: str) -> tuple[str, str, str]:
    del command
    return user_openid, "rm", "rm"
