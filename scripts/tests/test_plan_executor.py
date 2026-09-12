#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The plan executor never parses model output and never overshoots a waypoint."""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mission.executor import (  # noqa: E402
    PlanExecutorError, Vehicle, load_plan, step, velocity_toward, Waypoint,
)


def write_plan(tmp_path, waypoints, speed=4.0):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({
        "plan_version": 1,
        "speed_m_s": speed,
        "waypoints": waypoints,
    }))
    return path


def test_load_plan_rejects_actuator_keys(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({
        "speed_m_s": 4.0,
        "mavlink": 400,
        "waypoints": [{"north_m": 0, "east_m": 0, "altitude_agl_m": 10}],
    }))
    with pytest.raises(PlanExecutorError):
        load_plan(path)


def test_load_plan_rejects_non_finite_and_empty(tmp_path):
    with pytest.raises(PlanExecutorError):
        load_plan(write_plan(tmp_path, []))
    path = write_plan(tmp_path, [{"north_m": float("nan"), "east_m": 0, "altitude_agl_m": 10}])
    with pytest.raises(PlanExecutorError):
        load_plan(path)


def test_velocity_toward_is_along_the_line_and_stops_inside_the_radius():
    wp = Waypoint(100.0, 0.0, 10.0)
    vn, ve, vd, reached = velocity_toward(
        Vehicle(0.0, 0.0, -10.0), wp, speed_m_s=4.0, capture_radius_m=3.0,
        climb_speed_m_s=2.0, descent_speed_m_s=1.5)
    assert not reached
    assert vn == pytest.approx(4.0)
    assert ve == pytest.approx(0.0)
    assert vd == pytest.approx(0.0)
    vn, ve, vd, reached = velocity_toward(
        Vehicle(99.0, 0.0, -10.0), wp, 4.0, 3.0, 2.0, 1.5)
    assert reached
    assert (vn, ve, vd) == (0.0, 0.0, 0.0)


def test_climb_is_negative_down():
    wp = Waypoint(0.0, 0.0, 20.0)
    vn, ve, vd, reached = velocity_toward(
        Vehicle(0.0, 0.0, -5.0), wp, 4.0, 3.0, 2.0, 1.5)
    assert not reached
    assert vd == pytest.approx(-2.0)


def test_step_advances_and_then_idles(tmp_path):
    path = write_plan(tmp_path, [
        {"north_m": 0.0, "east_m": 0.0, "altitude_agl_m": 10.0},
        {"north_m": 50.0, "east_m": 0.0, "altitude_agl_m": 10.0},
    ])
    track = load_plan(path, capture_radius_m=3.0)
    # Sitting on the first waypoint consumes it and aims at the second.
    cmd = step(track, Vehicle(0.0, 0.0, -10.0))
    assert not cmd.complete
    assert cmd.vn > 0
    cmd = step(track, Vehicle(50.0, 0.0, -10.0))
    assert cmd.complete
    idle = step(track, Vehicle(50.0, 0.0, -10.0))
    assert idle.complete and idle.vn == idle.ve == idle.vd == 0.0
