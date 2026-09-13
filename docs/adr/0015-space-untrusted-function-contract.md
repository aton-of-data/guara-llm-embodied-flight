# ADR 0015 — Contract for an untrusted (and possibly LLM-driven) function in the space domain

- Status: Proposed (2026-09-13)
- Related: ADR 0010 (the air contract this instantiates), ADR 0011 (F´ as the second host),
  ADR 0012 (channels and the latched safe mode), ADR 0013 (LLM evaluation protocol);
  SPEC §2, §3.5 (T5); `docs/research/SPACE-AUTONOMY.md` §2, §4, §6;
  `GROUNDING.md` Addendum D (D.2, D.3, D.4, D.9, D.10, D.11);
  review `docs/reviews/2026-09-13-roadmap-docs-site-review.md` (G-2, G-3)

## Context

Rule T (`docs/PLAN-M8-M16.md` §1) asserts one chain in both domains: intent → deterministic
compiler → validated plan or sequence → trusted executor → **gateway** → RTA → recovery function.
Six of those seven elements are specified for space. The gateway is not.

ADR 0010 specifies the gateway once, and it is air-shaped throughout: it names
`guara_rta::GatewayLogic`, a `CfSetpoint` carrying horizontal speed, climb rate, descent rate and
yaw rate, PX4 parameters as the clamp source, and the geofence braking model of ADR 0004 as the
shadow check. ADR 0012 maps the *channels* and the *recovery function* for space and says nothing
about the gate. So the space domain, as specified today, has an untrusted function whose proposals
reach a trusted disposer with no stated filter, and ADR 0010's closing note — "the contract says
nothing about *who* may talk to the CF topic" — has no space counterpart at all.

Three facts from the pinned clone decide the shape of the answer, and all three are recorded in
`GROUNDING.md` before this ADR, not inferred:

- **The command path has no authorization.** `Svc::CmdDispatcher` decodes an opcode, looks it up in
  a registration table and dispatches; no requirement conditions dispatch on origin (D.10). A gate
  must therefore be a component standing in the path, not a policy applied to one.
- **F´ already has the shape for such a component.** `Svc::CmdSplitter` is a passive in-line
  component with `sync input array` command buffers, a mirrored output array and forwarded
  `Fw::CmdResponse`, that routes by opcode against one configured value (D.11). A gate that rejects
  rather than routes is the same component with a different predicate.
- **Uplink authentication exists upstream and is off by default.** F´ v4.3.0 ships
  `CcsdsSdlsDeframer` → `SdlsSaRouter` → decryptor in the `ComCcsdsSdls` subtopology, selecting a
  decryptor per security-association index from a compile-time map — and the default decryptor is
  `ClearTextDecryptor`, which performs no authentication, no integrity checking and no decryption,
  with SA 0 mapped to it (D.9). Authenticated telecommand is a configuration and a real decryptor,
  not new architecture; an unconfigured F´ deployment is an unauthenticated command path.

The asymmetry this leaves is hard to defend. On the air side an unauthenticated command path is a
published, numbered limitation (FM-12) with a milestone against it (M9b, AC-32/AC-33) and a rule
that a run using one must declare it. On the space side, where the operator is minutes away at
best and the recovery function is latched until a ground command releases it (ADR 0012 decision 3),
the same exposure is currently unnamed.

## Decision

Every proposal that reaches the space host from outside the assured layer is treated as hostile
input, by the same seven-rule structure as ADR 0010, instantiated on F´ signals. The gate is a
new component, `GuaraSpaceGateway`, standing in the command path with `Svc::CmdSplitter`'s port
shapes (D.11).

1. **Declared command origin.** Every space run declares the security association index and the
   decryptor instance its uplink was configured with (D.9). A deployment that reaches the gateway
   through SA 0 / `ClearTextDecryptor` is an *unauthenticated* command path; it is permitted for
   simulation and bench work and its runs are marked as such in the run contract, exactly as the
   air side marks an SROS2-less run. No space evidence directory may assert an authenticated
   command origin that the SA map does not support.

2. **The gate rejects; it does not route.** `GuaraSpaceGateway` sits between the command source and
   `Svc::CmdDispatcher`, takes the `Fw.Com` / `Fw.CmdResponse` port arrays of `Svc::CmdSplitter`,
   and admits a command only when its opcode is in a compile-time admissible set *and* the
   arbiter's state permits that opcode now. Everything else is answered with a `Fw::CmdResponse`
   failure and an event naming the rule that refused it. The admissible set is data, not code:
   changing it is a configuration change with a recorded hash, never a rebuild of the predicate.

3. **Trusted time.** Freshness and ordering use the reception instant on the host clock, never a
   stamp carried by the proposal. A sequence or directive whose own time fields are ahead of the
   host clock by more than `gateway.future_stamp_tolerance_s`, or already stale on arrival, is
   refused. Until the time system of AC-99 is declared (TAI / UTC / spacecraft elapsed time), this
   rule is stated against the host clock alone and the ADR records that as a `[PARAMETER TBD]`.

4. **Envelope.** Commanded attitude rates, slew durations and any actuator-facing magnitude the
   space intent schema can express are clamped to a per-vehicle envelope, declared in
   configuration alongside the parameter-set hash (G-K8). Non-finite values are refused outright
   rather than clamped. The air rule's clamp sources (PX4 parameters) have no F´ analogue, so the
   envelope is a Guará-side declaration and is `[REVIEW]` until an ADCS model supports it.

5. **Shadow check.** Before a slew or pointing proposal is admitted, the attitude keep-out
   predictor (`space/keepout.py`, AC-47) is evaluated on the *proposed* motion from the latest
   attitude state. A proposal whose predicted time to keep-out violation is not above
   `tau_ko + h_ko` is refused, not clamped: unlike a velocity, a partially executed slew has no
   safe truncation, so the proposal is rejected whole. This is the one rule that deliberately
   differs from ADR 0010 rule 3.

6. **Observability.** Every refusal increments a counter published as telemetry and raises one
   event carrying the rule that refused it and the opcode involved — the F´ analogue of ADR 0010
   rule 5's `RtaState` counters. A gate that is refusing continuously is a visible fact in the
   downlink, not a silent condition, and it is visible without a ground pass having occurred.

7. **The model is never in the command loop, and the latch is not the gate's to open.** A language
   model may propose an intent; the deterministic compiler turns it into a sequence that
   `Svc::FpySequencer` validates before running (D.3, D.4). The gateway never releases the
   safe-mode latch: release requires an authenticated ground telecommand and no on-board path
   exists (ADR 0012 decision 3, AC-98). An unreachable model pauses the mission and changes
   nothing in the assured layer.

The set is deliberately the same seven rules as ADR 0010, in the same order, so that a reader who
knows one domain can read the other by diff. Where a rule cannot transfer — rule 4's clamp source,
rule 5's truncation — the ADR says so rather than inventing an equivalence.

## Consequences

- (+) Rule T becomes true in both domains: the chain it asserts has no unspecified element left.
- (+) The space analogue of FM-12 is named before any space run produces evidence, so no space
  evidence directory can be written that quietly assumes an authenticated uplink.
- (+) Authentication costs configuration, not design: D.9's pipeline is already upstream, and the
  work is an SA map, a real decryptor and a rejection test — the shape AC-98 already asks for.
- (+) `GuaraSpaceGateway` is testable before any F´ deployment exists, because its predicate is
  the same pure decision the kernel already exports through the C ABI; it enters the conformance
  vector set as gateway rules do for air (AC-63, ADR 0010 rules in the kit).
- (−) Rule 4's envelope has no authoritative source the way PX4 parameters are authoritative for
  air. It is a Guará declaration, and a wrong declaration silently narrows the mission. It is
  `[REVIEW]` and belongs in per-vehicle configuration.
- (−) Rule 3 is incomplete until AC-99 declares the time system. Stating it against the host clock
  is correct and insufficient; the gap is recorded rather than closed by assumption.
- (−) One more component in the command path is one more thing between the ground and the vehicle.
  The mitigation is that it is passive, its predicate is pure, and its refusals are events: a gate
  that fails silent is indistinguishable from a gate that is absent, so rule 6 is not optional.
- The gate does not make the sequencer trustworthy. `Svc::FpySequencer` is pre-release upstream
  (D.4) and the intent → sequence compiler stays independent of it (risk RS-2).

## Alternatives rejected

| Alternative | Why not |
|---|---|
| Extend ADR 0010 with a space section | ADR 0010 is Accepted and its rules are written against `GatewayLogic` and `CfSetpoint`. Editing an accepted decision to carry a second host obscures which rules were ever tested on which host. A sibling ADR keeps both auditable, and the air ADR gains only a pointer |
| Rely on SDLS authentication alone | Authentication answers *who sent this*, never *may this be executed now*. D.10 shows nothing in the command path answers the second question. An authenticated ground station can still command a slew through a keep-out |
| Put the gate inside the arbiter component | The arbiter runs on a rate group (ADR 0011); the command path is event-driven. Coupling them would make command admission depend on the tick and give the arbiter two jobs. `Svc::CmdSplitter` shows the in-line passive shape is the idiomatic one (D.11) |
| Gate the `FpySequencer` directives instead of the commands | The sequencer is pre-release (D.4) and is deliberately replaceable. A gate bound to its directive interface would be bound to an interface the project has said it will not depend on |
| Defer the whole contract to M26/M27, when a host exists | The contract is what the host is built against. Deferring it means the first F´ deployment defines the boundary by accident, which is exactly how the air side acquired the H-1 and H-2 findings that ADR 0010 exists to close |
