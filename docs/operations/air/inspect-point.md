# Air operation — inspect a point

| | |
|---|---|
| Intent verb | `inspect_point` |
| Capability class | **S — sense** (ADR 0009) |
| Domain / host | Air · PX4 v1.17 SITL + ROS 2 Humble |
| Recovery function | PX4 internal modes Hold / RTL / Land |
| Status | **implemented** — compiled and unit-tested; flown only through the same executor as `survey`, with no dedicated SITL scenario yet |
| Evidence | `scripts/tests/test_mission_compiler.py`, fixture plan `mission/plans/inspect_pivot2.json` |

Fly to a named point of interest, hold at a computed stand-off, and capture. The operation a
farmer actually asks for between surveys: *look at that pivot*.

## 1. What the operator asks for

> "Go look at pivot two."
> "Dá uma olhada no pivô dois."

```json
{ "intent": "inspect_point", "poi_id": "pivot-2", "sensor": "rgb",
  "gsd_cm": 1.0, "altitude_agl_m": null, "deliver": ["photos"],
  "utterance_hash": "sha256:…" }
```

`poi_id` must already exist in the site model. A model that invents a point of interest is
rejected by `poi_known` with a machine-readable reason, not corrected into something plausible.

## 2. Words to motion

Identical to [survey](survey.md) §2 — the same stop grammar, the same schema, the same
compiler, the same trusted executor, the same gateway and the same decision core. Only the
plan geometry differs: a transit leg, a stand-off station derived from the sensor model and the
requested GSD, and a return leg.

## 3. What refuses it before flight

| Check | Refuses when |
|---|---|
| `poi_known` | The point of interest is not in the site model |
| `gsd_bounds` | The requested GSD is outside the sensor model |
| `altitude_ceiling` / `altitude_floor` | Stand-off altitude is outside the regulatory band |
| `coverage_in_geofence` | The stand-off station or a transit waypoint leaves the keep-in fence |
| `vlos` | The point of interest is farther from the pilot than the VLOS radius |
| `envelope` | Transit speed exceeds the gateway clamp |
| `energy` | Transit + hold + return exceeds the usable battery with reserve **[HYPOTHESIS model]** |

`coverage_in_field` is skipped for this intent and the plan records the skip rather than
silently dropping the check.

## 4. What watches it in flight

The same four channels as [survey](survey.md) §4. One difference matters: an inspection holds
station near a structure, so the geofence predictor's braking model and the DAA channel are
exercised at low ground speed, where `τ_gf` has the most margin and a hovering intruder
encounter has the least.

## 5. Evidence

```
$ ./scripts/dev.sh python3 -m pytest scripts/tests/test_mission_compiler.py -q
121 passed
```

No dedicated SITL scenario exists yet. Until one does, this operation is *implemented*, not
*flown*, and the catalogue says so.

## 6. What this operation must not claim

- No obstacle avoidance. Guará has no perception channel; the stand-off comes from the site
  model, not from seeing the structure. Flying near a pivot, a tower or a building is a
  planning assumption, not a sensed clearance.
- No inspection of people. Class S covers structures and crops; ADR 0009 decision 4 excludes
  surveillance of specific people by design.
- SITL is not flight, and this operation has not flown even there.

## 7. Open items

- A `llm_inspect_point` SITL scenario and its own AC-31-style pair.
- A stand-off monitor (minimum distance to a declared structure) before any real-world use;
  today the only in-flight geometric channel is the geofence.
