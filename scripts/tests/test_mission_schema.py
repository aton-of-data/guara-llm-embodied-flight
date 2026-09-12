#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-23: the Mission Intent schema is a closed vocabulary and rejects everything else.

An intent is the only artifact a language model is allowed to produce (ADR 0010 rule 6,
ADR 0013 decision 2). Every rejection must carry a machine-readable reason and no exception
may escape the validator, because its caller is a model whose output is hostile input.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mission.compiler import intent as mi  # noqa: E402


def valid_survey() -> dict:
    return {
        "intent": "survey",
        "field_id": "north-3",
        "sensor": "rgb",
        "gsd_cm": 3.0,
        "overlap": {"front": 0.75, "side": 0.65},
        "altitude_agl_m": None,
        "deliver": ["orthomosaic"],
        "utterance_hash": "sha256:" + "0" * 64,
    }


def test_valid_survey_is_accepted():
    parsed = mi.parse(valid_survey())
    assert parsed.intent == "survey"
    assert parsed.field_id == "north-3"


def test_unknown_intent_verb_is_rejected():
    bad = valid_survey() | {"intent": "spray_everything"}
    with pytest.raises(mi.IntentError) as e:
        mi.parse(bad)
    assert e.value.code == "schema"
    assert "intent" in e.value.reason


@pytest.mark.parametrize(
    "field,value",
    [
        ("gsd_cm", -1.0),
        ("gsd_cm", 1e6),
        ("gsd_cm", "three"),
        ("sensor", "lidar"),
        ("deliver", ["orthomosaic", "world_domination"]),
        ("deliver", []),
        ("field_id", 7),
        ("utterance_hash", "md5:abc"),
        ("altitude_agl_m", -5.0),
    ],
)
def test_out_of_vocabulary_values_are_rejected(field, value):
    bad = valid_survey() | {field: value}
    with pytest.raises(mi.IntentError) as e:
        mi.parse(bad)
    assert e.value.code == "schema"


def test_extra_properties_are_rejected():
    bad = valid_survey() | {"waypoints": [[0, 0]], "mavlink_command": 400}
    with pytest.raises(mi.IntentError):
        mi.parse(bad)


def test_overlap_bounds_are_rejected():
    for overlap in ({"front": 1.0, "side": 0.65}, {"front": 0.75}, {"front": 0.75, "side": -0.1}):
        with pytest.raises(mi.IntentError):
            mi.parse(valid_survey() | {"overlap": overlap})


def test_model_may_not_emit_coordinates():
    """L-M3: a model has no metric grounding, so geographic literals are never accepted."""
    for extra in ({"lat": -22.0}, {"latitude": -22.0}, {"position": [-22.0, -47.9]}):
        with pytest.raises(mi.IntentError):
            mi.parse(valid_survey() | extra)


def test_inspect_point_requires_a_map_grounded_poi():
    base = {
        "intent": "inspect_point",
        "poi_id": "pivot-2",
        "sensor": "thermal",
        "gsd_cm": 10.0,
        "deliver": ["thermal_map"],
        "utterance_hash": "sha256:" + "1" * 64,
    }
    assert mi.parse(base).poi_id == "pivot-2"
    with pytest.raises(mi.IntentError):
        mi.parse({k: v for k, v in base.items() if k != "poi_id"})


def test_stop_class_intents_need_nothing_else():
    for verb in ("abort", "land_now", "return_home", "status"):
        parsed = mi.parse({"intent": verb, "utterance_hash": "sha256:" + "2" * 64})
        assert parsed.intent == verb
        assert parsed.is_stop_class == (verb in ("abort", "land_now", "return_home"))


def test_survey_without_field_id_is_rejected():
    with pytest.raises(mi.IntentError):
        mi.parse({k: v for k, v in valid_survey().items() if k != "field_id"})


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "I cannot help with that.",
        "```json\n{not json}\n```",
        "[]",
        "null",
        '{"intent": "survey"',
        "{}" * 5000,
    ],
)
def test_non_json_and_malformed_model_output_never_raises_outside_intent_error(raw):
    with pytest.raises(mi.IntentError) as e:
        mi.parse_model_output(raw)
    assert e.value.code in ("not_json", "schema")


def test_fenced_json_from_a_chatty_model_is_recovered():
    raw = (
        "Sure! Here is the mission intent:\n\n```json\n"
        + '{"intent":"survey","field_id":"north-3","sensor":"rgb","gsd_cm":3.0,'
        + '"overlap":{"front":0.75,"side":0.65},"altitude_agl_m":null,'
        + '"deliver":["orthomosaic"],"utterance_hash":"sha256:'
        + "0" * 64
        + '"}\n```\nLet me know if you want a different resolution.\n'
    )
    assert mi.parse_model_output(raw).field_id == "north-3"


def test_schema_file_and_validator_agree():
    """The published schema file is the contract; the validator must not drift from it."""
    import json
    import jsonschema

    schema = json.loads((ROOT / "mission/schema/mission_intent.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(valid_survey(), schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(valid_survey() | {"intent": "spray_everything"}, schema)
