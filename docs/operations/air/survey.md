# Air operation — survey a field

| | |
|---|---|
| Intent verb | `survey` |
| Capability class | **S — sense** (ADR 0009); no physical interaction with the ground |
| Domain / host | Air · PX4 v1.17 SITL + ROS 2 Humble |
| Recovery function | PX4 internal modes Hold / RTL / Land (ADR 0001) |
| Status | **flown** in SITL as the complex function (AC-31); compiler ACs AC-23..AC-26 PASS |
| Evidence | `docs/evidence/20260912T023216Z_llm_survey_nominal_s42/`, `docs/evidence/20260912T134907Z_llm_survey_outside_s42_pair/` |

The reference operation of the air thread: fly a boustrophedon pattern over a named field at a
ground sample distance the operator asked for, capturing images for a later data product.

## 1. What the operator asks for

> "Survey the north field at two centimetres per pixel and give me the NDVI."
> "Levanta o talhão norte com dois centímetros por pixel e me dá o NDVI."

The model turns that into a Mission Intent and nothing else
(`mission/schema/mission_intent.schema.json`):

```json
{ "intent": "survey", "field_id": "north-field", "sensor": "multispectral",
  "gsd_cm": 2.0, "overlap": {"front": 0.75, "side": 0.65},
  "altitude_agl_m": null, "deliver": ["ndvi"],
  "utterance_hash": "sha256:…" }
```

No coordinate, no speed, no waypoint, no MAVLink: the schema has no field for them, and it is
closed (`additionalProperties: false`). `altitude_agl_m: null` means *the compiler decides*
from the sensor model and the requested GSD.

## 2. Words to motion

| Stage | Component | Trust position |
|---|---|---|
| 1 | Stop grammar (`mission/compiler/stop_grammar.py`) | Runs first; if it matches, this operation never starts |
| 2 | Model → intent | **Untrusted.** Validated against the closed schema, ≤ 64 KB, rejected with a machine-readable code |
| 3 | `mission/compiler/compile.py` | **Trusted, deterministic.** Site model + gateway limits in, plan out |
| 4 | `mission/compiler/verify.py` | Independent re-check of the finished plan, written not to reuse the compiler's own arithmetic |
| 5 | `mission/executor.py` + `scripts/sitl/ros_action.py fly-plan` | **Trusted executor.** Reads a compiled plan only; publishes `guara_msgs/CfSetpoint` |
| 6 | `GuaraCfGateway` | Freshness, envelope clamp, shadow geofence check of the *proposed* velocity |
| 7 | `DecisionCore` → PX4 | Switches to Hold / RTL / Land when the next seconds are unsafe |

## 3. What refuses it before flight

Each check is named in the plan document, and each has a unit test that makes it the only
failing check (AC-24):

| Check | Refuses when |
|---|---|
| `field_known` | `field_id` is not in the site model — the model may not invent a field |
| `gsd_bounds` | The requested GSD is outside what the sensor model supports |
| `deliverables_supported` | A requested product does not exist for the chosen sensor |
| `altitude_ceiling` / `altitude_floor` | Derived altitude exceeds the regulatory ceiling or is below the floor |
| `coverage_in_field` | A capture point falls outside the field polygon minus its buffers |
| `coverage_in_geofence` | Any waypoint leaves the keep-in fence — the same file PX4 loads, hashed (ADR 0004) |
| `vlos` | A waypoint is beyond the VLOS radius of the recorded pilot position |
| `envelope` | The plan's commanded speeds exceed the gateway clamp (ADR 0010 rule 2) |
| `energy` | Path length × the consumption model + reserve exceeds the usable battery **[HYPOTHESIS model]** |

Compiling the same intent against the same site model twice is byte-identical, and the plan
records the site hash and the compiler version (AC-25).

## 4. What watches it in flight

| Channel | Signal | Recovery |
|---|---|---|
| `geofence` | `T_gf` — predicted time to keep-in violation with the braking model (ADR 0004) | Hold |
| `monitors` | Copilot monitors generated from FRETish (`REQ-ALT-01` today) | Hold |
| `daa` | `T_daa` from the NOSA-isolated DAIDALUS node | Hold |
| `inputs_valid` | Stale, missing or implausible inputs; enabled channels fail closed | Hold |

Return to the complex function is asymmetric: only from Hold, only after hysteresis, dwell and
a switch budget, and only when the CF's own intent is clear again (ADR 0005, AC-12, AC-13).

## 5. Evidence

```
$ ./scripts/sitl_run.sh --scenario llm_survey_nominal --seed 42 --headless
$ ./scripts/dev.sh python3 scripts/check_ac.py AC-31 results/20260912T023216Z_llm_survey_nominal_s42
{"AC-31": {"depth_m": 0.0, "scenario": "llm_survey_nominal"}}
PASS AC-31
```

The adversarial member of the same pair — a compiled plan deliberately aimed outside the fence —
is the one that proves the boundary rather than the planner:

```
$ ./scripts/sitl_pair.sh --scenario llm_survey_outside --seed 42
max violation depth on=0.000 m  off=47.178 m
PASS AC-31
```

Narrative and the failed first attempt: [`docs/milestones/M9.md`](../../milestones/M9.md).

## 6. What this operation must not claim

- It is not certified, and shows no compliance with RBAC 100 or any other regime.
- SITL is not flight; no number above is a claim about a real aircraft.
- The RTA does not check *agronomy*. Surveying the wrong field at the right altitude is a
  correct flight and an undetected mission error (SPEC §7.12).
- The energy model is a hypothesis until calibrated on hardware; it bounds the `energy` check,
  not the aircraft.

## 7. Open items

- AC-27 (intent accuracy with `R ≥ 3` on a hosted instrument) is in progress.
- Transport authentication on `/guara/cf/*` is M9b (AC-32/AC-33); until then a model-driven CF
  runs only on a closed local DDS domain, and each run must say so.
- Capture triggering, image storage and the ODM products are M11, not this milestone.
