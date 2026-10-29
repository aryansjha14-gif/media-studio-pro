"""Image editing endpoints.

Two families:
  * /adjust  — instant, deterministic (Pillow). Returns the new asset directly.
  * /prompt, /generate, /upscale, /remove-background — AI. Returns a Job.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..jobs import jobs
from ..providers import get_provider
from ..schemas import (
    AdjustRequest,
    GenerateImageRequest,
    Job,
    MediaAsset,
    MediaKind,
    PromptEditRequest,
)
from ..services import image_ops
from ..storage import MediaStore

router = APIRouter(prefix="/v1/images", tags=["images"])
log = logging.getLogger(__name__)


def store(request: Request) -> MediaStore:
    return request.app.state.store


def _require_image(s: MediaStore, media_id: str) -> tuple[MediaAsset, Path]:
    try:
        asset = s.load_asset(media_id)
        path = s.find_file(media_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, f"unknown media id: {media_id}") from exc
    if asset.kind is not MediaKind.image:
        raise HTTPException(400, f"{media_id} is a {asset.kind.value}, not an image")
    return asset, path


def _save_result(s: MediaStore, img, *, meta: dict, ext: str = ".png") -> MediaAsset:
    media_id = s.new_id()
    out = s.path_for(media_id, f"result{ext}")
    if ext == ".jpg":
        image_ops.save_jpeg(img, out)
    else:
        image_ops.save_png(img, out)
    thumb = s.path_for(media_id, "thumb.jpg")
    image_ops.make_thumbnail(img, thumb)
    return s.asset_from_file(
        out, MediaKind.image, media_id=media_id, thumb_name="thumb.jpg",
        width=img.width, height=img.height, mime=f"image/{ext.lstrip('.')}", meta=meta,
    )


@router.post("/{media_id}/adjust", response_model=MediaAsset)
async def adjust(request: Request, media_id: str, body: AdjustRequest) -> MediaAsset:
    """Crop / rotate / resize / colour grade / filter — no AI, no cost, instant."""
    s = store(request)
    _, path = _require_image(s, media_id)
    img = image_ops.load_image(path)
    out = image_ops.apply_adjustments(img, body)
    return _save_result(
        s, out, ext=".jpg" if body.quality < 100 else ".png",
        meta={"tool": "adjust", "params": body.model_dump(exclude_none=True)},
    )


@router.post("/{media_id}/prompt", response_model=Job, status_code=202)
async def prompt_edit(request: Request, media_id: str, body: PromptEditRequest) -> Job:
    """Natural-language edit: "make it look like a rainy night in Mumbai"."""
    s = store(request)
    _, path = _require_image(s, media_id)
    provider = get_provider(request.app.state.settings)
    mask_bytes = None
    if body.mask_media_id:
        _, mask_path = _require_image(s, body.mask_media_id)
        mask_bytes = mask_path.read_bytes()

    source = path.read_bytes()
    suffix = path.suffix

    async def work() -> MediaAsset:
        edited = await provider.edit_image(source, body.prompt, mime="image/png", mask=mask_bytes)
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(edited))
        return _save_result(
            s, img,
            meta={
                "tool": "prompt_edit",
                "prompt": body.prompt,
                "provider": provider.name,
                "source_id": media_id,
                "source_suffix": suffix,
            },
        )

    return jobs.submit("image.prompt", work)


@router.post("/generate", response_model=Job, status_code=202)
async def generate(request: Request, body: GenerateImageRequest) -> Job:
    """Text-to-image from scratch."""
    s = store(request)
    provider = get_provider(request.app.state.settings)

    async def work() -> MediaAsset:
        import io

        from PIL import Image

        data = await provider.generate_image(
            body.prompt, width=body.width, height=body.height, negative=body.negative_prompt
        )
        img = Image.open(io.BytesIO(data))
        return _save_result(
            s, img,
            meta={"tool": "generate", "prompt": body.prompt, "provider": provider.name},
        )

    return jobs.submit("image.generate", work)


@router.post("/{media_id}/upscale", response_model=Job, status_code=202)
async def upscale(request: Request, media_id: str, factor: float = 2.0) -> Job:
    """AI upscale, falling back to Lanczos when the provider can't do it."""
    s = store(request)
    _, path = _require_image(s, media_id)
    provider = get_provider(request.app.state.settings)
    source = path.read_bytes()

    async def work() -> MediaAsset:
        import io

        from PIL import Image

        try:
            data = await provider.upscale(source, factor=factor)
            img = Image.open(io.BytesIO(data))
            used = f"{provider.name}:upscale"
        except NotImplementedError:
            img = image_ops.upscale_lanczos(image_ops.load_image(path), factor)
            used = "lanczos:fallback"
        return _save_result(s, img, meta={"tool": "upscale", "engine": used, "source_id": media_id})

    return jobs.submit("image.upscale", work)


@router.post("/{media_id}/remove-background", response_model=Job, status_code=202)
async def remove_background(request: Request, media_id: str) -> Job:
    s = store(request)
    _, path = _require_image(s, media_id)
    provider = get_provider(request.app.state.settings)
    source = path.read_bytes()

    async def work() -> MediaAsset:
        import io

        from PIL import Image

        data = await provider.remove_background(source)
        img = Image.open(io.BytesIO(data))
        return _save_result(
            s, img, meta={"tool": "remove_background", "provider": provider.name, "source_id": media_id}
        )

    return jobs.submit("image.remove_background", work)
