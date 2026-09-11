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


def check_ac11(_path: pathlib.Path) -> list[str]:
    """ADR 0003: no DAIDALUS dependency outside nosa/."""
    script = ROOT / "scripts" / "check_license_isolation.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if result.returncode != 0:
        return [result.stdout + result.stderr]
    return []


CHECKERS = {
    "AC-3": check_ac3,
    "AC-11": check_ac11,
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
