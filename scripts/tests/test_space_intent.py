#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Space Mission Intent schema: closed vocabulary, no actuator names (risk RS-6)."""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from space import intent as si  # noqa: E402


def valid_slew() -> dict:
    return {
        "intent": "slew",
        "boresight_id": "instrument-a",
        "target_id": "nadir",
        "utterance_hash": "sha256:" + "0" * 64,
    }


def test_valid_slew_is_accepted():
    parsed = si.parse(valid_slew())
    assert parsed.intent == "slew"
    assert parsed.boresight_id == "instrument-a"
    assert parsed.is_compilable


def test_unknown_verb_is_rejected():
    with pytest.raises(si.SpaceIntentError) as e:
        si.parse(valid_slew() | {"intent": "fire_thruster"})
    assert e.value.code == "schema"


def test_extra_properties_are_rejected():
    with pytest.raises(si.SpaceIntentError):
        si.parse(valid_slew() | {"fpy": "GOTO 1", "cmd": "RW.TORQUE"})


def test_actuator_and_sequence_vocabulary_is_rejected():
    for extra in ({"opcode": 0x01}, {"sequence": "slew.bin"}, {"quaternion": [1, 0, 0, 0]},
                  {"rate_rad_s": [0.1, 0, 0]}):
        with pytest.raises(si.SpaceIntentError):
            si.parse(valid_slew() | extra)


def test_stop_class_needs_nothing_else():
    for verb in ("abort", "safe_mode", "status"):
        parsed = si.parse({"intent": verb, "utterance_hash": "sha256:" + "2" * 64})
        assert parsed.is_stop_class == (verb in ("abort", "safe_mode"))
        assert not parsed.is_compilable or verb == "status"


def test_slew_without_target_is_rejected():
    with pytest.raises(si.SpaceIntentError):
        si.parse({k: v for k, v in valid_slew().items() if k != "target_id"})


def test_malformed_model_output_never_raises_outside_space_intent_error():
    for raw in ("", "I cannot help with that.", "[]", "null", "{}" * 500):
        with pytest.raises(si.SpaceIntentError) as e:
            si.parse_model_output(raw)
        assert e.value.code in ("not_json", "schema")


def test_schema_file_and_validator_agree():
    import json
    import jsonschema

    schema = json.loads((ROOT / "space/schema/space_intent.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(valid_slew(), schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(valid_slew() | {"intent": "torque_wheels"}, schema)
