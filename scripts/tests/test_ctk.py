#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M19 / AC-65: the independent Python port passes the published SPEC §3 vectors."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

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


def test_python_port_passes_adr0010_gateway_vectors():
    vectors = ROOT / "core/conformance/vectors/adr0010_gateway.json"
    n = len(json.loads(vectors.read_text()))
    r = subprocess.run(
        [sys.executable, "-m", "guara", "ctk", "run", "--port", "python",
         "--vectors", str(vectors)],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert r.returncode == 0, r.stderr
    assert f"PASS {n}/{n}" in r.stdout
    assert "adr0010_gateway.json" in r.stdout


def test_sil_port_passes_when_cabi_is_built():
    from guara.ctk.sil import find_cabi
    lib = find_cabi(ROOT)
    if lib is None:
        pytest.skip("guara_cabi shared library is not built")
    n = len(json.loads((ROOT / "core/conformance/vectors/spec_s3.json").read_text()))
    r = subprocess.run(
        [sys.executable, "-m", "guara", "ctk", "run", "--port", "sil"],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert r.returncode == 0, r.stderr
    assert f"PASS {n}/{n}" in r.stdout
    assert "sil-cabi" in r.stdout


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


def test_report_file_satisfies_ac66(tmp_path):
    dest = tmp_path / "latest_ctk"
    r = subprocess.run(
        [sys.executable, "-m", "guara", "ctk", "run", "--port", "python",
         "--report", str(dest)],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert r.returncode == 0, r.stderr
    report = dest / "report.txt"
    assert report.is_file()
    text = report.read_text()
    assert text == r.stdout
    chk = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_ac.py"), "AC-66", str(dest)],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert chk.returncode == 0, chk.stdout + chk.stderr
    assert "PASS AC-66" in chk.stdout


def test_ac66_rejects_a_report_without_the_decision_4_sentence(tmp_path):
    (tmp_path / "report.txt").write_text(
        "port python\ncore x\nabi y\nhost z\narch a\nvectors_sha256 abc\nresult PASS\n",
        encoding="utf-8",
    )
    chk = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_ac.py"), "AC-66", str(tmp_path)],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert chk.returncode == 1
    assert "necessary and not sufficient" in chk.stdout
