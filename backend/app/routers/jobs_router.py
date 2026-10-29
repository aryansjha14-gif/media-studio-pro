"""Job polling. The Android client hits this every ~1.5s while a job runs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..jobs import jobs
from ..schemas import Job

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.get("", response_model=list[Job])
async def list_jobs(limit: int = 25) -> list[Job]:
    return jobs.list_recent(limit=limit)


@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str) -> Job:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"unknown job id: {job_id}")
    return job
