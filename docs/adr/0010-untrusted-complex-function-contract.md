# ADR 0010 — Contract for an untrusted (and possibly LLM-driven) Complex Function

- Status: Accepted (2026-09-11)
- Related: SPEC §2 (Input Manager), §3.5 (T5), ADR 0001 rule 4, ADR 0005 items 6-7,
  ADR 0004; `docs/research/LLM-EMBODIMENT.md` §4-§5;
  review `docs/reviews/2026-09-11-m1-m5-review.md` (H-1, H-2, §4, §5)

## Context

ASTM F3269 bounds an untrusted Complex Function with a Safety Monitor and a Recovery Control
Function. Until this ADR, "untrusted" was implemented as *unprivileged*: the CF could only reach PX4
through the owned mode, and only while the arbiter state was CF. Inside that window, however, the CF
was believed:

- freshness was computed from the **CF-supplied stamp**, so one setpoint stamped in the future kept
  the gateway forwarding it after the CF had died (review H-1);
- any finite velocity and yaw were forwarded, while the geofence braking model assumes speeds inside
  the airframe envelope (review H-2);
- the return T5 asked only whether the *vehicle* was clear. A vehicle stopped at the fence is clear,
  so control went back to a CF whose very next setpoint flew at the fence again (review §4). The
  observed effect was T3 → T5 → T3 three times and then a latch.

The long-term goal (`LLM-EMBODIMENT.md`) puts a language model behind that interface. An LLM-driven
CF is not merely unverified: it emits fluent, well-formed commands that can be wrong, and its input
is text that an attacker may control. The gateway is the one place where an untrusted proposal
becomes vehicle motion, so the contract belongs there.

## Decision

Every CF setpoint is treated as hostile input. The gateway (`guara_rta::GatewayLogic`) enforces:

1. **Trusted time.** Freshness and ordering use the *reception* instant on the gateway clock. The
   CF-supplied stamp is only checked for plausibility: a stamp more than
   `gateway.future_stamp_tolerance_s` ahead of the gateway clock, or already older than
   `gateway.cf_timeout_s` on arrival, is rejected. The CF cannot extend its own liveness.
2. **Envelope.** Horizontal speed, climb rate, descent rate and yaw rate are clamped to
   `gateway.max_*`, which must be consistent with the airframe's PX4 limits (`MPC_XY_VEL_MAX`,
   `MPC_Z_VEL_MAX_UP`, `MPC_Z_VEL_MAX_DN`, `MPC_YAWRAUTO_MAX`) and with the braking model of
   ADR 0004. Non-finite components are rejected outright; a yaw outside [-π, π] leaves yaw
   uncontrolled rather than being forwarded.
3. **Shadow check.** Before a setpoint is forwarded, the geofence predictor is evaluated on the
   *proposed* velocity from the latest vehicle state. A proposal whose predicted `T_gf` is not above
   `tau_gf + h_gf` is replaced by zero velocity. The filter acts before the vehicle moves, not after.
4. **Intent-aware return.** T5 additionally requires that the CF's current proposal is clear
   (`Inputs::cf_intent_unsafe` false). A CF that keeps proposing the unsafe motion does not get
   control back; the CF's intent alone never *causes* a recovery, because in CF the gateway already
   filters it.
5. **Observability.** Rejections are counted and published in `RtaState`
   (`cf_rejected_stamp`, `cf_rejected_non_finite`, `cf_rejected_guard`, `cf_clamped`,
   `cf_intent_unsafe`, `cf_intent_t_gf_s`). A CF that is being filtered continuously is a visible
   fact in the run evidence, not a silent condition.
6. **The LLM is never in the setpoint loop.** A language model may propose or update a *plan*; a
   trusted, deterministic plan executor produces setpoints at the gateway's rate. API latency is
   seconds, the gateway timeout is 0.5 s: an LLM that answers late is a planner that is late, never a
   vehicle that is uncommanded.
7. **Model or link unavailability pauses the mission, not the safety layer.** The RTA keeps running
   on PX4-side inputs alone; losing the model is a mission-level event.

## Consequences

- (+) The failure modes an adversarial or hallucinating CF would find first are closed at the
  boundary, and each one has a unit test that fails without the fix
  (`test_gateway_envelope.cpp`, `test_return_policy.cpp`).
- (+) The AC-9 oscillation disappears: in the re-run of 2026-09-11 the fence was held with zero
  outside depth and no mode switch at all, because the proposal was filtered before it moved the
  vehicle.
- (−) A legitimate CF that flies deliberately close to the fence is throttled by the shadow check.
  The margin is `tau_gf + h_gf`, the same margin T5 uses, so the behaviour is at least consistent
  with the return policy.
- (−) The envelope parameters are airframe-specific and are [HYPOTHESIS] until measured; a wrong
  envelope silently limits the mission. They belong in the per-airframe configuration, not in the
  code.
- The contract says nothing about *who* may talk to `/guara/cf/setpoint`. Transport authentication
  (SROS2 on `/guara/cf/*` and `fmu/in/*`, FM-12) is still open and is a precondition for any
  networked or LLM-driven CF; see the remediation note in
  `docs/reviews/2026-09-11-m1-m5-remediation.md`.
