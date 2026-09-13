---
name: guara-execute
description: Stage 2 of the Guará pipeline — drive a scoped packet through an execution loop in Cursor/Grok, one task at a time against its gate, and record the log. Use when asked to hand a packet to Cursor, generate the executor prompt, run the loop, or when reporting what the loop produced.
---

# Stage 2 — execute (Cursor / Grok)

Input: `.claude/pipeline/<ID>/packet.md`. Output: `.claude/pipeline/<ID>/log.md`.

The executor is a fast, cheap, literal worker. It implements tasks; it does not decide.

## Cursor side

The contract lives in the repository as Cursor rules, so the loop is bound even when the
prompt is short:

| File | Attachment | Carries |
|---|---|---|
| `.cursor/rules/guara-repo.mdc` | always | the ten invariants, the gates, the stop rule |
| `.cursor/rules/guara-executor.mdc` | agent-requested (description) | the per-task loop, stop conditions, log discipline |
| `.cursor/rules/guara-sources.mdc` | glob-scoped to source files | SPDX, doc-comments-only, per-tick path, test-first |

`.claude/skills/guara-pipeline/references/quality-bar.md` is the source of truth; `guara-repo.mdc` is its Cursor mirror.
Change one, change the other in the same edit.

## Handoff

1. Verify the packet: every task has Files, Gate, Done-when; no placeholder left in Gates;
   no `UNKNOWN` grounding row a task depends on. A failing check returns to `guara-scope`.
2. Render `templates/cursor-prompt.md` with the packet inlined and give it to Cursor. The
   prompt names the two rule files; it does not restate them.
3. Set the packet `State: RUNNING`.

## The loop, per task

```
read T<k> → implement only Files listed → run Gate → read output
  green  → append log row, State DONE, next task
  red    → fix, rerun; attempt 2, attempt 3
  3 reds → STOP. log the last command and output verbatim. State BLOCKED. Next task only if it does not Depend on T<k>.
```

## Executor rules — enforced by `guara-executor.mdc`, restated here for review

- Touch only the files the task lists. Anything else is a finding for the log, not an edit.
- Never weaken a test, threshold or acceptance criterion to pass a gate.
- Never write a number you did not produce with a command in this loop.
- Never state an upstream API from memory; read it under `third_party/` and cite
  `repo@commit:file:line`.
- `SPDX-License-Identifier: Apache-2.0` on every new source file. Nothing NOSA outside `nosa/`.
- English only. No comment explaining *why* a change was made — doc comments only.
- Commit per task: `type(scope): imperative summary`. No `Co-authored-by`, no mention of an
  assistant or AI anywhere.
- A gate reporting zero tests is red, not green.
- Out of scope, always: target selection, weapons, defeating a geofence, failsafe or Remote ID.

## Log discipline

One row per attempt, not per task. Paste the output excerpt that decides the row — the
assertion line, the summary line, the error — never a whole build log, never a paraphrase.

## Close

When every task is `DONE` or `BLOCKED`, print, and nothing else:

```
packet: <ID>
done:    T<..>
blocked: T<..> (<gate>)
files:   <n> changed
next:    guara-review
```
