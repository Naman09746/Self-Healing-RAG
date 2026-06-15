"""Redis-backed evaluation queue.

Enables async / offline evaluation jobs to be queued, processed, and
tracked without blocking the main API.

Job lifecycle:
    QUEUED → PROCESSING → COMPLETED / FAILED

Queue keys (Redis):
    eval:queue          – List of pending job IDs
    eval:job:<id>       – Hash with job payload fields
    eval:result:<id>    – Hash with result fields
    evals:active_count  – Counter of currently processing jobs
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Job data
# ---------------------------------------------------------------------------

@dataclass
class EvalJob:
    """An evaluation job request."""
    job_id: str
    dataset_path: str
    status: JobStatus = JobStatus.QUEUED
    limit: Optional[int] = None
    created_at: float = 0.0
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    result_path: Optional[str] = None  # Path to the JSON report

    @classmethod
    def create(cls, dataset_path: str, limit: Optional[int] = None) -> "EvalJob":
        return cls(
            job_id=str(uuid.uuid4()),
            dataset_path=dataset_path,
            limit=limit,
            created_at=time.time(),
        )

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "dataset_path": self.dataset_path,
            "status": self.status.value,
            "limit": self.limit,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "result_path": self.result_path,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvalJob":
        return cls(
            job_id=str(d["job_id"]),
            dataset_path=str(d["dataset_path"]),
            status=JobStatus(d.get("status", "QUEUED")),
            limit=d.get("limit"),
            created_at=float(d.get("created_at", 0)),
            started_at=float(d["started_at"]) if d.get("started_at") else None,
            finished_at=float(d["finished_at"]) if d.get("finished_at") else None,
            error=d.get("error"),
            result_path=d.get("result_path"),
        )


# ---------------------------------------------------------------------------
# Evaluation Queue
# ---------------------------------------------------------------------------

class EvaluationQueue:
    """Redis-backed queue for async evaluation jobs."""

    def __init__(self, redis_url: Optional[str] = None) -> None:
        self._redis_url = redis_url or _DEFAULT_REDIS_URL
        self._redis: Optional[aioredis.Redis] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open Redis connection."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url, decode_responses=True
            )
            await self._redis.ping()
            logger.info("Connected to Redis evaluation queue at %s", self._redis_url)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
            logger.info("Redis evaluation queue disconnected.")

    async def is_healthy(self) -> bool:
        """Check if Redis is reachable."""
        try:
            if self._redis is None:
                return False
            await self._redis.ping()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        dataset_path: str,
        limit: Optional[int] = None,
    ) -> str:
        """Add an evaluation job to the queue.

        Returns the job ID.
        """
        await self._ensure_connected()

        job = EvalJob.create(dataset_path=dataset_path, limit=limit)
        job_key = f"eval:job:{job.job_id}"

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.hset(job_key, mapping=job.to_dict())  # type: ignore[arg-type]
            pipe.rpush("eval:queue", job.job_id)
            await pipe.execute()

        logger.info("Enqueued eval job %s (dataset=%s)", job.job_id, dataset_path)
        return job.job_id

    async def dequeue(self) -> Optional[EvalJob]:
        """Pop the next pending job from the queue.

        Returns None if the queue is empty.
        """
        await self._ensure_connected()

        job_id = await self._redis.lpop("eval:queue")
        if job_id is None:
            return None

        job_dict = await self._redis.hgetall(f"eval:job:{job_id}")
        if not job_dict:
            logger.warning("Job %s has no data; skipping.", job_id)
            return None

        job = EvalJob.from_dict(job_dict)
        job.status = JobStatus.PROCESSING
        job.started_at = time.time()

        await self._redis.hset(
            f"eval:job:{job.job_id}",
            mapping=job.to_dict(),
        )
        await self._redis.incr("eval:active_count")

        return job

    async def complete(
        self,
        job_id: str,
        result_path: str,
        error: Optional[str] = None,
    ) -> None:
        """Mark a job as completed or failed."""
        await self._ensure_connected()

        status = JobStatus.FAILED if error else JobStatus.COMPLETED
        job_dict = await self._redis.hgetall(f"eval:job:{job_id}")

        if job_dict:
            job = EvalJob.from_dict(job_dict)
            job.status = status
            job.finished_at = time.time()
            job.error = error
            job.result_path = result_path

            await self._redis.hset(
                f"eval:job:{job.job_id}",
                mapping=job.to_dict(),
            )

        await self._redis.decr("eval:active_count")
        logger.info("Job %s → %s", job_id, status.value)

    async def get_job(self, job_id: str) -> Optional[EvalJob]:
        """Get the current state of a job."""
        await self._ensure_connected()

        job_dict = await self._redis.hgetall(f"eval:job:{job_id}")
        if not job_dict:
            return None
        return EvalJob.from_dict(job_dict)

    async def list_jobs(
        self,
        limit: int = 20,
        status_filter: Optional[JobStatus] = None,
    ) -> list[EvalJob]:
        """List recent jobs, optionally filtered by status."""
        await self._ensure_connected()

        all_keys = await self._redis.keys("eval:job:*")
        jobs: list[EvalJob] = []

        for key in all_keys:
            job_dict = await self._redis.hgetall(key)
            if not job_dict:
                continue
            job = EvalJob.from_dict(job_dict)
            if status_filter and job.status != status_filter:
                continue
            jobs.append(job)

        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def queue_length(self) -> int:
        """Get the number of pending jobs."""
        await self._ensure_connected()
        return await self._redis.llen("eval:queue")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_connected(self) -> None:
        if self._redis is None:
            await self.connect()