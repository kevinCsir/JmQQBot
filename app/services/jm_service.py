#!/usr/bin/env python3
import random
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from utils.image_merge import CHUNK_SIZE, LongImagePlan, collect_album_image_dirs, collect_images, count_album_images


@dataclass(frozen=True)
class LongImageSelection:
    album_id: str
    album_title: str
    plans: tuple[LongImagePlan, ...]
    total_requested_images: int
    existing_image_count: int
    missing_image_count: int


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


def build_long_image_selection(album_id: str, start_index: int, end_index: int | None) -> LongImageSelection:
    client = build_client()
    option = create_option()
    album = client.get_album_detail(album_id)

    plans: list[LongImagePlan] = []
    total_requested_images = 0
    existing_image_count = 0
    missing_image_count = 0
    overall_index = 0

    for photo_id, *_ in album.episode_list:
        photo = client.get_photo_detail(photo_id, fetch_album=True)
        image_count = len(photo)
        if image_count <= 0:
            continue

        photo_label = str(getattr(photo, "index", photo.photo_id))
        for chunk_index, start_zero in enumerate(range(0, image_count, CHUNK_SIZE), start=1):
            overall_index += 1
            if overall_index < start_index:
                continue
            if end_index is not None and overall_index > end_index:
                return LongImageSelection(
                    album_id=album_id,
                    album_title=getattr(album, "name", "") or album_id,
                    plans=tuple(plans),
                    total_requested_images=total_requested_images,
                    existing_image_count=existing_image_count,
                    missing_image_count=missing_image_count,
                )

            end_zero = min(start_zero + CHUNK_SIZE, image_count)
            image_indices = tuple(range(start_zero + 1, end_zero + 1))
            source_paths = []
            for image_index in range(start_zero, end_zero):
                image = photo[image_index]
                source_path = Path(option.decide_image_filepath(image))
                source_paths.append(source_path)
                if source_path.exists():
                    existing_image_count += 1
                else:
                    missing_image_count += 1

            total_requested_images += len(source_paths)
            plans.append(
                LongImagePlan(
                    overall_index=overall_index,
                    photo_id=str(photo.photo_id),
                    photo_label=photo_label,
                    chunk_index=chunk_index,
                    start_page=start_zero + 1,
                    end_page=end_zero,
                    image_indices=image_indices,
                    source_paths=tuple(source_paths),
                    output_path=(
                        settings.longimg_dir
                        / album_id
                        / f"{photo_label}_part{chunk_index:03d}_{start_zero + 1:03d}-{end_zero:03d}.jpg"
                    ),
                )
            )

    return LongImageSelection(
        album_id=album_id,
        album_title=getattr(album, "name", "") or album_id,
        plans=tuple(plans),
        total_requested_images=total_requested_images,
        existing_image_count=existing_image_count,
        missing_image_count=missing_image_count,
    )


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
    sampled_results = random.sample(collected, sample_size)
    return _enrich_search_results_with_tags(client, sampled_results), sampled_pages


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


def _enrich_search_results_with_tags(client, results):
    enriched = []
    for album_id, title, tags in results:
        if tags:
            enriched.append((album_id, title, tags))
            continue
        try:
            album = client.get_album_detail(album_id)
            detail_tags = list(getattr(album, "tags", []) or [])
        except Exception:
            detail_tags = []
        enriched.append((album_id, title, detail_tags))
    return enriched


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


def create_targeted_downloader(reporter, target_photo_images: dict[str, set[int]]):
    jmcomic = require_jmcomic()
    base_downloader = create_progress_downloader(reporter)

    class TargetedDownloader(base_downloader):
        def do_filter(self, detail):
            if detail.is_album():
                selected_photos = []
                for photo in detail:
                    if str(photo.photo_id) in target_photo_images:
                        selected_photos.append(photo)
                return selected_photos

            if detail.is_photo():
                indices = sorted(target_photo_images.get(str(detail.photo_id), set()))
                if not indices:
                    return []
                selected_images = []
                for image_index in indices:
                    zero_based = image_index - 1
                    if 0 <= zero_based < len(detail):
                        selected_images.append(detail[zero_based])
                return selected_images

            return detail

    return TargetedDownloader


def download_album(album_id: str, reporter) -> None:
    jmcomic = require_jmcomic()
    option = create_option()
    downloader = create_progress_downloader(reporter)
    jmcomic.download_album(album_id, option=option, downloader=downloader)


def download_images_for_selection(selection: LongImageSelection, reporter) -> None:
    if selection.missing_image_count <= 0:
        return

    jmcomic = require_jmcomic()
    option = create_option()
    target_photo_images: dict[str, set[int]] = {}
    for plan in selection.plans:
        target_photo_images.setdefault(plan.photo_id, set()).update(plan.image_indices)

    reporter.set_scope(selection.total_requested_images, selection.album_title)
    downloader = create_targeted_downloader(reporter, target_photo_images)
    jmcomic.download_album(selection.album_id, option=option, downloader=downloader)
