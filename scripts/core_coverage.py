#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Measure line coverage of core/src from a gcov build (AC-62).

The pass threshold is PARAMETER TBD. This script reports a number; it does
not decide whether that number is enough.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_gcov(path: Path) -> tuple[int, int]:
    hit = 0
    miss = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = raw.split(":", 2)
        if len(parts) < 2:
            continue
        count = parts[0].strip()
        try:
            lineno = int(parts[1].strip())
        except ValueError:
            continue
        if lineno == 0 or count == "-":
            continue
        if count.startswith("#####") or count.startswith("====="):
            miss += 1
            continue
        if count.endswith("*"):
            count = count[:-1]
        try:
            n = int(count)
        except ValueError:
            continue
        if n > 0:
            hit += 1
        else:
            miss += 1
    return hit, miss


def _source_name(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:8]:
        if "Source:" in line:
            return Path(line.split("Source:", 1)[1].strip()).name
    return None


def run_gcov(build: Path) -> list[Path]:
    notes = [p for p in build.rglob("*.gcno") if "guara_core.dir" in p.parts]
    if not notes:
        raise SystemExit(f"FAIL core_coverage: no guara_core.dir .gcno under {build}")
    # CMake names notes `foo.cpp.gcno`. Passing the source makes gcov look for
    # `foo.gcno` and fail; pass the notes file. gcov returns 1 when a
    # translation unit has no executable lines or no matching .gcda.
    for gcno in notes:
        subprocess.run(
            ["gcov", "-p", str(gcno)],
            cwd=build,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return sorted(build.glob("*.gcov"))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", required=True, type=Path)
    p.add_argument("--src", type=Path, default=None)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    src = args.src or (root / "core" / "src")
    src_names = {f.name for f in src.iterdir() if f.suffix in {".cpp", ".c"}}
    build = args.build.resolve()
    files = run_gcov(build)
    if not files:
        print("FAIL core_coverage: gcov produced no .gcov files", file=sys.stderr)
        return 1
    total_hit = 0
    total_miss = 0
    reported: set[str] = set()
    for gcov_path in files:
        name = _source_name(gcov_path)
        if name is None or name not in src_names or name in reported:
            continue
        hit, miss = parse_gcov(gcov_path)
        total = hit + miss
        pct = (100.0 * hit / total) if total else 0.0
        print(f"file {name} lines={total} hit={hit} pct={pct:.1f}")
        reported.add(name)
        total_hit += hit
        total_miss += miss
    total = total_hit + total_miss
    if total == 0:
        print("FAIL core_coverage: no executable lines in core/src", file=sys.stderr)
        return 1
    pct = 100.0 * total_hit / total
    print(f"total lines={total} hit={total_hit} pct={pct:.1f}")
    print("note measured line coverage of core/src; branch PARAMETER TBD; not a bound")
    return 0


if __name__ == "__main__":
    sys.exit(main())
