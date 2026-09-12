# SPDX-License-Identifier: Apache-2.0
"""Planar polygon helpers for the mission compiler, in the local north/east frame.

Deliberately dependency-free (no shapely in the dev container) and deliberately simple:
every function here is either exact or conservative in the direction that rejects a plan.
Where a conservative choice is made it is named in the docstring.
"""
from __future__ import annotations

import math

Point = tuple[float, float]
Polygon = list[Point]


def point_in_polygon(p: Point, poly: Polygon) -> bool:
    """Even-odd ray cast. Boundary points count as inside (the fence is closed, ADR 0004)."""
    if len(poly) < 3:
        return False
    if distance_to_boundary(p, poly) == 0.0:
        return True
    x, y = p
    inside = False
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y):
            t = (y - y1) / (y2 - y1)
            if x < x1 + t * (x2 - x1):
                inside = not inside
    return inside


def _distance_to_segment(p: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distance_to_boundary(p: Point, poly: Polygon) -> float:
    """Unsigned distance from p to the polygon boundary."""
    return min(_distance_to_segment(p, poly[i], poly[(i + 1) % len(poly)])
               for i in range(len(poly)))


def clearance(p: Point, poly: Polygon) -> float:
    """Signed clearance: positive inside, negative outside, zero on the boundary."""
    d = distance_to_boundary(p, poly)
    return d if point_in_polygon(p, poly) else -d


def bounding_box(poly: Polygon) -> tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), max(xs), min(ys), max(ys)


def polygon_area(poly: Polygon) -> float:
    acc = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        acc += x1 * y2 - x2 * y1
    return abs(acc) / 2.0


def erode(poly: Polygon, buffer_m: float, step_m: float = 1.0) -> Polygon:
    """Conservative inward buffer.

    An exact polygon offset needs a general offsetting algorithm (and for concave shapes can
    split the polygon). The compiler only needs a region it is *sure* lies at least
    `buffer_m` inside the field, so the erosion is computed as the set of sample points whose
    clearance exceeds the buffer, returned as the axis-aligned hull of those samples. That is
    never larger than the true erosion, so a plan accepted against it is also inside the true
    erosion. `step_m` bounds the sampling error; the returned box is shrunk by one step.
    """
    if buffer_m <= 0.0:
        return list(poly)
    x0, x1, y0, y1 = bounding_box(poly)
    xs: list[float] = []
    ys: list[float] = []
    n_x = max(2, int((x1 - x0) / step_m) + 1)
    n_y = max(2, int((y1 - y0) / step_m) + 1)
    for i in range(n_x + 1):
        x = x0 + (x1 - x0) * i / n_x
        for j in range(n_y + 1):
            y = y0 + (y1 - y0) * j / n_y
            if clearance((x, y), poly) >= buffer_m:
                xs.append(x)
                ys.append(y)
    if not xs:
        return []
    lo_x, hi_x = min(xs) + step_m, max(xs) - step_m
    lo_y, hi_y = min(ys) + step_m, max(ys) - step_m
    if hi_x <= lo_x or hi_y <= lo_y:
        return []
    return [(lo_x, lo_y), (hi_x, lo_y), (hi_x, hi_y), (lo_x, hi_y)]
