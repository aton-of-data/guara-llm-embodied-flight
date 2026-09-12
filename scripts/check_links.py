#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Every relative link in a Markdown document points at something that exists.

The README is the map of this repository and the documents cross-reference each other
heavily; a moved file turns that map into a set of 404s silently. This check reads the
tracked Markdown files and resolves each relative link target against the tree.

External links (http/https/mailto) are not fetched — a network check would make the result
depend on someone else's uptime. Anchors are checked only for existence of the file part;
`docs/SPEC.md#5` passes when `docs/SPEC.md` exists.

Usage: python3 scripts/check_links.py
Exit status 0 when every relative link resolves, 1 otherwise.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]

# [text](target) and [text]: target, ignoring images the same way — a broken image is a
# broken link. Targets in backticks inside the text part do not match; the target group
# stops at the first whitespace or closing paren.
INLINE = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)")
REFERENCE = re.compile(r"^\[[^\]]+\]:\s*(\S+)", re.MULTILINE)

SKIP_SCHEMES = ("http://", "https://", "mailto:", "ftp://", "#")


def tracked_markdown() -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.md"],
                         capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if not f.startswith("third_party/")]


def targets(text: str):
    yield from INLINE.findall(text)
    yield from REFERENCE.findall(text)


def main() -> int:
    broken: list[tuple[str, str]] = []
    checked = 0
    for rel in tracked_markdown():
        doc = ROOT / rel
        text = doc.read_text(encoding="utf-8", errors="replace")
        for target in targets(text):
            if target.startswith(SKIP_SCHEMES):
                continue
            path_part = urllib.parse.unquote(target.split("#", 1)[0])
            if not path_part:
                continue
            checked += 1
            resolved = (doc.parent / path_part).resolve()
            if not resolved.exists():
                broken.append((rel, target))

    for where, target in broken:
        print(f"broken link: {where} -> {target}")
    verb = "PASS" if not broken else "FAIL"
    print(f"{verb} links: {checked - len(broken)}/{checked} relative links resolve "
          f"across {len(tracked_markdown())} Markdown files")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
