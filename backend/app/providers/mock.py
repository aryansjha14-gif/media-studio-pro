"""Offline provider — no API key, no cost, no network.

It produces *visibly fake* results on purpose: the prompt text is stamped on the
image and a colour grade is derived from a hash of the prompt, so you can verify
the whole upload -> job -> poll -> display flow before spending a rupee on
model credits. Never ship this provider to real users.
"""

from __future__ import annotations

import hashlib
import io
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

from ..config import Settings
from ..services import image_ops, video_ops
from .base import AIProvider


def _prompt_colour(prompt: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return digest[0], digest[1], digest[2]


class MockProvider(AIProvider):
    name = "mock"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    async def edit_image(
        self, image: bytes, prompt: str, *, mime: str = "image/png", mask: bytes | None = None
    ) -> bytes:
        img = Image.open(io.BytesIO(image)).convert("RGB")
        r, g, b = _prompt_colour(prompt)
        overlay = Image.new("RGB", img.size, (r, g, b))
        img = Image.blend(img, overlay, alpha=0.18)
        img = ImageEnhance.Contrast(img).enhance(1.05)
        _stamp(img, prompt, "MOCK PROVIDER")
        return image_ops.to_bytes(img, "PNG")

    async def generate_image(
        self, prompt: str, *, width: int = 1024, height: int = 1024, negative: str | None = None
    ) -> bytes:
        r, g, b = _prompt_colour(prompt)
        img = Image.new("RGB", (width, height), (r, g, b))
        draw = ImageDraw.Draw(img)
        for i in range(0, height, 64):
            shade = int(40 + 60 * (i / max(1, height)))
            draw.rectangle([0, i, width, i + 32], fill=(r // 2 + shade, g // 2 + shade, b // 2 + shade))
        _stamp(img, prompt, "MOCK PROVIDER · text-to-image")
        return image_ops.to_bytes(img, "PNG")

    async def upscale(self, image: bytes, *, factor: float = 2.0) -> bytes:
        img = Image.open(io.BytesIO(image))
        return image_ops.to_bytes(image_ops.upscale_lanczos(img, factor), "PNG")

    async def remove_background(self, image: bytes) -> bytes:
        img = Image.open(io.BytesIO(image)).convert("RGBA")
        # Cheap centre-weighted vignette alpha so the UI has something to show.
        w, h = img.size
        alpha = Image.new("L", (w, h), 0)
        ImageDraw.Draw(alpha).ellipse(
            [w * 0.08, h * 0.05, w * 0.92, h * 0.95], fill=255
        )
        img.putalpha(alpha)
        return image_ops.to_bytes(img, "PNG")

    async def video_from_prompt(
        self, prompt: str, *, seconds: int = 5, aspect_ratio: str = "16:9", negative: str | None = None
    ) -> bytes:
        size = {"16:9": (960, 540), "9:16": (540, 960), "1:1": (720, 720)}[aspect_ratio]
        r, g, b = _prompt_colour(prompt)
        fps = 12
        total = int(seconds * fps)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            frames_dir = tmp_dir / "frames"
            frames_dir.mkdir()
            for i in range(total):
                t = i / max(1, total - 1)
                base = Image.new("RGB", size, (r, g, b))
                draw = ImageDraw.Draw(base)
                x = int(t * (size[0] - 60))
                draw.ellipse([x, size[1] // 2 - 30, x + 60, size[1] // 2 + 30], fill=(255, 255, 255))
                _stamp(base, prompt, f"MOCK · text-to-video · frame {i + 1}/{total}")
                base.save(frames_dir / f"f_{i:04d}.png")
            out = tmp_dir / "out.mp4"
            await video_ops.frames_to_video(frames_dir, out, fps=fps, seconds=seconds)
            return out.read_bytes()

    async def edit_video(self, video: bytes, prompt: str, *, negative: str | None = None) -> bytes:
        # Mock: return a re-encoded copy so the flow is testable end to end.
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.mp4"
            src.write_bytes(video)
            info = await video_ops.probe(src)
            dst = Path(tmp) / "out.mp4"
            await video_ops.trim(src, dst, 0, info.get("duration") or 3.0, reencode=True)
            return dst.read_bytes()


def _stamp(img: Image.Image, prompt: str, label: str) -> None:
    draw = ImageDraw.Draw(img)
    w, h = img.size
    bar_h = max(48, h // 10)
    draw.rectangle([0, h - bar_h, w, h], fill=(0, 0, 0))
    text = prompt if len(prompt) <= 90 else prompt[:87] + "..."
    draw.text((12, h - bar_h + 8), label, fill=(160, 255, 190))
    draw.text((12, h - bar_h + 26), text, fill=(255, 255, 255))
