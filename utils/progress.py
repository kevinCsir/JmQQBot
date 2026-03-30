#!/usr/bin/env python3
import asyncio
import threading
from collections.abc import Awaitable, Callable


def render_progress_bar(completed: int, total: int) -> str:
    if total <= 0:
        return "下载中..."
    percent = min(100, int(completed * 100 / total))
    filled = min(10, percent // 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"下载进度 [{bar}] {percent}% ({completed}/{total})"


class DownloadProgressReporter:
    def __init__(self, loop: asyncio.AbstractEventLoop, send_text: Callable[[str], Awaitable[None]]):
        self.loop = loop
        self.send_text = send_text
        self.total = 0
        self.completed = 0
        self.last_milestone = -1
        self.lock = threading.Lock()

    def send_threadsafe(self, text: str) -> None:
        self.loop.call_soon_threadsafe(asyncio.create_task, self.send_text(text))

    def on_album(self, album) -> None:
        self.total = int(getattr(album, "page_count", 0) or 0)
        title = getattr(album, "name", "") or ""
        self.send_threadsafe(f"步骤 2/4 开始下载：《{title}》 共 {self.total} 张图片")

    def on_photo(self, photo) -> None:
        self.send_threadsafe(f"下载章节 {photo.index}/{len(photo.from_album)}：{photo.name}（{len(photo)} 张）")

    def on_image_cached(self) -> None:
        self._advance()

    def on_image_done(self) -> None:
        self._advance()

    def _advance(self) -> None:
        if self.total <= 0:
            return

        with self.lock:
            self.completed += 1
            percent = int(self.completed * 100 / self.total)
            milestone = min(100, (percent // 10) * 10)
            if milestone <= self.last_milestone:
                return
            self.last_milestone = milestone

        self.send_threadsafe(render_progress_bar(self.completed, self.total))

