#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The geofence predictor is hosted in core/; ROS tests keep the same include."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_predictor_header_lives_in_core_under_the_same_include():
    header = ROOT / "core/include/guara_geofence/predictor.hpp"
    assert header.is_file()
    text = header.read_text(encoding="utf-8")
    assert "T_gf" in text
    assert "kMaxVertices" in text
    ros_header = ROOT / "ros2_ws/src/guara_geofence/include/guara_geofence/predictor.hpp"
    assert not ros_header.exists()


def test_analytic_tests_were_not_rewritten_to_a_new_include():
    analytic = (
        ROOT / "ros2_ws/src/guara_geofence/test/test_predictor_analytic.cpp"
    ).read_text(encoding="utf-8")
    uncertainty = (
        ROOT / "ros2_ws/src/guara_geofence/test/test_predictor_uncertainty.cpp"
    ).read_text(encoding="utf-8")
    assert '#include "guara_geofence/predictor.hpp"' in analytic
    assert '#include "guara_geofence/predictor.hpp"' in uncertainty
    cmake = (ROOT / "ros2_ws/src/guara_geofence/CMakeLists.txt").read_text(encoding="utf-8")
    assert "GUARA_CORE_DIR" in cmake
    assert "geofence_predictor.cpp" in cmake
