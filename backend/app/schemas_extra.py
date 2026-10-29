"""Schemas for v2: resumable uploads, prompt planning and render."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class UploadInitRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    total_bytes: int = Field(gt=0)
    mime: str | None = None


class UploadSessionOut(BaseModel):
    upload_id: str
    received: int
    total_bytes: int
    chunk_size: int
    complete: bool


class PlanSegment(BaseModel):
    source_id: str
    source_name: str | None = None
    start: float
    end: float
    order: int
    title: str | None = None
    motion: Literal["static", "kenburns"] = "kenburns"
    quality: float = 1.0
    note: str | None = None


class SkippedSegment(BaseModel):
    source_id: str
    reason: str


class AutoPlan(BaseModel):
    """The edit decision list. Reviewed by the user before anything renders."""

    version: int = 1
    prompt: str
    width: int = 1920
    height: int = 1080
    fps: int = 30
    segments: list[PlanSegment] = Field(default_factory=list)
    skipped: list[SkippedSegment] = Field(default_factory=list)
    transitions: dict = Field(default_factory=lambda: {"type": "dissolve", "duration": 0.4})
    audio: dict = Field(default_factory=lambda: {"keep_original": False, "music_media_id": None})
    cards: dict = Field(default_factory=lambda: {"intro": None, "outro": None})
    grade: dict = Field(default_factory=lambda: {"mode": "auto"})
    estimated_seconds: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class PlanRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=4000)
    media_ids: list[str] = Field(min_length=1, max_length=200)
    music_media_id: str | None = None
    width: int = Field(default=1920, ge=480, le=3840)
    height: int = Field(default=1080, ge=480, le=2160)
    fps: int = Field(default=30, ge=12, le=60)


class RenderRequest(BaseModel):
    plan: AutoPlan
    music_media_id: str | None = None
