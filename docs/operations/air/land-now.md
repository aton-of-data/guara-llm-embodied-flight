# Air operation — land now

| | |
|---|---|
| Intent verb | `land_now` (stop class) |
| Capability class | Safety operation — available in every capability pack |
| Domain / host | Air · PX4 v1.17 + ROS 2 Humble |
| Target platform mode | **Land** |
| Status | Grammar **implemented**, model-independence measured (AC-29 PASS); mode mapping and button are M10 |
| Evidence | `docs/evidence/20260912T114925Z_cursor-stop-r3_cursor-agent/` |

Put the aircraft on the ground where it is. Ranked below `abort` and above `return_home` when
several stop phrases match the same utterance.

## 1. What the operator asks for

> "Land now." · "Land immediately." · "Emergency landing." · "Put it down here."
> "Pousa agora." · "Pousa já." · "Pousar de emergência."

The patterns are phrase-level on purpose: "we can land on fumes" is not a landing command, and
the grammar does not fire on it.

## 2. Words to motion

The stop path of [abort](abort.md) §2, with `land_now` as the resolved verb: grammar first, no
model request, straight to the platform mode. Rank order `abort` > `land_now` > `return_home`
resolves ambiguous utterances toward the more authoritative action.

## 3. Why it is a separate operation from abort

| | `abort` → Hold | `land_now` → Land |
|---|---|---|
| Vehicle ends | Airborne, stationary, recoverable by the pilot | On the ground, mission over |
| Reversible by the operator | Yes, by commanding a new mission | No |
| Right answer when | The mission is wrong, the situation is unclear, or the operator needs time | The aircraft must not stay in the air — payload, weather, injury risk below the flight path |
| Interaction with the RTA | Hold is also the RTA's own recovery target, so the two paths converge | Land is an operator decision; the RTA does not command Land on a geofence or DAA violation in v1 |

Documenting them separately is deliberate: an operator who says "land" means the ground, and a
system that quietly maps both phrases to Hold would be lying in the most dangerous direction.

## 4. Evidence

The AC-29 run covers the whole stop corpus, `land_now` included: 24/24 resolved by the grammar,
zero model requests (see [abort](abort.md) §4 for the executed command and output).

## 5. What this operation must not claim

- No landing-site assessment. PX4 Land descends where the aircraft is; nothing in Guará looks at
  what is underneath it. "Land now" is a command to stop flying, not a claim that the ground
  below is safe.
- Stop-path latency is unmeasured until AC-34 (M10).
- The mapping keyword → PX4 Land is specified, not yet an implemented runtime component.

## 6. Open items

- M10 voice pipeline, physical button, AC-34 latency.
- A landing-suitability monitor is not planned; if one is ever added it becomes its own channel
  with its own ADR, not a silent change to this operation.
