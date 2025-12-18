"""Pydantic models for the RPC Benchmarker application."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestCategory(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    LOAD = "load"


class TestLabel(str, Enum):
    LATEST = "latest"
    ARCHIVAL = "archival"


class IterationType(str, Enum):
    COLD = "cold"
    WARM = "warm"
    SUSTAINED = "sustained"


class IterationMode(str, Enum):
    QUICK = "quick"        # 2 iterations
    STANDARD = "standard"  # 3 iterations
    THOROUGH = "thorough"  # 10 iterations
    STATISTICAL = "statistical"  # 25 iterations


class ErrorCategory(str, Enum):
    """Categorization of RPC errors for analysis.

    Provider errors (not user's fault):
    - TIMEOUT: Provider didn't respond in time
    - RATE_LIMIT: Provider rate limiting (429)
    - CONNECTION: Network/connection issues
    - UNSUPPORTED: Method not supported by provider

    Parameter errors (likely user's fault):
    - INVALID_PARAMS: Bad parameter format/values
    - EXECUTION_REVERTED: Contract call reverted (wrong address/data)
    - BLOCK_RANGE_LIMIT: Block range exceeds provider limit

    Other:
    - RPC_ERROR: Other RPC-level errors
    - UNKNOWN: Unclassified errors
    """
    # Provider errors
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    CONNECTION = "connection"
    UNSUPPORTED = "unsupported"

    # Parameter errors
    INVALID_PARAMS = "invalid_params"
    EXECUTION_REVERTED = "execution_reverted"
    BLOCK_RANGE_LIMIT = "block_range_limit"

    # Other
    RPC_ERROR = "rpc_error"
    UNKNOWN = "unknown"

    @classmethod
    def is_provider_error(cls, error: "ErrorCategory") -> bool:
        """Check if this error is the provider's fault."""
        return error in (cls.TIMEOUT, cls.RATE_LIMIT, cls.CONNECTION, cls.UNSUPPORTED)

    @classmethod
    def is_param_error(cls, error: "ErrorCategory") -> bool:
        """Check if this error is likely the user's fault (bad params)."""
        return error in (cls.INVALID_PARAMS, cls.EXECUTION_REVERTED, cls.BLOCK_RANGE_LIMIT)


# ============================================================================
# Chain Configuration
# ============================================================================

class AddressEntry(BaseModel):
    """An address entry for testing."""
    label: str
    address: str
    verified: bool = False


class TokenEntry(BaseModel):
    """A token contract entry for testing."""
    symbol: str
    address: str
    holder_address: str
    verified: bool = False


class ChainConfig(BaseModel):
    """Configuration for a specific blockchain."""
    chain_id: int
    chain_name: str
    block_time_seconds: int = 12
    archive_cutoff_block: int
    native_token_symbol: str = "ETH"

    # RPC method support flags
    supports_debug_trace: bool = True
    supports_trace_replay: bool = True
    supports_large_logs: bool = True

    # Test addresses
    test_addresses: list[AddressEntry] = Field(default_factory=list)

    # Token contracts
    token_contracts: list[TokenEntry] = Field(default_factory=list)

    # Randomization pools
    archival_block_range: tuple[int, int] = (10000000, 15000000)
    transaction_pool: list[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_preset: bool = False


# ============================================================================
# Provider
# ============================================================================

class Provider(BaseModel):
    """An RPC provider configuration."""
    id: str
    name: str
    url: str
    region: str | None = None


class ProviderCreate(BaseModel):
    """Request to create a provider."""
    name: str
    url: str
    region: str | None = None


class ProviderValidationRequest(BaseModel):
    """Request to validate provider URLs."""
    urls: list[str]
    expected_chain_id: int


class ProviderValidationResponse(BaseModel):
    """Response from provider validation."""
    valid: bool
    results: list[dict[str, Any]]


# ============================================================================
# Test Configuration
# ============================================================================

class TestParams(BaseModel):
    """Parameters for test execution.

    Simplified parameter set - only requires:
    - A known address for balance tests (any address with non-zero balance)
    - Block references for archival tests
    - A token contract for getLogs (e.g. WETH - very common on all chains)
    """
    # Address for eth_getBalance tests
    known_address: str

    # Block references
    archival_block: int
    recent_block_offset: int = 100

    # getLogs configuration (use a high-volume token like WETH/USDC)
    logs_token_contract: str
    logs_range_small: int = 1000
    logs_range_large: int = 10000
    archival_logs_start_block: int


class TestCase(BaseModel):
    """Definition of a single test case."""
    id: int
    name: str
    category: TestCategory
    label: TestLabel
    enabled: bool = True
    rpc_method: str
    rpc_params: list[Any] = Field(default_factory=list)
    concurrency: int | None = None  # For load tests


class BenchmarkConfig(BaseModel):
    """Configuration for a benchmark run.

    Tests are run in ROUNDS to allow proper cache warming:
    - Round 1: All tests run once (cold - cache miss expected)
    - Round 2+: All tests run again (warm - cache hit expected)

    This gives distributed caches time to propagate between rounds.
    """
    iteration_mode: IterationMode = IterationMode.STANDARD
    timeout_seconds: int = 30
    delay_ms: int = 100  # Delay between individual requests
    inter_round_delay_ms: int = 2000  # Delay between rounds (allows cache propagation)
    categories: list[TestCategory] = Field(
        default_factory=lambda: [TestCategory.SIMPLE, TestCategory.MEDIUM, TestCategory.COMPLEX, TestCategory.LOAD]
    )
    labels: list[TestLabel] = Field(
        default_factory=lambda: [TestLabel.LATEST, TestLabel.ARCHIVAL]
    )
    test_params: TestParams
    enabled_test_ids: list[int] | None = None  # If None, all tests enabled

    # Load test specific
    load_concurrency_simple: int = 50
    load_concurrency_medium: int = 50
    load_concurrency_complex: int = 25

    def get_round_count(self) -> int:
        """Get the number of rounds based on mode."""
        return {
            IterationMode.QUICK: 2,      # 1 cold + 1 warm
            IterationMode.STANDARD: 3,   # 1 cold + 2 warm
            IterationMode.THOROUGH: 5,   # 1 cold + 4 warm
            IterationMode.STATISTICAL: 10,  # 1 cold + 9 warm
        }[self.iteration_mode]


# ============================================================================
# Benchmark Job
# ============================================================================

class BenchmarkJob(BaseModel):
    """A benchmark job."""
    id: str
    chain_id: int
    chain_name: str
    status: JobStatus = JobStatus.PENDING
    config: BenchmarkConfig
    providers: list[Provider]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    error_message: str | None = None


class JobCreate(BaseModel):
    """Request to create a benchmark job."""
    chain_id: int
    providers: list[ProviderCreate]
    config: BenchmarkConfig


# ============================================================================
# Results
# ============================================================================

class TestResult(BaseModel):
    """Result of a single test iteration."""
    job_id: str
    provider_id: str
    test_id: int
    test_name: str
    category: TestCategory
    label: TestLabel
    iteration: int
    iteration_type: IterationType
    response_time_ms: float | None = None
    success: bool
    error_type: str | None = None
    http_status: int | None = None
    response_size_bytes: int | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LoadTestResult(BaseModel):
    """Result of a load test."""
    job_id: str
    provider_id: str
    test_id: int
    test_name: str
    method: str
    concurrency: int
    total_time_ms: float
    min_ms: float
    max_ms: float
    avg_ms: float
    p50_ms: float
    p95_ms: float
    success_count: int
    error_count: int
    success_rate: float
    throughput_rps: float
    errors: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AggregatedResult(BaseModel):
    """Aggregated result for a test across iterations."""
    provider_id: str
    test_id: int
    test_name: str
    category: TestCategory
    label: TestLabel
    count: int
    success_rate: float

    # Core metrics
    cold_ms: float
    warm_ms: float
    cache_speedup: float

    # Extended metrics (when iterations >= 5)
    mean_ms: float | None = None
    median_ms: float | None = None
    min_ms: float | None = None
    max_ms: float | None = None
    std_dev_ms: float | None = None

    # Statistical metrics (when iterations >= 25)
    p90_ms: float | None = None
    p95_ms: float | None = None


class ArchiveComparison(BaseModel):
    """Comparison between latest and archival performance."""
    provider_id: str
    test_base_name: str
    category: TestCategory
    latest_mean_ms: float
    archival_mean_ms: float
    archive_penalty_ms: float
    archive_penalty_ratio: float


class LoadDegradation(BaseModel):
    """Comparison between sequential and load test performance."""
    provider_id: str
    method: str
    sequential_avg_ms: float
    load_avg_ms: float
    degradation_factor: float


# ============================================================================
# SSE Events
# ============================================================================

class SSEEvent(BaseModel):
    """Server-Sent Event."""
    event: str
    data: dict[str, Any]


# ============================================================================
# Export
# ============================================================================

class BenchmarkExport(BaseModel):
    """Full export of benchmark results."""
    metadata: dict[str, Any]
    chain: dict[str, Any]
    job: dict[str, Any]
    providers: list[dict[str, Any]]
    test_params: dict[str, Any]
    tests_executed: list[dict[str, Any]]
    results: dict[str, Any]
