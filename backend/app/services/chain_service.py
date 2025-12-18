"""Chain configuration management service."""

import json
import shutil
from pathlib import Path
from typing import Any

from ..core.config import settings
from ..models import ChainConfig


class ChainService:
    """Service for managing chain configurations."""

    def __init__(self):
        self.chains_dir = settings.chains_dir
        self.presets_dir = Path(__file__).parent.parent.parent / "presets" / "chains"

    def ensure_presets_loaded(self) -> None:
        """Ensure preset chain configs are copied to user data directory."""
        settings.ensure_data_dir()

        # Copy presets if they don't exist
        if self.presets_dir.exists():
            for preset_file in self.presets_dir.glob("*.json"):
                target_file = self.chains_dir / preset_file.name
                if not target_file.exists():
                    shutil.copy(preset_file, target_file)

    def list_chains(self) -> list[ChainConfig]:
        """List all available chain configurations."""
        self.ensure_presets_loaded()
        chains = []

        for chain_file in self.chains_dir.glob("*.json"):
            try:
                with open(chain_file) as f:
                    data = json.load(f)
                    chains.append(ChainConfig(**data))
            except Exception:
                # Skip invalid chain files
                continue

        return sorted(chains, key=lambda c: c.chain_id)

    def get_chain(self, chain_id: int) -> ChainConfig | None:
        """Get a chain configuration by ID."""
        self.ensure_presets_loaded()

        for chain_file in self.chains_dir.glob("*.json"):
            try:
                with open(chain_file) as f:
                    data = json.load(f)
                    if data.get("chain_id") == chain_id:
                        return ChainConfig(**data)
            except Exception:
                continue

        return None

    def save_chain(self, chain: ChainConfig) -> None:
        """Save a chain configuration."""
        settings.ensure_data_dir()

        # Determine filename
        if chain.is_preset:
            filename = f"{chain.chain_name.lower().replace(' ', '_')}.json"
        else:
            filename = f"custom_{chain.chain_id}.json"

        filepath = self.chains_dir / filename

        with open(filepath, "w") as f:
            json.dump(chain.model_dump(mode="json"), f, indent=2, default=str)

    def delete_chain(self, chain_id: int) -> bool:
        """Delete a custom chain configuration. Returns False if preset."""
        chain = self.get_chain(chain_id)
        if chain is None:
            return False

        if chain.is_preset:
            return False  # Cannot delete presets

        # Find and delete the file
        for chain_file in self.chains_dir.glob(f"custom_{chain_id}.json"):
            chain_file.unlink()
            return True

        return False

    def create_custom_chain(self, chain_data: dict[str, Any]) -> ChainConfig:
        """Create a new custom chain configuration."""
        chain_data["is_preset"] = False
        chain = ChainConfig(**chain_data)
        self.save_chain(chain)
        return chain

    def update_chain(self, chain_id: int, updates: dict[str, Any]) -> ChainConfig | None:
        """Update a chain configuration."""
        chain = self.get_chain(chain_id)
        if chain is None:
            return None

        # Apply updates
        chain_data = chain.model_dump()
        chain_data.update(updates)
        chain_data["chain_id"] = chain_id  # Ensure chain_id doesn't change

        updated_chain = ChainConfig(**chain_data)
        self.save_chain(updated_chain)
        return updated_chain


# Global chain service instance
chain_service = ChainService()
