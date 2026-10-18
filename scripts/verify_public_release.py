#!/usr/bin/env python3
"""Verify hashes, row counts, and privacy exclusions in the public release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from causal_firewall.public_release import verify_public_release


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir", type=Path, default=ROOT / "data" / "CF-P1-001"
    )
    args = parser.parse_args()
    result = verify_public_release(args.data_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
