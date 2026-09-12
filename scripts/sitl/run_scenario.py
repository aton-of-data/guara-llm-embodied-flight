#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Headless PX4 SIH scenario runner (runs inside the dev container; see scripts/sitl_run.sh).

Writes results/{run_id}/config.yaml before flight, the PX4 working directory
(including the ULog), and process logs; updates results/latest.
PX4 invocation and client commands: GROUNDING.md A.17-A.21.
"""
import argparse
import datetime
import hashlib
import os
import pathlib
import random
import re
import signal
import subprocess
import sys
import time

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from check_run_contract import pinned_commits  # noqa: E402

PX4_DIR = pathlib.Path(os.environ.get("PX4_DIR", "/opt/PX4-Autopilot"))
PX4_BUILD = pathlib.Path(os.environ.get("PX4_BUILD", PX4_DIR / "build/px4_sitl_default"))
ARMING_STATE_ARMED = 2  # px4_msgs/msg/VehicleStatus.msg:12

# PX4 parameters every Guará run must pin, with the reason each one matters.
#
# COM_MODE_ARM_CHK: the firmware default is 0 ("Allow external mode registration while armed",
# commander_params.c:1048), but px4-rc.simulator overrides it to 1 for developer convenience
# (init.d-posix/px4-rc.simulator:8). ADR 0001 rule 6 and the FM-3 failure mode assume the flight
# default, so every run forces it back to 0 and records the value it read back. Before the review of
# 2026-09-11 this was not done, and AC-15c was recorded PASS against a run in which the in-flight
# re-registration had in fact succeeded (finding C-1).
REQUIRED_PX4_PARAMS = {"COM_MODE_ARM_CHK": 0}
POLL_S = 0.5
_RUN_LOG = None


def log(msg: str) -> None:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    line = f"[sitl_run] {stamp} {msg}"
    print(line, flush=True)
    if _RUN_LOG is not None:
        _RUN_LOG.write(line + "\n")
        _RUN_LOG.flush()


def px4_client(command: str, timeout_s: float = 10.0) -> subprocess.CompletedProcess:
    module, *args = command.split()
    return subprocess.run([str(PX4_BUILD / "bin" / f"px4-{module}"), *args],
                          capture_output=True, text=True, timeout=timeout_s)


def listener_field(topic: str, field: str):
    """Return the first value of `field` printed by `listener <topic>`, or None."""
    try:
        out = px4_client(f"listener {topic} -n 1").stdout
    except subprocess.TimeoutExpired:
        return None
    match = re.search(rf"^\s*{re.escape(field)}:\s*(\S+)", out, re.MULTILINE)
    return match.group(1) if match else None


def is_armed() -> bool:
    return listener_field("vehicle_status", "arming_state") == str(ARMING_STATE_ARMED)


def is_airborne() -> bool:
    return is_armed() and listener_field("vehicle_land_detected", "landed") in ("False", "0", "false")


NAV_LOITER = 4  # VehicleStatus.NAVIGATION_STATE_AUTO_LOITER
NAV_RTL = 5
NAV_POSCTL = 2
REGISTERED_RE = re.compile(r"registered '.*' \(executor id \d+, nav_state (\d+)\)")


def is_loiter() -> bool:
    return listener_field("vehicle_status", "nav_state") == str(NAV_LOITER)


def is_rtl() -> bool:
    return listener_field("vehicle_status", "nav_state") == str(NAV_RTL)


def is_posctl() -> bool:
    return listener_field("vehicle_status", "nav_state") == str(NAV_POSCTL)


CONDITIONS = {
    "airborne": is_airborne,
    "disarmed": lambda: listener_field("vehicle_status", "arming_state") not in (None, str(ARMING_STATE_ARMED)),
    "loiter": is_loiter,
    "rtl": is_rtl,
    "posctl": is_posctl,
}


def apply_px4_params(params: dict) -> dict:
    """Set each parameter and read it back; returns {name: {"set": v, "read_back": v}}."""
    applied = {}
    for name, value in params.items():
        px4_client(f"param set {name} {value}")
        read_back = px4_client(f"param show -q {name}").stdout.strip()
        try:
            read_back_value = int(read_back)
        except ValueError:
            read_back_value = read_back
        applied[name] = {"set": value, "read_back": read_back_value}
        log(f"param {name} := {value} (read back {read_back_value!r})")
        if read_back_value != value:
            raise RuntimeError(f"PX4 parameter {name} is {read_back_value!r}, expected {value!r}")
    return applied


def owned_nav_state(run_dir: pathlib.Path) -> int:
    log_path = run_dir / "guara_rta_node.log"
    text = log_path.read_text(errors="replace") if log_path.is_file() else ""
    matches = list(REGISTERED_RE.finditer(text))
    if not matches:
        raise RuntimeError(f"owned nav_state not found in {log_path}")
    return int(matches[-1].group(1))


def ros_action(*args: str) -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / "sitl" / "ros_action.py"), *args]
    timeout = 90.0
    if args and args[0] == "inject-cf":
        timeout = 120.0
    if args and args[0] == "fly-plan":
        timeout = 240.0
        if "--timeout" in args:
            timeout = float(args[args.index("--timeout") + 1]) + 30.0
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    log(f"ros_action {' '.join(args)} -> rc={result.returncode} {result.stderr.strip()[-200:]}")
    if result.returncode != 0:
        raise RuntimeError(f"ros_action failed: {' '.join(args)}")


def start_ros_node(spec: dict, run_dir: pathlib.Path, ros_procs: list, suffix: str = "") -> None:
    exe = spec["executable"]
    handle = (run_dir / f"{exe}{suffix}.log").open("w")
    cmd = ["ros2", "run", spec["package"], exe]
    ros_args: list[str] = []
    if spec.get("params_file"):
        ros_args += ["--params-file", str(ROOT / spec["params_file"])]
    extra = spec.get("extra_params_file")
    if extra:
        ros_args += ["--params-file", str(ROOT / extra)]
    for key, value in (spec.get("params") or {}).items():
        ros_args += ["--param", f"{key}:={value}"]
    if ros_args:
        cmd += ["--ros-args", *ros_args]
    proc = subprocess.Popen(cmd, stdout=handle, stderr=subprocess.STDOUT)
    ros_procs.append((exe + suffix, proc, handle))
    log(f"started ros2 run {spec['package']} {exe}{suffix}")


def run_steps(scenario: dict, run_dir: pathlib.Path, ros_procs: list) -> None:
    ready_timeout = scenario["timeouts_s"]["ready"]
    for step in scenario["steps"]:
        if "sleep_s" in step:
            log(f"sleep {step['sleep_s']} s")
            time.sleep(step["sleep_s"])
            continue
        if set(step) <= {"wait_until", "timeout_s"} and "wait_until" in step:
            cond, timeout_s = step["wait_until"], float(step.get("timeout_s", 15))
            if not wait_for(CONDITIONS[cond], timeout_s):
                raise RuntimeError(f"timeout waiting for '{cond}'")
            log(f"condition '{cond}' reached")
            continue
        if "user_nav_state" in step:
            nav = owned_nav_state(run_dir) if step["user_nav_state"] == "owned" else int(step["user_nav_state"])
            ros_action("set-nav-state", str(nav))
            cond = step.get("wait_until")
            timeout_s = float(step.get("timeout_s", 15))
            if cond == "owned":
                if ros_action_wait_nav(nav, timeout_s) != 0:
                    log("retry owned-mode SET_NAV_STATE")
                    ros_action("set-nav-state", str(nav))
                    if ros_action_wait_nav(nav, timeout_s) != 0:
                        raise RuntimeError("timeout waiting for owned nav_state")
            elif cond:
                if not wait_for(CONDITIONS[cond], timeout_s):
                    raise RuntimeError(f"timeout waiting for '{cond}' after user_nav_state")
                log(f"condition '{cond}' reached")
            continue
        if "inject_verdict" in step:
            spec = step["inject_verdict"]
            ros_action("inject-verdict", spec["monitor_id"], "--duration", str(spec.get("duration_s", 3)))
            continue
        if "inject_cf" in step:
            spec = step["inject_cf"]
            vel = spec["velocity_ned"]
            ros_action("inject-cf", str(vel[0]), str(vel[1]), str(vel[2]),
                       "--duration", str(spec.get("duration_s", 10)))
            continue
        if "fly_plan" in step:
            spec = step["fly_plan"]
            plan = str(ROOT / spec["file"])
            timeout_s = str(spec.get("timeout_s", 180))
            extra = ["--allow-incomplete"] if spec.get("allow_incomplete") else []
            if spec.get("until_north_m") is not None:
                extra += ["--until-north", str(spec["until_north_m"])]
            ros_action("fly-plan", plan, "--timeout", timeout_s, *extra)
            continue
        if "kill" in step:
            sig = int(step.get("signal", 9))
            name = step["kill"]
            log(f"kill -{sig} {name}")
            subprocess.run(["pkill", f"-{sig}", "-f", name], check=False)
            continue
        if "start" in step:
            name = step["start"]
            spec = next(s for s in scenario.get("ros_nodes", []) if s["executable"] == name)
            start_ros_node(spec, run_dir, ros_procs, suffix=step.get("log_suffix", "_restart"))
            continue
        if "wait_log" in step:
            path = run_dir / step["wait_log"]
            pattern = step["pattern"]
            timeout_s = float(step.get("timeout_s", 20))
            if not wait_for_log(path, pattern, timeout_s):
                raise RuntimeError(f"timeout waiting for {pattern!r} in {path.name}")
            log(f"log matched {pattern!r} in {path.name}")
            continue
        if "wait_rta" in step:
            if ros_action("wait-rta", str(step["wait_rta"]), "--timeout", str(step.get("timeout_s", 15))):
                pass  # ros_action raises on failure
            continue
        cmd, cond, timeout_s = step["cmd"], step["wait_until"], step["timeout_s"]
        condition = CONDITIONS[cond]
        deadline = time.monotonic() + max(timeout_s, ready_timeout)
        while True:
            result = px4_client(cmd)
            log(f"{cmd} -> rc={result.returncode} {result.stdout.strip()[-200:]}")
            if wait_for(condition, min(10.0, timeout_s)):
                log(f"condition '{cond}' reached")
                break
            if time.monotonic() > deadline:
                raise RuntimeError(f"timeout waiting for '{cond}' after '{cmd}'")


def ros_action_wait_nav(nav: int, timeout_s: float) -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / "sitl" / "ros_action.py"),
           "wait-nav", str(nav), "--timeout", str(timeout_s)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 10)
    log(f"wait-nav {nav} -> rc={result.returncode} {result.stderr.strip()[-200:]}")
    return result.returncode


def wait_for(predicate, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(POLL_S)
    return False


def wait_for_log(path: pathlib.Path, pattern: str, timeout_s: float) -> bool:
    return wait_for(lambda: path.exists() and pattern in path.read_text(errors="replace"), timeout_s)


def build_config(args, scenario: dict, scenario_path: pathlib.Path, run_id: str, created: str) -> dict:
    px4_commit = subprocess.run(["git", "-C", str(PX4_DIR), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
    return {
        "run_id": run_id,
        "created_utc": created,
        "scenario": scenario["name"],
        "scenario_sha256": hashlib.sha256(scenario_path.read_bytes()).hexdigest(),
        "seed": args.seed,
        "headless": True,
        "guara_sha": os.environ.get("GUARA_SHA", "unknown"),
        "guara_dirty": os.environ.get("GUARA_DIRTY", "unknown") == "true",
        "image_id": os.environ.get("GUARA_IMAGE_ID", "unknown"),
        "px4_build_commit": px4_commit,
        "third_party": pinned_commits(ROOT / "third_party" / "VERSIONS.md"),
        "simulator": {
            "PX4_SIMULATOR": scenario["vehicle"]["simulator"],
            "PX4_SIM_MODEL": scenario["vehicle"]["model"],
            "PX4_SIM_SPEED_FACTOR": scenario["vehicle"]["speed_factor"],
            "home": scenario["home"],
            "px4_noise_seed": "fixed srand(1234) in SensorBaroSim (GROUNDING A.20)",
        },
        "steps": scenario["steps"],
        "expect": scenario.get("expect", {}),
        # Filled in after boot by apply_px4_params; AC-2 checks it (scripts/check_run_contract.py).
        "px4_params": {},
    }


def stop(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        log(f"{name} did not exit on SIGINT; killing")
        proc.kill()
        proc.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--headless", action="store_true", required=True,
                        help="required: GUI simulation is not supported")
    parser.add_argument("--run-suffix", default="",
                        help="appended to the run_id (used by sitl_pair.sh)")
    parser.add_argument("--param", action="append", default=[], metavar="NAME:=VALUE",
                        help="extra ros2 parameter for guara_rta_node")
    args = parser.parse_args()

    scenario_path = ROOT / "scenarios" / f"{args.scenario}.yaml"
    scenario = yaml.safe_load(scenario_path.read_text())
    random.seed(args.seed)  # scenario-level randomness only; PX4 noise seed is fixed (A.20)
    extras = {}
    for item in args.param:
        if ":=" not in item:
            raise SystemExit(f"invalid --param {item!r}; expected NAME:=VALUE")
        key, value = item.split(":=", 1)
        extras[key] = value
    if extras:
        for spec in scenario.get("ros_nodes", []):
            if spec.get("executable") == "guara_rta_node":
                spec.setdefault("params", {}).update(extras)

    now = datetime.datetime.now(datetime.timezone.utc)
    created = now.isoformat(timespec="seconds")
    run_id = f"{now:%Y%m%dT%H%M%SZ}_{args.scenario}_s{args.seed}{args.run_suffix}"
    run_dir = ROOT / "results" / run_id
    px4_work = run_dir / "px4"
    px4_work.mkdir(parents=True)

    global _RUN_LOG
    _RUN_LOG = (run_dir / "sitl_run.log").open("w")
    config = build_config(args, scenario, scenario_path, run_id, created)
    (run_dir / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=True))
    latest = ROOT / "results" / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(run_id)
    log(f"run {run_id}")

    env = dict(os.environ,
               PX4_SIMULATOR=scenario["vehicle"]["simulator"],
               PX4_SIM_MODEL=scenario["vehicle"]["model"],
               PX4_SIM_SPEED_FACTOR=str(scenario["vehicle"]["speed_factor"]),
               PX4_HOME_LAT=str(scenario["home"]["lat"]),
               PX4_HOME_LON=str(scenario["home"]["lon"]),
               PX4_HOME_ALT=str(scenario["home"]["alt"]),
               HEADLESS="1")
    agent_log = (run_dir / "xrce_agent.log").open("w")
    px4_log_path = run_dir / "px4.log"
    px4_log = px4_log_path.open("w")
    agent = subprocess.Popen(["MicroXRCEAgent", "udp4", "-p", "8888"], stdout=agent_log, stderr=subprocess.STDOUT)
    px4 = subprocess.Popen([str(PX4_BUILD / "bin" / "px4"), "-d", "-w", str(px4_work), str(PX4_BUILD / "etc")],
                           env=env, stdout=px4_log, stderr=subprocess.STDOUT)
    ros_procs: list[tuple[str, subprocess.Popen]] = []
    status = 0
    try:
        if not wait_for_log(px4_log_path, "Startup script returned successfully",
                            scenario["timeouts_s"]["boot"]):
            raise RuntimeError("PX4 did not finish startup")
        px4_params = dict(REQUIRED_PX4_PARAMS)
        px4_params.update(scenario.get("px4_params", {}))
        config["px4_params"] = apply_px4_params(px4_params)
        (run_dir / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=True))
        wait_for_log(run_dir / "xrce_agent.log", "session", 15)
        if scenario.get("record_verdicts"):
            verdict_log = (run_dir / "record_verdicts.log").open("w")
            rec = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts" / "sitl" / "record_verdicts.py"),
                 str(run_dir / "verdicts.jsonl")],
                stdout=verdict_log, stderr=subprocess.STDOUT)
            ros_procs.append(("record_verdicts", rec, verdict_log))
        if scenario.get("record_events"):
            event_log = (run_dir / "record_events.log").open("w")
            rec_e = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts" / "sitl" / "record_events.py"),
                 str(run_dir / "events.jsonl")],
                stdout=event_log, stderr=subprocess.STDOUT)
            ros_procs.append(("record_events", rec_e, event_log))
        if scenario.get("record_latency"):
            lat_log = (run_dir / "record_latency.log").open("w")
            rec_l = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts" / "sitl" / "record_latency.py"),
                 str(run_dir / "events.jsonl"), str(run_dir / "states.jsonl")],
                stdout=lat_log, stderr=subprocess.STDOUT)
            ros_procs.append(("record_latency", rec_l, lat_log))
        for spec in scenario.get("ros_nodes", []):
            start_ros_node(spec, run_dir, ros_procs)
        if any(s.get("executable") == "guara_rta_node" for s in scenario.get("ros_nodes", [])):
            if not wait_for_log(run_dir / "guara_rta_node.log", "registered '", 30):
                raise RuntimeError("arbiter did not register with PX4")
            log(f"arbiter registered nav_state={owned_nav_state(run_dir)}")
        if ros_procs:
            time.sleep(2.0)
        run_steps(scenario, run_dir, ros_procs)
        log("scenario complete")
    except Exception as exc:  # report and still shut down cleanly
        log(f"FAIL {exc}")
        status = 1
    finally:
        for name, proc, handle in reversed(ros_procs):
            stop(proc, name)
            handle.close()
        stop(px4, "px4")
        stop(agent, "MicroXRCEAgent")
        agent_log.close()
        px4_log.close()
        ulogs = sorted(px4_work.rglob("*.ulg"))
        log(f"ulog files: {[str(p.relative_to(run_dir)) for p in ulogs]}")
        if _RUN_LOG is not None:
            _RUN_LOG.close()
            _RUN_LOG = None
    return status


if __name__ == "__main__":
    sys.exit(main())
