# Acceptance criteria status

Updated: 2026-09-11. An AC is PASS only with an executed command and an excerpt
in the milestone report. This table is a tracker, not a substitute for those reports.

The review `docs/reviews/2026-09-11-m1-m5-review.md` invalidated part of the evidence behind this
table (one false PASS, and eleven rows produced by a checker that no longer ran). Every finding was
fixed and the affected criteria were re-run; `docs/reviews/2026-09-11-m1-m5-remediation.md` holds the
commands and their output. Rows re-verified after that work are marked "PASS (re-run 2026-09-11)".

| AC | Milestone | Status | Evidence |
|---|---|---|---|
| AC-1 | M1 | PASS (re-run 2026-09-11) | `docs/milestones/M1.md` (clean build of every package) |
| AC-2 | M1 | PASS | `docs/milestones/M1.md` |
| AC-2b | M1 | PASS | `docs/milestones/M1.md` |
| AC-3 | M2 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-3b | M2 | PASS | `docs/milestones/M2.md` |
| AC-4 | M3 | PASS | `docs/milestones/M3.md` |
| AC-5 | M3 | PASS | `docs/milestones/M3.md` |
| AC-6 | M3 | PASS | `docs/milestones/M3.md` |
| AC-7 | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-8 | M4 | PASS | `docs/milestones/M4.md` |
| AC-9 | M4 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-10 | M5 | PASS | `docs/milestones/M5.md` |
| AC-11 | M5 | PASS | `docs/milestones/M5.md` |
| AC-12 | M6 | PASS | `docs/milestones/M3.md` (hysteresis_dwell, same package) |
| AC-13 | M6 | PASS | `docs/milestones/M3.md` (latch_policy) |
| AC-14 | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-15 | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-15b | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-15c | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-16 | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-16b | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-17 | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-18 | M7 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-19 | M7 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-20 | M3 | PASS | `docs/milestones/M3.md` |
| AC-21 | M3 | PASS | `docs/milestones/M3.md` |
| AC-22 | M4–M6 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-23 | M8 | PASS | `docs/milestones/M8.md` |
| AC-24 | M8 | PASS | `docs/milestones/M8.md` |
| AC-25 | M8 | PASS | `docs/milestones/M8.md` |
| AC-26 | M8 | PASS | `docs/milestones/M8.md` |
| AC-27 | M9 | in progress | instrument smoke `composer-2.5` 1/1 nominal (`docs/milestones/M9.md`); not PASS (`repeats=1`, dirty tree) |
| AC-28 | M9 | in progress | mock path: 0 flyable unsafe plans (`scripts/tests/test_llm_eval.py`) |
| AC-29 | M9 | in progress | stop subset 8/8, 0 model requests (`docs/milestones/M9.md`) |
| AC-30 | M9 | PASS | `scripts/tests/test_llm_eval.py` (no key, no network) |
| AC-31 | M9 | in progress | nominal SITL PASS depth 0.000 m (`docs/milestones/M9.md`); outside-fence pair pending |
| AC-47 | M13c | in progress | `scripts/tests/test_keepout_analytic.py` (analytic cases PASS; Basilisk pairing not yet run) |
