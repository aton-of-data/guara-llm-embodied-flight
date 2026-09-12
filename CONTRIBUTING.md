# Contributing to Guará

Guará is a research prototype for civil flight safety, in the air and in orbit. Its claims are
limited to what an executed command supports, and the contribution rules exist to keep that
true. Read [§7 · Limits](README.md#7--limits-what-guará-does-not-guarantee) first — it says what
this project does *not* guarantee, and a contribution that quietly widens a claim is the one
kind of change that damages it.

## Scope

Civil flight safety only. Contributions implementing weapons or any payload intended to harm,
target selection, tracking or identification of specific people for enforcement or harassment,
covert surveillance, or the defeat of geofences, remote ID or failsafes will not be accepted
([ADR 0009](docs/adr/0009-use-case-capability-packs.md) §4). This is not negotiable and applies
regardless of how a change is framed.

## The rules that are not style preferences

These five are the ones a reviewer will actually block on.

1. **No number without a run.** Performance figures come only from `results/` via
   `scripts/aggregate.py`, and the reviewable part of a run is published under
   [`docs/evidence/`](docs/evidence). No milestone is complete without an executed command and
   an excerpt of its output. Never write a measurement you did not produce.
2. **No API from memory.** Every behavioural claim about PX4, ROS 2, F´, Ogma, Copilot,
   DAIDALUS or FRET cites `repo@commit:file:line` in [`GROUNDING.md`](GROUNDING.md), against the
   shallow clones pinned in [`third_party/VERSIONS.md`](third_party/VERSIONS.md). If your change
   touches an API, add the `GROUNDING.md` row **first**.
3. **Every safety function has a test that fails before the implementation.** Write the failing
   test, watch it fail, then implement.
4. **The decision path carries no dynamic allocation and has bounded time.** `DecisionCore` and
   everything it calls per tick. `test_decision_core_no_alloc.cpp` and
   `test_decision_core_timing.cpp` enforce it.
5. **A new flight operation gets its document before it gets code.** One document per operation,
   air and space, in [`docs/operations/`](docs/operations/README.md), with its checks, channels,
   recovery function and evidence.

## Licence and the NOSA boundary

Guará is Apache-2.0. Every new source file starts with `SPDX-License-Identifier: Apache-2.0`.

Nothing under the NASA Open Source Agreement may live outside `nosa/`
([ADR 0003](docs/adr/0003-daidalus-nosa-isolation.md)), and no GPL-2.0-only dependency may enter
the tree at all. The boundary is enforced by a script, not by convention:

```bash
python3 scripts/check_license_isolation.py
```

By contributing you agree your contribution is licensed under Apache-2.0.

## Setting up

The trusted mission layer is pure Python and needs no container:

```bash
pip install -r requirements-dev.txt
python3 -m pytest scripts/tests -q
python3 -m mission.compiler --intent mission/intents/survey_north_3.json
```

The C++ arbiter, the monitors and the SITL scenarios need the containers — see
[§9 · Reproduce it](README.md#9--reproduce-it). C++17, colcon/ament, gtest and launch_testing.

## Commits and pull requests

- **Granular commits**: one logical change each. A fix, its test and its documentation are
  usually three commits, not one.
- **Message format**: `type(scope): imperative summary` — for example
  `feat(rta): add dwell-time hysteresis`. Types in use: `feat`, `fix`, `test`, `docs`, `build`,
  `chore`.
- **English** everywhere: code, comments, documents, commit messages. Regulatory source excerpts
  may stay in their original language when quoted; paraphrase in English.
- **No `Co-authored-by` trailer**, and no mention of an assistant or AI tool in any commit
  message, code comment or document.
- In the pull request, say which command you ran and paste the output excerpt that supports it.

## Where help is most useful right now

These are open risks and unmet acceptance criteria, not invented tasks. Each links to where it
is tracked.

| Area | What is needed | Tracked as |
|---|---|---|
| Formal methods | A Haskell/LLVM/z3 environment that unblocks CopilotVerifier | R-11, blocks RQ4 |
| Detect and avoid | Sourced well-clear thresholds suited to small UAS, rather than DO-365B's large-aircraft values | R-5 |
| SITL | A traffic-injection path in PX4 SITL, never exercised | R-7 |
| Security | An SROS2 profile for the CF and bridge topics | FM-12 |
| Standards | A review of [§5.1](docs/ARCHITECTURE.md#51-astm-f3269-roles--guará-components) against the licensed ASTM F3269 text | R-8 |
| Space | A Basilisk ↔ ROS 2 setup that lets the existing arbiter face orbital dynamics | AC-48 |
| Space | A review of the safe-mode specification by someone who has flown one | RS-1 |
| LLM layer | A run of the corpus against a live `ollama` or `openai-compat` endpoint, and an Anthropic provider beside them | [`scripts/llm/provider.py`](scripts/llm/provider.py) |

Issues labelled `good first issue` are bounded, touch no arbiter code, and produce a visible
result. If you are unsure whether something is in scope, open an issue before writing code.

## Reporting a vulnerability

Do not open a public issue. See [`SECURITY.md`](SECURITY.md).

## Working notes

[`CLAUDE.md`](CLAUDE.md) is the project's own working-rules file and
[`docs/guara-prompt-pack.md`](docs/guara-prompt-pack.md) records the prompt sequence used to build
parts of this repository. Both are published for transparency about how the work was produced.
Neither is a contribution guide — this file is.
