# Air operation — status

| | |
|---|---|
| Intent verb | `status` |
| Capability class | Read-only; commands no motion |
| Domain / host | Air · PX4 v1.17 + ROS 2 Humble |
| Status | **specified** — the verb is in the closed schema and is explicitly *not compilable*; the answer path is M10/M11 |

Ask the system what it is doing. The only operation whose output is words rather than motion,
and therefore the one where a language model is most useful and least dangerous.

## 1. What the operator asks for

> "What are you doing?" · "How much battery is left?" · "Why did you stop?"
> "O que você está fazendo?" · "Quanta bateria resta?" · "Por que parou?"

## 2. Why it compiles to nothing

`status` is in `NOT_COMPILABLE` alongside the stop class: the compiler refuses to produce a
plan for it. There is no waypoint, no speed and no actuator anywhere in this path, so the
narrowest possible failure mode is a wrong sentence.

## 3. The rule that makes the answer trustworthy

Every quantitative statement in an answer must be traceable to a computed value — a telemetry
field, an RTA event, an index computed from captures — never to the model's impression
(`LLM-EMBODIMENT.md` L-P1). AC-37 makes an unsourced claim a test failure, not a style issue.

Two consequences:

- "Why did you stop?" is answered from the RTA event that caused the switch, naming the channel
  (`geofence`, `daa`, `monitors`, `inputs_valid`) — the same content AC-35 requires the voice
  announcement to carry, in the configured language pack (ADR 0008).
- "How much battery?" is answered from telemetry, with the model allowed to phrase it and not
  to estimate it.

## 4. What this operation must not claim

- A fluent answer is not a correct one. Status is the operation where a plausible-sounding
  fabrication is most likely and least physically constrained, which is why traceability is an
  acceptance criterion rather than a guideline.
- Nothing here makes the underlying telemetry right. A stale value narrated confidently is
  still stale; freshness is the Input Manager's job, not the narrator's.

## 5. Open items

- M10: the talk-back path, the readback-and-confirm loop and AC-35 announcements.
- M11: AC-37 report traceability, once there are computed data products to answer from.
