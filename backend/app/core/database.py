"""SQLite database layer using aiosqlite."""

import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator

import aiosqlite

from .config import settings

# SQL Schema
SCHEMA = """
-- Benchmark jobs
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    chain_id INTEGER NOT NULL,
    chain_name TEXT NOT NULL,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    duration_seconds REAL,
    error_message TEXT
);

-- Providers per job
CREATE TABLE IF NOT EXISTS job_providers (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    region TEXT
);

-- Test parameters per job
CREATE TABLE IF NOT EXISTS job_test_params (
    job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    params_json TEXT NOT NULL
);

-- Tests executed per job
CREATE TABLE IF NOT EXISTS job_tests_executed (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    test_id INTEGER NOT NULL,
    test_json TEXT NOT NULL
);

-- Sequential test results
CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    provider_id TEXT NOT NULL,
    test_id INTEGER NOT NULL,
    test_name TEXT NOT NULL,
    category TEXT NOT NULL,
    label TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    iteration_type TEXT NOT NULL,
    response_time_ms REAL,
    success INTEGER NOT NULL,
    error_type TEXT,
    error_message TEXT,
    http_status INTEGER,
    response_size_bytes INTEGER,
    timestamp TEXT NOT NULL
);

-- Load test results
CREATE TABLE IF NOT EXISTS load_test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    provider_id TEXT NOT NULL,
    test_id INTEGER NOT NULL,
    test_name TEXT NOT NULL,
    method TEXT NOT NULL,
    concurrency INTEGER NOT NULL,
    total_time_ms REAL NOT NULL,
    min_ms REAL NOT NULL,
    max_ms REAL NOT NULL,
    avg_ms REAL NOT NULL,
    p50_ms REAL NOT NULL,
    p95_ms REAL NOT NULL,
    p99_ms REAL NOT NULL,
    success_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    success_rate REAL NOT NULL,
    throughput_rps REAL NOT NULL,
    errors_json TEXT,
    timestamp TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_jobs_chain ON jobs(chain_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_test_results_job ON test_results(job_id);
CREATE INDEX IF NOT EXISTS idx_test_results_provider ON test_results(provider_id);
CREATE INDEX IF NOT EXISTS idx_load_results_job ON load_test_results(job_id);
"""


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(settings.db_path)
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to the database and initialize schema."""
        settings.ensure_data_dir()
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.executescript(SCHEMA)
        await self._connection.commit()

    async def disconnect(self) -> None:
        """Disconnect from the database."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def conn(self) -> aiosqlite.Connection:
        """Get the database connection."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection

    # ========================================================================
    # Jobs
    # ========================================================================

    async def create_job(
        self,
        job_id: str,
        chain_id: int,
        chain_name: str,
        status: str,
        config: dict[str, Any],
    ) -> None:
        """Create a new benchmark job."""
        await self.conn.execute(
            """
            INSERT INTO jobs (id, chain_id, chain_name, status, config_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, chain_id, chain_name, status, json.dumps(config), datetime.utcnow().isoformat()),
        )
        await self.conn.commit()

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        completed_at: datetime | None = None,
        duration_seconds: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update job status."""
        await self.conn.execute(
            """
            UPDATE jobs
            SET status = ?, completed_at = ?, duration_seconds = ?, error_message = ?
            WHERE id = ?
            """,
            (
                status,
                completed_at.isoformat() if completed_at else None,
                duration_seconds,
                error_message,
                job_id,
            ),
        )
        await self.conn.commit()

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get a job by ID."""
        async with self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        return None

    async def list_jobs(self, chain_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """List all jobs, optionally filtered by chain."""
        if chain_id is not None:
            query = "SELECT * FROM jobs WHERE chain_id = ? ORDER BY created_at DESC LIMIT ?"
            params = (chain_id, limit)
        else:
            query = "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?"
            params = (limit,)

        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job and all related data."""
        cursor = await self.conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await self.conn.commit()
        return cursor.rowcount > 0

    # ========================================================================
    # Providers
    # ========================================================================

    async def add_job_provider(
        self, job_id: str, provider_id: str, name: str, url: str, region: str | None
    ) -> None:
        """Add a provider to a job."""
        await self.conn.execute(
            """
            INSERT INTO job_providers (id, job_id, name, url, region)
            VALUES (?, ?, ?, ?, ?)
            """,
            (provider_id, job_id, name, url, region),
        )
        await self.conn.commit()

    async def get_job_providers(self, job_id: str) -> list[dict[str, Any]]:
        """Get all providers for a job."""
        async with self.conn.execute(
            "SELECT * FROM job_providers WHERE job_id = ?", (job_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ========================================================================
    # Test Parameters
    # ========================================================================

    async def save_job_test_params(self, job_id: str, params: dict[str, Any]) -> None:
        """Save test parameters for a job."""
        await self.conn.execute(
            """
            INSERT OR REPLACE INTO job_test_params (job_id, params_json)
            VALUES (?, ?)
            """,
            (job_id, json.dumps(params)),
        )
        await self.conn.commit()

    async def get_job_test_params(self, job_id: str) -> dict[str, Any] | None:
        """Get test parameters for a job."""
        async with self.conn.execute(
            "SELECT params_json FROM job_test_params WHERE job_id = ?", (job_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row["params_json"])
        return None

    # ========================================================================
    # Tests Executed
    # ========================================================================

    async def save_job_test_executed(self, job_id: str, test_id: int, test_data: dict[str, Any]) -> None:
        """Save a test that was executed."""
        await self.conn.execute(
            """
            INSERT INTO job_tests_executed (job_id, test_id, test_json)
            VALUES (?, ?, ?)
            """,
            (job_id, test_id, json.dumps(test_data)),
        )
        await self.conn.commit()

    async def get_job_tests_executed(self, job_id: str) -> list[dict[str, Any]]:
        """Get all tests executed for a job."""
        async with self.conn.execute(
            "SELECT test_json FROM job_tests_executed WHERE job_id = ? ORDER BY test_id",
            (job_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [json.loads(row["test_json"]) for row in rows]

    # ========================================================================
    # Test Results
    # ========================================================================

    async def save_test_result(self, result: dict[str, Any]) -> None:
        """Save a test result."""
        await self.conn.execute(
            """
            INSERT INTO test_results (
                job_id, provider_id, test_id, test_name, category, label,
                iteration, iteration_type, response_time_ms, success,
                error_type, error_message, http_status, response_size_bytes, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["job_id"],
                result["provider_id"],
                result["test_id"],
                result["test_name"],
                result["category"],
                result["label"],
                result["iteration"],
                result["iteration_type"],
                result.get("response_time_ms"),
                1 if result["success"] else 0,
                result.get("error_type"),
                result.get("error_message"),
                result.get("http_status"),
                result.get("response_size_bytes"),
                result.get("timestamp", datetime.utcnow().isoformat()),
            ),
        )
        await self.conn.commit()

    async def get_test_results(self, job_id: str) -> list[dict[str, Any]]:
        """Get all test results for a job."""
        async with self.conn.execute(
            "SELECT * FROM test_results WHERE job_id = ? ORDER BY provider_id, test_id, iteration",
            (job_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ========================================================================
    # Load Test Results
    # ========================================================================

    async def save_load_test_result(self, result: dict[str, Any]) -> None:
        """Save a load test result."""
        await self.conn.execute(
            """
            INSERT INTO load_test_results (
                job_id, provider_id, test_id, test_name, method, concurrency,
                total_time_ms, min_ms, max_ms, avg_ms, p50_ms, p95_ms, p99_ms,
                success_count, error_count, success_rate, throughput_rps, errors_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["job_id"],
                result["provider_id"],
                result["test_id"],
                result["test_name"],
                result["method"],
                result["concurrency"],
                result["total_time_ms"],
                result["min_ms"],
                result["max_ms"],
                result["avg_ms"],
                result["p50_ms"],
                result["p95_ms"],
                result["p99_ms"],
                result["success_count"],
                result["error_count"],
                result["success_rate"],
                result["throughput_rps"],
                json.dumps(result.get("errors", [])),
                result.get("timestamp", datetime.utcnow().isoformat()),
            ),
        )
        await self.conn.commit()

    async def get_load_test_results(self, job_id: str) -> list[dict[str, Any]]:
        """Get all load test results for a job."""
        async with self.conn.execute(
            "SELECT * FROM load_test_results WHERE job_id = ? ORDER BY provider_id, test_id",
            (job_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                r = dict(row)
                r["errors"] = json.loads(r.pop("errors_json") or "[]")
                results.append(r)
            return results


# Global database instance
_db: Database | None = None


async def get_db() -> Database:
    """Get the database instance, initializing if needed."""
    global _db
    if _db is None:
        _db = Database()
        await _db.connect()
    return _db


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[Database, None]:
    """Context manager for database access."""
    db = await get_db()
    yield db


async def init_db() -> None:
    """Initialize the database."""
    await get_db()
