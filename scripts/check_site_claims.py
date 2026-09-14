#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The site says what the repository says.

`scripts/check_site_links.py` proves that the site's internal references resolve. This is the
other half: that what the pages *claim* still matches the documents that own the claim. The
site is hand-written static HTML published from `site/`, so nothing else notices when a page
and its authority drift apart — and under this project's evidence discipline a published
number that no longer follows from its source is a defect of the same severity as a crash.

Four classes of claim are checked, and nothing else:

* The commit stamp. Every page carries a `Describes commit` line. It must name a real
  commit, that commit must be an ancestor of `HEAD`, every page must carry the same one,
  and it must be within `MAX_DRIFT` commits of `HEAD`. The stamp is a claim about which
  tree the page describes; a stale one is a false statement, not a cosmetic lapse.
* The acceptance-criteria tallies on `evidence.html`, against `docs/milestones/STATUS.md`:
  the three state counts, the re-run count, the highest criterion and the thread letters.
* Identifiers. Every `AC-`, `FM-`, `R-`, `RP-`, `RS-`, `RH-` and gap-register row named
  anywhere in `site/` must exist in the document that owns it.
* The entry path. The install line taught on the site must be the one the README teaches.

Usage: python3 scripts/check_site_claims.py
Exit status 0 when every claim holds, 1 otherwise.
"""
from __future__ import annotations

import collections
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
STATUS = ROOT / "docs" / "milestones" / "STATUS.md"

# How far a page may lag the tree before the stamp is a false claim rather than a rounding
# error. Documentation commits legitimately land after the stamp they carry; a release of
# work the page does not describe does not.
MAX_DRIFT = 25

STAMP = re.compile(r"<dt>Describes commit</dt><dd>([0-9a-f]{7,40})</dd>")
TAG = re.compile(r"<[^>]+>")

# Each identifier family, the document that owns it, and the pattern that finds a definition
# there. A definition is a leading table cell: the register and the risk tables are tables.
FAMILIES = {
    "AC": (STATUS, re.compile(r"^\|\s*(AC-[0-9]+[a-z]?)\s*\|", re.M)),
    "FM": (ROOT / "docs/SPEC.md", re.compile(r"^\|\s*(FM-[0-9]+)\s*\|", re.M)),
    "R": (ROOT / "docs/SPEC.md", re.compile(r"^\|\s*(R-[0-9]+)\s*\|", re.M)),
    "RP": (ROOT / "docs/PLAN-M8-M16.md", re.compile(r"^\|\s*(RP-[0-9]+)\s*\|", re.M)),
    "RS": (ROOT / "docs/research/SPACE-AUTONOMY.md",
           re.compile(r"^\|\s*(RS-[0-9]+)\s*\|", re.M)),
    "RH": (ROOT / "docs/PLAN-M17-M28.md", re.compile(r"^\|\s*(RH-[0-9]+)\s*\|", re.M)),
    "G": (ROOT / "docs/PLAN-M17-M28.md",
          re.compile(r"^\|\s*\*{0,2}(G-[A-Z][0-9]+)\*{0,2}\s*\|", re.M)),
}
# The same families as they appear in prose on a page.
CITED = re.compile(r"\b(AC-[0-9]+[a-z]?|FM-[0-9]+|R-[0-9]+|RP-[0-9]+|RS-[0-9]+|RH-[0-9]+"
                   r"|G-[A-Z][0-9]+)\b")


def git(*args: str) -> str:
    return subprocess.run(("git", "-C", str(ROOT)) + args,
                          capture_output=True, text=True).stdout.strip()


def text_of(page: pathlib.Path) -> str:
    body = re.sub(r"<(script|style).*?</\1>", " ", page.read_text(encoding="utf-8"),
                  flags=re.S)
    return re.sub(r"\s+", " ", TAG.sub(" ", body))


def status_tally() -> dict[str, object]:
    """What `STATUS.md` actually records, computed rather than transcribed."""
    whole = STATUS.read_text(encoding="utf-8")
    executed, planned = whole.split("## Planned criteria")
    rows = [r for r in executed.splitlines() if re.match(r"^\| AC-", r)]
    states: collections.Counter[str] = collections.Counter()
    for row in rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        states["PASS" if cells[3].startswith("PASS") else cells[3]] += 1
    # The thread letter is the second cell of every row in both tables: a thread the site
    # must account for exists whether its criteria are executed or still planned.
    threads = {
        [c.strip() for c in row.strip().strip("|").split("|")][1]
        for row in whole.splitlines() if re.match(r"^\| AC-", row)}
    every = FAMILIES["AC"][1].findall(whole)
    return {
        "pass": states["PASS"],
        "in progress": states["in progress"],
        "planned": len([r for r in planned.splitlines() if re.match(r"^\| AC-", r)]),
        "re-run": whole.count("PASS (re-run 2026-09-11)"),
        "threads": len(threads),
        "last": max(every, key=lambda a: int(re.sub(r"\D", "", a))),
    }


def check_stamps(pages: list[pathlib.Path], problems: list[str]) -> None:
    head = git("rev-parse", "HEAD")
    stamps: dict[str, list[str]] = collections.defaultdict(list)
    for page in pages:
        found = STAMP.findall(page.read_text(encoding="utf-8"))
        if not found:
            problems.append(f"{page.name}: no 'Describes commit' stamp")
            continue
        stamps[found[0]].append(page.name)

    if len(stamps) > 1:
        joined = "; ".join(f"{s} on {', '.join(p)}" for s, p in sorted(stamps.items()))
        problems.append(f"pages disagree about the commit they describe: {joined}")

    for stamp in stamps:
        full = git("rev-parse", "--verify", f"{stamp}^{{commit}}")
        if not full:
            problems.append(f"stamp {stamp} is not a commit in this repository")
            continue
        ancestor = subprocess.run(
            ("git", "-C", str(ROOT), "merge-base", "--is-ancestor", stamp, head))
        if ancestor.returncode != 0:
            problems.append(f"stamp {stamp} is not an ancestor of HEAD")
            continue
        drift = int(git("rev-list", "--count", f"{stamp}..HEAD"))
        if drift > MAX_DRIFT:
            problems.append(
                f"stamp {stamp} is {drift} commits behind HEAD (limit {MAX_DRIFT}): the "
                f"pages claim to describe a tree that is no longer this one")


def check_tallies(problems: list[str]) -> None:
    page = SITE / "evidence.html"
    if not page.is_file():
        problems.append("evidence.html is missing")
        return
    body = text_of(page)
    want = status_tally()

    for label, count in (("PASS", want["pass"]), ("in progress", want["in progress"]),
                         ("planned", want["planned"])):
        if f"{count} " not in body and f">{count}<" not in page.read_text(encoding="utf-8"):
            problems.append(
                f"evidence.html does not state {count} for '{label}', which is what "
                f"STATUS.md records")

    stated = re.search(r"AC PASS · ([0-9]+) in progress · ([0-9]+) planned", body)
    if not stated:
        problems.append("evidence.html has no 'n AC PASS · n in progress · n planned' line")
    elif (int(stated.group(1)), int(stated.group(2))) != (want["in progress"],
                                                          want["planned"]):
        problems.append(
            f"evidence.html status line says {stated.group(1)} in progress and "
            f"{stated.group(2)} planned; STATUS.md records {want['in progress']} and "
            f"{want['planned']}")

    if f"AC-1…{want['last']}" not in body:
        problems.append(
            f"evidence.html does not state the tracker range as AC-1…{want['last']}, which "
            f"is the highest criterion in STATUS.md")

    if re.search(r"across (\w+) threads", body):
        words = {4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
        want_word = words.get(want["threads"], str(want["threads"]))
        if f"across {want_word} threads" not in body:
            problems.append(
                f"evidence.html states the wrong thread count; STATUS.md defines "
                f"{want['threads']} ({want_word})")

    if f"{want['re-run']} are marked" not in body:
        problems.append(
            f"evidence.html does not state {want['re-run']} rows marked "
            f"'re-run 2026-09-11'; that is how many STATUS.md carries")


def check_identifiers(pages: list[pathlib.Path], problems: list[str]) -> None:
    known: dict[str, set[str]] = {}
    for family, (doc, pattern) in FAMILIES.items():
        if not doc.is_file():
            problems.append(f"authority document missing: {doc.relative_to(ROOT)}")
            known[family] = set()
            continue
        known[family] = set(pattern.findall(doc.read_text(encoding="utf-8")))

    for page in pages:
        for ident in sorted(set(CITED.findall(text_of(page)))):
            family = ident.split("-")[0] if not ident.startswith("G-") else "G"
            if ident not in known.get(family, set()):
                doc = FAMILIES[family][0].relative_to(ROOT)
                problems.append(f"{page.name}: {ident} is not defined in {doc}")


def check_entry_path(pages: list[pathlib.Path], problems: list[str]) -> None:
    """The site must not teach an install the README has moved off."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "pip install -e ." not in readme:
        problems.append("README no longer teaches 'pip install -e .'; this check is stale")
        return
    for page in pages:
        body = page.read_text(encoding="utf-8")
        if "pip install" not in body:
            continue
        if "pip install -e ." not in body:
            problems.append(
                f"{page.name}: teaches an install path without 'pip install -e .', which is "
                f"the path README §9 leads with")


def main() -> int:
    if not SITE.is_dir():
        print(f"no site directory at {SITE}", file=sys.stderr)
        return 1
    pages = sorted(SITE.rglob("*.html"))
    problems: list[str] = []

    check_stamps(pages, problems)
    check_tallies(problems)
    check_identifiers(pages, problems)
    check_entry_path(pages, problems)

    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f"{len(problems)} claim(s) on the site no longer match the repository",
              file=sys.stderr)
        return 1
    print(f"every claim checked holds across {len(pages)} page(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
