#!/usr/bin/env python3
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AlbumSendCommand:
    album_id: str
    range_text: str
    start_index: int
    end_index: int | None


@dataclass(frozen=True)
class AlbumInfoCommand:
    album_id: str
    source: str = "direct"
    original_text: str = ""


@dataclass(frozen=True)
class SearchCommand:
    mode: str
    query: str


@dataclass(frozen=True)
class HelpCommand:
    pass


ParsedCommand = AlbumSendCommand | AlbumInfoCommand | SearchCommand | HelpCommand | None


def parse_album_command(content: str) -> AlbumSendCommand | AlbumInfoCommand | None:
    matched = re.fullmatch(r"(\d+)(?:\s+(.+))?", content.strip(), flags=re.IGNORECASE)
    if not matched:
        return None

    album_id = matched.group(1)
    suffix = (matched.group(2) or "").strip().lower()
    if not suffix:
        return AlbumSendCommand(album_id=album_id, range_text="default", start_index=1, end_index=5)
    if suffix in {"info", "if"}:
        return AlbumInfoCommand(album_id=album_id)
    if suffix in {"all", "al"}:
        return AlbumSendCommand(album_id=album_id, range_text="all", start_index=1, end_index=None)
    if suffix.isdigit():
        index = int(suffix)
        if index <= 0:
            return None
        return AlbumSendCommand(album_id=album_id, range_text=suffix, start_index=index, end_index=index)

    range_match = re.fullmatch(r"(\d*)-(\d*)", suffix)
    if not range_match:
        return None

    start_text, end_text = range_match.groups()
    if not start_text and not end_text:
        return None

    start_index = int(start_text) if start_text else 1
    end_index = int(end_text) if end_text else None
    if start_index <= 0:
        return None
    if end_index is not None and end_index <= 0:
        return None
    if end_index is not None and end_index < start_index:
        return None

    return AlbumSendCommand(album_id=album_id, range_text=suffix, start_index=start_index, end_index=end_index)


def parse_search_command(content: str) -> SearchCommand | None:
    matched = re.fullmatch(
        r"(?:search|sr)(?:\s+(tag|tg|author|au|work|wk|actor|ac|site|st))?\s+(.+)",
        content.strip(),
        flags=re.IGNORECASE,
    )
    if not matched:
        return None
    mode = (matched.group(1) or "site").strip().lower()
    query = matched.group(2).strip()
    if not query:
        return None
    mode_alias_map = {
        "tg": "tag",
        "au": "author",
        "wk": "work",
        "ac": "actor",
        "st": "site",
    }
    mode = mode_alias_map.get(mode, mode)
    return SearchCommand(mode=mode, query=query)


def parse_filter_info_command(content: str) -> AlbumInfoCommand | None:
    matched = re.fullmatch(r"(?:guolv|filter|fl)\s+(.+)", content.strip(), flags=re.IGNORECASE)
    if not matched:
        return None

    original_text = matched.group(1).strip()
    digits = "".join(re.findall(r"\d+", original_text))
    if not digits:
        return None

    return AlbumInfoCommand(album_id=digits, source="filter", original_text=original_text)


def parse_help_command(content: str) -> HelpCommand | None:
    if re.fullmatch(r"(?:help|hp)", content.strip(), flags=re.IGNORECASE):
        return HelpCommand()
    return None


def parse_command(content: str) -> ParsedCommand:
    return (
        parse_help_command(content)
        or parse_filter_info_command(content)
        or parse_search_command(content)
        or parse_album_command(content)
    )
