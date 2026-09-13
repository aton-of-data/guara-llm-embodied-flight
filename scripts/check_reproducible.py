#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reproducibility checks.

`--pins` (M17 / AC-52, gap G-S2): `versions.env` is the single pin source.
Stdlib only, so it runs before the Python layer is installed.

`--scenario` (AC-2b): run a scenario N times with the same seed and compare
`config.yaml`. Only `run_id` and `created_utc` may differ (SPEC §6). Each run
must also pass the AC-2 run contract.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOLATILE_KEYS = ("run_id", "created_utc")


def check_pins() -> int:
    import pins

    errors = pins.check(ROOT)
    if errors:
        for line in errors:
            print(f"FAIL {line}")
        print(f"FAIL pins: {len(errors)} drift(s) from versions.env")
        return 1
    print("PASS pins: versions.env matches Dockerfiles, requirements, "
          "requirements.lock, third_party/VERSIONS.md and fetch_third_party.sh")
    return 0


def check_scenario(scenario: str, seed: int, runs: int) -> int:
    import yaml
    import check_run_contract

    configs = []
    for i in range(runs):
        cmd = [str(ROOT / "scripts" / "sitl_run.sh"), "--scenario", scenario,
               "--seed", str(seed), "--headless"]
        print(f"run {i + 1}/{runs}: {' '.join(cmd)}", flush=True)
        if subprocess.run(cmd, cwd=ROOT).returncode != 0:
            print(f"FAIL run {i + 1} exited non-zero")
            return 1
        run_dir = (ROOT / "results" / "latest").resolve()
        errors = check_run_contract.check(run_dir)
        if errors:
            print(f"FAIL run {i + 1} ({run_dir.name}): {errors}")
            return 1
        config = yaml.safe_load((run_dir / "config.yaml").read_text())
        configs.append((run_dir.name, {k: v for k, v in config.items() if k not in VOLATILE_KEYS}))

    ref_name, ref = configs[0]
    ok = True
    for name, config in configs[1:]:
        if config != ref:
            ok = False
            diff = sorted(k for k in set(ref) | set(config) if ref.get(k) != config.get(k))
            print(f"FAIL {name} differs from {ref_name} in keys: {diff}")
    if not ok:
        return 1
    print(f"PASS reproducible config.yaml over {runs} runs: {[n for n, _ in configs]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pins", action="store_true",
                        help="verify versions.env is the single pin source (AC-52)")
    parser.add_argument("--scenario")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--runs", type=int, default=2)
    args = parser.parse_args()
    if args.pins:
        return check_pins()
    if not args.scenario or args.seed is None:
        parser.error("--scenario and --seed are required unless --pins")
    if args.runs < 2:
        parser.error("--runs must be >= 2")
    return check_scenario(args.scenario, args.seed, args.runs)


if __name__ == "__main__":
    sys.exit(main())
