"""Replicate provider — access to any hosted model (FLUX, SDXL, etc.).

Set REPLICATE_API_TOKEN and AI_PROVIDER=replicate.
Uses the "Prefer: wait" header so short predictions return inline.
"""

from __future__ import annotations

import base64

import httpx

from ..config import Settings
from .base import AIProvider

TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=60.0, pool=10.0)


class ReplicateProvider(AIProvider):
    name = "replicate"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.replicate_api_token:
            raise RuntimeError("REPLICATE_API_TOKEN is not set but AI_PROVIDER=replicate")

    async def _predict(self, model: str, payload: dict) -> str:
        url = f"https://api.replicate.com/v1/models/{model}/predictions"
        headers = {
            "Authorization": f"Bearer {self.settings.replicate_api_token}",
            "Content-Type": "application/json",
            "Prefer": "wait=120",
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(url, json={"input": payload}, headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"replicate {model} -> {resp.status_code}: {resp.text[:400]}")
            data = resp.json()

        output = data.get("output")
        if isinstance(output, list) and output:
            output = output[0]
        if isinstance(output, dict):
            output = output.get("url")
        if not isinstance(output, str):
            raise RuntimeError(f"unexpected replicate output: {type(output)}")
        return output

    async def _download(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    async def edit_image(
        self, image: bytes, prompt: str, *, mime: str = "image/png", mask: bytes | None = None
    ) -> bytes:
        payload = {
            "prompt": prompt,
            "input_image": f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}",
            "output_format": "png",
        }
        if mask is not None:
            payload["mask"] = f"data:image/png;base64,{base64.b64encode(mask).decode('ascii')}"
        url = await self._predict(self.settings.replicate_image_edit_model, payload)
        return await self._download(url)
