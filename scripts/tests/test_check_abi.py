#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-61: a symbol change without an ABI bump is a failed check."""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def run(*args: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_abi.py"), *args],
        cwd=str(cwd or ROOT), capture_output=True, text=True,
    )


def test_baseline_matches_the_header():
    r = run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS abi" in r.stdout


def test_an_added_symbol_without_a_bump_fails(tmp_path):
    header = tmp_path / "guara.h"
    baseline = tmp_path / "abi_symbols.txt"
    shutil.copy2(ROOT / "core" / "include" / "guara" / "guara.h", header)
    shutil.copy2(ROOT / "core" / "abi_symbols.txt", baseline)
    text = header.read_text(encoding="utf-8")
    text = text.replace(
        "GUARA_API int guara_core_param_digest",
        "GUARA_API int guara_core_extra(void);\nGUARA_API int guara_core_param_digest",
    )
    header.write_text(text, encoding="utf-8")
    r = run("--header", str(header), "--baseline", str(baseline))
    assert r.returncode == 1, r.stdout
    assert "guara_core_extra" in r.stdout
    assert "without an ABI version bump" in r.stdout
