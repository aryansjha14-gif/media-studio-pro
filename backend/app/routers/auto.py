"""Prompt-driven editing: plan first, render only after review.

POST /v1/auto/plan    -> an edit decision list you can inspect and correct
POST /v1/auto/render  -> renders an approved plan as a job
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..jobs import jobs
from ..schemas import Job, MediaAsset, MediaKind
from ..schemas_extra import AutoPlan, PlanRequest, RenderRequest
from ..services import analysis, autoedit, planner
from ..services.video_ops import FFmpegError

router = APIRouter(prefix="/v1/auto", tags=["auto"])
log = logging.getLogger(__name__)


def _paths(request: Request, media_ids: list[str]) -> tuple[dict[str, Path], dict[str, MediaAsset]]:
    store = request.app.state.store
    paths: dict[str, Path] = {}
    assets: dict[str, MediaAsset] = {}
    for media_id in media_ids:
        try:
            asset = store.load_asset(media_id)
            paths[media_id] = store.find_file(media_id)
            assets[media_id] = asset
        except FileNotFoundError as exc:
            raise HTTPException(404, f"unknown media id: {media_id}") from exc
    return paths, assets


@router.post("/plan", response_model=AutoPlan)
async def plan(request: Request, body: PlanRequest) -> AutoPlan:
    """Analyse the footage and return the proposed edit, without rendering."""
    paths, assets = _paths(request, body.media_ids)

    analysed = []
    for media_id, path in paths.items():
        if assets[media_id].kind is MediaKind.video:
            try:
                analysed.append(await analysis.analyse_clip(path, media_id))
            except Exception as exc:  # noqa: BLE001
                log.warning("analysis failed for %s: %s", media_id, exc)
        else:
            # A still photograph becomes one fixed shot.
            analysed.append({
                "media_id": media_id,
                "info": {"duration": 3.0},
                "segments": [{
                    "source_id": media_id, "start": 0.0, "end": 3.0, "duration": 3.0,
                    "quality": 0.8, "luma": 0.5, "sharpness": 0.5,
                    "hash": f"photo-{media_id}",
                }],
            })

    if not analysed:
        raise HTTPException(422, "none of the supplied media could be analysed")

    return planner.build_plan(
        body.prompt, analysed,
        width=body.width, height=body.height, fps=body.fps,
        music_media_id=body.music_media_id,
    )


@router.post("/render", response_model=Job, status_code=202)
async def render(request: Request, body: RenderRequest) -> Job:
    """Render an approved plan. Long job: poll /v1/jobs/{id}."""
    settings = request.app.state.settings
    store = request.app.state.store
    plan_obj = body.plan

    ids = {s.source_id for s in plan_obj.segments}
    paths, _ = _paths(request, list(ids))

    music_path = None
    music_id = body.music_media_id or plan_obj.audio.get("music_media_id")
    if music_id:
        try:
            music_path = store.find_file(music_id)
        except FileNotFoundError:
            plan_obj.warnings.append("music track not found; rendering without music")

    async def work() -> MediaAsset:
        media_id = store.new_id()
        out = store.path_for(media_id, "render.mp4")
        report = await autoedit.render(plan_obj, paths, out, settings, music=music_path)
        thumb_name = None
        try:
            await autoedit.video_ops.thumbnail(out, store.path_for(media_id, "thumb.jpg"),
                                               at=min(1.0, (report.get("duration") or 1) / 2))
            thumb_name = "thumb.jpg"
        except FFmpegError:
            pass
        asset = store.asset_from_file(
            out, MediaKind.video, media_id=media_id, thumb_name=thumb_name,
            width=report.get("width"), height=report.get("height"),
            duration=report.get("duration"), mime="video/mp4",
            meta={
                "tool": "auto_edit",
                "prompt": plan_obj.prompt,
                "shots_planned": report.get("shots_planned"),
                "shots_rendered": report.get("shots_rendered"),
                "warnings": report.get("warnings", []),
                "report": {k: report.get(k) for k in
                           ("duration", "width", "height", "fps", "has_audio")},
            },
        )
        return asset

    return jobs.submit("auto.render", work)
