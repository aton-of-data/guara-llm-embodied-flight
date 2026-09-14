# SPDX-License-Identifier: Apache-2.0
"""`GuaraSpaceGateway`'s predicate: ADR 0015 rules 2-6 as a pure, host-free decision.

The space host does not exist yet. The component that will carry this predicate is specified
in ADR 0015 as a passive in-line component taking `Svc::CmdSplitter`'s port shapes
(`GROUNDING.md` D.11) and standing between the command source and `Svc::CmdDispatcher`, which
authorises nothing (D.10). What is written here is the part of that component that has no F´
in it: given a proposal, the arbiter state, the latest attitude and the vehicle model, is the
proposal admitted, and if not, which single rule refused it.

Keeping the predicate here rather than inside a deployment buys two things. It is testable
before any host exists (AC-102), and it is the artifact the eventual FPP component is conformed
*against* (AC-107) rather than trusted to match.

Rule 1 is not decidable from a proposal: it is the declaration that a run's uplink was
authenticated at all, and it is checked on the run contract by `scripts/check_run_contract.py
--profile space` (AC-103, `GROUNDING.md` D.9).

Rules are evaluated in ADR order and the first refusal is the reported one, so a refusal always
names exactly one rule. AC-102 requires more than that: each rule must be the *sole* refuser of
some proposal, which is a property of the rules and not of the ordering, and
`scripts/tests/test_space_gateway.py` constructs each case inside the other rules' envelopes to
show it.

The predicate allocates nothing per call beyond its returned value and holds no module state,
the Python mirror of the arbiter's per-tick rule (CLAUDE.md, SPEC §4).

Time system: every instant here is on the host clock. TAI, UTC and spacecraft elapsed time are
`[PARAMETER TBD]` until AC-99 declares one (ADR 0015 rule 3, `docs/PLAN-M17-M28.md` G-Z5).
"""
from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass, replace

import yaml

RULE_ADMISSIBLE = "rule2_admissible"
RULE_TIME = "rule3_time"
RULE_ENVELOPE = "rule4_envelope"
RULE_KEEPOUT = "rule5_keepout"

#: The rules a proposal can be refused by. Rule 6 refuses nothing; it is the requirement that
#: every refusal below is observable, which `Decision.event` and `Counters` carry.
RULES = (RULE_ADMISSIBLE, RULE_TIME, RULE_ENVELOPE, RULE_KEEPOUT)

STATES = ("INACTIVE", "CF", "RF", "LATCHED")

Vector = tuple[float, float, float]


def norm(v: Vector | None) -> float:
    if v is None:
        return 0.0
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


@dataclass(frozen=True)
class GatewayConfig:
    """The data half of the gate (ADR 0015 rule 2: the admissible set is data, not code)."""

    admissible: dict[str, tuple[str, ...]]
    future_stamp_tolerance_s: float
    proposal_timeout_s: float

    def with_admissible(self, admissible: dict[str, tuple[str, ...]]) -> "GatewayConfig":
        return replace(self, admissible={k: tuple(v) for k, v in admissible.items()})

    def admits(self, arbiter_state: str, verb: str) -> bool:
        return verb in self.admissible.get(arbiter_state, ())


@dataclass(frozen=True)
class VehicleModel:
    vehicle_id: str
    boresights: dict[str, dict]
    targets: dict[str, dict]
    forbidden: dict[str, dict]
    config: GatewayConfig


@dataclass(frozen=True)
class Proposal:
    """What reaches the gate from outside the assured layer. Every field is hostile input."""

    verb: str
    stamp_s: float
    boresight_id: str | None = None
    target_id: str | None = None
    hold_s: float | None = None
    proposed_body_rate_rad_s: Vector | None = None


@dataclass(frozen=True)
class AttitudeState:
    boresight_inertial: Vector
    forbidden_inertial: Vector
    valid: bool = True


@dataclass(frozen=True)
class RefusalEvent:
    """ADR 0015 rule 6: one event per refusal, naming the rule and the opcode involved."""

    rule: str
    verb: str
    detail: str


@dataclass(frozen=True)
class Decision:
    admitted: bool
    rule: str | None
    reason: str
    event: RefusalEvent | None = None
    clamped: tuple[str, ...] = ()
    admitted_body_rate_rad_s: Vector | None = None
    admitted_hold_s: float | None = None
    t_keepout_s: float | None = None


def _refuse(rule: str, verb: str, detail: str) -> Decision:
    reason = f"{rule}: {detail}"
    return Decision(admitted=False, rule=rule, reason=reason,
                    event=RefusalEvent(rule=rule, verb=verb, detail=detail))


def load_vehicle_model(path: pathlib.Path) -> VehicleModel:
    """Read a site model. A missing `gateway` block is an error, not a permissive default."""
    raw = yaml.safe_load(pathlib.Path(path).read_text()) or {}
    gateway = raw.get("gateway")
    if not isinstance(gateway, dict):
        raise ValueError(f"{path}: no `gateway` block; the gate has no admissible set to load")
    admissible = {state: tuple(gateway.get("admissible", {}).get(state, ()))
                  for state in STATES}
    config = GatewayConfig(
        admissible=admissible,
        future_stamp_tolerance_s=float(gateway["future_stamp_tolerance_s"]),
        proposal_timeout_s=float(gateway["proposal_timeout_s"]),
    )
    return VehicleModel(
        vehicle_id=str(raw.get("vehicle_id", "")),
        boresights=raw.get("boresights") or {},
        targets=raw.get("targets") or {},
        forbidden=raw.get("forbidden") or {},
        config=config,
    )


def _check_admissible(proposal: Proposal, arbiter_state: str, model: VehicleModel) -> Decision | None:
    """ADR 0015 rule 2. The gate rejects; it does not route."""
    if arbiter_state not in STATES:
        return _refuse(RULE_ADMISSIBLE, proposal.verb, f"unknown arbiter state {arbiter_state!r}")
    if not model.config.admits(arbiter_state, proposal.verb):
        return _refuse(RULE_ADMISSIBLE, proposal.verb,
                       f"verb {proposal.verb!r} is not admissible in state {arbiter_state}")
    # An identifier the vehicle model does not declare is not an admissible command either: the
    # gate would have nothing to evaluate rule 5 against, and fails closed rather than guessing.
    if proposal.boresight_id is not None and proposal.boresight_id not in model.boresights:
        return _refuse(RULE_ADMISSIBLE, proposal.verb,
                       f"boresight {proposal.boresight_id!r} is not declared by {model.vehicle_id}")
    if proposal.target_id is not None and proposal.target_id not in model.targets:
        return _refuse(RULE_ADMISSIBLE, proposal.verb,
                       f"target {proposal.target_id!r} is not declared by {model.vehicle_id}")
    return None


def _check_time(proposal: Proposal, model: VehicleModel, t_recv_s: float) -> Decision | None:
    """ADR 0015 rule 3. Freshness and ordering come from the reception instant, never from a
    stamp the proposal carries: an untrusted sender must not be able to extend its own liveness
    by stamping ahead, which is review finding H-1 on the air side (ADR 0010 rule 1)."""
    stamp_s, tolerance, timeout = (proposal.stamp_s, model.config.future_stamp_tolerance_s,
                                   model.config.proposal_timeout_s)
    if not math.isfinite(stamp_s) or not math.isfinite(t_recv_s):
        return _refuse(RULE_TIME, proposal.verb, f"stamp {stamp_s!r} is not a finite instant")
    if stamp_s > t_recv_s + tolerance:
        return _refuse(RULE_TIME, proposal.verb,
                       f"stamp leads the reception instant by {stamp_s - t_recv_s:.6f} s "
                       f"> {tolerance} s")
    if t_recv_s - stamp_s > timeout:
        return _refuse(RULE_TIME, proposal.verb,
                       f"already {t_recv_s - stamp_s:.6f} s old on arrival > {timeout} s")
    return None


def decide(*, proposal: Proposal, arbiter_state: str, attitude: AttitudeState,
           model: VehicleModel, t_recv_s: float) -> Decision:
    """Admit or refuse one proposal. `t_recv_s` is the reception instant on the host clock."""
    refusal = _check_admissible(proposal, arbiter_state, model)
    if refusal is not None:
        return refusal
    refusal = _check_time(proposal, model, t_recv_s)
    if refusal is not None:
        return refusal
    return Decision(admitted=True, rule=None, reason="admitted",
                    admitted_body_rate_rad_s=proposal.proposed_body_rate_rad_s,
                    admitted_hold_s=proposal.hold_s)
