"""Application settings, loaded from environment / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Media Studio API"
    storage_dir: Path = Path("./data")
    public_base_url: str = "http://localhost:8000"
    cors_origins: str = "*"

    # Large-media handling. Uploads are streamed to disk, never buffered in RAM,
    # so a 20 GB video is limited by disk and time rather than memory.
    max_upload_gb: float = 20.0
    chunk_size_mb: int = 16
    proxy_height: int = 540          # editing proxy for long videos
    preview_long_edge: int = 2048    # image preview for the phone

    # Render defaults
    target_lufs: float = -14.0
    music_volume_db: float = -18.0
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    # Provider selection
    ai_provider: str = "mock"

    fal_key: str | None = None
    image_edit_model: str = "fal-ai/flux-pro/kontext"
    image_gen_model: str = "fal-ai/flux/schnell"
    upscale_model: str = "fal-ai/clarity-upscaler"
    bg_removal_model: str = "fal-ai/imageutils/rembg"
    video_gen_model: str = "fal-ai/kling-video/v1.6/standard/text-to-video"
    video_edit_model: str = "fal-ai/kling-video/v1.6/standard/video-to-video"

    gemini_api_key: str | None = None
    gemini_image_model: str = "gemini-2.5-flash-image"

    replicate_api_token: str | None = None
    replicate_image_edit_model: str = "black-forest-labs/flux-kontext-pro"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_gb * 1024 * 1024 * 1024)

    @property
    def chunk_size_bytes(self) -> int:
        return self.chunk_size_mb * 1024 * 1024

    def public_url(self, relative: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/files/{relative.lstrip('/')}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
