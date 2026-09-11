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
POLL_S = 0.5


def log(msg: str) -> None:
    print(f"[sitl_run] {msg}", flush=True)


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


CONDITIONS = {
    "airborne": is_airborne,
    "disarmed": lambda: listener_field("vehicle_status", "arming_state") not in (None, str(ARMING_STATE_ARMED)),
}


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
    }


def run_steps(scenario: dict) -> None:
    ready_timeout = scenario["timeouts_s"]["ready"]
    for step in scenario["steps"]:
        if "sleep_s" in step:
            log(f"sleep {step['sleep_s']} s")
            time.sleep(step["sleep_s"])
            continue
        cmd, cond, timeout_s = step["cmd"], step["wait_until"], step["timeout_s"]
        condition = CONDITIONS[cond]
        deadline = time.monotonic() + max(timeout_s, ready_timeout)
        # Takeoff is rejected until preflight checks pass; resend until the condition holds.
        while True:
            result = px4_client(cmd)
            log(f"{cmd} -> rc={result.returncode} {result.stdout.strip()[-200:]}")
            if wait_for(condition, min(10.0, timeout_s)):
                log(f"condition '{cond}' reached")
                break
            if time.monotonic() > deadline:
                raise RuntimeError(f"timeout waiting for '{cond}' after '{cmd}'")


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
    args = parser.parse_args()

    scenario_path = ROOT / "scenarios" / f"{args.scenario}.yaml"
    scenario = yaml.safe_load(scenario_path.read_text())
    random.seed(args.seed)  # scenario-level randomness only; PX4 noise seed is fixed (A.20)

    now = datetime.datetime.now(datetime.timezone.utc)
    created = now.isoformat(timespec="seconds")
    run_id = f"{now:%Y%m%dT%H%M%SZ}_{args.scenario}_s{args.seed}"
    run_dir = ROOT / "results" / run_id
    px4_work = run_dir / "px4"
    px4_work.mkdir(parents=True)

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
        wait_for_log(run_dir / "xrce_agent.log", "session", 15)
        if scenario.get("record_verdicts"):
            verdict_log = (run_dir / "record_verdicts.log").open("w")
            rec = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts" / "sitl" / "record_verdicts.py"),
                 str(run_dir / "verdicts.jsonl")],
                stdout=verdict_log, stderr=subprocess.STDOUT)
            ros_procs.append(("record_verdicts", rec, verdict_log))
        for spec in scenario.get("ros_nodes", []):
            node_log = (run_dir / f"{spec['executable']}.log").open("w")
            proc = subprocess.Popen(
                ["ros2", "run", spec["package"], spec["executable"]],
                stdout=node_log, stderr=subprocess.STDOUT)
            ros_procs.append((spec["executable"], proc, node_log))
            log(f"started ros2 run {spec['package']} {spec['executable']}")
        if ros_procs:
            time.sleep(2.0)
        run_steps(scenario)
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
    return status


if __name__ == "__main__":
    sys.exit(main())
