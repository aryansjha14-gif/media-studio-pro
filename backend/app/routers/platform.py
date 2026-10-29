"""Creator platform packs, Snapchat-style lenses, and feature search.

Platform packs answer the question every creator has to answer per upload: what
aspect ratio, what safe area, what export size. Lenses give the visual looks.
Search makes 285 functions findable instead of buried.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..features import all_features, search
from ..jobs import jobs
from ..schemas import Job, MediaAsset, MediaKind
from ..services import image_ops, lenses, presets, video_ops
from ..storage import MediaStore

router = APIRouter(prefix="/v1", tags=["platform"])
log = logging.getLogger(__name__)


class StickerRequest(BaseModel):
    text: str = Field(min_length=1, max_length=120)
    style: str = Field(default="caption", pattern="^(caption|timestamp)$")


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


def _save_image(request: Request, img, *, meta: dict) -> MediaAsset:
    store = _store(request)
    media_id = store.new_id()
    out = store.path_for(media_id, "result.jpg")
    image_ops.save_jpeg(img, out, 92)
    thumb = store.path_for(media_id, "thumb.jpg")
    image_ops.make_thumbnail(img, thumb)
    return store.asset_from_file(
        out, MediaKind.image, media_id=media_id, thumb_name="thumb.jpg",
        width=img.width, height=img.height, mime="image/jpeg", meta=meta,
    )


# --------------------------------------------------------------------------- #
# platform packs
# --------------------------------------------------------------------------- #
@router.get("/platforms")
async def list_platforms() -> list[dict]:
    """Every platform frame with its size, aspect and safe areas."""
    return [presets.get(name) for name in presets.PLATFORMS]


@router.post("/platforms/{name}/image/{media_id}", response_model=MediaAsset)
async def fit_image(request: Request, name: str, media_id: str,
                    mode: str = Query(default="cover", pattern="^(cover|contain)$")) -> MediaAsset:
    """Crop or letterbox a photo into a platform's exact frame."""
    _, path = _asset(request, media_id, MediaKind.image)
    try:
        spec = presets.get(name)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    img = presets.fit(image_ops.load_image(path), name, mode=mode)
    return _save_image(request, img, meta={
        "tool": "platform_fit", "platform": name, "aspect": spec["aspect"],
        "source_id": media_id, "safe": spec["safe"],
    })


@router.post("/platforms/{name}/video/{media_id}", response_model=Job, status_code=202)
async def fit_video(request: Request, name: str, media_id: str) -> Job:
    """Reframe a video to a platform's frame (this is the Reels / Shorts path)."""
    _, path = _asset(request, media_id, MediaKind.video)
    try:
        spec = presets.get(name)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    store = _store(request)

    async def work() -> MediaAsset:
        w, h = spec["width"], spec["height"]
        media = store.new_id()
        tmp = store.path_for(media, "fit.mp4")
        await video_ops._run([
            video_ops.FFMPEG, "-y", "-i", str(path),
            "-vf", (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                    f"crop={w}:{h},setsar=1"),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-movflags", "+faststart", str(tmp),
        ], timeout=900)
        out = store.copy_in(media, tmp, "result.mp4")
        info = await video_ops.probe(out)
        await video_ops.thumbnail(out, store.path_for(media, "thumb.jpg"), at=1.0)
        return store.asset_from_file(
            out, MediaKind.video, media_id=media, thumb_name="thumb.jpg",
            width=info.get("width"), height=info.get("height"),
            duration=info.get("duration"), mime="video/mp4",
            meta={"tool": "platform_fit", "platform": name, "source_id": media_id},
        )

    return jobs.submit("platform.fit_video", work)


@router.post("/platforms/carousel/{media_id}", response_model=list[MediaAsset])
async def carousel(request: Request, media_id: str,
                   count: int = Query(default=3, ge=1, le=10)) -> list[MediaAsset]:
    """Slice one wide image into carousel slides."""
    _, path = _asset(request, media_id, MediaKind.image)
    slides = presets.carousel_slides(image_ops.load_image(path), count)
    return [
        _save_image(request, slide, meta={
            "tool": "carousel_slide", "slide": i + 1, "of": len(slides),
            "source_id": media_id,
        })
        for i, slide in enumerate(slides)
    ]


# --------------------------------------------------------------------------- #
# lenses
# --------------------------------------------------------------------------- #
@router.get("/lenses")
async def list_lenses() -> list[dict]:
    return [{"name": k, "description": v} for k, v in lenses.LENSES.items()]


@router.post("/lenses/{lens}/image/{media_id}", response_model=MediaAsset)
async def lens_image(request: Request, lens: str, media_id: str,
                     intensity: float = Query(default=1.0, ge=0.1, le=1.0)) -> MediaAsset:
    _, path = _asset(request, media_id, MediaKind.image)
    try:
        img = lenses.apply(image_ops.load_image(path), lens, intensity)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _save_image(request, img, meta={
        "tool": "lens", "lens": lens, "intensity": intensity, "source_id": media_id,
    })


@router.post("/lenses/{lens}/video/{media_id}", response_model=Job, status_code=202)
async def lens_video(request: Request, lens: str, media_id: str) -> Job:
    """Approximate a lens on video with an ffmpeg filter chain.

    Photo lenses are pixel-exact; the video path is a close approximation using
    ffmpeg filters, and the job report says so rather than implying parity.
    """
    _, path = _asset(request, media_id, MediaKind.video)
    if lens not in lenses.LENSES:
        raise HTTPException(404, f"unknown lens: {lens}")
    store = _store(request)

    chains = {
        "duotone": "hue=s=0,eq=contrast=1.15:brightness=0.02,colorbalance=rs=.2:bs=.3",
        "bloom": "gblur=sigma=6,eq=brightness=0.04:saturation=1.1",
        "chromatic": "rgbashift=rh=3:bh=-3",
        "vhs": "eq=saturation=0.7:contrast=0.9,noise=alls=12:allf=t",
        "kaleidoscope": "crop=iw/2:ih/2,split[a][b];[b]hflip[c];[a][c]hstack",
        "mirror": "crop=iw/2:ih,split[a][b];[b]hflip[c];[a][c]hstack",
        "thermal": "hue=s=0,pseudocolor=preset=turbo",
        "pixelate": "scale=iw/24:ih/24:flags=neighbor,scale=iw*24:ih*24:flags=neighbor",
        "noir": "hue=s=0,eq=contrast=1.35,vignette",
        "neon": "eq=saturation=1.9:contrast=1.2,unsharp=5:5:0.8",
    }
    chain = chains[lens]

    async def work() -> MediaAsset:
        media = store.new_id()
        tmp = store.path_for(media, "lens.mp4")
        try:
            await video_ops._run([
                video_ops.FFMPEG, "-y", "-i", str(path), "-vf", chain,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-movflags", "+faststart", str(tmp),
            ], timeout=900)
            engine = "ffmpeg-approximation"
        except video_ops.FFmpegError:
            # Filter unavailable in this build: fall back to a grade-only version.
            await video_ops._run([
                video_ops.FFMPEG, "-y", "-i", str(path),
                "-vf", "eq=saturation=1.2:contrast=1.1",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-movflags", "+faststart", str(tmp),
            ], timeout=900)
            engine = "fallback-grade"
        out = store.copy_in(media, tmp, "result.mp4")
        info = await video_ops.probe(out)
        await video_ops.thumbnail(out, store.path_for(media, "thumb.jpg"), at=1.0)
        return store.asset_from_file(
            out, MediaKind.video, media_id=media, thumb_name="thumb.jpg",
            width=info.get("width"), height=info.get("height"),
            duration=info.get("duration"), mime="video/mp4",
            meta={"tool": "lens_video", "lens": lens, "engine": engine, "source_id": media_id},
        )

    return jobs.submit("lens.video", work)


@router.post("/sticker/{media_id}", response_model=MediaAsset)
async def add_sticker(request: Request, media_id: str, body: StickerRequest) -> MediaAsset:
    _, path = _asset(request, media_id, MediaKind.image)
    img = lenses.sticker(
        image_ops.load_image(path), body.text, style=body.style,
        font_path=request.app.state.settings.font_path,
    )
    return _save_image(request, img, meta={
        "tool": "sticker", "style": body.style, "text": body.text, "source_id": media_id,
    })


# --------------------------------------------------------------------------- #
# search across every function
# --------------------------------------------------------------------------- #
@router.get("/features/search")
async def search_features(q: str = Query(min_length=1, max_length=60),
                          limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:
    """Search all functions by name, module or description."""
    return search(q, limit=limit)


@router.get("/features/{module}")
async def features_by_module(module: str) -> list[dict]:
    items = [f for f in all_features() if f["module"].lower() == module.lower()]
    if not items:
        raise HTTPException(404, f"no module {module}")
    return items
