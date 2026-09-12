#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Every source file in this repository carries an SPDX identifier (CLAUDE.md, ADR 0006).

This is the check behind that rule. It reads the file list from git, so it never walks
third_party/ or an untracked build directory, and it looks only at the first few lines —
an SPDX tag further down is not the convention and does not count.

Four categories are exempt, and each exemption is a statement about who owns the bytes:

* `docs/evidence/**` — run artefacts published verbatim from `results/`. Editing one would
  break the contract that an evidence directory is a copy of what a run produced.
* `ros2_ws/src/guara_monitors/generated/**` — Copilot output. Editing it would break the
  regeneration equality the monitor pipeline depends on.
* `ros2_ws/src/guara_monitors/template/**` — the Ogma template this project customises;
  upstream-derived and kept close to it.
* `nosa/**` NOSA-licensed sources carry their own NASA header, not Apache-2.0. Files under
  `nosa/` written by this project still carry the Apache tag, so they are checked; the
  check simply accepts either identifier there.

Usage: python3 scripts/check_spdx.py [--fix-list]
Exit status 0 when every checked file carries a tag, 1 otherwise.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

SUFFIXES = {".py", ".cpp", ".hpp", ".h", ".c", ".sh", ".msg", ".yaml", ".yml", ".cmake"}
NAMES = {"CMakeLists.txt"}

EXEMPT_PREFIXES = (
    "docs/evidence/",
    "ros2_ws/src/guara_monitors/generated/",
    "ros2_ws/src/guara_monitors/template/",
)

HEADER_LINES = 5
TAG = "SPDX-License-Identifier"


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                         capture_output=True, text=True, check=True).stdout
    return out.splitlines()


def is_checked(path: str) -> bool:
    if path.startswith("third_party/") or any(path.startswith(p) for p in EXEMPT_PREFIXES):
        return False
    p = pathlib.PurePosixPath(path)
    return p.suffix in SUFFIXES or p.name in NAMES


def has_tag(path: str) -> bool:
    full = ROOT / path
    try:
        with full.open(encoding="utf-8", errors="replace") as fh:
            for _, line in zip(range(HEADER_LINES), fh):
                if TAG in line:
                    return True
    except OSError:
        return False
    return False


def main() -> int:
    checked = [f for f in tracked_files() if is_checked(f)]
    missing = [f for f in checked if not has_tag(f)]
    for f in missing:
        print(f"missing {TAG}: {f}")
    verb = "PASS" if not missing else "FAIL"
    print(f"{verb} SPDX: {len(checked) - len(missing)}/{len(checked)} checked files carry a tag "
          f"in the first {HEADER_LINES} lines")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
