"""Upload + asset lookup."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile
from PIL import Image

from ..config import get_settings
from ..schemas import MediaAsset, MediaKind
from ..services import image_ops, video_ops
from ..storage import MediaStore

router = APIRouter(prefix="/v1/media", tags=["media"])
log = logging.getLogger(__name__)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".3gp"}


def store(request: Request) -> MediaStore:
    return request.app.state.store


@router.post("", response_model=MediaAsset, status_code=201)
async def upload(request: Request, file: UploadFile) -> MediaAsset:
    """Upload an image or video. Returns the asset the app then edits."""
    settings = get_settings()
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"file exceeds {settings.max_upload_gb} GB limit")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix in VIDEO_EXT or (file.content_type or "").startswith("video/"):
        kind = MediaKind.video
    elif suffix in IMAGE_EXT or (file.content_type or "").startswith("image/"):
        kind = MediaKind.image
    else:
        raise HTTPException(415, f"unsupported file type: {suffix or file.content_type}")

    s = store(request)
    media_id = s.new_id()
    raw_path = s.write_bytes(media_id, f"upload{suffix or ('.mp4' if kind is MediaKind.video else '.jpg')}", data)

    if kind is MediaKind.image:
        try:
            img = image_ops.load_image(raw_path)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(415, f"could not read image: {exc}") from exc
        thumb = s.path_for(media_id, "thumb.jpg")
        image_ops.make_thumbnail(img, thumb)
        return s.asset_from_file(
            raw_path, kind, media_id=media_id, thumb_name="thumb.jpg",
            width=img.width, height=img.height,
            mime=file.content_type, meta={"original_filename": file.filename},
        )

    try:
        info = await video_ops.probe(raw_path)
        thumb = s.path_for(media_id, "thumb.jpg")
        await video_ops.thumbnail(raw_path, thumb, at=min(1.0, (info.get("duration") or 1) / 2))
        thumb_name = "thumb.jpg"
    except Exception as exc:  # noqa: BLE001 — ffmpeg may be missing on a dev box
        log.warning("video probe/thumbnail failed: %s", exc)
        info, thumb_name = {}, None

    return s.asset_from_file(
        raw_path, kind, media_id=media_id, thumb_name=thumb_name,
        width=info.get("width"), height=info.get("height"),
        duration=info.get("duration"), mime=file.content_type,
        meta={"original_filename": file.filename, "fps": info.get("fps"), "codec": info.get("codec")},
    )


@router.get("/{media_id}", response_model=MediaAsset)
async def get_asset(request: Request, media_id: str) -> MediaAsset:
    try:
        return store(request).load_asset(media_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
