#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-2b: run a scenario N times with the same seed and compare config.yaml.

Only `run_id` and `created_utc` may differ (SPEC §6). Each run must also pass
the AC-2 run contract.
"""
import argparse
import pathlib
import subprocess
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_run_contract  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOLATILE_KEYS = ("run_id", "created_utc")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--runs", type=int, default=2)
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs must be >= 2")

    configs = []
    for i in range(args.runs):
        cmd = [str(ROOT / "scripts" / "sitl_run.sh"), "--scenario", args.scenario,
               "--seed", str(args.seed), "--headless"]
        print(f"run {i + 1}/{args.runs}: {' '.join(cmd)}", flush=True)
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
    print(f"PASS reproducible config.yaml over {args.runs} runs: {[n for n, _ in configs]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
