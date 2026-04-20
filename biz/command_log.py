#!/usr/bin/env python3
import asyncio
from datetime import datetime

from app.services.cache_service import list_album_command_logs
from app.services.qq_api import qq_api_service
from utils.command_parser import LogCommand


LOG_BATCH_SIZE = 5
LOG_FETCH_LIMIT = 10
COMMAND_TYPE_LABELS = {
    "send": "发图",
    "info": "简介",
}


async def handle(command: LogCommand, user_openid: str, msg_id: str) -> None:
    del command
    try:
        rows = await asyncio.to_thread(list_album_command_logs, LOG_FETCH_LIMIT)
    except Exception as exc:
        await qq_api_service.send_text(user_openid, msg_id, f"日志查询失败：{exc}")
        return

    if not rows:
        await qq_api_service.send_text(user_openid, msg_id, "最近没有编号命令日志")
        return

    total = len(rows)
    for start in range(0, total, LOG_BATCH_SIZE):
        batch = rows[start : start + LOG_BATCH_SIZE]
        header = f"最近编号命令日志（{start + 1}-{start + len(batch)} / {total}）："
        lines = [header]
        for row in batch:
            created_at_text = datetime.fromtimestamp(float(row["created_at"])).strftime("%Y-%m-%d %H:%M:%S")
            command_label = COMMAND_TYPE_LABELS.get(str(row["command_type"]), str(row["command_type"]))
            lines.append(
                f"{created_at_text} | {command_label} | [{row['album_id']}] {row['album_title']}"
            )
            lines.append(f"命令：{row['command_text']}")
        await qq_api_service.send_text(user_openid, msg_id, "\n".join(lines))


def dedupe_key(command: LogCommand, user_openid: str) -> tuple[str, str, str]:
    del command
    return user_openid, "log", "log"
