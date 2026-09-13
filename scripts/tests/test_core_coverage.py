#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-62: coverage measurement exists and does not invent a pass threshold."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_core_qa_measures_coverage_without_a_bound():
    qa = (ROOT / "scripts/core_qa.sh").read_text(encoding="utf-8")
    cmake = (ROOT / "core/CMakeLists.txt").read_text(encoding="utf-8")
    cov = (ROOT / "scripts/core_coverage.py").read_text(encoding="utf-8")
    assert "GUARA_CORE_COVERAGE" in qa
    assert "GUARA_CORE_COVERAGE" in cmake
    assert "PARAMETER TBD" in qa
    assert "not a bound" in cov
    assert "PARAMETER TBD" in cov
    assert ">= " not in cov


def test_parse_gcov_counts_hits_and_misses(tmp_path):
    import importlib.util

    p = tmp_path / "foo.cpp.gcov"
    p.write_text(
        "        -:    0:Source:foo.cpp\n"
        "        -:    1:// comment\n"
        "        1:    2:int hit() { return 1; }\n"
        "    #####:    3:int miss() { return 0; }\n"
        "        0:    4:int also_miss() { return 0; }\n",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location(
        "core_coverage", ROOT / "scripts/core_coverage.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    hit, miss = mod.parse_gcov(p)
    assert hit == 1
    assert miss == 2
