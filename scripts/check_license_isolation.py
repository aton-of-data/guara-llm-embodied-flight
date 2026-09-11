#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-11: no package outside nosa/ depends on DAIDALUS or includes its headers (ADR 0003)."""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORBIDDEN_NAME = re.compile(r"daidalus|guara_daidalus", re.IGNORECASE)
HEADER = re.compile(r'#\s*include\s*[<"][^>"]*daidalus', re.IGNORECASE)
SKIP_DIRS = {".git", "build", "install", "log", "results", "third_party", "nosa"}


def iter_files(root: pathlib.Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".pdf", ".ulg", ".a", ".so", ".o"}:
            continue
        yield path


def check() -> list[str]:
    errors: list[str] = []
    for path in iter_files(ROOT):
        rel = path.relative_to(ROOT)
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        if path.name in {"package.xml", "CMakeLists.txt"} and FORBIDDEN_NAME.search(text):
            errors.append(f"{rel}: package/CMake references DAIDALUS outside nosa/")
        if HEADER.search(text):
            errors.append(f"{rel}: includes a DAIDALUS header")
    return errors


def main() -> int:
    errors = check()
    if errors:
        print("FAIL AC-11")
        for err in errors:
            print(err)
        return 1
    print("PASS AC-11: no DAIDALUS dependency or include outside nosa/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
