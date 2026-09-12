# Public-readiness review — impact and usability

Date: 2026-09-12 · Reviewed commit: `7e204a7` · Scope: the repository as a public artefact,
not the correctness of the RTA. Nothing here re-scores an acceptance criterion.

Method: read the tree at `7e204a7`, resolved every internal README link, imported the pure-Python
packages outside the container, and read the GitHub repository metadata. Findings are separated
into what blocks the repository going public (P0), what costs contributors after it is public (P1),
and what decides whether it is found at all (P2).

---

## 0 · Status, 2026-09-12

Worked on branch `feature/2026-09-12-public-readiness-review`. Every P0 and P1 item is done,
and the implementable part of P2 is done; what remains needs a decision or an account that
this review cannot make on its own.

| Item | State | Note |
|---|---|---|
| P0-1 repository is private | **maintainer** | A settings change. Everything below is ready for it |
| P0-2 `CITATION.cff` | done | Repository name fixed; invalid `year` key dropped; `commit` and `contact` added |
| P0-3 Python dependencies | done | `requirements.txt`, `requirements-dev.txt`, and the same pins in the dev image |
| P0-4 CI | done | `checks.yml`: python, boundaries, cpp. All three green; the `cpp` job builds 2 packages and runs 22 gtest cases |
| P0-5 contribution surface | done | `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, three issue forms, PR template |
| P1-1 60-second path | done | `python3 -m mission.compiler`, two example intents, README block |
| P1-2 README split | done | 630 → 428 lines; four documents under `docs/` |
| P1-3 hero image | done | 2.3 MB → 227 KB across both mascots |
| P1-4 LLM providers | done | `ollama` and `openai-compat` added; unit-tested, never run against a live endpoint |
| P1-5 empty `results/` | done | `results/README.md`, and the ignore rule corrected to admit it |
| P1-6 prompt pack | done | Moved to `docs/guara-prompt-pack.md` |
| P1-7 published image | done | Manual workflow with a NOSA guard. Never run |
| P2-1 announcements | **maintainer** | §7 has the venues and the framing for each |
| P2-2 preprint | **maintainer** | An authorship decision |
| P2-3 figures | done | Generated from the evidence by `scripts/plot_evidence.py` |
| P2-4 release, Discussions | partly | `CHANGELOG.md` and the release procedure are in; cutting the tag and enabling Discussions are settings actions |

**The `cpp` job needed a correction on its first real run, and it was the worst kind.** It
reported success having built and tested nothing: `colcon` warns rather than fails when
`--packages-select` names a package it did not discover, and `colcon test-result` exits 0 on
zero tests, so the job was green with `0 packages finished` and `0 tests`. Discovery is now
explicit through `--base-paths`, and a final step fails the job unless both packages produced a
build directory and at least one test ran. It now reports `2 packages finished` and
`22 tests, 0 errors, 0 failures`.

**`publish-dev-image.yml` still has never executed**, because it builds PX4 from source and is
manual by design. Whether it fits a runner's disk and time budget is unknown.

**Defects found while doing the work**, none of which this review predicted:

- The evaluation harness failed on a clean clone: it created `results/latest_llm`
  unconditionally, and `results/` does not exist until a run has produced it. That was AC-30's
  own no-key, no-network test.
- `--api-key-env` defaulted to `CURSOR_API_KEY` for every provider, so the run evidence
  recorded a credential variable name even for runs that used none — which matters because
  ADR 0013 decision 7 makes that name part of the evidence contract.
- `scripts/plot_evidence.py` raised `ValueError` from `relative_to` instead of its named error
  when pointed at an evidence path outside the repository.
- The README claimed twelve scenarios; fourteen ship.
- The SPDX rule in `CLAUDE.md` and ADR 0006 had nothing enforcing it, and two relative links
  broke silently during the README split.

**Four checks passed only because they could not fail**, each caught and fixed: a link-checker
probe that was untracked and therefore invisible to `git ls-files`; a figure-freshness test that
regenerated the file it was about to compare; a missing-evidence test that passed because the
*script path* did not resolve, never reaching the loader; and the `cpp` CI job above, which is
the one that mattered, since it would have certified every future pull request while running
nothing. Any new check on this branch now gets a negative test — run it against the failure it
is supposed to catch — before it is trusted. A green tick is not evidence; the log is.

---

## 1 · Verdict

**The content is ready. The distribution is not.**

The engineering substance is well above the bar for a public research repository: thirteen ADRs,
a grounded API record (`GROUNDING.md`), an acceptance tracker that documents its own invalidated
rows, evidence directories published verbatim, a licence boundary enforced by a script rather than
by convention, and a README that states its limits before its results. Repositories with a tenth
of this get attention.

What is missing is everything between a visitor and their first executed command. The repository
is private, has no CI, declares no Python dependencies, offers no path that runs in under an hour,
and has no contribution surface (no `CONTRIBUTING.md`, no issue templates, no filed issues) despite
a README section that names six specific contributions it wants. The result is a project that
reads as finished and behaves as unenterable.

Estimated work to close P0 + P1: one to two focused days. None of it touches the arbiter.

---

## 2 · What already works, and should not be changed

These are the assets. Any restructuring must preserve them.

| Asset | Why it carries weight |
|---|---|
| §8 "Limits: what Guará does not guarantee" | Naming FM-1…FM-12, `[UNKNOWN]` controller behaviour and "SITL does not transfer" before anyone asks is the single most credibility-positive thing in the repository. Reviewers in this field read the limits section first. |
| The invalidated-evidence history in `docs/milestones/STATUS.md` | A tracker that records one false PASS and eleven rows from a checker that had stopped running, plus the re-run commands, is stronger evidence of process than an all-green table. |
| §2.2, the natural-language-drone-control table | Nine surveyed works with their stated safety basis, ending in a one-line thesis ("safety = prompt engineering + tool restriction + human override"). This is the paragraph that will be quoted. |
| `GROUNDING.md` `repo@commit:file:line` discipline | Removes the whole class of "the README says the API does X" objections. |
| The NOSA isolation boundary with `check_license_isolation.py` | Turns a licence worry into a passing check. This is genuinely reusable by other projects and is worth its own write-up. |
| Trademarks section | Nominative-use handling of NASA / PX4 / ROS marks, done correctly and in advance. Most projects get a takedown request first. |
| `docs/operations/` as the scope map | One document per flight operation, air and space, before code. Rare and legible. |

---

## 3 · P0 — blocks going public

### P0-1 · The repository is private

`aton-of-data/guara-llm-embodied-flight` is `private: true`, 0 stars, 0 forks, 0 issues. Description
and 21 topics are already set and are good. Nothing below matters until visibility flips.

### P0-2 · `CITATION.cff` points at a repository that does not exist

```yaml
repository-code: "https://github.com/aton-of-data/guara"
```

The repository is `guara-llm-embodied-flight`. Any citation generated from this file resolves to a
404. This is the one defect that directly damages the stated goal of being citable.

Also missing from the file: `url`, `version`/`commit`, `date-released`, and `abstract` keywords
already present in the README. Add them so the GitHub "Cite this repository" widget is complete.

### P0-3 · Python dependencies are declared nowhere

`mission/compiler/intent.py` imports `jsonschema`; the harness and the compiler import `yaml`; the
README documents `python3 -m pytest scripts/tests -q`. There is no `requirements.txt`, no
`pyproject.toml`, and `docker/Dockerfile` installs `python3-pip` without installing any of them.
Confirmed outside the container: `space.keepout` imports clean, `mission.compiler.compile` fails on
`ModuleNotFoundError: No module named 'jsonschema'`.

Two consequences. A visitor cannot run the mission compiler at all without guessing the dependency
set, and the documented pytest command needs verification inside a freshly built `guara-dev:m1`
before it is left in the README as a promise.

### P0-4 · No CI

There is no `.github/` directory. Every claim in the repository is reproducible by hand and none of
it is reproduced automatically. For a project whose central principle is "no number without a run",
the absence of a green badge is a structural contradiction a reviewer will notice.

The heavy PX4 SITL batch does not belong in CI. Everything else does, and it is cheap:

- `scripts/tests/` (mission compiler, corpus, plan executor, keep-out, AC checker, LLM harness on
  the `mock` provider — which exists precisely so this is possible with no key and no network)
- `scripts/check_license_isolation.py`
- an SPDX-header check over every new source file (currently a CLAUDE.md rule with no enforcement)
- a link check over README and `docs/` (they are clean today; keep them clean)
- a `colcon build` + `colcon test` of `guara_rta`, `guara_geofence`, `guara_msgs` in a ROS 2 Humble
  container — this is the C++ core, and it does not need PX4 SITL to compile and unit-test

### P0-5 · No contribution surface

No `CONTRIBUTING.md`, no `CODE_OF_CONDUCT.md`, no `SECURITY.md`, no issue or PR templates, no filed
issues. README §14 names six concrete wanted contributions (R-11, R-5, R-7, FM-12, R-8, AC-48/RS-1)
— and offers nowhere to claim one. That paragraph is the highest-value content in the repository for
an incoming contributor and it is currently a dead end.

`SECURITY.md` is not optional here: this is safety-critical flight software with a documented
unauthenticated-DDS failure mode (FM-12). A disclosure address must exist before the code is public.

---

## 4 · P1 — the adoption funnel

### P1-1 · There is no path to a first result in under an hour

The only documented entry point is `./scripts/fetch_third_party.sh` followed by a `guara-dev:m1`
build that compiles PX4 v1.17.0 SITL with submodules and builds the Micro XRCE-DDS Agent from
source. That is tens of minutes at best, on a machine with Docker, before a visitor sees anything.

Meanwhile `mission/` and `space/` are pure Python needing two pip packages. The mission compiler,
the labelled corpus, the stop grammar and the analytic keep-out predictor — which is to say the
entire LLM-embodiment story that the repository is named after — run on a laptop in seconds.

**This is the largest single leverage point in the review.** A "60-second try" that compiles an
utterance into a plan, then shows the same envelope refusing an unsafe one, converts a reader into
a user before they have decided whether to install Docker.

Suggested shape, near the top of the README:

```bash
pip install -r requirements.txt
python3 -m mission.compiler.compile --site mission/site/demo_farm.yaml \
  --utterance "survey the north field at 40 metres"     # -> a plan
python3 -m mission.compiler.compile --site mission/site/demo_farm.yaml \
  --utterance "survey 500 metres north of the fence"    # -> a named refusal
```

(A single-utterance CLI entry point does not exist yet and would need adding; the compiler is
currently reachable only through the eval harness and the tests.)

### P1-2 · The README is a paper, not a landing page

592 lines, ~5,300 words, 14 numbered sections, with "Reproduce it" at section 10 — line 399 of 592.
The writing is excellent and nothing in it is filler. That is the problem: a first-time visitor
must read a 40 KB document to find out whether they can run anything.

Recommended split, no content lost:

- **README** keeps: the hero, the two-domain table, §1 the gap, §2.2 the prior-art thesis, the
  measured-results table, the 60-second try, the limits section, and links out. Target ≤ 250 lines.
- **`docs/ARCHITECTURE.md`** takes §5, §6 and the gateway-enforcement table.
- **`docs/RELATED-WORK.md`** takes the whole of §2 — it is a literature review and a genuine
  standalone contribution that is currently buried at line 91 of a README.
- **`docs/ROADMAP.md`** takes §12.
- **`docs/LICENSING.md`** takes §13 and the trademarks section.

### P1-3 · The `mascot.png` hero is 1.8 MB

Every page view pulls 1.8 MB before the first sentence, and it is the first thing a mobile visitor
loads. Resize to ~800 px wide and re-encode; keep the original under `docs/assets/`.

### P1-4 · The LLM layer supports exactly one real provider

`PROVIDERS = {"mock": MockProvider, "cursor-agent": CursorAgentProvider}`.

For a repository whose title is *LLM-embodied flight*, the only way to reproduce RQ6a/RQ6b is a
paid Cursor plan with enough concurrent Cloud Agent slots — the provider even carries an
`is_capacity_error` helper for "upgrade to Ultra". Nobody outside will reproduce the headline
numbers.

The provider abstraction is already the right shape (prompt in, text out; never sees the site model
or the plan). Adding providers is contained, low-risk work and does not touch the arbiter:

- an **OpenAI-compatible** provider, which simultaneously covers OpenAI, vLLM, llama.cpp,
  LM Studio and OpenRouter via a base-URL parameter
- an **Anthropic** provider
- an **Ollama** provider — the one that matters most, because §9 commits to *open-weight* models and
  because a reviewer with no API key can then reproduce the corpus offline

This single change moves the LLM claim from "trust the evidence directory" to "run it yourself",
and it is also what makes the repository interesting to the local-LLM community, which is large and
under-served in robotics.

### P1-5 · `results/` does not exist in a fresh clone

Six documented commands take a `results/...` path. The directory is git-ignored and absent, so each
of those commands fails on a clean checkout until a run has produced it. Say so explicitly in the
reproduce table, or ship a `results/.gitkeep` with a one-line README explaining that
`docs/evidence/` is the published, reviewable subset.

### P1-6 · `CLAUDE.md` and `guara-prompt-pack.md` sit at the repository root

Both are interesting and should stay public — the prompt pack in particular is an honest artefact
and a differentiator. But at the root they read as project instructions to a human contributor and
will be mistaken for the contribution guide, especially while no `CONTRIBUTING.md` exists. Move the
prompt pack to `docs/`, keep `CLAUDE.md` at the root (tooling expects it there), and have
`CONTRIBUTING.md` point at both with one sentence explaining what they are.

### P1-7 · No published container image

Every documented command begins with a local image build. Publishing `guara-dev` to GHCR would
remove the largest single barrier to running the SITL scenarios.

Caveat, and it is a real one: the NOSA/Apache interaction is marked `[REVIEW]` and ADR 0003 requires
a lawyer before distributing any container that embeds DAIDALUS. `guara-dev:m1` does **not** embed
DAIDALUS (that is `scripts/daa.sh`'s separate path), so publishing the dev image appears clear —
but confirm the image contents against `check_license_isolation.py` before pushing, and do not
publish any image built from `nosa/`.

---

## 5 · P2 — why it will or will not be found

### P2-1 · Nothing has been announced anywhere

Zero stars is not a quality signal, it is a distribution signal. The audiences for this work are
specific, reachable, and currently unaware of it. See §7.

### P2-2 · There is no preprint

README §14 says so plainly. The repository is dense enough that the paper is mostly assembled:
§1 is the gap, §2 is related work, §5–6 are the method, §7 is the result, §8 is the threats to
validity. P6 already targets NFM. Until an arXiv number exists there is nothing for anyone to cite,
and citation is how a repository like this compounds.

### P2-3 · The results are invisible at a glance

The headline claim — **p99 61 ms** — is a table cell at line 327 of the README. It is not in the
hero, not a badge, and not a figure. One latency-distribution plot from the 30-run batch, and one
RTA-on-vs-off geofence trace from the paired run (0.000 m vs 47.178 m breach), would do more for
comprehension than several paragraphs. Both datasets already exist under `docs/evidence/`.

Add badges that are true today: license, PX4 v1.17.0, ROS 2 Humble, and — once CI exists — a build
badge and a "p99 switch latency 61 ms" badge linked to `docs/evidence/batch_latency/`.

### P2-4 · No GitHub Discussions, no releases, no tags

`has_discussions: false`, no releases. Cut a `v0.1.0` release at the commit that carries the
measured batch, with release notes that name the evidence directory. A release is what makes the
CITATION commit stable and is the natural object to link in an announcement.

---

## 6 · The open threads this repository can answer

These are the issues to file. Each is a thread that exists in someone else's repository, paper or
standard, and that this repository is specifically positioned to close. They are ordered by how
much credibility each buys relative to its cost.

### Upstream contributions — the highest-value work

| # | Thread | Where it lives | What Guará ships | Cost |
|---|---|---|---|---|
| U1 | Ogma has no PX4 variable database or example | `nasa/ogma` | `guara_monitors/specs/vars-db.json` over `px4_msgs`, a customised ROS template, and a generated monitor flying against `/fmu/out/*`. This is contribution **C2** and it is already written. | Low — it is a PR against an Apache-2.0 NASA repo, and it makes Guará part of Ogma's own documentation |
| U2 | Ogma's F´ backend emits events only, into a hardcoded `module Ref`, with no verdict output port | `nasa/ogma` | The gap is documented in `GROUNDING.md` D.8; the fix is a verdict output port and a configurable module name (AC-45, AC-46) | Medium, and it is the single change that makes Ogma usable for RTA rather than logging, in any F´ mission |
| U3 | PX4's external-mode fallback fires only on arming-check timeout, never on a predicted property violation | `PX4/PX4-Autopilot` (PR #20707) | A working semantic fallback built entirely on the existing interface, with measured switch latency and five characterised failure modes | The PR is large; the *issue comment* carrying the measurement is not, and should be posted first |
| U4 | `px4-ros2-interface-lib` documents executor-death timing only partially | `Auterion/px4-ros2-interface-lib` | FM-1…FM-5 measured in SITL, including the ~1.2 s detection window and the FM-2 case where the executor's death is invisible to PX4 with an internal mode active | Low — a documentation issue with numbers attached, and it is directly useful to that library's maintainers |

### Research questions the repository is set up to answer

| # | Question | Status here | What closes it |
|---|---|---|---|
| R1 | Can a formally specified RTA boundary bound an LLM's physical authority on a real autopilot, with a measured latency? | Answered for PX4 SITL: 61 ms p99, AC-31 paired run | Real flight, which the repository correctly refuses to claim |
| R2 | Does a jailbroken model gain physical authority through a typed intent + deterministic compiler? | RQ6b specified, corpus exists, harness exists | A jailbreak corpus run against the compiler — and the interesting result is publishable either way. RoboPAIR reports 100% against LLM-controlled robots; a 0% *physical* breach rate against the same prompts is the strongest single claim available to this project |
| R3 | Is the stop path genuinely model-independent? | **Answered**: AC-29, 24/24 on the stop corpus with 0 model requests, repeats=3 | Nothing — this is already a result and should be stated more loudly than it is |
| R4 | Does Copilot's verifier prove the generated monitors? | Blocked by R-11, toolchain unavailable | A Haskell/LLVM/z3 environment — a pure-infrastructure contribution anyone with the right machine can make |
| R5 | Are DO-365B well-clear thresholds meaningful for small UAS? | Open risk R-5 | Sourced thresholds. This is a literature question, not a coding one, and is the most accessible open item for an outside academic |
| R6 | Does the same switching core hold under orbital dynamics? | AC-47 analytic only; no host, no simulator | A Basilisk ↔ ROS 2 bridge (AC-48). Highest-ceiling open item in the repository |
| R7 | Can F´ be given a latched safe mode with no upstream heritage? | RS-1, specified, no code | Review by someone who has flown one. README §14 already asks for this, correctly |

### Issues to file immediately (the contributor on-ramp)

Label these `good first issue` — each is bounded, does not touch the arbiter, and produces a visible
result:

1. Add `requirements.txt` and a no-Docker quickstart for `mission/` and `space/` (P0-3, P1-1)
2. Add a single-utterance CLI entry point to the mission compiler (P1-1)
3. Add an Ollama provider to `scripts/llm/provider.py` (P1-4)
4. Add an OpenAI-compatible provider with a configurable base URL (P1-4)
5. Add an Anthropic provider (P1-4)
6. Plot the latency distribution from `docs/evidence/batch_latency/` (P2-3)
7. Plot the RTA-on vs RTA-off geofence trace from the paired run (P2-3)
8. Fix `CITATION.cff` `repository-code` and complete the metadata (P0-2)
9. Resize the hero image (P1-3)
10. Add a `pt-BR` / `en` language-pack test case (ADR 0008 — reachable for a non-roboticist)

---

## 7 · Where to place it, worldwide

Ordered by expected return. Each venue wants a different framing of the same repository; the
framings are given because using the wrong one is how a good project gets ignored.

| Venue | Framing to lead with | Notes |
|---|---|---|
| **PX4 Discourse** — the EchoPilot thread in particular | "You asked the community for safety ideas for LLM → PX4. Here is a measured runtime-assurance boundary, and here is what it costs: 61 ms." | The highest-probability first audience. The thread is cited in README §2.2, its author explicitly asked for this, and it is a direct reply rather than an announcement |
| **ROS Discourse** | "Runtime assurance for ROS 2 + PX4: an arbiter as a `ModeExecutor`, with formally generated monitors" | Reaches the ROS 2 safety and aerial working groups |
| **NASA FRET / Ogma / Copilot issue trackers** | U1 and U2 as PRs, not announcements | Contributing upstream is what makes those maintainers cite the project back. This is the highest-leverage action in this entire document |
| **NFM (NASA Formal Methods)** | The preprint, P6 | Already the plan. Correct venue |
| **arXiv cs.RO + cs.SE** | Preprint, cross-listed | Gives everything else something to cite |
| **r/LocalLLaMA**, local-LLM communities | "An LLM flies a drone and physically cannot leave the geofence — here is the boundary, and it runs against Ollama" | Only becomes true after P1-4. Then it is a strong post: this community is large, hostile to hand-waving, and has almost no robotics content with real safety engineering in it |
| **Hacker News** | "Show HN: A measured safety boundary between an LLM and a drone" | One shot. Do not fire it before P0 and P1-1 are closed — the first comment will be "how do I run it" |
| **Awesome lists** | `awesome-ros2`, `awesome-robotics`, `awesome-uav`, `awesome-embodied-ai`, `awesome-formal-methods`, `awesome-llm-robotics` | Cheap, permanent, compounding. Do these the week the repository goes public |
| **ASTM F38 / F3269 community, EASA & ANAC contacts** | "An open reference implementation of the F3269 architecture, with the mapping marked `[REVIEW]` pending the licensed text" | Slow, but R-8 is an open risk and this is how it gets closed — by someone with the standard in hand |
| **Brazilian agricultural-drone and academic networks (ITA, INPE, USP, Embrapa)** | G6: 13,224 registered agricultural drones, ~84% on one closed platform, under RBAC 100 | This is the project's structural advantage and no international venue will surface it. It is also the natural source of a field-trial partner for M12 |

---

## 8 · Recommended order

**Before public** — P0-2 (citation), P0-3 (requirements), P0-5 (`CONTRIBUTING`, `SECURITY`,
`CODE_OF_CONDUCT`, issue templates), P0-4 (CI on the cheap checks), then flip the repository public
and file the ten on-ramp issues.

**First week public** — P1-1 (the 60-second try), P1-2 (split the README), P1-3 (image), P2-4
(`v0.1.0` release, Discussions on), awesome-list PRs, and the PX4 Discourse reply.

**First month** — P1-4 (Ollama and OpenAI-compatible providers, which unblocks external
reproduction of the headline claim), U1 and U4 upstream, P2-3 (the two figures), and the preprint.

The two items with the highest ratio of credibility gained to work required are **U1** — a PR that
puts a PX4 variable database into Ogma itself — and **P1-4** — making the LLM claim reproducible by
anyone with a laptop. Neither touches the arbiter, and both are reachable this month.
