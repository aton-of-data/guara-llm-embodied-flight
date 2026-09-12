# SPDX-License-Identifier: Apache-2.0
"""Load a git-ignored .env without ever printing a value (ADR 0013 decision 7).

The harness records only the *name* of the variable it read. Existing environment
values win, so a caller who already exported a key is not silently overridden.
"""
from __future__ import annotations

import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = ROOT / ".env"


def load_env_file(path: pathlib.Path | None = None) -> list[str]:
    """Load KEY=VALUE lines. Returns the names that were newly set. Never returns values."""
    path = DEFAULT_ENV_FILE if path is None else pathlib.Path(path)
    loaded: list[str] = []
    if not path.is_file():
        return loaded
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or not key.isidentifier():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded
