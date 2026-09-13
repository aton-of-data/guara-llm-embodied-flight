#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The agent pipeline describes itself accurately (docs/AGENT-PIPELINE.md).

The process lives on two surfaces — Claude Code skills under `.claude/skills/` and editor
rules under `.cursor/rules/` — that carry the same invariants to two different loaders. They
drift silently: a renamed script, a moved template or a rule file that lost its front matter
costs nothing at edit time and everything at the moment an agent is supposed to be bound by it.
This check is what makes the mirror a fact rather than an intention.

It verifies four things:

* every skill directory holds a `SKILL.md` whose front matter declares `name` (equal to the
  directory) and a non-empty `description`, which is what the loader dispatches on;
* every `.mdc` rule declares `description` and `alwaysApply`, since a rule attached by neither
  is loaded by nothing;
* every repository path quoted in those documents resolves in the tree — a token holding a
  `<...>` placeholder is a pattern, not a reference, and is skipped;
* every `scripts/*` command these documents name exists — inside a fenced gate block as well
  as in prose, since that is where the gates themselves are written — so a gate cannot be
  cited after the script behind it is gone.

Usage: python3 scripts/check_pipeline.py [--root DIR]
Exit status 0 when the surfaces agree with the tree, 1 otherwise.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

QUOTED = re.compile(r"`([^`\n]+)`")
PLACEHOLDER = re.compile(r"[<>*]")
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

# A quoted token is a path reference when it holds a separator and either a suffix this
# repository uses or a first segment that is a real directory. `N/A` is a verdict, not a
# path, and the second condition is what tells them apart.
SUFFIXES = {".md", ".mdc", ".py", ".sh", ".cpp", ".hpp", ".yaml", ".yml", ".txt", ".json"}

# Gate commands live in fenced blocks, which carry no backticks of their own.
COMMAND = re.compile(r"\bscripts/[\w./-]+\.(?:py|sh)")


def front_matter(text: str) -> dict[str, str] | None:
    m = FRONT_MATTER.match(text)
    if not m:
        return None
    fields: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def quoted_tokens(text: str):
    for token in QUOTED.findall(text):
        token = token.strip()
        if "/" not in token or " " in token or PLACEHOLDER.search(token):
            continue
        if token.startswith(("http://", "https://", "repo@")):
            continue
        yield token.rstrip(".,;:")


def is_reference(token: str, root: pathlib.Path, doc: pathlib.Path) -> bool:
    if pathlib.PurePosixPath(token).suffix in SUFFIXES:
        return True
    head = token.split("/", 1)[0]
    return (root / head).is_dir() or (doc.parent / head).is_dir()


def resolve(token: str, root: pathlib.Path, doc: pathlib.Path) -> bool:
    """Root-relative first, then relative to the document that quoted it."""
    return (root / token).exists() or (doc.parent / token).exists()


def check(root: pathlib.Path) -> tuple[list[str], int, int, int]:
    skills_dir = root / ".claude" / "skills"
    rules_dir = root / ".cursor" / "rules"
    quality_bar = skills_dir / "guara-pipeline" / "references" / "quality-bar.md"
    problems: list[str] = []
    checked = 0

    if not skills_dir.is_dir() or not rules_dir.is_dir():
        return ([f"expected {skills_dir} and {rules_dir}"], 0, 0, 0)

    skills = sorted(p for p in skills_dir.iterdir() if p.is_dir())
    for skill in skills:
        doc = skill / "SKILL.md"
        if not doc.is_file():
            problems.append(f"{skill.relative_to(root)}: no SKILL.md")
            continue
        fields = front_matter(doc.read_text(encoding="utf-8"))
        if fields is None:
            problems.append(f"{doc.relative_to(root)}: no front matter")
            continue
        if fields.get("name") != skill.name:
            problems.append(f"{doc.relative_to(root)}: name is {fields.get('name')!r}, "
                            f"directory is {skill.name!r}")
        if not fields.get("description"):
            problems.append(f"{doc.relative_to(root)}: empty description")

    rules = sorted(rules_dir.glob("*.mdc"))
    for rule in rules:
        fields = front_matter(rule.read_text(encoding="utf-8"))
        if fields is None:
            problems.append(f"{rule.relative_to(root)}: no front matter")
            continue
        if not fields.get("description"):
            problems.append(f"{rule.relative_to(root)}: empty description")
        if fields.get("alwaysApply") not in {"true", "false"}:
            problems.append(f"{rule.relative_to(root)}: alwaysApply must be true or false")

    documents = sorted(skills_dir.rglob("*.md")) + list(rules)
    page = root / "docs" / "AGENT-PIPELINE.md"
    if page.is_file():
        documents.append(page)
    for doc in documents:
        for token in quoted_tokens(doc.read_text(encoding="utf-8")):
            if not is_reference(token, root, doc):
                continue
            checked += 1
            if not resolve(token, root, doc):
                problems.append(f"{doc.relative_to(root)}: quoted path does not exist: {token}")

    if not quality_bar.is_file():
        problems.append("the quality bar is missing")

    for doc in documents:
        for command in set(COMMAND.findall(doc.read_text(encoding="utf-8"))):
            checked += 1
            if not (root / command).exists():
                problems.append(f"{doc.relative_to(root)}: names a missing script: {command}")

    return problems, checked, len(skills), len(rules)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=ROOT,
                        help="tree to check (default: this repository)")
    args = parser.parse_args(argv)

    problems, checked, skills, rules = check(args.root.resolve())
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1
    print(f"PASS pipeline: {skills} skills, {rules} rules, {checked} references resolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
