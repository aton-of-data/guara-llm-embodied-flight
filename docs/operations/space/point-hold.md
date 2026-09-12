# Space operation — hold a pointing attitude

| | |
|---|---|
| Intent verb | `point_hold` |
| Domain / host | Space · F´ v4.3.0 (specified) |
| Recovery function | Safe mode, latched (ADR 0012 decision 3) |
| Status | **implemented** (schema) · **specified** (everything that moves) |
| Evidence | `scripts/tests/test_space_intent.py` |

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

## 4. What this operation must not claim

- Nothing has held anything. The schema is closed and tested; the attitude control, the power
  model and the momentum model do not exist in this repository.
- A predicted violation is not a collision, a brown-out or a saturation — it is the output of a
  model whose fidelity is stated wherever a number from it is.
- No claim of compliance with NPR 7150.2 or ECSS; neither has been read for this project
  (`SPACE-AUTONOMY.md` §7).

## 5. Open items

- Energy and momentum models with declared assumptions, then their FRETish requirements.
- AC-48-style pairs for the slow channels, which need a simulator with orbit and eclipse.
