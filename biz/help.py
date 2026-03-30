#!/usr/bin/env python3

from app.services.qq_api import qq_api_service
from utils.command_parser import HelpCommand


HELP_TEXT = "\n".join(
    [
        "可用指令：",
        "1. 发图",
        "123456",
        "123456 5",
        "123456 5-10",
        "123456 5-",
        "123456 -5",
        "123456 all",
        "别名：123456 al",
        "2. 简介",
        "123456 info",
        "别名：123456 if",
        "3. 搜索",
        "search 关键词",
        "search tag 纯爱",
        "search author MANA",
        "search work 原神",
        "search actor 雷电将军",
        "别名：sr 关键词 / sr tg 纯爱 / sr au MANA / sr wk 原神 / sr ac 雷电将军",
        "4. 过滤提取数字并查简介",
        "guolv 一整句话",
        "别名：filter 一整句话 / fl 一整句话",
        "5. 帮助",
        "help",
        "别名：hp",
    ]
)


async def handle(command: HelpCommand, user_openid: str, msg_id: str) -> None:
    await qq_api_service.send_text(user_openid, msg_id, HELP_TEXT)


def dedupe_key(command: HelpCommand, user_openid: str) -> tuple[str, str, str]:
    return user_openid, "help", "help"
