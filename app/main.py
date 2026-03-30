#!/usr/bin/env python3
import asyncio
from fastapi import FastAPI

from app.services.cache_service import enforce_cache_limit, init_db
from app.routes.files import router as files_router
from app.routes.qq_callback import router as qq_router


app = FastAPI()
app.include_router(qq_router)
app.include_router(files_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "AutoJm ready"}


@app.on_event("startup")
async def startup_maintenance() -> None:
    await asyncio.to_thread(init_db)
    await asyncio.to_thread(enforce_cache_limit)
