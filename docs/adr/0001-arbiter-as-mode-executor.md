# ADR 0001 — RTA arbiter as ModeExecutor vs. independent node

- Status: Proposed (P1, 2026-09-11)
- Related: SPEC §2, §3.5, §4, §5; ADR 0005

## Context

The arbiter must (a) take the complex function (CF) out of control, (b) trigger
Hold/RTL/Land with measurable latency, and (c) have its own failures lead to a
known PX4 reaction. Relevant facts:

- `ModeExecutorBase::scheduleMode/rtl/land` trigger internal modes via
  `VEHICLE_CMD_SET_NAV_STATE` on a dedicated topic [G 1.1-1.4].
- The executor is only in charge when its owned mode is selected; a switch made
  by the user (RC/MAVLink) returns control to the autopilot; switches made by the
  executor keep it in charge [G 1.6, A.2, A.3].
- An external mode that stops answering the arming check drives PX4 to RTL in
  ~1.2 s; `can_arm_and_run=false` produces the same effect in ≤ ~300 ms [G 2.1-2.4, A.5, A.6].
- While armed, PX4 does not accept new registrations [G 2.7, A.16].
- `sendCommandSync` allocates and can block ~3.9 s [G A.1].

## Options

**A. ModeExecutor with a CF "gateway" owned mode (same process).**
The CF publishes setpoints on a Guará topic; the owned mode forwards them to PX4.

**B. ModeExecutor whose owned mode is the CF itself in another process.**
Requires the CF to register the mode and the executor to be the same registration —
the interface-lib binds executor and owned mode in the same object [G 1.5]; there is
no evidence of an executor owning a mode from another process. [UNKNOWN] → discarded without a new P0.

**C. Independent node sending `vehicle_command` as a GCS.**
Commands with source `User` remove any executor from charge [G A.3]; the
arbiter would have no owned mode, hence no liveness signal monitored by
PX4 (FM-1/FM-4 without reaction). Acceptance of `SET_NAV_STATE` coming from
`/fmu/in/vehicle_command` was not verified: [UNKNOWN].

## Decision

Option **A**, with rules:

1. Process `guara_rta` contains `GuaraExecutor` (ModeExecutorBase) and
   `GuaraCfGateway` (ModeBase, owned mode). `Settings.activation =
   ActivateOnlyWhenArmed` (default) [G 1.5].
2. **Decision/actuation split:** `DecisionCore` is pure code (no ROS, no
   allocation after init, bounded time) run by a timer with period `T_s`.
   Actuation (`scheduleMode`, `rtl`, `land`) runs in a separate callback group,
   fed by a fixed-capacity queue. The blocking of [G A.1] stays outside the decision path, per CLAUDE.md.
3. **Core heartbeat:** `GuaraCfGateway::checkArmingAndRunConditions`
   reports failure if the age of the core's last tick > `H_max` (FM-4) [G A.4-A.6].
4. **Gateway as Input Manager:** in the tick that fires T3, the gateway starts
   publishing zero velocity and discards the CF until the state returns to `CF` (FM-7).
5. Guará **never** calls `deferFailsafesSync(true)` (AC-20).
6. `COM_MODE_ARM_CHK` stays `0`: accepting registration in flight would open the door
   to components not inspected before takeoff; PX4 itself documents the default as
   "disabled for safety reasons" [G A.16]. Accepted consequence: FM-3.

## Consequences

- (+) Death or hang of the arbiter with CF active falls into the PX4 fallback
  chain (RTL), without extra code in the FMU.
- (+) The CF does not command PX4 directly through the intended path; the gateway can
  block it in the same tick as the decision.
- (−) The CF depends on the arbiter process: an arbiter crash interrupts the CF.
- (−) With an internal RF active, arbiter death is not detected (FM-2).
- (−) A pilot who switches modes disables Guará until re-entering the owned mode (by design).
- (−) FM-12: the gateway does not prevent other publishers on `/fmu/in/trajectory_setpoint` [G A.13].
- Risks to verify in M3: AC-15, AC-15b, AC-15c, AC-16, AC-16b, AC-21.
