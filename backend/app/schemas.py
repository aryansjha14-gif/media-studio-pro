"""Pydantic request/response models — this is the API contract the Android
client is generated against (see docs/API.md)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MediaKind(str, Enum):
    image = "image"
    video = "video"


class MediaAsset(BaseModel):
    """A piece of media stored on the server (original, edited or generated)."""

    id: str
    kind: MediaKind
    url: str
    thumb_url: str | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    size_bytes: int | None = None
    mime: str | None = None
    created_at: datetime = Field(default_factory=_now)
    # Free-form provenance: which tool/prompt/provider produced this asset.
    meta: dict[str, Any] = Field(default_factory=dict)


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Job(BaseModel):
    """Long-running AI work (prompt edits, generation, upscaling)."""

    id: str
    kind: str
    status: JobStatus = JobStatus.queued
    progress: float = 0.0
    asset: MediaAsset | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# --------------------------------------------------------------------------- #
# Image editing
# --------------------------------------------------------------------------- #

class CropBox(BaseModel):
    """Pixel crop relative to the current image."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ResizeSpec(BaseModel):
    width: int | None = Field(default=None, gt=0, le=8192)
    height: int | None = Field(default=None, gt=0, le=8192)
    fit: Literal["cover", "contain", "stretch"] = "cover"


class AdjustRequest(BaseModel):
    """Deterministic, non-AI image adjustments. All fields optional."""

    crop: CropBox | None = None
    rotate: float | None = Field(default=None, description="Degrees, clockwise")
    flip_horizontal: bool = False
    flip_vertical: bool = False
    resize: ResizeSpec | None = None
    brightness: float = Field(default=1.0, ge=0.0, le=3.0)
    contrast: float = Field(default=1.0, ge=0.0, le=3.0)
    saturation: float = Field(default=1.0, ge=0.0, le=3.0)
    sharpness: float = Field(default=1.0, ge=0.0, le=3.0)
    blur: float = Field(default=0.0, ge=0.0, le=20.0)
    filter: Literal[
        "none", "grayscale", "sepia", "warm", "cool", "vintage", "punch", "mono"
    ] = "none"
    quality: int = Field(default=92, ge=40, le=100)


class PromptEditRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=2000)
    # Optional mask (white = editable area) as another media id.
    mask_media_id: str | None = None
    negative_prompt: str | None = None
    guidance: float | None = Field(default=None, ge=0.0, le=20.0)


class GenerateImageRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=2000)
    negative_prompt: str | None = None
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    steps: int = Field(default=4, ge=1, le=50)


# --------------------------------------------------------------------------- #
# Video editing
# --------------------------------------------------------------------------- #

class TrimRequest(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    reencode: bool = True


class FrameRequest(BaseModel):
    at: float = Field(ge=0)


class MergeRequest(BaseModel):
    media_ids: list[str] = Field(min_length=2)


class VideoPromptRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=2000)
    negative_prompt: str | None = None


class GenerateVideoRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=2000)
    negative_prompt: str | None = None
    duration: int = Field(default=5, ge=2, le=10)
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
