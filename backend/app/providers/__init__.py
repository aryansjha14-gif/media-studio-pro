"""AI provider registry. Selected with the AI_PROVIDER env var."""

from __future__ import annotations

from ..config import Settings
from .base import AIProvider
from .mock import MockProvider


def get_provider(settings: Settings) -> AIProvider:
    name = (settings.ai_provider or "mock").lower()
    if name == "mock":
        return MockProvider(settings)
    if name == "fal":
        from .fal import FalProvider

        return FalProvider(settings)
    if name == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(settings)
    if name == "replicate":
        from .replicate import ReplicateProvider

        return ReplicateProvider(settings)
    raise ValueError(
        f"Unknown AI_PROVIDER '{settings.ai_provider}'. Use mock | fal | gemini | replicate."
    )


__all__ = ["AIProvider", "get_provider", "MockProvider"]
