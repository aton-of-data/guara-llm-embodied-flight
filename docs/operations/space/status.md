# Space operation — status

| | |
|---|---|
| Intent verb | `status` |
| Domain / host | Space · F´ v4.3.0 |
| Status | **specified**; the verb is in the closed schema and is explicitly *not compilable* |

Ask what the spacecraft is doing and why. Read-only: no sequence, no actuator, no attitude
change anywhere in this path.

## 1. Why it is more useful here than in the air

In the air the operator can look up. In orbit everything anyone knows arrives as telemetry
through a ground-station pass, and the gap between *what the vehicle did* and *what the
operator believes* is where mission loss accumulates. A narrated status answer is a cheap,
physically harmless place to put a language model — provided it narrates computed values and
never estimates them.

## 2. The rule that makes the answer trustworthy

Same as the air thread: every quantitative statement traces to a computed value — a telemetry
channel, an arbiter event, a predictor output — never to the model's impression (AC-37's
discipline applied to the space profile). "Why are we in safe mode?" is answered from the
channel that caused the entry (`attitude_keepout`, `power_margin`, `momentum`, `inputs_valid`,
`requirements`), not from a plausible story about it.

## 3. What this operation must not claim

- A fluent answer is not a correct one, and in orbit it is much harder to check.
- Nothing in this repository yet produces spacecraft telemetry to answer from.

## 4. Open items

- Telemetry channel selection for a reference F´ deployment — the same data file that becomes
  the upstream Ogma variable-DB contribution for F´ (GROUNDING D.7, AC-45/AC-46).
