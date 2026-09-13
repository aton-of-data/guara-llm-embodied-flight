#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M19 / AC-65: the independent Python port passes the published SPEC §3 vectors."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
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


def test_python_port_passes_monitor_table_vectors():
    vectors = ROOT / "core/conformance/vectors/monitor_table.json"
    n = len(json.loads(vectors.read_text()))
    r = subprocess.run(
        [sys.executable, "-m", "guara", "ctk", "run", "--port", "python",
         "--vectors", str(vectors)],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert r.returncode == 0, r.stderr
    assert f"PASS {n}/{n}" in r.stdout
    assert "monitor_table.json" in r.stdout


def test_python_port_passes_geofence_vectors():
    vectors = ROOT / "core/conformance/vectors/geofence.json"
    n = len(json.loads(vectors.read_text()))
    r = subprocess.run(
        [sys.executable, "-m", "guara", "ctk", "run", "--port", "python",
         "--vectors", str(vectors)],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert r.returncode == 0, r.stderr
    assert f"PASS {n}/{n}" in r.stdout
    assert "geofence.json" in r.stdout


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


def test_a_t4_mutation_in_the_c_abi_is_rejected_when_cmake_is_present():
    if shutil.which("cmake") is None:
        pytest.skip("cmake is not on PATH")
    env = _env()
    env["PYTHON"] = sys.executable
    r = subprocess.run(
        ["bash", str(ROOT / "scripts/ctk_mutation_sil.sh")],
        cwd=str(ROOT), capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS ctk_mutation_sil" in r.stdout


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


def test_bench_report_satisfies_ac60(tmp_path):
    dest = tmp_path / "latest_bench"
    r = subprocess.run(
        [sys.executable, "-m", "guara", "ctk", "bench", "--port", "python",
         "--report", str(dest)],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert r.returncode == 0, r.stderr
    text = (dest / "report.txt").read_text()
    assert "measured, not a bound" in text
    assert "max_step_ns" in text
    assert "n_ops" in text
    chk = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_ac.py"), "AC-60", str(dest)],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert chk.returncode == 0, chk.stdout + chk.stderr
    assert "PASS AC-60" in chk.stdout


def test_ac60_rejects_a_report_that_omits_the_measured_disclaimer(tmp_path):
    (tmp_path / "report.txt").write_text(
        "port python\nhost z\narch a\nn_ops 3\nmax_step_ns 9\n",
        encoding="utf-8",
    )
    chk = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_ac.py"), "AC-60", str(tmp_path)],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert chk.returncode == 1
    assert "measured, not a bound" in chk.stdout
