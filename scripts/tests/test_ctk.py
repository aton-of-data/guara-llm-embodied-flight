#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M19 / AC-65: the independent Python port passes the published SPEC §3 vectors."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return env


def test_python_port_passes_spec_s3_vectors():
    n = len(json.loads((ROOT / "core/conformance/vectors/spec_s3.json").read_text()))
    r = subprocess.run(
        [sys.executable, "-m", "guara", "ctk", "run", "--port", "python"],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert r.returncode == 0, r.stderr
    assert f"PASS {n}/{n}" in r.stdout
    assert "python-reference" in r.stdout
    assert "vectors_sha256" in r.stdout
    assert "necessary and not sufficient" in r.stdout
    assert "nothing about the safety of the system that contains it" in r.stdout


def test_a_t4_mutation_is_rejected_by_the_kit():
    r = subprocess.run(
        ["bash", str(ROOT / "scripts/ctk_mutation.sh")],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS ctk_mutation" in r.stdout


def test_spec_records_the_ambiguities_the_port_found():
    text = (ROOT / "docs/SPEC.md").read_text(encoding="utf-8")
    assert "### 3.6 Ambiguities recorded by the independent Python port" in text
    assert "cf_intent_unsafe" in text
    assert "transition 9" in text
