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

from space import keepout

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
    motion_required: tuple[str, ...]
    future_stamp_tolerance_s: float
    proposal_timeout_s: float
    max_slew_rate_rad_s: float
    max_hold_s: float
    tau_ko_s: float
    h_ko_s: float
    horizon_s: float

    @property
    def keepout_margin_s(self) -> float:
        """The margin a pointing proposal must beat: tau_ko + h_ko (ADR 0012 channel table)."""
        return self.tau_ko_s + self.h_ko_s

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
    """The latest attitude the gate evaluates a proposal from.

    `forbidden_inertial` is either one direction or a mapping from the forbidden-body name in
    the vehicle model to its inertial direction; the gate sweeps every entry and refuses on the
    nearest violation, so declaring a second bright body cannot loosen the gate.
    """

    boresight_inertial: Vector
    forbidden_inertial: Vector | dict[str, Vector]
    valid: bool = True

    def forbidden_bodies(self) -> tuple[tuple[str, Vector], ...]:
        if isinstance(self.forbidden_inertial, dict):
            return tuple(self.forbidden_inertial.items())
        return (("forbidden", self.forbidden_inertial),)


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


@dataclass(frozen=True)
class Counters:
    """ADR 0015 rule 6, in the shape a telemetry channel carries.

    A gate that fails silent is indistinguishable from a gate that is absent, so the refusal
    counts are downlinked continuously and not only after a ground pass. They are a value the
    caller carries, not module state: `decide` stays pure and `count` returns a new set.
    """

    refusals: dict[str, int] = None  # type: ignore[assignment]
    admitted: int = 0
    last_event: RefusalEvent | None = None

    def __post_init__(self) -> None:
        if self.refusals is None:
            object.__setattr__(self, "refusals", {rule: 0 for rule in RULES})

    @property
    def total(self) -> int:
        return sum(self.refusals.values())


def count(counters: Counters, decision: Decision) -> Counters:
    """Fold one decision into a counter set. Exactly one counter moves per call."""
    if decision.admitted:
        return Counters(refusals=dict(counters.refusals), admitted=counters.admitted + 1,
                        last_event=counters.last_event)
    refusals = dict(counters.refusals)
    refusals[decision.rule] = refusals.get(decision.rule, 0) + 1
    return Counters(refusals=refusals, admitted=counters.admitted, last_event=decision.event)


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
        motion_required=tuple(gateway.get("motion_required", ())),
        future_stamp_tolerance_s=float(gateway["future_stamp_tolerance_s"]),
        proposal_timeout_s=float(gateway["proposal_timeout_s"]),
        max_slew_rate_rad_s=float(gateway["envelope"]["max_slew_rate_rad_s"]),
        max_hold_s=float(gateway["envelope"]["max_hold_s"]),
        tau_ko_s=float(gateway["tau_ko_s"]),
        h_ko_s=float(gateway["h_ko_s"]),
        horizon_s=float(gateway["horizon_s"]),
    )
    if config.horizon_s < config.keepout_margin_s:
        # Beyond the horizon the predictor reports +inf, which the gate would read as safe.
        raise ValueError(
            f"{path}: gateway.horizon_s {config.horizon_s} < tau_ko + h_ko "
            f"{config.keepout_margin_s}; the shadow check would admit unjudged proposals")
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


def _check_envelope(proposal: Proposal, model: VehicleModel
                    ) -> tuple[Decision | None, Vector | None, float | None, tuple[str, ...]]:
    """ADR 0015 rule 4. Finite magnitudes are clamped to the declared envelope; a non-finite
    magnitude is refused outright, because there is no value to clamp it to.

    The envelope is a Guará declaration, not a reading from the vehicle: ADR 0015 consequence 5
    records that a wrong declaration narrows the mission, and the site model marks every value
    `[PARAMETER TBD]` and `[REVIEW]`."""
    clamped: list[str] = []
    rate = proposal.proposed_body_rate_rad_s
    if rate is not None:
        if not all(math.isfinite(v) for v in rate):
            return (_refuse(RULE_ENVELOPE, proposal.verb,
                            f"body rate {rate!r} is not finite; refused, not clamped"),
                    None, None, ())
        magnitude = norm(rate)
        if magnitude > model.config.max_slew_rate_rad_s:
            scale = model.config.max_slew_rate_rad_s / magnitude
            rate = (rate[0] * scale, rate[1] * scale, rate[2] * scale)
            clamped.append("proposed_body_rate_rad_s")
    hold_s = proposal.hold_s
    if hold_s is not None:
        if not math.isfinite(hold_s):
            return (_refuse(RULE_ENVELOPE, proposal.verb,
                            f"hold {hold_s!r} is not finite; refused, not clamped"),
                    None, None, ())
        if hold_s > model.config.max_hold_s:
            hold_s = model.config.max_hold_s
            clamped.append("hold_s")
    return None, rate, hold_s, tuple(clamped)


def _check_keepout(proposal: Proposal, attitude: AttitudeState, model: VehicleModel,
                   rate: Vector | None) -> tuple[Decision | None, float | None]:
    """ADR 0015 rule 5. Evaluate `space.keepout` on the *proposed* motion before admitting it.

    This is the one rule that deliberately differs from ADR 0010 rule 3: the air gateway clamps
    a velocity, this one refuses the proposal whole, because a half-executed slew is not a
    smaller slew. Fail-closed: no attitude, no boresight, no decision."""
    must_move = proposal.verb in model.config.motion_required
    if rate is None or norm(rate) == 0.0:
        if must_move:
            # A proposer that declines to declare its motion does not thereby escape the rule.
            return _refuse(RULE_KEEPOUT, proposal.verb,
                           f"{proposal.verb} declares no motion to shadow-check; refused"), None
        return None, None  # nothing is commanded to move; there is no motion to shadow
    if not attitude.valid:
        return _refuse(RULE_KEEPOUT, proposal.verb,
                       "attitude state is not valid; the shadow check cannot be evaluated"), None
    boresight = model.boresights.get(proposal.boresight_id or "")
    if not boresight:
        return _refuse(RULE_KEEPOUT, proposal.verb,
                       "proposal commands motion without a boresight to protect"), None
    theta_min = float(boresight["keepout_theta_min_rad"])
    worst_name, worst_t = "", math.inf
    for name, direction in attitude.forbidden_bodies():
        t_s = keepout.predict(attitude.boresight_inertial, direction, rate, theta_min,
                              model.config.horizon_s)
        if t_s < worst_t:
            worst_name, worst_t = name, t_s
    if not worst_t > model.config.keepout_margin_s:
        return _refuse(RULE_KEEPOUT, proposal.verb,
                       f"predicted {worst_t:.3f} s to the {worst_name} keep-out cone, not above "
                       f"tau_ko + h_ko = {model.config.keepout_margin_s} s; refused whole"), None
    return None, worst_t


def decide(*, proposal: Proposal, arbiter_state: str, attitude: AttitudeState,
           model: VehicleModel, t_recv_s: float) -> Decision:
    """Admit or refuse one proposal. `t_recv_s` is the reception instant on the host clock."""
    refusal = _check_admissible(proposal, arbiter_state, model)
    if refusal is not None:
        return refusal
    refusal = _check_time(proposal, model, t_recv_s)
    if refusal is not None:
        return refusal
    refusal, rate, hold_s, clamped = _check_envelope(proposal, model)
    if refusal is not None:
        return refusal
    refusal, t_keepout_s = _check_keepout(proposal, attitude, model, rate)
    if refusal is not None:
        return refusal
    reason = "admitted" if not clamped else "admitted, clamped: " + ", ".join(clamped)
    return Decision(admitted=True, rule=None, reason=reason, clamped=clamped,
                    admitted_body_rate_rad_s=rate, admitted_hold_s=hold_s,
                    t_keepout_s=t_keepout_s)
