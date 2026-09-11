#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Acceptance-criterion checkers (SPEC §6). Numbers come only from run artifacts."""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def check_ac20(_path: pathlib.Path) -> list[str]:
    """FM-9: Guará never enables failsafe deferral."""
    errors: list[str] = []
    src = ROOT / "ros2_ws" / "src"
    result = subprocess.run(
        ["grep", "-rn", r"deferFailsafesSync *( *true", str(src)],
        capture_output=True, text=True)
    if result.returncode == 0:
        errors.append("deferFailsafesSync(true) present:\n" + result.stdout)
    elif result.returncode != 1:
        errors.append(f"grep failed: {result.stderr}")
    return errors


def check_ac3(run_dir: pathlib.Path) -> list[str]:
    """Ogma/Copilot monitor publishes a violation in the altitude scenario."""
    errors: list[str] = []
    verdicts = run_dir / "verdicts.jsonl"
    if not verdicts.is_file():
        return ["missing verdicts.jsonl"]
    lines = [ln for ln in verdicts.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return ["verdicts.jsonl is empty (monitor published nothing)"]
    records = [json.loads(ln) for ln in lines]
    fired = [v for v in records if v.get("violated")]
    if not fired:
        errors.append("no MonitorVerdict with violated=true")
    elif not any(v.get("monitor_id") == "REQ-ALT-01" for v in fired):
        errors.append("violation present but monitor_id is not REQ-ALT-01")
    return errors


def check_ac7(run_dir: pathlib.Path) -> list[str]:
    """Injected monitor trigger drives nav_state to AUTO_LOITER (Hold)."""
    try:
        from pyulog import ULog
    except ImportError:
        return ["pyulog missing; run via ./scripts/dev.sh"]
    ulogs = sorted(run_dir.rglob("*.ulg"))
    if not ulogs:
        return ["no .ulg in run directory"]
    ulog = ULog(str(ulogs[0]), message_name_filter_list=["vehicle_status"])
    datasets = [d for d in ulog.data_list if d.name == "vehicle_status"]
    if not datasets:
        return ["ULog has no vehicle_status"]
    ts = datasets[0].data["timestamp"]
    nav = datasets[0].data["nav_state"]
    t_owned = None
    t_loiter = None
    for t, ns in zip(ts, nav):
        if 23 <= int(ns) <= 30:
            t_owned = int(t)
        elif t_owned is not None and int(ns) == 4 and t_loiter is None:
            t_loiter = int(t)
    if t_owned is None:
        return ["ULog never shows owned/external nav_state (23-30)"]
    if t_loiter is None:
        return ["ULog shows owned mode but no AUTO_LOITER afterwards"]
    dt_s = (t_loiter - t_owned) * 1e-6
    metrics = {
        "AC-7": {
            "t_owned_us": t_owned,
            "t_loiter_us": t_loiter,
            "dt_owned_to_hold_s": dt_s,
            "note": "dt is owned-mode sample to AUTO_LOITER; L6 needs the matching vehicle_command stamp (M7)",
        }
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"owned→AUTO_LOITER dt={dt_s:.3f} s (written to metrics.json)")
    return []


def _transitions(log_text: str) -> list[str]:
    found = []
    for line in log_text.splitlines():
        if "]: T" in line and " -> " in line:
            found.append(line)
    return found


def check_ac14(run_dir: pathlib.Path) -> list[str]:
    """User mode switch → INACTIVE; no executor command afterwards."""
    log_path = run_dir / "guara_rta_node.log"
    if not log_path.is_file():
        return ["missing guara_rta_node.log"]
    lines = _transitions(log_path.read_text(errors="replace"))
    seen_t2 = False
    seen_t1_after_t2 = False
    for ln in lines:
        if " T2 " in ln:
            seen_t2 = True
        if seen_t2 and " T1 " in ln:
            seen_t1_after_t2 = True
            continue
        if seen_t1_after_t2 and (" T3 " in ln or " T6 " in ln or " T5 " in ln):
            return [f"executor commanded after T1: {ln.strip()}"]
    if not seen_t2:
        return ["no T2 (enter CF) in arbiter log"]
    if not seen_t1_after_t2:
        return ["no T1 (INACTIVE) after CF (pilot override)"]
    return []


def check_ac15(run_dir: pathlib.Path) -> list[str]:
    """FM-1: kill arbiter in CF → AUTO_RTL in ULog."""
    try:
        from pyulog import ULog
    except ImportError:
        return ["pyulog missing; run via ./scripts/dev.sh"]
    ulogs = sorted(run_dir.rglob("*.ulg"))
    if not ulogs:
        return ["no .ulg in run directory"]
    ulog = ULog(str(ulogs[0]), message_name_filter_list=["vehicle_status"])
    datasets = [d for d in ulog.data_list if d.name == "vehicle_status"]
    if not datasets:
        return ["ULog has no vehicle_status"]
    ts = datasets[0].data["timestamp"]
    nav = datasets[0].data["nav_state"]
    t_owned = None
    t_rtl = None
    for t, ns in zip(ts, nav):
        if 23 <= int(ns) <= 30:
            t_owned = int(t)
        elif t_owned is not None and int(ns) == 5 and t_rtl is None:
            t_rtl = int(t)
    if t_owned is None:
        return ["ULog never shows owned/external nav_state"]
    if t_rtl is None:
        return ["ULog shows owned mode but no AUTO_RTL afterwards"]
    px4_log = (run_dir / "px4.log").read_text(errors="replace") if (run_dir / "px4.log").is_file() else ""
    if "flagging unresponsive" not in px4_log:
        return ["px4.log has no mode-executor unresponsive warning"]
    if "Failsafe activated" not in px4_log:
        return ["px4.log has no 'Failsafe activated'"]
    if "RTL: start return" not in px4_log:
        return ["px4.log has no 'RTL: start return'"]
    dt_s = (t_rtl - t_owned) * 1e-6
    metrics = {
        "AC-15": {
            "t_owned_us": t_owned,
            "t_rtl_us": t_rtl,
            "dt_last_owned_to_rtl_s": dt_s,
            "px4_unresponsive": True,
            "px4_failsafe": True,
            "note": "ULog dt is last owned-mode sample to first AUTO_RTL (logger period). FM-1 detection is kill→rtl in sitl_run.log.",
        }
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"owned→AUTO_RTL dt={dt_s:.3f} s (written to metrics.json)")
    return []


def check_ac15b(run_dir: pathlib.Path) -> list[str]:
    """FM-2: kill arbiter in Hold → AUTO_LOITER persists, no AUTO_RTL."""
    try:
        from pyulog import ULog
    except ImportError:
        return ["pyulog missing; run via ./scripts/dev.sh"]
    ulogs = sorted(run_dir.rglob("*.ulg"))
    if not ulogs:
        return ["no .ulg in run directory"]
    ulog = ULog(str(ulogs[0]), message_name_filter_list=["vehicle_status"])
    datasets = [d for d in ulog.data_list if d.name == "vehicle_status"]
    if not datasets:
        return ["ULog has no vehicle_status"]
    ts = datasets[0].data["timestamp"]
    nav = datasets[0].data["nav_state"]
    t_owned = None
    t_loiter = None
    saw_rtl_after_loiter = False
    last_after = None
    for t, ns in zip(ts, nav):
        nsi = int(ns)
        if 23 <= nsi <= 30:
            t_owned = int(t)
        elif t_owned is not None and nsi == 4 and t_loiter is None:
            t_loiter = int(t)
        if t_loiter is not None:
            last_after = nsi
            if nsi == 5:
                saw_rtl_after_loiter = True
    if t_owned is None:
        return ["ULog never shows owned/external nav_state"]
    if t_loiter is None:
        return ["ULog shows owned mode but no AUTO_LOITER afterwards"]
    if saw_rtl_after_loiter:
        return ["AUTO_RTL after Hold; FM-2 expected Hold to persist"]
    metrics = {
        "AC-15b": {
            "t_owned_us": t_owned,
            "t_loiter_us": t_loiter,
            "last_nav_state_after_hold": last_after,
            "rtl_after_hold": False,
        }
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"Hold persisted after arbiter kill (last nav_state={last_after})")
    return []


def check_ac15c(run_dir: pathlib.Path) -> list[str]:
    """FM-3: armed restart is rejected by PX4."""
    px4_log = (run_dir / "px4.log").read_text(errors="replace") if (run_dir / "px4.log").is_file() else ""
    armed_hit = px4_log.find("already registered")
    if armed_hit < 0:
        armed_hit = px4_log.find("Not accepting registration requests while armed")
    if armed_hit < 0:
        return ["px4.log has no armed-registration rejection"]
    if not (run_dir / "guara_rta_node_restart.log").is_file():
        return ["missing guara_rta_node_restart.log"]
    disarmed = px4_log.find("Disarmed")
    if disarmed != -1 and armed_hit > disarmed:
        return ["registration rejection was logged after disarm"]
    print("PX4 rejected armed registration (event in px4.log)")
    return []


def check_ac11(_path: pathlib.Path) -> list[str]:
    """ADR 0003: no DAIDALUS dependency outside nosa/."""
    script = ROOT / "scripts" / "check_license_isolation.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if result.returncode != 0:
        return [result.stdout + result.stderr]
    return []


CHECKERS = {
    "AC-3": check_ac3,
    "AC-7": check_ac7,
    "AC-11": check_ac11,
    "AC-14": check_ac14,
    "AC-15": check_ac15,
    "AC-15b": check_ac15b,
    "AC-15c": check_ac15c,
    "AC-20": check_ac20,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ac", help="acceptance criterion id, e.g. AC-20")
    parser.add_argument("path", nargs="?", default=".",
                        help="run directory or results path (unused by some ACs)")
    args = parser.parse_args()
    checker = CHECKERS.get(args.ac)
    if checker is None:
        print(f"FAIL unknown or unimplemented checker: {args.ac}", file=sys.stderr)
        print("implemented: " + ", ".join(sorted(CHECKERS)), file=sys.stderr)
        return 2
    errors = checker(pathlib.Path(args.path))
    if errors:
        print(f"FAIL {args.ac}")
        for err in errors:
            print(err)
        return 1
    print(f"PASS {args.ac}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
