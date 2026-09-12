# SPDX-License-Identifier: Apache-2.0
"""Attitude keep-out predictor (ADR 0012 channel `attitude_keepout`, AC-47).

An orbiting body cannot stop, so the air geofence's braking model does not transfer
(`docs/research/SPACE-AUTONOMY.md` §5). This predictor answers a purely geometric
question: at the current attitude and body rate, when does a protected boresight
enter a keep-out cone around a bright body?

Fail-closed: non-finite inputs, a zero-length vector, or an already-violated cone
report T = 0. Receding, still, or out-of-horizon cases report +∞.

The first implementation is the planar closed form used by AC-47. A constant body
rate about the axis perpendicular to the boresight–forbidden plane changes the
angle at a constant rate; that is exact, not a numerical integration, so the
analytic tests can demand ±0.05 s the way AC-8 demands it of the geofence
predictor.
"""
from __future__ import annotations

import math

INF = math.inf
TOL_S = 0.05  # AC-47 tolerance; documented here so tests and callers share it.


def _finite(*values: float) -> bool:
    return all(math.isfinite(v) for v in values)


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(_dot(v, v))


def _unit(v: tuple[float, float, float]) -> tuple[float, float, float] | None:
    n = _norm(v)
    if n <= 0.0 or not math.isfinite(n):
        return None
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]
           ) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def angle_rad(a: tuple[float, float, float], b: tuple[float, float, float]) -> float | None:
    """Angle between two vectors. None if either is degenerate or non-finite."""
    ua, ub = _unit(a), _unit(b)
    if ua is None or ub is None:
        return None
    return math.acos(max(-1.0, min(1.0, _dot(ua, ub))))


def time_to_cone_violation(theta_rad: float, theta_min_rad: float,
                           omega_close_rad_s: float, horizon_s: float) -> float:
    """Closed-form time until θ(t) = θ_min under a constant closing rate.

    `omega_close_rad_s` is −dθ/dt: positive when the boresight is rotating toward
    the forbidden direction. Units are radians and seconds. Values above `horizon_s`
    are reported as +∞, matching the geofence predictor's horizon convention.
    """
    if not _finite(theta_rad, theta_min_rad, omega_close_rad_s, horizon_s):
        return 0.0
    if theta_min_rad < 0.0 or horizon_s < 0.0:
        return 0.0
    if theta_rad <= theta_min_rad:
        return 0.0
    if omega_close_rad_s <= 0.0:
        return INF
    t = (theta_rad - theta_min_rad) / omega_close_rad_s
    if t > horizon_s:
        return INF
    return t


def predict(boresight_inertial: tuple[float, float, float],
            forbidden_inertial: tuple[float, float, float],
            body_rate_rad_s: tuple[float, float, float],
            theta_min_rad: float,
            horizon_s: float) -> float:
    """Time-to-violation from current inertial vectors and a body rate.

    The body rate is treated as inertial for the analytic window (the rate is
    assumed constant in the plane of the two vectors). The component of ω along
    `boresight × forbidden` is the closing rate; the component along the boresight
    or the forbidden direction does not change the angle.
    """
    ua = _unit(boresight_inertial)
    us = _unit(forbidden_inertial)
    if ua is None or us is None or not _finite(*body_rate_rad_s, theta_min_rad, horizon_s):
        return 0.0
    theta = angle_rad(ua, us)
    if theta is None:
        return 0.0
    axis = _cross(ua, us)
    axis_n = _norm(axis)
    if axis_n <= 1e-12:
        # Parallel or anti-parallel: the rate cannot close a zero-width plane.
        # Already inside is handled by time_to_cone_violation; anti-parallel is
        # receding-or-still unless a rate exists, but there is no unique axis.
        return time_to_cone_violation(theta, theta_min_rad, 0.0, horizon_s)
    axis_u = (axis[0] / axis_n, axis[1] / axis_n, axis[2] / axis_n)
    omega_close = _dot(body_rate_rad_s, axis_u)
    return time_to_cone_violation(theta, theta_min_rad, omega_close, horizon_s)
