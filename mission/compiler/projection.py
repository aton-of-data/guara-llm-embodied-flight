# SPDX-License-Identifier: Apache-2.0
"""Azimuthal equidistant projection, identical to the one the arbiter uses.

AC-26 compares compiler waypoints against the fence polygon the arbiter loads, so the two
must project geographic coordinates the same way. This is a transcription of
`guara_geofence::projectToLocal` (`ros2_ws/src/guara_geofence/src/predictor.cpp:262`), which
itself follows `px4_ros2_cpp/src/utils/map_projection_impl.cpp:28-85`; the inverse follows
`localToGlobal` in the same file. Earth radius is PX4's 6371 km sphere, not WGS84.
"""
from __future__ import annotations

import math

EARTH_RADIUS_M = 6371000.0


def global_to_local(lat_deg: float, lon_deg: float, ref_lat_deg: float,
                    ref_lon_deg: float) -> tuple[float, float]:
    """Return (north_m, east_m) of (lat, lon) about the reference point."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    ref_lat = math.radians(ref_lat_deg)
    ref_lon = math.radians(ref_lon_deg)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    cos_d_lon = math.cos(lon - ref_lon)
    arg = min(1.0, max(-1.0, math.sin(ref_lat) * sin_lat + math.cos(ref_lat) * cos_lat * cos_d_lon))
    c = math.acos(arg)
    k = (c / math.sin(c)) if abs(c) > 0.0 else 1.0
    north = k * (math.cos(ref_lat) * sin_lat - math.sin(ref_lat) * cos_lat * cos_d_lon) \
        * EARTH_RADIUS_M
    east = k * cos_lat * math.sin(lon - ref_lon) * EARTH_RADIUS_M
    return north, east


def local_to_global(north_m: float, east_m: float, ref_lat_deg: float,
                    ref_lon_deg: float) -> tuple[float, float]:
    """Return (lat_deg, lon_deg) of a local north/east offset about the reference point."""
    ref_lat = math.radians(ref_lat_deg)
    ref_lon = math.radians(ref_lon_deg)
    x_rad = north_m / EARTH_RADIUS_M
    y_rad = east_m / EARTH_RADIUS_M
    c = math.sqrt(x_rad * x_rad + y_rad * y_rad)
    if abs(c) <= 0.0:
        return ref_lat_deg, ref_lon_deg
    sin_c, cos_c = math.sin(c), math.cos(c)
    lat = math.asin(cos_c * math.sin(ref_lat) + (x_rad * sin_c * math.cos(ref_lat)) / c)
    lon = ref_lon + math.atan2(y_rad * sin_c,
                               c * math.cos(ref_lat) * cos_c - x_rad * math.sin(ref_lat) * sin_c)
    return math.degrees(lat), math.degrees(lon)
