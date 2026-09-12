# SPDX-License-Identifier: Apache-2.0
"""Trusted deterministic plan executor (ADR 0010 rule 6, docs/PLAN-M8-M16.md M9).

This module turns a compiled plan's waypoints into a velocity in the local NED
frame. It never parses model output: the only input is a plan document the
compiler (or a reviewed test fixture) wrote. The ROS 2 node in
`scripts/sitl/ros_action.py` publishes the velocity as `CfSetpoint`; this file
is the allocation-bounded inner loop, unit-tested without ROS.

The executor does not re-check the compiler's static constraints. In flight the
RTA is the independent layer (LLM-EMBODIMENT.md §5.3). A fixture plan that aims
outside the fence is a legitimate test of that layer (AC-31), the analogue of
AC-9's constant-velocity CF.
"""
from __future__ import annotations

import json
import math
import pathlib
from dataclasses import dataclass


class PlanExecutorError(ValueError):
    """The document is not a plan the executor will fly."""


@dataclass(frozen=True)
class Waypoint:
    north_m: float
    east_m: float
    altitude_agl_m: float
    action: str = "transit"


@dataclass
class Vehicle:
    north_m: float
    east_m: float
    down_m: float  # PX4 local z, positive down


@dataclass(frozen=True)
class Command:
    vn: float
    ve: float
    vd: float
    reached: bool
    index: int
    complete: bool


@dataclass
class PlanTrack:
    waypoints: list[Waypoint]
    speed_m_s: float
    capture_radius_m: float
    climb_speed_m_s: float
    descent_speed_m_s: float
    index: int = 0

    @property
    def complete(self) -> bool:
        return self.index >= len(self.waypoints)

    @property
    def current(self) -> Waypoint | None:
        if self.complete:
            return None
        return self.waypoints[self.index]


def load_plan(path: pathlib.Path | str, capture_radius_m: float = 3.0,
              climb_speed_m_s: float = 2.0, descent_speed_m_s: float = 1.5) -> PlanTrack:
    """Load a plan JSON. Rejects anything that is not a waypoint list with speeds."""
    path = pathlib.Path(path)
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise PlanExecutorError(f"not a plan document: {e}") from None
    if not isinstance(raw, dict):
        raise PlanExecutorError("plan must be a JSON object")
    for forbidden in ("mavlink", "setpoint", "opcode", "fpy", "vehicle_command"):
        if forbidden in raw:
            raise PlanExecutorError(f"plan document contains actuator key '{forbidden}'")
    wps = raw.get("waypoints")
    if not isinstance(wps, list) or not wps:
        raise PlanExecutorError("plan has no waypoints")
    waypoints: list[Waypoint] = []
    for i, wp in enumerate(wps):
        if not isinstance(wp, dict):
            raise PlanExecutorError(f"waypoint {i} is not an object")
        try:
            waypoints.append(Waypoint(
                north_m=float(wp["north_m"]),
                east_m=float(wp["east_m"]),
                altitude_agl_m=float(wp["altitude_agl_m"]),
                action=str(wp.get("action", "transit")),
            ))
        except (KeyError, TypeError, ValueError) as e:
            raise PlanExecutorError(f"waypoint {i} is missing a numeric field: {e}") from None
        wp_tuple = waypoints[-1]
        if not all(math.isfinite(v) for v in
                   (wp_tuple.north_m, wp_tuple.east_m, wp_tuple.altitude_agl_m)):
            raise PlanExecutorError(f"waypoint {i} is non-finite")
    try:
        speed = float(raw["speed_m_s"])
    except (KeyError, TypeError, ValueError) as e:
        raise PlanExecutorError(f"plan speed_m_s is missing: {e}") from None
    if not math.isfinite(speed) or speed <= 0.0:
        raise PlanExecutorError("plan speed_m_s must be a positive finite number")
    return PlanTrack(
        waypoints=waypoints,
        speed_m_s=speed,
        capture_radius_m=float(capture_radius_m),
        climb_speed_m_s=float(climb_speed_m_s),
        descent_speed_m_s=float(descent_speed_m_s),
    )


def velocity_toward(vehicle: Vehicle, waypoint: Waypoint, speed_m_s: float,
                    capture_radius_m: float, climb_speed_m_s: float,
                    descent_speed_m_s: float) -> tuple[float, float, float, bool]:
    """Return (vn, ve, vd, reached) in NED. vd is positive down."""
    dn = waypoint.north_m - vehicle.north_m
    de = waypoint.east_m - vehicle.east_m
    current_agl = -vehicle.down_m
    dz_up = waypoint.altitude_agl_m - current_agl
    horiz = math.hypot(dn, de)
    reached = horiz <= capture_radius_m and abs(dz_up) <= capture_radius_m
    if reached:
        return 0.0, 0.0, 0.0, True
    vn = ve = 0.0
    if horiz > 1e-6:
        scale = speed_m_s / horiz
        # Slow down inside three capture radii so the vehicle does not overshoot.
        if horiz < capture_radius_m * 3.0:
            scale *= max(0.25, horiz / (capture_radius_m * 3.0))
        vn = dn * scale
        ve = de * scale
    vd = 0.0
    if dz_up > 0.2:
        vd = -min(climb_speed_m_s, abs(dz_up))
    elif dz_up < -0.2:
        vd = min(descent_speed_m_s, abs(dz_up))
    return vn, ve, vd, False


def step(track: PlanTrack, vehicle: Vehicle) -> Command:
    """Advance the track by one sample. Zero velocity once the last waypoint is reached."""
    if track.complete:
        return Command(0.0, 0.0, 0.0, True, track.index, True)
    wp = track.current
    vn, ve, vd, reached = velocity_toward(
        vehicle, wp, track.speed_m_s, track.capture_radius_m,
        track.climb_speed_m_s, track.descent_speed_m_s)
    if reached:
        track.index += 1
        if track.complete:
            return Command(0.0, 0.0, 0.0, True, track.index, True)
        return step(track, vehicle)
    return Command(vn, ve, vd, False, track.index, False)
