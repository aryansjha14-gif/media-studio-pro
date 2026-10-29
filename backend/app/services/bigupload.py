"""Resumable, streamed uploads for very large media.

The v1 endpoint read the whole file into memory, which is fine for a photo and
hopeless for a 20 GB video. This module never holds more than one chunk:

    POST /v1/uploads            -> upload_id + chunk size
    PUT  /v1/uploads/{id}?offset=N  (raw chunk body, appended at N)
    GET  /v1/uploads/{id}       -> bytes received so far (resume after a drop)
    POST /v1/uploads/{id}/complete -> registers the media asset

Appending at an explicit offset makes the flow resumable: the client asks for
the current offset and continues from there, so a phone that loses signal at
19 GB does not start again.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from ..config import Settings
from ..schemas import MediaAsset, MediaKind
from ..storage import MediaStore

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".3gp"}


@dataclass
class UploadSession:
    id: str
    filename: str
    mime: str
    kind: str
    total_bytes: int
    received: int
    created_at: float


class UploadManager:
    def __init__(self, store: MediaStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings
        self.root = Path(settings.storage_dir) / "_uploads"
        self.root.mkdir(parents=True, exist_ok=True)

    # -- session bookkeeping ---------------------------------------------- #
    def _dir(self, upload_id: str) -> Path:
        return self.root / upload_id

    def _part(self, upload_id: str) -> Path:
        return self._dir(upload_id) / "part.bin"

    def _meta(self, upload_id: str) -> Path:
        return self._dir(upload_id) / "session.json"

    def _save(self, session: UploadSession) -> UploadSession:
        self._meta(session.id).write_text(json.dumps(asdict(session)), encoding="utf-8")
        return session

    def load(self, upload_id: str) -> UploadSession:
        path = self._meta(upload_id)
        if not path.exists():
            raise FileNotFoundError(f"unknown upload id: {upload_id}")
        return UploadSession(**json.loads(path.read_text(encoding="utf-8")))

    # -- API --------------------------------------------------------------- #
    def create(self, filename: str, total_bytes: int, mime: str | None) -> UploadSession:
        if total_bytes > self.settings.max_upload_bytes:
            raise ValueError(
                f"file is {total_bytes / 1024**3:.1f} GB; limit is {self.settings.max_upload_gb} GB"
            )
        suffix = Path(filename).suffix.lower()
        if suffix in VIDEO_EXT or (mime or "").startswith("video/"):
            kind = MediaKind.video.value
        elif suffix in IMAGE_EXT or (mime or "").startswith("image/"):
            kind = MediaKind.image.value
        else:
            raise ValueError(f"unsupported file type: {suffix or mime}")

        upload_id = uuid.uuid4().hex[:16]
        self._dir(upload_id).mkdir(parents=True, exist_ok=True)
        self._part(upload_id).touch()
        return self._save(UploadSession(
            id=upload_id, filename=filename, mime=mime or "application/octet-stream",
            kind=kind, total_bytes=total_bytes, received=0, created_at=time.time(),
        ))

    def append(self, upload_id: str, offset: int, data: bytes) -> UploadSession:
        session = self.load(upload_id)
        if offset != session.received:
            raise ValueError(f"offset mismatch: expected {session.received}, got {offset}")
        if session.received + len(data) > session.total_bytes:
            raise ValueError("chunk would exceed the declared file size")
        with self._part(upload_id).open("ab") as fh:
            fh.write(data)
        session.received += len(data)
        return self._save(session)

    async def append_stream(self, upload_id: str, offset: int, stream) -> UploadSession:
        """Append from an async iterator without loading the chunk in memory."""
        session = self.load(upload_id)
        if offset != session.received:
            raise ValueError(f"offset mismatch: expected {session.received}, got {offset}")
        written = 0
        with self._part(upload_id).open("ab") as fh:
            async for piece in stream:
                fh.write(piece)
                written += len(piece)
        session.received += written
        return self._save(session)

    async def complete(self, upload_id: str) -> tuple[MediaAsset, dict]:
        """Promote the uploaded file into the media store, with probe + proxy."""
        from . import image_ops, video_ops

        session = self.load(upload_id)
        if session.received != session.total_bytes:
            raise ValueError(
                f"upload incomplete: {session.received} of {session.total_bytes} bytes"
            )

        media_id = self.store.new_id()
        suffix = Path(session.filename).suffix.lower() or (
            ".mp4" if session.kind == MediaKind.video.value else ".jpg"
        )
        raw = self.store.path_for(media_id, f"original{suffix}")
        shutil.move(str(self._part(upload_id)), raw)

        report: dict = {"proxy": None, "preview": None}
        if session.kind == MediaKind.image.value:
            img = image_ops.load_image(raw)
            thumb = self.store.path_for(media_id, "thumb.jpg")
            image_ops.make_thumbnail(img, thumb)
            preview = img.copy()
            preview.thumbnail(
                (self.settings.preview_long_edge, self.settings.preview_long_edge),
                image_ops.Image.LANCZOS,
            )
            image_ops.save_jpeg(preview, self.store.path_for(media_id, "preview.jpg"), 88)
            report["preview"] = "preview.jpg"
            asset = self.store.asset_from_file(
                raw, MediaKind.image, media_id=media_id, thumb_name="thumb.jpg",
                width=img.width, height=img.height, mime=session.mime,
                meta={"original_filename": session.filename, "upload": "chunked"},
            )
        else:
            info = await video_ops.probe(raw)
            thumb = self.store.path_for(media_id, "thumb.jpg")
            await video_ops.thumbnail(raw, thumb, at=min(1.0, (info.get("duration") or 1) / 2))
            # Low-res proxy keeps timeline scrubbing usable on a 4K hour-long file.
            try:
                await video_ops.make_proxy(
                    raw, self.store.path_for(media_id, "proxy.mp4"), self.settings.proxy_height
                )
                report["proxy"] = "proxy.mp4"
            except Exception as exc:  # noqa: BLE001 - proxy is an optimisation
                report["proxy_error"] = str(exc)
            asset = self.store.asset_from_file(
                raw, MediaKind.video, media_id=media_id, thumb_name="thumb.jpg",
                width=info.get("width"), height=info.get("height"),
                duration=info.get("duration"), mime=session.mime,
                meta={
                    "original_filename": session.filename, "upload": "chunked",
                    "fps": info.get("fps"), "codec": info.get("codec"),
                },
            )

        shutil.rmtree(self._dir(upload_id), ignore_errors=True)
        return asset, report
