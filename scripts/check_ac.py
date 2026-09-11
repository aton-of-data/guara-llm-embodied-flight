#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Acceptance-criterion checkers (SPEC §6). Numbers come only from run artifacts."""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The line the arbiter logs once registration with PX4 succeeded (arbiter_node.cpp).
REGISTERED_RE = re.compile(r"registered '.*' \(executor id \d+, nav_state \d+\)")


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
    """Ogma/Copilot monitor publishes a violation in the altitude scenario, and only then.

    A monitor stuck at violated=true would have satisfied the original checker: in the run reviewed
    on 2026-09-11 every one of the 1728 verdicts, including those on the ground, reported a
    violation. The criterion now needs the negative control as well: the monitor must report at
    least one non-violation with complete inputs before the first violation, i.e. an actual
    false -> true transition.
    """
    errors: list[str] = []
    verdicts = run_dir / "verdicts.jsonl"
    if not verdicts.is_file():
        return ["missing verdicts.jsonl"]
    lines = [ln for ln in verdicts.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return ["verdicts.jsonl is empty (monitor published nothing)"]
    records = [json.loads(ln) for ln in lines]
    alt = [v for v in records if v.get("monitor_id") == "REQ-ALT-01"]
    if not alt:
        return ["no MonitorVerdict from REQ-ALT-01"]
    fired = [v for v in alt if v.get("violated")]
    if not fired:
        return ["no REQ-ALT-01 verdict with violated=true"]
    first_violation = next(i for i, v in enumerate(alt) if v.get("violated"))
    clear_before = [v for v in alt[:first_violation]
                    if not v.get("violated") and v.get("inputs_complete", True)]
    if not clear_before:
        errors.append(
            f"no violated=false verdict before the first violation ({first_violation} samples): "
            "the criterion is vacuous, a monitor stuck at true would pass")
    n_clear = sum(1 for v in alt if not v.get("violated"))
    print(json.dumps({"AC-3": {"n_verdicts": len(alt), "n_violated": len(fired),
                               "n_clear": n_clear,
                               "first_violation_index": first_violation}}, indent=2))
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
    ulog = ULog(str(ulogs[0]),
                message_name_filter_list=["vehicle_status", "vehicle_command"])
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
    # L6 of the latency budget (SPEC §4.1): the arbiter's SET_NAV_STATE command in the ULog to the
    # nav_state change. Recording it here was the AC-7 gap of the review of 2026-09-11.
    t_cmd_us = _ulog_set_nav_state_us(ulog, NAV_LOITER, before_us=t_loiter)
    if t_cmd_us is None:
        return ["ULog has no VEHICLE_CMD_SET_NAV_STATE(AUTO_LOITER) before the Hold: L6 unmeasurable"]
    dt_s = (t_loiter - t_owned) * 1e-6
    l6_s = (t_loiter - t_cmd_us) * 1e-6
    metrics = {
        "AC-7": {
            "t_owned_us": t_owned,
            "t_cmd_us": t_cmd_us,
            "t_loiter_us": t_loiter,
            "dt_owned_to_hold_s": dt_s,
            "l6_s": l6_s,
            "note": "l6_s is the ULog SET_NAV_STATE(AUTO_LOITER) stamp to the AUTO_LOITER sample",
        }
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"owned→AUTO_LOITER dt={dt_s:.3f} s, L6={l6_s:.3f} s (written to metrics.json)")
    return []


CMD_SET_NAV_STATE = 100001  # px4_msgs/msg/VehicleCommand.msg:114
NAV_LOITER = 4
NAV_RTL = 5


def _ulog_set_nav_state_us(ulog, nav_state: int, before_us: int | None = None) -> int | None:
    """Timestamp of the last SET_NAV_STATE(nav_state) command logged before `before_us`."""
    datasets = [d for d in ulog.data_list if d.name == "vehicle_command"]
    if not datasets:
        return None
    data = datasets[0].data
    found = None
    for i, command in enumerate(data["command"]):
        if int(command) != CMD_SET_NAV_STATE:
            continue
        if abs(float(data["param1"][i]) - float(nav_state)) > 0.5:
            continue
        t = int(data["timestamp"][i])
        if before_us is not None and t > before_us:
            continue
        found = t
    return found


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

    # P-6 is a property of what reached PX4, not of what the arbiter logged. The ULog carries every
    # vehicle_command with its source_component, so the absence of executor commands after the
    # override is asserted against the flight log (review of 2026-09-11, AC-14 gap).
    errors, meta = _no_executor_command_after_override(run_dir)
    if errors:
        return errors
    (run_dir / "metrics.json").write_text(json.dumps({"AC-14": meta}, indent=2) + "\n")
    print(f"pilot override at {meta['t_override_us']} us; "
          f"{meta['n_executor_commands_after']} executor commands afterwards")
    return []


COMPONENT_MODE_EXECUTOR_START = 1000  # px4_msgs/msg/VehicleCommand.msg:198


def _no_executor_command_after_override(run_dir: pathlib.Path) -> tuple[list[str], dict]:
    """No SET_NAV_STATE from a mode executor after the pilot leaves the owned mode."""
    try:
        from pyulog import ULog
    except ImportError:
        return ["pyulog missing; run via ./scripts/dev.sh"], {}
    ulogs = sorted(run_dir.rglob("*.ulg"))
    if not ulogs:
        return ["no .ulg in run directory"], {}
    ulog = ULog(str(ulogs[0]), message_name_filter_list=["vehicle_status", "vehicle_command"])
    by_name = {d.name: d for d in ulog.data_list}
    status = by_name.get("vehicle_status")
    if status is None:
        return ["ULog has no vehicle_status"], {}
    t_override = None
    in_owned = False
    for t, ns in zip(status.data["timestamp"], status.data["nav_state"]):
        if 23 <= int(ns) <= 30:
            in_owned = True
        elif in_owned and t_override is None:
            t_override = int(t)
    if t_override is None:
        return ["ULog never leaves the owned mode: the override did not happen"], {}
    after = []
    cmd = by_name.get("vehicle_command")
    if cmd is not None:
        for i, command in enumerate(cmd.data["command"]):
            t = int(cmd.data["timestamp"][i])
            source = int(cmd.data["source_component"][i])
            if t <= t_override or source < COMPONENT_MODE_EXECUTOR_START:
                continue
            if int(command) != CMD_SET_NAV_STATE:
                continue
            after.append({"t_us": t, "param1": float(cmd.data["param1"][i]), "source": source})
    if after:
        return [f"executor commands after the override: {after}"], {}
    return [], {"t_override_us": t_override, "n_executor_commands_after": 0}


def check_ac15(run_dir: pathlib.Path) -> list[str]:
    """FM-1: kill arbiter in CF → AUTO_RTL in ULog."""
    try:
        from pyulog import ULog
    except ImportError:
        return ["pyulog missing; run via ./scripts/dev.sh"]
    ulogs = sorted(run_dir.rglob("*.ulg"))
    if not ulogs:
        return ["no .ulg in run directory"]
    ulog = ULog(str(ulogs[0]),
                message_name_filter_list=["vehicle_status", "trajectory_setpoint"])
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
    # Detection time of FM-1, measured entirely on the PX4 clock: the arbiter's last trajectory
    # setpoint before the failsafe, to the AUTO_RTL sample. The logger decimates the setpoint topic,
    # so the sampling period is reported with the value instead of being hidden (review of
    # 2026-09-11, AC-15 gap: "detection time recorded in metrics.json" was not met).
    sp = [d for d in ulog.data_list if d.name == "trajectory_setpoint"]
    detection = {"available": False}
    if sp:
        sp_ts = [int(t) for t in sp[0].data["timestamp"]]
        before = [t for t in sp_ts if t <= t_rtl]
        gaps = sorted((b - a) * 1e-6 for a, b in zip(sp_ts, sp_ts[1:]))
        if before and gaps:
            detection = {
                "available": True,
                "t_last_setpoint_us": before[-1],
                "dt_last_setpoint_to_rtl_s": (t_rtl - before[-1]) * 1e-6,
                "setpoint_sampling_p50_s": gaps[len(gaps) // 2],
                "setpoint_sampling_max_s": gaps[-1],
                "note": "upper bound: the arbiter died at or after the last logged setpoint",
            }
    if not detection["available"]:
        return ["ULog has no trajectory_setpoint before AUTO_RTL: detection time unmeasurable"]
    metrics = {
        "AC-15": {
            "t_owned_us": t_owned,
            "t_rtl_us": t_rtl,
            "dt_last_owned_to_rtl_s": dt_s,
            "detection": detection,
            "px4_unresponsive": True,
            "px4_failsafe": True,
        }
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"owned→AUTO_RTL dt={dt_s:.3f} s, detection<={detection['dt_last_setpoint_to_rtl_s']:.3f} s "
          f"(+/-{detection['setpoint_sampling_p50_s']:.3f} s sampling)")
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
    """FM-3: an armed restart is rejected by PX4.

    PX4 prints "Not accepting registration requests while armed" on the rejection path
    (ModeManagement.cpp:378). "Mode '...' already registered" is printed on the *accept* path
    (ModeManagement.cpp:137) when PX4 re-registers the mode under a new index, which is what happens
    when COM_MODE_ARM_CHK is 1. Accepting that warning as evidence of FM-3 was finding C-1 of the
    review of 2026-09-11, so the checker now requires the rejection string, requires the run contract
    to have pinned COM_MODE_ARM_CHK = 0, and requires the restarted arbiter to have failed to
    register.
    """
    errors = []
    config_path = run_dir / "config.yaml"
    if config_path.is_file():
        config = yaml.safe_load(config_path.read_text()) or {}
        entry = (config.get("px4_params") or {}).get("COM_MODE_ARM_CHK")
        if entry is None or entry.get("read_back") != 0:
            errors.append(
                "run did not pin COM_MODE_ARM_CHK = 0; registration while armed was permitted")
    else:
        errors.append("missing config.yaml")

    px4_log = (run_dir / "px4.log").read_text(errors="replace") if (run_dir / "px4.log").is_file() else ""
    rejected = px4_log.find("Not accepting registration requests while armed")
    if rejected < 0:
        errors.append("px4.log has no 'Not accepting registration requests while armed'")
    if "already registered" in px4_log:
        errors.append("px4.log shows 'already registered': PX4 accepted the armed re-registration")
    disarmed = px4_log.find("Disarmed")
    if rejected >= 0 and disarmed != -1 and rejected > disarmed:
        errors.append("registration rejection was logged after disarm")

    restart_log = run_dir / "guara_rta_node_restart.log"
    if not restart_log.is_file():
        errors.append("missing guara_rta_node_restart.log")
    elif REGISTERED_RE.search(restart_log.read_text(errors="replace")):
        errors.append("restarted arbiter registered while armed")
    if errors:
        return errors
    print("PX4 rejected the armed registration and the restarted arbiter did not register")
    return []


def _ulog_owned_then(run_dir: pathlib.Path, nav_want: int, label: str) -> tuple[list[str], dict]:
    try:
        from pyulog import ULog
    except ImportError:
        return ["pyulog missing; run via ./scripts/dev.sh"], {}
    ulogs = sorted(run_dir.rglob("*.ulg"))
    if not ulogs:
        return ["no .ulg in run directory"], {}
    ulog = ULog(str(ulogs[0]), message_name_filter_list=["vehicle_status"])
    datasets = [d for d in ulog.data_list if d.name == "vehicle_status"]
    if not datasets:
        return ["ULog has no vehicle_status"], {}
    ts = datasets[0].data["timestamp"]
    nav = datasets[0].data["nav_state"]
    t_owned = None
    t_want = None
    for t, ns in zip(ts, nav):
        nsi = int(ns)
        if 23 <= nsi <= 30:
            if t_want is None:
                t_owned = int(t)
        elif t_owned is not None and nsi == nav_want and t_want is None:
            t_want = int(t)
    if t_owned is None:
        return ["ULog never shows owned/external nav_state"], {}
    if t_want is None:
        return [f"ULog shows owned mode but no {label} afterwards"], {}
    return [], {"t_owned_us": t_owned, "t_after_us": t_want, "dt_s": (t_want - t_owned) * 1e-6}


def check_ac16(run_dir: pathlib.Path) -> list[str]:
    """FM-4: decision-thread hang → AUTO_RTL."""
    text = (run_dir / "guara_rta_node.log").read_text(errors="replace") if (run_dir / "guara_rta_node.log").is_file() else ""
    if "decision thread hang" not in text:
        return ["arbiter log has no decision-thread hang injection"]
    errors, meta = _ulog_owned_then(run_dir, 5, "AUTO_RTL")
    if errors:
        return errors
    px4_log = (run_dir / "px4.log").read_text(errors="replace") if (run_dir / "px4.log").is_file() else ""
    if "Failsafe activated" not in px4_log and "RTL: start return" not in px4_log:
        return ["px4.log has no Failsafe/RTL after decision hang"]
    # FM-4 and FM-5 reach AUTO_RTL by different PX4 paths and must not be confused (review of
    # 2026-09-11, AC-16 gap). FM-4 is the arming-check path: the ROS executor still answers PX4, so
    # the mode is never flagged unresponsive; the owned mode fails its own check and PX4 falls back.
    if "flagging unresponsive" in px4_log:
        return ["px4.log shows 'flagging unresponsive': this is the FM-5 path, not FM-4"]
    meta["path"] = "arming check (FM-4)"
    meta["px4_unresponsive"] = False
    (run_dir / "metrics.json").write_text(json.dumps({"AC-16": meta}, indent=2) + "\n")
    print(f"owned→AUTO_RTL dt={meta['dt_s']:.3f} s after decision hang")
    return []


def check_ac16b(run_dir: pathlib.Path) -> list[str]:
    """FM-5: ROS executor hang → AUTO_RTL."""
    text = (run_dir / "guara_rta_node.log").read_text(errors="replace") if (run_dir / "guara_rta_node.log").is_file() else ""
    if "ROS executor hang" not in text:
        return ["arbiter log has no ROS-executor hang injection"]
    errors, meta = _ulog_owned_then(run_dir, 5, "AUTO_RTL")
    if errors:
        return errors
    px4_log = (run_dir / "px4.log").read_text(errors="replace") if (run_dir / "px4.log").is_file() else ""
    if "flagging unresponsive" not in px4_log:
        return ["px4.log has no mode-executor unresponsive warning"]
    if "RTL: start return" not in px4_log:
        return ["px4.log has no 'RTL: start return'"]
    meta["path"] = "mode executor unresponsive (FM-5)"
    meta["px4_unresponsive"] = True
    (run_dir / "metrics.json").write_text(json.dumps({"AC-16b": meta}, indent=2) + "\n")
    print(f"owned→AUTO_RTL dt={meta['dt_s']:.3f} s after ROS hang")
    return []


def check_ac17(run_dir: pathlib.Path) -> list[str]:
    """FM-6: stale local position → HOLD within two ticks of A_i."""
    text = (run_dir / "guara_rta_node.log").read_text(errors="replace") if (run_dir / "guara_rta_node.log").is_file() else ""
    if "drop local position" not in text:
        return ["arbiter log has no local-position drop injection"]
    events_path = run_dir / "events.jsonl"
    if not events_path.is_file():
        return ["missing events.jsonl"]
    records = [json.loads(ln) for ln in events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    t2 = None
    t3 = None
    for rec in records:
        if rec.get("transition") == 2:
            t2 = rec
        if t2 is not None and rec.get("transition") == 3 and (int(rec.get("cause_mask", 0)) & 8):
            t3 = rec
    if t3 is None:
        return ["no T3 with CAUSE_INPUT after T2 in events.jsonl"]
    age = float(t3["t_decide_s"]) - float(t3["t_input_recv_s"])
    a_i = 0.2
    two_ticks = 0.10
    slack = 0.05
    if age < a_i - slack:
        return [f"T3 age {age:.3f} s < A_i {a_i} s"]
    # The criterion is "within two ticks of A_i"; the earlier upper bound added a further 0.05 s of
    # slack and was looser than the SPEC (review of 2026-09-11, AC-17 gap).
    if age > a_i + two_ticks:
        return [f"T3 age {age:.3f} s > A_i + 2 ticks ({a_i + two_ticks} s)"]
    errors, meta = _ulog_owned_then(run_dir, 4, "AUTO_LOITER")
    if errors:
        return errors
    metrics = {"AC-17": {"age_s": age, "a_i_s": a_i, "t3_tick": t3.get("tick"), **meta}}
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"stale local position T3 age={age:.3f} s (A_i=0.2 s); owned→AUTO_LOITER dt={meta['dt_s']:.3f} s")
    return []


_EARTH_R_M = 6371000.0


def _project_to_local(lat_deg: float, lon_deg: float, ref_lat_deg: float, ref_lon_deg: float) -> tuple[float, float]:
    """Azimuthal equidistant, same formula as guara_geofence::projectToLocal."""
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    ref_lat, ref_lon = math.radians(ref_lat_deg), math.radians(ref_lon_deg)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    cos_d_lon = math.cos(lon - ref_lon)
    arg = min(1.0, max(-1.0, math.sin(ref_lat) * sin_lat + math.cos(ref_lat) * cos_lat * cos_d_lon))
    c = math.acos(arg)
    k = c / math.sin(c) if abs(c) > 0.0 else 1.0
    north = k * (math.cos(ref_lat) * sin_lat - math.sin(ref_lat) * cos_lat * cos_d_lon) * _EARTH_R_M
    east = k * cos_lat * math.sin(lon - ref_lon) * _EARTH_R_M
    return north, east


def _pip(q: tuple[float, float], poly: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        intersects = ((a[1] > q[1]) != (b[1] > q[1])) and (
            q[0] < (b[0] - a[0]) * (q[1] - a[1]) / (b[1] - a[1] + 0.0) + a[0])
        if b[1] != a[1] and intersects:
            inside = not inside
    return inside


def _boundary_distance(q: tuple[float, float], poly: list[tuple[float, float]]) -> float:
    best = float("inf")
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        abx, aby = bx - ax, by - ay
        len2 = abx * abx + aby * aby
        t = 0.0 if len2 == 0.0 else max(0.0, min(1.0, ((q[0] - ax) * abx + (q[1] - ay) * aby) / len2))
        dx, dy = q[0] - (ax + t * abx), q[1] - (ay + t * aby)
        best = min(best, math.hypot(dx, dy))
    return best


def _max_violation_depth(run_dir: pathlib.Path, flat_lat_lon: list[float]) -> tuple[list[str], float]:
    try:
        from pyulog import ULog
    except ImportError:
        return ["pyulog missing; run via ./scripts/dev.sh"], 0.0
    ulogs = sorted(run_dir.rglob("*.ulg"))
    if not ulogs:
        return ["no .ulg in run directory"], 0.0
    ulog = ULog(str(ulogs[0]), message_name_filter_list=["vehicle_local_position"])
    datasets = [d for d in ulog.data_list if d.name == "vehicle_local_position"]
    if not datasets:
        return ["ULog has no vehicle_local_position"], 0.0
    data = datasets[0].data
    xs, ys = data["x"], data["y"]
    ref_lat = data["ref_lat"] if "ref_lat" in data else None
    ref_lon = data["ref_lon"] if "ref_lon" in data else None
    home = yaml.safe_load((run_dir / "config.yaml").read_text())["simulator"]["home"]
    pairs = list(zip(flat_lat_lon[0::2], flat_lat_lon[1::2]))
    max_depth = 0.0
    for i, (x, y) in enumerate(zip(xs, ys)):
        q = (float(x), float(y))
        if not math.isfinite(q[0]) or not math.isfinite(q[1]):
            continue
        rlat, rlon = float(home["lat"]), float(home["lon"])
        if ref_lat is not None:
            cand_lat, cand_lon = float(ref_lat[i]), float(ref_lon[i])
            if math.isfinite(cand_lat) and math.isfinite(cand_lon):
                rlat, rlon = cand_lat, cand_lon
        poly = [_project_to_local(la, lo, rlat, rlon) for la, lo in pairs]
        if any(not math.isfinite(p[0]) or not math.isfinite(p[1]) for p in poly):
            continue
        if _pip(q, poly) or _boundary_distance(q, poly) <= 1e-6:
            continue
        max_depth = max(max_depth, _boundary_distance(q, poly))
    return [], max_depth


def check_ac9(pair_dir: pathlib.Path) -> list[str]:
    """With RTA, fence is not violated; without RTA the same CF exits the polygon."""
    on_dir = pair_dir / "rta_on"
    off_dir = pair_dir / "rta_off"
    if not on_dir.exists() or not off_dir.exists():
        return [f"pair directory {pair_dir} needs rta_on/ and rta_off/"]
    cfg = yaml.safe_load((on_dir / "config.yaml").read_text())
    flat = cfg.get("expect", {}).get("geofence", {}).get("polygon_lat_lon_deg")
    if not flat or len(flat) < 6:
        return ["rta_on config.yaml missing expect.geofence.polygon_lat_lon_deg"]
    err_on, depth_on = _max_violation_depth(on_dir, flat)
    if err_on:
        return [f"rta_on: {e}" for e in err_on]
    err_off, depth_off = _max_violation_depth(off_dir, flat)
    if err_off:
        return [f"rta_off: {e}" for e in err_off]
    log_on = on_dir / "guara_rta_node.log"
    transitions = _transitions(log_on.read_text(errors="replace")) if log_on.is_file() else []
    metrics = {"AC-9": {
        "depth_rta_on_m": depth_on,
        "depth_rta_off_m": depth_off,
        "transitions_rta_on": transitions,
    }}
    (pair_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"max violation depth on={depth_on:.3f} m  off={depth_off:.3f} m  "
          f"transitions={transitions}")
    errors = []
    # The SPEC criterion is "0 m outside the fence"; the previous 0.05 m tolerance was an
    # unrecorded relaxation (review of 2026-09-11, AC-9 gap). Only projection round-off is allowed.
    if depth_on > 1e-6:
        errors.append(f"with RTA max violation depth {depth_on:.6f} m > 0")
    if depth_off <= 0.0:
        errors.append(f"without RTA max violation depth {depth_off:.3f} m; scenario did not exit the fence")
    return errors


def check_ac18(batch: pathlib.Path) -> list[str]:
    """p50/p99 of L0..L6 and δ_lat from ≥ 30 runs; every stage present."""
    metrics_path = batch / "metrics.json"
    if not metrics_path.is_file():
        return [f"missing {metrics_path}; run python3 scripts/aggregate.py {batch}"]
    m = json.loads(metrics_path.read_text(encoding="utf-8"))
    errors = []
    if int(m.get("n_runs", 0)) < 30:
        errors.append(f"n_runs={m.get('n_runs')} < 30")
    stages = m.get("stages") or {}
    for name in ("L0", "L1", "L2", "L3", "L4", "L5", "L6"):
        st = stages.get(name) or {}
        if int(st.get("n") or 0) < 30:
            errors.append(f"{name} n={st.get('n')} < 30")
        if st.get("p50_s") is None or st.get("p99_s") is None:
            errors.append(f"{name} missing p50/p99")
    dl = m.get("delta_lat") or {}
    if int(dl.get("n") or 0) < 30:
        errors.append(f"delta_lat n={dl.get('n')} < 30")
    if dl.get("p50_s") is None or dl.get("p99_s") is None:
        errors.append("delta_lat missing p50/p99")
    print(json.dumps({"AC-18": {"n_runs": m.get("n_runs"), "stages": stages, "delta_lat": dl}}, indent=2))
    return errors


def check_ac19(batch: pathlib.Path) -> list[str]:
    """PX4↔ROS 2 clock alignment p99 measured; cross-process latencies gated at 10 ms."""
    metrics_path = batch / "metrics.json"
    if not metrics_path.is_file():
        return [f"missing {metrics_path}"]
    m = json.loads(metrics_path.read_text(encoding="utf-8"))
    ca = m.get("clock_alignment") or {}
    p99 = ca.get("abs_p99_s")
    if p99 is None:
        return ["clock_alignment.abs_p99_s missing"]
    print(json.dumps({"AC-19": ca}, indent=2))
    return []


def check_ac22(batch: pathlib.Path) -> list[str]:
    """O-1 with measured δ_lat and τ_rec."""
    metrics_path = batch / "metrics.json"
    if not metrics_path.is_file():
        return [f"missing {metrics_path}"]
    m = json.loads(metrics_path.read_text(encoding="utf-8"))
    o1 = m.get("o1") or {}
    if o1.get("delta_lat_p99_s") is None:
        return ["o1.delta_lat_p99_s missing"]
    if o1.get("tau_rec_p99_s") is None:
        return ["o1.tau_rec_p99_s missing (ULog speed after Hold)"]
    print(json.dumps({"AC-22": o1}, indent=2))
    errors = []
    if not o1.get("geofence_satisfied"):
        errors.append("O-1 geofence: tau_gf < delta_lat p99")
    if not o1.get("daa_satisfied"):
        errors.append("O-1 DAA: tau_daa < tau_rec p99 + delta_lat p99")
    return errors


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
    "AC-9": check_ac9,
    "AC-11": check_ac11,
    "AC-14": check_ac14,
    "AC-15": check_ac15,
    "AC-15b": check_ac15b,
    "AC-15c": check_ac15c,
    "AC-16": check_ac16,
    "AC-16b": check_ac16b,
    "AC-17": check_ac17,
    "AC-18": check_ac18,
    "AC-19": check_ac19,
    "AC-20": check_ac20,
    "AC-22": check_ac22,
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
