# The agent pipeline

Most of this repository was produced by language models under a fixed process. This document
describes that process, and the files that enforce it, so a reader can judge the work by the
method rather than by the claim. It is a working practice, not an architectural decision:
there is no ADR behind it, and nothing here constrains a human contributor, who is governed by
[`CONTRIBUTING.md`](../CONTRIBUTING.md).

The premise is that a model is reliable in proportion to how little it is asked to decide at
once. So the work is split into three stages run by different models in different tools, each
with one job, and each stage hands the next a written artifact rather than a conversation.

## The three stages

| # | Stage | Where | Job | Artifact |
|---|---|---|---|---|
| 1 | Scope | a large model, one session per packet | Turn a request into a falsifiable claim with tasks, gates and acceptance | `packet.md` |
| 2 | Execute | a fast model in an editor loop | Implement one task at a time against its gate | `log.md` |
| 3 | Review | a large model, fresh session | Re-run the gates, attack the claim, return a verdict | `review.md` |

The separation is the point. A scoper that writes code defends its own plan; an executor that
redefines acceptance moves the target it is being measured against; a reviewer carrying the
scoper's context re-derives its assumptions instead of testing them. So stage 3 starts from a
clean session, and stage 2 is forbidden to improvise: a task needing a decision the packet does
not contain goes back to stage 1.

A review returns `ACCEPT`, `CHANGES` or `REJECT`. `CHANGES` appends to the packet and returns
to stage 2, at most twice; after that the packet is re-scoped. `REJECT` means the claim was
refuted or the approach was wrong, which is an outcome, not a failure.

## Stage 1 is the scientific part

The scoping stage runs a fixed order — question, hypothesis, falsifier, grounding, procedure,
tasks, acceptance — and forbids writing tasks before the procedure exists. That order is what
keeps the rest honest:

- A **hypothesis** is phrased so an observation can refute it. "The arbiter reaches Hold within
  X ms of the monitor trip", not "latency improves".
- A **falsifier** is named before the work starts, and stage 3 tries to produce it. A claim
  nobody attacked is recorded `UNKNOWN`, not confirmed.
- **Grounding** rows cite `repo@commit:file:line` against the pinned clones in `third_party/`
  ([`GROUNDING.md`](../GROUNDING.md)). A row that is not known is written `UNKNOWN` and becomes
  a task; it is never guessed.
- **Acceptance** rows each carry the command that verifies them, and reuse an AC id from
  [`docs/milestones/STATUS.md`](milestones/STATUS.md) when one exists.

This is the same discipline the repository already applies to its results — no number without a
run, no API from memory — moved one step earlier, to the point where the work is defined.

## What every stage restates

Ten invariants, distilled from [`CLAUDE.md`](../CLAUDE.md) and the five blocking rules in
[`CONTRIBUTING.md`](../CONTRIBUTING.md), are carried by every artifact and marked `HOLDS`,
`VIOLATED` or `N/A` with the evidence that decided the mark. They live in one file,
[`quality-bar.md`](../.claude/skills/guara-pipeline/references/quality-bar.md), together with
the script that enforces each and the standing gate commands.

Two rules do most of the work. A gate that reports zero tests is red, not green — a check that
selected nothing has verified nothing. And no gate is ever made to pass by weakening a test, a
threshold or an acceptance criterion; doing so is a `CHANGES` verdict by construction.

## The files

| File | Loaded by | Carries |
|---|---|---|
| [`.claude/skills/guara-pipeline/`](../.claude/skills/guara-pipeline/SKILL.md) | Claude Code | The stage map, the quality bar, the packet schema |
| [`.claude/skills/guara-scope/`](../.claude/skills/guara-scope/SKILL.md) | Claude Code | Stage 1: the seven-step order, the pre-flight reads, the hard stops |
| [`.claude/skills/guara-execute/`](../.claude/skills/guara-execute/SKILL.md) | Claude Code | Stage 2: the handoff and the loop |
| [`.claude/skills/guara-review/`](../.claude/skills/guara-review/SKILL.md) | Claude Code | Stage 3: the review order, the severities, the verdicts |
| [`.cursor/rules/guara-repo.mdc`](../.cursor/rules/guara-repo.mdc) | every editor request | The ten invariants, compressed |
| [`.cursor/rules/guara-executor.mdc`](../.cursor/rules/guara-executor.mdc) | a packet loop | The per-task loop, the stop conditions, the log discipline |
| [`.cursor/rules/guara-sources.mdc`](../.cursor/rules/guara-sources.mdc) | editing a source file | SPDX, doc comments only, the per-tick path, test first |

The two surfaces are mirrors, and they drift silently if nobody checks, so a script checks:

```bash
python3 scripts/check_pipeline.py
```

It resolves every cross-reference in the skills and the rules, verifies that every script named
by the quality bar exists, and refuses a rule file that lost its front matter. It runs in CI
beside the licence, header and link checks.

Packets, logs and reviews are written under `.claude/pipeline/<ID>/` and stay there: that
directory is ignored by git. What leaves it is the work itself, and any finding with reach
beyond one packet, copied into [`docs/reviews/`](reviews).

## Limits

This process constrains how work is produced; it does not make a model correct. Every claim in
this repository still rests on an executed command and its output, which is what
[`docs/evidence/`](evidence) holds and what a reviewer should read first. The stages reduce two
specific failures — a plan that quietly becomes its own verification, and a change that widens
a claim nobody re-tested — and they do not address a third: a wrong hypothesis, stated
precisely, executed cleanly and confirmed by a gate that measures the wrong thing. Only a
reader can catch that one.
