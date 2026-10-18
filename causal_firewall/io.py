"""Load frozen Study 0 configuration files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_policy(path: str | Path) -> dict[str, Any]:
    """Load JSON-compatible YAML without adding a third-party dependency.

    JSON is a strict subset of YAML 1.2, so the distributed access_policy.yaml
    remains a valid YAML document while being readable by the standard library.
    """

    return load_json(path)

