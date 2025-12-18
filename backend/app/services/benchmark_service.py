"""Benchmark execution service."""

import asyncio
import json
import statistics
import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator

import httpx

from ..core.database import get_db
from ..models import (
    BenchmarkConfig,
    BenchmarkJob,
    JobStatus,
    Provider,
    TestCase,
    TestCategory,
    IterationType,
    SSEEvent,
    ErrorCategory,
)
from .chain_service import chain_service
from .test_definitions import build_test_cases

# eth_getLogs can take a long time for large block ranges
GETLOGS_TIMEOUT_SECONDS = 300  # 5 minutes


class BenchmarkService:
    """Service for running RPC benchmarks."""

    def __init__(self):
        self._running_jobs: dict[str, bool] = {}  # job_id -> cancelled flag

    async def create_job(
        self,
        chain_id: int,
        providers: list[dict[str, Any]],
        config: BenchmarkConfig,
    ) -> BenchmarkJob:
        """Create a new benchmark job."""
        # Get chain config
        chain = chain_service.get_chain(chain_id)
        if chain is None:
            raise ValueError(f"Chain {chain_id} not found")

        # Generate job ID
        job_id = str(uuid.uuid4())[:8]

        # Create provider objects
        provider_objects = []
        for p in providers:
            provider = Provider(
                id=str(uuid.uuid4())[:8],
                name=p["name"],
                url=p["url"],
                region=p.get("region"),
            )
            provider_objects.append(provider)

        # Create job
        job = BenchmarkJob(
            id=job_id,
            chain_id=chain_id,
            chain_name=chain.chain_name,
            status=JobStatus.PENDING,
            config=config,
            providers=provider_objects,
        )

        # Save to database
        db = await get_db()
        await db.create_job(
            job_id=job.id,
            chain_id=job.chain_id,
            chain_name=job.chain_name,
            status=job.status.value,
            config=job.config.model_dump(mode="json"),
        )

        # Save providers
        for provider in provider_objects:
            await db.add_job_provider(
                job_id=job.id,
                provider_id=provider.id,
                name=provider.name,
                url=provider.url,
                region=provider.region,
            )

        # Save test params
        await db.save_job_test_params(
            job_id=job.id,
            params=config.test_params.model_dump(mode="json"),
        )

        return job

    async def run_job(self, job_id: str) -> AsyncGenerator[SSEEvent, None]:
        """Run a benchmark job and yield progress events."""
        db = await get_db()

        # Get job
        job_data = await db.get_job(job_id)
        if job_data is None:
            yield SSEEvent(event="error", data={"message": f"Job {job_id} not found"})
            return

        # Parse config
        config_data = job_data["config_json"]
        if isinstance(config_data, str):
            config_data = json.loads(config_data)
        config = BenchmarkConfig(**config_data)

        # Get providers
        providers_data = await db.get_job_providers(job_id)
        providers = [Provider(**p) for p in providers_data]

        # Mark job as running
        self._running_jobs[job_id] = False  # Not cancelled
        await db.update_job_status(job_id, JobStatus.RUNNING.value)

        start_time = time.time()

        try:
            # Get current block number (use first provider)
            current_block = await self._get_current_block(providers[0].url, config.timeout_seconds)

            # Build test cases
            test_cases = build_test_cases(
                params=config.test_params,
                current_block=current_block,
                enabled_ids=config.enabled_test_ids,
                load_concurrency={
                    "simple": config.load_concurrency_simple,
                    "medium": config.load_concurrency_medium,
                    "complex": config.load_concurrency_complex,
                },
            )

            # Filter by categories and labels
            test_cases = [
                tc for tc in test_cases
                if tc.category in config.categories and tc.label in config.labels
            ]

            # Save tests executed
            for tc in test_cases:
                await db.save_job_test_executed(
                    job_id=job_id,
                    test_id=tc.id,
                    test_data=tc.model_dump(mode="json"),
                )

            # Separate sequential and load tests
            sequential_tests = [tc for tc in test_cases if tc.category != TestCategory.LOAD]
            load_tests = [tc for tc in test_cases if tc.category == TestCategory.LOAD]

            rounds = config.get_round_count()
            total_tests = len(sequential_tests) * len(providers) + len(load_tests) * len(providers)

            # Calculate total work units for progress tracking
            # Each sequential test per round is 1 unit, each load test is worth 1 unit
            total_sequential_units = len(sequential_tests) * len(providers) * rounds
            total_load_units = len(load_tests) * len(providers)
            total_work_units = total_sequential_units + total_load_units
            completed_units = 0

            # Emit job started
            yield SSEEvent(
                event="job_started",
                data={
                    "job_id": job_id,
                    "total_tests": total_tests,
                    "total_sequential": len(sequential_tests),
                    "total_load": len(load_tests),
                    "rounds": rounds,
                    "providers": len(providers),
                    "total_work_units": total_work_units,
                },
            )

            # Run sequential tests in ROUNDS
            # Round 1 = cold (cache miss expected)
            # Round 2+ = warm (cache hit expected after propagation delay)
            for round_num in range(rounds):
                if self._running_jobs.get(job_id):
                    break  # Cancelled

                iteration_type = IterationType.COLD if round_num == 0 else IterationType.WARM

                yield SSEEvent(
                    event="round_started",
                    data={
                        "round": round_num + 1,
                        "total_rounds": rounds,
                        "iteration_type": iteration_type.value,
                    },
                )

                # Run each test once per round, cycling through all providers
                for provider in providers:
                    if self._running_jobs.get(job_id):
                        break

                    for test in sequential_tests:
                        if self._running_jobs.get(job_id):
                            break

                        # Use longer timeout for getLogs
                        timeout = GETLOGS_TIMEOUT_SECONDS if test.rpc_method == "eth_getLogs" else config.timeout_seconds
                        result = await self._execute_rpc_call(
                            provider.url,
                            test.rpc_method,
                            test.rpc_params,
                            timeout,
                        )

                        # Save result
                        test_result = {
                            "job_id": job_id,
                            "provider_id": provider.id,
                            "test_id": test.id,
                            "test_name": test.name,
                            "category": test.category.value,
                            "label": test.label.value,
                            "iteration": round_num + 1,  # Round number as iteration
                            "iteration_type": iteration_type.value,
                            "response_time_ms": result.get("response_time_ms"),
                            "success": result["success"],
                            "error_type": result.get("error_type"),
                            "error_message": result.get("error_message"),
                            "http_status": result.get("http_status"),
                            "response_size_bytes": result.get("response_size_bytes"),
                            "log_count": result.get("log_count"),  # For eth_getLogs tests
                        }
                        await db.save_test_result(test_result)

                        # Update progress
                        completed_units += 1
                        progress = completed_units / total_work_units if total_work_units > 0 else 0

                        yield SSEEvent(
                            event="iteration_complete",
                            data={
                                "test_id": test.id,
                                "test_name": test.name,
                                "round": round_num + 1,
                                "total_rounds": rounds,
                                "iteration_type": iteration_type.value,
                                "provider_name": provider.name,
                                "response_time_ms": result.get("response_time_ms"),
                                "success": result["success"],
                                "progress": progress,
                                "completed_units": completed_units,
                                "total_work_units": total_work_units,
                            },
                        )

                        # Small delay between individual requests
                        if config.delay_ms > 0:
                            await asyncio.sleep(config.delay_ms / 1000)

                # Inter-round delay to allow cache propagation (except after last round)
                if round_num < rounds - 1:
                    yield SSEEvent(
                        event="round_complete",
                        data={
                            "round": round_num + 1,
                            "total_rounds": rounds,
                            "waiting_ms": config.inter_round_delay_ms,
                        },
                    )
                    if config.inter_round_delay_ms > 0:
                        await asyncio.sleep(config.inter_round_delay_ms / 1000)

            yield SSEEvent(
                event="sequential_complete",
                data={"total_rounds": rounds, "tests_per_round": len(sequential_tests) * len(providers)},
            )

            # Run load tests (one provider at a time)
            for provider in providers:
                if self._running_jobs.get(job_id):
                    break

                for test in load_tests:
                    if self._running_jobs.get(job_id):
                        break

                    yield SSEEvent(
                        event="load_test_started",
                        data={
                            "test_id": test.id,
                            "test_name": test.name,
                            "provider_id": provider.id,
                            "provider_name": provider.name,
                            "concurrency": test.concurrency,
                        },
                    )

                    # Run concurrent requests (use longer timeout for getLogs)
                    load_timeout = GETLOGS_TIMEOUT_SECONDS if test.rpc_method == "eth_getLogs" else config.timeout_seconds
                    load_result = await self._execute_load_test(
                        provider.url,
                        test.rpc_method,
                        test.rpc_params,
                        test.concurrency or 50,
                        load_timeout,
                    )

                    # Save load test result
                    load_test_result = {
                        "job_id": job_id,
                        "provider_id": provider.id,
                        "test_id": test.id,
                        "test_name": test.name,
                        "method": test.rpc_method,
                        "concurrency": test.concurrency or 50,
                        **load_result,
                    }
                    await db.save_load_test_result(load_test_result)

                    # Update progress
                    completed_units += 1
                    progress = completed_units / total_work_units if total_work_units > 0 else 0

                    yield SSEEvent(
                        event="load_test_complete",
                        data={
                            "test_id": test.id,
                            "test_name": test.name,
                            "provider_id": provider.id,
                            "throughput_rps": load_result["throughput_rps"],
                            "avg_ms": load_result["avg_ms"],
                            "progress": progress,
                            "completed_units": completed_units,
                            "total_work_units": total_work_units,
                        },
                    )

                    # Cooldown between load tests
                    await asyncio.sleep(2)

            # Mark job as completed
            duration = time.time() - start_time
            status = JobStatus.CANCELLED if self._running_jobs.get(job_id) else JobStatus.COMPLETED

            await db.update_job_status(
                job_id=job_id,
                status=status.value,
                completed_at=datetime.utcnow(),
                duration_seconds=duration,
            )

            yield SSEEvent(
                event="job_complete",
                data={"job_id": job_id, "duration_seconds": duration, "status": status.value},
            )

        except Exception as e:
            # Mark job as failed
            duration = time.time() - start_time
            await db.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED.value,
                completed_at=datetime.utcnow(),
                duration_seconds=duration,
                error_message=str(e),
            )

            yield SSEEvent(
                event="error",
                data={"message": str(e), "job_id": job_id},
            )

        finally:
            self._running_jobs.pop(job_id, None)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        if job_id in self._running_jobs:
            self._running_jobs[job_id] = True
            return True
        return False

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get a job by ID with all related data."""
        db = await get_db()
        job_data = await db.get_job(job_id)
        if job_data is None:
            return None

        providers = await db.get_job_providers(job_id)
        test_params = await db.get_job_test_params(job_id)

        return {
            **job_data,
            "providers": providers,
            "test_params": test_params,
        }

    async def get_job_results(self, job_id: str) -> dict[str, Any]:
        """Get all results for a job."""
        db = await get_db()

        test_results = await db.get_test_results(job_id)
        load_results = await db.get_load_test_results(job_id)
        tests_executed = await db.get_job_tests_executed(job_id)
        providers = await db.get_job_providers(job_id)

        # Create provider name lookup
        provider_names = {p["id"]: p["name"] for p in providers}

        # Compute aggregated results
        aggregated = self._compute_aggregated_results(test_results)

        # Add provider names to aggregated results
        for agg in aggregated:
            agg["provider_name"] = provider_names.get(agg["provider_id"], "Unknown")

        # Add provider names and aliases to load test results
        for lr in load_results:
            lr["provider_name"] = provider_names.get(lr["provider_id"], "Unknown")
            # Add alias for frontend compatibility
            lr["requests_per_second"] = lr.get("throughput_rps", 0)

        # Add provider names to sequential results
        for sr in test_results:
            sr["provider_name"] = provider_names.get(sr["provider_id"], "Unknown")

        # Compute log count comparisons for eth_getLogs tests
        log_count_comparisons = self._compute_log_count_comparisons(test_results, provider_names)

        return {
            "sequential": test_results,
            "load_tests": load_results,
            "tests_executed": tests_executed,
            "aggregated": aggregated,
            "log_count_comparisons": log_count_comparisons,
        }

    async def _get_current_block(self, url: str, timeout: int) -> int:
        """Get current block number from provider."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
                timeout=timeout,
            )
            result = response.json()
            return int(result["result"], 16)

    def _classify_rpc_error(self, error_obj: dict[str, Any], method: str) -> ErrorCategory:
        """Classify an RPC error into a category.

        This helps distinguish between:
        - Provider issues (timeout, rate limit, unsupported method)
        - Parameter issues (invalid address, execution reverted, block range too large)
        """
        error_code = error_obj.get("code", 0)
        error_msg = error_obj.get("message", "").lower()

        # Check for execution reverted (parameter error - wrong contract/data)
        if "execution reverted" in error_msg or "revert" in error_msg:
            return ErrorCategory.EXECUTION_REVERTED

        # Check for invalid params (parameter error)
        if error_code == -32602 or "invalid argument" in error_msg or "invalid param" in error_msg:
            return ErrorCategory.INVALID_PARAMS

        # Check for method not supported (provider limitation)
        if (error_code == -32601 or "not supported" in error_msg or
            "not found" in error_msg or "method not found" in error_msg or
            "does not exist" in error_msg):
            return ErrorCategory.UNSUPPORTED

        # Check for block range limit (provider limitation, but fixable by user)
        if ("block range" in error_msg or "too many" in error_msg or
            "exceeds" in error_msg or "limit" in error_msg and "log" in error_msg):
            return ErrorCategory.BLOCK_RANGE_LIMIT

        # Check for resource exhaustion (provider issue)
        if "resource" in error_msg or "memory" in error_msg:
            return ErrorCategory.RATE_LIMIT

        # Default to generic RPC error
        return ErrorCategory.RPC_ERROR

    async def _execute_rpc_call(
        self,
        url: str,
        method: str,
        params: list[Any],
        timeout: int,
    ) -> dict[str, Any]:
        """Execute a single RPC call and return timing results with error classification."""
        async with httpx.AsyncClient() as client:
            start = time.perf_counter()
            try:
                response = await client.post(
                    url,
                    json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
                    timeout=timeout,
                )
                elapsed = (time.perf_counter() - start) * 1000  # ms

                # Rate limit (provider error)
                if response.status_code == 429:
                    return {
                        "success": False,
                        "error_type": ErrorCategory.RATE_LIMIT.value,
                        "error_is_provider_fault": True,
                        "http_status": 429,
                        "response_time_ms": elapsed,
                    }

                result = response.json()
                if "error" in result:
                    error_category = self._classify_rpc_error(result["error"], method)
                    is_provider_fault = ErrorCategory.is_provider_error(error_category)
                    return {
                        "success": False,
                        "error_type": error_category.value,
                        "error_is_provider_fault": is_provider_fault,
                        "error_message": result["error"].get("message", ""),
                        "http_status": response.status_code,
                        "response_time_ms": elapsed,
                    }

                # For eth_getLogs, extract the log count for data consistency tracking
                log_count = None
                if method == "eth_getLogs" and "result" in result:
                    logs = result["result"]
                    if isinstance(logs, list):
                        log_count = len(logs)

                return {
                    "success": True,
                    "response_time_ms": elapsed,
                    "http_status": response.status_code,
                    "response_size_bytes": len(response.content),
                    "log_count": log_count,
                }

            except httpx.TimeoutException:
                elapsed = (time.perf_counter() - start) * 1000
                return {
                    "success": False,
                    "error_type": ErrorCategory.TIMEOUT.value,
                    "error_is_provider_fault": True,
                    "response_time_ms": elapsed,
                }
            except httpx.ConnectError:
                return {
                    "success": False,
                    "error_type": ErrorCategory.CONNECTION.value,
                    "error_is_provider_fault": True,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error_type": ErrorCategory.UNKNOWN.value,
                    "error_is_provider_fault": False,
                    "error_message": str(e),
                }

    async def _execute_load_test(
        self,
        url: str,
        method: str,
        params: list[Any],
        concurrency: int,
        timeout: int,
    ) -> dict[str, Any]:
        """Execute a load test with concurrent requests."""
        start_time = time.perf_counter()

        # Create tasks for concurrent execution
        async with httpx.AsyncClient() as client:
            tasks = []
            for _ in range(concurrency):
                task = self._timed_rpc_call(client, url, method, params, timeout)
                tasks.append(task)

            results = await asyncio.gather(*tasks)

        total_time = (time.perf_counter() - start_time) * 1000  # ms

        # Analyze results with detailed error tracking
        times = []
        success_count = 0
        error_count = 0
        provider_error_count = 0
        param_error_count = 0
        error_breakdown: dict[str, int] = {}

        for r in results:
            if r["success"]:
                success_count += 1
                if r.get("response_time_ms"):
                    times.append(r["response_time_ms"])
            else:
                error_count += 1
                error_type = r.get("error_type", "unknown")
                error_breakdown[error_type] = error_breakdown.get(error_type, 0) + 1

                # Track provider vs param errors
                if r.get("error_is_provider_fault", True):
                    provider_error_count += 1
                else:
                    param_error_count += 1

        # Calculate statistics
        if times:
            times_sorted = sorted(times)
            min_ms = times_sorted[0]
            max_ms = times_sorted[-1]
            avg_ms = statistics.mean(times)
            p50_ms = times_sorted[len(times) // 2]
            p95_idx = int(len(times) * 0.95)
            p95_ms = times_sorted[min(p95_idx, len(times) - 1)]
            p99_idx = int(len(times) * 0.99)
            p99_ms = times_sorted[min(p99_idx, len(times) - 1)]
        else:
            min_ms = max_ms = avg_ms = p50_ms = p95_ms = p99_ms = 0

        throughput = success_count / (total_time / 1000) if total_time > 0 else 0

        return {
            "total_time_ms": total_time,
            "min_ms": min_ms,
            "max_ms": max_ms,
            "avg_ms": avg_ms,
            "p50_ms": p50_ms,
            "p95_ms": p95_ms,
            "p99_ms": p99_ms,
            "success_count": success_count,
            "error_count": error_count,
            "provider_error_count": provider_error_count,
            "param_error_count": param_error_count,
            "success_rate": success_count / concurrency if concurrency > 0 else 0,
            "throughput_rps": throughput,
            "errors": list(error_breakdown.keys()),
            "error_breakdown": error_breakdown,
        }

    async def _timed_rpc_call(
        self,
        client: httpx.AsyncClient,
        url: str,
        method: str,
        params: list[Any],
        timeout: int,
    ) -> dict[str, Any]:
        """Execute a timed RPC call with error classification."""
        start = time.perf_counter()
        try:
            response = await client.post(
                url,
                json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
                timeout=timeout,
            )
            elapsed = (time.perf_counter() - start) * 1000

            if response.status_code == 429:
                return {
                    "success": False,
                    "error_type": ErrorCategory.RATE_LIMIT.value,
                    "error_is_provider_fault": True,
                    "response_time_ms": elapsed,
                }

            result = response.json()
            if "error" in result:
                error_category = self._classify_rpc_error(result["error"], method)
                return {
                    "success": False,
                    "error_type": error_category.value,
                    "error_is_provider_fault": ErrorCategory.is_provider_error(error_category),
                    "response_time_ms": elapsed,
                }

            return {"success": True, "response_time_ms": elapsed}

        except httpx.TimeoutException:
            return {
                "success": False,
                "error_type": ErrorCategory.TIMEOUT.value,
                "error_is_provider_fault": True,
            }
        except Exception:
            return {
                "success": False,
                "error_type": ErrorCategory.UNKNOWN.value,
                "error_is_provider_fault": False,
            }

    def _compute_aggregated_results(
        self, test_results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Compute aggregated results from individual test results with error analysis."""
        # Group by provider and test
        groups: dict[tuple[str, int], list[dict]] = {}
        for r in test_results:
            key = (r["provider_id"], r["test_id"])
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        aggregated = []
        for (provider_id, test_id), results in groups.items():
            if not results:
                continue

            first = results[0]
            successful = [r for r in results if r["success"]]
            failed = [r for r in results if not r["success"]]
            times = [r["response_time_ms"] for r in successful if r.get("response_time_ms")]

            # Error analysis
            error_breakdown: dict[str, int] = {}
            error_messages: list[str] = []
            provider_errors = 0
            param_errors = 0
            for r in failed:
                error_type = r.get("error_type", "unknown")
                error_breakdown[error_type] = error_breakdown.get(error_type, 0) + 1

                # Collect unique error messages
                error_msg = r.get("error_message")
                if error_msg and error_msg not in error_messages:
                    error_messages.append(error_msg)

                # Classify fault
                if error_type in ("timeout", "rate_limit", "connection", "unsupported"):
                    provider_errors += 1
                elif error_type in ("invalid_params", "execution_reverted", "block_range_limit"):
                    param_errors += 1
                else:
                    # For unknown/rpc_error, count as provider unless we know otherwise
                    provider_errors += 1

            # Get cold and warm times
            cold_result = next((r for r in results if r["iteration_type"] == "cold"), None)
            warm_results = [r for r in results if r["iteration_type"] in ("warm", "sustained") and r["success"]]

            cold_ms = cold_result["response_time_ms"] if cold_result and cold_result.get("response_time_ms") else 0
            warm_ms = statistics.mean([r["response_time_ms"] for r in warm_results if r.get("response_time_ms")]) if warm_results else cold_ms

            cache_speedup = cold_ms / warm_ms if warm_ms > 0 else 1.0

            agg = {
                "provider_id": provider_id,
                "test_id": test_id,
                "test_name": first["test_name"],
                "category": first["category"],
                "label": first["label"],
                "count": len(results),
                "success_count": len(successful),
                "error_count": len(failed),
                "success_rate": len(successful) / len(results) if results else 0,
                "cold_ms": cold_ms,
                "warm_ms": warm_ms,
                "cache_speedup": cache_speedup,
                # Error analysis
                "provider_errors": provider_errors,
                "param_errors": param_errors,
                "error_breakdown": error_breakdown,
                "error_messages": error_messages[:5],  # Limit to first 5 unique messages
            }

            # Extended metrics (when enough samples)
            if len(times) >= 5:
                agg["mean_ms"] = statistics.mean(times)
                agg["median_ms"] = statistics.median(times)
                agg["min_ms"] = min(times)
                agg["max_ms"] = max(times)
                agg["std_dev_ms"] = statistics.stdev(times) if len(times) > 1 else 0

            # Statistical metrics
            if len(times) >= 25:
                sorted_times = sorted(times)
                agg["p90_ms"] = sorted_times[int(len(times) * 0.90)]
                agg["p95_ms"] = sorted_times[int(len(times) * 0.95)]

            aggregated.append(agg)

        return aggregated

    def _compute_log_count_comparisons(
        self,
        test_results: list[dict[str, Any]],
        provider_names: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Compute log count comparisons across providers for getLogs tests.

        This helps identify data consistency issues where providers return
        different numbers of logs for the same query.
        """
        from collections import Counter

        # Filter to only getLogs tests with log_count data
        getLogs_results = [
            r for r in test_results
            if r.get("log_count") is not None or (
                "getLogs" in r.get("test_name", "") and r.get("success")
            )
        ]

        if not getLogs_results:
            return []

        # Group by test_id and iteration (round)
        groups: dict[tuple[int, int], list[dict]] = {}
        for r in getLogs_results:
            key = (r["test_id"], r["iteration"])
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        comparisons = []
        for (test_id, iteration), results in groups.items():
            if len(results) < 2:
                # Need at least 2 providers to compare
                continue

            first = results[0]

            # Build provider counts dict (provider_name -> log_count)
            provider_counts: dict[str, int | None] = {}
            for r in results:
                pname = provider_names.get(r["provider_id"], r["provider_id"])
                provider_counts[pname] = r.get("log_count")

            # Find consensus (most common non-None count)
            valid_counts = [c for c in provider_counts.values() if c is not None]
            if valid_counts:
                count_frequency = Counter(valid_counts)
                consensus_count = count_frequency.most_common(1)[0][0]
            else:
                consensus_count = None

            # Check for mismatches
            has_mismatch = False
            if consensus_count is not None:
                for count in valid_counts:
                    if count != consensus_count:
                        has_mismatch = True
                        break

            comparisons.append({
                "test_id": test_id,
                "test_name": first["test_name"],
                "round_number": iteration,
                "provider_counts": provider_counts,
                "consensus_count": consensus_count,
                "has_mismatch": has_mismatch,
            })

        # Sort by test_id, then round_number
        comparisons.sort(key=lambda x: (x["test_id"], x["round_number"]))

        return comparisons


# Global service instance
benchmark_service = BenchmarkService()
