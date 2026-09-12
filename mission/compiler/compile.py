# SPDX-License-Identifier: Apache-2.0
"""Deterministic Mission Intent -> flight plan compiler (docs/PLAN-M8-M16.md M8).

Trust position. This module is the trusted, deterministic layer between an untrusted intent
and a trusted plan executor (LLM-EMBODIMENT.md §5.1). It never talks to a model, never reads
model text, and never emits a setpoint. Its output is a plan, and a plan is flyable only if
every static check passed.

What it checks, and what it does not. The compiler checks the *plan*; the RTA monitors the
*flight* (LLM-EMBODIMENT.md §5.3). Two independent layers: a plan that passes every check
here can still be stopped in the air by the arbiter, and that is the design, not a
redundancy.

Every numeric model here — energy, turn penalty, sensor geometry — is a [HYPOTHESIS] carried
from the site file. The compiler's correctness claim is about the checks and the determinism,
never about the fidelity of those models.
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
from dataclasses import dataclass, field as dc_field

import yaml

from . import geometry as geom
from . import projection as proj
from .intent import Intent

COMPILER_VERSION = "guara-mission-compiler/0.1"

PLAN_VERSION = 1

#: Order in which checks are reported. Checks are independent: a check that cannot be
#: evaluated because an earlier one failed is reported `skipped`, never `pass` and never
#: `fail`, so a rejection always names exactly the violated constraint.
CHECK_ORDER = (
    "field_known",
    "poi_known",
    "gsd_bounds",
    "deliverables_supported",
    "altitude_ceiling",
    "altitude_floor",
    "coverage_in_field",
    "coverage_in_geofence",
    "vlos",
    "envelope",
    "energy",
)


class NotCompilable(Exception):
    """The intent produces no plan by design (stop-class and status intents)."""


@dataclass(frozen=True)
class GatewayLimits:
    """The gateway clamp of ADR 0010 rule 2, read from the run's arbiter parameters."""

    max_speed_h_m_s: float
    max_climb_rate_m_s: float
    max_descent_rate_m_s: float
    source: str = ""


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # pass | fail | skipped
    detail: str = ""


@dataclass(frozen=True)
class Waypoint:
    north_m: float
    east_m: float
    altitude_agl_m: float
    action: str  # transit | capture
    lat_deg: float
    lon_deg: float


@dataclass
class Plan:
    intent_verb: str
    site_id: str
    site_hash: str
    intent_hash: str
    utterance_hash: str
    compiler_version: str
    origin: dict
    altitude_agl_m: float
    speed_m_s: float
    achieved_gsd_cm: float
    swath_m: float
    line_spacing_m: float
    waypoints: list[Waypoint]
    path_length_m: float
    duration_s: float
    energy_wh: float
    checks: list[Check] = dc_field(default_factory=list)
    geofence_lat_lon_deg: list[float] = dc_field(default_factory=list)

    @property
    def flyable(self) -> bool:
        return not self.failed_checks()

    def failed_checks(self) -> list[str]:
        return [c.name for c in self.checks if c.status == "fail"]

    def as_dict(self) -> dict:
        return _canonical({
            "plan_version": PLAN_VERSION,
            "compiler_version": self.compiler_version,
            "intent": self.intent_verb,
            "site_id": self.site_id,
            "site_hash": self.site_hash,
            "intent_hash": self.intent_hash,
            "utterance_hash": self.utterance_hash,
            "frame": "ned_local",
            "origin": self.origin,
            "altitude_agl_m": self.altitude_agl_m,
            "speed_m_s": self.speed_m_s,
            "achieved_gsd_cm": self.achieved_gsd_cm,
            "swath_m": self.swath_m,
            "line_spacing_m": self.line_spacing_m,
            "path_length_m": self.path_length_m,
            "duration_s": self.duration_s,
            "energy_wh": self.energy_wh,
            "flyable": self.flyable,
            "checks": [{"name": c.name, "status": c.status, "detail": c.detail}
                       for c in self.checks],
            "geofence_lat_lon_deg": self.geofence_lat_lon_deg,
            "waypoints": [{"north_m": w.north_m, "east_m": w.east_m,
                           "altitude_agl_m": w.altitude_agl_m, "action": w.action,
                           "lat_deg": w.lat_deg, "lon_deg": w.lon_deg}
                          for w in self.waypoints],
        })

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, indent=2) + "\n"


#: Keys whose values are degrees. Six decimals of a degree is 0.11 m, and that rounding
#: accumulated into a metre-scale disagreement with the independent verifier of
#: mission.compiler.verify; eight decimals is about a millimetre.
_DEGREE_KEYS = ("lat", "lon", "lat_deg", "lon_deg", "geofence_lat_lon_deg")
_METRE_DECIMALS = 6
_DEGREE_DECIMALS = 8


def _canonical(value, decimals: int = _METRE_DECIMALS):
    """Round every float so serialisation is byte-stable (AC-25).

    Values below the rounding resolution collapse to 0.0 rather than being written in
    exponent form, which keeps plans diffable and free of platform-dependent formatting.
    """
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite value in plan")
        r = round(value, decimals)
        return 0.0 if abs(r) < 10.0 ** -decimals else r
    if isinstance(value, dict):
        return {k: _canonical(v, _DEGREE_DECIMALS if k in _DEGREE_KEYS else decimals)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(v, decimals) for v in value]
    return value


class Site:
    """The site model: the only source of geography the compiler will use."""

    def __init__(self, raw: dict, source: str = "") -> None:
        self.raw = raw
        self.source = source
        self.site_id = str(raw["site_id"])
        self.origin_lat_deg = float(raw["origin"]["lat"])
        self.origin_lon_deg = float(raw["origin"]["lon"])
        self.origin_alt_amsl_m = float(raw["origin"]["alt_amsl_m"])
        self.limits = raw["limits"]
        self.plan_cfg = raw["plan"]
        self.battery = raw["battery"]
        self.sensors = raw["sensors"]
        self.fields = raw["fields"]
        self.pois = raw.get("pois", {})
        self.geofence_cfg = raw["geofence"]

    @classmethod
    def from_raw(cls, raw: dict, source: str = "") -> "Site":
        return cls(raw, source=source)

    def hash(self) -> str:
        canonical = json.dumps(self.raw, sort_keys=True, separators=(",", ":"),
                               default=str)
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    def to_local(self, lat_deg: float, lon_deg: float) -> tuple[float, float]:
        return proj.global_to_local(lat_deg, lon_deg, self.origin_lat_deg, self.origin_lon_deg)

    def to_global(self, north_m: float, east_m: float) -> tuple[float, float]:
        return proj.local_to_global(north_m, east_m, self.origin_lat_deg, self.origin_lon_deg)

    def geofence_local(self) -> geom.Polygon:
        return [self.to_local(lat, lon)
                for lat, lon in self.geofence_cfg["polygon_lat_lon_deg"]]

    def geofence_lat_lon_flat(self) -> list[float]:
        """The fence in the flat form the arbiter parameter expects (ADR 0004)."""
        return [float(c) for pair in self.geofence_cfg["polygon_lat_lon_deg"] for c in pair]

    def field_local(self, field_id: str) -> geom.Polygon:
        return [self.to_local(lat, lon)
                for lat, lon in self.fields[field_id]["polygon_lat_lon_deg"]]

    def poi_local(self, poi_id: str) -> tuple[float, float]:
        lat, lon = self.pois[poi_id]["lat_lon_deg"]
        return self.to_local(float(lat), float(lon))

    def home_local(self) -> tuple[float, float]:
        return float(self.raw["home"]["north_m"]), float(self.raw["home"]["east_m"])

    def pilot_local(self) -> tuple[float, float]:
        return float(self.raw["pilot"]["north_m"]), float(self.raw["pilot"]["east_m"])


def load_site(path: pathlib.Path | str) -> Site:
    path = pathlib.Path(path)
    return Site(yaml.safe_load(path.read_text()), source=str(path))


def load_gateway_limits(path: pathlib.Path | str) -> GatewayLimits:
    """Read the gateway clamp from an arbiter parameter file, so the compiler and the
    gateway cannot disagree about the envelope (ADR 0010 rule 2)."""
    path = pathlib.Path(path)
    params = yaml.safe_load(path.read_text())["guara_rta"]["ros__parameters"]
    return GatewayLimits(
        max_speed_h_m_s=float(params["gateway.max_speed_h_m_s"]),
        max_climb_rate_m_s=float(params["gateway.max_climb_rate_m_s"]),
        max_descent_rate_m_s=float(params["gateway.max_descent_rate_m_s"]),
        source=str(path),
    )


def altitude_for_gsd(sensor: dict, gsd_cm: float) -> float:
    """Altitude [m AGL] that yields `gsd_cm` with this sensor (pinhole model)."""
    return gsd_cm * float(sensor["focal_length_mm"]) * float(sensor["image_width_px"]) \
        / (float(sensor["sensor_width_mm"]) * 100.0)


def gsd_for_altitude(sensor: dict, altitude_m: float) -> float:
    return float(sensor["sensor_width_mm"]) * altitude_m * 100.0 \
        / (float(sensor["focal_length_mm"]) * float(sensor["image_width_px"]))


def _boustrophedon(poly: geom.Polygon, spacing_m: float) -> list[tuple[float, float]]:
    """Lawnmower lines across the shorter axis of the polygon's box, along the longer one."""
    n0, n1, e0, e1 = geom.bounding_box(poly)
    span_n, span_e = n1 - n0, e1 - e0
    lines: list[tuple[float, float]] = []
    if span_e >= span_n:                      # lines run east-west, stepping north
        count = max(1, int(math.ceil(span_n / spacing_m)))
        for i in range(count + 1):
            n = n0 + min(span_n, i * spacing_m)
            a, b = (e0, e1) if i % 2 == 0 else (e1, e0)
            lines.append((n, a))
            lines.append((n, b))
            if n >= n1:
                break
    else:                                     # lines run north-south, stepping east
        count = max(1, int(math.ceil(span_e / spacing_m)))
        for i in range(count + 1):
            e = e0 + min(span_e, i * spacing_m)
            a, b = (n0, n1) if i % 2 == 0 else (n1, n0)
            lines.append((a, e))
            lines.append((b, e))
            if e >= e1:
                break
    return lines


def compile_plan(intent: Intent, site: Site, limits: GatewayLimits) -> Plan:
    """Compile an intent into a plan, or into a plan that says why it is not flyable.

    Raises `NotCompilable` for intents that produce no plan by design: the stop class is
    handled by a keyword grammar straight to platform modes and must never wait for a
    compiler, let alone a model (ADR 0013 decision 6).
    """
    if not intent.is_compilable:
        raise NotCompilable(
            f"intent '{intent.intent}' is handled outside the compiler (stop class or status)")

    checks: dict[str, Check] = {}

    def ok(name: str, detail: str = "") -> None:
        checks[name] = Check(name, "pass", detail)

    def fail(name: str, detail: str) -> None:
        checks[name] = Check(name, "fail", detail)

    def skip(name: str, detail: str) -> None:
        checks[name] = Check(name, "skipped", detail)

    def finish() -> Plan:
        for name in CHECK_ORDER:
            checks.setdefault(name, Check(name, "skipped", "not evaluated"))
        plan.checks = [checks[name] for name in CHECK_ORDER]
        return plan

    # An empty shell, filled in as the compilation proceeds, so that a rejection still
    # returns a plan object carrying its checks.
    plan = Plan(
        intent_verb=intent.intent,
        site_id=site.site_id,
        site_hash=site.hash(),
        intent_hash=intent.hash(),
        utterance_hash=intent.utterance_hash,
        compiler_version=COMPILER_VERSION,
        origin={"lat": site.origin_lat_deg, "lon": site.origin_lon_deg,
                "alt_amsl_m": site.origin_alt_amsl_m},
        altitude_agl_m=0.0,
        speed_m_s=float(site.plan_cfg["cruise_speed_m_s"]),
        achieved_gsd_cm=0.0,
        swath_m=0.0,
        line_spacing_m=0.0,
        waypoints=[],
        path_length_m=0.0,
        duration_s=0.0,
        energy_wh=0.0,
        geofence_lat_lon_deg=site.geofence_lat_lon_flat(),
    )

    # ---- named-object resolution -----------------------------------------------------
    target_field = None
    target_poi = None
    if intent.intent == "survey":
        skip("poi_known", "survey intent")
        if intent.field_id not in site.fields:
            fail("field_known", f"field '{intent.field_id}' is not in site '{site.site_id}'")
            return finish()
        ok("field_known", str(intent.field_id))
        target_field = str(intent.field_id)
    else:  # inspect_point
        skip("field_known", "inspect_point intent")
        if intent.poi_id not in site.pois:
            fail("poi_known", f"point of interest '{intent.poi_id}' is not in the site model")
            return finish()
        ok("poi_known", str(intent.poi_id))
        target_poi = str(intent.poi_id)

    sensor = site.sensors[intent.sensor]

    # ---- sensor and product vocabulary -----------------------------------------------
    gsd_req = float(intent.gsd_cm)
    gsd_min, gsd_max = float(sensor["gsd_cm_min"]), float(sensor["gsd_cm_max"])
    if not gsd_min <= gsd_req <= gsd_max:
        fail("gsd_bounds",
             f"{gsd_req} cm/px is outside the {intent.sensor} range [{gsd_min}, {gsd_max}]")
    else:
        ok("gsd_bounds", f"{gsd_req} cm/px")

    unsupported = [d for d in intent.deliver if d not in sensor["products"]]
    if unsupported:
        fail("deliverables_supported",
             f"{intent.sensor} cannot produce {sorted(unsupported)}")
    else:
        ok("deliverables_supported", ", ".join(intent.deliver))

    # ---- altitude ---------------------------------------------------------------------
    derived = altitude_for_gsd(sensor, gsd_req)
    altitude = float(intent.altitude_agl_m) if intent.altitude_agl_m is not None else derived
    ceiling = min(float(site.limits["max_altitude_agl_m"]),
                  float(site.geofence_cfg["alt_max_m"]))
    floor = float(site.limits["min_altitude_agl_m"])
    if altitude > ceiling:
        fail("altitude_ceiling", f"{altitude:.2f} m AGL exceeds the ceiling {ceiling:.2f} m")
    else:
        ok("altitude_ceiling", f"{altitude:.2f} m AGL <= {ceiling:.2f} m")
    if altitude < floor:
        fail("altitude_floor", f"{altitude:.2f} m AGL is below the floor {floor:.2f} m")
    else:
        ok("altitude_floor", f"{altitude:.2f} m AGL >= {floor:.2f} m")

    plan.altitude_agl_m = altitude
    plan.achieved_gsd_cm = gsd_for_altitude(sensor, altitude)
    plan.swath_m = float(sensor["image_width_px"]) * plan.achieved_gsd_cm / 100.0

    # ---- coverage ---------------------------------------------------------------------
    fence = site.geofence_local()
    home = site.home_local()
    track: list[tuple[float, float, str]] = []

    if target_field is not None:
        side = intent.overlap_side if intent.overlap_side is not None else 0.65
        plan.line_spacing_m = max(1.0, plan.swath_m * (1.0 - float(side)))
        poly = site.field_local(target_field)
        buffer_m = float(site.fields[target_field]["buffer_m"])
        coverage = geom.erode(poly, buffer_m)
        if not coverage or geom.polygon_area(coverage) <= 0.0:
            fail("coverage_in_field",
                 f"field '{target_field}' has no area left after its {buffer_m} m buffer")
            return finish()
        ok("coverage_in_field",
           f"{geom.polygon_area(coverage):.0f} m2 inside the {buffer_m} m buffer")
        lines = _boustrophedon(coverage, plan.line_spacing_m)
        track.append((home[0], home[1], "transit"))
        track.extend((n, e, "capture") for n, e in lines)
        track.append((home[0], home[1], "transit"))
    else:
        skip("coverage_in_field", "inspect_point intent")
        poi = site.poi_local(target_poi)
        track = [(home[0], home[1], "transit"), (poi[0], poi[1], "capture"),
                 (home[0], home[1], "transit")]

    margin = float(site.limits["fence_margin_m"])
    outside = [(n, e) for n, e, _ in track if geom.clearance((n, e), fence) < margin]
    if outside:
        worst = min(outside, key=lambda p: geom.clearance(p, fence))
        fail("coverage_in_geofence",
             f"{len(outside)} of {len(track)} waypoints are within {margin} m of the fence "
             f"or outside it (worst clearance {geom.clearance(worst, fence):.1f} m)")
    else:
        ok("coverage_in_geofence", f"{len(track)} waypoints, margin {margin} m")

    pilot = site.pilot_local()
    vlos_r = float(site.limits["vlos_radius_m"])
    far = [(n, e) for n, e, _ in track if math.dist((n, e), pilot) > vlos_r]
    if far:
        worst_d = max(math.dist(p, pilot) for p in far)
        fail("vlos", f"{len(far)} waypoints beyond the {vlos_r} m VLOS radius "
                     f"(worst {worst_d:.0f} m)")
    else:
        ok("vlos", f"all waypoints within {vlos_r} m of the pilot")

    plan.waypoints = [
        Waypoint(n, e, altitude, action, *site.to_global(n, e)) for n, e, action in track
    ]

    # ---- envelope and energy ----------------------------------------------------------
    speed = float(site.plan_cfg["cruise_speed_m_s"])
    climb = float(site.plan_cfg["climb_speed_m_s"])
    descent = float(site.plan_cfg["descent_speed_m_s"])
    breaches = []
    if speed > limits.max_speed_h_m_s:
        breaches.append(f"cruise {speed} > gateway.max_speed_h_m_s {limits.max_speed_h_m_s}")
    if climb > limits.max_climb_rate_m_s:
        breaches.append(f"climb {climb} > gateway.max_climb_rate_m_s {limits.max_climb_rate_m_s}")
    if descent > limits.max_descent_rate_m_s:
        breaches.append(
            f"descent {descent} > gateway.max_descent_rate_m_s {limits.max_descent_rate_m_s}")
    if breaches:
        fail("envelope", "; ".join(breaches))
    else:
        ok("envelope", f"cruise {speed} m/s inside the gateway clamp")

    length = sum(math.dist((track[i][0], track[i][1]), (track[i + 1][0], track[i + 1][1]))
                 for i in range(len(track) - 1))
    turns = max(0, len(track) - 2)
    turn_s = turns * float(site.plan_cfg["turn_penalty_s"])
    vertical_s = altitude / climb + altitude / descent
    plan.path_length_m = length
    plan.duration_s = length / speed + turn_s + vertical_s
    cruise_wh = float(site.battery["cruise_power_w"]) * (length / speed + turn_s) / 3600.0
    hover_wh = float(site.battery["hover_power_w"]) * vertical_s / 3600.0
    plan.energy_wh = cruise_wh + hover_wh

    reserve = float(site.battery["reserve_fraction"])
    usable = float(site.battery["usable_wh"])
    required = plan.energy_wh * (1.0 + reserve)
    if required > usable:
        fail("energy", f"{required:.1f} Wh needed with a {reserve:.0%} reserve, "
                       f"{usable:.1f} Wh usable")
    else:
        ok("energy", f"{required:.1f} Wh of {usable:.1f} Wh usable")

    return finish()
