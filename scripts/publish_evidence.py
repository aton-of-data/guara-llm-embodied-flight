#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Copy the reviewable part of a SITL run into docs/evidence/ (review of 2026-09-11).

results/ holds ULogs, PX4 working directories and process logs; it is gitignored and therefore
invisible to anyone who does not have this machine. The run contract (config.yaml), the metrics a
checker computed (metrics.json) and, for a pair or a batch, the index files are small, text, and are
exactly what a reviewer needs to see which build produced which number. This script publishes those
files, verbatim, under docs/evidence/<run_id>/.

Usage:
    ./scripts/publish_evidence.py results/latest [results/latest_pair ...]
    ./scripts/publish_evidence.py --all          # every run directory that has a metrics.json
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
EVIDENCE = ROOT / "docs" / "evidence"
PUBLISHED = ("config.yaml", "metrics.json", "pair.yaml", "runs.txt", "checks.txt")


def publish(run_dir: pathlib.Path) -> list[pathlib.Path]:
    run_dir = run_dir.resolve()
    out = EVIDENCE / run_dir.name
    written = []
    for name in PUBLISHED:
        src = run_dir / name
        if not src.is_file():
            continue
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out / name)
        written.append(out / name)
    # A pair directory holds two symlinked members; publish their contracts as well.
    for member in ("rta_on", "rta_off"):
        if (run_dir / member).is_dir():
            for path in publish((run_dir / member).resolve()):
                written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dirs", nargs="*", type=pathlib.Path)
    parser.add_argument("--all", action="store_true",
                        help="publish every results/ directory that has a metrics.json")
    args = parser.parse_args()

    targets = list(args.run_dirs)
    if args.all:
        targets += sorted({p.parent for p in RESULTS.glob("*/metrics.json")})
    if not targets:
        parser.error("give at least one run directory, or --all")

    written = []
    for run_dir in targets:
        if not run_dir.is_dir():
            print(f"skip {run_dir}: not a directory", file=sys.stderr)
            continue
        written += publish(run_dir)
    for path in written:
        print(path.relative_to(ROOT))
    print(f"{len(written)} file(s) published under {EVIDENCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
