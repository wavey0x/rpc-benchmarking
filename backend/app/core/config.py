"""Application configuration."""

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class Settings(BaseModel):
    """Application settings."""

    # Application
    app_name: str = "RPC Benchmarker"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server
    host: str = "127.0.0.1"
    port: int = 8420

    # Data directory
    data_dir: Path = Path.home() / ".rpc-benchmarker"

    # Defaults
    default_timeout_seconds: int = 30
    default_delay_ms: int = 100
    default_iteration_mode: str = "standard"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "benchmarks.db"

    @property
    def chains_dir(self) -> Path:
        return self.data_dir / "chains"

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"

    def ensure_data_dir(self) -> None:
        """Ensure data directory and subdirectories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chains_dir.mkdir(parents=True, exist_ok=True)

    def load_app_config(self) -> dict[str, Any]:
        """Load application config from file."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                return json.load(f)
        return {}

    def save_app_config(self, config: dict[str, Any]) -> None:
        """Save application config to file."""
        self.ensure_data_dir()
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)


# Global settings instance
settings = Settings()

# Override from environment
if os.getenv("RPC_BENCHMARKER_DEBUG"):
    settings.debug = True
if os.getenv("RPC_BENCHMARKER_HOST"):
    settings.host = os.getenv("RPC_BENCHMARKER_HOST")
if os.getenv("RPC_BENCHMARKER_PORT"):
    settings.port = int(os.getenv("RPC_BENCHMARKER_PORT"))
if os.getenv("RPC_BENCHMARKER_DATA_DIR"):
    settings.data_dir = Path(os.getenv("RPC_BENCHMARKER_DATA_DIR"))
