# Space operation — slew a boresight to a target

| | |
|---|---|
| Intent verb | `slew` |
| Domain / host | Space · F´ v4.3.0 (specified); the analytic predictor runs host-free today |
| Recovery function | **Safe mode — does not exist in F´ and must be written** (ADR 0012 decision 2, risk RS-1) |
| Status | **implemented** (predictor + closed schema, AC-47 PASS) · **specified** (host, dynamics, safe mode) |
| Evidence | `docs/milestones/M13c.md`; `scripts/tests/test_keepout_analytic.py`, `scripts/tests/test_space_intent.py`, `scripts/tests/test_space_gateway.py` |

Rotate the spacecraft so a named aperture points at a named target. The operation that carries
the whole space thread, because it is the one that can destroy an instrument in seconds without
anybody on the ground being able to intervene inside the light-time delay.

## 1. What the operator asks for

> "Point the instrument at the ground station for the next pass."

```json
{ "intent": "slew", "boresight_id": "instrument-a",
  "target_id": "ground-station-1", "utterance_hash": "sha256:…" }
```

The schema (`space/schema/space_intent.schema.json`) contains **no quaternion, no F´ command
name, no Fpy directive and no actuator**. `boresight_id` and `target_id` must exist in the
vehicle model (`space/site/demo_sat.yaml`); a model that invents either is rejected.

## 2. Words to motion

| Stage | Component | Trust position | State |
|---|---|---|---|
| 1 | Stop grammar (`abort`, `safe_mode`) | Never reaches a model | specified |
| 2 | Model → Space Intent | **Untrusted**, closed schema, ≤ 64 KB (`space/intent.py`) | implemented |
| 3 | Intent → **validated** sequence | Trusted deterministic compiler, targeting `Svc::FpySequencer`, kept replaceable (risk RS-2) | specified (M16) |
| 4 | `Svc::FpySequencer` | Loads and validates before running (GROUNDING D.3) | upstream, pre-release |
| 5 | Arbiter gate | `GuaraSpaceGateway` (ADR 0015), the analogue of `GuaraCfGateway`: §4 | predicate implemented (`space/gateway.py`, AC-102); the F´ component specified (M26) |
| 6 | `DecisionCore` on a rate group | The same core as the air thread — AC-39/AC-40 require identical decisions | specified (M13) |
| 7 | Safe mode | The recovery function, latched | specified (M14) |

## 3. The channel that makes this operation safe

`attitude_keepout` (ADR 0012 channel table), implemented in `space/keepout.py`:

> at the current attitude and body rate, when does a protected boresight enter the keep-out cone
> around a bright body?

The air geofence's braking model does not transfer — an orbiting body cannot stop — so the
predictor answers a purely geometric question in closed form. The component of ω along
`boresight × forbidden` is the closing rate; the other components do not change the angle.
Fail-closed: non-finite input, a degenerate vector or an already-violated cone reports `T = 0`;
receding, still, or beyond the horizon reports `+∞` — the same convention as the geofence
predictor.

The other channels of the space profile (`power_margin`, `momentum`, `inputs_valid`,
`requirements`) are specified in ADR 0012; only `inputs_valid` ports directly from the air
thread. **There is no DAA channel.**

## 4. What refuses a proposal before it moves anything

`GuaraSpaceGateway` (ADR 0015) stands between the command source and `Svc::CmdDispatcher`,
which authorises nothing (`GROUNDING.md` D.10). Its predicate is implemented host-free in
[`space/gateway.py`](../../../space/gateway.py) and every rule is the sole refuser of at least
one case in `scripts/tests/test_space_gateway.py` (AC-102):

| Rule | What it refuses (slew) |
|---|---|
| 1 · declared origin | Nothing at the gate. The run declares its SDLS security association and decryptor; a run claiming an authenticated origin the declaration does not support fails `check_run_contract.py --profile space` (AC-103, `GROUNDING.md` D.9) |
| 2 · admissible set | A verb the arbiter state does not permit, or an identifier `space/site/demo_sat.yaml` does not declare. The admissible set is data; narrowing it is a configuration change |
| 3 · trusted time | A stamp ahead of the reception instant past `future_stamp_tolerance_s`, or already stale on arrival. Freshness is never read off the proposal |
| 4 · envelope | A non-finite magnitude, outright. Finite magnitudes are clamped to the per-vehicle envelope and the clamp is reported |
| 5 · shadow check | A slew whose predicted time to a keep-out violation is not above `tau_ko + h_ko`, swept over every declared forbidden body. Refused **whole**: unlike a velocity, a half-executed slew has no safe truncation, so this rule deliberately differs from ADR 0010 rule 3. A slew that declares *no* motion, no boresight or no valid attitude is refused too — a proposer does not escape the rule by leaving a field out (`gateway.motion_required`) |
| 6 · observability | Nothing. It requires that each refusal above carries one event naming its rule and the verb, and one counter increment |

Rule 7 is structural: the gate has no path that releases the safe-mode latch, and none of the
tests can construct one (ADR 0012 decision 3).

**The gate is a predicate, not a component.** No FPP exists, no F´ deployment has ever run it,
and its conformance vectors are AC-107. What is tested is the decision, on a host, in Python.

## 5. Evidence

```
$ ./scripts/dev.sh python3 -m pytest scripts/tests/test_keepout_analytic.py -q
11 passed
$ ./scripts/dev.sh python3 scripts/check_ac.py AC-47
PASS AC-47
$ ./scripts/dev.sh python3 -m pytest scripts/tests/test_space_gateway.py -q
36 passed
```

Analytic cases only — approaching, receding, tangent, zero rate, already inside, non-finite —
to ±0.05 s, the AC-8 pattern. AC-48 (orbital run, channel on versus off) has not been executed:
there is no simulator in the loop yet.

The gateway suite is unit tests on a host, not a run: it shows the rules are independent, not
that any spacecraft obeyed them. AC-102 is `in progress`, not PASS, for that reason.

## 6. What this operation must not claim

- **No spacecraft, no host, no dynamics.** Nothing in the space thread has run inside F´ or
  against an orbital simulator. The predictor is geometry with tests.
- **The recovery function does not exist.** Safe mode is the most safety-critical code the
  project has not written (RS-1), and every claim about `slew` inherits that gap.
- **No detect-and-avoid, no conjunction assessment** (ADR 0012 decision 1, RS-5).
- The planar constant-rate closed form is exact for the analytic window and an approximation
  for a real slew profile; a Basilisk-calibrated claim is bounded by the simulator's fidelity
  (RS-4).
- Every angle in `space/site/demo_sat.yaml` is **[PARAMETER TBD]**, not a measurement.

## 7. Open items

- M13c: Basilisk through the published ROS 2 bridge, driving the *unmodified* `guara_rta` node
  — the cheapest first experiment, before any F´ code exists (ADR 0012 decision 5).
- M13: shared-core extraction (AC-39), the F´ deployment and `Svc::Health` registration.
- M16: intent → validated sequence compiler, and the RQ6b corpus re-run against this schema.
