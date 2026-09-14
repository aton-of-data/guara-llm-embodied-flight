# Space operation — hold a pointing attitude

| | |
|---|---|
| Intent verb | `point_hold` |
| Domain / host | Space · F´ v4.3.0 (specified) |
| Recovery function | Safe mode, latched (ADR 0012 decision 3) |
| Status | **implemented** (schema) · **specified** (everything that moves) |
| Evidence | `scripts/tests/test_space_intent.py`, `scripts/tests/test_space_gateway.py` |

Keep a named aperture on a named target for a requested duration: a downlink pass, a science
observation, a thermal soak. Where `slew` is a transient, `point_hold` is the long exposure
during which the constraints that matter are the slow ones.

## 1. What the operator asks for

> "Hold the instrument on nadir for twenty minutes."

```json
{ "intent": "point_hold", "boresight_id": "instrument-a", "target_id": "nadir",
  "hold_s": 1200, "utterance_hash": "sha256:…" }
```

`hold_s` is a **request**, bounded by the schema (0 < `hold_s` ≤ 86400) and re-bounded by the
compiler against the vehicle model; `null` means the compiler uses the site default.

## 2. The channels a hold actually exercises

| Channel | Why a hold is its worst case | State |
|---|---|---|
| `attitude_keepout` | A fixed inertial attitude sweeps relative to the sun as the orbit advances: a hold that is legal at entry can violate the cone later without any commanded rate | implemented (predictor), specified (in-loop) |
| `power_margin` | The load set runs for the whole hold, through eclipse. Predicted state of charge at the end of the eclipse against `soc_min` | specified, **[PARAMETER TBD]** |
| `momentum` | Holding an inertially fixed attitude against gravity-gradient and drag torques accumulates reaction-wheel momentum toward saturation | specified, **[PARAMETER TBD]** |
| `inputs_valid` | Eclipse dropouts, sensor blinding, loss of attitude knowledge — harsher in degree than the air case, identical in kind | ports from `guara_rta` |

Two of those three new channels depend on models (power, momentum) that are **[HYPOTHESIS]**
until calibrated against Basilisk, and that bounds every result they could produce (RS-4).

## 3. Why the return policy is different here

In the air, `RF(HOLD) → CF` is allowed after hysteresis and dwell because Hold is cheap and a
pilot is watching (ADR 0005). In orbit nobody is watching inside the light-time delay, so the
space profile disables `T5`: safe mode **latches**, and only a ground command releases it
(ADR 0012 decision 3, AC-43). This is a *configuration* of the same decision core that already
supports latching (P-4, AC-13), not new logic — which is exactly why the two hosts are a
stronger claim than one host twice.

## 4. What refuses a proposal before it moves anything

`GuaraSpaceGateway` (ADR 0015) stands between the command source and `Svc::CmdDispatcher`,
which authorises nothing (`GROUNDING.md` D.10). Its predicate is implemented host-free in
[`space/gateway.py`](../../../space/gateway.py) and every rule is the sole refuser of at least
one case in `scripts/tests/test_space_gateway.py` (AC-102):

| Rule | What it refuses (hold) |
|---|---|
| 1 · declared origin | Nothing at the gate. The run declares its SDLS security association and decryptor; a run claiming an authenticated origin the declaration does not support fails `check_run_contract.py --profile space` (AC-103, `GROUNDING.md` D.9) |
| 2 · admissible set | A verb the arbiter state does not permit, or an identifier `space/site/demo_sat.yaml` does not declare. The admissible set is data; narrowing it is a configuration change |
| 3 · trusted time | A stamp ahead of the reception instant past `future_stamp_tolerance_s`, or already stale on arrival. Freshness is never read off the proposal |
| 4 · envelope | A non-finite magnitude, outright. Finite magnitudes are clamped to the per-vehicle envelope and the clamp is reported |
| 5 · shadow check | A hold whose commanded motion closes a keep-out cone inside `tau_ko + h_ko`. A hold commanding no rate is admitted by this rule at entry, because `point_hold` is not in `gateway.motion_required` — the sweep of a fixed inertial attitude against the sun is the channel's job *during* the hold, not the gate's at admission. `slew` is in that list and is refused when it declares no motion |
| 6 · observability | Nothing. It requires that each refusal above carries one event naming its rule and the verb, and one counter increment |

Rule 7 is structural: the gate has no path that releases the safe-mode latch, and none of the
tests can construct one (ADR 0012 decision 3).

**The gate is a predicate, not a component.** No FPP exists, no F´ deployment has ever run it,
and its conformance vectors are AC-107. What is tested is the decision, on a host, in Python.

## 5. What this operation must not claim

- Nothing has held anything. The schema is closed and tested; the attitude control, the power
  model and the momentum model do not exist in this repository.
- A predicted violation is not a collision, a brown-out or a saturation — it is the output of a
  model whose fidelity is stated wherever a number from it is.
- No claim of compliance with NPR 7150.2 or ECSS; neither has been read for this project
  (`SPACE-AUTONOMY.md` §7).

## 6. Open items

- Energy and momentum models with declared assumptions, then their FRETish requirements.
- AC-48-style pairs for the slow channels, which need a simulator with orbit and eclipse.
