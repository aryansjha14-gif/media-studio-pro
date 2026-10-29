"""Video endpoints: trim/merge/frame (ffmpeg, instant) and AI generate/restyle."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..jobs import jobs
from ..providers import get_provider
from ..schemas import (
    FrameRequest,
    GenerateVideoRequest,
    Job,
    MediaAsset,
    MediaKind,
    MergeRequest,
    TrimRequest,
    VideoPromptRequest,
)
from ..services import video_ops
from ..storage import MediaStore

router = APIRouter(prefix="/v1/videos", tags=["videos"])
log = logging.getLogger(__name__)


def store(request: Request) -> MediaStore:
    return request.app.state.store


def _require_video(s: MediaStore, media_id: str) -> tuple[MediaAsset, Path]:
    try:
        asset = s.load_asset(media_id)
        path = s.find_file(media_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, f"unknown media id: {media_id}") from exc
    if asset.kind is not MediaKind.video:
        raise HTTPException(400, f"{media_id} is a {asset.kind.value}, not a video")
    return asset, path


async def _save_video(s: MediaStore, src: Path, *, meta: dict) -> MediaAsset:
    media_id = s.new_id()
    out = s.copy_in(media_id, src, "result.mp4")
    thumb_name = None
    info: dict = {}
    try:
        info = await video_ops.probe(out)
        thumb = s.path_for(media_id, "thumb.jpg")
        await video_ops.thumbnail(out, thumb, at=min(1.0, (info.get("duration") or 1) / 2))
        thumb_name = "thumb.jpg"
    except Exception as exc:  # noqa: BLE001
        log.warning("post-process probe failed: %s", exc)
    return s.asset_from_file(
        out, MediaKind.video, media_id=media_id, thumb_name=thumb_name,
        width=info.get("width"), height=info.get("height"),
        duration=info.get("duration"), mime="video/mp4", meta=meta,
    )


@router.post("/{media_id}/trim", response_model=MediaAsset)
async def trim(request: Request, media_id: str, body: TrimRequest) -> MediaAsset:
    """Cut a clip. Fast enough to be synchronous."""
    s = store(request)
    asset, path = _require_video(s, media_id)
    duration = asset.duration or (await video_ops.probe(path)).get("duration") or 0
    end = min(body.end, duration) if duration else body.end
    if end <= body.start:
        raise HTTPException(400, f"end ({body.end}s) must be after start ({body.start}s)")
    tmp = s.path_for(media_id, "trim_tmp.mp4")
    try:
        await video_ops.trim(path, tmp, body.start, end, reencode=body.reencode)
        return await _save_video(
            s, tmp, meta={"tool": "trim", "source_id": media_id, "start": body.start, "end": end}
        )
    finally:
        tmp.unlink(missing_ok=True)


@router.post("/{media_id}/frame", response_model=MediaAsset)
async def extract_frame(request: Request, media_id: str, body: FrameRequest) -> MediaAsset:
    """Grab a still frame — the bridge from video to the image editor."""
    from ..services import image_ops

    s = store(request)
    _, path = _require_video(s, media_id)
    tmp = s.path_for(media_id, "frame_tmp.jpg")
    try:
        await video_ops.extract_frame(path, tmp, body.at)
        img = image_ops.load_image(tmp)
        media = s.new_id()
        out = s.path_for(media, "result.jpg")
        image_ops.save_jpeg(img, out)
        thumb = s.path_for(media, "thumb.jpg")
        image_ops.make_thumbnail(img, thumb)
        return s.asset_from_file(
            out, MediaKind.image, media_id=media, thumb_name="thumb.jpg",
            width=img.width, height=img.height, mime="image/jpeg",
            meta={"tool": "extract_frame", "source_id": media_id, "at": body.at},
        )
    finally:
        tmp.unlink(missing_ok=True)


@router.post("/merge", response_model=Job, status_code=202)
async def merge(request: Request, body: MergeRequest) -> Job:
    s = store(request)
    paths = [_require_video(s, mid)[1] for mid in body.media_ids]

    async def work() -> MediaAsset:
        media = s.new_id()
        tmp = s.path_for(media, "merge_tmp.mp4")
        await video_ops.merge(paths, tmp)
        return await _save_video(s, tmp, meta={"tool": "merge", "source_ids": body.media_ids})

    return jobs.submit("video.merge", work)


@router.post("/generate", response_model=Job, status_code=202)
async def generate(request: Request, body: GenerateVideoRequest) -> Job:
    """Text-to-video."""
    s = store(request)
    provider = get_provider(request.app.state.settings)

    async def work() -> MediaAsset:
        data = await provider.video_from_prompt(
            body.prompt,
            seconds=body.duration,
            aspect_ratio=body.aspect_ratio,
            negative=body.negative_prompt,
        )
        media = s.new_id()
        tmp = s.write_bytes(media, "provider_out.mp4", data)
        return await _save_video(
            s, tmp,
            meta={"tool": "video_generate", "prompt": body.prompt, "provider": provider.name},
        )

    return jobs.submit("video.generate", work)


@router.post("/{media_id}/prompt", response_model=Job, status_code=202)
async def prompt_edit(request: Request, media_id: str, body: VideoPromptRequest) -> Job:
    """Restyle / transform an existing clip with a prompt (video-to-video)."""
    s = store(request)
    _, path = _require_video(s, media_id)
    provider = get_provider(request.app.state.settings)
    source = path.read_bytes()

    async def work() -> MediaAsset:
        data = await provider.edit_video(source, body.prompt, negative=body.negative_prompt)
        media = s.new_id()
        tmp = s.write_bytes(media, "provider_out.mp4", data)
        return await _save_video(
            s, tmp,
            meta={
                "tool": "video_prompt",
                "prompt": body.prompt,
                "provider": provider.name,
                "source_id": media_id,
            },
        )

    return jobs.submit("video.prompt", work)
