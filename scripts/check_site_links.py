#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Every internal link and asset reference in site/ resolves.

The project site is hand-written static HTML with no build step, which means a renamed file
or a mistyped fragment fails silently in a browser rather than loudly in CI. This is the
check that makes it loud. It is the site-side counterpart of `scripts/check_links.py`,
which does the same job for the relative links between markdown documents.

Three classes of reference are checked, and nothing else:

* `href` / `src` pointing at a file in `site/` — the file must exist.
* `href="#fragment"` and `href="page.html#fragment"` — the id must exist in that page.
* Nothing external. An `http(s)://` or `mailto:` target is not this script's business;
  reaching the network from a check would make the result depend on the weather.

Usage: python3 scripts/check_site_links.py
Exit status 0 when every internal reference resolves, 1 otherwise.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

REF = re.compile(r'(?:href|src)\s*=\s*"([^"]+)"', re.I)
ID = re.compile(r'\bid\s*=\s*"([^"]+)"', re.I)
EXTERNAL = ("http://", "https://", "mailto:", "data:", "//")


def ids_of(path: pathlib.Path) -> set[str]:
    return set(ID.findall(path.read_text(encoding="utf-8")))


def main() -> int:
    if not SITE.is_dir():
        print(f"no site directory at {SITE}", file=sys.stderr)
        return 1

    pages = sorted(SITE.rglob("*.html"))
    id_cache: dict[pathlib.Path, set[str]] = {}
    problems: list[str] = []

    for page in pages:
        text = page.read_text(encoding="utf-8")
        for raw in REF.findall(text):
            ref = raw.strip()
            if not ref or ref.startswith(EXTERNAL):
                continue

            target, _, fragment = ref.partition("#")
            if target:
                resolved = (page.parent / target).resolve()
                if not resolved.is_file():
                    problems.append(f"{page.relative_to(ROOT)}: missing target {ref}")
                    continue
            else:
                resolved = page  # a bare "#fragment" points into this page

            if fragment:
                if resolved.suffix.lower() != ".html":
                    continue
                if resolved not in id_cache:
                    id_cache[resolved] = ids_of(resolved)
                if fragment not in id_cache[resolved]:
                    problems.append(
                        f"{page.relative_to(ROOT)}: no id '{fragment}' in "
                        f"{resolved.relative_to(ROOT)}")

    for problem in problems:
        print(problem, file=sys.stderr)

    checked = len(pages)
    if problems:
        print(f"{len(problems)} unresolved reference(s) across {checked} page(s)",
              file=sys.stderr)
        return 1
    print(f"every internal reference resolves across {checked} page(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
