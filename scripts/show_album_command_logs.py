#!/usr/bin/env python3
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.services.cache_service import init_db


def main() -> int:
    parser = argparse.ArgumentParser(description="Show recent album command logs from local SQLite.")
    parser.add_argument("--limit", type=int, default=10, help="Number of recent rows to show")
    args = parser.parse_args()

    init_db()
    conn = sqlite3.connect(settings.cache_db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, album_id, album_title, command_type, command_text, created_at
            FROM album_command_logs
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, args.limit),),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("No album command logs found.")
        return 0

    for row in rows:
        created_at_text = datetime.fromtimestamp(float(row["created_at"])).strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{row['id']}\t{created_at_text}\t{row['command_type']}\t"
            f"{row['album_id']}\t{row['album_title']}\t{row['command_text']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
