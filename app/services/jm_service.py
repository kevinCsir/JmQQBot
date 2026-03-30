#!/usr/bin/env python3
import random
from pathlib import Path

from app.config import settings
from utils.image_merge import collect_album_image_dirs, collect_images, count_album_images


def require_jmcomic():
    try:
        import jmcomic
    except ModuleNotFoundError as exc:
        raise RuntimeError("未安装 jmcomic 依赖，请先安装 requirements.txt") from exc
    return jmcomic


def create_option():
    jmcomic = require_jmcomic()
    return jmcomic.create_option_by_file(str(settings.jm_option_path))


def build_client():
    option = create_option()
    return option.build_jm_client()


def get_album_dir(album_id: str) -> Path:
    return settings.download_dir / album_id


def count_local_images(album_id: str) -> int:
    return count_album_images(get_album_dir(album_id))


def get_album_info_payload(album_id: str):
    client = build_client()
    album = client.get_album_detail(album_id)

    page_count = int(getattr(album, "page_count", 0) or 0)
    if page_count <= 0:
        local_count = count_local_images(album_id)
        if local_count > 0:
            page_count = local_count
        else:
            page_count = 0
            for photo_id, *_ in album.episode_list:
                photo = client.get_photo_detail(photo_id, fetch_album=False)
                page_count += len(photo)

    return album, page_count


def search_random(query: str, mode: str):
    client = build_client()
    collected = []
    seen = set()
    sampled_pages: list[int] = []

    first_page = _search_page(client, query, mode, 1)
    sampled_pages.append(1)
    _collect_search_page(first_page, collected, seen)

    max_page = min(max(int(getattr(first_page, "page_count", 1) or 1), 1), settings.tag_search_page_limit)
    candidate_pages = list(range(2, max_page + 1))
    random.shuffle(candidate_pages)

    for page in candidate_pages:
        result_page = _search_page(client, query, mode, page)
        sampled_pages.append(page)
        _collect_search_page(result_page, collected, seen)

        if len(sampled_pages) >= settings.tag_search_page_limit:
            break

    if not collected:
        return [], sampled_pages
    sample_size = min(settings.tag_search_result_count, len(collected))
    return random.sample(collected, sample_size), sampled_pages


def _search_page(client, query: str, mode: str, page: int):
    if mode == "tag":
        return client.search_tag(query, page=page)
    if mode == "author":
        return client.search_author(query, page=page)
    if mode == "work":
        return client.search_work(query, page=page)
    if mode == "actor":
        return client.search_actor(query, page=page)
    if mode == "site":
        return client.search_site(query, page=page)
    raise ValueError(f"Unsupported search mode: {mode}")


def _collect_search_page(result_page, collected, seen) -> None:
    for album_id, title, tags in result_page.iter_id_title_tag():
        if album_id in seen:
            continue
        seen.add(album_id)
        collected.append((album_id, title, tags))


def create_progress_downloader(reporter):
    jmcomic = require_jmcomic()

    class ProgressDownloader(jmcomic.JmDownloader):
        def before_album(self, album):
            super().before_album(album)
            reporter.on_album(album)

        def before_photo(self, photo):
            super().before_photo(photo)
            reporter.on_photo(photo)

        def before_image(self, image, img_save_path):
            super().before_image(image, img_save_path)
            if image.exists and self.option.decide_download_cache(image):
                reporter.on_image_cached()

        def after_image(self, image, img_save_path):
            super().after_image(image, img_save_path)
            reporter.on_image_done()

    return ProgressDownloader


def download_album(album_id: str, reporter) -> None:
    jmcomic = require_jmcomic()
    option = create_option()
    downloader = create_progress_downloader(reporter)
    jmcomic.download_album(album_id, option=option, downloader=downloader)
