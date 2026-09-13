#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-61: the exported C ABI matches the committed baseline.

A release fails if the GUARA_API symbol set changes without the corresponding
ABI version bump *and* a baseline rewrite. Stdlib only.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER = ROOT / "core" / "include" / "guara" / "guara.h"
DEFAULT_BASELINE = ROOT / "core" / "abi_symbols.txt"

API_RE = re.compile(r"GUARA_API[\s\w\*]+\b(guara_[a-z0-9_]+)\s*\(")
VER_RE = re.compile(r'#define\s+GUARA_ABI_VERSION\s+"([^"]+)"')


def parse_header(path: pathlib.Path) -> tuple[str, list[str]]:
    text = path.read_text(encoding="utf-8")
    ver = VER_RE.search(text)
    if ver is None:
        raise ValueError(f"{path}: no GUARA_ABI_VERSION")
    names = sorted(set(API_RE.findall(text)))
    return ver.group(1), names


def parse_baseline(path: pathlib.Path) -> tuple[str, list[str]]:
    ver = None
    names: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("abi:"):
            ver = line.split(":", 1)[1].strip()
            continue
        names.append(line)
    if ver is None:
        raise ValueError(f"{path}: no 'abi:' line")
    return ver, sorted(names)


def check(header: pathlib.Path, baseline: pathlib.Path) -> list[str]:
    errors: list[str] = []
    h_ver, h_names = parse_header(header)
    b_ver, b_names = parse_baseline(baseline)
    added = sorted(set(h_names) - set(b_names))
    removed = sorted(set(b_names) - set(h_names))
    if h_ver != b_ver:
        errors.append(f"ABI version {h_ver!r} != baseline {b_ver!r}")
    if added:
        errors.append("symbols added: " + ", ".join(added))
    if removed:
        errors.append("symbols removed: " + ", ".join(removed))
    if (added or removed) and h_ver == b_ver:
        errors.append("symbol set changed without an ABI version bump")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=pathlib.Path, default=DEFAULT_BASELINE)
    parser.add_argument("--header", type=pathlib.Path, default=HEADER)
    args = parser.parse_args()
    try:
        errors = check(args.header, args.baseline)
    except (OSError, ValueError) as exc:
        print(f"FAIL abi: {exc}")
        return 1
    if errors:
        for e in errors:
            print(f"FAIL {e}")
        print("FAIL abi: header and core/abi_symbols.txt disagree")
        return 1
    ver, names = parse_header(args.header)
    print(f"PASS abi {ver}: {len(names)} exported symbols match the baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
