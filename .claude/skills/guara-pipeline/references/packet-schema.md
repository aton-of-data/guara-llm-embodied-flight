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

## States

`READY` (scoped, not started) · `RUNNING` · `DONE` (gate green, evidence recorded) ·
`BLOCKED` (stop rule hit) · `CHANGES` (review returned it).
