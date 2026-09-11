#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for the acceptance-criteria checkers (review 2026-09-11, finding C-2).

Commit 7d6ddeb removed the `def check_ac11(...)` line while editing a neighbouring function. The
module still imported, but `CHECKERS` referenced a name that no longer existed, so *every* checker
raised NameError and none of the eleven checker-based PASS rows could be reproduced. Nothing in the
build noticed.

These tests run without ROS or PX4:
  * every checker in CHECKERS is importable, callable, and fails cleanly on an empty run directory
    instead of raising;
  * the AC-15c fixtures pin finding C-1: the PX4 warning "Mode '...' already registered" is printed
    on the *accept* path and must not be accepted as evidence of a rejection.

Run: ./scripts/dev.sh python3 -m pytest scripts/tests -q
"""
import importlib.util
import json
import pathlib
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_check_ac():
    spec = importlib.util.spec_from_file_location("check_ac", ROOT / "scripts" / "check_ac.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_ac"] = module
    spec.loader.exec_module(module)
    return module


check_ac = load_check_ac()

REJECTION = "ERROR [commander] Not accepting registration requests while armed"
ACCEPTED = "WARN  [commander] Mode 'Guara CF Gateway' already registered (as 'Guara CF Gateway')"
REGISTERED = "[guara_rta]: registered 'Guara CF Gateway' (executor id 2, nav_state 24)"


def test_every_checker_is_callable():
    assert check_ac.CHECKERS, "no checkers registered"
    for ac_id, checker in check_ac.CHECKERS.items():
        assert callable(checker), ac_id


@pytest.mark.parametrize("ac_id", sorted(check_ac.CHECKERS))
def test_checker_fails_cleanly_on_an_empty_directory(ac_id, tmp_path):
    """A checker must report errors, not raise: a crash is indistinguishable from a missing check."""
    errors = check_ac.CHECKERS[ac_id](tmp_path)
    assert isinstance(errors, list)
    # AC-11 and AC-20 are static checks of the source tree and legitimately pass with no run data.
    if ac_id not in ("AC-11", "AC-20"):
        assert errors, f"{ac_id} passed on an empty directory"


def write_run(tmp_path, px4_log_lines, *, arm_check=0, restart_log=REGISTERED):
    (tmp_path / "px4.log").write_text("\n".join(px4_log_lines) + "\n")
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(
        {"px4_params": {"COM_MODE_ARM_CHK": {"set": 0, "read_back": arm_check}}}))
    if restart_log is not None:
        (tmp_path / "guara_rta_node_restart.log").write_text(restart_log + "\n")
    return tmp_path


def test_ac15c_accepts_a_real_rejection(tmp_path):
    run = write_run(tmp_path, ["INFO  [commander] Takeoff detected", REJECTION, "Disarmed by landing"],
                    restart_log="[guara_rta]: waiting for PX4 to accept the registration")
    assert check_ac.check_ac15c(run) == []


def test_ac15c_rejects_the_already_registered_warning(tmp_path):
    """Finding C-1: this is the accept path, and the restarted arbiter did register."""
    run = write_run(tmp_path, ["INFO  [commander] Takeoff detected", ACCEPTED, "Disarmed by landing"])
    errors = check_ac.check_ac15c(run)
    assert any("already registered" in e for e in errors)
    assert any("registered while armed" in e for e in errors)


def test_ac15c_rejects_a_run_that_did_not_pin_the_parameter(tmp_path):
    run = write_run(tmp_path, [REJECTION], arm_check=1,
                    restart_log="[guara_rta]: registration refused")
    assert any("COM_MODE_ARM_CHK" in e for e in check_ac.check_ac15c(run))


def test_ac3_requires_a_negative_control(tmp_path):
    """A monitor stuck at violated=true must not pass AC-3."""
    stuck = [{"monitor_id": "REQ-ALT-01", "violated": True, "inputs_complete": True}] * 10
    (tmp_path / "verdicts.jsonl").write_text("\n".join(json.dumps(v) for v in stuck) + "\n")
    assert any("vacuous" in e for e in check_ac.check_ac3(tmp_path))

    healthy = ([{"monitor_id": "REQ-ALT-01", "violated": False, "inputs_complete": True}] * 5 +
               [{"monitor_id": "REQ-ALT-01", "violated": True, "inputs_complete": True}] * 5)
    (tmp_path / "verdicts.jsonl").write_text("\n".join(json.dumps(v) for v in healthy) + "\n")
    assert check_ac.check_ac3(tmp_path) == []
