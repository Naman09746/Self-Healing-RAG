"""Unit tests for the Redis-backed evaluation queue (EvaluationQueue, EvalJob)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.evaluation.queue import (
    EvaluationQueue,
    EvalJob,
    JobStatus,
)


class TestEvalJob:
    def test_create(self) -> None:
        job = EvalJob.create(dataset_path="/tmp/test.jsonl", limit=5)
        assert job.job_id is not None
        assert job.dataset_path == "/tmp/test.jsonl"
        assert job.limit == 5
        assert job.status == JobStatus.QUEUED
        assert job.created_at > 0
        assert job.started_at is None
        assert job.finished_at is None
        assert job.error is None
        assert job.result_path is None

    def test_create_defaults(self) -> None:
        job = EvalJob.create(dataset_path="/tmp/test.jsonl")
        assert job.limit is None

    def test_to_dict(self) -> None:
        job = EvalJob.create(dataset_path="/tmp/ds.jsonl")
        d = job.to_dict()
        assert d["job_id"] == job.job_id
        assert d["dataset_path"] == "/tmp/ds.jsonl"
        assert d["status"] == "QUEUED"

    def test_from_dict(self) -> None:
        d = {
            "job_id": "abc-123",
            "dataset_path": "/tmp/ds.jsonl",
            "status": "COMPLETED",
            "limit": 10,
            "created_at": 1000.0,
            "started_at": 1001.0,
            "finished_at": 1005.0,
            "error": None,
            "result_path": "/tmp/report.json",
        }
        job = EvalJob.from_dict(d)
        assert job.job_id == "abc-123"
        assert job.status == JobStatus.COMPLETED
        assert job.limit == 10
        assert job.result_path == "/tmp/report.json"

    def test_round_trip(self) -> None:
        original = EvalJob.create(dataset_path="/tmp/ds.jsonl", limit=3)
        d = original.to_dict()
        d["status"] = "PROCESSING"
        restored = EvalJob.from_dict(d)
        assert restored.job_id == original.job_id
        assert restored.status == JobStatus.PROCESSING
        assert restored.limit == 3


@pytest.fixture
def mock_redis() -> MagicMock:
    """Create a fully mocked async Redis client."""
    mock = MagicMock()
    # Pipeline mock
    pipe = AsyncMock()
    pipe.hset.return_value = pipe
    pipe.rpush.return_value = pipe
    pipe.execute.return_value = [True, True]
    mock.pipeline.return_value.__aenter__.return_value = pipe

    mock.ping = AsyncMock(return_value=True)
    mock.hset = AsyncMock(return_value=True)
    mock.hgetall = AsyncMock(return_value={})
    mock.lpop = AsyncMock(return_value=None)
    mock.llen = AsyncMock(return_value=0)
    mock.rpush = AsyncMock(return_value=1)
    mock.incr = AsyncMock(return_value=1)
    mock.decr = AsyncMock(return_value=0)
    mock.keys = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def queue(mock_redis: MagicMock) -> EvaluationQueue:
    q = EvaluationQueue(redis_url="redis://mock:6379/0")
    q._redis = mock_redis  # type: ignore[assignment]
    return q


class TestEvaluationQueue:
    @pytest.mark.asyncio
    async def test_connect(self) -> None:
        q = EvaluationQueue(redis_url="redis://mock:6379/0")
        mock = AsyncMock()
        mock.ping = AsyncMock(return_value=True)
        with patch("redis.asyncio.from_url", return_value=mock):
            await q.connect()
            assert q._redis is not None
        await q.close()

    @pytest.mark.asyncio
    async def test_is_healthy_connected(self, queue: EvaluationQueue) -> None:
        assert await queue.is_healthy() is True

    @pytest.mark.asyncio
    async def test_is_healthy_disconnected(self) -> None:
        q = EvaluationQueue(redis_url="redis://mock:6379/0")
        assert await q.is_healthy() is False

    @pytest.mark.asyncio
    async def test_enqueue(self, queue: EvaluationQueue, mock_redis: MagicMock) -> None:
        job_id = await queue.enqueue("/tmp/test.jsonl", limit=5)
        assert job_id is not None
        assert len(job_id) > 0

    @pytest.mark.asyncio
    async def test_dequeue_empty(self, queue: EvaluationQueue) -> None:
        job = await queue.dequeue()
        assert job is None

    @pytest.mark.asyncio
    async def test_dequeue_with_job(self, queue: EvaluationQueue, mock_redis: MagicMock) -> None:
        mock_redis.lpop.return_value = "job-1"
        mock_redis.hgetall.return_value = {
            "job_id": "job-1",
            "dataset_path": "/tmp/test.jsonl",
            "status": "QUEUED",
            "limit": "",
            "created_at": str(time.time()),
            "started_at": "",
            "finished_at": "",
            "error": "",
            "result_path": "",
        }
        job = await queue.dequeue()
        assert job is not None
        assert job.job_id == "job-1"
        assert job.status == JobStatus.PROCESSING
        assert job.started_at is not None

    @pytest.mark.asyncio
    async def test_complete_job(self, queue: EvaluationQueue, mock_redis: MagicMock) -> None:
        mock_redis.hgetall.return_value = {
            "job_id": "job-1",
            "dataset_path": "/tmp/test.jsonl",
            "status": "PROCESSING",
            "limit": "",
            "created_at": str(time.time()),
            "started_at": str(time.time()),
            "finished_at": "",
            "error": "",
            "result_path": "",
        }
        await queue.complete("job-1", result_path="/tmp/report.json", error=None)

    @pytest.mark.asyncio
    async def test_complete_job_with_error(self, queue: EvaluationQueue, mock_redis: MagicMock) -> None:
        mock_redis.hgetall.return_value = {
            "job_id": "job-1",
            "dataset_path": "/tmp/test.jsonl",
            "status": "PROCESSING",
            "limit": "",
            "created_at": str(time.time()),
            "started_at": "",
            "finished_at": "",
            "error": "",
            "result_path": "",
        }
        await queue.complete("job-1", result_path="", error="Something went wrong")

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, queue: EvaluationQueue) -> None:
        job = await queue.get_job("nonexistent")
        assert job is None

    @pytest.mark.asyncio
    async def test_get_job_found(self, queue: EvaluationQueue, mock_redis: MagicMock) -> None:
        mock_redis.hgetall.return_value = {
            "job_id": "job-1",
            "dataset_path": "/tmp/test.jsonl",
            "status": "QUEUED",
            "limit": "",
            "created_at": str(time.time()),
            "started_at": "",
            "finished_at": "",
            "error": "",
            "result_path": "",
        }
        job = await queue.get_job("job-1")
        assert job is not None
        assert job.job_id == "job-1"

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, queue: EvaluationQueue) -> None:
        jobs = await queue.list_jobs()
        assert jobs == []

    @pytest.mark.asyncio
    async def test_list_jobs_with_filter(self, queue: EvaluationQueue, mock_redis: MagicMock) -> None:
        mock_redis.keys.return_value = ["eval:job:1"]
        mock_redis.hgetall.return_value = {
            "job_id": "1",
            "dataset_path": "/tmp/test.jsonl",
            "status": "COMPLETED",
            "limit": "",
            "created_at": str(time.time()),
            "started_at": "",
            "finished_at": "",
            "error": "",
            "result_path": "",
        }
        jobs = await queue.list_jobs(status_filter=JobStatus.COMPLETED)
        assert len(jobs) == 1

        jobs_not_found = await queue.list_jobs(status_filter=JobStatus.FAILED)
        assert len(jobs_not_found) == 0

    @pytest.mark.asyncio
    async def test_queue_length(self, queue: EvaluationQueue, mock_redis: MagicMock) -> None:
        mock_redis.llen.return_value = 3
        length = await queue.queue_length()
        assert length == 3

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        q = EvaluationQueue(redis_url="redis://mock:6379/0")
        mock = AsyncMock()
        q._redis = mock  # type: ignore[assignment]
        await q.close()
        mock.close.assert_awaited_once()