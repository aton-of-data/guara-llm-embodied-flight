#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-57: an out-of-tree CMake project finds the installed guara::core target."""
from __future__ import annotations

import pathlib
import stat

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_consumer_finds_the_exported_target():
    text = (ROOT / "core/examples/consumer/CMakeLists.txt").read_text(encoding="utf-8")
    assert "find_package(guara_core REQUIRED)" in text
    assert "guara::core" in text
    assert "add_subdirectory" not in text


def test_package_config_exports_guara_core():
    cmake = (ROOT / "core/CMakeLists.txt").read_text(encoding="utf-8")
    assert "EXPORT_NAME core" in cmake
    assert "guara_coreConfig.cmake.in" in cmake
    assert "write_basic_package_version_file" in cmake
    cfg = (ROOT / "core/cmake/guara_coreConfig.cmake.in").read_text(encoding="utf-8")
    assert "guara_coreTargets.cmake" in cfg
    assert "guara::core" in cfg


def test_consumer_check_script_installs_then_builds():
    script = ROOT / "scripts/check_core_consumer.sh"
    text = script.read_text(encoding="utf-8")
    assert "cmake --install" in text
    assert "core/examples/consumer" in text
    assert "CMAKE_PREFIX_PATH" in text
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR
