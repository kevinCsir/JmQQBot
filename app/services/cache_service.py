#!/usr/bin/env python3
import json
import shutil
import sqlite3
import time
from pathlib import Path

from app.config import settings


def _now_ts() -> float:
    return time.time()


def _album_dirs(album_id: str) -> list[Path]:
    return [
        settings.download_dir / album_id,
        settings.longimg_dir / album_id,
        settings.pdf_dir / album_id,
    ]


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except FileNotFoundError:
                continue
    return total


def _album_size_bytes(album_id: str) -> int:
    return sum(_dir_size_bytes(path) for path in _album_dirs(album_id))


def total_cache_size_bytes() -> int:
    return _dir_size_bytes(settings.download_dir)


def _format_bytes(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(max(size_bytes, 0))
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"


def cache_usage_summary() -> str:
    current_size = total_cache_size_bytes()
    if not settings.auto_lru_cache_enabled:
        return f"当前缓存占用：{_format_bytes(current_size)}（LRU 自动清理已关闭）"

    limit_bytes = int(settings.local_cache_limit_gb * 1024 * 1024 * 1024)
    if limit_bytes <= 0:
        return f"当前缓存占用：{_format_bytes(current_size)}（未设置有效上限）"

    usage_percent = min(100, int(current_size * 100 / limit_bytes)) if limit_bytes > 0 else 0
    return (
        f"当前缓存占用：{_format_bytes(current_size)} / {_format_bytes(limit_bytes)} "
        f"（{usage_percent}%）"
    )


def _connect() -> sqlite3.Connection:
    db_path = settings.cache_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _log_event(conn: sqlite3.Connection, event_type: str, album_id: str | None, message: str) -> None:
    conn.execute(
        """
        INSERT INTO cache_events (event_type, album_id, message, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (event_type, album_id, message, _now_ts()),
    )


def _migrate_legacy_json_if_needed(conn: sqlite3.Connection) -> None:
    legacy_path = settings.legacy_cache_state_path
    if not legacy_path.exists():
        return

    row = conn.execute("SELECT COUNT(*) AS count FROM album_cache").fetchone()
    if row is not None and int(row["count"]) > 0:
        return

    try:
        data = json.loads(legacy_path.read_text(encoding="utf-8"))
    except Exception:
        _log_event(conn, "legacy_migration_failed", None, "旧缓存状态文件读取失败，已跳过迁移")
        return

    albums = data.get("albums", {}) if isinstance(data, dict) else {}
    if not isinstance(albums, dict):
        _log_event(conn, "legacy_migration_failed", None, "旧缓存状态文件格式异常，已跳过迁移")
        return

    migrated_count = 0
    for album_id, meta in albums.items():
        if not isinstance(album_id, str) or not isinstance(meta, dict):
            continue
        last_access_ts = float(meta.get("last_access_ts", _now_ts()) or _now_ts())
        size_bytes = int(meta.get("size_bytes", 0) or 0)
        conn.execute(
            """
            INSERT INTO album_cache (album_id, last_access_ts, size_bytes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(album_id) DO UPDATE SET
                last_access_ts = excluded.last_access_ts,
                size_bytes = excluded.size_bytes,
                updated_at = excluded.updated_at
            """,
            (album_id, last_access_ts, size_bytes, last_access_ts, _now_ts()),
        )
        migrated_count += 1

    if migrated_count > 0:
        _log_event(conn, "legacy_migrated", None, f"已从旧 json 缓存状态迁移 {migrated_count} 条记录")


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS album_cache (
                album_id TEXT PRIMARY KEY,
                last_access_ts REAL NOT NULL,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                album_id TEXT,
                message TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cache_events_created_at
            ON cache_events(created_at)
            """
        )
        _migrate_legacy_json_if_needed(conn)


def touch_album(album_id: str) -> None:
    if not settings.auto_lru_cache_enabled:
        return

    init_db()
    now_ts = _now_ts()
    size_bytes = _album_size_bytes(album_id)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO album_cache (album_id, last_access_ts, size_bytes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(album_id) DO UPDATE SET
                last_access_ts = excluded.last_access_ts,
                size_bytes = excluded.size_bytes,
                updated_at = excluded.updated_at
            """,
            (album_id, now_ts, size_bytes, now_ts, now_ts),
        )


def remove_album_cache(album_id: str) -> None:
    for path in _album_dirs(album_id):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def clear_all_cached_media() -> dict[str, int | str]:
    init_db()

    album_ids: set[str] = set()
    file_count = 0
    freed_size_bytes = 0
    roots = [settings.download_dir, settings.longimg_dir, settings.pdf_dir]

    for root in roots:
        if not root.exists():
            continue

        for child in root.iterdir():
            album_ids.add(child.name)

        for child in root.rglob("*"):
            if not child.is_file():
                continue
            file_count += 1
            try:
                freed_size_bytes += child.stat().st_size
            except FileNotFoundError:
                continue

        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)

    with _connect() as conn:
        conn.execute("DELETE FROM album_cache")
        _log_event(
            conn,
            "cache_cleared",
            None,
            f"手动清空全部图片缓存，删除 {len(album_ids)} 个目录、{file_count} 个文件，释放约 {freed_size_bytes} 字节",
        )

    return {
        "album_count": len(album_ids),
        "file_count": file_count,
        "freed_size_bytes": freed_size_bytes,
        "freed_size_text": _format_bytes(freed_size_bytes),
    }


def enforce_cache_limit() -> list[str]:
    if not settings.auto_lru_cache_enabled:
        return []

    limit_bytes = int(settings.local_cache_limit_gb * 1024 * 1024 * 1024)
    if limit_bytes <= 0:
        return []

    init_db()

    if settings.download_dir.exists():
        existing_album_ids = {path.name for path in settings.download_dir.iterdir() if path.is_dir()}
    else:
        existing_album_ids = set()

    now_ts = _now_ts()
    with _connect() as conn:
        known_rows = conn.execute("SELECT album_id FROM album_cache").fetchall()
        known_album_ids = {str(row["album_id"]) for row in known_rows}

        for album_id in known_album_ids - existing_album_ids:
            conn.execute("DELETE FROM album_cache WHERE album_id = ?", (album_id,))
            _log_event(conn, "cache_missing_cleanup", album_id, "缓存记录存在但本地资源目录已不存在，已移除记录")

        for album_id in existing_album_ids:
            conn.execute(
                """
                INSERT INTO album_cache (album_id, last_access_ts, size_bytes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(album_id) DO UPDATE SET
                    size_bytes = excluded.size_bytes,
                    updated_at = excluded.updated_at
                """,
                (album_id, now_ts, _album_size_bytes(album_id), now_ts, now_ts),
            )

        deleted: list[str] = []
        current_size = total_cache_size_bytes()
        if current_size <= limit_bytes:
            return deleted

        rows = conn.execute(
            """
            SELECT album_id, last_access_ts, size_bytes
            FROM album_cache
            ORDER BY last_access_ts ASC, album_id ASC
            """
        ).fetchall()

        for row in rows:
            if current_size <= limit_bytes:
                break

            album_id = str(row["album_id"])
            freed = _album_size_bytes(album_id)
            remove_album_cache(album_id)
            conn.execute("DELETE FROM album_cache WHERE album_id = ?", (album_id,))
            deleted.append(album_id)
            current_size = max(0, current_size - freed)
            _log_event(conn, "cache_evicted", album_id, f"按 LRU 清理缓存，释放约 {freed} 字节")

        return deleted


def list_cache_events(limit: int = 50) -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, event_type, album_id, message, created_at
            FROM cache_events
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
