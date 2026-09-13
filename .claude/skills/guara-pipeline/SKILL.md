---
name: guara-pipeline
description: Local three-stage work pipeline for Guará — Opus 5 scopes, Cursor/Grok executes in a loop, Claude reviews. Use when starting any non-trivial change, when asked to "scope this", "hand this to Cursor", "run the loop", "review the loop output", or when a packet under .claude/pipeline/ is mentioned. Holds the shared quality bar and the handoff schema.
---

# Guará pipeline

Local process. Not an ADR, not a contribution rule, nothing here is merged.

## Stages

| # | Stage | Model | Skill | Artifact |
|---|---|---|---|---|
| 1 | Scope | Opus 5 (this session) | `guara-scope` | `.claude/pipeline/<ID>/packet.md` |
| 2 | Execute | Cursor / Grok, on a `/loop 5m` timer | `guara-execute` | `.claude/pipeline/<ID>/log.md` |
| 3 | Review | Opus 5, fresh session | `guara-review` | `.claude/pipeline/<ID>/review.md` |

`<ID>` = `YYYYMMDD-<kebab-slug>`. One packet = one falsifiable claim + its gates.
Never merge stages: the scoper does not write implementation code, the executor does
not redefine acceptance, the reviewer does not fix while reviewing.

Loop back on `CHANGES` verdict: review → packet §Deltas → execute again. Max 2 returns,
then re-scope from stage 1.

## Where each stage's rules live

| Surface | File | Loaded by |
|---|---|---|
| Claude Code | `.claude/skills/guara-*/SKILL.md` | the Skill tool |
| Cursor | `.cursor/rules/guara-repo.mdc` (always) | every Cursor request |
| Cursor | `.cursor/rules/guara-executor.mdc` (agent-requested) | a packet loop |
| Cursor | `.cursor/rules/guara-sources.mdc` (glob-scoped) | editing a source file |

`references/quality-bar.md` is the single source of truth for the invariants;
`guara-repo.mdc` mirrors it for Cursor. They are edited together, never separately.

## Read before acting

- `references/quality-bar.md` — the ten invariants every stage restates verbatim.
- `references/packet-schema.md` — the handoff format, field by field.

## Routing

- "scope / plan / prework / write the packet" → `guara-scope`
- "hand off / cursor prompt / run the loop" → `guara-execute`
- "review / verdict / did the loop hold" → `guara-review`

## Language rules for every artifact

Imperative. Tables over prose. No preamble, no restatement, no closing summary.
Commands verbatim and copy-pasteable. Every claim carries either `repo@commit:file:line`
or a command + output excerpt. Unknown is written `UNKNOWN`, never guessed.
