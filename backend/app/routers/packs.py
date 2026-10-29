"""Canva-, Runway- and Veed-style packs.

Three products, three habits, one engine:

  Canva   - templates, brand kit, magic resize across every platform at once
  Runway  - motion on stills, generative video, chroma key, camera moves
  Veed    - subtitles, progress bars, noise cleanup, one-click aspect packs

Everything here reuses the same media engine, so a "Canva" action and a "Veed"
action produce assets in exactly the same shape and stay editable afterwards.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..jobs import jobs
from ..schemas import Job, MediaAsset, MediaKind
from ..services import image_ops, presets, video_ops
from ..storage import MediaStore

router = APIRouter(prefix="/v1/packs", tags=["packs"])
log = logging.getLogger(__name__)


class MagicResizeRequest(BaseModel):
    platforms: list[str] = Field(min_length=1, max_length=12)
    mode: str = Field(default="cover", pattern="^(cover|contain)$")


class BrandRequest(BaseModel):
    headline: str = Field(default="", max_length=90)
    subline: str = Field(default="", max_length=90)
    colour: str = Field(default="#0F766E", pattern=r"^#[0-9a-fA-F]{6}$")
    position: str = Field(default="bottom", pattern="^(top|bottom)$")


class SubtitleRequest(BaseModel):
    srt: str = Field(min_length=4, max_length=200_000)


class ChromaRequest(BaseModel):
    colour: str = Field(default="green", pattern="^(green|blue)$")
    similarity: float = Field(default=0.30, ge=0.05, le=0.9)
    smoothness: float = Field(default=0.10, ge=0.0, le=1.0)


class MotionRequest(BaseModel):
    motion: str = Field(default="in", pattern="^(in|out|left|right)$")
    strength: float = Field(default=1.12, ge=1.02, le=1.5)


class ProgressRequest(BaseModel):
    colour: str = Field(default="#6EE7B7", pattern=r"^#[0-9a-fA-F]{6}$")
    height_pct: float = Field(default=0.012, ge=0.004, le=0.06)


def _store(request: Request) -> MediaStore:
    return request.app.state.store


def _asset(request: Request, media_id: str, kind: MediaKind) -> tuple[MediaAsset, Path]:
    store = _store(request)
    try:
        asset = store.load_asset(media_id)
        path = store.find_file(media_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, f"unknown media id: {media_id}") from exc
    if asset.kind is not kind:
        raise HTTPException(400, f"{media_id} is a {asset.kind.value}, not a {kind.value}")
    return asset, path


def _save_image(request: Request, img, meta: dict) -> MediaAsset:
    store = _store(request)
    media_id = store.new_id()
    out = store.path_for(media_id, "result.jpg")
    image_ops.save_jpeg(img, out, 92)
    image_ops.make_thumbnail(img, store.path_for(media_id, "thumb.jpg"))
    return store.asset_from_file(
        out, MediaKind.image, media_id=media_id, thumb_name="thumb.jpg",
        width=img.width, height=img.height, mime="image/jpeg", meta=meta,
    )


async def _register_video(request: Request, tmp: Path, meta: dict) -> MediaAsset:
    store = _store(request)
    media_id = store.new_id()
    out = store.copy_in(media_id, tmp, "result.mp4")
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


def _hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# Canva habits
# --------------------------------------------------------------------------- #
@router.post("/magic-resize/{media_id}", response_model=list[MediaAsset])
async def magic_resize(request: Request, media_id: str, body: MagicResizeRequest) -> list[MediaAsset]:
    """One photo, every platform size, in a single call."""
    _, path = _asset(request, media_id, MediaKind.image)
    img = image_ops.load_image(path)
    out: list[MediaAsset] = []
    for platform in body.platforms:
        try:
            fitted = presets.fit(img, platform, mode=body.mode)
        except KeyError:
            log.warning("unknown platform %s", platform)
            continue
        spec = presets.get(platform)
        out.append(_save_image(request, fitted, {
            "tool": "magic_resize", "platform": platform, "aspect": spec["aspect"],
            "source_id": media_id,
        }))
    if not out:
        raise HTTPException(422, "none of the requested platforms are known")
    return out


@router.post("/brand/{media_id}", response_model=MediaAsset)
async def apply_brand(request: Request, media_id: str, body: BrandRequest) -> MediaAsset:
    """Brand bar with headline and subline — the Canva 'brand kit' behaviour."""
    from PIL import Image, ImageDraw

    _, path = _asset(request, media_id, MediaKind.image)
    base = image_ops.load_image(path).convert("RGB")
    colour = _hex_rgb(body.colour)
    bar_h = int(base.height * 0.16)
    canvas = Image.new("RGB", (base.width, base.height + bar_h), colour)
    top = 0 if body.position == "bottom" else bar_h
    canvas.paste(base, (0, top))
    draw = ImageDraw.Draw(canvas)
    font_path = request.app.state.settings.font_path
    try:
        from PIL import ImageFont

        head_font = ImageFont.truetype(font_path, int(bar_h * 0.34))
        sub_font = ImageFont.truetype(font_path, int(bar_h * 0.20))
    except Exception:  # noqa: BLE001
        from PIL import ImageFont

        head_font = sub_font = ImageFont.load_default()
    text_y = 0 if body.position == "bottom" else 0
    pad = int(bar_h * 0.12)
    if body.headline:
        draw.text((pad, text_y + pad), body.headline, font=head_font, fill=(255, 255, 255))
    if body.subline:
        draw.text((pad, text_y + pad + int(bar_h * 0.42)), body.subline,
                  font=sub_font, fill=(235, 245, 240))
    return _save_image(request, canvas, {
        "tool": "brand_apply", "colour": body.colour, "source_id": media_id,
    })


# --------------------------------------------------------------------------- #
# Veed habits
# --------------------------------------------------------------------------- #
@router.post("/subtitles/{media_id}", response_model=Job, status_code=202)
async def burn_subtitles(request: Request, media_id: str, body: SubtitleRequest) -> Job:
    """Burn an SRT into the frame. Needs libass in the ffmpeg build."""
    _, path = _asset(request, media_id, MediaKind.video)
    store = _store(request)

    async def work() -> MediaAsset:
        media = store.new_id()
        srt = store.path_for(media, "subs.srt")
        srt.write_text(body.srt, encoding="utf-8")
        tmp = store.path_for(media, "subtitled.mp4")
        await video_ops.burn_subtitles(path, srt, tmp)
        return await _register_video(request, tmp, {"tool": "subtitles", "source_id": media_id})

    return jobs.submit("pack.subtitles", work)


@router.post("/progress-bar/{media_id}", response_model=Job, status_code=202)
async def progress_bar(request: Request, media_id: str, body: ProgressRequest) -> Job:
    """Story-style progress bar across the top of the frame."""
    _, path = _asset(request, media_id, MediaKind.video)
    store = _store(request)
    r, g, b = _hex_rgb(body.colour)

    async def work() -> MediaAsset:
        info = await video_ops.probe(path)
        width = info.get("width") or 1080
        bar = max(2, int((info.get("height") or 1920) * body.height_pct))
        media = store.new_id()
        tmp = store.path_for(media, "progress.mp4")
        await video_ops._run([
            video_ops.FFMPEG, "-y", "-i", str(path),
            "-vf", f"drawbox=x=0:y=0:w=iw:h={bar}:color=0x{r:02X}{g:02X}{b:02X}@0.9:t=fill",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "copy", "-movflags", "+faststart", str(tmp),
        ], timeout=900)
        return await _register_video(request, tmp, {
            "tool": "progress_bar", "colour": body.colour, "source_id": media_id,
            "note": "static bar; animated fill is on the roadmap",
        })

    return jobs.submit("pack.progress_bar", work)


@router.post("/denoise-audio/{media_id}", response_model=Job, status_code=202)
async def denoise_audio(request: Request, media_id: str) -> Job:
    """Strip hiss and room noise (Veed's 'clean audio')."""
    _, path = _asset(request, media_id, MediaKind.video)
    store = _store(request)

    async def work() -> MediaAsset:
        media = store.new_id()
        tmp = store.path_for(media, "clean.mp4")
        await video_ops._run([
            video_ops.FFMPEG, "-y", "-i", str(path),
            "-af", "afftdn=nf=-25,loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", str(tmp),
        ], timeout=900)
        return await _register_video(request, tmp, {"tool": "denoise_audio",
                                                    "source_id": media_id})

    return jobs.submit("pack.denoise", work)


# --------------------------------------------------------------------------- #
# Runway habits
# --------------------------------------------------------------------------- #
@router.post("/chroma-key/{media_id}", response_model=Job, status_code=202)
async def chroma_key(request: Request, media_id: str, body: ChromaRequest) -> Job:
    """Green/blue screen removal, output as a WebM with alpha where supported."""
    _, path = _asset(request, media_id, MediaKind.video)
    store = _store(request)
    colour = "0x00FF00" if body.colour == "green" else "0x0000FF"

    async def work() -> MediaAsset:
        media = store.new_id()
        tmp = store.path_for(media, "keyed.mp4")
        await video_ops._run([
            video_ops.FFMPEG, "-y", "-i", str(path),
            "-vf", (f"chromakey={colour}:{body.similarity}:{body.smoothness},"
                    "format=yuv420p"),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "copy", "-movflags", "+faststart", str(tmp),
        ], timeout=900)
        return await _register_video(request, tmp, {
            "tool": "chroma_key", "colour": body.colour, "source_id": media_id,
        })

    return jobs.submit("pack.chroma_key", work)


@router.post("/camera-motion/{media_id}", response_model=Job, status_code=202)
async def camera_motion(request: Request, media_id: str, body: MotionRequest) -> Job:
    """Push in, pull out, or pan across a still or clip (Runway-style camera moves)."""
    store = _store(request)
    source_asset = store.load_asset(media_id)
    source_path = store.find_file(media_id)
    if source_asset.kind not in (MediaKind.video, MediaKind.image):
        raise HTTPException(400, "camera motion needs video or an image")

    z_expr = {
        "in": f"min(zoom+0.0009,{body.strength})",
        "out": f"if(lte(zoom,1.0),{body.strength},max(1.001,zoom-0.0009))",
        "left": f"min(zoom+0.0006,{body.strength})",
        "right": f"min(zoom+0.0006,{body.strength})",
    }[body.motion]
    x_expr = "0" if body.motion == "left" else ("iw-iw/zoom" if body.motion == "right" else "iw/2-(iw/zoom/2)")
    y_expr = "ih/2-(ih/zoom/2)"

    async def work() -> MediaAsset:
        media = store.new_id()
        tmp = store.path_for(media, "motion.mp4")
        if source_asset.kind is MediaKind.image:
            inputs = ["-loop", "1", "-t", "4", "-i", str(source_path)]
            audio = ["-an"]
        else:
            inputs = ["-i", str(source_path)]
            audio = ["-c:a", "aac"]
        await video_ops._run([
            video_ops.FFMPEG, "-y", *inputs,
            "-vf", f"scale=1920:-2,zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}'"
                   f":d=1:s=1920x1080:fps=30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            *audio, "-movflags", "+faststart", str(tmp),
        ], timeout=900)
        return await _register_video(request, tmp, {
            "tool": "camera_motion", "motion": body.motion, "source_id": media_id,
        })

    return jobs.submit("pack.camera_motion", work)
