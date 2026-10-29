"""Feature coverage, so the claim of 200+ functions is checkable."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..features import all_features, summary

router = APIRouter(prefix="/v1/features", tags=["features"])


@router.get("/summary")
async def feature_summary() -> dict:
    return summary()


@router.get("")
async def feature_list(status: str | None = Query(default=None),
                       module: str | None = Query(default=None)) -> list[dict]:
    items = all_features()
    if status:
        items = [f for f in items if f["status"] == status]
    if module:
        items = [f for f in items if f["module"] == module]
    return items
