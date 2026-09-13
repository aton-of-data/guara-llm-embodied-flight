# SPDX-License-Identifier: Apache-2.0
"""Host-side parameter schema and digest (G-K8).

The switching kernel does not parse YAML. This module validates a ROS 2
parameter file against config/rta_params.schema.json and hashes the core
fields with the same FNV-1a 64 encoding as core/src/abi.cpp, so a host can
record the digest next to GUARA_CORE_VERSION without linking the kernel.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from . import doctor

SCHEMA_FILE = Path("config") / "rta_params.schema.json"

# Header order of guara_params. A change here without a matching C change is a
# failed test (scripts/tests/test_params.py).
CORE_KEYS = (
    "core.tau_daa_s",
    "core.tau_gf_s",
    "core.h_daa_s",
    "core.h_gf_s",
    "core.dwell_s",
    "core.n_max",
    "core.window_s",
    "core.return_enabled",
    "core.escalation_enabled",
    "core.escalation_s",
)

FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211
SWITCH_HISTORY_CAPACITY = 32

# Default parameter-set digest (LE FNV-1a-64). Locked by core/test/test_abi_digest.c.
DEFAULT_DIGEST_HEX = "c9f82e52ea1d4469"


class ParamsError(Exception):
    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class ParamSet:
    source: str
    core: dict[str, float | int | bool]
    digest_hex: str
    core_version: str
    abi_version: str


def _schema_path(root: Path) -> Path:
    return root / SCHEMA_FILE


def schema(root: Path | None = None) -> dict:
    base = root if root is not None else doctor.repo_root()
    if base is None:
        raise ParamsError("clone", "versions.env not found; run from a clone")
    path = _schema_path(base)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ParamsError("schema", f"cannot read {path}: {exc}") from exc


def versions_from_header(root: Path) -> tuple[str, str]:
    header = root / "core" / "include" / "guara" / "guara.h"
    text = header.read_text(encoding="utf-8")
    core = re.search(r'#define\s+GUARA_CORE_VERSION\s+"([^"]+)"', text)
    abi = re.search(r'#define\s+GUARA_ABI_VERSION\s+"([^"]+)"', text)
    if core is None or abi is None:
        raise ParamsError("header", f"{header}: missing version macros")
    return core.group(1), abi.group(1)


def _fnv1a(h: int, data: bytes) -> int:
    for b in data:
        h ^= b
        h = (h * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return h


def digest_core(core: dict[str, float | int | bool]) -> bytes:
    """FNV-1a-64 over IEEE-754 little-endian fields in CORE_KEYS order."""
    h = FNV_OFFSET
    h = _fnv1a(h, struct.pack("<d", float(core["core.tau_daa_s"])))
    h = _fnv1a(h, struct.pack("<d", float(core["core.tau_gf_s"])))
    h = _fnv1a(h, struct.pack("<d", float(core["core.h_daa_s"])))
    h = _fnv1a(h, struct.pack("<d", float(core["core.h_gf_s"])))
    h = _fnv1a(h, struct.pack("<d", float(core["core.dwell_s"])))
    n_max = int(core["core.n_max"])
    if n_max < 1 or n_max > SWITCH_HISTORY_CAPACITY:
        raise ParamsError("range", f"core.n_max={n_max} is outside 1..{SWITCH_HISTORY_CAPACITY}")
    h = _fnv1a(h, struct.pack("<H", n_max))
    h = _fnv1a(h, struct.pack("<d", float(core["core.window_s"])))
    h = _fnv1a(h, bytes([1 if core["core.return_enabled"] else 0]))
    h = _fnv1a(h, bytes([1 if core["core.escalation_enabled"] else 0]))
    h = _fnv1a(h, struct.pack("<d", float(core["core.escalation_s"])))
    return h.to_bytes(8, "little")


def load(path: Path | str, root: Path | None = None) -> ParamSet:
    import jsonschema
    import yaml

    path = Path(path)
    base = root if root is not None else doctor.repo_root()
    if base is None:
        raise ParamsError("clone", "versions.env not found; run from a clone")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ParamsError("yaml", f"{path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ParamsError("yaml", f"{path}: expected a mapping")
    try:
        jsonschema.validate(raw, schema(base), cls=jsonschema.Draft202012Validator)
    except jsonschema.ValidationError as e:
        loc = "/".join(str(p) for p in e.absolute_path) or path.name
        raise ParamsError("schema", f"{loc}: {e.message}") from None
    except jsonschema.SchemaError as e:  # pragma: no cover
        raise ParamsError("schema", f"schema file is invalid: {e.message}") from None

    params = raw["guara_rta"]["ros__parameters"]
    core = {k: params[k] for k in CORE_KEYS}
    digest_hex = digest_core(core).hex()
    core_version, abi_version = versions_from_header(base)
    return ParamSet(
        source=str(path),
        core=core,
        digest_hex=digest_hex,
        core_version=core_version,
        abi_version=abi_version,
    )


def run(argv: list[str] | None = None, out=sys.stdout, err=sys.stderr) -> int:
    parser = argparse.ArgumentParser(
        prog="guara params",
        description="Validate an arbiter parameter file and print its core digest.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="schema-validate a YAML file and print the digest")
    check.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    if args.cmd != "check":
        parser.error(f"unknown command {args.cmd}")
        return 1
    try:
        for f in args.files:
            ps = load(f)
            print(
                f"PASS params: {ps.source} digest={ps.digest_hex} "
                f"core={ps.core_version} abi={ps.abi_version}",
                file=out,
            )
    except ParamsError as exc:
        print(f"FAIL params: {exc}", file=err)
        return 1
    return 0
