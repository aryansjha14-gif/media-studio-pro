"""One endpoint per editing tool, plus a single prompt endpoint that chains them.

Everything here is deterministic work on the server: instant, free, and safe to
expose to a free tier. The prompt endpoint is the interesting one — it turns a
sentence into a chain of these tools, which is how "make it brighter and add a
watermark" becomes two real operations instead of a shrug.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..jobs import jobs
from ..schemas import AdjustRequest, Job, MediaAsset, MediaKind
from ..services import image_ops, video_ops
from ..storage import MediaStore

router = APIRouter(prefix="/v1/tools", tags=["tools"])
log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# request bodies
# --------------------------------------------------------------------------- #
class CurvesRequest(BaseModel):
    points: list[tuple[int, int]] = Field(min_length=2, max_length=12)


class HslRequest(BaseModel):
    hue_shift: float = Field(default=0.0, ge=-180, le=180)
    saturation: float = Field(default=1.0, ge=0, le=3)
    lightness: float = Field(default=1.0, ge=0, le=3)


class VignetteRequest(BaseModel):
    amount: float = Field(default=0.35, ge=0, le=1)
    feather: float = Field(default=1.4, ge=0.5, le=2)


class GrainRequest(BaseModel):
    strength: float = Field(default=0.06, ge=0, le=0.4)


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    position: str = Field(default="bottom", pattern="^(top|center|bottom)$")
    size_ratio: float = Field(default=0.06, ge=0.02, le=0.2)


class WatermarkRequest(BaseModel):
    text: str = Field(min_length=1, max_length=80)
    opacity: float = Field(default=0.45, ge=0.05, le=1)


class FrameRequest(BaseModel):
    width_ratio: float = Field(default=0.04, ge=0.005, le=0.2)


class CollageRequest(BaseModel):
    media_ids: list[str] = Field(min_length=2, max_length=9)
    columns: int = Field(default=2, ge=1, le=3)


class BatchRequest(BaseModel):
    media_ids: list[str] = Field(min_length=1, max_length=100)
    adjust: AdjustRequest = Field(default_factory=AdjustRequest)


class SpeedRequest(BaseModel):
    factor: float = Field(default=2.0, ge=0.25, le=4.0)


class ReframeRequest(BaseModel):
    aspect: str = Field(default="9:16", pattern=r"^\d{1,2}:\d{1,2}$")


class NormaliseRequest(BaseModel):
    lufs: float = Field(default=-14.0, ge=-30, le=-8)


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=1000)
    media_id: str


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _store(request: Request) -> MediaStore:
    return request.app.state.store


def _image(request: Request, media_id: str) -> tuple[MediaAsset, Path]:
    store = _store(request)
    try:
        asset = store.load_asset(media_id)
        path = store.find_file(media_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, f"unknown media id: {media_id}") from exc
    if asset.kind is not MediaKind.image:
        raise HTTPException(400, f"{media_id} is not an image")
    return asset, path


def _video(request: Request, media_id: str) -> tuple[MediaAsset, Path]:
    store = _store(request)
    try:
        asset = store.load_asset(media_id)
        path = store.find_file(media_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, f"unknown media id: {media_id}") from exc
    if asset.kind is not MediaKind.video:
        raise HTTPException(400, f"{media_id} is not a video")
    return asset, path


def _save_image(request: Request, img, *, tool: str, source_id: str, extra: dict | None = None) -> MediaAsset:
    store = _store(request)
    media_id = store.new_id()
    out = store.path_for(media_id, "result.png")
    image_ops.save_png(img, out)
    thumb = store.path_for(media_id, "thumb.jpg")
    image_ops.make_thumbnail(img, thumb)
    return store.asset_from_file(
        out, MediaKind.image, media_id=media_id, thumb_name="thumb.jpg",
        width=img.width, height=img.height, mime="image/png",
        meta={"tool": tool, "source_id": source_id, **(extra or {})},
    )


# --------------------------------------------------------------------------- #
# image tools
# --------------------------------------------------------------------------- #
@router.post("/image/{media_id}/curves", response_model=MediaAsset)
async def curves(request: Request, media_id: str, body: CurvesRequest) -> MediaAsset:
    """RGB tone curve. Points are (input, output) on a 0-255 scale."""
    _, path = _image(request, media_id)
    img = image_ops.apply_curves(image_ops.load_image(path), body.points)
    return _save_image(request, img, tool="curves", source_id=media_id,
                       extra={"points": len(body.points)})


@router.post("/image/{media_id}/hsl", response_model=MediaAsset)
async def hsl(request: Request, media_id: str, body: HslRequest) -> MediaAsset:
    _, path = _image(request, media_id)
    img = image_ops.apply_hsl(
        image_ops.load_image(path), body.hue_shift, body.saturation, body.lightness
    )
    return _save_image(request, img, tool="hsl", source_id=media_id)


@router.post("/image/{media_id}/vignette", response_model=MediaAsset)
async def vignette(request: Request, media_id: str, body: VignetteRequest) -> MediaAsset:
    _, path = _image(request, media_id)
    img = image_ops.add_vignette(image_ops.load_image(path), body.amount, body.feather)
    return _save_image(request, img, tool="vignette", source_id=media_id)


@router.post("/image/{media_id}/grain", response_model=MediaAsset)
async def grain(request: Request, media_id: str, body: GrainRequest) -> MediaAsset:
    _, path = _image(request, media_id)
    img = image_ops.add_grain(image_ops.load_image(path), body.strength)
    return _save_image(request, img, tool="grain", source_id=media_id)


@router.post("/image/{media_id}/text", response_model=MediaAsset)
async def add_text(request: Request, media_id: str, body: TextRequest) -> MediaAsset:
    _, path = _image(request, media_id)
    img = image_ops.draw_text(
        image_ops.load_image(path), body.text, position=body.position,
        size_ratio=body.size_ratio, font_path=request.app.state.settings.font_path,
    )
    return _save_image(request, img, tool="text", source_id=media_id, extra={"text": body.text})


@router.post("/image/{media_id}/watermark", response_model=MediaAsset)
async def add_watermark(request: Request, media_id: str, body: WatermarkRequest) -> MediaAsset:
    _, path = _image(request, media_id)
    img = image_ops.watermark(image_ops.load_image(path), body.text, body.opacity)
    return _save_image(request, img, tool="watermark", source_id=media_id)


@router.post("/image/{media_id}/frame", response_model=MediaAsset)
async def add_frame(request: Request, media_id: str, body: FrameRequest) -> MediaAsset:
    _, path = _image(request, media_id)
    img = image_ops.add_frame(image_ops.load_image(path), body.width_ratio)
    return _save_image(request, img, tool="frame", source_id=media_id)


@router.post("/image/{media_id}/auto-enhance", response_model=MediaAsset)
async def auto_enhance(request: Request, media_id: str) -> MediaAsset:
    _, path = _image(request, media_id)
    img, report = image_ops.auto_enhance(image_ops.load_image(path))
    return _save_image(request, img, tool="auto_enhance", source_id=media_id, extra=report)


@router.post("/collage", response_model=MediaAsset)
async def make_collage(request: Request, body: CollageRequest) -> MediaAsset:
    images = [image_ops.load_image(_image(request, mid)[1]) for mid in body.media_ids]
    img = image_ops.collage(images, columns=body.columns)
    return _save_image(request, img, tool="collage", source_id=body.media_ids[0],
                       extra={"tiles": len(images)})


@router.post("/batch", response_model=list[MediaAsset])
async def batch_adjust(request: Request, body: BatchRequest) -> list[MediaAsset]:
    """Apply one set of adjustments to many photos in a single call."""
    out: list[MediaAsset] = []
    for media_id in body.media_ids:
        _, path = _image(request, media_id)
        img = image_ops.apply_adjustments(image_ops.load_image(path), body.adjust)
        out.append(_save_image(request, img, tool="batch_adjust", source_id=media_id))
    return out


# --------------------------------------------------------------------------- #
# video tools
# --------------------------------------------------------------------------- #
@router.post("/video/{media_id}/speed", response_model=Job, status_code=202)
async def speed(request: Request, media_id: str, body: SpeedRequest) -> Job:
    _, path = _video(request, media_id)
    store = _store(request)

    async def work() -> MediaAsset:
        media = store.new_id()
        tmp = store.path_for(media, "speed.mp4")
        await video_ops.apply_speed(path, tmp, body.factor)
        return await _register_video(request, tmp, {"tool": "speed", "factor": body.factor,
                                                    "source_id": media_id})

    return jobs.submit("video.speed", work)


@router.post("/video/{media_id}/reverse", response_model=Job, status_code=202)
async def reverse(request: Request, media_id: str) -> Job:
    _, path = _video(request, media_id)
    store = _store(request)

    async def work() -> MediaAsset:
        media = store.new_id()
        tmp = store.path_for(media, "reverse.mp4")
        await video_ops.reverse(path, tmp)
        return await _register_video(request, tmp, {"tool": "reverse", "source_id": media_id})

    return jobs.submit("video.reverse", work)


@router.post("/video/{media_id}/reframe", response_model=Job, status_code=202)
async def reframe(request: Request, media_id: str, body: ReframeRequest) -> Job:
    """Re-crop to a target aspect ratio, centred (9:16 for Reels)."""
    asset, path = _video(request, media_id)
    store = _store(request)
    w_ratio, h_ratio = (int(x) for x in body.aspect.split(":"))
    target = w_ratio / h_ratio

    async def work() -> MediaAsset:
        info = await video_ops.probe(path)
        src_w = info.get("width") or asset.width or 1080
        src_h = info.get("height") or asset.height or 1920
        current = src_w / src_h
        if current > target:
            crop_w, crop_h = int(src_h * target), src_h
        else:
            crop_w, crop_h = src_w, int(src_w / target)
        media = store.new_id()
        tmp = store.path_for(media, "reframe.mp4")
        await video_ops._run([
            video_ops.FFMPEG, "-y", "-i", str(path),
            "-vf", f"crop={crop_w}:{crop_h},scale={crop_w}:{crop_h}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-movflags", "+faststart", str(tmp),
        ], timeout=600)
        return await _register_video(request, tmp, {"tool": "reframe", "aspect": body.aspect,
                                                    "source_id": media_id})

    return jobs.submit("video.reframe", work)


@router.post("/video/{media_id}/audio/extract", response_model=MediaAsset)
async def extract_audio(request: Request, media_id: str) -> MediaAsset:
    _, path = _video(request, media_id)
    store = _store(request)
    media = store.new_id()
    out = store.path_for(media, "audio.m4a")
    await video_ops._run([
        video_ops.FFMPEG, "-y", "-i", str(path), "-vn", "-c:a", "aac",
        "-b:a", "192k", str(out),
    ], timeout=300)
    return store.asset_from_file(
        out, MediaKind.video, media_id=media, mime="audio/mp4",
        meta={"tool": "extract_audio", "source_id": media_id, "kind": "audio"},
    )


@router.post("/video/{media_id}/audio/normalise", response_model=Job, status_code=202)
async def normalise_audio(request: Request, media_id: str, body: NormaliseRequest) -> Job:
    _, path = _video(request, media_id)
    store = _store(request)

    async def work() -> MediaAsset:
        media = store.new_id()
        tmp = store.path_for(media, "normalised.mp4")
        await video_ops._run([
            video_ops.FFMPEG, "-y", "-i", str(path),
            "-af", f"loudnorm=I={body.lufs}:TP=-1.5:LRA=11",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", str(tmp),
        ], timeout=600)
        return await _register_video(request, tmp, {"tool": "loudnorm", "lufs": body.lufs,
                                                    "source_id": media_id})

    return jobs.submit("video.loudnorm", work)


async def _register_video(request: Request, path: Path, meta: dict) -> MediaAsset:
    store = _store(request)
    media_id = store.new_id()
    out = store.copy_in(media_id, path, "result.mp4")
    thumb_name = None
    info: dict = {}
    try:
        info = await video_ops.probe(out)
        await video_ops.thumbnail(out, store.path_for(media_id, "thumb.jpg"),
                                  at=min(1.0, (info.get("duration") or 1) / 2))
        thumb_name = "thumb.jpg"
    except Exception as exc:  # noqa: BLE001
        log.warning("probe failed: %s", exc)
    return store.asset_from_file(
        out, MediaKind.video, media_id=media_id, thumb_name=thumb_name,
        width=info.get("width"), height=info.get("height"),
        duration=info.get("duration"), mime="video/mp4", meta=meta,
    )


# --------------------------------------------------------------------------- #
# prompt -> chain of tools
# --------------------------------------------------------------------------- #
IMAGE_INTENTS: list[tuple[str, str, dict]] = [
    (r"bright|light|dark|expos", "brightness", {"brightness": 1.15}),
    (r"contrast|punchy", "contrast", {"contrast": 1.12}),
    (r"black and white|monochrome|b&w|grayscale", "filter", {"filter": "grayscale"}),
    (r"sepia|vintage|old", "filter", {"filter": "sepia"}),
    (r"warm", "filter", {"filter": "warm"}),
    (r"cool|cold|blue", "filter", {"filter": "cool"}),
    (r"sharpen|sharp", "sharpness", {"sharpness": 1.3}),
    (r"vignette", "vignette", {}),
    (r"grain|film", "grain", {}),
    (r"watermark", "watermark", {}),
    (r"enhance|improve|better", "auto_enhance", {}),
]


@router.post("/prompt/execute", response_model=Job, status_code=202)
async def execute_prompt(request: Request, body: PromptRequest) -> Job:
    """Apply a sentence as a chain of real operations.

    Deterministic intents (brightness, filters, vignette, grain, watermark) run
    locally and cost nothing. Anything that needs a model is left for the AI
    endpoints, and the job report says which parts were handled where — so the
    app never claims a generative edit it did not perform.
    """
    asset, path = _image(request, body.media_id)
    store = _store(request)
    prompt = body.prompt.lower()

    async def work() -> MediaAsset:
        img = image_ops.load_image(path)
        applied: list[str] = []

        adjust_kwargs: dict = {}
        for pattern, op, params in IMAGE_INTENTS:
            if not re.search(pattern, prompt):
                continue
            if op in ("brightness", "contrast", "sharpness"):
                adjust_kwargs.update(params)
            elif op == "filter":
                adjust_kwargs["filter"] = params["filter"]
            elif op == "vignette":
                img = image_ops.add_vignette(img)
                applied.append("vignette")
            elif op == "grain":
                img = image_ops.add_grain(img)
                applied.append("grain")
            elif op == "watermark":
                img = image_ops.watermark(img, "SAMPLE")
                applied.append("watermark")
            elif op == "auto_enhance":
                img, _ = image_ops.auto_enhance(img)
                applied.append("auto_enhance")

        if adjust_kwargs:
            img = image_ops.apply_adjustments(img, AdjustRequest(**adjust_kwargs))
            applied.extend(adjust_kwargs)

        if not applied:
            raise ValueError(
                "no deterministic edit matched that prompt; use /v1/images/{id}/prompt "
                "for generative edits"
            )

        return _save_image(request, img, tool="prompt_execute", source_id=body.media_id,
                           extra={"prompt": body.prompt, "applied": applied})

    return jobs.submit("prompt.execute", work)
