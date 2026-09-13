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
from dataclasses import dataclass, replace
from pathlib import Path

from .. import doctor, params
from .geofence import GfParams, GfPrediction, GfState, ReferenceGeofence
from .gateway import GatewayLimits, ReferenceGateway
from .monitors import MonitorEval, ReferenceMonitor
from .reference import Inputs, Params, ReferenceCore
from .sil import SilCore, SilGateway, SilGeofence, SilMonitor, find_cabi, load_cabi

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


def _params(overlay: dict | None, base: Params | None = None) -> Params:
    p = Params() if base is None else replace(base)
    if not overlay:
        return p
    for key, val in overlay.items():
        if not hasattr(p, key):
            raise CtkError(f"unknown param {key}")
        setattr(p, key, val)
    return p


def _known(vec_id: str, step_i: int, key: str, known) -> None:
    """Raise unless `key` is a field this vector set compares."""
    if key not in known:
        raise CtkError(
            f"{vec_id} step {step_i}: unknown expectation {key!r}; "
            f"this vector set compares {', '.join(sorted(known))}"
        )


def _check(vec_id: str, step_i: int, expect: dict, got) -> None:
    mapping = {
        "state": got.state,
        "recovery": got.recovery,
        "command": got.command,
        "transition": got.transition,
        "unsafe_causes": got.unsafe_causes,
    }
    for key, want in expect.items():
        _known(vec_id, step_i, key, mapping)
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


def _looks_like_geofence(data: list) -> bool:
    if not data:
        return False
    return "vertices" in data[0] or bool(
        {step.get("op") for step in (data[0].get("steps") or [])} & {"predict", "project", "classify", "check_params"}
    )


def _gf_params(raw: dict | None, base: GfParams | None = None) -> GfParams:
    p = GfParams() if base is None else replace(base)
    if not raw:
        return p
    for key in ("a_brake_h_m_s2", "a_brake_v_m_s2", "k_sigma", "v_min_m_s", "horizon_s"):
        if key in raw:
            setattr(p, key, float(raw[key]))
    return p


def _gf_state(step: dict) -> GfState:
    return GfState(
        north_m=float(step.get("north_m", 0.0)),
        east_m=float(step.get("east_m", 0.0)),
        altitude_m=float(step.get("altitude_m", 0.0)),
        vn_m_s=float(step.get("vn_m_s", 0.0)),
        ve_m_s=float(step.get("ve_m_s", 0.0)),
        climb_rate_m_s=float(step.get("climb_rate_m_s", 0.0)),
        eph_m=float(step.get("eph_m", 0.0)),
        epv_m=float(step.get("epv_m", 0.0)),
    )


def _check_geofence(vec_id: str, step_i: int, expect: dict, got: GfPrediction) -> None:
    mapping = {
        "t_gf_s": got.t_gf_s,
        "t_horizontal_s": got.t_horizontal_s,
        "t_vertical_s": got.t_vertical_s,
        "inside": got.inside,
        "exit_distance_m": got.exit_distance_m,
    }
    for key, want in expect.items():
        _known(vec_id, step_i, key, mapping)
        got_v = mapping[key]
        if key == "inside":
            if int(got_v) != int(want):
                raise CtkError(f"{vec_id} step {step_i}: {key} got {got_v} want {want}")
            continue
        want_n = _num(want)
        if math.isinf(want_n) or math.isinf(got_v):
            if not (math.isinf(want_n) and math.isinf(got_v) and (want_n > 0) == (got_v > 0)):
                raise CtkError(f"{vec_id} step {step_i}: {key} got {got_v} want {want}")
            continue
        tol = 1e-6 if key == "exit_distance_m" else 0.05
        if abs(got_v - want_n) > tol:
            raise CtkError(f"{vec_id} step {step_i}: {key} got {got_v} want {want}")


def _check_project(vec_id: str, step_i: int, expect: dict, north_m: float, east_m: float) -> None:
    mapping = {"north_m": north_m, "east_m": east_m}
    for key, want in expect.items():
        _known(vec_id, step_i, key, mapping)
        got_v = mapping[key]
        tol = 1e-6 if abs(float(want)) < 1e-9 else 0.01
        if abs(got_v - float(want)) > tol:
            raise CtkError(f"{vec_id} step {step_i}: {key} got {got_v} want {want}")


def _run_geofence_vectors(data: list, make_geofence) -> VectorRun:
    stats = VectorRun(n_ok=0, n_all=len(data), n_ops=0, max_step_ns=0)
    for vec in data:
        table = make_geofence()
        if "vertices" in vec:
            table.configure(
                [_num(x) for x in vec["vertices"]],
                float(vec.get("alt_min_m", 0.0)),
                float(vec.get("alt_max_m", 1.0e9)),
            )
        params = _gf_params(vec.get("params"))
        vec_id = vec["id"]
        for i, step in enumerate(vec["steps"]):
            op = step.get("op")
            t0 = time.perf_counter_ns()
            if op == "predict":
                got = table.predict(params, _gf_state(step))
                _mark(stats, t0)
                _check_geofence(vec_id, i, step.get("expect") or {}, got)
            elif op == "project":
                got = table.project(
                    float(step["lat_deg"]), float(step["lon_deg"]),
                    float(step["ref_lat_deg"]), float(step["ref_lon_deg"]))
                _mark(stats, t0)
                _check_project(vec_id, i, step.get("expect") or {}, got.x, got.y)
            elif op == "classify":
                verts = step.get("vertices", vec.get("vertices") or [])
                got = table.polygon_error([_num(x) for x in verts])
                _mark(stats, t0)
                want = (step.get("expect") or {}).get("polygon_error")
                if want is not None and got != want:
                    raise CtkError(f"{vec_id} step {i}: polygon_error got {got} want {want}")
            elif op == "check_params":
                p = _gf_params(step.get("params"), params)
                got = table.params_error(p)
                _mark(stats, t0)
                if "params_error" not in (step.get("expect") or {}):
                    raise CtkError(f"{vec_id} step {i}: check_params missing params_error")
                want = step["expect"]["params_error"]
                if got != want:
                    raise CtkError(f"{vec_id} step {i}: params_error got {got!r} want {want!r}")
            else:
                raise CtkError(f"{vec_id} step {i}: unknown op {op}")
        stats.n_ok += 1
    return stats


def _looks_like_gateway(data: list) -> bool:
    if not data:
        return False
    ops = {step.get("op") for step in (data[0].get("steps") or [])}
    return bool(ops & {"setpoint", "compute"})


def _looks_like_gateway_limits(data: list) -> bool:
    if not data:
        return False
    ops = {step.get("op") for step in (data[0].get("steps") or [])}
    return "check_gateway_limits" in ops


def _looks_like_monitor_max_age(data: list) -> bool:
    if not data:
        return False
    ops = {step.get("op") for step in (data[0].get("steps") or [])}
    return "check_max_age" in ops


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


def _looks_like_types(data: list) -> bool:
    if not data:
        return False
    ops = {step.get("op") for step in (data[0].get("steps") or [])}
    return "check_name" in ops


def _run_types_vectors(data: list, make_core) -> VectorRun:
    stats = VectorRun(n_ok=0, n_all=len(data), n_ops=0, max_step_ns=0)
    core = make_core(Params())
    for vec in data:
        vec_id = vec["id"]
        for i, step in enumerate(vec["steps"]):
            op = step.get("op")
            t0 = time.perf_counter_ns()
            if op != "check_name":
                raise CtkError(f"{vec_id} step {i}: unknown op {op}")
            got = core.vocabulary_name(str(step["kind"]), int(step["code"]))
            _mark(stats, t0)
            want = (step.get("expect") or {}).get("name")
            if want is None:
                raise CtkError(f"{vec_id} step {i}: check_name missing name")
            if got != want:
                raise CtkError(f"{vec_id} step {i}: name got {got!r} want {want!r}")
        stats.n_ok += 1
    return stats


def _looks_like_core_params(data: list) -> bool:
    if not data:
        return False
    ops = {step.get("op") for step in (data[0].get("steps") or [])}
    return "check_core_params" in ops


def _run_core_params_vectors(data: list, make_core) -> VectorRun:
    stats = VectorRun(n_ok=0, n_all=len(data), n_ops=0, max_step_ns=0)
    core = make_core(Params())
    for vec in data:
        vec_id = vec["id"]
        base = _params(vec.get("params"))
        for i, step in enumerate(vec["steps"]):
            op = step.get("op")
            t0 = time.perf_counter_ns()
            if op != "check_core_params":
                raise CtkError(f"{vec_id} step {i}: unknown op {op}")
            p = _params(step.get("params"), base)
            got = core.params_error(p)
            _mark(stats, t0)
            if "params_error" not in (step.get("expect") or {}):
                raise CtkError(f"{vec_id} step {i}: check_core_params missing params_error")
            want = step["expect"]["params_error"]
            if got != want:
                raise CtkError(f"{vec_id} step {i}: params_error got {got!r} want {want!r}")
        stats.n_ok += 1
    return stats


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
        _known(vec_id, step_i, key, set(mapping) | {"yaw", "speed_h"})
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


def _gw_limits(raw: dict | None, base: GatewayLimits | None = None) -> GatewayLimits:
    p = GatewayLimits() if base is None else replace(base)
    if not raw:
        return p
    for key in ("max_speed_h_m_s", "max_climb_rate_m_s", "max_descent_rate_m_s",
                "max_yaw_rate_rad_s", "future_stamp_tolerance_s", "cf_timeout_s"):
        if key in raw:
            setattr(p, key, float(raw[key]))
    return p


def _run_gateway_limits_vectors(data: list, make_gateway) -> VectorRun:
    stats = VectorRun(n_ok=0, n_all=len(data), n_ops=0, max_step_ns=0)
    gw = make_gateway(GatewayLimits())
    for vec in data:
        vec_id = vec["id"]
        base = _gw_limits(vec.get("limits"))
        for i, step in enumerate(vec["steps"]):
            op = step.get("op")
            t0 = time.perf_counter_ns()
            if op != "check_gateway_limits":
                raise CtkError(f"{vec_id} step {i}: unknown op {op}")
            got = gw.limits_error(_gw_limits(step.get("limits"), base))
            _mark(stats, t0)
            if "limits_error" not in (step.get("expect") or {}):
                raise CtkError(f"{vec_id} step {i}: check_gateway_limits missing limits_error")
            want = step["expect"]["limits_error"]
            if got != want:
                raise CtkError(f"{vec_id} step {i}: limits_error got {got!r} want {want!r}")
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
        _known(vec_id, step_i, key, mapping)
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


def _run_monitor_max_age_vectors(data: list, make_monitor) -> VectorRun:
    stats = VectorRun(n_ok=0, n_all=len(data), n_ops=0, max_step_ns=0)
    table = make_monitor(0.5)
    for vec in data:
        vec_id = vec["id"]
        for i, step in enumerate(vec["steps"]):
            op = step.get("op")
            t0 = time.perf_counter_ns()
            if op != "check_max_age":
                raise CtkError(f"{vec_id} step {i}: unknown op {op}")
            got = table.max_age_error(float(step["max_age_s"]))
            _mark(stats, t0)
            if "max_age_error" not in (step.get("expect") or {}):
                raise CtkError(f"{vec_id} step {i}: check_max_age missing max_age_error")
            want = step["expect"]["max_age_error"]
            if got != want:
                raise CtkError(f"{vec_id} step {i}: max_age_error got {got!r} want {want!r}")
        stats.n_ok += 1
    return stats


def run_vectors(path: Path, make_core=None, make_gateway=None, make_monitor=None,
                make_geofence=None) -> VectorRun:
    if make_core is None:
        make_core = lambda params: ReferenceCore(params=params)
    if make_gateway is None:
        make_gateway = lambda limits: ReferenceGateway(limits=limits)
    if make_monitor is None:
        make_monitor = lambda max_age: ReferenceMonitor(max_age_s=max_age)
    if make_geofence is None:
        make_geofence = lambda: ReferenceGeofence()
    data = json.loads(path.read_text(encoding="utf-8"))
    if _looks_like_geofence(data):
        return _run_geofence_vectors(data, make_geofence)
    if _looks_like_monitor_max_age(data):
        return _run_monitor_max_age_vectors(data, make_monitor)
    if _looks_like_monitor(data):
        return _run_monitor_vectors(data, make_monitor)
    if _looks_like_gateway_limits(data):
        return _run_gateway_limits_vectors(data, make_gateway)
    if _looks_like_gateway(data):
        return _run_gateway_vectors(data, make_gateway)
    if _looks_like_core_params(data):
        return _run_core_params_vectors(data, make_core)
    if _looks_like_types(data):
        return _run_types_vectors(data, make_core)
    return _run_spec_vectors(data, make_core)


def run_suite(path: Path, make_core=None, make_gateway=None, make_monitor=None,
              make_geofence=None) -> tuple[VectorRun, list[Path]]:
    """Run one vector file, or every vector file in a directory.

    Returns the aggregate result and the files it covers, in name order.
    """
    files = vector_files(path)
    acc = VectorRun(n_ok=0, n_all=0, n_ops=0, max_step_ns=0)
    for f in files:
        one = run_vectors(f, make_core, make_gateway, make_monitor, make_geofence)
        acc.n_ok += one.n_ok
        acc.n_all += one.n_all
        acc.n_ops += one.n_ops
        acc.max_step_ns = max(acc.max_step_ns, one.max_step_ns)
    return acc, files


def suite_digest(files: list[Path]) -> str:
    """sha256 over each file's name and bytes, in name order."""
    hasher = hashlib.sha256()
    for f in files:
        hasher.update(f.name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(f.read_bytes())
    return hasher.hexdigest()


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
    make_geofence = lambda: ReferenceGeofence()
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
        make_geofence = lambda _lib=lib: SilGeofence(_lib)
        port_name = "sil-cabi"
    return port_name, make_core, make_gateway, make_monitor, make_geofence


def run(argv: list[str] | None = None, out=None, err=None) -> int:
    """Run the `guara ctk` subcommand. Streams resolve at call time."""
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    parser = argparse.ArgumentParser(
        prog="guara ctk",
        description="Run published decision vectors against a port.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    runp = sub.add_parser("run", help="execute vectors and print a report")
    runp.add_argument("--port", required=True, choices=("python", "sil"))
    runp.add_argument("--vectors", type=Path, default=None,
                      help="a vector file, or a directory of them "
                           "(default: the whole published set)")
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
    port_name, make_core, make_gateway, make_monitor, make_geofence = factory

    if args.cmd == "run":
        vectors = args.vectors if args.vectors is not None else default_vector_dir(root)
        try:
            stats, files = run_suite(
                vectors, make_core, make_gateway, make_monitor, make_geofence)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, CtkError) as exc:
            print(f"FAIL ctk: {exc}", file=err)
            return 1
        digest = suite_digest(files)
        core_ver, abi_ver = params.versions_from_header(root)
        body = "\n".join(_report_lines(
            port_name, core_ver, abi_ver, digest, ",".join(f.name for f in files),
            stats.n_ok, stats.n_all,
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
            acc, files = run_suite(
                vectors, make_core, make_gateway, make_monitor, make_geofence)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, CtkError) as exc:
            print(f"FAIL ctk: {exc}", file=err)
            return 1
        core_ver, abi_ver = params.versions_from_header(root)
        body = "\n".join(_bench_lines(
            port_name, core_ver, abi_ver, ",".join(f.name for f in files),
            suite_digest(files), acc,
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
