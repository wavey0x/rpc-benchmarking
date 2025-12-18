"""Test case definitions for RPC benchmarking.

Simplified test battery focusing on tests that don't require complex parameters.
Removed: balanceOf (needs ERC20+holder), getTransaction* (needs tx hash),
getStorageAt (needs storage layout), trace/debug (often unsupported + needs tx).
"""

from typing import Any

from ..models import TestCase, TestCategory, TestLabel, TestParams


def get_test_definitions() -> list[dict[str, Any]]:
    """Get the base test definitions (without parameters filled in)."""
    return [
        # Simple Tests (1-5) - No or minimal params required
        {
            "id": 1,
            "name": "eth_blockNumber",
            "category": "simple",
            "label": "latest",
            "rpc_method": "eth_blockNumber",
            "param_template": [],
        },
        {
            "id": 2,
            "name": "eth_chainId",
            "category": "simple",
            "label": "latest",
            "rpc_method": "eth_chainId",
            "param_template": [],
        },
        {
            "id": 3,
            "name": "eth_gasPrice",
            "category": "simple",
            "label": "latest",
            "rpc_method": "eth_gasPrice",
            "param_template": [],
        },
        {
            "id": 4,
            "name": "eth_getBalance (latest)",
            "category": "simple",
            "label": "latest",
            "rpc_method": "eth_getBalance",
            "param_template": ["{known_address}", "latest"],
        },
        {
            "id": 5,
            "name": "eth_getBalance (archival)",
            "category": "simple",
            "label": "archival",
            "rpc_method": "eth_getBalance",
            "param_template": ["{known_address}", "{archival_block_hex}"],
        },
        # Medium Tests (6-7) - Just block number needed
        {
            "id": 6,
            "name": "eth_getBlockByNumber (latest)",
            "category": "medium",
            "label": "latest",
            "rpc_method": "eth_getBlockByNumber",
            "param_template": ["{recent_block_hex}", True],
        },
        {
            "id": 7,
            "name": "eth_getBlockByNumber (archival)",
            "category": "medium",
            "label": "archival",
            "rpc_method": "eth_getBlockByNumber",
            "param_template": ["{archival_block_hex}", True],
        },
        # Complex Tests (8-11) - getLogs with token contract (user requested to keep)
        # Names use {range_small} and {range_large} placeholders for actual block counts
        {
            "id": 8,
            "name": "eth_getLogs small range (latest)",
            "category": "complex",
            "label": "latest",
            "rpc_method": "eth_getLogs",
            "param_template": [
                {
                    "address": "{logs_token_contract}",
                    "fromBlock": "{logs_recent_start_hex}",
                    "toBlock": "{logs_recent_end_hex}",
                    "topics": ["{transfer_topic}"],
                }
            ],
            "range_size": "small",
        },
        {
            "id": 9,
            "name": "eth_getLogs small range (archival)",
            "category": "complex",
            "label": "archival",
            "rpc_method": "eth_getLogs",
            "param_template": [
                {
                    "address": "{logs_token_contract}",
                    "fromBlock": "{logs_archival_start_hex}",
                    "toBlock": "{logs_archival_end_small_hex}",
                    "topics": ["{transfer_topic}"],
                }
            ],
            "range_size": "small",
        },
        {
            "id": 10,
            "name": "eth_getLogs large range (latest)",
            "category": "complex",
            "label": "latest",
            "rpc_method": "eth_getLogs",
            "param_template": [
                {
                    "address": "{logs_token_contract}",
                    "fromBlock": "{logs_recent_start_large_hex}",
                    "toBlock": "{logs_recent_end_hex}",
                    "topics": ["{transfer_topic}"],
                }
            ],
            "range_size": "large",
        },
        {
            "id": 11,
            "name": "eth_getLogs large range (archival)",
            "category": "complex",
            "label": "archival",
            "rpc_method": "eth_getLogs",
            "param_template": [
                {
                    "address": "{logs_token_contract}",
                    "fromBlock": "{logs_archival_start_hex}",
                    "toBlock": "{logs_archival_end_large_hex}",
                    "topics": ["{transfer_topic}"],
                }
            ],
            "range_size": "large",
        },
        # Load Tests (12-13)
        {
            "id": 12,
            "name": "eth_blockNumber burst",
            "category": "load",
            "label": "latest",
            "rpc_method": "eth_blockNumber",
            "param_template": [],
            "load_tier": "simple",
        },
        {
            "id": 13,
            "name": "eth_getLogs burst",
            "category": "load",
            "label": "latest",
            "rpc_method": "eth_getLogs",
            "param_template": [
                {
                    "address": "{logs_token_contract}",
                    "fromBlock": "{logs_recent_start_hex}",
                    "toBlock": "{logs_recent_end_hex}",
                    "topics": ["{transfer_topic}"],
                }
            ],
            "load_tier": "complex",
        },
    ]


# ERC20 Transfer event topic
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _to_hex(value: int) -> str:
    """Convert integer to hex string."""
    return hex(value)


def build_test_cases(
    params: TestParams,
    current_block: int,
    enabled_ids: list[int] | None = None,
    load_concurrency: dict[str, int] | None = None,
) -> list[TestCase]:
    """Build test cases with filled-in parameters."""
    definitions = get_test_definitions()
    test_cases = []

    # Calculate derived values
    recent_block = current_block - params.recent_block_offset
    archival_block = params.archival_block

    # Block ranges for getLogs
    logs_recent_end = current_block - 10  # Slight offset from head
    logs_recent_start_small = logs_recent_end - params.logs_range_small
    logs_recent_start_large = logs_recent_end - params.logs_range_large

    logs_archival_start = params.archival_logs_start_block
    logs_archival_end_small = logs_archival_start + params.logs_range_small
    logs_archival_end_large = logs_archival_start + params.logs_range_large

    # Build substitution map (simplified - removed unused params)
    subs = {
        "known_address": params.known_address,
        "archival_block_hex": _to_hex(archival_block),
        "recent_block_hex": _to_hex(recent_block),
        "logs_token_contract": params.logs_token_contract,
        "transfer_topic": TRANSFER_TOPIC,
        "logs_recent_start_hex": _to_hex(logs_recent_start_small),
        "logs_recent_start_large_hex": _to_hex(logs_recent_start_large),
        "logs_recent_end_hex": _to_hex(logs_recent_end),
        "logs_archival_start_hex": _to_hex(logs_archival_start),
        "logs_archival_end_small_hex": _to_hex(logs_archival_end_small),
        "logs_archival_end_large_hex": _to_hex(logs_archival_end_large),
    }

    load_conc = load_concurrency or {"simple": 50, "medium": 50, "complex": 25}

    # Block range info for debugging (will be added to test metadata)
    block_ranges = {
        8: (logs_recent_start_small, logs_recent_end),  # small latest
        9: (logs_archival_start, logs_archival_end_small),  # small archival
        10: (logs_recent_start_large, logs_recent_end),  # large latest
        11: (logs_archival_start, logs_archival_end_large),  # large archival
    }

    for defn in definitions:
        test_id = defn["id"]

        # Check if enabled
        if enabled_ids is not None and test_id not in enabled_ids:
            continue

        # Substitute parameters
        rpc_params = _substitute_params(defn["param_template"], subs)

        # Build test name - include actual block range for getLogs tests
        test_name = defn["name"]
        range_size = defn.get("range_size")

        # For getLogs tests, show actual block range in name for debugging
        if test_id in block_ranges:
            from_block, to_block = block_ranges[test_id]
            block_count = to_block - from_block
            # Format: "eth_getLogs [12000000→12050000] (archival)"
            if "small range" in test_name:
                test_name = test_name.replace("small range", f"[{from_block:,}→{to_block:,}]")
            elif "large range" in test_name:
                test_name = test_name.replace("large range", f"[{from_block:,}→{to_block:,}]")

        # Determine concurrency for load tests
        concurrency = None
        if defn["category"] == "load":
            tier = defn.get("load_tier", "simple")
            concurrency = load_conc.get(tier, 50)

        test_case = TestCase(
            id=test_id,
            name=test_name,
            category=TestCategory(defn["category"]),
            label=TestLabel(defn["label"]),
            enabled=True,
            rpc_method=defn["rpc_method"],
            rpc_params=rpc_params,
            concurrency=concurrency,
        )
        test_cases.append(test_case)

    return test_cases


def _substitute_params(template: Any, subs: dict[str, str]) -> Any:
    """Recursively substitute parameters in a template."""
    if isinstance(template, str):
        # Check if it's a substitution placeholder
        if template.startswith("{") and template.endswith("}"):
            key = template[1:-1]
            return subs.get(key, template)
        return template
    elif isinstance(template, dict):
        return {k: _substitute_params(v, subs) for k, v in template.items()}
    elif isinstance(template, list):
        return [_substitute_params(item, subs) for item in template]
    else:
        return template
