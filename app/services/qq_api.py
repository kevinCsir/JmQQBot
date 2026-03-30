#!/usr/bin/env python3
import asyncio

from botpy.api import BotAPI
from botpy.errors import ServerError
from botpy.http import BotHttp

from app.config import settings


class QQApiService:
    def __init__(self):
        self.api = BotAPI(
            BotHttp(
                timeout=20,
                is_sandbox=settings.qq_bot_is_sandbox,
                app_id=settings.qq_bot_app_id,
                secret=settings.qq_bot_secret,
            )
        )
        self._message_seq_state: dict[str, int] = {}
        self._message_seq_lock = asyncio.Lock()

    async def next_msg_seq(self, msg_id: str) -> int:
        async with self._message_seq_lock:
            next_value = self._message_seq_state.get(msg_id, 0) + 1
            self._message_seq_state[msg_id] = next_value
            return next_value

    async def send_text(self, user_openid: str, msg_id: str, content: str) -> None:
        msg_seq = str(await self.next_msg_seq(msg_id))
        await self.api.post_c2c_message(
            openid=user_openid,
            msg_id=msg_id,
            msg_seq=msg_seq,
            content=content,
            msg_type=0,
        )

    async def send_image(self, user_openid: str, url: str) -> None:
        await self.api.post_c2c_file(
            openid=user_openid,
            file_type=1,
            url=url,
            srv_send_msg=True,
        )

    async def send_image_with_retry(self, user_openid: str, msg_id: str, url: str, label: str) -> bool:
        delays = list(settings.image_send_retry_delays)
        for attempt in range(1, settings.image_send_max_retries + 1):
            try:
                await self.send_image(user_openid, url)
                return True
            except ServerError as exc:
                if attempt >= settings.image_send_max_retries:
                    await self.send_text(user_openid, msg_id, f"{label} 发送失败，已重试 {attempt} 次：{exc}")
                    return False
                delay = delays[min(attempt - 1, len(delays) - 1)]
                await self.send_text(user_openid, msg_id, f"{label} 发送失败，{delay:.0f} 秒后重试（第 {attempt + 1} 次）")
                await asyncio.sleep(delay)
            except Exception as exc:
                await self.send_text(user_openid, msg_id, f"{label} 发送失败：{exc}")
                return False
        return False


qq_api_service = QQApiService()
