#!/usr/bin/env python3
"""Development run script for RPC Benchmarker."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.app.main import main

if __name__ == "__main__":
    main()
