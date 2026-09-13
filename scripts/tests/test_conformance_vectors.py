#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M19: the published SPEC §3 vectors name every kernel transition."""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
VECTORS = ROOT / "core/conformance/vectors/spec_s3.json"


def test_spec_s3_vectors_cover_every_kernel_transition():
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    ids = [v["id"] for v in data]
    assert len(ids) == len(set(ids))
    seen: set[int] = set()
    for vec in data:
        for step in vec["steps"]:
            if step.get("action") == "latch":
                seen.add(9)
            trans = step.get("expect", {}).get("transition")
            if trans:
                seen.add(int(trans))
    assert seen == {1, 2, 3, 4, 5, 6, 7, 8, 9}
    assert "hysteresis_band_blocks_return" in ids
    assert "t5_blocked_by_cf_intent" in ids


def test_conformance_readme_states_necessary_not_sufficient():
    text = (ROOT / "core/conformance/README.md").read_text(encoding="utf-8")
    assert "necessary and not sufficient" in text
    assert "C ABI" in text


def test_adr0010_vectors_cover_trusted_time_envelope_and_shadow():
    data = json.loads(
        (ROOT / "core/conformance/vectors/adr0010_gateway.json").read_text(encoding="utf-8")
    )
    ids = {v["id"] for v in data}
    assert "future_stamp_rejected" in ids
    assert "age_from_reception" in ids
    assert "velocity_clamped" in ids
    assert "non_finite_rejected" in ids
    assert "shadow_guard_blocks" in ids
    tags = {tag for v in data for tag in v.get("adr", [])}
    assert tags == {"0010-1", "0010-2", "0010-3"}


def test_gateway_limits_vectors_cover_every_init_branch():
    data = json.loads(
        (ROOT / "core/conformance/vectors/gateway_limits.json").read_text(encoding="utf-8")
    )
    ids = {v["id"] for v in data}
    assert "default_gateway_limits_are_valid" in ids
    assert "cf_timeout_must_be_positive" in ids
    assert "future_stamp_tolerance_must_be_non_negative" in ids
    cmake = (ROOT / "core/CMakeLists.txt").read_text(encoding="utf-8")
    assert "conformance_adr0010_gateway" in cmake


def test_monitor_table_vectors_cover_stale_incomplete_and_hostile_fields():
    data = json.loads(
        (ROOT / "core/conformance/vectors/monitor_table.json").read_text(encoding="utf-8")
    )
    ids = {v["id"] for v in data}
    assert "stale_expected_is_invalid" in ids
    assert "incomplete_inputs_are_invalid" in ids
    assert "out_of_range_action_is_invalid" in ids
    assert "log_class_never_switches" in ids
    assert "seventeenth_id_is_rejected" in ids
    cmake = (ROOT / "core/CMakeLists.txt").read_text(encoding="utf-8")
    assert "conformance_monitor_table" in cmake
    assert "test_monitor_vectors.c" in cmake


def test_geofence_vectors_cover_ac8_and_uncertainty_band():
    data = json.loads(
        (ROOT / "core/conformance/vectors/geofence.json").read_text(encoding="utf-8")
    )
    ids = {v["id"] for v in data}
    assert "convex_straight_approach" in ids
    assert "zero_velocity_is_infinite" in ids
    assert "outside_is_zero" in ids
    assert "hover_inside_uncertainty_band" in ids
    assert "concave_tangent_reflex_stays_inside" in ids
    assert "zero_k_sigma_disables_the_band" in ids
    assert "projection_small_distance" in ids
    assert "too_few_vertices" in ids
    assert "self_intersecting_bowtie" in ids
    assert "too_many_vertices" in ids
    assert "default_predictor_params_are_valid" in ids
    assert "a_brake_h_must_be_positive" in ids


def test_core_params_vectors_cover_every_validate_branch():
    data = json.loads(
        (ROOT / "core/conformance/vectors/core_params.json").read_text(encoding="utf-8")
    )
    ids = {v["id"] for v in data}
    assert "default_core_params_are_valid" in ids
    assert "n_max_must_be_at_least_one" in ids
    assert "n_max_must_not_exceed_history" in ids
    assert "window_s_must_be_finite_positive" in ids
    cmake = (ROOT / "core/CMakeLists.txt").read_text(encoding="utf-8")
    assert "conformance_core_params" in cmake
    assert "test_core_params_vectors.c" in cmake


def test_types_vectors_cover_state_recovery_and_command_names():
    data = json.loads(
        (ROOT / "core/conformance/vectors/types.json").read_text(encoding="utf-8")
    )
    ids = {v["id"] for v in data}
    assert "state_names" in ids
    assert "recovery_names" in ids
    assert "command_names" in ids
    assert "transition_names" in ids
    assert "cause_names" in ids
    cmake = (ROOT / "core/CMakeLists.txt").read_text(encoding="utf-8")
    assert "conformance_types" in cmake
    assert "test_types_vectors.c" in cmake
