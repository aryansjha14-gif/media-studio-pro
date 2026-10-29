"""Platform packs: YouTube, Instagram, Snapchat, TikTok, WhatsApp.

Each preset is the same thing a creator does by hand for every upload: crop to
the right aspect, respect the platform's safe areas, and export at the size the
platform wants. Doing it once on the server means the phone does not have to
know any of these numbers.
"""

from __future__ import annotations

from PIL import Image, ImageOps

PLATFORMS: dict[str, dict] = {
    "youtube_video": {
        "label": "YouTube video", "width": 1920, "height": 1080, "aspect": "16:9",
        "safe": {"top": 0.05, "bottom": 0.10, "left": 0.05, "right": 0.05},
        "notes": "16:9. Keep text out of the bottom 10% (player controls).",
    },
    "youtube_thumbnail": {
        "label": "YouTube thumbnail", "width": 1280, "height": 720, "aspect": "16:9",
        "safe": {"top": 0.05, "bottom": 0.12, "left": 0.05, "right": 0.15},
        "notes": "Under 2 MB. Big text, readable at phone size.",
    },
    "youtube_short": {
        "label": "YouTube Short", "width": 1080, "height": 1920, "aspect": "9:16",
        "safe": {"top": 0.10, "bottom": 0.20, "left": 0.06, "right": 0.12},
        "notes": "Vertical. Bottom 20% is covered by controls and description.",
    },
    "instagram_reel": {
        "label": "Instagram Reel", "width": 1080, "height": 1920, "aspect": "9:16",
        "safe": {"top": 0.12, "bottom": 0.25, "left": 0.06, "right": 0.18},
        "notes": "Vertical. Keep captions above the bottom 25%.",
    },
    "instagram_feed": {
        "label": "Instagram feed", "width": 1080, "height": 1350, "aspect": "4:5",
        "safe": {"top": 0.05, "bottom": 0.05, "left": 0.05, "right": 0.05},
        "notes": "4:5 takes the most feed height. 1:1 is also accepted.",
    },
    "instagram_story": {
        "label": "Instagram story", "width": 1080, "height": 1920, "aspect": "9:16",
        "safe": {"top": 0.14, "bottom": 0.18, "left": 0.06, "right": 0.06},
        "notes": "Vertical. Top 14% holds the progress bar and avatar.",
    },
    "instagram_carousel_slide": {
        "label": "Instagram carousel slide", "width": 1080, "height": 1350, "aspect": "4:5",
        "safe": {"top": 0.05, "bottom": 0.05, "left": 0.05, "right": 0.05},
        "notes": "Up to 10 slides. Keep the first one self-explanatory.",
    },
    "snapchat_snap": {
        "label": "Snapchat snap", "width": 1080, "height": 1920, "aspect": "9:16",
        "safe": {"top": 0.12, "bottom": 0.22, "left": 0.06, "right": 0.06},
        "notes": "Vertical. Lenses and captions live in the middle band.",
    },
    "tiktok_video": {
        "label": "TikTok video", "width": 1080, "height": 1920, "aspect": "9:16",
        "safe": {"top": 0.10, "bottom": 0.28, "left": 0.06, "right": 0.20},
        "notes": "Vertical. The right 20% and bottom 28% hold buttons and captions.",
    },
    "whatsapp_status": {
        "label": "WhatsApp status", "width": 1080, "height": 1920, "aspect": "9:16",
        "safe": {"top": 0.10, "bottom": 0.15, "left": 0.06, "right": 0.06},
        "notes": "Vertical, short. Compress hard - data matters.",
    },
    "whatsapp_square": {
        "label": "WhatsApp square", "width": 1080, "height": 1080, "aspect": "1:1",
        "safe": {"top": 0.05, "bottom": 0.05, "left": 0.05, "right": 0.05},
        "notes": "Square, safe for chat previews.",
    },
    "linkedin_post": {
        "label": "LinkedIn post", "width": 1200, "height": 627, "aspect": "1.91:1",
        "safe": {"top": 0.05, "bottom": 0.05, "left": 0.05, "right": 0.05},
        "notes": "Wide landscape card.",
    },
}


def get(name: str) -> dict:
    if name not in PLATFORMS:
        raise KeyError(f"unknown platform preset: {name}. Available: {', '.join(PLATFORMS)}")
    return {"name": name, **PLATFORMS[name]}


def fit(img: Image.Image, name: str, *, mode: str = "cover") -> Image.Image:
    """Resize to the platform frame. `cover` crops, `contain` letterboxes."""
    spec = get(name)
    w, h = spec["width"], spec["height"]
    if mode == "contain":
        fitted = ImageOps.contain(img.convert("RGB"), (w, h), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), (0, 0, 0))
        canvas.paste(fitted, ((w - fitted.width) // 2, (h - fitted.height) // 2))
        return canvas
    return ImageOps.fit(img.convert("RGB"), (w, h), Image.LANCZOS)


def carousel_slides(img: Image.Image, count: int = 3) -> list[Image.Image]:
    """Slice a wide image into square-ish slides for a carousel post."""
    base = img.convert("RGB")
    count = max(1, min(10, count))
    slide_w = base.width // count
    slides = []
    for i in range(count):
        box = (i * slide_w, 0, (i + 1) * slide_w if i < count - 1 else base.width, base.height)
        slides.append(ImageOps.fit(base.crop(box), (1080, 1350), Image.LANCZOS))
    return slides
