"""Local image operations with Pillow.

These are the fast, free, offline edits: crop, rotate, resize, colour grading,
filter presets, thumbnails, Lanczos upscaling. AI edits live in app/providers.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from ..schemas import AdjustRequest

FILTER_PRESETS = {
    "none",
    "grayscale",
    "sepia",
    "warm",
    "cool",
    "vintage",
    "punch",
    "mono",
}


def load_image(path: Path) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    return img


def _apply_preset(img: Image.Image, preset: str) -> Image.Image:
    if preset == "none":
        return img
    if preset == "grayscale":
        return ImageOps.grayscale(img).convert(img.mode)
    if preset == "mono":
        return ImageOps.grayscale(img).convert(img.mode).filter(ImageFilter.SHARPEN)
    if preset == "sepia":
        gray = ImageOps.grayscale(img).convert("RGB")
        sepia = Image.new("RGB", gray.size)
        sepia.putdata(
            [
                (min(255, int(r * 1.07 + g * 0.15)), min(255, int(r * 0.55 + g * 0.55)), int(g * 0.72))
                for r, g, _ in gray.getdata()
            ]
        )
        return sepia.convert(img.mode)
    if preset == "warm":
        img = ImageEnhance.Color(img).enhance(1.1)
        r, g, b, *rest = img.split()
        r = r.point(lambda v: min(255, int(v * 1.08)))
        b = b.point(lambda v: int(v * 0.92))
        return Image.merge(img.mode, (r, g, b, *rest))
    if preset == "cool":
        r, g, b, *rest = img.split()
        r = r.point(lambda v: int(v * 0.92))
        b = b.point(lambda v: min(255, int(v * 1.1)))
        return Image.merge(img.mode, (r, g, b, *rest))
    if preset == "vintage":
        img = ImageEnhance.Color(img).enhance(0.75)
        img = ImageEnhance.Contrast(img).enhance(0.9)
        return _apply_preset(img, "sepia")
    if preset == "punch":
        img = ImageEnhance.Contrast(img).enhance(1.25)
        return ImageEnhance.Color(img).enhance(1.35)
    return img


def _resize(img: Image.Image, spec) -> Image.Image:
    tw, th = spec.width, spec.height
    if tw is None and th is None:
        return img
    w, h = img.size
    if spec.fit == "stretch":
        return img.resize((tw or w, th or h), Image.LANCZOS)
    if tw and th:
        scale = max(tw / w, th / h) if spec.fit == "cover" else min(tw / w, th / h)
    elif tw:
        scale = tw / w
    else:
        scale = th / h
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    img = img.resize(new_size, Image.LANCZOS)
    if spec.fit == "cover" and tw and th:
        left = (img.width - tw) // 2
        top = (img.height - th) // 2
        img = img.crop((left, top, left + tw, top + th))
    return img


def apply_adjustments(img: Image.Image, req: AdjustRequest) -> Image.Image:
    if req.crop:
        box = (
            req.crop.x,
            req.crop.y,
            min(img.width, req.crop.x + req.crop.width),
            min(img.height, req.crop.y + req.crop.height),
        )
        if box[2] > box[0] and box[3] > box[1]:
            img = img.crop(box)

    if req.rotate:
        img = img.rotate(-req.rotate, expand=True, resample=Image.BICUBIC)
    if req.flip_horizontal:
        img = ImageOps.mirror(img)
    if req.flip_vertical:
        img = ImageOps.flip(img)

    if req.brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(req.brightness)
    if req.contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(req.contrast)
    if req.saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(req.saturation)
    if req.sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(req.sharpness)
    if req.blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(req.blur))

    img = _apply_preset(img, req.filter)

    if req.resize:
        img = _resize(img, req.resize)
    return img


def save_jpeg(img: Image.Image, path: Path, quality: int = 92) -> Path:
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    img.save(path, "JPEG", quality=quality, optimize=True)
    return path


def save_png(img: Image.Image, path: Path) -> Path:
    img.save(path, "PNG", optimize=True)
    return path


def make_thumbnail(img: Image.Image, path: Path, max_side: int = 512) -> Path:
    thumb = img.copy()
    thumb.thumbnail((max_side, max_side), Image.LANCZOS)
    return save_jpeg(thumb, path, quality=85)


def upscale_lanczos(img: Image.Image, factor: float = 2.0) -> Image.Image:
    """Offline fallback upscaler — decent, instant, no credits spent."""
    factor = max(1.0, min(4.0, factor))
    size = (int(img.width * factor), int(img.height * factor))
    out = img.resize(size, Image.LANCZOS)
    return out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3))


def to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    if fmt.upper() == "JPEG":
        if img.mode == "RGBA":
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        img.save(buf, "JPEG", quality=92, optimize=True)
    else:
        img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
