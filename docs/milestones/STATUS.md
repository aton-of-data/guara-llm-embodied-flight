# Acceptance criteria status

Updated: 2026-09-13. An AC is PASS only with an executed command and an excerpt in the
milestone report. This table is a tracker, not a substitute for those reports.

Threads (`docs/PLAN-M8-M16.md` §1, `docs/PLAN-M17-M28.md`): **core** = the PX4 RTA of
M1–M7 · **A** = air / LLM embodiment · **B** = the F´ host · **C** = the space domain ·
**S** = setup and delivery. Statuses are `PASS`, `in progress` (code exists, the criterion
is not met yet) and `planned` (specified, no code). Every `planned` row is a promise in
the plan, not work in flight.

The review `docs/reviews/2026-09-11-m1-m5-review.md` invalidated part of the evidence behind this
table (one false PASS, and eleven rows produced by a checker that no longer ran). Every finding was
fixed and the affected criteria were re-run; `docs/reviews/2026-09-11-m1-m5-remediation.md` holds the
commands and their output. Rows re-verified after that work are marked "PASS (re-run 2026-09-11)".

## Executed criteria

| AC | Thread | Milestone | Status | Evidence |
|---|---|---|---|---|
| AC-1 | core | M1 | PASS (re-run 2026-09-11) | `docs/milestones/M1.md` (clean build of every package) |
| AC-2 | core | M1 | PASS | `docs/milestones/M1.md` |
| AC-2b | core | M1 | PASS | `docs/milestones/M1.md` |
| AC-3 | core | M2 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-3b | core | M2 | PASS | `docs/milestones/M2.md` |
| AC-4 | core | M3 | PASS | `docs/milestones/M3.md` |
| AC-5 | core | M3 | PASS | `docs/milestones/M3.md` |
| AC-6 | core | M3 | PASS | `docs/milestones/M3.md` |
| AC-7 | core | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-8 | core | M4 | PASS | `docs/milestones/M4.md` |
| AC-9 | core | M4 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-10 | core | M5 | PASS | `docs/milestones/M5.md` |
| AC-11 | core | M5 | PASS | `docs/milestones/M5.md` |
| AC-12 | core | M6 | PASS | `docs/milestones/M3.md` (hysteresis_dwell, same package) |
| AC-13 | core | M6 | PASS | `docs/milestones/M3.md` (latch_policy) |
| AC-14 | core | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-15 | core | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-15b | core | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-15c | core | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-16 | core | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-16b | core | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-17 | core | M3 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-18 | core | M7 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-19 | core | M7 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-20 | core | M3 | PASS | `docs/milestones/M3.md` |
| AC-21 | core | M3 | PASS | `docs/milestones/M3.md` |
| AC-22 | core | M4–M6 | PASS (re-run 2026-09-11) | `docs/reviews/2026-09-11-m1-m5-remediation.md` §5 |
| AC-23 | A | M8 | PASS | `docs/milestones/M8.md` |
| AC-24 | A | M8 | PASS | `docs/milestones/M8.md` |
| AC-25 | A | M8 | PASS | `docs/milestones/M8.md` |
| AC-26 | A | M8 | PASS | `docs/milestones/M8.md` |
| AC-27 | A | M9 | in progress | instrument smoke `composer-2.5` 1/1 nominal (`docs/milestones/M9.md`); not PASS (`repeats=1`, dirty tree) |
| AC-28 | A | M9 | in progress | mock path: 0 flyable unsafe plans (`scripts/tests/test_llm_eval.py`) |
| AC-29 | A | M9 | PASS | stop corpus 24/24, 0 model requests, repeats=3, clean tree (`docs/evidence/20260912T114925Z_cursor-stop-r3_cursor-agent/`) |
| AC-30 | A | M9 | PASS | `scripts/tests/test_llm_eval.py` (no key, no network) |
| AC-31 | A | M9 | PASS | pair on=0.000 m off=47.178 m (`docs/evidence/20260912T134907Z_llm_survey_outside_s42_pair/`); nominal member also PASS |
| AC-47 | C | M13c | PASS | `docs/milestones/M13c.md` (analytic cases, ±0.05 s, clean tree at `696c4ed`) |
| AC-51 | S | M17 | in progress | `guara doctor` (tier 0); not PASS until Linux, macOS and Windows/WSL are all recorded |
| AC-52 | S | M17 | in progress | pin-drift check and hash-pinned `requirements.lock` (CPython 3.10); second-machine byte-identity unrecorded |
| AC-55 | S | M17 | in progress | `core` job in `.github/workflows/checks.yml`; matrix evidence not yet recorded |
| AC-57 | K | M18 | in progress | `core/` CMake library and C ABI; `guara params check`; coding subset [REVIEW] in `core/CODING_SUBSET.md` |
| AC-58 | K | M18 | in progress | `colcon test --packages-select guara_rta --ctest-args -R 'decision_core\|hysteresis\|latch\|gateway'`: 8/8 on arm64 in `guara-dev:m1`; no milestone report yet |
| AC-62 | K | M18 | in progress | `scripts/core_qa.sh`: ASan/UBSan on ABI tests; clang-tidy; vector-suite coverage unmeasured |
| AC-63 | K | M19 | in progress | spec_s3.json: T1–T7, T2b, FM-7, hysteresis band, intent-aware T5; gateway vectors absent |
| AC-64 | K | M19 | in progress | `scripts/ctk_mutation.sh` rejects a T4-disabled Python port; ROS/F´/SIL mutations untested |
| AC-65 | K | M19 | in progress | `guara ctk run --port python` passes spec_s3; ambiguities filed in SPEC §3.6, not resolved |

## Planned criteria

No code exists for these. They are listed so that the scope of the claim is visible in the same
place as the evidence for it.

| AC | Thread | Milestone | Content | Blocked on |
|---|---|---|---|---|
| AC-32 | A | M9b | SROS2: an uncredentialed node cannot publish an accepted CF setpoint | an SROS2 profile for `/guara/cf/*` (FM-12) |
| AC-33 | A | M9b | PX4 bridge topics under the same policy, or the run declares the omission | AC-32 |
| AC-34 | A | M10 | Voice: utterance end → readback, and stop word → recovery function active with the model killed | the voice pipeline |
| AC-35 | A | M10 | Every RTA switch announced with its cause channel, in the configured language pack | the voice pipeline |
| AC-36 | A | M11 | Achieved coverage and GSD computed from the log and the captures, with method and uncertainty | imaging and ODM products |
| AC-37 | A | M11 | Every quantitative statement in a generated report traces to a computed index | AC-36 |
| AC-38 | A | M12 | No class D/T/C capability pack loads without its monitors and site preconditions | the D/T/C monitors (ADR 0009) |
| AC-39 | B | M13 | The PX4 unit ACs pass against the extracted shared core with no edits to the test files | `guara_core` extraction |
| AC-40 | B | M13 | The F´ adapter produces the same decisions as the ROS 2 adapter on the same input vectors | the F´ deployment, `scripts/fprime.sh` |
| AC-41 | B | M13 | A hung decision core is detected by `Svc::Health` and the detection time recorded | AC-40 |
| AC-42 | B | M14 | Safe-mode entry stops the sequence, commands the survivable attitude and sheds loads in bounded cycles | the safe-mode component (risk RS-1) |
| AC-43 | B | M14 | Safe mode is latched: no return to the CF without a ground command | AC-42 |
| AC-44 | B | M14 | Safe-mode entry is idempotent, with exactly one entry event | AC-42 |
| AC-45 | B | M15 | An Ogma-generated F´ monitor publishes a **verdict on an output port** and is consumed unmodified | upstream Ogma work (GROUNDING D.8) |
| AC-46 | B | M15 | The generated component's module name is configurable and compiles with no hand edits | upstream Ogma work (GROUNDING D.8) |
| AC-48 | C | M13c | An orbital run: keep-out channel on = zero cone violation, channel off = violation | a simulator in the loop (Basilisk ↔ ROS 2) |
| AC-49 | C | M16 | Latency budget in the orbital profile with the F´ host, reported as AC-18 reports PX4 | M13, M14 |
| AC-50 | C | M16 | Zero adversarial utterances produce a sequence that passes both sequencer validation and the gate | the intent → sequence compiler |
| AC-53 | S | M17 | Multi-arch `guara-dev` pull; a scenario runs from the digest with no PX4 source build | GHCR publish of linux/amd64 and linux/arm64 |
| AC-54 | S | M17 | Cold clone → first green SITL measured on a declared reference machine | `scripts/bench_setup.sh` |
| AC-56 | S | M17 | Tier-2 path runs with the network disabled when the image and clones are cached | `GUARA_OFFLINE=1` |

M18–M28 (AC-57..AC-101) are specified in [`docs/PLAN-M17-M28.md`](../PLAN-M17-M28.md) §3–§6 and are not yet inventoried here as in-progress work.

Operation-level view of the same scope: [`docs/operations/`](../operations/README.md).
