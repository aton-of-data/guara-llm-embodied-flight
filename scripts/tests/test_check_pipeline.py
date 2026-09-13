#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A drifted skill or rule surface is a failed check (docs/AGENT-PIPELINE.md)."""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

SKILL = """---
name: {name}
description: {description}
---

# {name}

Reads `{quoted}`.
"""

RULE = """---
description: A rule.
alwaysApply: {always}
---

# Rule

Gate:

```bash
python3 scripts/check_pipeline.py
```
"""


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_pipeline.py"), *args],
        cwd=str(ROOT), capture_output=True, text=True,
    )


def tree(root: pathlib.Path, *, name="guara-pipeline", description="A skill.",
         quoted="scripts/check_pipeline.py", always="true") -> pathlib.Path:
    skill = root / ".claude" / "skills" / "guara-pipeline"
    (skill / "references").mkdir(parents=True)
    (root / ".cursor" / "rules").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "scripts" / "check_pipeline.py").write_text("", encoding="utf-8")
    (skill / "SKILL.md").write_text(
        SKILL.format(name=name, description=description, quoted=quoted), encoding="utf-8")
    (skill / "references" / "quality-bar.md").write_text(
        "# Quality bar\n\nGate: `scripts/check_pipeline.py`.\n", encoding="utf-8")
    (root / ".cursor" / "rules" / "guara-repo.mdc").write_text(
        RULE.format(always=always), encoding="utf-8")
    return root


def test_this_repository_agrees_with_its_own_surfaces():
    r = run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS pipeline" in r.stdout


def test_a_skill_name_that_lost_its_directory_fails(tmp_path):
    tree(tmp_path, name="guara-renamed")
    r = run("--root", str(tmp_path))
    assert r.returncode == 1
    assert "directory is 'guara-pipeline'" in r.stdout


def test_a_rule_without_front_matter_fails(tmp_path):
    tree(tmp_path)
    (tmp_path / ".cursor" / "rules" / "guara-repo.mdc").write_text("# Rule\n", encoding="utf-8")
    r = run("--root", str(tmp_path))
    assert r.returncode == 1
    assert "no front matter" in r.stdout


def test_a_rule_attached_by_nothing_fails(tmp_path):
    tree(tmp_path, always="maybe")
    r = run("--root", str(tmp_path))
    assert r.returncode == 1
    assert "alwaysApply must be true or false" in r.stdout


def test_a_quoted_path_that_moved_fails(tmp_path):
    tree(tmp_path, quoted="scripts/check_gone.py")
    r = run("--root", str(tmp_path))
    assert r.returncode == 1
    assert "quoted path does not exist: scripts/check_gone.py" in r.stdout


def test_a_gate_script_named_inside_a_fence_is_checked(tmp_path):
    tree(tmp_path)
    (tmp_path / "scripts" / "check_pipeline.py").unlink()
    r = run("--root", str(tmp_path))
    assert r.returncode == 1
    assert "names a missing script: scripts/check_pipeline.py" in r.stdout


def test_a_verdict_is_not_read_as_a_path(tmp_path):
    tree(tmp_path, quoted="N/A")
    r = run("--root", str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
