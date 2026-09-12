# ADR 0012 — Space-domain RTA: signals, recovery function, and simulator

- Status: Accepted (2026-09-11); implementation M13–M16 (`docs/PLAN-M8-M16.md`)
- Related: ADR 0003 (DAIDALUS isolation), ADR 0004 (geofence prediction), ADR 0005 (return
  to CF), ADR 0011 (F´ as second host); SPEC §3.1, §7.2; `docs/research/SPACE-AUTONOMY.md` §5, §6

## Context

The temptation when moving Guará to a satellite is to keep the signal names and change the
units. `T_gf` and `T_daa` do not survive that move:

- The geofence predictor's braking model (ADR 0004) assumes the vehicle can stop. An
  orbiting body cannot. "Recovery" costs Δv or wheel momentum, and the recovery manoeuvre
  itself must satisfy the same constraints it is recovering from — the simultaneous
  constraint-satisfaction problem of the attitude-manoeuvring RTA literature.
- `T_daa` is a DO-365 well-clear construct from DAIDALUS, an air-traffic object. Orbital
  conjunction assessment is probabilistic, screened on the ground with days of lead time,
  and the manoeuvre decision is an operational process, not a reflex. Claiming "DAA for
  satellites" from a DAIDALUS port would be overreach **[REVIEW]**.

What does transfer is the *shape* of the architecture: a predicted time to violation of a
declared constraint, a threshold with hysteresis and dwell, an asymmetric switch into a
recovery function, and a gate that stops the untrusted function from acting.

## Decision

1. **The space channel set replaces, not extends, the air channel set.** Channels in the
   space profile:

   | Channel | Signal | First implementation |
   |---|---|---|
   | `attitude_keepout` | Predicted time until a protected boresight (instrument, star tracker) comes within `θ_min` of a bright body, from current attitude and body rates | Analytic geometric predictor, tested the way AC-8 tests the geofence predictor |
   | `power_margin` | Predicted state of charge at the end of the current eclipse given the commanded load set, against `soc_min` | Energy model with declared assumptions, all values [PARAMETER TBD] |
   | `momentum` | Predicted reaction-wheel momentum against saturation inside the sequence horizon | Model-based, [PARAMETER TBD] |
   | `inputs_valid` | Stale, missing or invalid inputs — loss of attitude knowledge, sensor blinding, eclipse-driven dropouts | Ports directly from `guara_rta`'s Input Manager, including ADR 0010's trusted-time rule |
   | `requirements` | Copilot monitors generated from FRETish requirements | Toolchain ports unchanged; only the requirements differ |

   **There is no DAA channel.** DAIDALUS stays in `nosa/` and out of the space thread
   (ADR 0003 unchanged). Proximity keep-out volumes, if ever added, are a separate channel
   with their own ADR, not a DAIDALUS reuse.

2. **The recovery function is a safe mode that the project writes.** F´ has none
   (`docs/research/SPACE-AUTONOMY.md` §2.2). The v1 safe mode is specified as: stop the
   running sequence, command a declared survivable attitude (sun-pointing), shed the
   declared non-essential load set, and hold until the ground releases it. Its
   properties are FRETish requirements and its release requires an explicit ground
   command — there is **no automatic return to the complex function in the space
   profile**.

3. **The return policy changes, and the change is the point.** ADR 0005 allows
   `RF(HOLD) → CF` after hysteresis and dwell because Hold is cheap and a pilot is
   watching. In orbit nobody is watching within the light-time delay, and safe mode is a
   declared operational state a ground team is expected to clear. So the space profile is
   `T5` disabled: `LATCHED` on entry to safe mode, released only by ground command. The
   decision core already supports latching (P-4, AC-13); the space profile is a
   configuration of the same core, not new logic.

4. **`attitude_keepout` is the first monitor implemented.** It is geometric, has exact
   analytic test cases, and it maps to a real mission-loss mechanism (a pointing error
   that puts a bright body into a star tracker or an instrument aperture). Power and
   momentum follow, because they need an energy and an actuator model whose fidelity would
   otherwise bound every claim made about them.

5. **Simulator: Basilisk, reached through the existing ROS 2 arbiter first.** Basilisk is
   an astrodynamics framework of C/C++ modules scripted from Python, with
   faster-than-real-time and Monte-Carlo modes, which is what the batch statistics of
   RQ1/RQ2 need. A published Basilisk ↔ ROS 2 bridge means the *existing* `guara_rta` node
   can be exercised against orbital dynamics before any F´ code exists. NOS3/42 is the
   secondary option and is cFS-oriented, which suits Ogma's cFS backend rather than its F´
   one. The F´ `Ref` deployment with no dynamics is used only for interface and latency
   tests.

6. **Evidence discipline is unchanged.** A space run writes `results/{run_id}/` with seed,
   pinned commits, Guará SHA and a log, and passes `scripts/check_run_contract.py`, exactly
   as a SITL run does. No number enters a document except through `scripts/aggregate.py`.

## Consequences

- (+) The space thread makes claims only about constraints it actually models, and says so.
- (+) The cheapest experiment comes first: orbital dynamics against the existing core,
  before the expensive F´ port (ADR 0011 decision 2).
- (+) The `LATCHED`-on-safe-mode profile is a genuinely different recovery policy, so the
  two hosts exercise two different corners of the same decision core.
- (−) Two of the three new monitors depend on models (power, momentum) that are
  [HYPOTHESIS] until calibrated against Basilisk, which bounds any result from them.
- (−) Dropping the DAA channel means the space thread cannot reuse the DAIDALUS work at
  all, so the ADR 0003 investment does not amortise across hosts.
- (−) Basilisk fidelity bounds every space claim (risk RS-4); analytic cases must pass
  before any Basilisk number is reported.
