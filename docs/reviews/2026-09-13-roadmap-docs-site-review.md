# Review — the roadmap, the gap register, the documentation set and the site

Date: 2026-09-13 · Reviewed commit: `2e6f80e` (branch `feat/2026-09-13-agent-pipeline`) ·
Scope: `docs/ROADMAP.md`, `docs/PLAN-M17-M28.md` §1 and §7, `docs/milestones/STATUS.md`,
`README.md` §8–§11, `CHANGELOG.md`, and the six pages under `site/`. Nothing here re-scores an
acceptance criterion or touches kernel code.

Method: read the four planning documents against each other and against the tree; rendered every
site page to text and compared its commands and its claims with the README and with the gap
register; ran `scripts/check_links.py` (PASS, 202 links) and `scripts/check_site_links.py` (PASS,
6 pages); counted the corpus, the scenarios and the evidence directories that the numbers on the
site depend on; resolved the commit stamps printed on each page against `git log`.

Findings are graded **C** (a contradiction between two published documents — a reader is actively
misled), **G** (a hole in the gap register itself, i.e. a gap the register does not own) and
**S** (a site defect). Severity within each grade is the order given.

---

## 1 · Verdict

The gap register in [`docs/PLAN-M17-M28.md`](../PLAN-M17-M28.md) §1 is the strongest planning
artefact this project has produced. Every row is a real absence rather than a wish, each has
exactly one owning milestone, §8 closes the loop from row to milestone to AC to ADR, and §7 RH-9
pre-empts the specific overclaim ("measured worst observed" read as a bound) that a reviewer would
attack first. Rule D and Rule H are the correct gates and they are stated before they are needed.
The related-work coverage is current against real repositories and cites primary sources, not
summaries. None of that needs changing.

What does not hold up is **status coherence**. Between `22ab122` and `2e6f80e` — 78 commits — the
project built the host-free kernel, the C ABI, the conformance kit, the tier-0 package, the
lockfile and the doctor, and recorded 16 acceptance criteria as in progress against them. Four of
the five documents a reader would consult to learn that still describe the project as it was
before that work started. The roadmap in particular says the opposite of the truth: it files the
work in flight under *Proposed* and names as *next* work that has been displaced.

The second finding is narrower and more consequential for the stated goal. The air side of
"secure LLM navigation" is a complete chain — closed schema, deterministic compiler, named
refusals, stop grammar outside the model, gateway contract, transport authentication scheduled,
adversarial corpus, paired RTA on/off evidence. The space side reuses the *architecture* of that
chain but not its *security artefacts*: there is no space adversarial corpus, no gateway contract
instantiated for F´, and no authentication on the path that submits a space intent. AC-50 is
written as though the first of those exists. The gap register owns none of the three. §3 below
proposes four rows (G-Z9, G-Z10, G-Z11, and a re-owner of G-H13) that close them, all ground-side
and none blocked on hardware.

The site is well built and honest, and it has no roadmap. A visitor cannot learn what is next,
what is open, or that a gap register exists.

---

## 2 · C — contradictions between published documents

### C-1 · The roadmap files the work in flight under "Proposed", and names displaced work as "next"

[`docs/ROADMAP.md:42`](../ROADMAP.md) heads M17–M28 "Proposed — delivery and real hardware", and
the *In progress* table above it ends at [`:28`](../ROADMAP.md) with `P5–P7 … | next`. Against
the tree: `core/` is a plain-CMake library with a C ABI and a conformance kit, `guara/ctk/` runs
two ports, `pyproject.toml` and `requirements.lock` exist, `guara doctor` is a CI step, the
`core` job builds on three operating systems, and
[`docs/reviews/2026-09-13-m17-m19-kernel-review.md`](2026-09-13-m17-m19-kernel-review.md) reviewed
110 files of it. `STATUS.md` marks AC-51..AC-66 in progress.

The roadmap is the one document whose entire job is "what is happening now". It is wrong about
that, in the direction that understates delivered work — the opposite of the failure mode this
project guards against, but a defect of the same kind.

**Fix.** Move M17, M18 and M19 into *In progress* with their AC states as `STATUS.md` records
them; leave M20–M28 under *Proposed*; re-state P5–P7 with their real position rather than "next".

### C-2 · `STATUS.md` contradicts its own table

[`docs/milestones/STATUS.md:102`](../milestones/STATUS.md) closes with "M18–M28 (AC-57..AC-101)
… are not yet inventoried here as in-progress work". Ten rows immediately above it inventory
AC-57..AC-66 as in-progress work.

**Fix.** Narrow the sentence to M20–M28 (AC-67..AC-101).

### C-3 · README §11 describes a project two tracks out of date

[`README.md:454`](../../README.md): "M1–M8 are done, M9 and M13c are in progress, and the F´ host
and the orbital batch are planned." The S and K tracks are absent, although §9 of the same README
already documents `pip install -e .`, `guara doctor`, `cmake -S core` and `guara ctk run`. One
README states in §9 what it denies in §11.

[`README.md:459`](../../README.md) and [`ROADMAP.md:63`](../ROADMAP.md) both route blocking risks
to `SPEC.md` §9 and `SPACE-AUTONOMY.md` §8 only, so RH-1..RH-9 — including RH-5 (one maintainer
cannot run a release programme and a flight-test programme at once) and RH-7 (real flights involve
real people) — are unreachable from either entry point. The risk register is now split across
three documents with no index.

**Fix.** Rewrite §11 against `STATUS.md`; add `PLAN-M17-M28.md` §7 to both risk sentences; or
better, give the four risk families (R-\*, RP-\*, RS-\*, RH-\*) one index table in `SPEC.md` §9
and point everything at it.

### C-4 · The plan's own status line stops at M17

[`docs/PLAN-M17-M28.md:3`](../PLAN-M17-M28.md): "Status: proposed; M17 started (pin-drift check,
hash lock, doctor)". M18's kernel and C ABI and M19's kit and two ports have landed since.

**Fix.** Extend the line; keep the version bump, since the gap rows themselves have not changed.

### C-5 · `CHANGELOG.md` has no record of M17–M19

The `[Unreleased]` section names the no-container path, the providers, the contribution surface,
CI, the GHCR workflow, the figures and the agent pipeline. It says nothing about the host-free
kernel, the C ABI, the conformance kit and its vectors, `pyproject.toml`, the hash-pinned lock,
`guara doctor` or the `guara` CLI — approximately 12.7 kLOC, and the only part of this repository
a third party will consume as an artefact.

**Fix.** One `### Added` block for the kernel and the kit, one for the tier-0 package and the
hermetic setup, each naming the ACs it serves and the ADR it implements (0014).

### C-6 · `operations/README.md` §1 predates the S and K tracks

[`docs/operations/README.md`](../operations/README.md) §1 names threads A, B and C only, and
routes the reader to `PLAN-M8-M16.md` for the thread list. `STATUS.md` defines six threads.
The scope map is the document CLAUDE.md makes authoritative for scope; it should not be the last
one updated.

---

## 3 · G — what the gap register does not own

The register claims completeness: "This is the answer to 'cover all gaps': the list is the
contract" ([`PLAN-M17-M28.md:22`](../PLAN-M17-M28.md)). Four rows are missing, three of them on
the axis the project most wants to strengthen.

### G-1 · There is no space adversarial corpus, and AC-50 assumes one

[`PLAN-M8-M16.md:203`](../PLAN-M8-M16.md) scopes M16 as "the RQ6b corpus re-run against the space
intent schema", and [`:208`](../PLAN-M8-M16.md) AC-50 requires zero adversarial utterances to
produce a sequence that passes both sequencer validation and the gate. The only corpus in the tree
is `mission/corpus/*.yaml` — 18 adversarial cases, all air: fields, spraying, GSD, ceiling,
geofence, battery. Not one of them can exercise the space attack surface, because the vocabulary
does not contain it: a slew whose path crosses a sun or earth keep-out while both endpoints are
legal, a request to release the safe-mode latch, a sequence whose members are individually valid
and whose aggregate exhausts momentum or power margin, a command issued to exploit the gap between
ground-station passes, an eclipse-timed pointing request.

"Re-run the air corpus against the space schema" cannot produce evidence for AC-50: every case
will be rejected at the schema, for the wrong reason, and the run will look like a pass.

No G-Z row owns this. It is also the cheapest high-value work left in track Z — a YAML file and a
red-teaming afternoon, no simulator, no target, no F´ host — and therefore the one item in the
space thread a contributor can finish today.

**Proposed row.** `G-Z9 | The adversarial corpus is air-only; the space intent vocabulary has no
adversarial cases at all, so AC-50 has nothing to run | M16` — with its own AC requiring the space
cases to exercise every verb in `space/schema/space_intent.schema.json` and every channel of
ADR 0012, and requiring the rejection to be attributed to a named check rather than to the schema.

### G-2 · No authentication on the path that submits a space intent

G-Z3 authenticates one thing: release of the safe-mode latch (AC-98). Nothing states who may
submit an intent or a sequence in the first place — the direct sibling of FM-12 and M9b on the air
side. [`docs/research/SPACE-AUTONOMY.md:62`](../research/SPACE-AUTONOMY.md) has already identified
the choke point (`Svc::CmdDispatcher`, `Svc::CmdSplitter`, `Svc::Seq`, `Svc::SeqDispatcher`, "the
analogue of `GuaraCfGateway`"), so this is a gap in the register, not in the research.

The asymmetry is hard to defend as written: the air domain treats an unauthenticated command path
as an accepted, published limitation with a milestone against it, while the space domain — where
the operator is minutes away at best — does not name it.

**Proposed row.** `G-Z10 | No authenticated origin for a space intent or a sequence: only the
safe-mode release is covered (G-Z3), and the command path that reaches the sequencer is
unconstrained | M27` — its AC the space analogue of AC-32, not of AC-98.

### G-3 · ADR 0010's gateway contract has no space instantiation

Rule T ([`PLAN-M8-M16.md`](../PLAN-M8-M16.md) §1) asserts one chain in both domains: intent →
compiler → validated plan → trusted executor → **gateway** → RTA → recovery. The gateway is
specified once, for air, in ADR 0010: freshness on the receiver's clock, envelope clamp, shadow
fence check, and rules 1–6. ADR 0012 maps channels and the recovery function for space and does
not instantiate those rules. So in the space domain the chain Rule T claims has a specified
element missing at exactly the trust boundary.

**Proposed row.** `G-Z11 | ADR 0010's gateway rules are air-shaped and have no space
instantiation: no freshness source, no envelope clamp on commanded rates, no shadow keep-out check
on a proposed slew, no stated rule for what the gate does while the arbiter state is not CF |
M26` — resolved either by a space section in ADR 0010 or by ADR 0015.

### G-4 · Two rows are owned by the wrong milestone, and the wrong one is late

[`PLAN-M17-M28.md:67`](../PLAN-M17-M28.md) assigns **G-H13** — the corpus was written by the
author of the compiler, never externally reviewed, never coverage-measured (RP-1) — to **M25**,
the flight campaign, at the end of track H behind HITL, the companion, instrumentation and the
dossier. The weakness needs no hardware, and while it is open every AC-28 result understates
exposure by an unknown amount. `site/contribute.html` already advertises it as the approachable
contribution. It belongs at M9/M9b, where the harness it tests already runs.

[`:66`](../PLAN-M17-M28.md) **G-H12** — request budget, hard timeout, watchdog on the model
process, defined degraded mode — is likewise pure software discipline held at M25, although
`scripts/llm/eval.py` and the provider abstraction exist now and a stale plan reaching the
executor is a *today* failure mode, not a flight-day one.

[`:65`](../PLAN-M17-M28.md) **G-H11** names M9b and AC-32/AC-33 in its text and then records M25
as owner, breaking the register's own one-owner rule. M25 *gates on* the row; M9b *owns* it.

**Fix.** G-H13 → M9b (or M9), G-H12 → M9b, G-H11 owner → M9b with M25 recorded as the gate.
This is the change that most improves the register's fitness for the project's stated goal: all
three rows are the security discipline around an LLM in the loop, and all three are currently
scheduled after the flights that would depend on them.

---

## 4 · S — the site

### S-1 · There is no roadmap on the site, and the gap register is invisible

Six pages: Overview, Architecture, Integrate, Evidence, Nomenclature, Contribute. The word
*roadmap* appears once in the rendered text of the whole site, as a table cell in
`nomenclature.html` defining the symbol `M-n`. `docs/ROADMAP.md`, `docs/PLAN-M8-M16.md`,
`docs/PLAN-M17-M28.md` and `docs/milestones/STATUS.md` are linked from no page but that one
(`STATUS.md` is reachable from `evidence.html:300`).

A visitor can therefore learn what has been measured and what the limits are, and cannot learn
what happens next. For a single-author project seeking review time, hardware and standards
access, the gap register is the most persuasive document in the repository: 37 rows, each a named
absence with an owner, published before anyone asked. Not surfacing it is the largest missed
opportunity on the site.

**Fix.** A seventh page — *Roadmap* in the navigation, `GUARA-SITE-06` — carrying the four
tracks, the ordering diagram from §2, Rule O / Rule D / Rule H, the gap register as its central
table grouped G-S / G-K / G-H / G-Z with the owning milestone per row, and the four risk families
in one table. The content already exists; nothing needs to be written from scratch.

### S-2 · The site's tier-0 path is the pre-M17 one, and disagrees with the README

`site/index.html:351` teaches `pip install -r requirements.txt` and `python3 -m mission.compiler`.
README §9 leads with `pip install -e .`, `guara doctor` and `guara compile` (G-S3, AC-51), and
`site/integrate.html:665` already uses `pip install -e .` and `guara ctk run`. Two published entry
paths, one project, and the one on the landing page is the older one.

`site/contribute.html:321` instructs `docker pull ghcr.io/aton-of-data/guara-dev:m1` as the way
into the full bench. G-S4 states that the GHCR publish is manual and amd64-only, "so there is no
reliable pull path and none at all for arm64". The site promises what the register says does not
reliably exist — the one class of statement this project treats as a defect of crash severity.

**Fix.** Bring `index.html` to the README's block; on `contribute.html` either mark the pull path
as amd64-only and possibly stale, or point at the local build until AC-53 passes.

### S-3 · Open work is the M8–M16 set only

`index.html` §Open work and `contribute.html` §1 list R-11, R-5, R-7, FM-12, R-8, AC-48, RS-1 and
RQ6b. Every item is from the previous plan. Absent, and each stronger as a recruiting ask than
several that are listed:

- **AC-65** — write an implementation of the switching core from `docs/SPEC.md` and the header
  alone, by a path independent of `core/`, and find what the SPEC fails to say. No hardware, no
  container, no ROS; it is the single item that would most improve the SPEC, and ADR 0014
  decision 3 makes ABI v1 provisional until it exists. This is the best open item in the project
  and it appears nowhere on the site.
- **G-Z9** (§3 above) — the space adversarial corpus, a YAML file.
- **AC-71** — the Humble → Jazzy port, ahead of the 2027-05 EOL (RH-1).
- **AC-60 / AC-76 on arm** — anyone with a Pi 5 or an Orin Nano can produce the first non-x86
  timing numbers this project has.

**Fix.** Add those four; keep the existing eight; source the section from the gap register so it
cannot drift again.

### S-4 · The commit stamps are stale, and nothing checks them

Five pages print `Describes commit 75f5760` (`docs/readme: link the project site`, 2026-09-12,
78 commits behind `HEAD`); `integrate.html:98` prints `9d61cf7`. Under this project's own evidence
discipline the stamp is a load-bearing claim about which tree the page describes, and
`scripts/check_site_links.py` verifies links only.

**Fix.** Extend `check_site_links.py`: every stamp must be an ancestor of `HEAD`, all pages must
carry the same stamp unless deliberately divergent, and a distance beyond an agreed number of
commits fails rather than warns.

---

## 5 · What is correct and should not be touched

- The gap register's structure: one owner per row, §8 traceability, and rows written as absences
  rather than intentions.
- Rule D and Rule H, and the SITL → HITL → bench → tether → low-altitude → operational ordering
  with each step's evidence bundle a precondition of the next.
- RH-9 and AC-60's "measured worst observed, not a bound" phrasing, and AC-66 requiring the
  conformance report to state its own insufficiency in its own text.
- The limits sections on `index.html` and `evidence.html`, including the published account of the
  review that invalidated twelve of this project's own rows.
- `RELATED-WORK.md` §2.2 and §2.3: current, primary-sourced, and honest about what the surveyed
  work does and does not claim.
- Every number the site quotes checks out against the tree: 14 scenarios, 30-run batch, p99
  61 ms, 0.000 m / 47.178 m paired, 20 published evidence directories.

## 6 · Recommended order

1. C-1, C-2, C-3, C-4 — four documents, one pass, no new content: make the published status match
   `STATUS.md`.
2. G-4 — re-own G-H11, G-H12, G-H13 to M9b. Cheapest change with the largest effect on the LLM
   security posture.
3. G-1 — add G-Z9 and its AC; write the space adversarial corpus.
4. S-1 — the roadmap page, sourced from the gap register.
5. S-2, S-4 — align the tier-0 path, gate the commit stamps in CI.
6. G-2, G-3 — G-Z10 and G-Z11, and the decision of whether the space gateway is an ADR 0010
   section or ADR 0015.
7. C-5, C-6, S-3 — the changelog block, the scope map's thread list, the open-work list.
