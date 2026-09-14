# Roadmap

What is done, what is in progress and what is planned, with the gate on each. Split out of
the README, which links here from §11. The acceptance-criteria inventory is
[`milestones/STATUS.md`](milestones/STATUS.md).

---

Ordered by the rule that protects the core: the PX4 results come first, thread A runs beside
them because it touches no arbiter code, and threads B and C start only after the latency and
batch milestones are complete ([`docs/PLAN-M8-M16.md`](PLAN-M8-M16.md) §1).

## Done

| Milestone | Content | Evidence |
|---|---|---|
| M1–M2 | Headless SITL in a container, API grounding, first Ogma monitor over `/fmu/out/*` | [M1](milestones/M1.md), [M2](milestones/M2.md) |
| M3–M5 | Arbiter, geofence predictor, DAIDALUS node | [M3](milestones/M3.md)–[M5](milestones/M5.md) |
| M6–M7, P4 | Scenario generator, 30-run batch, latency budget (AC-18/19/22 re-run 2026-09-11) | [M7](milestones/M7.md), [`docs/evidence/batch_latency/`](evidence/batch_latency) |
| M8 | Mission Intent schema and deterministic compiler, no model involved | [M8](milestones/M8.md), AC-23..AC-26 |

## In progress

| Milestone | Thread | Content | State |
|---|---|---|---|
| M9 | A | LLM instruments against the labelled corpus; a compiled plan flown as the CF | AC-29, AC-30, AC-31 PASS; AC-27/AC-28 open ([M9](milestones/M9.md)) |
| M13c | C | Attitude keep-out predictor and the closed space-intent vocabulary | AC-47 PASS; AC-48 needs a simulator ([M13c](milestones/M13c.md)) |
| M17 | S | Hermetic setup: single pin source, hash-pinned lock, `guara doctor`, offline mode | AC-51, AC-52, AC-55, AC-56 in progress; AC-53, AC-54 planned |
| M18 | K | `guara-core`: the host-free kernel and its C ABI, ABI symbol gate, parameter digest | AC-57..AC-62 in progress, none PASS |
| M19 | K | `guara-ctk`: published vectors, the Python reference port, the SIL port through the C ABI | AC-63..AC-66 in progress; ROS 2 and F´ ports absent |
| M26–M27 | C | The [ADR 0015](adr/0015-space-untrusted-function-contract.md) gateway predicate and the space command-origin declaration, both host-free | AC-102, AC-103 in progress; no F´ component and no space run exists |
| P5–P7 | core | Adversarial CF (RQ5), preprint and NFM submission, `px4_msgs` variable DB upstream to `nasa/ogma` (C2) | not started; displaced by M17–M19 |

## Planned

| Milestone | Thread | Content | Gate |
|---|---|---|---|
| M9b | A | SROS2 on the CF and bridge topics | closes FM-12; until then, closed local DDS domain only |
| M10–M11 | A | Voice pipeline, imaging, ODM products, talk-back | AC-34..AC-37 |
| M12 | A | Field-trial readiness: VLOS operations manual, risk assessment, LGPD policy | human regulatory review |
| M13 | B | Shared `guara_core` extraction, F´ deployment, `Svc::Health` registration | AC-39 must pass with **no edits to the PX4 test files** |
| M14 | B | The safe mode F´ does not have — the project's most safety-critical new code | AC-42..AC-44, risk RS-1 |
| M15 | B | Ogma F´ backend upstream: verdict output port, configurable module name | AC-45, AC-46 |
| M16 | C | Orbital batch, intent → validated sequence, RQ6b against the space schema | AC-49, AC-50 |

## Proposed — delivery and real hardware

[`docs/PLAN-M17-M28.md`](PLAN-M17-M28.md) continues past M16: the gap register, and the
milestones that turn the repository into installable artifacts and take the architecture off
the simulator. Its packaging decision is [ADR 0014](adr/0014-delivery-model.md) — a versioned
safety kernel, a conformance kit, two host packages and a companion image, rather than a
single SDK.

M17, M18 and M19 have started and are listed under *In progress* above; what follows is the part
of the plan with no code.

| Milestone | Track | Content | Gate |
|---|---|---|---|
| M20 | K | Published artifacts: ROS 2 packages, F´ library, wheel, companion image, SBOM, Jazzy | AC-67..AC-71 |
| M21–M23 | H | HITL, companion bring-up and on-target timing, flight instrumentation | AC-72..AC-83 |
| M24–M25 | H | Operational safety dossier, then the bounded-LLM flight campaign | AC-84..AC-92 |
| M26–M28 | Z | F´ on an OBC-class target, the space operational interface, the orbital campaign | AC-93..AC-101 |

Ten further criteria, AC-102..AC-111, were added on 2026-09-13 from
[`docs/reviews/2026-09-13-roadmap-docs-site-review.md`](reviews/2026-09-13-roadmap-docs-site-review.md)
and are specified in [`docs/PLAN-M17-M28.md`](PLAN-M17-M28.md) §9. Two of them, AC-102 and AC-103,
moved into the in-progress table above on 2026-09-14. They belong to milestones that
already exist — M2, M9b, M14, M16, M19, M26, M27 — and none of them needs hardware, a host, a
simulator or a network. They are the space gate of [ADR 0015](adr/0015-space-untrusted-function-contract.md),
its published vectors, the safe-mode entry logic and its keep-out sweep, a space adversarial
corpus, model-side runtime discipline, corpus coverage, monitor non-vacuity, and the core semantics
the SPEC does not state.

Full acceptance-criteria inventory, executed and planned:
[`docs/milestones/STATUS.md`](milestones/STATUS.md).

Blocking risks. The four families — `R-*`, `RP-*`, `RS-*`, `RH-*` — are indexed in
[`docs/SPEC.md` §9](SPEC.md), which names the document defining each: CopilotVerifier
toolchain availability (R-11, blocks RQ4), DO-365B thresholds unsuited to small UAS (R-5), Hold
as a DAA recovery against converging traffic (R-6), traffic injection in SITL never exercised
(R-7), the unavailable ASTM F3269 text (R-8), and the space thread's own RS-1…RS-6 — of which
RS-1, the safe mode with no heritage, is the one a reviewer should attack first — and AC-109 now
measures one half of it without waiting for a host.
