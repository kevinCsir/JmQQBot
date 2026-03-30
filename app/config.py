#!/usr/bin/env python3
import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    app_host: str = os.getenv("AUTOJM_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("AUTOJM_PORT", "8080"))
    qq_bot_app_id: str = os.getenv("QQ_BOT_APP_ID", "").strip()
    qq_bot_secret: str = os.getenv("QQ_BOT_SECRET", "").strip()
    qq_bot_is_sandbox: bool = os.getenv("QQ_BOT_IS_SANDBOX", "1").strip().lower() not in {"0", "false", "no"}
    download_dir: Path = ROOT_DIR / "downloads"
    longimg_dir: Path = ROOT_DIR / "downloads_longimg"
    pdf_dir: Path = ROOT_DIR / "downloads_pdf"
    jm_option_path: Path = ROOT_DIR / "app" / "jm_option.yml"
    default_preview_count: int = int(os.getenv("AUTOJM_DEFAULT_PREVIEW_COUNT", "5"))
    tag_search_page_limit: int = int(os.getenv("AUTOJM_TAG_SEARCH_PAGE_LIMIT", "3"))
    tag_search_result_count: int = int(os.getenv("AUTOJM_TAG_SEARCH_RESULT_COUNT", "5"))
    image_send_max_retries: int = int(os.getenv("AUTOJM_IMAGE_SEND_MAX_RETRIES", "3"))
    image_send_retry_delays: tuple[float, ...] = tuple(
        float(item)
        for item in os.getenv("AUTOJM_IMAGE_SEND_RETRY_DELAYS", "1,2,4").split(",")
        if item.strip()
    )
    image_send_interval_seconds: float = float(os.getenv("AUTOJM_IMAGE_SEND_INTERVAL_SECONDS", "0.8"))
    longimg_max_width: int = int(os.getenv("AUTOJM_LONGIMG_MAX_WIDTH", "720"))
    longimg_jpeg_quality: int = int(os.getenv("AUTOJM_LONGIMG_JPEG_QUALITY", "72"))
    auto_lru_cache_enabled: bool = os.getenv("AUTOJM_AUTO_LRU_CACHE", "1").strip().lower() not in {"0", "false", "no"}
    local_cache_limit_gb: float = float(os.getenv("AUTOJM_LOCAL_CACHE_LIMIT_GB", "5"))
    cache_db_path: Path = Path(os.getenv("AUTOJM_CACHE_DB_PATH", str(ROOT_DIR / ".autojm_cache.db")))
    legacy_cache_state_path: Path = ROOT_DIR / ".autojm_cache_state.json"


settings = Settings()
