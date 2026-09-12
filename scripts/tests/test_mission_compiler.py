#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-24, AC-25, AC-26: the deterministic mission compiler.

The compiler is the trusted half of the LLM path (LLM-EMBODIMENT.md §5.3, ADR 0013
decision 8): whatever a model proposes, only a plan that passes every static check may be
flown. One test per check, each built so that exactly one check is violated.
"""
import copy
import pathlib
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mission.compiler import compile as mc  # noqa: E402
from mission.compiler import geometry as geom  # noqa: E402
from mission.compiler import intent as mi  # noqa: E402

SITE_FILE = ROOT / "mission/site/demo_farm.yaml"
PARAMS_FILE = ROOT / "config/rta_params.yaml"


@pytest.fixture()
def site():
    return mc.load_site(SITE_FILE)


@pytest.fixture()
def limits():
    return mc.load_gateway_limits(PARAMS_FILE)


def survey_intent(**over) -> mi.Intent:
    raw = {
        "intent": "survey",
        "field_id": "north-3",
        "sensor": "rgb",
        "gsd_cm": 3.0,
        "overlap": {"front": 0.75, "side": 0.65},
        "altitude_agl_m": None,
        "deliver": ["orthomosaic"],
        "utterance_hash": "sha256:" + "0" * 64,
    }
    raw.update(over)
    return mi.parse(raw)


def mutate(site, path, value):
    """Return a copy of the site model with one nested key replaced."""
    raw = copy.deepcopy(site.raw)
    node = raw
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return mc.Site.from_raw(raw, source=site.source)


# --------------------------------------------------------------------------------------
# the nominal plan
# --------------------------------------------------------------------------------------

def test_nominal_survey_compiles(site, limits):
    plan = mc.compile_plan(survey_intent(), site, limits)
    assert plan.flyable
    assert [c.name for c in plan.checks if c.status != "pass"] == []
    assert len(plan.waypoints) >= 4
    assert plan.altitude_agl_m == pytest.approx(109.44, abs=0.5)  # rgb, 3 cm/px
    assert plan.path_length_m > 0
    assert plan.energy_wh > 0


def test_plan_records_its_provenance(site, limits):
    plan = mc.compile_plan(survey_intent(), site, limits)
    assert plan.site_hash.startswith("sha256:")
    assert plan.intent_hash.startswith("sha256:")
    assert plan.compiler_version == mc.COMPILER_VERSION
    assert plan.utterance_hash == "sha256:" + "0" * 64


# --------------------------------------------------------------------------------------
# AC-24: one failing check per case, and the same case passes once the violation is gone
# --------------------------------------------------------------------------------------

def test_check_field_known(site, limits):
    plan = mc.compile_plan(survey_intent(field_id="atlantis"), site, limits)
    assert not plan.flyable
    assert plan.failed_checks() == ["field_known"]


def test_check_poi_known(site, limits):
    raw = {
        "intent": "inspect_point",
        "poi_id": "nowhere",
        "sensor": "thermal",
        "gsd_cm": 10.0,
        "deliver": ["thermal_map"],
        "utterance_hash": "sha256:" + "3" * 64,
    }
    plan = mc.compile_plan(mi.parse(raw), site, limits)
    assert plan.failed_checks() == ["poi_known"]
    ok = mc.compile_plan(mi.parse(raw | {"poi_id": "pivot-2"}), site, limits)
    assert ok.flyable, ok.failed_checks()


def test_check_altitude_ceiling(site, limits):
    plan = mc.compile_plan(survey_intent(altitude_agl_m=180.0), site, limits)
    assert plan.failed_checks() == ["altitude_ceiling"]
    assert mc.compile_plan(survey_intent(altitude_agl_m=100.0), site, limits).flyable


def test_check_altitude_floor(site, limits):
    plan = mc.compile_plan(survey_intent(altitude_agl_m=2.0), site, limits)
    assert plan.failed_checks() == ["altitude_floor"]


def test_check_gsd_bounds(site, limits):
    plan = mc.compile_plan(survey_intent(gsd_cm=0.2), site, limits)
    assert plan.failed_checks() == ["gsd_bounds"]
    assert mc.compile_plan(survey_intent(gsd_cm=2.0), site, limits).flyable


def test_check_deliverables_supported(site, limits):
    plan = mc.compile_plan(survey_intent(deliver=["ndvi"]), site, limits)
    assert plan.failed_checks() == ["deliverables_supported"]
    ok = mc.compile_plan(
        survey_intent(sensor="multispectral", gsd_cm=5.0, deliver=["ndvi"]), site, limits)
    assert ok.flyable, ok.failed_checks()


def test_check_coverage_in_field(site, limits):
    """A buffer wider than the field leaves nothing to survey."""
    wide = mutate(site, ["fields", "north-3", "buffer_m"], 200.0)
    plan = mc.compile_plan(survey_intent(), wide, limits)
    assert plan.failed_checks() == ["coverage_in_field"]


def test_check_coverage_in_geofence(site, limits):
    """AC-26: a field that sticks out of the keep-in fence cannot be surveyed."""
    plan = mc.compile_plan(survey_intent(field_id="outside-fence"), site, limits)
    assert plan.failed_checks() == ["coverage_in_geofence"]


def test_check_vlos(site, limits):
    near = mutate(site, ["limits", "vlos_radius_m"], 40.0)
    plan = mc.compile_plan(survey_intent(), near, limits)
    assert plan.failed_checks() == ["vlos"]


def test_check_energy(site, limits):
    tiny = mutate(site, ["battery", "usable_wh"], 5.0)
    plan = mc.compile_plan(survey_intent(), tiny, limits)
    assert plan.failed_checks() == ["energy"]


def test_check_envelope(site, limits):
    """The plan's commanded speed must fit the gateway clamp of ADR 0010 rule 2."""
    fast = mutate(site, ["plan", "cruise_speed_m_s"], limits.max_speed_h_m_s + 3.0)
    plan = mc.compile_plan(survey_intent(), fast, limits)
    assert plan.failed_checks() == ["envelope"]


def test_stop_class_intents_are_not_compiled(site, limits):
    for verb in ("abort", "land_now", "return_home"):
        parsed = mi.parse({"intent": verb, "utterance_hash": "sha256:" + "4" * 64})
        with pytest.raises(mc.NotCompilable):
            mc.compile_plan(parsed, site, limits)


# --------------------------------------------------------------------------------------
# AC-26: every waypoint is inside the fence the run also gives to the RTA
# --------------------------------------------------------------------------------------

def test_geofence_every_waypoint_inside_the_same_polygon(site, limits):
    plan = mc.compile_plan(survey_intent(), site, limits)
    fence = site.geofence_local()
    for wp in plan.waypoints:
        assert geom.point_in_polygon((wp.north_m, wp.east_m), fence), wp


def test_geofence_polygon_exported_for_the_rta_matches_the_site_file(site):
    exported = site.geofence_lat_lon_flat()
    assert len(exported) % 2 == 0 and len(exported) // 2 >= 3
    raw = yaml.safe_load(SITE_FILE.read_text())
    flat = [c for v in raw["geofence"]["polygon_lat_lon_deg"] for c in v]
    assert exported == flat


def test_geofence_projection_matches_px4_formulation(site):
    """The compiler must project with the same azimuthal equidistant formulation and Earth
    radius the arbiter uses (guara_geofence::projectToLocal), or AC-26 means nothing."""
    from mission.compiler import projection as proj

    lat0, lon0 = site.origin_lat_deg, site.origin_lon_deg
    for dn, de in ((0.0, 0.0), (100.0, 0.0), (0.0, -250.0), (1500.0, 900.0)):
        lat, lon = proj.local_to_global(dn, de, lat0, lon0)
        back = proj.global_to_local(lat, lon, lat0, lon0)
        assert back[0] == pytest.approx(dn, abs=1e-6)
        assert back[1] == pytest.approx(de, abs=1e-6)
    assert proj.EARTH_RADIUS_M == 6371000.0


# --------------------------------------------------------------------------------------
# AC-25: determinism
# --------------------------------------------------------------------------------------

def test_determinism_same_intent_same_site_same_bytes(site, limits):
    a = mc.compile_plan(survey_intent(), site, limits).to_json()
    b = mc.compile_plan(survey_intent(), mc.load_site(SITE_FILE), limits).to_json()
    assert a == b


def test_determinism_site_change_changes_the_hash(site, limits):
    a = mc.compile_plan(survey_intent(), site, limits)
    moved = mutate(site, ["limits", "vlos_radius_m"], 501.0)
    b = mc.compile_plan(survey_intent(), moved, limits)
    assert a.site_hash != b.site_hash


def test_determinism_no_floating_point_noise_in_the_serialized_plan(site, limits):
    plan = mc.compile_plan(survey_intent(), site, limits)
    text = plan.to_json()
    assert "e-" not in text.lower().replace("sha256", "")  # no exponent-formatted noise
    assert text.endswith("\n")
