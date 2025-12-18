"""API routes for the RPC Benchmarker."""

import csv
import hashlib
import io
import json
import random
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, File
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from ..core.config import settings
from ..core.database import get_db
from ..models import (
    BenchmarkConfig,
    ChainConfig,
    JobCreate,
    ProviderValidationRequest,
    ProviderValidationResponse,
    TestParams,
)
from ..services import ChainService, BenchmarkService, get_test_definitions, build_test_cases

router = APIRouter()
chain_service = ChainService()
benchmark_service = BenchmarkService()


# ============================================================================
# Chain Configuration Endpoints
# ============================================================================

@router.get("/chains")
async def list_chains() -> list[dict[str, Any]]:
    """List all chain configurations."""
    chains = chain_service.list_chains()
    return [c.model_dump(mode="json") for c in chains]


@router.get("/chains/{chain_id}")
async def get_chain(chain_id: int) -> dict[str, Any]:
    """Get a chain configuration by ID."""
    chain = chain_service.get_chain(chain_id)
    if chain is None:
        raise HTTPException(status_code=404, detail=f"Chain {chain_id} not found")
    return chain.model_dump(mode="json")


@router.post("/chains")
async def create_chain(chain_data: dict[str, Any]) -> dict[str, Any]:
    """Create a custom chain configuration."""
    try:
        chain = chain_service.create_custom_chain(chain_data)
        return chain.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/chains/{chain_id}")
async def update_chain(chain_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    """Update a chain configuration."""
    chain = chain_service.update_chain(chain_id, updates)
    if chain is None:
        raise HTTPException(status_code=404, detail=f"Chain {chain_id} not found")
    return chain.model_dump(mode="json")


@router.delete("/chains/{chain_id}")
async def delete_chain(chain_id: int) -> dict[str, str]:
    """Delete a custom chain configuration."""
    if not chain_service.delete_chain(chain_id):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete preset chains or chain not found"
        )
    return {"status": "deleted"}


# ============================================================================
# Provider Validation
# ============================================================================

@router.post("/providers/validate")
async def validate_providers(request: ProviderValidationRequest) -> ProviderValidationResponse:
    """Validate provider URLs return the expected chain ID."""
    results = []

    async with httpx.AsyncClient() as client:
        for url in request.urls:
            try:
                response = await client.post(
                    url,
                    json={"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1},
                    timeout=10,
                )
                data = response.json()
                chain_id = int(data.get("result", "0x0"), 16)
                valid = chain_id == request.expected_chain_id
                results.append({
                    "url": _mask_url(url),
                    "valid": valid,
                    "chain_id": chain_id,
                    "expected_chain_id": request.expected_chain_id,
                })
            except Exception as e:
                results.append({
                    "url": _mask_url(url),
                    "valid": False,
                    "error": str(e),
                })

    all_valid = all(r.get("valid", False) for r in results)
    return ProviderValidationResponse(valid=all_valid, results=results)


# ============================================================================
# Test Parameters
# ============================================================================

@router.get("/test-cases")
async def list_test_cases() -> list[dict[str, Any]]:
    """List all available test case definitions."""
    return get_test_definitions()


@router.post("/params/randomize")
async def randomize_params(chain_id: int = Query(...)) -> dict[str, Any]:
    """Generate random valid test parameters for a chain."""
    chain = chain_service.get_chain(chain_id)
    if chain is None:
        raise HTTPException(status_code=404, detail=f"Chain {chain_id} not found")

    # Pick random values from chain config
    test_address = random.choice(chain.test_addresses) if chain.test_addresses else None
    token = random.choice(chain.token_contracts) if chain.token_contracts else None

    # Random archival block in range
    archival_block = random.randint(
        chain.archival_block_range[0],
        chain.archival_block_range[1]
    )

    # Pick random transaction
    tx_hash = random.choice(chain.transaction_pool) if chain.transaction_pool else None

    params = {
        "known_address": test_address.address if test_address else "0x" + "0" * 40,
        "token_contract": token.address if token else "0x" + "0" * 40,
        "token_holder": token.holder_address if token else "0x" + "0" * 40,
        "storage_contract": token.address if token else "0x" + "0" * 40,
        "storage_slot": "0x0",
        "archival_block": archival_block,
        "recent_block_offset": 100,
        "recent_tx_hash": tx_hash,
        "archival_tx_hash": tx_hash,
        "logs_token_contract": token.address if token else "0x" + "0" * 40,
        "logs_range_small": 1000,
        "logs_range_large": 10000,
        "archival_logs_start_block": archival_block,
    }

    return params


@router.post("/params/validate")
async def validate_params(
    chain_id: int = Query(...),
    provider_url: str = Query(...),
    params: dict[str, Any] = None,
) -> dict[str, Any]:
    """Validate test parameters are usable."""
    if params is None:
        params = {}

    validation_results = []
    # ERC20 Transfer event topic
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

    async with httpx.AsyncClient() as client:
        # Get current block number first
        current_block = 0
        try:
            response = await client.post(
                provider_url,
                json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
                timeout=10,
            )
            data = response.json()
            current_block = int(data.get("result", "0x0"), 16)
        except Exception:
            pass

        # Validate known address has balance
        known_address = params.get("known_address", "")
        if known_address:
            try:
                response = await client.post(
                    provider_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "eth_getBalance",
                        "params": [known_address, "latest"],
                        "id": 1,
                    },
                    timeout=10,
                )
                data = response.json()
                if "error" in data:
                    validation_results.append({
                        "field": "known_address",
                        "valid": False,
                        "message": f"Invalid address: {data['error'].get('message', 'unknown error')}",
                    })
                else:
                    has_balance = int(data.get("result", "0x0"), 16) > 0
                    validation_results.append({
                        "field": "known_address",
                        "valid": has_balance,
                        "message": "Address has balance" if has_balance else "Address has no balance (may cause test failures)",
                    })
            except Exception as e:
                validation_results.append({
                    "field": "known_address",
                    "valid": False,
                    "message": str(e),
                })
        else:
            validation_results.append({
                "field": "known_address",
                "valid": False,
                "message": "Address is required",
            })

        # Validate logs_token_contract is a valid contract with Transfer events
        logs_contract = params.get("logs_token_contract", "")
        if logs_contract:
            try:
                # First check if it's a contract (has code)
                response = await client.post(
                    provider_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "eth_getCode",
                        "params": [logs_contract, "latest"],
                        "id": 1,
                    },
                    timeout=10,
                )
                data = response.json()
                if "error" in data:
                    validation_results.append({
                        "field": "logs_token_contract",
                        "valid": False,
                        "message": f"Invalid address: {data['error'].get('message', 'unknown error')}",
                    })
                else:
                    code = data.get("result", "0x")
                    if code == "0x" or code == "0x0":
                        validation_results.append({
                            "field": "logs_token_contract",
                            "valid": False,
                            "message": "Address is not a contract (no code)",
                        })
                    else:
                        # Check if contract has recent Transfer events
                        if current_block > 0:
                            from_block = hex(max(0, current_block - 1000))
                            to_block = hex(current_block)
                            response = await client.post(
                                provider_url,
                                json={
                                    "jsonrpc": "2.0",
                                    "method": "eth_getLogs",
                                    "params": [{
                                        "address": logs_contract,
                                        "fromBlock": from_block,
                                        "toBlock": to_block,
                                        "topics": [transfer_topic],
                                    }],
                                    "id": 1,
                                },
                                timeout=15,
                            )
                            data = response.json()
                            if "error" in data:
                                validation_results.append({
                                    "field": "logs_token_contract",
                                    "valid": False,
                                    "message": f"getLogs failed: {data['error'].get('message', 'unknown error')}",
                                })
                            else:
                                logs = data.get("result", [])
                                if len(logs) > 0:
                                    validation_results.append({
                                        "field": "logs_token_contract",
                                        "valid": True,
                                        "message": f"Contract has {len(logs)} Transfer events in last 1000 blocks",
                                    })
                                else:
                                    validation_results.append({
                                        "field": "logs_token_contract",
                                        "valid": False,
                                        "message": "No Transfer events found in last 1000 blocks (may not be an ERC20 or low activity)",
                                    })
                        else:
                            validation_results.append({
                                "field": "logs_token_contract",
                                "valid": True,
                                "message": "Contract exists (could not verify Transfer events)",
                            })
            except Exception as e:
                validation_results.append({
                    "field": "logs_token_contract",
                    "valid": False,
                    "message": str(e),
                })
        else:
            validation_results.append({
                "field": "logs_token_contract",
                "valid": False,
                "message": "Token contract is required for getLogs tests",
            })

        # Validate archival block is reasonable
        archival_block = params.get("archival_block", 0)
        if archival_block and current_block > 0:
            if archival_block > current_block:
                validation_results.append({
                    "field": "archival_block",
                    "valid": False,
                    "message": f"Archival block {archival_block} is in the future (current: {current_block})",
                })
            elif archival_block < 1:
                validation_results.append({
                    "field": "archival_block",
                    "valid": False,
                    "message": "Archival block must be greater than 0",
                })
            else:
                validation_results.append({
                    "field": "archival_block",
                    "valid": True,
                    "message": f"Archival block {archival_block} is valid",
                })

            # Check that token contract existed at archival block (if both are provided)
            if logs_contract and archival_block > 0:
                try:
                    response = await client.post(
                        provider_url,
                        json={
                            "jsonrpc": "2.0",
                            "method": "eth_getCode",
                            "params": [logs_contract, hex(archival_block)],
                            "id": 1,
                        },
                        timeout=10,
                    )
                    data = response.json()
                    if "error" in data:
                        validation_results.append({
                            "field": "archival_block",
                            "valid": False,
                            "message": f"Could not verify contract at archival block: {data['error'].get('message', '')}",
                        })
                    else:
                        code = data.get("result", "0x")
                        if code == "0x" or code == "0x0":
                            validation_results.append({
                                "field": "archival_block",
                                "valid": False,
                                "message": f"Token contract was not deployed at block {archival_block}. Choose a later block.",
                            })
                        else:
                            validation_results.append({
                                "field": "archival_block",
                                "valid": True,
                                "message": f"Token contract existed at archival block {archival_block}",
                            })
                except Exception as e:
                    validation_results.append({
                        "field": "archival_block",
                        "valid": False,
                        "message": f"Failed to check contract at archival block: {str(e)}",
                    })

    all_valid = all(r["valid"] for r in validation_results)
    return {"valid": all_valid, "results": validation_results}


# ============================================================================
# Benchmark Jobs
# ============================================================================

@router.post("/jobs")
async def create_job(job_data: JobCreate) -> dict[str, Any]:
    """Create a new benchmark job."""
    try:
        job = await benchmark_service.create_job(
            chain_id=job_data.chain_id,
            providers=[p.model_dump() for p in job_data.providers],
            config=job_data.config,
        )
        return job.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs")
async def list_jobs(
    chain_id: int | None = Query(None),
    limit: int = Query(100, le=1000),
) -> list[dict[str, Any]]:
    """List all jobs, optionally filtered by chain."""
    db = await get_db()
    jobs = await db.list_jobs(chain_id=chain_id, limit=limit)

    # Parse config JSON
    for job in jobs:
        if isinstance(job.get("config_json"), str):
            job["config"] = json.loads(job["config_json"])
        else:
            job["config"] = job.get("config_json", {})

    return jobs


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    """Get a job by ID."""
    job = await benchmark_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Parse config JSON
    if isinstance(job.get("config_json"), str):
        job["config"] = json.loads(job["config_json"])

    return job


@router.get("/jobs/{job_id}/results")
async def get_job_results(job_id: str) -> dict[str, Any]:
    """Get results for a job."""
    db = await get_db()
    job = await db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    results = await benchmark_service.get_job_results(job_id)
    return results


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> dict[str, str]:
    """Delete a job and all related data."""
    db = await get_db()
    if not await db.delete_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"status": "deleted"}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, str]:
    """Cancel a running job."""
    if benchmark_service.cancel_job(job_id):
        return {"status": "cancelled"}
    raise HTTPException(status_code=400, detail="Job not running or not found")


# ============================================================================
# Progress (Server-Sent Events)
# ============================================================================

@router.get("/jobs/{job_id}/progress")
async def job_progress(job_id: str):
    """Stream job progress via Server-Sent Events."""
    async def event_generator():
        async for event in benchmark_service.run_job(job_id):
            yield {
                "event": event.event,
                "data": json.dumps(event.data),
            }

    return EventSourceResponse(event_generator())


# ============================================================================
# Export
# ============================================================================

@router.get("/export/{job_id}/json")
async def export_json(job_id: str) -> Response:
    """Export job results as JSON."""
    db = await get_db()
    job = await db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    providers = await db.get_job_providers(job_id)
    test_params = await db.get_job_test_params(job_id)
    tests_executed = await db.get_job_tests_executed(job_id)
    results = await benchmark_service.get_job_results(job_id)

    # Parse config
    config = job.get("config_json", {})
    if isinstance(config, str):
        config = json.loads(config)

    # Build export
    export = {
        "metadata": {
            "tool_version": settings.app_version,
            "exported_at": datetime.utcnow().isoformat() + "Z",
        },
        "chain": {
            "id": job["chain_id"],
            "name": job["chain_name"],
        },
        "job": {
            "id": job["id"],
            "created_at": job["created_at"],
            "completed_at": job.get("completed_at"),
            "duration_seconds": job.get("duration_seconds"),
            "status": job["status"],
            "config": config,
        },
        "providers": [
            {
                "id": p["id"],
                "name": p["name"],
                "region": p.get("region"),
                "url_hash": hashlib.sha256(p["url"].encode()).hexdigest()[:16],
            }
            for p in providers
        ],
        "test_params": test_params,
        "tests_executed": tests_executed,
        "results": results,
    }

    # Generate filename
    chain_name = job["chain_name"].lower().replace(" ", "_")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    filename = f"benchmark_{chain_name}_{job['chain_id']}_{timestamp}.json"

    return Response(
        content=json.dumps(export, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/{job_id}/csv")
async def export_csv(job_id: str) -> Response:
    """Export job results summary as CSV."""
    db = await get_db()
    job = await db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    providers = await db.get_job_providers(job_id)
    results = await benchmark_service.get_job_results(job_id)

    # Create provider ID to name map
    provider_names = {p["id"]: p["name"] for p in providers}

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Provider", "Test", "Category", "Label",
        "Cold (ms)", "Warm (ms)", "Cache Speedup",
        "Success Rate", "Count"
    ])

    # Write aggregated results
    for agg in results.get("aggregated", []):
        writer.writerow([
            provider_names.get(agg["provider_id"], agg["provider_id"]),
            agg["test_name"],
            agg["category"],
            agg["label"],
            f"{agg['cold_ms']:.1f}" if agg.get("cold_ms") else "",
            f"{agg['warm_ms']:.1f}" if agg.get("warm_ms") else "",
            f"{agg['cache_speedup']:.2f}" if agg.get("cache_speedup") else "",
            f"{agg['success_rate']:.1%}" if agg.get("success_rate") is not None else "",
            agg.get("count", ""),
        ])

    # Generate filename
    chain_name = job["chain_name"].lower().replace(" ", "_")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    filename = f"benchmark_{chain_name}_{job['chain_id']}_{timestamp}.csv"

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================================
# Import
# ============================================================================

@router.post("/import")
async def import_results(file: UploadFile = File(...)) -> dict[str, Any]:
    """Import benchmark results from exported JSON file."""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be a JSON file")

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    # Validate required fields
    required = ["chain", "job", "providers", "results"]
    missing = [f for f in required if f not in data]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {missing}")

    db = await get_db()

    # Extract data
    chain = data["chain"]
    job_data = data["job"]
    providers = data["providers"]
    results = data["results"]
    test_params = data.get("test_params")
    tests_executed = data.get("tests_executed", [])

    # Generate new job ID for imported data (with 'imp-' prefix)
    import uuid
    job_id = f"imp-{str(uuid.uuid4())[:6]}"

    # Get config from job data
    config = job_data.get("config", {})

    # Create job record
    await db.create_job(
        job_id=job_id,
        chain_id=chain["id"],
        chain_name=chain["name"],
        status="imported",
        config=config,
    )

    # Update job with completion info
    await db.update_job_status(
        job_id=job_id,
        status="imported",
        completed_at=datetime.fromisoformat(job_data["completed_at"].replace("Z", "")) if job_data.get("completed_at") else None,
        duration_seconds=job_data.get("duration_seconds"),
    )

    # Add providers (generate fake URLs since we only have hashes)
    for p in providers:
        await db.add_job_provider(
            job_id=job_id,
            provider_id=p["id"],
            name=p["name"],
            url=f"imported://{p.get('url_hash', 'unknown')}",
            region=p.get("region"),
        )

    # Save test params if present
    if test_params:
        await db.save_job_test_params(job_id, test_params)

    # Save tests executed
    for test in tests_executed:
        await db.save_job_test_executed(job_id, test.get("id", 0), test)

    # Import sequential test results
    sequential = results.get("sequential", [])
    for r in sequential:
        test_result = {
            "job_id": job_id,
            "provider_id": r.get("provider_id"),
            "test_id": r.get("test_id"),
            "test_name": r.get("test_name"),
            "category": r.get("category"),
            "label": r.get("label"),
            "iteration": r.get("iteration", 1),
            "iteration_type": r.get("iteration_type", "warm"),
            "response_time_ms": r.get("response_time_ms"),
            "success": r.get("success", False),
            "error_type": r.get("error_type"),
            "error_message": r.get("error_message"),
            "http_status": r.get("http_status"),
            "response_size_bytes": r.get("response_size_bytes"),
            "timestamp": r.get("timestamp", datetime.utcnow().isoformat()),
        }
        await db.save_test_result(test_result)

    # Import load test results
    load_tests = results.get("load_tests", [])
    for lt in load_tests:
        load_result = {
            "job_id": job_id,
            "provider_id": lt.get("provider_id"),
            "test_id": lt.get("test_id"),
            "test_name": lt.get("test_name"),
            "method": lt.get("method", "unknown"),
            "concurrency": lt.get("concurrency", 0),
            "total_time_ms": lt.get("total_time_ms", 0),
            "min_ms": lt.get("min_ms", 0),
            "max_ms": lt.get("max_ms", 0),
            "avg_ms": lt.get("avg_ms", 0),
            "p50_ms": lt.get("p50_ms", 0),
            "p95_ms": lt.get("p95_ms", 0),
            "p99_ms": lt.get("p99_ms", 0),
            "success_count": lt.get("success_count", 0),
            "error_count": lt.get("error_count", 0),
            "success_rate": lt.get("success_rate", 0),
            "throughput_rps": lt.get("throughput_rps", 0),
            "errors": lt.get("errors", []),
            "timestamp": lt.get("timestamp", datetime.utcnow().isoformat()),
        }
        await db.save_load_test_result(load_result)

    return {
        "success": True,
        "job_id": job_id,
        "message": f"Imported {len(sequential)} sequential results and {len(load_tests)} load test results",
        "chain": chain["name"],
        "providers": [p["name"] for p in providers],
    }


# ============================================================================
# Helpers
# ============================================================================

def _mask_url(url: str) -> str:
    """Mask API keys in URL for display."""
    # Simple masking - hide query params that might contain keys
    if "?" in url:
        base, params = url.split("?", 1)
        return f"{base}?***"
    return url
