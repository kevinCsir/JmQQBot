#!/usr/bin/env python3
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import ROOT_DIR, settings


router = APIRouter()
FILE_SERVE_ROOTS = [settings.longimg_dir]


@router.get("/files/{file_path:path}")
async def serve_file(file_path: str) -> FileResponse:
    target = (ROOT_DIR / file_path).resolve()
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    for allowed_root in FILE_SERVE_ROOTS:
        try:
            target.relative_to(Path(allowed_root).resolve())
            return FileResponse(target)
        except ValueError:
            continue

    raise HTTPException(status_code=403, detail="Forbidden path")

