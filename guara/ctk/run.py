# SPDX-License-Identifier: Apache-2.0
"""Conformance kit runner (M19). Python reference and SIL (C ABI) ports."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .. import doctor, params
from .gateway import GatewayLimits, ReferenceGateway
from .monitors import MonitorEval, ReferenceMonitor
from .reference import Inputs, Params, ReferenceCore
from .sil import SilCore, SilGateway, SilMonitor, find_cabi, load_cabi

NOTE = (
    "Conformance is necessary and not sufficient: this run demonstrates "
    "behavioural equivalence to the published vectors and nothing about the "
    "safety of the system that contains it."
)
BENCH_NOTE = (
    "max_step_ns is the worst observed wall-clock time of one kernel entry "
    "on this host; it is measured, not a bound (G-K4 stays open until a WCET tool)."
)


@dataclass
class VectorRun:
    n_ok: int
    n_all: int
    n_ops: int
    max_step_ns: int


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


def _num(value) -> float:
    if value is None:
        return math.nan
    if value == "nan":
        return math.nan
    if value == "inf":
        return math.inf
    return float(value)


def _looks_like_gateway(data: list) -> bool:
    if not data:
        return False
    ops = {step.get("op") for step in (data[0].get("steps") or [])}
    return bool(ops & {"setpoint", "compute"})


def _looks_like_monitor(data: list) -> bool:
    if not data:
        return False
    ops = {step.get("op") for step in (data[0].get("steps") or [])}
    return bool(ops & {"expect", "observe", "evaluate"})


def _mark(stats: VectorRun, t0: int) -> None:
    dt = time.perf_counter_ns() - t0
    stats.n_ops += 1
    if dt > stats.max_step_ns:
        stats.max_step_ns = dt


def _run_spec_vectors(data: list, make_core) -> VectorRun:
    stats = VectorRun(n_ok=0, n_all=len(data), n_ops=0, max_step_ns=0)
    for vec in data:
        core = make_core(_params(vec.get("params")))
        vec_id = vec["id"]
        for i, step in enumerate(vec["steps"]):
            t0 = time.perf_counter_ns()
            if step.get("action") == "latch":
                got = core.latch_on_actuation_failure(float(step["t_s"]))
            else:
                got = core.step(_inputs(step["in"]))
            _mark(stats, t0)
            _check(vec_id, i, step.get("expect") or {}, got)
        stats.n_ok += 1
    return stats


def _check_gateway(vec_id: str, step_i: int, expect: dict, got) -> None:
    mapping = {
        "forwarding_cf": got.forwarding_cf,
        "vx": got.vx,
        "vz": got.vz,
        "rejected_stamp": got.rejected_stamp,
        "rejected_non_finite": got.rejected_non_finite,
        "rejected_yaw": got.rejected_yaw,
        "rejected_guard": got.rejected_guard,
        "clamped": got.clamped,
    }
    for key, want in expect.items():
        if key == "yaw":
            if want is None:
                if not math.isnan(got.yaw):
                    raise CtkError(f"{vec_id} step {step_i}: yaw got {got.yaw} want nan")
            elif abs(got.yaw - float(want)) > 1e-4:
                raise CtkError(f"{vec_id} step {step_i}: yaw got {got.yaw} want {want}")
            continue
        if key == "speed_h":
            speed = math.hypot(got.vx, got.vy)
            if abs(speed - float(want)) > 1e-4:
                raise CtkError(f"{vec_id} step {step_i}: speed_h got {speed} want {want}")
            continue
        if key not in mapping:
            continue
        got_v = mapping[key]
        if isinstance(want, (int, float)) and isinstance(got_v, float):
            if abs(got_v - float(want)) > 1e-4:
                raise CtkError(f"{vec_id} step {step_i}: {key} got {got_v} want {want}")
        elif got_v != want:
            raise CtkError(f"{vec_id} step {step_i}: {key} got {got_v} want {want}")


def _run_gateway_vectors(data: list, make_gateway) -> VectorRun:
    stats = VectorRun(n_ok=0, n_all=len(data), n_ops=0, max_step_ns=0)
    for vec in data:
        limits = GatewayLimits()
        if "timeout_s" in vec:
            limits.cf_timeout_s = float(vec["timeout_s"])
        gw = make_gateway(limits)
        vec_id = vec["id"]
        for i, step in enumerate(vec["steps"]):
            op = step["op"]
            t0 = time.perf_counter_ns()
            if op == "state":
                gw.on_core_state(int(step["state"]), float(step["t_s"]))
                _mark(stats, t0)
            elif op == "guard":
                gw.set_guard(int(step["mode"]))
                _mark(stats, t0)
            elif op == "setpoint":
                v = tuple(_num(x) for x in step["v"])
                gw.on_cf_setpoint(float(step["t_recv_s"]), float(step["stamp_s"]), v,
                                  _num(step.get("yaw")))
                _mark(stats, t0)
            elif op == "compute":
                got = gw.compute(float(step["t_s"]))
                _mark(stats, t0)
                _check_gateway(vec_id, i, step.get("expect") or {}, got)
            else:
                raise CtkError(f"{vec_id} step {i}: unknown op {op}")
        stats.n_ok += 1
    return stats


def _check_monitor(vec_id: str, step_i: int, expect: dict, got: MonitorEval) -> None:
    mapping = {
        "violation": got.violation,
        "action": got.action,
        "invalid": got.invalid,
        "first_violating_id": got.first_violating_id,
        "first_invalid_id": got.first_invalid_id,
    }
    for key, want in expect.items():
        if key not in mapping:
            continue
        if mapping[key] != want:
            raise CtkError(f"{vec_id} step {step_i}: {key} got {mapping[key]!r} want {want!r}")


def _run_monitor_vectors(data: list, make_monitor) -> VectorRun:
    stats = VectorRun(n_ok=0, n_all=len(data), n_ops=0, max_step_ns=0)
    for vec in data:
        table = make_monitor(float(vec.get("max_age_s", 0.5)))
        vec_id = vec["id"]
        for i, step in enumerate(vec["steps"]):
            op = step["op"]
            t0 = time.perf_counter_ns()
            if op == "expect":
                table.expect(step["id"])
                _mark(stats, t0)
            elif op == "observe":
                acc = table.observe(
                    step["id"],
                    int(step.get("class", 1)),
                    int(step.get("action", 0)),
                    int(step.get("violated", 0)),
                    int(step.get("complete", 1)),
                    float(step["t_recv_s"]),
                )
                _mark(stats, t0)
                if "expect_accept" in step and acc != int(step["expect_accept"]):
                    raise CtkError(
                        f"{vec_id} step {i}: accept got {acc} want {step['expect_accept']}"
                    )
            elif op == "evaluate":
                got = table.evaluate(float(step["t_s"]))
                _mark(stats, t0)
                _check_monitor(vec_id, i, step.get("expect") or {}, got)
            else:
                raise CtkError(f"{vec_id} step {i}: unknown op {op}")
        stats.n_ok += 1
    return stats


def run_vectors(path: Path, make_core=None, make_gateway=None, make_monitor=None) -> VectorRun:
    if make_core is None:
        make_core = lambda params: ReferenceCore(params=params)
    if make_gateway is None:
        make_gateway = lambda limits: ReferenceGateway(limits=limits)
    if make_monitor is None:
        make_monitor = lambda max_age: ReferenceMonitor(max_age_s=max_age)
    data = json.loads(path.read_text(encoding="utf-8"))
    if _looks_like_monitor(data):
        return _run_monitor_vectors(data, make_monitor)
    if _looks_like_gateway(data):
        return _run_gateway_vectors(data, make_gateway)
    return _run_spec_vectors(data, make_core)


def vector_files(path: Path) -> list[Path]:
    if path.is_dir():
        files = sorted(p for p in path.glob("*.json") if p.is_file())
        if not files:
            raise CtkError(f"no JSON vectors in {path}")
        return files
    return [path]


def default_vectors(root: Path) -> Path:
    return root / "core" / "conformance" / "vectors" / "spec_s3.json"


def default_vector_dir(root: Path) -> Path:
    return root / "core" / "conformance" / "vectors"


def _report_lines(port: str, core_ver: str, abi_ver: str, digest: str,
                  vectors_name: str, n_ok: int, n_all: int) -> list[str]:
    return [
        f"port           {port}",
        f"core           {core_ver}",
        f"abi            {abi_ver}",
        f"host           {sys.platform}",
        f"arch           {platform.machine() or 'unknown'}",
        f"vectors        {vectors_name}",
        f"vectors_sha256 {digest}",
        f"result         PASS {n_ok}/{n_all}",
        f"note           {NOTE}",
    ]


def _bench_lines(port: str, core_ver: str, abi_ver: str, names: str,
                 digest: str, stats: VectorRun) -> list[str]:
    return [
        f"port           {port}",
        f"core           {core_ver}",
        f"abi            {abi_ver}",
        f"host           {sys.platform}",
        f"arch           {platform.machine() or 'unknown'}",
        f"vectors        {names}",
        f"vectors_sha256 {digest}",
        f"n_ops          {stats.n_ops}",
        f"max_step_ns    {stats.max_step_ns}",
        f"result         PASS {stats.n_ok}/{stats.n_all}",
        f"note           {BENCH_NOTE}",
    ]


def write_report(path: Path, body: str) -> None:
    if path.suffix:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return
    path.mkdir(parents=True, exist_ok=True)
    (path / "report.txt").write_text(body, encoding="utf-8")


def _port_factory(root: Path, port: str, lib_arg: Path | None, err):
    make_core = lambda params: ReferenceCore(params=params)
    make_gateway = lambda limits: ReferenceGateway(limits=limits)
    make_monitor = lambda max_age: ReferenceMonitor(max_age_s=max_age)
    port_name = "python-reference"
    if port == "sil":
        lib_path = find_cabi(root, lib_arg)
        if lib_path is None:
            print("FAIL ctk: C ABI library not found (build core/ or pass --lib)", file=err)
            return None
        try:
            lib = load_cabi(lib_path)
        except OSError as exc:
            print(f"FAIL ctk: cannot load {lib_path}: {exc}", file=err)
            return None
        make_core = lambda params, _lib=lib: SilCore(_lib, params)
        make_gateway = lambda limits, _lib=lib: SilGateway(_lib, limits)
        make_monitor = lambda max_age, _lib=lib: SilMonitor(_lib, max_age)
        port_name = "sil-cabi"
    return port_name, make_core, make_gateway, make_monitor


def run(argv: list[str] | None = None, out=sys.stdout, err=sys.stderr) -> int:
    parser = argparse.ArgumentParser(
        prog="guara ctk",
        description="Run published decision vectors against a port.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    runp = sub.add_parser("run", help="execute vectors and print a report")
    runp.add_argument("--port", required=True, choices=("python", "sil"))
    runp.add_argument("--vectors", type=Path, default=None)
    runp.add_argument("--lib", type=Path, default=None,
                      help="shared C ABI library for --port sil (or set GUARA_CABI)")
    runp.add_argument("--report", type=Path, default=None,
                      help="write the report to a file, or to report.txt in this directory")
    benchp = sub.add_parser(
        "bench",
        help="record worst observed step time (measured, not a bound)",
    )
    benchp.add_argument("--port", required=True, choices=("python", "sil"))
    benchp.add_argument("--vectors", type=Path, default=None)
    benchp.add_argument("--lib", type=Path, default=None)
    benchp.add_argument("--report", type=Path, required=True,
                        help="write the bench record (directory or file)")
    args = parser.parse_args(argv)

    root = doctor.repo_root()
    if root is None:
        print("FAIL ctk: versions.env not found; run from a clone", file=err)
        return 1
    factory = _port_factory(root, args.port, args.lib, err)
    if factory is None:
        return 1
    port_name, make_core, make_gateway, make_monitor = factory

    if args.cmd == "run":
        vectors = args.vectors if args.vectors is not None else default_vectors(root)
        try:
            stats = run_vectors(vectors, make_core, make_gateway, make_monitor)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, CtkError) as exc:
            print(f"FAIL ctk: {exc}", file=err)
            return 1
        digest = hashlib.sha256(vectors.read_bytes()).hexdigest()
        core_ver, abi_ver = params.versions_from_header(root)
        body = "\n".join(_report_lines(
            port_name, core_ver, abi_ver, digest, vectors.name, stats.n_ok, stats.n_all,
        )) + "\n"
        print(body, file=out, end="")
        if args.report is not None:
            try:
                write_report(args.report, body)
            except OSError as exc:
                print(f"FAIL ctk: cannot write report: {exc}", file=err)
                return 1
        return 0

    if args.cmd == "bench":
        vectors = args.vectors if args.vectors is not None else default_vector_dir(root)
        try:
            files = vector_files(vectors)
            acc = VectorRun(n_ok=0, n_all=0, n_ops=0, max_step_ns=0)
            hasher = hashlib.sha256()
            names: list[str] = []
            for f in files:
                hasher.update(f.read_bytes())
                names.append(f.name)
                one = run_vectors(f, make_core, make_gateway, make_monitor)
                acc.n_ok += one.n_ok
                acc.n_all += one.n_all
                acc.n_ops += one.n_ops
                if one.max_step_ns > acc.max_step_ns:
                    acc.max_step_ns = one.max_step_ns
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, CtkError) as exc:
            print(f"FAIL ctk: {exc}", file=err)
            return 1
        core_ver, abi_ver = params.versions_from_header(root)
        body = "\n".join(_bench_lines(
            port_name, core_ver, abi_ver, ",".join(names), hasher.hexdigest(), acc,
        )) + "\n"
        print(body, file=out, end="")
        try:
            write_report(args.report, body)
        except OSError as exc:
            print(f"FAIL ctk: cannot write report: {exc}", file=err)
            return 1
        return 0

    parser.error(f"unknown command {args.cmd}")
    return 1
