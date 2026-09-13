---
name: guara-scope
description: Stage 1 of the Guará pipeline — Opus 5 turns a request into a falsifiable work packet with tasks, gates, grounding and acceptance, ready for a Cursor/Grok execution loop. Use when asked to scope, plan, spec, do the prework, or write the packet for a change; also before any work that touches the arbiter, the kernel, a flight operation or a measured result.
---

# Stage 1 — scope (Opus 5)

Produce `.claude/pipeline/<ID>/packet.md`. Write no implementation code in this stage.

## Method — scientific order, not task order

Run these seven steps in order. Do not start writing tasks before step 5.

1. **Question.** State what the work settles, as one question. If the request holds two
   questions, split into two packets.
2. **Hypothesis.** The expected answer, phrased so an observation can refute it.
   "The arbiter reaches Hold within X ms of the monitor trip" — not "latency improves".
3. **Falsifier.** The observation that kills it. No falsifier → the packet is a chore, mark
   `Question: engineering chore, no claim` and skip steps 4 and 11 of acceptance.
4. **Grounding.** Read the real source under `third_party/` and cite
   `repo@commit:file:line`. Never infer an API. A row that is unknown is written `UNKNOWN`
   and becomes a task. If the change touches an API, the `GROUNDING.md` row is task T1.
5. **Procedure.** The commands that produce the observation, verbatim, with seed and
   commit recorded. Reproducible and headless for SITL.
6. **Tasks.** Decompose so each task has one gate and one observable. Order by dependency.
   Test-first pairs are two tasks: write the failing test, then implement.
7. **Acceptance.** One AC row per claim, each with the command that verifies it. Reuse the
   AC id from `docs/milestones/STATUS.md` when one exists; otherwise mark `AC: new`.

## Pre-flight reads

Read before writing the packet, in this order, stopping when the question is answered:

| Read | When |
|---|---|
| `CLAUDE.md`, `.claude/skills/guara-pipeline/references/quality-bar.md` | always |
| `GROUNDING.md` | any behavioural claim about an upstream API |
| `docs/SPEC.md`, the relevant `docs/adr/*.md` | any architectural choice |
| `docs/operations/README.md` + the operation's document | any flight operation |
| `docs/milestones/STATUS.md` | any AC, any milestone claim |
| `docs/PLAN-M8-M16.md`, `docs/PLAN-M17-M28.md` | thread placement (core/A/B/C/S/K) |

## Hard stops

Stop and ask, do not assume:

- the request implies a new flight operation with no document in `docs/operations/`
- the request would produce a number without a run, or cite one not in `results/`
- the request is space/F´ work while the PX4 latency and batch results are outstanding (Rule O)
- the request touches target selection, weapons, or defeating a geofence, failsafe or Remote ID

## Output

Fill `templates/packet.md` exactly. Then print, and nothing else:

```
packet: .claude/pipeline/<ID>/packet.md
tasks:  T1..Tn
gates:  <n> commands
open:   <UNKNOWN rows, or none>
```

Hand off with `guara-execute`.
