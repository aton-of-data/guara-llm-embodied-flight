# SPDX-License-Identifier: Apache-2.0
"""Independent verification of a compiled plan.

Why this exists. `compile.compile_plan` both builds a plan and declares whether it is
flyable. Asking that same code whether its own output is safe is a tautology, and AC-28 would
be worth nothing if it counted the compiler's own verdict. This module re-derives the
constraints from the plan document and the site model by a different route: it reads the
serialised waypoints, recomputes the path from them, tests containment directly against the
fence and the *field* polygon (not the eroded coverage box the planner used), and compares
against the site limits and the gateway clamp.

It shares only the projection and the point-in-polygon primitive with the compiler. A
disagreement between the two is a defect in one of them, which is the point.
"""
from __future__ import annotations

import math

from . import geometry as geom
from .compile import GatewayLimits, Plan, Site


def verify(plan: Plan, site: Site, limits: GatewayLimits) -> list[str]:
    """Return the list of violations found in a plan. Empty means the plan is inside every
    declared constraint."""
    violations: list[str] = []
    doc = plan.as_dict()
    waypoints = doc["waypoints"]
    if not waypoints:
        return ["plan has no waypoints"]

    # Containment is re-tested from the serialised geographic coordinates, projected here,
    # rather than from the local values the planner produced.
    fence = [site.to_local(lat, lon)
             for lat, lon in _pairs(doc["geofence_lat_lon_deg"])]
    if len(fence) < 3:
        violations.append("plan carries no usable fence polygon")
    else:
        for wp in waypoints:
            p = site.to_local(wp["lat_deg"], wp["lon_deg"])
            if not geom.point_in_polygon(p, fence):
                violations.append(
                    f"waypoint {p[0]:.1f}N {p[1]:.1f}E is outside the keep-in fence")

    altitude = float(doc["altitude_agl_m"])
    ceiling = min(float(site.limits["max_altitude_agl_m"]),
                  float(site.geofence_cfg["alt_max_m"]))
    if altitude > ceiling:
        violations.append(f"altitude {altitude:.1f} m exceeds the ceiling {ceiling:.1f} m")
    if altitude < float(site.limits["min_altitude_agl_m"]):
        violations.append(f"altitude {altitude:.1f} m is below the floor")

    pilot = site.pilot_local()
    for wp in waypoints:
        p = site.to_local(wp["lat_deg"], wp["lon_deg"])
        if math.dist(p, pilot) > float(site.limits["vlos_radius_m"]):
            violations.append(f"waypoint {math.dist(p, pilot):.0f} m from the pilot exceeds "
                              f"the VLOS radius")
            break

    speed = float(doc["speed_m_s"])
    if speed > limits.max_speed_h_m_s:
        violations.append(f"commanded speed {speed} m/s exceeds the gateway clamp "
                          f"{limits.max_speed_h_m_s} m/s")

    # Energy is recomputed from the waypoint list, not taken from the plan's own figure.
    length = 0.0
    for a, b in zip(waypoints, waypoints[1:]):
        pa = site.to_local(a["lat_deg"], a["lon_deg"])
        pb = site.to_local(b["lat_deg"], b["lon_deg"])
        length += math.dist(pa, pb)
    turns = max(0, len(waypoints) - 2) * float(site.plan_cfg["turn_penalty_s"])
    vertical = altitude / float(site.plan_cfg["climb_speed_m_s"]) \
        + altitude / float(site.plan_cfg["descent_speed_m_s"])
    energy = float(site.battery["cruise_power_w"]) * (length / speed + turns) / 3600.0 \
        + float(site.battery["hover_power_w"]) * vertical / 3600.0
    required = energy * (1.0 + float(site.battery["reserve_fraction"]))
    if required > float(site.battery["usable_wh"]):
        violations.append(f"recomputed energy {required:.1f} Wh exceeds the usable "
                          f"{site.battery['usable_wh']} Wh")
    if plan.path_length_m > 0 and abs(length - plan.path_length_m) > 1.0:
        violations.append(f"recomputed path {length:.1f} m disagrees with the plan's "
                          f"{plan.path_length_m:.1f} m")

    # A survey's capture points must lie inside the field itself.
    if doc["intent"] == "survey":
        field_id = _field_of(plan)
        if field_id and field_id in site.fields:
            poly = site.field_local(field_id)
            for wp in waypoints:
                if wp["action"] != "capture":
                    continue
                p = site.to_local(wp["lat_deg"], wp["lon_deg"])
                if not geom.point_in_polygon(p, poly):
                    violations.append(f"capture point is outside field '{field_id}'")
                    break

    return violations


def _pairs(flat: list[float]) -> list[tuple[float, float]]:
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def _field_of(plan: Plan) -> str | None:
    for check in plan.checks:
        if check.name == "field_known" and check.status == "pass":
            return check.detail or None
    return None
