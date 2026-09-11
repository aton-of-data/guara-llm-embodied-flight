#!/usr/bin/env python3
"""AC-2: verify the run contract of one SITL run directory (SPEC §6).

Checks config.yaml (seed, pinned third_party commits, Guará SHA, PX4 build commit)
and that at least one valid ULog was written. If the scenario declares
`expect.min_altitude_m`, the ULog must show the vehicle reached it.
"""
import argparse
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
ULOG_MAGIC = b"ULog\x01\x12\x35"
STARTUP_ERROR = re.compile(r"ERROR \[param\]|rcS: \d+: .*not found")
REQUIRED_KEYS = (
    "run_id", "created_utc", "scenario", "scenario_sha256", "seed", "headless",
    "guara_sha", "guara_dirty", "image_id", "px4_build_commit", "third_party", "simulator",
)


def pinned_commits(versions_md: pathlib.Path) -> dict:
    """Parse the pinned-commit table in third_party/VERSIONS.md."""
    commits = {}
    for line in versions_md.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4:
            match = re.fullmatch(r"`([0-9a-f]{40})`", cells[3])
            if match:
                commits[cells[0]] = match.group(1)
    return commits


def max_altitude_m(ulog_path: pathlib.Path) -> float:
    from pyulog import ULog  # installed by PX4 Tools/setup/requirements.txt

    ulog = ULog(str(ulog_path), message_name_filter_list=["vehicle_local_position"])
    datasets = [d for d in ulog.data_list if d.name == "vehicle_local_position"]
    if not datasets or len(datasets[0].data["z"]) == 0:
        return float("nan")
    return float(-min(datasets[0].data["z"]))  # NED: altitude = -z


def check(run_dir: pathlib.Path) -> list:
    errors = []
    config_path = run_dir / "config.yaml"
    if not config_path.is_file():
        return [f"missing {config_path}"]
    config = yaml.safe_load(config_path.read_text()) or {}

    for key in REQUIRED_KEYS:
        if key not in config:
            errors.append(f"config.yaml missing key: {key}")
    if errors:
        return errors

    if not isinstance(config["seed"], int):
        errors.append("seed must be an integer")
    if not re.fullmatch(r"[0-9a-f]{40}", str(config["guara_sha"])):
        errors.append(f"guara_sha is not a commit SHA: {config['guara_sha']}")

    expected = pinned_commits(ROOT / "third_party" / "VERSIONS.md")
    if config["third_party"] != expected:
        errors.append(f"third_party commits differ from VERSIONS.md: {config['third_party']} != {expected}")
    if config["px4_build_commit"] != expected.get("PX4-Autopilot"):
        errors.append(f"px4_build_commit {config['px4_build_commit']} != pinned PX4-Autopilot commit")

    px4_log = run_dir / "px4.log"
    if not px4_log.is_file():
        errors.append(f"missing {px4_log}")
    else:
        for line in px4_log.read_text(errors="replace").splitlines():
            # Startup script errors silently leave parameters at defaults (GROUNDING A.22).
            if STARTUP_ERROR.search(line):
                errors.append(f"px4.log startup error: {line.strip()}")

    ulogs = sorted(run_dir.rglob("*.ulg"))
    valid = [p for p in ulogs if p.stat().st_size > len(ULOG_MAGIC) and p.read_bytes()[:7] == ULOG_MAGIC]
    if not valid:
        errors.append(f"no valid .ulg under {run_dir} (found {len(ulogs)} file(s))")
        return errors

    min_alt = (config.get("expect") or {}).get("min_altitude_m")
    if min_alt is not None:
        reached = max(max_altitude_m(p) for p in valid)
        if not reached >= float(min_alt):
            errors.append(f"max altitude {reached:.2f} m < expected {min_alt} m")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=pathlib.Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    errors = check(run_dir)
    for err in errors:
        print(f"FAIL {err}")
    if errors:
        return 1
    print(f"PASS run contract: {run_dir.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
