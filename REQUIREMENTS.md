# Ethereum RPC Benchmarking Utility

## Overview

A lightweight utility to benchmark and compare performance across multiple Ethereum RPC providers. Users supply RPC endpoints, run benchmarks across standardized test cases, and visualize comparative results.

## Goals

- **Simple**: Easy to configure, run, and interpret
- **Fair**: All providers tested with identical queries against the same on-chain data
- **Comprehensive**: Test different complexity levels of RPC calls
- **Local-first**: Runs entirely locally, with optional JSON export for sharing

---

## Functional Requirements

### 1. Chain & Provider Configuration

#### 1.1 Chain Selection

The tool supports multiple EVM chains. Users select or configure a chain before running benchmarks.

**Pre-loaded chain presets:**

| Chain | ID | Archive Cutoff | Notes |
|-------|-----|----------------|-------|
| Ethereum | 1 | ~12,000,000 | Full support including debug/trace |
| Arbitrum One | 42161 | ~150,000,000 | Different block cadence |
| Optimism | 10 | ~100,000,000 | Bedrock upgrade considerations |
| Base | 8453 | ~5,000,000 | Newer chain, less historical data |
| Polygon | 137 | ~40,000,000 | High throughput, different token ecosystem |
| BSC | 56 | ~25,000,000 | BEP-20 tokens |
| Avalanche C-Chain | 43114 | ~20,000,000 | AVAX ecosystem |

Users can also create **custom chain configurations** for any EVM chain.

#### 1.2 Provider Configuration

- Accept multiple RPC URLs as input (minimum 2, no hard maximum)
- Each provider entry includes:
  - `name`: Display name (e.g., "Alchemy", "Infura", "QuickNode")
  - `url`: RPC endpoint URL
  - `region`: Optional tag (e.g., "us-east", "eu-west") for grouping results
- Configuration via:
  - Web UI form input
  - JSON config file upload
  - Environment variables for sensitive URLs
- **Important**: All providers in a benchmark run must serve the same chain

### 2. Benchmark Test Suite

#### 2.1 Call Categories

Tests are organized into four categories:

| Category | Description | Example Calls |
|----------|-------------|---------------|
| **Simple** | Minimal compute, no state traversal | `eth_blockNumber`, `eth_chainId`, `eth_gasPrice`, `eth_getBalance` |
| **Medium** | Single state lookup or execution | `eth_call` (balanceOf), `eth_getTransactionByHash`, `eth_getBlockByNumber`, `eth_getTransactionReceipt` |
| **Complex** | Heavy compute, state traversal, or wide ranges | `eth_getLogs` (1000+ blocks), `debug_traceTransaction`, `trace_replayTransaction` |
| **Load** | Concurrent request burst to test throughput | Configurable method at configurable concurrency |

#### 2.1.1 Test Labels

Each test carries metadata labels for filtering and visualization:

| Label | Description |
|-------|-------------|
| `latest` | Query executed against chain head / latest state |
| `archival` | Query executed against historical state (requires archive node) |

**Why this matters:** Archive queries require providers to traverse historical state tries, which is significantly more expensive than querying current state. Many providers use different infrastructure (or pricing) for archive vs. non-archive requests. Comparing `latest` vs `archival` performance for the same call type reveals:
- Whether the provider has optimized archive access
- Potential latency differences between hot (recent) and cold (old) data
- If the provider is using a full node vs. archive node backend

#### 2.2 Standard Test Cases

Each test case uses **deterministic parameters** to ensure fair comparison.

Tests are listed with their label: `[latest]` or `[archival]`

---

**Simple Tests:**

| # | Test | Label | Description |
|---|------|-------|-------------|
| 1 | `eth_blockNumber` | `latest` | Get current block number |
| 2 | `eth_chainId` | `latest` | Get chain ID |
| 3 | `eth_gasPrice` | `latest` | Get current gas price |
| 4 | `eth_getBalance` | `latest` | Balance of known address at latest block |
| 5 | `eth_getBalance` | `archival` | Balance of known address at archival block (~3 years old) |

---

**Medium Tests:**

| # | Test | Label | Description |
|---|------|-------|-------------|
| 6 | `eth_call` (balanceOf) | `latest` | USDC balance check at latest block |
| 7 | `eth_call` (balanceOf) | `archival` | USDC balance check at archival block |
| 8 | `eth_getBlockByNumber` | `latest` | Fetch recent block (head - 100) with transactions |
| 9 | `eth_getBlockByNumber` | `archival` | Fetch archival block (~3 years old) with transactions |
| 10 | `eth_getTransactionByHash` | `latest` | Fetch a recent transaction |
| 11 | `eth_getTransactionReceipt` | `latest` | Receipt for recent transaction |
| 12 | `eth_getStorageAt` | `latest` | Read storage slot at latest block |
| 13 | `eth_getStorageAt` | `archival` | Read storage slot at archival block |

---

**Complex Tests:**

| # | Test | Label | Description |
|---|------|-------|-------------|
| 14 | `eth_getLogs` (1k blocks) | `latest` | Transfer events from recent 1,000 block range |
| 15 | `eth_getLogs` (1k blocks) | `archival` | Transfer events from archival 1,000 block range |
| 16 | `eth_getLogs` (10k blocks) | `latest` | Transfer events from recent 10,000 block range |
| 17 | `eth_getLogs` (10k blocks) | `archival` | Transfer events from archival 10,000 block range |
| 18 | `debug_traceTransaction` | `archival` | Trace a complex swap transaction (optional) |
| 19 | `trace_replayTransaction` | `archival` | Replay transaction with trace (optional) |

---

**Load Tests:**

| # | Test | Concurrency | Description |
|---|------|-------------|-------------|
| 20 | `eth_blockNumber` burst | 50 | 50 concurrent requests for simple call |
| 21 | `eth_call` burst | 50 | 50 concurrent requests for medium call |
| 22 | `eth_getLogs` burst | 25 | 25 concurrent requests for complex call |

**Load test configuration (editable in UI):**

| Setting | Default | Description |
|---------|---------|-------------|
| Concurrency (simple) | 50 | Parallel requests for simple call burst |
| Concurrency (medium) | 50 | Parallel requests for medium call burst |
| Concurrency (complex) | 25 | Parallel requests for complex call burst (lower to avoid mass rate limiting) |
| Method (simple) | `eth_blockNumber` | Which simple method to use |
| Method (medium) | `eth_call` (balanceOf) | Which medium method to use |
| Method (complex) | `eth_getLogs` (1k range) | Which complex method to use |

**What load tests reveal:**
- **Rate limiting behavior**: Does the provider throttle? At what threshold?
- **Performance degradation**: How much slower under load vs. sequential?
- **Consistency**: High variance under load = poor connection pooling/queuing
- **Max throughput**: Effective requests-per-second capability

---

**Test Count Summary:**
- Simple: 5 tests (3 latest, 2 archival)
- Medium: 8 tests (5 latest, 3 archival)
- Complex: 6 tests (2 latest, 4 archival)
- Load: 3 tests (concurrent bursts)
- **Total: 22 tests**

#### 2.3 Test Parameters

Pre-defined constants for Ethereum mainnet (can be extended for other chains):

```python
TEST_PARAMS = {
    # Chain
    "chain_id": 1,

    # Known addresses for balance/call tests
    "known_address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",  # vitalik.eth
    "usdc_contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "usdc_holder": "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",  # Binance

    # Storage slot test (USDC totalSupply slot)
    "storage_contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "storage_slot": "0x0",

    # Block references
    "archival_block": 12000000,        # ~March 2021, ~3.5 years old
    "recent_block_offset": 100,        # latest - 100 for "recent" tests

    # Transaction hashes
    "recent_tx_hash": "0x...",         # A recent transaction (update periodically)
    "archival_tx_hash": "0x...",       # Complex swap from archival block range

    # getLogs ranges
    "logs_range_small": 1000,
    "logs_range_large": 10000,
    "archival_logs_start": 12000000,   # Start of archival log range
    # recent logs: (latest - range) to latest
}
```

**Note on archival block selection:** Block 12,000,000 was chosen because:
- Old enough to require archive node access (~3.5 years)
- USDC contract was active with significant transfer volume
- After major protocol upgrades (stable state)
- Well within typical archive node retention

#### 2.4 Configurable Test Parameters (UI)

To ensure fair benchmarking and avoid pre-cached results, **all test parameters are viewable and editable via the UI**.

**Why this matters:**
- Static test parameters might be pre-cached by providers (from other users, internal testing, etc.)
- Users may want to test queries relevant to their specific use case
- Fresh/random parameters ensure true cold-cache measurement

**Parameter Configuration UI:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Test Parameters                                    [Randomize] │
├─────────────────────────────────────────────────────────────────┤
│ Addresses                                                       │
│   Known Address:     [0xd8dA6BF2...] [📋] [🎲]                  │
│   Token Contract:    [0xA0b86991...] [📋] [🎲]                  │
│   Token Holder:      [0x47ac0Fb4...] [📋] [🎲]                  │
│                                                                 │
│ Block References                                                │
│   Archival Block:    [12000000    ] (~Mar 2021)                │
│   Recent Offset:     [100         ] blocks behind head          │
│                                                                 │
│ getLogs Ranges                                                  │
│   Small Range:       [1000        ] blocks                      │
│   Large Range:       [10000       ] blocks                      │
│                                                                 │
│ Transaction Hashes                                              │
│   Recent Tx:         [0x...       ] [Fetch Random Recent]       │
│   Archival Tx:       [0x...       ] [Fetch Random from Block]   │
│                                                                 │
│ [Load Defaults] [Save Config] [Import JSON]                     │
└─────────────────────────────────────────────────────────────────┘
```

**Randomization features:**

| Parameter | Randomization Strategy |
|-----------|----------------------|
| Known Address | Pick from list of well-known addresses with guaranteed activity |
| Token Contract | Pick from top 20 ERC20 tokens by transfer volume |
| Token Holder | Query top holders of selected token, pick randomly |
| Archival Block | Random block between 10M-15M (guaranteed archive territory) |
| Transaction Hash | Fetch random tx from specified block via `eth_getBlockByNumber` |

**Pre-flight validation:**
Before running benchmarks, the system validates that test parameters are usable:
- Addresses exist and have balance/activity at specified blocks
- Transaction hashes are valid
- Block numbers are within reasonable ranges
- Token holder actually held tokens at archival block

**Parameter presets:**
- **Defaults**: Ship with sensible static values (current TEST_PARAMS)
- **Fresh**: Auto-generate random valid parameters before each run
- **Custom**: User-defined values saved locally
- **Import/Export**: JSON format for sharing configurations

#### 2.5 Chain Configuration Management

Each chain requires specific configuration for tests to work correctly. This is managed via a dedicated **Chain Config** page.

**Chain Configuration UI:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Chain Configuration                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ Chain: [Ethereum Mainnet ▼]  Chain ID: 1                                    │
│                                                                             │
│ ┌─ Presets ─────────────────────────────────────────────────────────────┐  │
│ │ [Ethereum] [Arbitrum] [Optimism] [Base] [Polygon] [+ Custom Chain]    │  │
│ └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════ │
│                                                                             │
│ CHAIN SETTINGS                                                              │
│ ├─ Chain Name:       [Ethereum Mainnet    ]                                 │
│ ├─ Chain ID:         [1                   ]                                 │
│ ├─ Block Time:       [12                  ] seconds                         │
│ ├─ Archive Cutoff:   [12000000            ] (blocks older = archival)       │
│ └─ Native Token:     [ETH                 ]                                 │
│                                                                             │
│ RPC METHOD SUPPORT                                                          │
│ ├─ [✓] debug_traceTransaction                                               │
│ ├─ [✓] trace_replayTransaction                                              │
│ └─ [✓] eth_getLogs (large ranges)                                           │
│                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════ │
│                                                                             │
│ TEST ADDRESSES (used for balance/call tests)                                │
│ ┌───────────────────────────────────────────────────────────────────────┐  │
│ │ Label              │ Address                                    │ ✓ │  │
│ ├────────────────────┼────────────────────────────────────────────┼───┤  │
│ │ vitalik.eth        │ 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 │ ✓ │  │
│ │ Binance Hot Wallet │ 0x28C6c06298d514Db089934071355E5743bf21d60 │ ✓ │  │
│ │ Coinbase           │ 0x71660c4005BA85c37ccec55d0C4493E66Fe775d3 │ ✓ │  │
│ └───────────────────────────────────────────────────────────────────────┘  │
│ [+ Add Address] [Import from block...] [Validate All]                       │
│                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════ │
│                                                                             │
│ TOKEN CONTRACTS (for balanceOf and getLogs tests)                           │
│ ┌───────────────────────────────────────────────────────────────────────┐  │
│ │ Symbol │ Address                                    │ Known Holder   │  │
│ ├────────┼────────────────────────────────────────────┼────────────────┤  │
│ │ USDC   │ 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 │ 0x47ac0Fb4...  │  │
│ │ USDT   │ 0xdAC17F958D2ee523a2206206994597C13D831ec7 │ 0xF977814e...  │  │
│ │ DAI    │ 0x6B175474E89094C44Da98b954EescdeCB5dC3C6f5│ 0x40ec5B33...  │  │
│ │ WETH   │ 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 │ 0x8EB8a3b9...  │  │
│ └───────────────────────────────────────────────────────────────────────┘  │
│ [+ Add Token] [Import popular tokens]                                       │
│                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════ │
│                                                                             │
│ ARCHIVAL BLOCK RANGE (for randomization)                                    │
│ ├─ From Block: [10000000      ] (~Jan 2020)                                 │
│ ├─ To Block:   [15000000      ] (~Jun 2022)                                 │
│ └─ Note: Randomize will pick blocks within this range for archival tests   │
│                                                                             │
│ TRANSACTION POOL (for getTransaction/trace tests)                           │
│ ┌───────────────────────────────────────────────────────────────────────┐  │
│ │ 0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060    │  │
│ │ 0x2d4c0b967f3b5c67e5e16fbb8d8e3e3f7c4e2a0e...                         │  │
│ │ [+ Add Transaction] [Fetch from recent blocks...]                     │  │
│ └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════ │
│                                                                             │
│ [Auto-populate from RPC ↻]  [Save Config]  [Export JSON]  [Reset to Default]│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Auto-populate from RPC:**
When clicked, uses one of the configured providers to automatically discover:
1. Verify chain ID matches
2. Get current block number
3. Calculate reasonable archival block range based on block time
4. Fetch recent blocks and extract active addresses/transactions
5. Populate randomization pools with discovered data

This allows users to quickly bootstrap a configuration for any chain without manual research.

**Chain config validation:**
Before saving, validates:
- Chain ID is a valid positive integer
- At least one test address configured
- At least one token contract configured
- Archive cutoff block < current block
- Archival block range is valid (from < to, both < current)

**Pre-flight chain verification:**
Before running benchmarks:
1. Query `eth_chainId` from all providers
2. Verify all providers return the same chain ID
3. Verify chain ID matches selected configuration
4. Warn if any mismatches detected

### 3. Benchmark Execution

#### 3.1 Run Configuration

- **Timeout**: Per-request timeout in seconds (default: 30s)
- **Delay**: Milliseconds between requests to avoid rate limiting (default: 100ms)
- **Concurrency**: Sequential by default, optional parallel mode per provider
- **Categories**: Select which categories to run (simple/medium/complex/load or all)
- **Labels**: Filter by test label (latest/archival/all) - useful for testing non-archive nodes
- **Load Test Concurrency**: Configurable per complexity tier (default: 50/50/25)

#### 3.1.1 Iteration Strategy

Rather than arbitrary iteration counts, we explicitly measure **cold** vs **warm** cache performance:

| Iteration | Name | Purpose |
|-----------|------|---------|
| 1 | `cold` | First request - no provider cache |
| 2 | `warm` | Second request - likely cached |
| 3 | `sustained` | Third request - confirms cache behavior |

**Default: 3 iterations per test** (cold + warm + sustained)

**Why 3 instead of 10?**
- Iterations 2-10 measure the same thing (cached performance)
- 3 iterations capture the meaningful state transitions
- Faster benchmark runs (~6 min vs ~15 min for full suite)
- Lower rate limit risk
- Reports actionable metrics: cold time, warm time, cache speedup ratio

**Configurable modes:**

| Mode | Iterations | Use case |
|------|------------|----------|
| Quick | 2 | Fast comparison, cold vs warm only |
| Standard | 3 | Default, balanced |
| Thorough | 10 | More samples for variance analysis |
| Statistical | 25 | Meaningful P90 percentile calculations |

**Inter-iteration delay:**
- Default: 0ms between iterations of the same test (measures immediate cache)
- Optional: Configurable delay (e.g., 1000ms) to test cache TTL behavior

#### 3.2 Execution Flow

1. User configures providers and run parameters
2. User initiates benchmark job
3. Pre-flight validation: verify chain ID, test parameters
4. Backend executes tests sequentially per provider
5. Progress indicator shows completion percentage (via SSE)
6. Results available when all tests complete (typically 2-5 minutes)

**Sequential Test Execution Order:**
```
For each provider:
    For each enabled test (in order: simple → medium → complex):
        For each iteration (1=cold, 2=warm, 3+=sustained):
            Execute RPC call
            Record timing and result
            Wait delay_ms before next iteration
        Wait delay_ms before next test
    Move to next provider
```

**Load Test Execution Order:**

Load tests are run **ONE PROVIDER AT A TIME** to avoid cross-provider interference:

```
For each provider:
    For each load test (simple burst, medium burst, complex burst):
        Send N concurrent requests simultaneously
        Wait for ALL responses (or timeout)
        Record individual timings and aggregate metrics
        Wait 2 seconds before next load test (cooldown)
    Move to next provider
```

This ensures each provider's load test results reflect only that provider's capacity, not contention with other providers.

#### 3.3 Error Handling

- Timeout: Record as failed, continue to next test
- Rate limit (429): Record error, apply exponential backoff, retry up to 3 times
- Connection error: Record as failed, continue
- Invalid response: Record as failed with error type
- Unsupported method: Skip test for that provider, note in results

### 4. Metrics Collection

For each test iteration, capture:

| Metric | Description |
|--------|-------------|
| `response_time_ms` | Total time from request sent to response received |
| `success` | Boolean - did the request succeed |
| `error_type` | If failed: timeout, rate_limit, connection, invalid_response, unsupported |
| `http_status` | HTTP status code |
| `response_size_bytes` | Size of response payload |

#### 4.1 Aggregated Metrics (per test, per provider)

**Core metrics (always calculated):**
- **Count**: Total attempts
- **Success Rate**: Percentage successful
- **Cold Time**: First iteration response time (uncached)
- **Warm Time**: Average of iterations 2+ (cached)
- **Cache Speedup**: cold_time / warm_time (e.g., 2.0x means cache is 50% faster)

**Extended metrics (when iterations >= 5):**
- **Mean**: Average response time (all successful iterations)
- **Median (P50)**: 50th percentile response time
- **Min/Max**: Range of response times
- **Std Dev**: Variance measure (high = inconsistent)

**Statistical metrics (when iterations >= 25):**
- **P90**: 90th percentile response time
- **P95**: 95th percentile response time

Note: P99 requires 100+ samples to be meaningful and is not reported.

#### 4.2 Load Test Metrics

Load tests capture different metrics since all requests run concurrently:

| Metric | Description |
|--------|-------------|
| `concurrency` | Number of parallel requests sent |
| `total_time_ms` | Wall clock time from first request to last response |
| `min_ms` | Fastest individual response |
| `max_ms` | Slowest individual response |
| `avg_ms` | Average response time across all concurrent requests |
| `p50_ms` | Median response time |
| `p95_ms` | 95th percentile (with 50 samples, this is meaningful) |
| `success_count` | Number of successful responses |
| `error_count` | Number of failed responses (timeouts, rate limits, errors) |
| `success_rate` | success_count / concurrency |
| `throughput_rps` | Effective requests per second: success_count / (total_time_ms / 1000) |

**Load test comparison table (example output):**

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Load Test: eth_blockNumber (50 concurrent)                                   │
├─────────────┬──────────┬──────────┬─────────┬─────────┬─────────┬────────────┤
│ Provider    │ min      │ p50      │ avg     │ p95     │ max     │ throughput │
├─────────────┼──────────┼──────────┼─────────┼─────────┼─────────┼────────────┤
│ Tenderly    │ 57ms     │ 79ms     │ 79ms    │ 106ms   │ 125ms   │ 312 rps    │
│ eRPC Edge   │ 87ms     │ 267ms    │ 480ms   │ 1,322ms │ 1,420ms │ 89 rps     │
│ Provider C  │ 45ms     │ 52ms     │ 58ms    │ 89ms    │ 112ms   │ 445 rps    │
└─────────────┴──────────┴──────────┴─────────┴─────────┴─────────┴────────────┘
```

### 5. Results & Visualization

#### 5.1 Dashboard Views

**Summary View:**
- Overall ranking table: providers sorted by average performance
- Success rate comparison across all tests
- Quick verdict: "fastest overall", "most reliable", etc.

**Category Breakdown:**
- Performance comparison per category (simple/medium/complex)
- Identifies providers that excel at specific workloads

**Cold vs Warm Cache Comparison:**
- Side-by-side comparison of cold (first request) vs warm (cached) performance
- Shows "cache speedup" per provider - how much faster cached responses are
- Identifies providers with effective caching vs. those with minimal caching benefit
- Grouped bar charts: cold time vs warm time per test
- Helps answer: "Is this provider fast because of good caching or good infrastructure?"

**Latest vs Archival Comparison:**
- Side-by-side comparison of the same call type at latest vs archival blocks
- Highlights providers with optimized archive infrastructure
- Shows "archive penalty" - the latency increase for archival queries
- Grouped bar charts: `eth_getBalance (latest)` next to `eth_getBalance (archival)`
- Archive performance ratio: archival_time / latest_time (lower is better)

**Detailed View:**
- Per-test results with box plots showing distribution
- Response time histograms per provider
- Error breakdown by type
- Filter toggles: show latest only / archival only / all

**Regional Comparison** (if region tags provided):
- Group results by region
- Identify regional performance patterns

**Load Test Results:**
- Comparison table showing min/p50/avg/p95/max per provider (like screenshot example)
- Throughput bar chart (requests per second)
- Success rate indicators (highlight providers with errors under load)
- Latency distribution histogram per provider
- "Load degradation factor": avg_load_time / avg_sequential_time (shows how much slower under load)

#### 5.2 Chart Types

- **Bar charts**: Average response times by provider
- **Box plots**: Response time distributions showing median, quartiles, outliers
- **Tables**: Detailed metrics with sorting/filtering
- **Success rate indicators**: Visual pass/fail rates

#### 5.3 Export

- **JSON**: Full raw results with all iterations and metadata
- **CSV**: Summary table for spreadsheet analysis
- Download buttons in UI

**Export filename format:**
```
benchmark_{chain_name}_{chain_id}_{timestamp}.json
benchmark_{chain_name}_{chain_id}_{timestamp}.csv
```

Examples:
- `benchmark_ethereum_1_2024-01-15_143022.json`
- `benchmark_arbitrum_42161_2024-01-15_150134.json`
- `benchmark_polygon_137_2024-01-15_161245.csv`

**JSON export structure:**

The export contains everything needed to understand and reproduce the benchmark:

```json
{
  "metadata": {
    "tool_version": "1.0.0",
    "exported_at": "2024-01-15T14:30:22Z"
  },
  "chain": {
    "id": 1,
    "name": "Ethereum Mainnet",
    "archive_cutoff_block": 12000000
  },
  "job": {
    "id": "abc123-uuid",
    "created_at": "2024-01-15T14:25:00Z",
    "completed_at": "2024-01-15T14:30:22Z",
    "duration_seconds": 322,
    "status": "completed",
    "config": {
      "iteration_mode": "standard",
      "timeout_seconds": 30,
      "delay_ms": 100,
      "categories": ["simple", "medium", "complex", "load"],
      "labels": ["latest", "archival"]
    }
  },
  "providers": [
    {
      "id": "p1",
      "name": "Alchemy",
      "region": "us-east",
      "url_hash": "sha256:abc..."
    }
  ],
  "test_params": {
    "known_address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    "token_contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "token_holder": "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",
    "archival_block": 12000000,
    "recent_block_offset": 100,
    "logs_range_small": 1000,
    "logs_range_large": 10000
  },
  "tests_executed": [
    {
      "id": 1,
      "name": "eth_blockNumber",
      "category": "simple",
      "label": "latest",
      "enabled": true,
      "rpc_method": "eth_blockNumber",
      "rpc_params": []
    },
    {
      "id": 5,
      "name": "eth_getBalance (archival)",
      "category": "simple",
      "label": "archival",
      "enabled": true,
      "rpc_method": "eth_getBalance",
      "rpc_params": ["0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "0xB71B00"]
    },
    {
      "id": 20,
      "name": "eth_blockNumber_burst",
      "category": "load",
      "label": "latest",
      "enabled": true,
      "rpc_method": "eth_blockNumber",
      "rpc_params": [],
      "concurrency": 50
    }
  ],
  "results": {
    "sequential": [
      {
        "provider_id": "p1",
        "test_id": 1,
        "iterations": [
          { "iteration": 1, "type": "cold", "response_time_ms": 45.2, "success": true },
          { "iteration": 2, "type": "warm", "response_time_ms": 32.1, "success": true },
          { "iteration": 3, "type": "sustained", "response_time_ms": 31.8, "success": true }
        ]
      }
    ],
    "load_tests": [
      {
        "provider_id": "p1",
        "test_id": 20,
        "concurrency": 50,
        "total_time_ms": 1250,
        "min_ms": 28,
        "max_ms": 312,
        "avg_ms": 89,
        "p50_ms": 67,
        "p95_ms": 245,
        "success_count": 48,
        "error_count": 2,
        "throughput_rps": 38.4
      }
    ],
    "aggregated": [
      {
        "provider_id": "p1",
        "test_id": 1,
        "cold_ms": 45.2,
        "warm_ms": 31.95,
        "cache_speedup": 1.41,
        "success_rate": 1.0
      }
    ]
  }
}
```

**Note:** Provider URLs are not included in exports (security - may contain API keys). Instead, a `url_hash` is provided for verification purposes.

---

## Non-Functional Requirements

### 6. Technology Stack

**Backend:**
- Python 3.11+
- FastAPI for REST API
- `httpx` or `aiohttp` for async HTTP requests
- `web3.py` for RPC call construction (optional, can use raw JSON-RPC)
- Pydantic for data validation
- SQLite for job persistence (or in-memory for simplicity)

**Frontend:**
- Vanilla JavaScript (ES6+) with no build step
- CSS: Custom styles with CSS variables for theming
- Chart.js for visualizations (loaded via CDN or bundled)
- Static files served by FastAPI (no separate frontend server)
- Responsive design for desktop browsers

**Frontend File Structure:**
```
frontend/
├── index.html              # Single HTML entry point
├── css/
│   └── styles.css          # All styles (CSS variables, layout, components)
├── js/
│   ├── app.js              # Main entry point, router
│   ├── api.js              # API client (fetch wrapper, SSE handler)
│   ├── state.js            # Simple state management
│   ├── components/
│   │   ├── benchmark-wizard.js   # New benchmark flow
│   │   ├── chain-config.js       # Chain configuration UI
│   │   ├── results-list.js       # Results list view
│   │   ├── results-detail.js     # Single result view
│   │   ├── progress-view.js      # Live progress display
│   │   └── charts.js             # Chart.js wrapper functions
│   └── utils/
│       ├── formatting.js         # Number/date formatting
│       └── validation.js         # Input validation helpers
└── lib/
    └── chart.min.js              # Chart.js (bundled for offline use)
```

### 7. Performance

- Handle up to 10 providers in a single benchmark run
- Estimated run times (10 providers × 100ms delay):
  - **Sequential tests (19 tests):**
    - Quick mode: 2 iterations = 380 requests, ~2 minutes
    - Standard mode: 3 iterations = 570 requests, ~3 minutes
    - Thorough mode: 10 iterations = 1,900 requests, ~10 minutes
    - Statistical mode: 25 iterations = 4,750 requests, ~25 minutes
  - **Load tests (3 tests):**
    - 50+50+25 = 125 concurrent requests per provider
    - 1,250 total requests, ~30 seconds (run in parallel)
  - **Full suite (22 tests, standard mode):** ~4 minutes total
- UI remains responsive during benchmark execution
- Results persist locally until explicitly cleared

### 8. Security

- RPC URLs may contain API keys - never log full URLs
- Sanitize displayed URLs (mask API keys)
- No external data transmission - fully local operation
- Optional: support for URLs via environment variables

### 9. Storage

**Location:** `~/.rpc-benchmarker/`

**Directory Structure:**
```
~/.rpc-benchmarker/
├── config.json              # App-level settings
├── chains/                  # Chain configurations
│   ├── ethereum.json        # Preset: Ethereum Mainnet
│   ├── arbitrum.json        # Preset: Arbitrum One
│   ├── optimism.json        # Preset: Optimism
│   ├── base.json            # Preset: Base
│   ├── polygon.json         # Preset: Polygon
│   ├── bsc.json             # Preset: BSC
│   ├── avalanche.json       # Preset: Avalanche C-Chain
│   └── custom_*.json        # User-created chain configs
└── benchmarks.db            # SQLite database for jobs and results
```

**config.json:**
```json
{
  "default_timeout_seconds": 30,
  "default_delay_ms": 100,
  "default_iteration_mode": "standard",
  "theme": "system"
}
```

**SQLite Schema (benchmarks.db):**

```sql
-- Benchmark jobs
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    chain_id INTEGER NOT NULL,
    chain_name TEXT NOT NULL,
    status TEXT NOT NULL,  -- pending, running, completed, failed, cancelled
    config_json TEXT NOT NULL,  -- BenchmarkConfig as JSON
    created_at TEXT NOT NULL,
    completed_at TEXT,
    duration_seconds REAL
);

-- Providers per job
CREATE TABLE job_providers (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url_encrypted TEXT NOT NULL,  -- URL encrypted or hashed
    region TEXT
);

-- Test parameters per job
CREATE TABLE job_test_params (
    job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    params_json TEXT NOT NULL  -- TestParams as JSON
);

-- Sequential test results
CREATE TABLE test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    provider_id TEXT NOT NULL,
    test_id INTEGER NOT NULL,
    test_name TEXT NOT NULL,
    category TEXT NOT NULL,
    label TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    iteration_type TEXT NOT NULL,  -- cold, warm, sustained
    response_time_ms REAL,
    success INTEGER NOT NULL,
    error_type TEXT,
    http_status INTEGER,
    response_size_bytes INTEGER,
    timestamp TEXT NOT NULL
);

-- Load test results
CREATE TABLE load_test_results (
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
    success_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    throughput_rps REAL NOT NULL,
    errors_json TEXT,  -- list of error types as JSON
    timestamp TEXT NOT NULL
);

-- Indexes for common queries
CREATE INDEX idx_jobs_chain ON jobs(chain_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_test_results_job ON test_results(job_id);
CREATE INDEX idx_load_results_job ON load_test_results(job_id);
```

**First-run Behavior:**
1. Check if `~/.rpc-benchmarker/` exists
2. If not, create directory structure
3. Copy preset chain configs from application bundle
4. Initialize empty SQLite database with schema
5. Create default `config.json`

**Data Retention:**
- No automatic cleanup - user controls when to delete old results
- "Clear All Data" option in Settings page
- Individual job deletion via Results page

---

## User Interface Specification

### 10. Navigation Structure

```
┌────────────────────────────────────────────────────────────────────────────┐
│ RPC Benchmarker                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  [🏠 Benchmark]    [⛓️ Chain Config]    [📊 Results]    [⚙️ Settings]      │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

| Page | Purpose |
|------|---------|
| **Benchmark** | Configure providers, test params, and run benchmarks |
| **Chain Config** | Manage chain-specific settings, addresses, tokens, block ranges |
| **Results** | View past benchmark results, compare runs, export data |
| **Settings** | App preferences, default timeout/delay values, theme |

### 11. Pages/Views

#### 11.1 Home / New Benchmark

**Step 1: Select Chain**
- Dropdown to select from configured chains
- Shows: Chain name, Chain ID, number of configured addresses/tokens
- Quick link to "Chain Config" page if selected chain needs setup
- Displays warning if chain config is incomplete

**Step 2: Providers**
- Form to add/remove providers (name, URL, region)
- Import providers from JSON
- Mask API keys in displayed URLs
- Chain ID verification indicator (confirms providers serve selected chain)

**Step 3: Test Parameters**
- View all 22 planned tests in a table with columns: Enable | Test Name | Category | Label | Parameters
- **Individual test toggle**: Checkbox next to each test to enable/disable
- "Select All" / "Deselect All" buttons per category
- Edit any parameter (addresses, blocks, ranges)
- "Randomize All" button for fresh uncached queries (uses chain config pools)
- "Load Defaults" to reset
- Pre-flight validation status indicator (green checkmark or red X per test)
- Expandable section showing exact RPC calls that will be made
- Grayed out tests if chain doesn't support them (e.g., debug_trace on chains without trace support)
- Test count indicator: "18 of 22 tests enabled"

**Step 4: Run Options**
- Iteration mode selector (Quick/Standard/Thorough/Statistical)
- Category filter (simple/medium/complex/load)
- Label filter (latest/archival)
- Timeout and delay settings
- Load test configuration:
  - Concurrency sliders (10-100) for each tier
  - Method selector for each load test

**Actions:**
- "Preview Tests" - show exact test plan before running
- "Start Benchmark" button
- List of previous runs with timestamps (filterable by chain)

#### 11.2 Chain Config Page

See section 2.5 for detailed UI mockup. Key features:
- Chain preset selector (quick-switch between chains)
- All configuration fields for selected chain
- Auto-populate from RPC button
- Import/Export chain configs as JSON
- Validation status indicators

#### 11.3 Progress View

- Current chain displayed at top
- Progress bar showing completion percentage
- Live status: "Testing Provider X - Test Y (iteration Z)"
- Cancel button
- Auto-redirect to results when complete

#### 11.4 Results View

**Results List:**
- Table of all benchmark runs
- Columns: Date, Chain, Providers, Tests Run, Duration
- Filter by chain dropdown
- Search by provider name
- Click to view detailed results

**Single Result View:**
- Chain info banner at top (name, ID)
- Summary statistics
- Tab navigation: Summary | By Category | Cold vs Warm | Latest vs Archival | Load Tests | Export
- Interactive charts (hover for values)
- Export buttons (JSON, CSV)

**Compare Mode:**
- Select 2+ results (same chain) to compare side-by-side
- Useful for comparing same providers over time or different provider sets

---

## Data Models

### 12. Core Entities

```python
# Chain configuration (stored per chain, user-editable)
ChainConfig:
    chain_id: int
    chain_name: str
    block_time_seconds: int
    archive_cutoff_block: int
    native_token_symbol: str

    # RPC method support flags
    supports_debug_trace: bool
    supports_trace_replay: bool
    supports_large_logs: bool

    # Test addresses (for balance checks)
    test_addresses: list[AddressEntry]

    # Token contracts (for balanceOf and getLogs)
    token_contracts: list[TokenEntry]

    # Randomization pools
    archival_block_range: tuple[int, int]  # (from_block, to_block)
    transaction_pool: list[str]            # tx hashes for getTransaction/trace tests

    # Metadata
    created_at: datetime
    updated_at: datetime
    is_preset: bool                        # true if shipped with app, false if user-created

AddressEntry:
    label: str           # e.g., "vitalik.eth"
    address: str         # 0x...
    verified: bool       # passed validation

TokenEntry:
    symbol: str          # e.g., "USDC"
    address: str         # contract address
    holder_address: str  # known holder for balanceOf tests
    verified: bool

# Provider configuration
Provider:
    id: str (uuid)
    name: str
    url: str
    region: str | None

# Benchmark job (includes chain info for result identification)
BenchmarkJob:
    id: str (uuid)
    created_at: datetime
    completed_at: datetime | None
    status: "pending" | "running" | "completed" | "failed" | "cancelled"
    chain_id: int                          # chain this benchmark was run against
    chain_name: str                        # denormalized for display
    config: BenchmarkConfig
    providers: list[Provider]

# Run configuration
BenchmarkConfig:
    iteration_mode: "quick" | "standard" | "thorough" | "statistical"  # 2/3/10/25 iterations
    timeout_seconds: int
    delay_ms: int
    inter_iteration_delay_ms: int  # delay between iterations of same test (for cache TTL testing)
    categories: list["simple" | "medium" | "complex" | "load"]
    labels: list["latest" | "archival"]  # filter which tests to run
    test_params: TestParams  # user-configured or randomized parameters
    # Load test specific config
    load_concurrency_simple: int     # default: 50
    load_concurrency_medium: int     # default: 50
    load_concurrency_complex: int    # default: 25

# Test parameters (user-configured or randomized)
TestParams:
    # Addresses
    known_address: str               # for eth_getBalance tests
    token_contract: str              # ERC20 for balanceOf and getLogs
    token_holder: str                # address holding tokens for balanceOf
    storage_contract: str            # contract for eth_getStorageAt
    storage_slot: str                # storage slot to query

    # Block references
    archival_block: int              # specific block for archival tests
    recent_block_offset: int         # offset from head for "recent" tests (default: 100)

    # Transaction hashes
    recent_tx_hash: str | None       # for getTransactionByHash/Receipt (recent)
    archival_tx_hash: str | None     # for debug_trace/trace_replay (archival)

    # getLogs configuration
    logs_token_contract: str         # token to query Transfer events
    logs_range_small: int            # small range size (default: 1000)
    logs_range_large: int            # large range size (default: 10000)
    archival_logs_start_block: int   # start block for archival log queries

# Individual test result
TestResult:
    job_id: str
    provider_id: str
    test_name: str
    category: str
    label: "latest" | "archival"
    iteration: int
    iteration_type: "cold" | "warm" | "sustained"  # 1st=cold, 2nd=warm, 3+=sustained
    response_time_ms: float | None
    success: bool
    error_type: str | None
    http_status: int | None
    response_size_bytes: int | None
    timestamp: datetime

# Aggregated results (computed)
AggregatedResult:
    provider_id: str
    test_name: str
    category: str
    label: "latest" | "archival"
    count: int
    success_rate: float
    # Core metrics (always present)
    cold_ms: float              # first iteration
    warm_ms: float              # average of iterations 2+
    cache_speedup: float        # cold_ms / warm_ms
    # Extended metrics (when iterations >= 5)
    mean_ms: float | None
    median_ms: float | None
    min_ms: float | None
    max_ms: float | None
    std_dev_ms: float | None
    # Statistical metrics (when iterations >= 25)
    p90_ms: float | None
    p95_ms: float | None

# Archive comparison (computed for paired tests)
ArchiveComparison:
    provider_id: str
    test_base_name: str              # e.g., "eth_getBalance" (without label)
    category: str
    latest_mean_ms: float
    archival_mean_ms: float
    archive_penalty_ms: float        # archival - latest
    archive_penalty_ratio: float     # archival / latest

# Load test result (one per load test per provider)
LoadTestResult:
    job_id: str
    provider_id: str
    test_name: str                   # e.g., "eth_blockNumber_burst"
    method: str                      # RPC method used
    concurrency: int                 # number of parallel requests
    total_time_ms: float             # wall clock time for entire burst
    min_ms: float
    max_ms: float
    avg_ms: float
    p50_ms: float
    p95_ms: float
    success_count: int
    error_count: int
    success_rate: float
    throughput_rps: float            # requests per second
    errors: list[str]                # error types encountered
    timestamp: datetime

# Load degradation comparison (computed)
LoadDegradation:
    provider_id: str
    method: str
    sequential_avg_ms: float         # from standard test
    load_avg_ms: float               # from load test
    degradation_factor: float        # load_avg / sequential_avg
```

---

## API Endpoints

### 13. REST API

```
# Benchmark Jobs
POST   /api/jobs                    Create new benchmark job
GET    /api/jobs                    List all jobs (filterable by chain_id)
GET    /api/jobs/{id}               Get job status and config
GET    /api/jobs/{id}/results       Get results (raw or aggregated)
DELETE /api/jobs/{id}               Delete job and results
POST   /api/jobs/{id}/cancel        Cancel running job

# Progress (Server-Sent Events)
GET    /api/jobs/{id}/progress      SSE stream of job progress updates

# Chain Configuration
GET    /api/chains                  List all chain configs (presets + custom)
GET    /api/chains/{chain_id}       Get chain config by chain ID
POST   /api/chains                  Create custom chain config
PUT    /api/chains/{chain_id}       Update chain config
DELETE /api/chains/{chain_id}       Delete custom chain config (presets cannot be deleted)

# Provider Validation
POST   /api/providers/validate      Validate provider URLs return expected chain ID
                                    Body: { "urls": [...], "expected_chain_id": 1 }

# Test Parameters
GET    /api/test-cases              List available test cases with their parameters
POST   /api/params/randomize        Generate random valid test parameters for chain
                                    Body: { "chain_id": 1 }
POST   /api/params/validate         Validate test parameters are usable
                                    Body: { "chain_id": 1, "params": {...}, "provider_url": "..." }

# Export
GET    /api/export/{id}/json        Download results as JSON
GET    /api/export/{id}/csv         Download summary as CSV
```

**SSE Progress Events:**

The `/api/jobs/{id}/progress` endpoint streams Server-Sent Events with the following event types:

| Event | Data | Description |
|-------|------|-------------|
| `job_started` | `{ job_id, total_tests, total_iterations }` | Job has begun |
| `provider_started` | `{ provider_id, provider_name }` | Starting tests for provider |
| `test_started` | `{ test_id, test_name, category, label }` | Individual test starting |
| `iteration_complete` | `{ test_id, iteration, response_time_ms, success }` | Single iteration done |
| `test_complete` | `{ test_id, test_name, results_summary }` | All iterations for test done |
| `provider_complete` | `{ provider_id, provider_name }` | All tests for provider done |
| `job_complete` | `{ job_id, duration_seconds }` | Entire job finished |
| `error` | `{ message, test_id?, provider_id? }` | Error occurred |

**Example SSE stream:**
```
event: job_started
data: {"job_id": "abc123", "total_tests": 22, "total_iterations": 66}

event: provider_started
data: {"provider_id": "p1", "provider_name": "Alchemy"}

event: test_started
data: {"test_id": 1, "test_name": "eth_blockNumber", "category": "simple", "label": "latest"}

event: iteration_complete
data: {"test_id": 1, "iteration": 1, "response_time_ms": 45.2, "success": true}
...
```

---

## Future Considerations (Out of Scope for V1)

- Scheduled/recurring benchmarks
- Historical trend analysis across multiple runs
- Latency testing from multiple geographic regions (would require distributed deployment)
- Advanced tests: `eth_subscribe`, batch requests, WebSocket RPC performance
- Provider auto-detection (identify provider from URL patterns)
- Cost estimation based on provider pricing
- Batch RPC request testing (multiple calls in single HTTP request)

---

## Success Criteria

The utility is complete when:

1. User can select from pre-configured chains or create custom chain config
2. User can input 2+ RPC provider URLs (verified against selected chain)
3. Benchmark runs all test categories (simple/medium/complex/load) and labels (latest/archival) successfully
4. Results display comparative charts showing response time differences
5. Cold vs warm comparison view shows cache speedup metrics
6. Latest vs archival comparison view shows archive penalty metrics
7. Load test results show throughput and percentile breakdown (min/p50/avg/p95/max)
8. User can export results as JSON with chain info in filename
9. Results list is filterable by chain
10. Tool runs entirely locally without external dependencies (beyond RPC calls)
11. Total setup time < 5 minutes (clone, install deps, run)
