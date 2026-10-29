"""Google Gemini image editing ("nano banana" family).

Cheapest way to get genuinely good instruction-based editing, and it accepts
inline image bytes, so no upload dance is needed.

Docs: https://ai.google.dev/gemini-api/docs/image-generation
Set GEMINI_API_KEY and AI_PROVIDER=gemini.

Note: this provider does images only. Use fal for video generation.
"""

from __future__ import annotations

import base64

import httpx

from ..config import Settings
from .base import AIProvider

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=60.0, pool=10.0)


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set but AI_PROVIDER=gemini")

    async def _generate(self, parts: list[dict]) -> bytes:
        url = f"{BASE}/{self.settings.gemini_image_model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "x-goog-api-key": self.settings.gemini_api_key or "",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"gemini -> {resp.status_code}: {resp.text[:400]}")
            data = resp.json()

        candidates = data.get("candidates") or []
        for candidate in candidates:
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"])
        raise RuntimeError("gemini returned no image (prompt may have been blocked)")

    async def edit_image(
        self, image: bytes, prompt: str, *, mime: str = "image/png", mask: bytes | None = None
    ) -> bytes:
        parts: list[dict] = [
            {"inlineData": {"mimeType": mime, "data": base64.b64encode(image).decode("ascii")}},
            {"text": prompt},
        ]
        if mask is not None:
            parts.insert(
                1,
                {
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": base64.b64encode(mask).decode("ascii"),
                    }
                },
            )
            parts.insert(2, {"text": "The second image is a mask: only edit the white region."})
        return await self._generate(parts)

    async def generate_image(
        self, prompt: str, *, width: int = 1024, height: int = 1024, negative: str | None = None
    ) -> bytes:
        text = prompt if not negative else f"{prompt}\n\nAvoid: {negative}"
        return await self._generate([{"text": text}])
