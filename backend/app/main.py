"""Media Studio API entrypoint.

Run locally:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Docs (Swagger):
    http://localhost:8000/docs
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .providers import get_provider
from .routers import auto, features, images, jobs_router, media, platform, tools, uploads, videos
from .services.video_ops import FFmpegError
from .services.bigupload import UploadManager
from .storage import MediaStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Image & video editing API with prompt-based (AI) editing.\n\n"
        "Media editing is instant; AI work returns a Job you poll at /v1/jobs/{id}."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.settings = settings
app.state.store = MediaStore(settings)
app.state.uploads = UploadManager(app.state.store, settings)

# Serve stored media. In production put a CDN or S3 in front of this.
app.mount("/files", StaticFiles(directory=str(app.state.store.root)), name="files")

app.include_router(media.router)
app.include_router(images.router)
app.include_router(videos.router)
app.include_router(jobs_router.router)
app.include_router(uploads.router)
app.include_router(auto.router)
app.include_router(features.router)
app.include_router(tools.router)
app.include_router(platform.router)


@app.exception_handler(FFmpegError)
async def ffmpeg_error_handler(request: Request, exc: FFmpegError) -> JSONResponse:
    """Missing binary / bad encode -> 503 with an actionable message."""
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "code": "video_engine_unavailable"},
    )


@app.get("/health", tags=["meta"])
async def health() -> dict:
    try:
        provider_name = get_provider(settings).name
    except Exception as exc:  # noqa: BLE001
        provider_name = f"misconfigured: {exc}"
    from .features import summary

    return {
        "status": "ok",
        "provider": provider_name,
        "storage_dir": str(app.state.store.root),
        "max_upload_gb": settings.max_upload_gb,
        "chunk_size_mb": settings.chunk_size_mb,
        "features": summary(),
    }


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}
