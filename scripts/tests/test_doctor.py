#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-51 / G-S3 / G-S5: `guara doctor` is the workstation preflight.

The tests pin the contract PLAN-M17-M28.md AC-51 names: the command exits 0,
prints the platform, the pins from versions.env and the tier reached. They
also pin ADR 0014 decision 4: the output does not call Guará itself "safe".
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return env


def run_doctor() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "guara", "doctor"],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )


def test_doctor_exits_zero_and_reports_platform_pins_and_tier():
    r = run_doctor()
    assert r.returncode == 0, r.stdout + r.stderr
    out = r.stdout
    assert "platform" in out
    assert "machine" in out
    assert "python" in out
    assert "PX4_REF" in out
    assert "v1.17.0" in out
    assert "T0" in out
    assert "PASS doctor: tier T0" in out


def test_doctor_does_not_claim_safety():
    r = run_doctor()
    assert r.returncode == 0, r.stderr
    blob = (r.stdout + r.stderr).lower()
    assert "safe" not in blob


def test_doctor_fails_when_the_clone_cannot_be_found(monkeypatch, capsys):
    sys.path.insert(0, str(ROOT))
    from guara import doctor

    monkeypatch.setattr(doctor, "repo_root", lambda: None)
    assert doctor.run() == 1
    captured = capsys.readouterr()
    assert "versions.env not found" in captured.err


def test_cli_without_a_command_is_usage_error():
    r = subprocess.run(
        [sys.executable, "-m", "guara"],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )
    assert r.returncode != 0
