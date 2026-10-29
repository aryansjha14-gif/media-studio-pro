"""Minimal async job manager.

Everything long-running (AI calls, video encodes) returns a Job immediately and
the client polls GET /v1/jobs/{id}. This keeps the mobile client simple and
survives slow model cold-starts.

Production note: this is in-process and single-node. For multi-replica deploys
swap the store for Redis + a worker queue (Celery / RQ / arq). The router and
service code does not change — only `JobManager.submit` and `JobManager.get`.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable

from .schemas import Job, JobStatus, MediaAsset

log = logging.getLogger(__name__)

JobFn = Callable[[], Awaitable[MediaAsset]]


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: set[asyncio.Task] = set()

    def create(self, kind: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:16], kind=kind)
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_recent(self, limit: int = 50) -> list[Job]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def submit(self, kind: str, fn: JobFn) -> Job:
        job = self.create(kind)
        task = asyncio.create_task(self._run(job, fn))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def _run(self, job: Job, fn: JobFn) -> None:
        job.status = JobStatus.running
        job.progress = 0.05
        job.updated_at = datetime.now(timezone.utc)
        try:
            asset = await fn()
            job.asset = asset
            job.status = JobStatus.succeeded
            job.progress = 1.0
        except NotImplementedError as exc:
            job.status = JobStatus.failed
            job.error = f"not supported by the configured provider: {exc}"
            log.warning("job %s unsupported: %s", job.id, exc)
        except Exception as exc:  # noqa: BLE001 — surface any provider error
            job.status = JobStatus.failed
            job.error = f"{type(exc).__name__}: {exc}"
            log.exception("job %s failed", job.id)
        finally:
            job.updated_at = datetime.now(timezone.utc)


jobs = JobManager()
