"""Resumable uploads for very large files (up to MAX_UPLOAD_GB, 20 GB by default).

The body is streamed straight to disk, so memory use stays flat whether the file
is 4 MB or 20 GB.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..schemas import MediaAsset
from ..schemas_extra import UploadInitRequest, UploadSessionOut

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])


def manager(request: Request):
    return request.app.state.uploads


@router.post("", response_model=UploadSessionOut, status_code=201)
async def init_upload(request: Request, body: UploadInitRequest) -> UploadSessionOut:
    try:
        session = manager(request).create(body.filename, body.total_bytes, body.mime)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    settings = request.app.state.settings
    return UploadSessionOut(
        upload_id=session.id, received=session.received, total_bytes=session.total_bytes,
        chunk_size=settings.chunk_size_bytes, complete=False,
    )


@router.put("/{upload_id}", response_model=UploadSessionOut)
async def append_chunk(request: Request, upload_id: str, offset: int = 0) -> UploadSessionOut:
    """Append the raw request body at `offset`. Send the next chunk from `received`."""
    try:
        session = await manager(request).append_stream(upload_id, offset, request.stream())
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return UploadSessionOut(
        upload_id=session.id, received=session.received, total_bytes=session.total_bytes,
        chunk_size=request.app.state.settings.chunk_size_bytes,
        complete=session.received >= session.total_bytes,
    )


@router.get("/{upload_id}", response_model=UploadSessionOut)
async def upload_status(request: Request, upload_id: str) -> UploadSessionOut:
    """Ask where to resume after a dropped connection."""
    try:
        session = manager(request).load(upload_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return UploadSessionOut(
        upload_id=session.id, received=session.received, total_bytes=session.total_bytes,
        chunk_size=request.app.state.settings.chunk_size_bytes,
        complete=session.received >= session.total_bytes,
    )


@router.post("/{upload_id}/complete", response_model=MediaAsset, status_code=201)
async def complete_upload(request: Request, upload_id: str) -> MediaAsset:
    try:
        asset, report = await manager(request).complete(upload_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    asset.meta["proxy"] = report.get("proxy")
    asset.meta["preview"] = report.get("preview")
    return request.app.state.store.save_asset(asset)
