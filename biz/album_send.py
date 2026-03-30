#!/usr/bin/env python3
import asyncio
from urllib.parse import quote

from app.config import ROOT_DIR, settings
from app.services.cache_service import enforce_cache_limit, touch_album
from app.services.jm_service import count_local_images, download_album
from app.services.qq_api import qq_api_service
from utils.command_parser import AlbumSendCommand
from utils.image_merge import expected_long_image_paths, generate_long_images, needs_long_image_generation
from utils.progress import DownloadProgressReporter


def public_file_url(public_base_url: str, file_path):
    resolved_path = file_path.resolve()
    relative_path = resolved_path.relative_to(ROOT_DIR.resolve()).as_posix()
    return f"{public_base_url.rstrip('/')}/files/{quote(relative_path)}"


async def handle(command: AlbumSendCommand, user_openid: str, msg_id: str, public_base_url: str) -> None:
    request_label = _describe_request(command)
    touch_album(command.album_id)
    await qq_api_service.send_text(user_openid, msg_id, f"收到编号 {command.album_id}，准备发送{request_label}")
    await qq_api_service.send_text(user_openid, msg_id, "步骤 1/4 检查本地资源")

    local_count = count_local_images(command.album_id)
    if local_count > 0:
        await qq_api_service.send_text(user_openid, msg_id, f"本地已存在 {local_count} 张图片，跳过下载")
    else:
        await qq_api_service.send_text(user_openid, msg_id, "本地未找到资源，准备下载")
        reporter = DownloadProgressReporter(
            asyncio.get_running_loop(),
            lambda text: qq_api_service.send_text(user_openid, msg_id, text),
        )
        try:
            await asyncio.to_thread(download_album, command.album_id, reporter)
        except Exception as exc:
            await qq_api_service.send_text(user_openid, msg_id, f"下载失败：{exc}")
            return
        local_count = count_local_images(command.album_id)
        await qq_api_service.send_text(user_openid, msg_id, f"下载完成，本地现有 {local_count} 张图片")
        deleted = enforce_cache_limit()
        if deleted:
            await qq_api_service.send_text(user_openid, msg_id, f"本地缓存超阈值，已按 LRU 清理：{', '.join(deleted)}")

    if local_count <= 0:
        await qq_api_service.send_text(user_openid, msg_id, "未找到可处理的图片，任务结束")
        return

    album_dir = settings.download_dir / command.album_id
    await qq_api_service.send_text(user_openid, msg_id, "步骤 3/4 检查 5 合 1 长图")
    if needs_long_image_generation(album_dir, settings.longimg_dir):
        await qq_api_service.send_text(user_openid, msg_id, "开始生成长图")
        try:
            longimg_paths = await asyncio.to_thread(generate_long_images, album_dir, settings.longimg_dir)
        except Exception as exc:
            await qq_api_service.send_text(user_openid, msg_id, f"长图生成失败：{exc}")
            return
        await qq_api_service.send_text(user_openid, msg_id, f"长图生成完成，共 {len(longimg_paths)} 张")
    else:
        longimg_paths = expected_long_image_paths(album_dir, settings.longimg_dir)
        await qq_api_service.send_text(user_openid, msg_id, "长图已存在且是最新版本，跳过生成")

    start_pos = max(command.start_index - 1, 0)
    selected_paths = longimg_paths[start_pos:command.end_index]
    if not selected_paths:
        await qq_api_service.send_text(user_openid, msg_id, "没有可发送的长图，任务结束")
        return

    await qq_api_service.send_text(user_openid, msg_id, f"步骤 4/4 开始发送，共 {len(selected_paths)} 张长图")
    success_count = 0
    for index, image_path in enumerate(selected_paths, start=1):
        actual_index = start_pos + index
        label = f"第 {actual_index} 张长图（本次 {index}/{len(selected_paths)}）"
        await qq_api_service.send_text(user_openid, msg_id, f"发送{label}")
        sent = await qq_api_service.send_image_with_retry(
            user_openid=user_openid,
            msg_id=msg_id,
            url=public_file_url(public_base_url, image_path),
            label=label,
        )
        if sent:
            success_count += 1
        else:
            await qq_api_service.send_text(user_openid, msg_id, f"{label} 连续失败，任务已停止")
            return
        await asyncio.sleep(settings.image_send_interval_seconds)

    if command.range_text == "default" and len(longimg_paths) > settings.default_preview_count:
        await qq_api_service.send_text(
            user_openid,
            msg_id,
            f"已发送前 {settings.default_preview_count} 张。发送“{command.album_id} all”可获取全部，或发送“{command.album_id} 5-10”获取指定范围",
        )
    else:
        await qq_api_service.send_text(user_openid, msg_id, "全部发送完成")


def dedupe_key(command: AlbumSendCommand, user_openid: str) -> tuple[str, str, str]:
    return user_openid, command.album_id, command.range_text


def _describe_request(command: AlbumSendCommand) -> str:
    if command.end_index is None:
        return f"第 {command.start_index} 张之后的全部长图"
    if command.start_index == 1 and command.end_index == settings.default_preview_count:
        return f"前 {settings.default_preview_count} 张长图"
    return f"第 {command.start_index}-{command.end_index} 张长图"
