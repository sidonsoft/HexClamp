#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "agents"))

from store import bootstrap_runtime_state  # noqa: E402


if __name__ == "__main__":
    created = bootstrap_runtime_state()
    print(json.dumps({"bootstrapped": created}, indent=2))
