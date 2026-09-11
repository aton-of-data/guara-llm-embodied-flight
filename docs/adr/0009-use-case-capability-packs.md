# ADR 0009 — All civil use cases via capability packs, gated by risk class

- Status: Accepted (author decision, 2026-09-11); implementation M8+
- Related: docs/research/LLM-EMBODIMENT.md §3.6, §5, §10; ADR 0007, 0008; CLAUDE.md §Prohibitions

## Context

The author wants every possible use of LLM embodiment, not survey-only. CLAUDE.md fixes the scope to civil
flight safety with no target-selection or weapon functions. Use cases differ in physical risk and regulation
(e.g. spraying under MAPA Portaria 298/2021; BVLOS under RBAC 100 [REVIEW]).

## Decision

1. **Capability pack** = folder `capabilities/<name>/` declaring: intent schema extension, compiler rules,
   required sensors/payload, required monitors (FRETish requirement IDs), recovery overrides, regulatory
   preconditions, and readback keys for ADR 0008. The core stays generic.
2. **Risk classes** (engineering classes, not regulatory categories):

   | Class | Physical interaction | Examples | Extra gates |
   |---|---|---|---|
   | S — sense | none | survey, mapping, inspection, monitoring | base RTA (geofence, DAA, stale inputs) |
   | D — dispense | releases material | spraying, spreading, seeding, biological release | + payload/flow, wind/drift, buffer-zone, dose monitors; operator credentials recorded; disabled by default |
   | T — transport | carries/drops cargo | delivery, sample transport | + mass/CG, drop-zone monitors |
   | C — cooperate | near people or other robots | SAR support, multi-drone | + people-proximity policy, swarm deconfliction; phase 4 |

3. A pack is loadable only if all its required monitors exist and pass their ACs, and its regulatory preconditions
   are set in site configuration (e.g. operator registration IDs). Class D/T/C packs refuse to run otherwise.
4. **Excluded by design (never packs):** weapons or payloads intended to harm; target selection, tracking or
   identification of specific people for enforcement or harassment; covert surveillance of people; interference
   with other aircraft; defeating geofences, remote-ID or failsafes. SAR may detect people to help them, never to target.
5. Rollout: S packs first (M8–M11), D packs after T2 airframe P0 and dispense monitors (phase 3).

## Consequences

- (+) Every civil use case has a defined path; the author's broad scope is kept without weakening safety.
- (+) Monitors and regulation are explicit per pack and auditable (C4 evidence report).
- (−) Class D/T need monitors and hardware Guará does not yet have; they stay disabled until they exist.
- (−) Regulatory preconditions differ per country; site configuration must be localized [REVIEW].
