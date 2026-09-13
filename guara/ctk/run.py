# SPDX-License-Identifier: Apache-2.0
"""Conformance kit runner (M19). Ports other than the Python reference are later."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

from .. import doctor, params
from .reference import Inputs, Params, ReferenceCore

NOTE = (
    "Conformance is necessary and not sufficient: this run demonstrates "
    "behavioural equivalence to the published vectors and nothing about the "
    "safety of the system that contains it."
)


class CtkError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _time(value) -> float:
    if value is None:
        return math.inf
    return float(value)


def _inputs(raw: dict) -> Inputs:
    return Inputs(
        t_s=float(raw["t_s"]),
        in_charge=int(raw["in_charge"]),
        owned_mode_active=int(raw["owned_mode_active"]),
        t_daa_s=_time(raw.get("t_daa_s")),
        t_gf_s=_time(raw.get("t_gf_s")),
        monitor_violation=int(raw.get("monitor_violation", 0)),
        monitor_action=int(raw.get("monitor_action", 1)),
        input_invalid=int(raw.get("input_invalid", 0)),
        cf_intent_unsafe=int(raw.get("cf_intent_unsafe", 0)),
    )


def _params(overlay: dict | None) -> Params:
    p = Params()
    if not overlay:
        return p
    for key, val in overlay.items():
        if not hasattr(p, key):
            raise CtkError(f"unknown param {key}")
        setattr(p, key, val)
    return p


def _check(vec_id: str, step_i: int, expect: dict, got) -> None:
    mapping = {
        "state": got.state,
        "recovery": got.recovery,
        "command": got.command,
        "transition": got.transition,
        "unsafe_causes": got.unsafe_causes,
    }
    for key, want in expect.items():
        if key not in mapping:
            continue
        if mapping[key] != want:
            raise CtkError(
                f"{vec_id} step {step_i}: {key} got {mapping[key]} want {want}"
            )


def run_vectors(path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    n_ok = 0
    for vec in data:
        core = ReferenceCore(params=_params(vec.get("params")))
        vec_id = vec["id"]
        for i, step in enumerate(vec["steps"]):
            if step.get("action") == "latch":
                got = core.latch_on_actuation_failure(float(step["t_s"]))
            else:
                got = core.step(_inputs(step["in"]))
            _check(vec_id, i, step.get("expect") or {}, got)
        n_ok += 1
    return n_ok, len(data)


def default_vectors(root: Path) -> Path:
    return root / "core" / "conformance" / "vectors" / "spec_s3.json"


def run(argv: list[str] | None = None, out=sys.stdout, err=sys.stderr) -> int:
    parser = argparse.ArgumentParser(
        prog="guara ctk",
        description="Run published decision vectors against a port.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    runp = sub.add_parser("run", help="execute vectors and print a report")
    runp.add_argument("--port", required=True, choices=("python",))
    runp.add_argument("--vectors", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.cmd != "run":
        parser.error(f"unknown command {args.cmd}")
        return 1

    root = doctor.repo_root()
    if root is None:
        print("FAIL ctk: versions.env not found; run from a clone", file=err)
        return 1
    vectors = args.vectors if args.vectors is not None else default_vectors(root)
    try:
        n_ok, n_all = run_vectors(vectors)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, CtkError) as exc:
        print(f"FAIL ctk: {exc}", file=err)
        return 1

    digest = hashlib.sha256(vectors.read_bytes()).hexdigest()
    core_ver, abi_ver = params.versions_from_header(root)
    print(f"port           python-reference", file=out)
    print(f"core           {core_ver}", file=out)
    print(f"abi            {abi_ver}", file=out)
    print(f"host           {sys.platform}", file=out)
    print(f"arch           {platform.machine() or 'unknown'}", file=out)
    print(f"vectors        {vectors.name}", file=out)
    print(f"vectors_sha256 {digest}", file=out)
    print(f"result         PASS {n_ok}/{n_all}", file=out)
    print(f"note           {NOTE}", file=out)
    return 0
