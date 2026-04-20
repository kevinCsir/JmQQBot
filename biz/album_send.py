#!/usr/bin/env python3
import asyncio
from urllib.parse import quote

from app.config import ROOT_DIR, settings
from app.services.cache_service import cache_usage_summary, enforce_cache_limit, log_album_command, touch_album
from app.services.jm_service import build_long_image_selection, download_images_for_selection
from app.services.qq_api import qq_api_service
from utils.command_parser import AlbumSendCommand
from utils.image_merge import merge_images_vertically, output_needs_generation
from utils.progress import DownloadProgressReporter


def public_file_url(public_base_url: str, file_path):
    resolved_path = file_path.resolve()
    relative_path = resolved_path.relative_to(ROOT_DIR.resolve()).as_posix()
    return f"{public_base_url.rstrip('/')}/files/{quote(relative_path)}"


async def handle(command: AlbumSendCommand, user_openid: str, msg_id: str, public_base_url: str) -> None:
    request_label = _describe_request(command)
    touch_album(command.album_id)
    await qq_api_service.send_text(user_openid, msg_id, f"收到编号 {command.album_id}，准备发送{request_label}")
    await qq_api_service.send_text(user_openid, msg_id, "步骤 1/4 计算目标范围")

    try:
        selection = await asyncio.to_thread(build_long_image_selection, command.album_id, command.start_index, command.end_index)
    except Exception as exc:
        await qq_api_service.send_text(user_openid, msg_id, f"资源规划失败：{exc}")
        return

    if not selection.plans:
        await qq_api_service.send_text(user_openid, msg_id, "没有可发送的长图，任务结束")
        return

    await asyncio.to_thread(
        log_album_command,
        command.album_id,
        selection.album_title,
        "send",
        _command_text(command),
    )

    await qq_api_service.send_text(
        user_openid,
        msg_id,
        f"已定位到 {len(selection.plans)} 张目标长图，对应 {selection.total_requested_images} 张原图",
    )

    await qq_api_service.send_text(user_openid, msg_id, "步骤 2/4 检查并补齐原图")
    if selection.missing_image_count <= 0:
        await qq_api_service.send_text(
            user_openid,
            msg_id,
            f"所需原图已齐全，共 {selection.existing_image_count} 张，跳过下载",
        )
        await qq_api_service.send_text(user_openid, msg_id, cache_usage_summary())
    else:
        await qq_api_service.send_text(
            user_openid,
            msg_id,
            f"本地已命中 {selection.existing_image_count}/{selection.total_requested_images} 张，准备补齐缺失的 {selection.missing_image_count} 张",
        )
        reporter = DownloadProgressReporter(
            asyncio.get_running_loop(),
            lambda text: qq_api_service.send_text(user_openid, msg_id, text),
        )
        try:
            await asyncio.to_thread(download_images_for_selection, selection, reporter)
        except Exception as exc:
            await qq_api_service.send_text(user_openid, msg_id, f"下载失败：{exc}")
            return
        await qq_api_service.send_text(user_openid, msg_id, f"下载完成，已补齐目标原图")
        deleted = enforce_cache_limit()
        if deleted:
            await qq_api_service.send_text(user_openid, msg_id, f"本地缓存超阈值，已按 LRU 清理：{', '.join(deleted)}")
        await qq_api_service.send_text(user_openid, msg_id, cache_usage_summary())

    await qq_api_service.send_text(user_openid, msg_id, "步骤 3/4 生成目标长图")
    generated_count = 0
    reused_count = 0
    for plan in selection.plans:
        if output_needs_generation(plan.output_path, plan.source_paths):
            try:
                await asyncio.to_thread(merge_images_vertically, list(plan.source_paths), plan.output_path)
            except Exception as exc:
                await qq_api_service.send_text(user_openid, msg_id, f"长图生成失败：{exc}")
                return
            generated_count += 1
        else:
            reused_count += 1
    if generated_count > 0:
        await qq_api_service.send_text(
            user_openid,
            msg_id,
            f"长图处理完成，新生成 {generated_count} 张，复用 {reused_count} 张",
        )
    else:
        await qq_api_service.send_text(user_openid, msg_id, "目标长图已存在且是最新版本，跳过生成")

    await qq_api_service.send_text(user_openid, msg_id, f"步骤 4/4 开始发送，共 {len(selection.plans)} 张长图")
    success_count = 0
    for index, plan in enumerate(selection.plans, start=1):
        label = f"第 {plan.overall_index} 张长图（本次 {index}/{len(selection.plans)}）"
        await qq_api_service.send_text(user_openid, msg_id, f"发送{label}")
        sent = await qq_api_service.send_image_with_retry(
            user_openid=user_openid,
            msg_id=msg_id,
            url=public_file_url(public_base_url, plan.output_path),
            label=label,
        )
        if sent:
            success_count += 1
        else:
            await qq_api_service.send_text(user_openid, msg_id, f"{label} 连续失败，任务已停止")
            return
        await asyncio.sleep(settings.image_send_interval_seconds)

    if command.range_text == "default" and len(selection.plans) >= settings.default_preview_count:
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


def _command_text(command: AlbumSendCommand) -> str:
    if command.range_text == "default":
        return command.album_id
    return f"{command.album_id} {command.range_text}"
