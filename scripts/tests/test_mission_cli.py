# SPDX-License-Identifier: Apache-2.0
"""The model-free command-line entry point of the trusted mission layer.

These tests pin the contract the README's no-container path promises: a flyable
plan exits 0, a plan that fails a check exits 2 and names the checks on stderr,
and the stop grammar resolves without a model in either shipped language.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "mission.compiler", *args],
                          capture_output=True, text=True, cwd=str(ROOT))


def intent(tmp_path: pathlib.Path, **over) -> str:
    sys.path.insert(0, str(ROOT))
    from mission.compiler.intent import utterance_hash

    raw = {"intent": "survey", "field_id": "north-3", "sensor": "rgb", "gsd_cm": 3.0,
           "deliver": ["orthomosaic"], "utterance_hash": utterance_hash("survey north 3")}
    raw.update(over)
    path = tmp_path / "intent.json"
    path.write_text(json.dumps(raw))
    return str(path)


def test_a_flyable_intent_compiles_and_exits_zero(tmp_path):
    r = run("--intent", intent(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "intent          survey" in r.stdout
    assert "FAIL" not in r.stdout


def test_an_out_of_envelope_intent_is_refused_with_named_checks(tmp_path):
    r = run("--intent", intent(tmp_path, gsd_cm=40.0))
    assert r.returncode == 2
    assert "refused (checks):" in r.stderr
    for name in ("gsd_bounds", "altitude_ceiling"):
        assert name in r.stderr


def test_an_intent_that_fails_the_schema_is_refused_not_compiled(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"intent": "survey"}))
    r = run("--intent", str(path))
    assert r.returncode == 2
    assert "refused (schema)" in r.stderr


def test_the_json_output_is_the_canonical_plan(tmp_path):
    r = run("--intent", intent(tmp_path), "--json")
    assert r.returncode == 0, r.stderr
    plan = json.loads(r.stdout)
    assert plan["flyable"] is True
    assert plan["intent"] == "survey"
    assert plan["waypoints"]


@pytest.mark.parametrize("utterance,verb", [("abort", "abort"),
                                            ("land now", "land_now"),
                                            ("pouse agora", "land_now")])
def test_the_stop_grammar_resolves_without_a_model(utterance, verb):
    r = run("--stop", utterance)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == verb


def test_a_non_stop_utterance_is_not_resolved_by_the_grammar():
    r = run("--stop", "survey the north field")
    assert r.returncode == 2
    assert "no stop verb" in r.stderr


def _guara(*args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run([sys.executable, "-m", "guara", "compile", *args],
                          capture_output=True, text=True, cwd=str(ROOT), env=env)


def test_guara_compile_is_the_same_stop_path_as_the_module():
    r = _guara("--stop", "pouse agora")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "land_now"


def test_guara_compile_refuses_an_out_of_envelope_intent(tmp_path):
    r = _guara("--intent", intent(tmp_path, gsd_cm=40.0))
    assert r.returncode == 2
    assert "refused (checks):" in r.stderr
    for name in ("gsd_bounds", "altitude_ceiling"):
        assert name in r.stderr
