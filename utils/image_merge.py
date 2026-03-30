#!/usr/bin/env python3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from PIL import Image

from app.config import settings


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
CHUNK_SIZE = 5
OUTPUT_SUFFIX = ".jpg"


@dataclass(frozen=True)
class LongImagePlan:
    overall_index: int
    photo_id: str
    photo_label: str
    chunk_index: int
    start_page: int
    end_page: int
    image_indices: tuple[int, ...]
    source_paths: tuple[Path, ...]
    output_path: Path


def collect_images(folder: Path) -> List[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def iter_image_dirs(album_dir: Path) -> Iterable[Path]:
    child_dirs = sorted(path for path in album_dir.iterdir() if path.is_dir())
    if child_dirs:
        return child_dirs
    return [album_dir]


def collect_album_image_dirs(album_dir: Path) -> List[Path]:
    return [folder for folder in iter_image_dirs(album_dir) if collect_images(folder)]


def count_album_images(album_dir: Path) -> int:
    if not album_dir.exists():
        return 0
    return sum(len(collect_images(folder)) for folder in collect_album_image_dirs(album_dir))


def expected_long_image_paths(album_dir: Path, output_root: Path) -> List[Path]:
    result: List[Path] = []
    if not album_dir.exists():
        return result

    for image_dir in collect_album_image_dirs(album_dir):
        image_paths = collect_images(image_dir)
        for idx, start in enumerate(range(0, len(image_paths), CHUNK_SIZE), start=1):
            chunk = image_paths[start : start + CHUNK_SIZE]
            result.append(
                output_root
                / album_dir.name
                / f"{image_dir.name}_part{idx:03d}_{start + 1:03d}-{start + len(chunk):03d}{OUTPUT_SUFFIX}"
            )

    return result


def needs_long_image_generation(album_dir: Path, output_root: Path) -> bool:
    expected = expected_long_image_paths(album_dir, output_root)
    if not expected:
        return True

    for image_path in expected:
        if not image_path.exists():
            return True

    newest_source = 0.0
    for folder in collect_album_image_dirs(album_dir):
        for image_path in collect_images(folder):
            newest_source = max(newest_source, image_path.stat().st_mtime)

    oldest_output = min(path.stat().st_mtime for path in expected)
    return newest_source > oldest_output


def merge_images_vertically(image_paths: List[Path], output_path: Path) -> None:
    images = [Image.open(path) for path in image_paths]
    resized: List[Image.Image] = []
    canvas: Image.Image | None = None
    try:
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS

        min_width = min(img.width for img in images)
        target_width = min(min_width, settings.longimg_max_width)
        total_height = 0
        for img in images:
            if img.width != target_width:
                new_height = int(img.height * target_width / img.width)
                current = img.resize((target_width, new_height), resample=resample)
            else:
                current = img.copy()
            current = current.convert("RGB")
            resized.append(current)
            total_height += current.height

        canvas = Image.new("RGB", (target_width, total_height))
        offset_y = 0
        for img in resized:
            canvas.paste(img, (0, offset_y))
            offset_y += img.height

        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(
            output_path,
            format="JPEG",
            quality=settings.longimg_jpeg_quality,
            optimize=True,
            progressive=True,
            subsampling="4:2:0",
        )
    finally:
        if canvas is not None:
            canvas.close()
        for img in resized:
            img.close()
        for img in images:
            img.close()


def output_needs_generation(output_path: Path, source_paths: Iterable[Path]) -> bool:
    source_paths = list(source_paths)
    if not source_paths:
        return False
    if not output_path.exists():
        return True

    try:
        output_mtime = output_path.stat().st_mtime
    except FileNotFoundError:
        return True

    newest_source = 0.0
    for path in source_paths:
        try:
            newest_source = max(newest_source, path.stat().st_mtime)
        except FileNotFoundError:
            return True

    return newest_source > output_mtime


def generate_long_images(album_dir: Path, output_root: Path) -> List[Path]:
    if not album_dir.exists():
        raise ValueError(f"未找到图片目录: {album_dir}")

    generated: List[Path] = []
    for image_dir in collect_album_image_dirs(album_dir):
        image_paths = collect_images(image_dir)
        for idx, start in enumerate(range(0, len(image_paths), CHUNK_SIZE), start=1):
            chunk = image_paths[start : start + CHUNK_SIZE]
            output_path = (
                output_root
                / album_dir.name
                / f"{image_dir.name}_part{idx:03d}_{start + 1:03d}-{start + len(chunk):03d}{OUTPUT_SUFFIX}"
            )
            merge_images_vertically(chunk, output_path)
            generated.append(output_path)

    if not generated:
        raise ValueError(f"未找到可拼接图片: {album_dir}")

    return generated
