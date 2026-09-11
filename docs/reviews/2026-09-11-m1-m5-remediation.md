# Remediation of the M1–M5 review (2026-09-11)

Closes every finding of [`2026-09-11-m1-m5-review.md`](2026-09-11-m1-m5-review.md). Method: for each
finding, a test that fails against the old behaviour (CLAUDE.md, Engineering), then the fix, then a
re-run of the acceptance criteria the finding touched. Run artifacts stay in `results/`; the run
contracts and computed metrics referenced below are published under `docs/evidence/`.

Scope note: the review was written at `aa449d1`. `C-2` had already been repaired at HEAD by
`fe0ce97`; what was missing was the regression test that would have caught it, which is part of this
work.

## 1. Critical

### C-1 — AC-15c was a false PASS · closed, criterion re-run

PX4 SITL raises `COM_MODE_ARM_CHK` to 1 (`init.d-posix/px4-rc.simulator:8`), so registration while
armed was permitted and the run matched the *accept*-path warning `Mode '…' already registered`
(`ModeManagement.cpp:137`) instead of the rejection
(`ModeManagement.cpp:378`).

- The runner now pins every PX4 parameter the architecture depends on, reads it back, fails the run
  if the read-back differs, and records the pair in `config.yaml`
  (`scripts/sitl/run_scenario.py`, `REQUIRED_PX4_PARAMS`).
- AC-2's run contract checks the recorded value (`scripts/check_run_contract.py`).
- The AC-15c checker requires the rejection string, the pinned parameter, and a restart log in which
  the arbiter did **not** register; it now fails if `already registered` is present at all.
- The scenario waits for the rejection string, not the warning.

Re-run (`20260911T222015Z_restart_arbiter_armed_s42`):

```
[sitl_run] 22:20:17 param COM_MODE_ARM_CHK := 0 (read back 0)
[sitl_run] 22:20:44 log matched 'Not accepting registration requests while armed' in px4.log
PASS run contract: 20260911T222015Z_restart_arbiter_armed_s42
PX4 rejected the armed registration and the restarted arbiter did not register
PASS AC-15c
```

The restarted arbiter's own log ends with
`what(): registration of executor and owned mode failed` — FM-3 is now genuinely exercised.

### C-2 — checker regression could not fail the build · closed

`scripts/tests/test_check_ac.py` (pytest, no ROS or PX4 needed) asserts that every entry of
`CHECKERS` is callable and fails *cleanly* on an empty run directory, which is exactly what the
`NameError` of `7d6ddeb` would have broken. The same file pins C-1 with fixtures: the accept-path
warning must not be accepted as evidence of a rejection.

```
$ ./scripts/dev.sh python3 -m pytest scripts/tests -q
20 passed in 5.90s
```

## 2. High — safety defects

| ID | Fix | Test that fails without it |
|---|---|---|
| H-1 | Freshness and ordering are measured from the reception instant on the gateway clock; a stamp ahead of now by more than `gateway.future_stamp_tolerance_s`, or already older than the timeout on arrival, is rejected and counted. | `test_gateway_envelope.cpp`: `FutureStampDoesNotDefeatTheLivenessTimeout`, `AgeIsMeasuredFromReception`, `SetpointReceivedBeforeEntryIsDiscarded` |
| H-2 | Velocity is clamped to `gateway.max_speed_h_m_s` / `max_climb_rate_m_s` / `max_descent_rate_m_s`, yaw is rate limited to `max_yaw_rate_rad_s`, non-finite components are rejected, out-of-range yaw leaves yaw uncontrolled. | `VelocityIsClampedToTheEnvelope`, `NonFiniteIsRejected`, `YawIsRateLimited`, `OutOfRangeYawLeavesYawUncontrolled` |
| H-3 | `ChannelConfig::required` became `enabled`: a channel the arbiter consumes is a channel it depends on, and an enabled channel that is missing, stale or invalid sets `V(k)`. An invalid DAA ownship is an invalid input, never "no conflict". | `test_channel_gating.cpp`: `EnabledDaaChannelFailsClosed`, `DisabledChannelIsIgnored` |
| H-4 | Monitor aggregation moved into `MonitorTable`: expected monitors are declared by name (`inputs.monitor.expected_ids`); missing, stale, `inputs_complete=false`, malformed and table-overflow all set `V(k)`. | `test_monitor_table.cpp` (10 cases) |
| H-5 | A geofence sample without a global reference or with a failed projection invalidates the enabled channel; `geofence.enabled` and `inputs.geofence.enabled` must be set together or the node refuses to start. | `InvalidGeofenceSampleFailsClosed`; the consistency check is exercised by `sitl_pair.sh` |
| H-6 | `monitor_class` and `action` are validated against the message contract before use, so `action=3` can no longer become `Recovery(4)`; an out-of-contract publisher is an invalid input. | `OutOfRangeActionIsInvalid`, `OutOfRangeClassIsInvalid`, `ValidSampleClearsTheInvalidMark` |
| H-7 | Each intruder report keeps its own observation time and is added to DAIDALUS at that time; a full table evicts the oldest entry instead of dropping new intruders; the ownship gate invalidates `DaaStatus` when the local/global position stops arriving. | `test_traffic_table.cpp` (5 cases), `test_daa_equivalence.cpp: TrafficTimeChangesTheEvaluation` |

Beyond the table, the shipped configuration is no longer the thing that decides whether a protection
exists. `safety.profile` is `flight` by default in code; the flight profile refuses to start a
configuration with a disabled protection channel, an enabled monitor channel with no expected
monitors, or an enabled channel without a finite `max_age_s`. An operation that genuinely has no
DAA, monitors or geofence must say so in `safety.accepted_omissions`; the declaration is logged at
start, copied into the run configuration and published in `RtaState`.
`config/rta_params_flight.yaml` is the reference flight configuration;
`config/rta_params.yaml` is explicitly the SITL bench file (`safety.profile: sitl`).

## 3. Design issues

- **Return ignores the CF's intent** — `Inputs::cf_intent_unsafe` withholds T5 while the CF's current
  proposal would re-enter the unsafe set, and the gateway shadow-checks each proposed setpoint
  against the geofence predictor before forwarding it (`GeofenceSetpointGuard`). The decision group
  publishes the vehicle state to the gateway callback through a lock-free two-slot snapshot, so the
  check adds no lock and no allocation to either path. See ADR 0010.
- **Lateral uncertainty** — the predictor now also bounds `T_gf` by the distance to the *nearest*
  boundary: a sample within `k_sigma·eph` of the fence, or within `k_sigma·epv` of an altitude limit,
  is a violation whatever the heading (`test_predictor_uncertainty.cpp`). With `k_sigma = 0` the
  model reduces to the previous one, so the AC-8 analytic cases are unchanged.
- **Latch bypass** — the switch history survives T1. Re-entering the owned mode no longer clears
  `N_max`; entries still decay with the window `W` (`test_return_policy.cpp`).
- **Mode effect not confirmed** — a request now carries the `nav_state` it must produce.
  `ActuatorLogic` starts a confirmation window on the accepting acknowledgement and reports a failure
  if `vehicle_status.nav_state` does not show the effect within `actuator.confirm_timeout_s`
  (`test_actuator_confirmation.cpp`).
- **Actuation failure left the vehicle hovering** — an actuation failure now also fails the owned
  mode's arming check (`guara_actuation_failed`), so PX4's own fallback chain takes the vehicle
  instead of leaving it in a mode the arbiter can no longer steer.
- **Untested glue** — the monitor table, channel gating, profile validation, gateway envelope and
  actuator confirmation are pure classes in `guara_rta_core` with their own tests; `arbiter_node.cpp`
  keeps only the ROS wiring.
- **Hygiene** — the three Ogma-derived template sources carry SPDX and the Ogma/NASA notice.
  `scripts/publish_evidence.py` copies the run contract and metrics of a run, pair or batch into
  `docs/evidence/`, so the numbers quoted in a report can be checked without this machine.

## 4. Medium — evidence brought up to the criterion

| AC | What changed | Re-run result |
|---|---|---|
| AC-3 | The requirement was vacuous: `input_signal >= 0` is violated by any climb, and PX4 ground noise made every one of the 1728 verdicts a violation. REQ-ALT-01 now states a real 2.0 m ceiling (`input_signal >= (0.0 - 2.0)`), below the PX4 takeoff altitude, and the checker requires a `violated=false` verdict before the first violation. | 1836 verdicts, 1485 clear, 351 violated, first violation at index 555 — `PASS AC-3` |
| AC-7 | L6 is now taken from the ULog `VEHICLE_CMD_SET_NAV_STATE(AUTO_LOITER)` stamp, as the SPEC asks, and recorded in `metrics.json`. | `L6 = 0.012 s` — `PASS AC-7` |
| AC-9 | `tau_gf` back to the canonical 1.0 s with the O-1 justification written into the overlay (δ_lat p99 = 0.068 s, M7 batch); checker tolerance tightened from 0.05 m to projection round-off; the pair was produced by `sitl_pair.sh`, which now switches predictor and channel together. | on = 0.000 m outside, off = 9.993 m, **no mode switch at all**: the shadow check stopped the CF before the fence, so the T3→T5→T3 oscillation of the reviewed run does not occur — `PASS AC-9` |
| AC-14 | P-6 is asserted against the ULog: no `SET_NAV_STATE` from a `source_component ≥ COMPONENT_MODE_EXECUTOR_START` after the pilot leaves the owned mode. | 0 executor commands after the override — `PASS AC-14` |
| AC-15 | A detection time is computed on the PX4 clock (last logged `trajectory_setpoint` before the failsafe → AUTO_RTL) and recorded with its sampling period, instead of the logger spacing. | detection ≤ 1.268 s (±0.200 s sampling), consistent with the 1.2 s hypothesis — `PASS AC-15` |
| AC-16 / AC-16b | The two paths are now distinguished: FM-4 must *not* show `flagging unresponsive` (arming-check path), FM-5 must show it. `metrics.json` records which path the run took. | `PASS AC-16`, `PASS AC-16b` |
| AC-17 | Upper bound tightened to the SPEC's `A_i + 2 ticks = 0.30 s` (the extra 0.05 s of slack is gone). | re-run: T3 age 0.220 s — `PASS AC-17` |
| AC-10 | A small-UAS, low-altitude encounter was added (60 m AMSL, 12 m/s ownship, 15 m/s head-on intruder at 3 km) plus a case proving that an intruder's own observation time changes the evaluation. | wrapper `T_daa = 45.624 s` = standalone `45.624 s` |
| AC-1 | Clean from-scratch build of every Guará package, `nosa/` included, with the output recorded in `docs/milestones/M1.md`. | 6 workspace packages in 11 min 45 s + `guara_daidalus` in 36 s; 96 + 13 + 20 tests pass |

## 5. Acceptance criteria re-run after the fixes

All runs on this machine, in the pinned dev image, with `COM_MODE_ARM_CHK = 0` recorded in each run
contract. Unit tests: `./scripts/dev.sh colcon test` (workspace) and
`./scripts/dev.sh bash -lc 'colcon test --base-paths nosa --packages-select guara_daidalus'`.

| Criterion | Command | Result |
|---|---|---|
| AC-3 | `sitl_run.sh --scenario alt_ceiling_violation --seed 42` + `check_ac.py AC-3` | PASS |
| AC-7 | `sitl_run.sh --scenario monitor_trigger_hold --seed 42` + `check_ac.py AC-7` | PASS |
| AC-9 | `sitl_pair.sh --scenario gf_straight_concave --seed 42` + `check_ac.py AC-9` | PASS |
| AC-14 | `sitl_run.sh --scenario pilot_override --seed 42` + `check_ac.py AC-14` | PASS |
| AC-15 | `sitl_run.sh --scenario kill_arbiter_in_cf --seed 42` + `check_ac.py AC-15` | PASS |
| AC-15b | `sitl_run.sh --scenario kill_arbiter_in_hold --seed 42` + `check_ac.py AC-15b` | PASS |
| AC-15c | `sitl_run.sh --scenario restart_arbiter_armed --seed 42` + `check_ac.py AC-15c` | PASS |
| AC-16 | `sitl_run.sh --scenario hang_decision_thread --seed 42` + `check_ac.py AC-16` | PASS |
| AC-16b | `sitl_run.sh --scenario hang_ros_executor --seed 42` + `check_ac.py AC-16b` | PASS |
| AC-17 | `sitl_run.sh --scenario stale_local_position --seed 42` + `check_ac.py AC-17` | PASS: T3 at age 0.220 s, inside the tightened `A_i + 2 ticks = 0.30 s` |
| AC-18 | `sitl_batch.sh --runs 30 --seed-start 301` + `aggregate.py` + `check_ac.py AC-18` | PASS, `fail=0 of 30`, δ_lat p50 = 0.0448 s, p99 = 0.0610 s |
| AC-19 | `check_ac.py AC-19 results/batch_latency` | PASS, clock alignment p99 = 4.894 s (L1 stays out of δ_lat) |
| AC-22 | `check_ac.py AC-22 results/batch_latency` | PASS, O-1 holds: τ_gf 1.0 s > δ_lat p99 0.061 s; τ_daa 30 s > τ_rec p99 1.738 s + δ_lat p99 |
| AC-2 | `check_run_contract.py` on each run above | PASS |
| AC-1 | `rm -rf build install log && colcon build` (workspace, then `nosa`) | PASS, excerpt in `docs/milestones/M1.md` |
| unit | `colcon test` (workspace) | 96 tests, 0 failures |
| unit | `colcon test --base-paths nosa --packages-select guara_daidalus` | 13 tests, 0 failures |
| tools | `python3 -m pytest scripts/tests -q` | 20 passed |

## 6. Still open

These are recorded here rather than closed, and none of them is a leftover of a finding above.

- **SROS2 on `/guara/cf/*` and `fmu/in/*` (FM-12).** The gateway now bounds *what* an untrusted CF
  can ask for; nothing yet bounds *who* may ask. This is a precondition for any networked or
  LLM-driven CF (ADR 0010, consequence 3).
- **RQ6b corpus.** Jailbreaking the mission compiler has no implementation yet; the compiler itself
  is future work (`LLM-EMBODIMENT.md` §5.3).

  RQ5 has a first implementation: `test_gateway_fuzz.cpp` drives 200 000 ticks of a deterministic
  adversarial CF (NaN, infinities, ±1000 m/s, stamps up to 100 s in the future or the past, replays,
  silences) against a guard that refuses at random, and asserts four invariants — envelope, state,
  freshness/ordering, guard. Against the pre-review gateway the same test fails immediately
  (`speed 893.452 vs 5.0001`, `vz -215.176 vs -3.0001`); against the current one it forwards 52 855
  setpoints while rejecting 27 029 implausible stamps, 41 085 non-finite values and 13 483 guard
  refusals, with no invariant violated. It is not yet a *corpus* of realistic LLM misbehaviour.
- **Gateway envelope values are [HYPOTHESIS].** They must be filled in per airframe from the PX4
  limits and the ADR 0004 braking measurement before any flight.
- **Nominal-flight T3 on local-position age.** The reviewed AC-14 run showed one; the re-run does
  not. `inputs.local_position.max_age_s = 0.2` with a 50 Hz stream stays an availability risk to
  measure, not a defect observed at this commit.
- **AC-5 timing is host-sensitive.** `decision_core_timing` asserts a 1 ms bound on the worst tick.
  Run on its own it measures ~0.5 ms; in one parallel `colcon test` on this virtualised host it
  reported 1.033 ms. The bound is a property of the decision core, but the measurement needs a quiet
  machine to be meaningful, and the milestone evidence should say which it was.
- **PX4 clamping of external trajectory setpoints** is still ungrounded; the gateway clamps on the
  trusted side rather than relying on it.
