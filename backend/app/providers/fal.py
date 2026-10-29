"""fal.ai provider — recommended default for a real deployment.

Why fal: one API key covers instruction-based image editing (FLUX Kontext),
text-to-image, upscaling, background removal, text-to-video and video-to-video.
Billing is per call and the queue is fast.

Docs: https://fal.ai/models
Set FAL_KEY in .env, then AI_PROVIDER=fal.
"""

from __future__ import annotations

import base64
import mimetypes

import httpx

from ..config import Settings
from .base import AIProvider

FAL_RUN_URL = "https://fal.run"
TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=60.0, pool=10.0)


def _data_uri(data: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


class FalProvider(AIProvider):
    name = "fal"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.fal_key:
            raise RuntimeError("FAL_KEY is not set but AI_PROVIDER=fal")

    async def _call(self, model: str, payload: dict) -> dict:
        headers = {
            "Authorization": f"Key {self.settings.fal_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(f"{FAL_RUN_URL}/{model}", json=payload, headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"fal {model} -> {resp.status_code}: {resp.text[:400]}")
            return resp.json()

    async def _download(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    @staticmethod
    def _first_url(result: dict, *keys: str) -> str:
        for key in keys:
            value = result.get(key)
            if isinstance(value, dict) and value.get("url"):
                return value["url"]
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value[0]["url"]
        raise RuntimeError(f"no media URL in fal response: {list(result)}")

    # -- images ------------------------------------------------------------ #
    async def edit_image(
        self, image: bytes, prompt: str, *, mime: str = "image/png", mask: bytes | None = None
    ) -> bytes:
        payload: dict = {
            "prompt": prompt,
            "image_url": _data_uri(image, mime),
            "num_images": 1,
            "output_format": "png",
            "safety_tolerance": "2",
        }
        if mask is not None:
            payload["mask_url"] = _data_uri(mask, "image/png")
        result = await self._call(self.settings.image_edit_model, payload)
        return await self._download(self._first_url(result, "images", "image"))

    async def generate_image(
        self, prompt: str, *, width: int = 1024, height: int = 1024, negative: str | None = None
    ) -> bytes:
        payload = {
            "prompt": prompt,
            "image_size": {"width": width, "height": height},
            "num_images": 1,
            "enable_safety_checker": True,
        }
        if negative:
            payload["negative_prompt"] = negative
        result = await self._call(self.settings.image_gen_model, payload)
        return await self._download(self._first_url(result, "images", "image"))

    async def upscale(self, image: bytes, *, factor: float = 2.0) -> bytes:
        result = await self._call(
            self.settings.upscale_model,
            {"image_url": _data_uri(image), "scale": max(2, int(factor))},
        )
        return await self._download(self._first_url(result, "image", "images"))

    async def remove_background(self, image: bytes) -> bytes:
        result = await self._call(
            self.settings.bg_removal_model, {"image_url": _data_uri(image)}
        )
        return await self._download(self._first_url(result, "image", "images"))

    # -- video ------------------------------------------------------------- #
    async def video_from_prompt(
        self, prompt: str, *, seconds: int = 5, aspect_ratio: str = "16:9", negative: str | None = None
    ) -> bytes:
        payload = {"prompt": prompt, "duration": str(seconds), "aspect_ratio": aspect_ratio}
        if negative:
            payload["negative_prompt"] = negative
        result = await self._call(self.settings.video_gen_model, payload)
        return await self._download(self._first_url(result, "video"))

    async def edit_video(self, video: bytes, prompt: str, *, negative: str | None = None) -> bytes:
        mime = mimetypes.guess_type("clip.mp4")[0] or "video/mp4"
        payload = {"prompt": prompt, "video_url": _data_uri(video, mime)}
        if negative:
            payload["negative_prompt"] = negative
        result = await self._call(self.settings.video_edit_model, payload)
        return await self._download(self._first_url(result, "video"))
