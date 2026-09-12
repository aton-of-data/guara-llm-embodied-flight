#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Every relative link in a Markdown document points at something that exists.

The README is the map of this repository and the documents cross-reference each other
heavily; a moved file turns that map into a set of 404s silently. This check reads the
tracked Markdown files and resolves each relative link target against the tree.

External links (http/https/mailto) are not fetched — a network check would make the result
depend on someone else's uptime.

Anchors are checked too, against GitHub's slug rule: lowercase, drop everything that is not a
word character, whitespace or a hyphen, then replace each space with a hyphen — each space, not
each run, which is why a heading like `## 7 · Limits` anchors as `#7--limits`. Renumbering a
section silently invalidates every link into it, and that is exactly what this catches.

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

SKIP_SCHEMES = ("http://", "https://", "mailto:", "ftp://")

HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
EXPLICIT_ANCHOR = re.compile(r'<a id="([^"]+)"')
NOT_SLUG = re.compile(r"[^\w\s-]", re.UNICODE)


def slug(heading: str) -> str:
    """GitHub's anchor rule. Each space becomes a hyphen, so a run becomes several."""
    return NOT_SLUG.sub("", heading.strip().lower()).strip().replace(" ", "-")


def anchors_of(text: str) -> set[str]:
    return ({slug(m.group(1)) for m in HEADING.finditer(text)}
            | set(EXPLICIT_ANCHOR.findall(text)))


def tracked_markdown() -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.md"],
                         capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if not f.startswith("third_party/")]


def targets(text: str):
    yield from INLINE.findall(text)
    yield from REFERENCE.findall(text)


def main() -> int:
    docs = tracked_markdown()
    text_of = {rel: (ROOT / rel).read_text(encoding="utf-8", errors="replace") for rel in docs}
    anchor_of = {rel: anchors_of(t) for rel, t in text_of.items()}

    broken: list[tuple[str, str, str]] = []
    checked = anchors_checked = 0
    for rel, text in text_of.items():
        doc = ROOT / rel
        for target in targets(text):
            if target.startswith(SKIP_SCHEMES):
                continue
            path_part, _, fragment = target.partition("#")
            path_part = urllib.parse.unquote(path_part)

            if path_part:
                checked += 1
                resolved = (doc.parent / path_part).resolve()
                if not resolved.exists():
                    broken.append((rel, target, "no such file"))
                    continue
                try:
                    other = str(resolved.relative_to(ROOT))
                except ValueError:
                    continue
            else:
                other = rel  # a bare #fragment points inside this document

            if fragment and other in anchor_of:
                anchors_checked += 1
                if urllib.parse.unquote(fragment) not in anchor_of[other]:
                    broken.append((rel, target, "no such anchor"))

    for where, target, why in broken:
        print(f"broken link ({why}): {where} -> {target}")
    verb = "PASS" if not broken else "FAIL"
    print(f"{verb} links: {checked} relative links and {anchors_checked} anchors checked "
          f"across {len(docs)} Markdown files, {len(broken)} broken")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
