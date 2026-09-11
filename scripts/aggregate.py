#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Aggregate per-run latency metrics into results/batch_latency/metrics.json (SPEC §4, AC-18).

Numbers are computed only from run artifacts (events.jsonl, states.jsonl, ULog).
Usage: python3 scripts/aggregate.py results/batch_latency
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CMD_SET_NAV_STATE = 100001
NAV_LOITER = 4
CLOCK_ALIGN_LIMIT_S = 0.010  # AC-19 hypothesis
STAGES = ("L0", "L1", "L2", "L3", "L4", "L5", "L6")


def _finite(value) -> bool:
    return value is not None and math.isfinite(float(value))


def percentile(values: list[float], p: float) -> float:
    xs = sorted(values)
    if not xs:
        return float("nan")
    if len(xs) == 1:
        return xs[0]
    rank = (len(xs) - 1) * (p / 100.0)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return xs[lo]
    w = rank - lo
    return xs[lo] * (1.0 - w) + xs[hi] * w


def _jsonl(path: pathlib.Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _ulog_l0_l5_l6_tau(run_dir: pathlib.Path, t_cmd_pub_ros_s: float | None) -> dict:
    try:
        from pyulog import ULog
    except ImportError as exc:
        return {"error": f"pyulog missing: {exc}"}
    ulogs = sorted(run_dir.rglob("*.ulg"))
    if not ulogs:
        return {"error": "no .ulg"}
    ulog = ULog(str(ulogs[0]),
                message_name_filter_list=["vehicle_status", "vehicle_command", "vehicle_local_position"])
    by_name = {d.name: d for d in ulog.data_list}

    l0_samples = []
    lpos = by_name.get("vehicle_local_position")
    if lpos is not None and "timestamp" in lpos.data and "timestamp_sample" in lpos.data:
        for ts, sample in zip(lpos.data["timestamp"], lpos.data["timestamp_sample"]):
            dt = (int(ts) - int(sample)) * 1e-6
            if math.isfinite(dt) and -1.0 < dt < 1.0:
                l0_samples.append(dt)

    t_cmd_us = None
    cmd = by_name.get("vehicle_command")
    if cmd is not None:
        for i, command in enumerate(cmd.data["command"]):
            if int(command) != CMD_SET_NAV_STATE:
                continue
            param1 = float(cmd.data["param1"][i])
            if abs(param1 - float(NAV_LOITER)) > 0.5:
                continue
            t_cmd_us = int(cmd.data["timestamp"][i])

    t_loiter_us = None
    status = by_name.get("vehicle_status")
    if status is not None:
        for ts, ns in zip(status.data["timestamp"], status.data["nav_state"]):
            if int(ns) == NAV_LOITER:
                t_loiter_us = int(ts)
                if t_cmd_us is not None and t_loiter_us >= t_cmd_us:
                    break

    tau_rec_s = None
    if t_loiter_us is not None and lpos is not None:
        vx, vy, vz = lpos.data.get("vx"), lpos.data.get("vy"), lpos.data.get("vz")
        ts = lpos.data["timestamp"]
        t_stop = None
        for i, t in enumerate(ts):
            if int(t) < t_loiter_us:
                continue
            speed = math.sqrt(float(vx[i]) ** 2 + float(vy[i]) ** 2 + float(vz[i]) ** 2)
            if speed < 0.5:
                t_stop = int(t)
                break
        if t_stop is not None:
            tau_rec_s = (t_stop - t_loiter_us) * 1e-6

    l5_ulog = None
    if t_cmd_us is not None and _finite(t_cmd_pub_ros_s):
        l5_ulog = t_cmd_us * 1e-6 - float(t_cmd_pub_ros_s)
    l6 = None
    if t_cmd_us is not None and t_loiter_us is not None:
        l6 = (t_loiter_us - t_cmd_us) * 1e-6

    return {
        "l0_ulog_p50_s": percentile(l0_samples, 50) if l0_samples else None,
        "l5_ulog_s": l5_ulog,
        "l6_s": l6,
        "tau_rec_s": tau_rec_s,
        "t_cmd_ulog_us": t_cmd_us,
        "t_loiter_ulog_us": t_loiter_us,
        "n_l0_ulog": len(l0_samples),
    }


def extract_run(run_dir: pathlib.Path) -> dict:
    events = _jsonl(run_dir / "events.jsonl")
    states = _jsonl(run_dir / "states.jsonl")
    t3 = next((e for e in events if int(e.get("transition", 0)) == 3), None)
    if t3 is None:
        return {"run_id": run_dir.name, "error": "no T3 in events.jsonl"}

    clock_samples = [abs(float(s["clock_err_s"])) for s in states if _finite(s.get("clock_err_s"))]
    l0_state = [float(s["l0_s"]) for s in states if _finite(s.get("l0_s")) and float(s["l0_s"]) >= 0.0]

    l4 = None
    if _finite(t3.get("t_decide_s")) and _finite(t3.get("t_input_recv_s")):
        l4 = float(t3["t_decide_s"]) - float(t3["t_input_recv_s"])
    l5_ack = None
    if _finite(t3.get("t_ack_s")) and _finite(t3.get("t_cmd_pub_s")):
        l5_ack = float(t3["t_ack_s"]) - float(t3["t_cmd_pub_s"])

    ulog = _ulog_l0_l5_l6_tau(run_dir, t3.get("t_cmd_pub_ros_s"))
    l0 = t3.get("l0_s")
    if not _finite(l0) and _finite(ulog.get("l0_ulog_p50_s")):
        l0 = ulog["l0_ulog_p50_s"]
    l1 = t3.get("clock_err_s")
    l2 = t3.get("l2_s") if _finite(t3.get("l2_s")) else 0.0
    l3 = t3.get("l3_s")
    l5 = ulog.get("l5_ulog_s")
    if not _finite(l5):
        l5 = l5_ack
    l6 = ulog.get("l6_s")

    stages = {"L0": l0, "L1": l1, "L2": l2, "L3": l3, "L4": l4, "L5": l5, "L6": l6}
    delta = 0.0
    missing = []
    for name in STAGES:
        val = stages[name]
        if not _finite(val):
            missing.append(name)
        else:
            delta += float(val)

    return {
        "run_id": run_dir.name,
        "stages_s": {k: (None if not _finite(v) else float(v)) for k, v in stages.items()},
        "delta_lat_s": None if missing else delta,
        "missing_stages": missing,
        "l5_ack_s": l5_ack,
        "clock_err_abs_p99_s": percentile(clock_samples, 99) if clock_samples else None,
        "n_clock_samples": len(clock_samples),
        "n_l0_state_samples": len(l0_state),
        "tau_rec_s": ulog.get("tau_rec_s"),
        "ulog": {k: ulog[k] for k in ("l0_ulog_p50_s", "t_cmd_ulog_us", "t_loiter_ulog_us", "n_l0_ulog")
                 if k in ulog},
        "error": ulog.get("error"),
    }


def _run_dirs(batch: pathlib.Path) -> list[pathlib.Path]:
    listed = batch / "runs.txt"
    if listed.is_file():
        ids = [ln.strip() for ln in listed.read_text(encoding="utf-8").splitlines() if ln.strip()]
        dirs = []
        for rid in ids:
            path = batch / rid
            if path.is_dir():
                dirs.append(path.resolve())
            elif (ROOT / "results" / rid).is_dir():
                dirs.append(ROOT / "results" / rid)
        return dirs
    return sorted(p for p in batch.iterdir() if p.is_dir() or p.is_symlink())


def aggregate(batch: pathlib.Path) -> dict:
    runs = []
    errors = []
    for run_dir in _run_dirs(batch):
        rec = extract_run(run_dir)
        (run_dir / "metrics.json").write_text(json.dumps(rec, indent=2) + "\n")
        if rec.get("error") and rec.get("stages_s") is None:
            errors.append(f"{run_dir.name}: {rec['error']}")
        runs.append(rec)

    by_stage: dict[str, list[float]] = {s: [] for s in STAGES}
    deltas = []
    clock_p99s = []
    tau_recs = []
    for rec in runs:
        stages = rec.get("stages_s") or {}
        for name in STAGES:
            if _finite(stages.get(name)):
                by_stage[name].append(float(stages[name]))
        if _finite(rec.get("delta_lat_s")):
            deltas.append(float(rec["delta_lat_s"]))
        if _finite(rec.get("clock_err_abs_p99_s")):
            clock_p99s.append(float(rec["clock_err_abs_p99_s"]))
        if _finite(rec.get("tau_rec_s")):
            tau_recs.append(float(rec["tau_rec_s"]))

    stage_stats = {}
    for name in STAGES:
        xs = by_stage[name]
        stage_stats[name] = {
            "n": len(xs),
            "p50_s": percentile(xs, 50) if xs else None,
            "p99_s": percentile(xs, 99) if xs else None,
        }

    params_path = ROOT / "config" / "rta_params.yaml"
    tau_gf = 1.0
    tau_daa = 30.0
    try:
        import yaml
        params = yaml.safe_load(params_path.read_text())["guara_rta"]["ros__parameters"]
        tau_gf = float(params["core.tau_gf_s"])
        tau_daa = float(params["core.tau_daa_s"])
    except Exception:
        pass

    delta_p99 = percentile(deltas, 99) if deltas else None
    tau_rec_p99 = percentile(tau_recs, 99) if tau_recs else None
    clock_p99 = percentile(clock_p99s, 99) if clock_p99s else None
    cross_ok = _finite(clock_p99) and float(clock_p99) < CLOCK_ALIGN_LIMIT_S

    o1_gf = _finite(delta_p99) and tau_gf >= float(delta_p99)
    o1_daa = _finite(delta_p99) and _finite(tau_rec_p99) and tau_daa >= float(tau_rec_p99) + float(delta_p99)

    summary = {
        "n_runs": len(runs),
        "n_complete_delta": len(deltas),
        "stages": stage_stats,
        "delta_lat": {
            "n": len(deltas),
            "p50_s": percentile(deltas, 50) if deltas else None,
            "p99_s": delta_p99,
        },
        "clock_alignment": {
            "abs_p99_s": clock_p99,
            "limit_s": CLOCK_ALIGN_LIMIT_S,
            "cross_process_reported": cross_ok,
        },
        "tau_rec": {
            "n": len(tau_recs),
            "p50_s": percentile(tau_recs, 50) if tau_recs else None,
            "p99_s": tau_rec_p99,
            "note": "time after AUTO_LOITER until speed < 0.5 m/s (ULog)",
        },
        "o1": {
            "tau_gf_s": tau_gf,
            "tau_daa_s": tau_daa,
            "delta_lat_p99_s": delta_p99,
            "tau_rec_p99_s": tau_rec_p99,
            "geofence_satisfied": o1_gf,
            "daa_satisfied": o1_daa,
        },
        "runs": [{"run_id": r["run_id"], "delta_lat_s": r.get("delta_lat_s"),
                  "missing_stages": r.get("missing_stages")} for r in runs],
        "errors": errors,
    }
    (batch / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python3 scripts/aggregate.py results/batch_latency", file=sys.stderr)
        return 2
    batch = pathlib.Path(sys.argv[1])
    if not batch.is_dir():
        print(f"missing batch directory {batch}", file=sys.stderr)
        return 2
    summary = aggregate(batch)
    print(f"n_runs={summary['n_runs']} complete_delta={summary['n_complete_delta']}")
    for name, stats in summary["stages"].items():
        print(f"  {name} n={stats['n']} p50={stats['p50_s']} p99={stats['p99_s']}")
    dl = summary["delta_lat"]
    print(f"  delta_lat n={dl['n']} p50={dl['p50_s']} p99={dl['p99_s']}")
    ca = summary["clock_alignment"]
    print(f"  clock_err_abs_p99={ca['abs_p99_s']} cross_process={ca['cross_process_reported']}")
    print(f"wrote {batch / 'metrics.json'}")
    return 0 if summary["n_runs"] else 1


if __name__ == "__main__":
    sys.exit(main())
