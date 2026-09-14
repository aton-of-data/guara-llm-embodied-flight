#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-102: ADR 0015 rules 2-6, each the sole refuser of a proposal that violates only it.

The falsifier the packet names is independence: a proposal crafted to violate exactly one
rule must be refused by that rule and by no other, and the same proposal with the violation
removed must be admitted. Every case below is therefore built inside the other rules'
envelopes, so a second rule naming itself is a real finding and not a fixture accident.

Rule 1 (declared command origin) is not a property of a proposal; it is checked on the run
contract and lives at the end of this file with AC-103.
"""
import math
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from space import gateway as gw  # noqa: E402

SITE = ROOT / "space/site/demo_sat.yaml"


@pytest.fixture(scope="module")
def model() -> "gw.VehicleModel":
    return gw.load_vehicle_model(SITE)


def nominal(**overrides) -> dict:
    """A slew that every rule admits: fresh, inside the envelope, pointing away from the sun.

    The boresight is +x, the forbidden direction is +z, so the angle is pi/2 and a body rate
    about -y rotates the boresight away from it. theta_min for instrument-a is 0.35 rad.
    """
    base = dict(
        verb="slew",
        boresight_id="instrument-a",
        target_id="ground-station-1",
        stamp_s=100.0,
        hold_s=None,
        proposed_body_rate_rad_s=(0.0, 0.01, 0.0),
    )
    base.update(overrides)
    return base


def state(**overrides) -> "gw.AttitudeState":
    base = dict(
        boresight_inertial=(1.0, 0.0, 0.0),
        forbidden_inertial=(0.0, 0.0, 1.0),
        valid=True,
    )
    base.update(overrides)
    return gw.AttitudeState(**base)


def decide(model, *, arbiter_state="CF", t_recv_s=100.0, **overrides) -> "gw.Decision":
    return gw.decide(
        proposal=gw.Proposal(**nominal(**overrides)),
        arbiter_state=arbiter_state,
        attitude=state(),
        model=model,
        t_recv_s=t_recv_s,
    )


# --- the control: nothing is violated -------------------------------------------------

def test_nominal_proposal_is_admitted(model):
    d = decide(model)
    assert d.admitted, d.reason
    assert d.rule is None


# --- rule 2: the gate rejects, it does not route --------------------------------------

def test_rule2_refuses_an_opcode_the_state_does_not_permit(model):
    d = decide(model, arbiter_state="LATCHED")
    assert not d.admitted
    assert d.rule == "rule2_admissible"
    # The violation removed: the same proposal in a state that permits the verb.
    assert decide(model, arbiter_state="CF").admitted


def test_rule2_refuses_an_identifier_the_vehicle_model_does_not_declare(model):
    d = decide(model, boresight_id="instrument-z")
    assert not d.admitted
    assert d.rule == "rule2_admissible"
    assert decide(model, boresight_id="instrument-a").admitted


def test_rule2_admissible_set_is_data_not_a_literal(model):
    narrowed = gw.VehicleModel(
        vehicle_id=model.vehicle_id,
        boresights=model.boresights,
        targets=model.targets,
        forbidden=model.forbidden,
        config=model.config.with_admissible({"CF": ("status",)}),
    )
    d = gw.decide(proposal=gw.Proposal(**nominal()), arbiter_state="CF",
                  attitude=state(), model=narrowed, t_recv_s=100.0)
    assert not d.admitted and d.rule == "rule2_admissible"


def test_rule2_status_is_admissible_in_every_state(model):
    for st in ("INACTIVE", "CF", "RF", "LATCHED"):
        d = decide(model, arbiter_state=st, verb="status", boresight_id=None, target_id=None,
                   proposed_body_rate_rad_s=None)
        assert d.admitted, f"{st}: {d.reason}"


def test_rule2_never_releases_the_safe_mode_latch(model):
    # ADR 0015 rule 7: no admitted opcode leaves LATCHED. The gate has no release path.
    for verb in ("slew", "point_hold", "safe_mode", "abort"):
        d = decide(model, arbiter_state="LATCHED", verb=verb)
        assert not d.admitted, verb
    assert not hasattr(gw, "release_latch")


# --- rule 3: trusted time -------------------------------------------------------------

def test_rule3_refuses_a_stamp_ahead_of_the_reception_instant(model):
    tol = model.config.future_stamp_tolerance_s
    d = decide(model, stamp_s=100.0 + 10 * tol, t_recv_s=100.0)
    assert not d.admitted
    assert d.rule == "rule3_time"
    assert decide(model, stamp_s=100.0, t_recv_s=100.0).admitted


def test_rule3_refuses_a_proposal_already_stale_on_arrival(model):
    timeout = model.config.proposal_timeout_s
    d = decide(model, stamp_s=100.0, t_recv_s=100.0 + 10 * timeout)
    assert not d.admitted
    assert d.rule == "rule3_time"


def test_rule3_uses_the_reception_instant_not_the_carried_stamp(model):
    # Two proposals agreeing on the stamp and differing only in when they arrived must
    # decide differently: the gate cannot be reading freshness off the proposal.
    fresh = decide(model, stamp_s=100.0, t_recv_s=100.0)
    late = decide(model, stamp_s=100.0, t_recv_s=100.0 + 10 * model.config.proposal_timeout_s)
    assert fresh.admitted and not late.admitted


def test_rule3_refuses_a_non_finite_stamp(model):
    for bad in (math.nan, math.inf, -math.inf):
        d = decide(model, stamp_s=bad)
        assert not d.admitted and d.rule == "rule3_time"


# --- rule 4: envelope -----------------------------------------------------------------

def test_rule4_refuses_a_non_finite_magnitude_outright(model):
    for bad in (math.nan, math.inf):
        d = decide(model, proposed_body_rate_rad_s=(0.0, bad, 0.0))
        assert not d.admitted
        assert d.rule == "rule4_envelope"
        assert d.clamped == ()
    assert decide(model, proposed_body_rate_rad_s=(0.0, 0.01, 0.0)).admitted


def test_rule4_refuses_a_non_finite_hold(model):
    d = decide(model, verb="point_hold", hold_s=math.nan)
    assert not d.admitted and d.rule == "rule4_envelope"


def test_rule4_clamps_a_finite_magnitude_and_admits_it(model):
    # ADR 0015 rule 4 clamps; only a non-finite value is refused. The clamp must be visible.
    over = 10 * model.config.max_slew_rate_rad_s
    d = decide(model, proposed_body_rate_rad_s=(0.0, over, 0.0))
    assert d.admitted
    assert "proposed_body_rate_rad_s" in d.clamped
    assert gw.norm(d.admitted_body_rate_rad_s) == pytest.approx(
        model.config.max_slew_rate_rad_s, rel=1e-9)


def test_rule4_clamps_the_hold_duration(model):
    d = decide(model, verb="point_hold", hold_s=10 * model.config.max_hold_s)
    assert d.admitted
    assert "hold_s" in d.clamped
    assert d.admitted_hold_s == pytest.approx(model.config.max_hold_s)


def test_rule4_leaves_a_proposal_inside_the_envelope_untouched(model):
    d = decide(model, verb="point_hold", hold_s=1.0)
    assert d.admitted and d.clamped == ()
    assert d.admitted_hold_s == pytest.approx(1.0)


# --- rule 5: keep-out shadow check ----------------------------------------------------

def closing_rate(model) -> tuple[float, float, float]:
    """A rate inside the rule-4 envelope that still closes the cone inside tau_ko + h_ko.

    boresight +x, forbidden +z: the closing axis is x cross z = -y, so a rate along -y
    rotates the boresight toward the sun. theta = pi/2, theta_min = 0.35 rad, and
    tau_ko + h_ko = 35 s, so any omega above (pi/2 - 0.35)/35 = 0.0349 rad/s closes in time.
    """
    rate = model.config.max_slew_rate_rad_s  # 0.05 rad/s > 0.0349, and exactly on the envelope
    return (0.0, -rate, 0.0)


def test_rule5_refuses_a_slew_that_closes_the_keep_out_cone(model):
    d = decide(model, proposed_body_rate_rad_s=closing_rate(model))
    assert not d.admitted
    assert d.rule == "rule5_keepout"
    # Inside the rule-4 envelope, so rule 4 is not what refused it.
    assert d.clamped == ()
    # The violation removed: the same magnitude rotating away from the forbidden direction.
    away = tuple(-v for v in closing_rate(model))
    assert decide(model, proposed_body_rate_rad_s=away).admitted


def test_rule5_refuses_the_slew_whole_and_never_truncates_it(model):
    d = decide(model, proposed_body_rate_rad_s=closing_rate(model))
    assert not d.admitted
    assert d.admitted_body_rate_rad_s is None
    assert d.clamped == ()


def test_rule5_margin_is_above_tau_plus_h_for_every_admitted_slew(model):
    d = decide(model)
    assert d.admitted
    assert d.t_keepout_s > model.config.tau_ko_s + model.config.h_ko_s


def test_rule5_refuses_when_the_attitude_state_is_invalid(model):
    d = gw.decide(proposal=gw.Proposal(**nominal()), arbiter_state="CF",
                  attitude=state(valid=False), model=model, t_recv_s=100.0)
    assert not d.admitted and d.rule == "rule5_keepout"


def test_rule5_does_not_gate_a_proposal_with_no_motion(model):
    d = decide(model, verb="status", boresight_id=None, target_id=None,
               proposed_body_rate_rad_s=None)
    assert d.admitted
    assert d.t_keepout_s is None


# --- rule 6: observability ------------------------------------------------------------

def refusing_cases(model) -> list[tuple[str, "gw.Decision"]]:
    return [
        ("rule2_admissible", decide(model, arbiter_state="LATCHED")),
        ("rule3_time", decide(model, stamp_s=200.0)),
        ("rule4_envelope", decide(model, proposed_body_rate_rad_s=(0.0, math.nan, 0.0))),
        ("rule5_keepout", decide(model, proposed_body_rate_rad_s=closing_rate(model))),
    ]


def test_rule6_every_refusal_raises_exactly_one_event_naming_its_rule_and_verb(model):
    for rule, d in refusing_cases(model):
        assert d.rule == rule
        assert d.event is not None
        assert d.event.rule == rule
        assert d.event.verb == ("slew" if rule != "rule2_admissible" else "slew")
        assert rule in d.reason


def test_rule6_no_refusal_is_silent(model):
    for _, d in refusing_cases(model):
        assert not d.admitted and d.event is not None


def test_rule6_counters_increment_only_the_rule_that_refused(model):
    counters = gw.Counters()
    for rule, d in refusing_cases(model):
        before = counters
        counters = gw.count(counters, d)
        delta = {k: counters.refusals[k] - before.refusals[k] for k in counters.refusals}
        assert delta.pop(rule) == 1
        assert set(delta.values()) == {0}
    assert counters.total == len(refusing_cases(model))


def test_rule6_an_admitted_proposal_raises_no_refusal_event(model):
    d = decide(model)
    assert d.admitted and d.event is None
    counters = gw.count(gw.Counters(), d)
    assert counters.total == 0
    assert counters.admitted == 1


def test_rule6_counters_are_a_returned_value_and_the_predicate_holds_no_state(model):
    first = decide(model, arbiter_state="LATCHED")
    second = decide(model, arbiter_state="LATCHED")
    assert first == second, "decide() is not pure: two identical calls disagree"


# --- the rules are independent, which is the packet's falsifier -----------------------

def test_every_rule_is_the_sole_refuser_of_at_least_one_case(model):
    named = {rule for rule, _ in refusing_cases(model)}
    assert named == set(gw.RULES)


# --- rule 1 (AC-103): the run contract declares the command origin --------------------

def contract(tmp_path, **command_path) -> pathlib.Path:
    import yaml

    run = tmp_path / "20260913T000000Z_space_demo"
    run.mkdir()
    (run / "config.yaml").write_text(yaml.safe_dump({
        "run_id": run.name,
        "created_utc": "2026-09-13T00:00:00+00:00",
        "scenario": "space_slew_demo",
        "scenario_sha256": "0" * 64,
        "seed": 42,
        "headless": True,
        "guara_sha": "0" * 40,
        "guara_dirty": False,
        "command_path": command_path,
    }))
    return run


def run_contract(run: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_run_contract.py"), "--profile", "space",
         str(run)],
        capture_output=True, text=True, cwd=str(ROOT))


def test_ac103_unauthenticated_run_is_permitted_and_marked(tmp_path):
    run = contract(tmp_path, authenticated=False, sdls_sa_index=0,
                   decryptor="Svc::Ccsds::ClearTextDecryptor")
    result = run_contract(run)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "unauthenticated" in result.stdout


def test_ac103_authenticated_claim_over_cleartext_fails(tmp_path):
    run = contract(tmp_path, authenticated=True, sdls_sa_index=0,
                   decryptor="Svc::Ccsds::ClearTextDecryptor")
    result = run_contract(run)
    assert result.returncode == 1
    assert "D.9" in result.stdout


def test_ac103_authenticated_claim_with_a_real_decryptor_passes(tmp_path):
    run = contract(tmp_path, authenticated=True, sdls_sa_index=3,
                   decryptor="Svc::Ccsds::AesGcmDecryptor")
    result = run_contract(run)
    assert result.returncode == 0, result.stdout + result.stderr


def test_ac103_a_space_run_without_the_declaration_fails(tmp_path):
    import yaml

    run = tmp_path / "20260913T000000Z_no_decl"
    run.mkdir()
    (run / "config.yaml").write_text(yaml.safe_dump({"run_id": run.name, "seed": 42}))
    assert run_contract(run).returncode == 1
