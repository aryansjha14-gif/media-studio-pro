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


# --------------------------------------------------------------------------- #
# v3 additions: curves, HSL, LUT, finishing, text, collage, batch
# --------------------------------------------------------------------------- #

def apply_curves(img: Image.Image, points: list[tuple[int, int]]) -> Image.Image:
    """RGB tone curve from control points, interpolated to a 256-entry LUT."""
    if len(points) < 2:
        return img
    pts = sorted(points)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    lut = []
    for value in range(256):
        if value <= xs[0]:
            lut.append(max(0, min(255, ys[0])))
        elif value >= xs[-1]:
            lut.append(max(0, min(255, ys[-1])))
        else:
            for i in range(len(xs) - 1):
                if xs[i] <= value <= xs[i + 1]:
                    span = xs[i + 1] - xs[i] or 1
                    ratio = (value - xs[i]) / span
                    lut.append(max(0, min(255, int(ys[i] + ratio * (ys[i + 1] - ys[i])))))
                    break
    return img.point(lut * len(img.getbands()))


def apply_hsl(
    img: Image.Image,
    hue_shift: float = 0.0,
    saturation: float = 1.0,
    lightness: float = 1.0,
) -> Image.Image:
    """Hue rotation plus saturation and lightness, applied in HSV space."""
    from PIL import ImageEnhance

    hsv = img.convert("HSV")
    h, s, v = hsv.split()
    if hue_shift:
        shift = int(hue_shift / 360.0 * 255) % 256
        h = h.point(lambda x: (x + shift) % 256)
    if saturation != 1.0:
        s = s.point(lambda x: max(0, min(255, int(x * saturation))))
    if lightness != 1.0:
        v = v.point(lambda x: max(0, min(255, int(x * lightness))))
    out = Image.merge("HSV", (h, s, v)).convert(img.mode)
    return ImageEnhance.Color(out).enhance(1.0)


def parse_cube_lut(path: Path) -> tuple[int, list[tuple[float, float, float]]]:
    """Read a .cube 3D LUT (Adobe/Resolve format)."""
    size, entries = 0, []
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper().startswith("LUT_3D_SIZE"):
            size = int(line.split()[-1])
        elif line[0].isdigit() or line[0] == "-":
            parts = line.split()
            if len(parts) >= 3:
                try:
                    entries.append((float(parts[0]), float(parts[1]), float(parts[2])))
                except ValueError:
                    continue
    return size, entries


def apply_lut(img: Image.Image, size: int, entries: list[tuple[float, float, float]],
              strength: float = 1.0) -> Image.Image:
    """Nearest-neighbour 3D LUT application, blended by `strength`."""
    if not size or not entries:
        return img
    rgb = img.convert("RGB")
    lut_lookup = {}
    index = 0
    for b in range(size):
        for g in range(size):
            for r in range(size):
                if index < len(entries):
                    lut_lookup[(r, g, b)] = entries[index]
                index += 1

    def nearest(r: int, g: int, b: int) -> tuple[float, float, float]:
        key = (
            round(r / 255 * (size - 1)),
            round(g / 255 * (size - 1)),
            round(b / 255 * (size - 1)),
        )
        return lut_lookup.get(key, (r / 255, g / 255, b / 255))

    cache: dict[tuple[int, int, int], tuple[int, int, int]] = {}

    def convert(pixel):
        if pixel not in cache:
            nr, ng, nb = nearest(*pixel)
            out = (
                int(min(255, max(0, (pixel[0] + (nr * 255 - pixel[0]) * strength)))),
                int(min(255, max(0, (pixel[1] + (ng * 255 - pixel[1]) * strength)))),
                int(min(255, max(0, (pixel[2] + (nb * 255 - pixel[2]) * strength)))),
            )
            cache[pixel] = out
        return cache[pixel]

    out = rgb.point(lambda x: x)
    out.putdata([convert(p) for p in rgb.getdata()])
    return out.convert(img.mode)


def add_vignette(img: Image.Image, amount: float = 0.35, feather: float = 1.4) -> Image.Image:
    from PIL import ImageDraw, ImageFilter

    base = img.convert("RGB")
    mask = Image.new("L", base.size, 0)
    draw = ImageDraw.Draw(mask)
    w, h = base.size
    inset_x, inset_y = int(w * (1 - feather) / 2), int(h * (1 - feather) / 2)
    draw.ellipse([inset_x, inset_y, w - inset_x, h - inset_y], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(8, min(w, h) // 14)))
    dark = Image.new("RGB", base.size, (0, 0, 0))
    return Image.composite(base, Image.blend(base, dark, amount), mask)


def add_grain(img: Image.Image, strength: float = 0.06) -> Image.Image:
    import random

    base = img.convert("RGB")
    noise = Image.new("L", base.size)
    noise.putdata([random.randint(0, 255) for _ in range(base.width * base.height)])
    grain = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(base, Image.blend(base, grain, 0.5), strength)


def draw_text(
    img: Image.Image, text: str, *, position: str = "bottom", size_ratio: float = 0.06,
    colour: tuple[int, int, int] = (255, 255, 255), font_path: str | None = None,
) -> Image.Image:
    from PIL import ImageDraw, ImageFont

    base = img.convert("RGB")
    draw = ImageDraw.Draw(base)
    size = max(14, int(base.height * size_ratio))
    font = None
    if font_path:
        try:
            font = ImageFont.truetype(font_path, size)
        except Exception:  # noqa: BLE001
            font = None
    if font is None:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(base.height * 0.03)
    x = (base.width - tw) // 2
    y = {"top": pad, "center": (base.height - th) // 2,
         "bottom": base.height - th - pad}.get(position, base.height - th - pad)
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=colour)
    return base


def watermark(img: Image.Image, text: str, opacity: float = 0.45) -> Image.Image:
    from PIL import ImageDraw, ImageFont

    base = img.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    size = max(12, int(base.height * 0.035))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    pad = int(base.height * 0.02)
    draw.text(
        (base.width - (bbox[2] - bbox[0]) - pad, base.height - (bbox[3] - bbox[1]) - pad),
        text, font=font, fill=(255, 255, 255, int(255 * opacity)),
    )
    return Image.alpha_composite(base, layer)


def add_frame(img: Image.Image, width_ratio: float = 0.04,
              colour: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    base = img.convert("RGB")
    border = max(2, int(min(base.size) * width_ratio))
    out = Image.new("RGB", (base.width + border * 2, base.height + border * 2), colour)
    out.paste(base, (border, border))
    return out


def collage(images: list[Image.Image], columns: int = 2,
            gutter: int = 12, background: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """Grid collage. All tiles share one cell size, cropped to fill."""
    if not images:
        raise ValueError("collage needs at least one image")
    columns = max(1, min(columns, len(images)))
    rows = (len(images) + columns - 1) // columns
    cell_w = max(img.width for img in images)
    cell_h = max(img.height for img in images)
    out_w = columns * cell_w + (columns + 1) * gutter
    out_h = rows * cell_h + (rows + 1) * gutter
    canvas = Image.new("RGB", (out_w, out_h), background)
    for index, img in enumerate(images):
        tile = ImageOps.fit(img.convert("RGB"), (cell_w, cell_h), Image.LANCZOS)
        row, col = divmod(index, columns)
        canvas.paste(tile, (gutter + col * (cell_w + gutter), gutter + row * (cell_h + gutter)))
    return canvas


def auto_enhance(img: Image.Image) -> tuple[Image.Image, dict]:
    """Neutral mid-tone, corrected white balance, mild contrast."""
    from PIL import ImageStat

    base = img.convert("RGB")
    stat = ImageStat.Stat(base)
    mean = sum(stat.mean) / 3 / 255.0
    brightness = max(0.75, min(1.35, 0.5 / mean if mean else 1.0))
    r, g, b = stat.mean
    grey = (r + g + b) / 3
    channels = base.split()
    corrected = [
        ch.point(lambda v, m=m: max(0, min(255, int(v * (grey / m if m else 1.0)))))
        for ch, m in zip(channels, (r, g, b))
    ]
    balanced = Image.merge("RGB", tuple(corrected))
    out = ImageEnhance.Brightness(balanced).enhance(brightness)
    out = ImageEnhance.Contrast(out).enhance(1.06)
    return out, {"brightness": round(brightness, 3), "white_balance": "grey-world"}
