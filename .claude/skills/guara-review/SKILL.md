---
name: guara-review
description: Stage 3 of the Guará pipeline — review what the Cursor/Grok loop produced against its packet, as a skeptical program committee, and return ACCEPT, CHANGES or REJECT. Use when asked to review a packet, check the loop output, verify a milestone claim, or before anything produced by the loop is proposed for merge.
---

# Stage 3 — review (Opus 5, fresh session)

Inputs: `packet.md`, `log.md`, the working tree. Output:
`.claude/pipeline/<ID>/review.md`. Do not fix while reviewing — findings only.

Start from a clean session. A reviewer carrying the scoper's context re-derives its
assumptions instead of testing them.

## Order

1. **Re-run the gates yourself.** A green row in the log is a claim, not evidence.
   A gate that will not run is a finding.
2. **Falsify the hypothesis.** Take the packet's Falsifier and try to produce it. State
   what you tried. A hypothesis nobody attacked is `UNKNOWN`, not confirmed.
3. **Check the numbers.** Every figure traces to `results/` via `scripts/aggregate.py` with
   its seed and commit, and to a published directory under `docs/evidence/`. A number
   without that chain is a REJECT-class finding.
4. **Check the grounding.** Every upstream API claim resolves to `repo@commit:file:line`
   against `third_party/` at the pinned commit. Open the file and read the line.
5. **Check test-first.** For each safety function: does a test exist that fails without the
   implementation? Verify by reverting the implementation, not by reading the diff.
6. **Walk the ten invariants.** `.claude/skills/guara-pipeline/references/quality-bar.md`,
   each marked with the evidence that decided the mark.
7. **Scope check.** Files touched outside the packet's Tasks. Claims widened beyond
   `README.md` §7 limits. Anything in the Non-goals list.
8. **Hygiene.** SPDX headers, NOSA isolation, links, commit messages, no AI mention, English.

## Findings

| Severity | Meaning |
|---|---|
| BLOCK | a false claim, an unbacked number, a weakened gate, a scope breach |
| MAJOR | an invariant violated, a missing test, grounding from memory |
| MINOR | hygiene, wording, a missing link |

Each finding: file:line, what is wrong, the command or excerpt that shows it, the smallest
fix. No praise, no summary of what went well.

## Verdict

| Verdict | Condition | Next |
|---|---|---|
| ACCEPT | no BLOCK, no MAJOR; gates re-run green | packet `DONE` |
| CHANGES | MAJOR or BLOCK with a bounded fix | append to packet §Deltas, return to `guara-execute` (max 2 returns) |
| REJECT | the hypothesis is refuted, or the approach is wrong | re-scope from `guara-scope` |

A finding that turns out to affect the repository beyond this packet is copied to
`docs/reviews/<YYYY-MM-DD>-<slug>.md`. Nothing else from the pipeline leaves `.claude/`.

## Close

Print, and nothing else:

```
packet:  <ID>
verdict: ACCEPT | CHANGES | REJECT
block:   <n>   major: <n>   minor: <n>
re-run:  <gates you executed>
```
