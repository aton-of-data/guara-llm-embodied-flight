# SPDX-License-Identifier: Apache-2.0
"""Independent Python port of the braking-aware geofence predictor (ADR 0004).

Does not import `core/` or the C ABI.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MAX_VERTICES = 64
GEOM_EPS = 1e-9
INF = math.inf
EARTH_RADIUS_M = 6371000.0
PI = 3.14159265358979323846

POLY_ERROR_NAMES = (
    "none",
    "too_few_vertices",
    "too_many_vertices",
    "non_finite_vertex",
    "degenerate_edge",
    "self_intersecting",
    "zero_area",
)


def polygon_error_name(code: int) -> str:
    if 0 <= code < len(POLY_ERROR_NAMES):
        return POLY_ERROR_NAMES[code]
    return "unknown"


@dataclass
class Vec2:
    x: float = 0.0
    y: float = 0.0


@dataclass
class GfParams:
    a_brake_h_m_s2: float = 3.0
    a_brake_v_m_s2: float = 2.0
    k_sigma: float = 2.0
    v_min_m_s: float = 0.2
    horizon_s: float = 30.0


@dataclass
class GfState:
    north_m: float = 0.0
    east_m: float = 0.0
    altitude_m: float = 0.0
    vn_m_s: float = 0.0
    ve_m_s: float = 0.0
    climb_rate_m_s: float = 0.0
    eph_m: float = 0.0
    epv_m: float = 0.0


@dataclass
class GfPrediction:
    t_gf_s: float = INF
    t_horizontal_s: float = INF
    t_vertical_s: float = INF
    inside: int = 1
    exit_distance_m: float = INF


def _cross(a: Vec2, b: Vec2) -> float:
    return a.x * b.y - a.y * b.x


def _dot(a: Vec2, b: Vec2) -> float:
    return a.x * b.x + a.y * b.y


def _sub(a: Vec2, b: Vec2) -> Vec2:
    return Vec2(a.x - b.x, a.y - b.y)


def _norm(a: Vec2) -> float:
    return math.hypot(a.x, a.y)


def _orientation(a: Vec2, b: Vec2, c: Vec2) -> int:
    v = _cross(_sub(b, a), _sub(c, a))
    if v > GEOM_EPS:
        return 1
    if v < -GEOM_EPS:
        return -1
    return 0


def _on_segment(a: Vec2, b: Vec2, q: Vec2) -> bool:
    return (q.x <= max(a.x, b.x) + GEOM_EPS and q.x >= min(a.x, b.x) - GEOM_EPS and
            q.y <= max(a.y, b.y) + GEOM_EPS and q.y >= min(a.y, b.y) - GEOM_EPS)


def _segments_touch(p1: Vec2, p2: Vec2, q1: Vec2, q2: Vec2) -> bool:
    o1 = _orientation(p1, p2, q1)
    o2 = _orientation(p1, p2, q2)
    o3 = _orientation(q1, q2, p1)
    o4 = _orientation(q1, q2, p2)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _on_segment(p1, p2, q1):
        return True
    if o2 == 0 and _on_segment(p1, p2, q2):
        return True
    if o3 == 0 and _on_segment(q1, q2, p1):
        return True
    if o4 == 0 and _on_segment(q1, q2, p2):
        return True
    return False


def classify_polygon(vertices_ne: list[float]) -> str:
    n = len(vertices_ne) // 2
    if n < 3:
        return "too_few_vertices"
    if n > MAX_VERTICES:
        return "too_many_vertices"
    verts = [Vec2(vertices_ne[2 * i], vertices_ne[2 * i + 1]) for i in range(n)]
    for v in verts:
        if not math.isfinite(v.x) or not math.isfinite(v.y):
            return "non_finite_vertex"
    twice_area = 0.0
    for i in range(n):
        a = verts[i]
        b = verts[(i + 1) % n]
        if _norm(_sub(b, a)) <= GEOM_EPS:
            return "degenerate_edge"
        twice_area += _cross(a, b)
    for i in range(n):
        for j in range(i + 1, n):
            adjacent = j == i + 1 or (i == 0 and j == n - 1)
            if adjacent:
                continue
            if _segments_touch(verts[i], verts[(i + 1) % n], verts[j], verts[(j + 1) % n]):
                return "self_intersecting"
    if abs(twice_area) <= GEOM_EPS:
        return "zero_area"
    return "none"


def _point_segment_distance(q: Vec2, a: Vec2, b: Vec2) -> float:
    ab = _sub(b, a)
    len2 = _dot(ab, ab)
    t = 0.0 if len2 <= 0.0 else _dot(_sub(q, a), ab) / len2
    t = min(1.0, max(0.0, t))
    return _norm(_sub(q, Vec2(a.x + t * ab.x, a.y + t * ab.y)))


def _channel_time(distance_m: float, speed_m_s: float, a_brake: float,
                  margin_m: float, horizon_s: float) -> float:
    if not math.isfinite(distance_m):
        return INF
    d_stop = speed_m_s * speed_m_s / (2.0 * a_brake) + margin_m
    t = max(0.0, (distance_m - d_stop) / speed_m_s)
    return INF if t > horizon_s else t


class ReferenceGeofence:
    def __init__(self) -> None:
        self.verts: list[Vec2] = []
        self.alt_min_m = -INF
        self.alt_max_m = INF

    def configure(self, vertices_ne: list[float], alt_min_m: float, alt_max_m: float) -> None:
        n = len(vertices_ne) // 2
        self.verts = [Vec2(vertices_ne[2 * i], vertices_ne[2 * i + 1]) for i in range(n)]
        self.alt_min_m = alt_min_m
        self.alt_max_m = alt_max_m

    def polygon_error(self, vertices_ne: list[float]) -> str:
        return classify_polygon(vertices_ne)

    def predict(self, params: GfParams, state: GfState) -> GfPrediction:
        out = GfPrediction()
        pos = Vec2(state.north_m, state.east_m)
        inside_h = self._contains(pos)
        inside_v = (state.altitude_m >= self.alt_min_m - GEOM_EPS and
                    state.altitude_m <= self.alt_max_m + GEOM_EPS)
        out.inside = 1 if inside_h and inside_v else 0
        if not out.inside:
            out.t_gf_s = out.t_horizontal_s = out.t_vertical_s = 0.0
            out.exit_distance_m = 0.0
            return out
        lateral = params.k_sigma * max(0.0, state.eph_m)
        vertical = params.k_sigma * max(0.0, state.epv_m)
        if lateral > 0.0 and self._boundary_distance(pos) <= lateral:
            out.t_gf_s = out.t_horizontal_s = out.t_vertical_s = 0.0
            out.exit_distance_m = 0.0
            return out
        if vertical > 0.0 and (state.altitude_m - self.alt_min_m <= vertical or
                               self.alt_max_m - state.altitude_m <= vertical):
            out.t_gf_s = out.t_horizontal_s = out.t_vertical_s = 0.0
            out.exit_distance_m = 0.0
            return out
        speed = math.hypot(state.vn_m_s, state.ve_m_s)
        if speed >= params.v_min_m_s:
            u = Vec2(state.vn_m_s / speed, state.ve_m_s / speed)
            out.exit_distance_m = self._exit_distance(pos, u)
            out.t_horizontal_s = _channel_time(
                out.exit_distance_m, speed, params.a_brake_h_m_s2,
                params.k_sigma * max(0.0, state.eph_m), params.horizon_s)
        climb = state.climb_rate_m_s
        if abs(climb) >= params.v_min_m_s:
            distance = (self.alt_max_m - state.altitude_m if climb > 0.0
                        else state.altitude_m - self.alt_min_m)
            out.t_vertical_s = _channel_time(
                distance, abs(climb), params.a_brake_v_m_s2,
                params.k_sigma * max(0.0, state.epv_m), params.horizon_s)
        out.t_gf_s = min(out.t_horizontal_s, out.t_vertical_s)
        return out

    def _boundary_distance(self, q: Vec2) -> float:
        d = INF
        n = len(self.verts)
        for i in range(n):
            d = min(d, _point_segment_distance(q, self.verts[i], self.verts[(i + 1) % n]))
        return d

    def _contains(self, q: Vec2, tolerance_m: float = 1e-6) -> bool:
        if not self.verts:
            return False
        if self._boundary_distance(q) <= tolerance_m:
            return True
        inside = False
        n = len(self.verts)
        j = n - 1
        for i in range(n):
            a = self.verts[i]
            b = self.verts[j]
            if (a.y > q.y) != (b.y > q.y):
                x_cross = a.x + (q.y - a.y) * (b.x - a.x) / (b.y - a.y)
                if q.x < x_cross:
                    inside = not inside
            j = i
        return inside

    def _exit_distance(self, p: Vec2, u: Vec2) -> float:
        events: list[float] = []
        n = len(self.verts)
        for i in range(n):
            a = self.verts[i]
            b = self.verts[(i + 1) % n]
            e = _sub(b, a)
            ap = _sub(a, p)
            denom = _cross(u, e)
            if abs(denom) > GEOM_EPS * _norm(e):
                s = _cross(ap, e) / denom
                t = _cross(ap, u) / denom
                if t >= -GEOM_EPS and t <= 1.0 + GEOM_EPS and s > GEOM_EPS:
                    events.append(s)
            elif abs(_cross(ap, u)) <= GEOM_EPS * max(1.0, _norm(ap)):
                for s in (_dot(ap, u), _dot(_sub(b, p), u)):
                    if s > GEOM_EPS:
                        events.append(s)
        events.sort()
        previous = 0.0
        for s in events:
            if s - previous <= GEOM_EPS:
                continue
            mid = 0.5 * (previous + s)
            q = Vec2(p.x + mid * u.x, p.y + mid * u.y)
            if not self._contains(q, GEOM_EPS * 10.0):
                return previous
            previous = s
        return previous if events else INF

    def project(self, lat_deg: float, lon_deg: float, ref_lat_deg: float,
                ref_lon_deg: float) -> Vec2:
        return project_to_local(lat_deg, lon_deg, ref_lat_deg, ref_lon_deg)


def project_to_local(lat_deg: float, lon_deg: float, ref_lat_deg: float,
                     ref_lon_deg: float) -> Vec2:
    deg2rad = PI / 180.0
    lat = lat_deg * deg2rad
    lon = lon_deg * deg2rad
    ref_lat = ref_lat_deg * deg2rad
    ref_lon = ref_lon_deg * deg2rad
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    cos_d_lon = math.cos(lon - ref_lon)
    arg = min(1.0, max(-1.0, math.sin(ref_lat) * sin_lat +
                       math.cos(ref_lat) * cos_lat * cos_d_lon))
    c = math.acos(arg)
    k = 1.0 if abs(c) <= 0.0 else c / math.sin(c)
    return Vec2(
        k * (math.cos(ref_lat) * sin_lat - math.sin(ref_lat) * cos_lat * cos_d_lon) * EARTH_RADIUS_M,
        k * cos_lat * math.sin(lon - ref_lon) * EARTH_RADIUS_M,
    )
