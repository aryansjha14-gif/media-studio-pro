"""Provider interface.

Every AI capability the app needs is one method here. Add a provider by
subclassing AIProvider and registering it in app/providers/__init__.py.
Methods raise NotImplementedError when a provider cannot do something — the
job manager turns that into a clear 4xx-style job error instead of a crash.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Settings


class AIProvider(ABC):
    name: str = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # -- images ------------------------------------------------------------ #
    @abstractmethod
    async def edit_image(
        self, image: bytes, prompt: str, *, mime: str = "image/png", mask: bytes | None = None
    ) -> bytes:
        """Instruction-based edit. Returns the edited image bytes."""

    async def generate_image(
        self, prompt: str, *, width: int = 1024, height: int = 1024, negative: str | None = None
    ) -> bytes:
        raise NotImplementedError(f"{self.name} cannot generate images from scratch")

    async def upscale(self, image: bytes, *, factor: float = 2.0) -> bytes:
        raise NotImplementedError(f"{self.name} cannot AI-upscale")

    async def remove_background(self, image: bytes) -> bytes:
        raise NotImplementedError(f"{self.name} cannot remove backgrounds")

    # -- video ------------------------------------------------------------- #
    async def video_from_prompt(
        self, prompt: str, *, seconds: int = 5, aspect_ratio: str = "16:9", negative: str | None = None
    ) -> bytes:
        raise NotImplementedError(f"{self.name} cannot generate video")

    async def edit_video(self, video: bytes, prompt: str, *, negative: str | None = None) -> bytes:
        raise NotImplementedError(f"{self.name} cannot restyle video")
