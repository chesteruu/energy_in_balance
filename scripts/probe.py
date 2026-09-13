#!/usr/bin/env python3
"""Log in to Energy in Balance and print the live snapshot.

Usage:
  export EIB_USERNAME='you@example.com'
  export EIB_PASSWORD='secret'
  python scripts/probe.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from custom_components.energy_in_balance.api import EnergyInBalanceApi  # noqa: E402


async def main() -> int:
    username = os.environ.get("EIB_USERNAME")
    password = os.environ.get("EIB_PASSWORD")
    if not username or not password:
        print("Set EIB_USERNAME and EIB_PASSWORD first.", file=sys.stderr)
        return 2

    api = EnergyInBalanceApi(username, password)
    try:
        snapshot = await api.async_update(force_slow=True)
    finally:
        await api.async_close()

    for key, value in asdict(snapshot).items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
