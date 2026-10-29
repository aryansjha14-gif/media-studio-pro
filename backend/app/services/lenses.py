"""Snapchat-style looks that do not need a face.

Real Snapchat lenses track your face with an on-device model and attach
geometry to it. That is a device-side job (ML Kit / ARCore) and is listed as
planned, not faked here. What this module does implement is the visual layer of
a lens: duotone, bloom, chromatic aberration, VHS, kaleidoscope, mirror,
thermal, pixelate, plus caption and timestamp stickers. They apply to a photo or
a video frame identically, which is what makes a "lens" feel consistent.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

LENSES = {
    "duotone": "Two-colour gradient look, high contrast",
    "bloom": "Soft glow on highlights, dreamy",
    "chromatic": "RGB split, music-video look",
    "vhs": "Scanlines, soft colour, tape noise",
    "kaleidoscope": "Mirrored quadrants, trippy",
    "mirror": "Split mirror reflection",
    "thermal": "False-colour heat map",
    "pixelate": "Retro pixel blocks",
    "noir": "Hard black and white with vignette",
    "neon": "Boosted colour with glow edges",
}


def _duotone(img: Image.Image, dark=(24, 16, 64), light=(255, 190, 90)) -> Image.Image:
    grey = ImageOps.grayscale(img).convert("L")
    out = Image.new("RGB", img.size)
    out.putdata([
        tuple(int(dark[i] + (light[i] - dark[i]) * (v / 255)) for i in range(3))
        for v in grey.getdata()
    ])
    return ImageEnhance.Contrast(out).enhance(1.12)


def _bloom(img: Image.Image) -> Image.Image:
    base = img.convert("RGB")
    bright = base.point(lambda v: max(0, v - 150) * 2)
    glow = bright.filter(ImageFilter.GaussianBlur(radius=max(4, min(base.size) // 60)))
    return Image.blend(base, Image.blend(base, glow, 0.85), 0.55)


def _chromatic(img: Image.Image, shift: int = 4) -> Image.Image:
    base = img.convert("RGB")
    r, g, b = base.split()
    r = ImageOps.offset(r, shift, 0) if hasattr(ImageOps, "offset") else r
    from PIL import ImageChops
    r = ImageChops.offset(r, shift, 0)
    b = ImageChops.offset(b, -shift, 0)
    return Image.merge("RGB", (r, g, b))


def _vhs(img: Image.Image) -> Image.Image:
    base = ImageEnhance.Color(img.convert("RGB")).enhance(0.7)
    draw = ImageDraw.Draw(base)
    for y in range(0, base.height, 4):
        draw.line([(0, y), (base.width, y)], fill=(0, 0, 0), width=1)
    return Image.blend(base, ImageEnhance.Contrast(base).enhance(0.85), 0.6)


def _kaleidoscope(img: Image.Image) -> Image.Image:
    base = img.convert("RGB")
    w, h = base.size
    half = base.crop((0, 0, w // 2, h // 2)).resize((w // 2, h // 2))
    quad = ImageOps.mirror(half)
    canvas = Image.new("RGB", (w, h))
    canvas.paste(half, (0, 0))
    canvas.paste(quad, (w // 2, 0))
    canvas.paste(ImageOps.flip(half), (0, h // 2))
    canvas.paste(ImageOps.flip(quad), (w // 2, h // 2))
    return canvas


def _mirror(img: Image.Image) -> Image.Image:
    base = img.convert("RGB")
    w, h = base.size
    left = base.crop((0, 0, w // 2, h))
    canvas = Image.new("RGB", (w, h))
    canvas.paste(left, (0, 0))
    canvas.paste(ImageOps.mirror(left), (w // 2, 0))
    return canvas


def _thermal(img: Image.Image) -> Image.Image:
    grey = ImageOps.grayscale(img)
    palette = []
    for i in range(256):
        t = i / 255
        palette.extend((
            int(min(255, 255 * (1.5 * t))),
            int(min(255, 255 * max(0, 1 - abs(t - 0.55) * 2.2))),
            int(min(255, 255 * max(0, 1 - t * 2.2))),
        ))
    out = Image.new("RGB", img.size)
    out.putdata([tuple(palette[v * 3:v * 3 + 3]) for v in grey.getdata()])
    return out


def _pixelate(img: Image.Image, blocks: int = 24) -> Image.Image:
    base = img.convert("RGB")
    small = base.resize((max(4, base.width // blocks), max(4, base.height // blocks)), Image.BILINEAR)
    return small.resize(base.size, Image.NEAREST)


def _noir(img: Image.Image) -> Image.Image:
    from .image_ops import add_vignette

    base = ImageOps.grayscale(img).convert("RGB")
    base = ImageEnhance.Contrast(base).enhance(1.35)
    return add_vignette(base, amount=0.45)


def _neon(img: Image.Image) -> Image.Image:
    base = ImageEnhance.Color(img.convert("RGB")).enhance(1.9)
    base = ImageEnhance.Contrast(base).enhance(1.2)
    edges = base.filter(ImageFilter.EDGE_ENHANCE_MORE)
    return Image.blend(base, edges, 0.35)


_RENDERERS = {
    "duotone": _duotone, "bloom": _bloom, "chromatic": _chromatic, "vhs": _vhs,
    "kaleidoscope": _kaleidoscope, "mirror": _mirror, "thermal": _thermal,
    "pixelate": _pixelate, "noir": _noir, "neon": _neon,
}


def apply(img: Image.Image, lens: str, intensity: float = 1.0) -> Image.Image:
    """Apply a lens. `intensity` blends the result back toward the original."""
    renderer = _RENDERERS.get(lens)
    if renderer is None:
        raise ValueError(f"unknown lens: {lens}. Available: {', '.join(LENSES)}")
    result = renderer(img.convert("RGB"))
    if intensity >= 0.999:
        return result
    return Image.blend(img.convert("RGB"), result, max(0.0, min(1.0, intensity)))


def sticker(img: Image.Image, text: str, *, style: str = "caption",
            font_path: str | None = None) -> Image.Image:
    """Snapchat-style caption badge or timestamp sticker."""
    base = img.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    size = max(18, base.height // 16)
    font = None
    if font_path:
        try:
            from PIL import ImageFont

            font = ImageFont.truetype(font_path, size)
        except Exception:  # noqa: BLE001
            font = None
    from PIL import ImageFont

    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = size // 2
    if style == "caption":
        x, y = (base.width - tw) // 2, base.height - th - pad * 4
        draw.rounded_rectangle(
            [x - pad, y - pad, x + tw + pad, y + th + pad],
            radius=pad, fill=(255, 255, 255, 235),
        )
        draw.text((x, y), text, font=font, fill=(20, 20, 20, 255))
    else:  # timestamp / lower-left
        x, y = pad, base.height - th - pad * 3
        draw.rectangle([x - pad // 2, y - pad // 2, x + tw + pad // 2, y + th + pad // 2],
                       fill=(0, 0, 0, 150))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    return Image.alpha_composite(base, layer).convert("RGB")
