# Packet schema

One file, `.claude/pipeline/<ID>/packet.md`. The executor reads nothing else from the
scoper. If a field is empty the packet is not ready to hand off.

| Field | Content | Rule |
|---|---|---|
| `ID` | `YYYYMMDD-<kebab-slug>` | matches the directory name |
| `Question` | the one thing this packet settles, as a question | one sentence, answerable yes/no or by a number |
| `Hypothesis` | the expected answer, stated so it can be false | names the observable and the direction |
| `Falsifier` | the observation that kills the hypothesis | concrete, measurable |
| `Grounding` | `repo@commit:file:line` rows the work depends on | `UNKNOWN` is allowed; guessing is not |
| `Non-goals` | what this packet must not touch | at least one row |
| `Read-set` | every file the executor may open, and nothing else | the loop's token budget: a path not listed is a finding for the log, not a read |
| `Tasks` | ordered T1..Tn | each with Files, Gate, Done-when |
| `Gates` | the exact commands, verbatim | copy-pasteable, no placeholders left |
| `Evidence` | where the run artifacts land | `results/<run>` and/or `docs/evidence/<stamp>_<name>` |
| `Acceptance` | AC rows, each with its verifying command | maps to `docs/milestones/STATUS.md` when an AC id exists |
| `Invariants` | the ten rows of `quality-bar.md` with a mark | `HOLDS` / `VIOLATED` / `N/A` + one clause of why |
| `Risks` | what plausibly breaks, and the cheaper fallback | at least one row |
| `Deltas` | filled only by a `CHANGES` review loop | appended, never rewritten |

## Task row

```
T<k> · <imperative summary>
  Files:     <paths, exact>
  Depends:   T<j> | none
  Do:        <2-6 imperative lines, no rationale>
  Gate:      <command>
  Done-when: <observable in the gate output>
```

A task is sized so its gate runs in one command. A task that needs a decision the packet
does not contain is malformed: it goes back to the scoper, it is not improvised.

## Read-set

The executor's context is the packet plus the `Read-set`, and nothing else. Two rules make
that bound real rather than advisory:

- every path a task writes is in the `Read-set`, so `Files` never introduces a path the
  executor has not been permitted to open;
- a task that turns out to need a file outside the set is **malformed**. The executor logs
  the path it wanted and stops the task; it does not widen its own scope.

A packet whose `Read-set` exceeds roughly 20 files is two packets.

Two paths are outside the set by definition: the packet itself and the loop's own `log.md`,
which is always writable. A verification-only task — one that answers a question with a command
and changes nothing — writes `Files: none`, and its answer lands in the log.

## States

`READY` (scoped, not started) · `RUNNING` · `DONE` (gate green, evidence recorded) ·
`BLOCKED` (stop rule hit) · `CHANGES` (review returned it).
