# RPC Benchmarker

A tool for comparing performance of Ethereum JSON-RPC providers. Runs standardized tests across multiple providers and generates detailed comparison reports.

## Features

- **Multi-provider comparison** - Test multiple RPC endpoints side-by-side
- **Sequential tests** - Measure cold/warm latency for various RPC methods
- **Load tests** - Concurrent request performance with throughput metrics
- **Archival tests** - Compare historical data access performance
- **Export/Import** - Share results as JSON, import others' benchmarks
- **Error tracking** - Categorize errors as provider vs parameter issues

## Install

```bash
# Clone and setup
cd rpc-benchmarking
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Run
cd backend
python -m uvicorn app.main:app --reload --port 8420
```

Open http://localhost:8420 in your browser.

## Usage

### 1. Select Chain
Choose from presets (Ethereum, Arbitrum, etc.) or add custom chains.

### 2. Add Providers
Enter RPC URLs to compare. Auto-validates chain ID match.

### 3. Configure Tests
- **Quick** - 1 iteration per test
- **Standard** - 3 iterations (cold + warm)
- **Thorough** - 5 iterations

Filter by category (simple/medium/complex/load) and type (latest/archival).

### 4. Set Parameters
- **Known Address** - Any address with balance (e.g., exchange wallet)
- **Archival Block** - Historical block number for archival tests
- **Token Contract** - High-volume ERC20 for getLogs tests (e.g., USDC, WETH)

### 5. Run & Review
Start benchmark, watch progress, then explore:
- **Overview** - Error summary and success rates
- **Sequential Tests** - Latency breakdown by test
- **Load Tests** - Throughput and percentile latencies
- **Comparison** - Side-by-side provider ranking

### Import Results
On the History page, click "Import Results" to load exported JSON from others.

## Data Storage

All data stored in `~/.rpc-benchmarker/`:
- `benchmarks.db` - SQLite database
- `chains/` - Chain configurations

## Tests Included

| Category | Test | Description |
|----------|------|-------------|
| Simple | eth_blockNumber | Current block number |
| Simple | eth_chainId | Chain identifier |
| Simple | eth_gasPrice | Current gas price |
| Simple | eth_getBalance | Address balance (latest + archival) |
| Medium | eth_getBlockByNumber | Block data (latest + archival) |
| Complex | eth_getLogs | Event logs (1k/10k blocks, latest/archival) |
| Load | eth_blockNumber burst | 50 concurrent requests |
| Load | eth_getLogs burst | 25 concurrent requests |

## License

MIT
