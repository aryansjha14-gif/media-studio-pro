"""Local-disk media store.

Layout:
    <storage_dir>/<media_id>/original.<ext>
    <storage_dir>/<media_id>/thumb.jpg
    <storage_dir>/<media_id>/asset.json

Swap this class out for S3/R2/GCS in production: implement the same four
methods and nothing else in the codebase changes.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from .config import Settings
from .schemas import MediaAsset, MediaKind


class MediaStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = Path(settings.storage_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    # -- paths ------------------------------------------------------------- #
    def dir_for(self, media_id: str) -> Path:
        p = self.root / media_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def path_for(self, media_id: str, filename: str) -> Path:
        return self.dir_for(media_id) / filename

    def resolve(self, media_id: str, filename: str) -> Path:
        path = (self.root / media_id / filename).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("path traversal blocked")
        return path

    # -- assets ------------------------------------------------------------ #
    def new_id(self) -> str:
        return uuid.uuid4().hex[:16]

    def save_asset(self, asset: MediaAsset) -> MediaAsset:
        meta_path = self.path_for(asset.id, "asset.json")
        meta_path.write_text(asset.model_dump_json(indent=2), encoding="utf-8")
        return asset

    def load_asset(self, media_id: str) -> MediaAsset:
        meta_path = self.root / media_id / "asset.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"unknown media id: {media_id}")
        return MediaAsset.model_validate_json(meta_path.read_text(encoding="utf-8"))

    def find_file(self, media_id: str) -> Path:
        """The primary file of an asset — never the thumbnail or metadata."""
        d = self.root / media_id
        if not d.is_dir():
            raise FileNotFoundError(f"unknown media id: {media_id}")
        # Recorded explicitly at save time, so lookups never guess.
        try:
            recorded = self.load_asset(media_id).meta.get("filename")
        except (FileNotFoundError, ValueError):
            recorded = None
        if recorded and (d / recorded).exists():
            return d / recorded
        for pattern in ("original.*", "result.*", "upload.*"):
            for candidate in sorted(d.glob(pattern)):
                if "thumb" not in candidate.name:
                    return candidate
        for candidate in sorted(d.iterdir()):
            if candidate.suffix.lower() not in {".json", ".txt"} and "thumb" not in candidate.name:
                return candidate
        raise FileNotFoundError(f"no media file for {media_id}")

    def write_bytes(self, media_id: str, filename: str, data: bytes) -> Path:
        path = self.path_for(media_id, filename)
        path.write_bytes(data)
        return path

    def copy_in(self, media_id: str, src: Path, filename: str) -> Path:
        dst = self.path_for(media_id, filename)
        shutil.copyfile(src, dst)
        return dst

    # -- URLs -------------------------------------------------------------- #
    def url_for(self, media_id: str, filename: str) -> str:
        return self.settings.public_url(f"{media_id}/{filename}")

    def asset_from_file(
        self,
        path: Path,
        kind: MediaKind,
        *,
        media_id: str | None = None,
        thumb_name: str | None = None,
        width: int | None = None,
        height: int | None = None,
        duration: float | None = None,
        mime: str | None = None,
        meta: dict | None = None,
    ) -> MediaAsset:
        media_id = media_id or self.new_id()
        d = self.dir_for(media_id)
        target = d / f"original{path.suffix.lower()}"
        if path.resolve() != target.resolve():
            shutil.copyfile(path, target)
        asset = MediaAsset(
            id=media_id,
            kind=kind,
            url=self.url_for(media_id, target.name),
            thumb_url=self.url_for(media_id, thumb_name) if thumb_name else None,
            width=width,
            height=height,
            duration=duration,
            size_bytes=target.stat().st_size,
            mime=mime,
            meta={**(meta or {}), "filename": target.name},
        )
        return self.save_asset(asset)
