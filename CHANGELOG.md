<!-- SPDX-License-Identifier: Apache-2.0 -->
# Changelog

Guará is a research prototype. What a version means here is narrow and worth stating: a tag
marks a commit at which the acceptance criteria listed as PASS were reproduced by an executed
command, and at which the evidence directories those criteria cite are the ones in the tree. It
is not a stability promise and not a certification.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions are
`MAJOR.MINOR.PATCH`, starting below 1.0 because interfaces change without notice.

## [Unreleased]

### Added
- No-container path: `python3 -m mission.compiler --intent | --stop`, two worked example
  intents under `mission/intents/`, and declared Python dependencies in `requirements.txt`
  and `requirements-dev.txt`.
- LLM providers `ollama` and `openai-compat`, so RQ6a/RQ6b can be reproduced against a local
  open-weight model or any OpenAI-compatible server rather than only a paid hosted instrument.
- Contribution surface: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue forms
  and a pull-request template.
- CI (`.github/workflows/checks.yml`) over the checks that need no PX4 build, plus
  `scripts/check_spdx.py` and `scripts/check_links.py`.
- `scripts/check_site_claims.py`, which fails when the published site stops agreeing with the
  repository: a commit stamp that is not an ancestor of `HEAD`, that differs between pages or
  that lags by more than 25 commits; an acceptance-criteria tally on `site/evidence.html` that
  `docs/milestones/STATUS.md` does not support; an `AC-`, `FM-`, `R-`, `RP-`, `RS-`, `RH-` or
  gap-register identifier cited on a page and absent from the document that owns it; and an
  install path taught on the site that `README.md` §9 has moved off. It runs in the `boundaries`
  job and again in the Pages workflow before anything is published.
- A manual workflow publishing the dev image to GHCR, with a guard refusing to publish an
  image that references NOSA-licensed software.
- Figures drawn from the published evidence by `scripts/plot_evidence.py`.
- The agent pipeline is written down and enforced: `docs/AGENT-PIPELINE.md` describes the
  scope / execute / review stages, `.claude/skills/guara-*` and `.cursor/rules/guara-*.mdc`
  carry the invariants to the two surfaces that load them, and `scripts/check_pipeline.py`
  refuses a surface that has drifted from the tree.
- **The host-free safety kernel and its C ABI** ([ADR 0014](docs/adr/0014-delivery-model.md),
  M18): `core/` builds with plain CMake and no ament, ROS, PX4 or Eigen; `guara/guara.h`
  exposes caller-supplied storage so the kernel allocates nothing and owns no clock;
  `scripts/check_abi.py` gates the exported symbol set and `scripts/core_qa.sh` runs ASan,
  UBSan and clang-tidy. Serves AC-57..AC-62, all `in progress`.
- **The conformance kit** (M19): published decision vectors under `core/conformance/vectors/`
  covering the SPEC §3 transitions, the ADR 0010 gateway rules, the monitor table and the
  geofence channel; a Python reference port written from the SPEC alone and a SIL port through
  the C ABI, both run by `guara ctk run`; `scripts/ctk_mutation.sh` requires the set to detect
  an injected behavioural change. Each report states in its own text that conformance is
  necessary and not sufficient. Serves AC-63..AC-66, all `in progress`.
- **Hermetic setup** (M17): `versions.env` as the single source of every pin, read by the
  Dockerfiles, the lockfile generator and `scripts/check_reproducible.py --pins`; a hash-pinned
  `requirements.lock`; `pyproject.toml` and the `guara` CLI, so the tier-0 path no longer needs
  a clone; `guara doctor` as the workstation preflight; `GUARA_OFFLINE=1`. Serves AC-51, AC-52,
  AC-55, AC-56, all `in progress`.
- **The space untrusted-function contract**
  ([ADR 0015](docs/adr/0015-space-untrusted-function-contract.md)): ADR 0010's seven rules
  instantiated on F´ signals, plus the declared command origin ADR 0010 left open. Grounded in
  `GROUNDING.md` D.9–D.11 against `fprime@7d8f579` — F´ ships an SDLS uplink stage whose default
  decryptor performs no authentication, nothing in the command path authorises a command, and
  `Svc::CmdSplitter` supplies the port shapes for a gate that refuses instead of routing.
- Ten ground-side acceptance criteria, AC-102..AC-111
  ([`docs/PLAN-M17-M28.md`](docs/PLAN-M17-M28.md) §9), and the gap rows that own them: G-Z9..G-Z13
  and a new G-M group for monitors and the specification. None needs hardware, a host, a simulator
  or a network.

### Changed
- The gap register re-owns G-H11, G-H12 and G-H13 from M25 to M9b: none needs hardware, and each
  silently weakens an AC-28 result while open.
- `docs/ROADMAP.md`, `README.md` §11, `docs/milestones/STATUS.md` and
  `docs/operations/README.md` now agree with each other on which milestones are in flight; the
  six threads are listed in one place.
- `docs/SPEC.md` §9 indexes the four risk families (`R-*`, `RP-*`, `RS-*`, `RH-*`) and names the
  document that defines each. Previously the README and the roadmap pointed at two of the four.
- `docs/site` carries a roadmap page: the four tracks, the ordering, Rule O / Rule D / Rule H and
  the gap register, which until now existed only in the repository.
- The site now agrees with the documents it restates. `site/evidence.html` carried the pre-M17
  tracker — 35 PASS, 2 in progress, 18 planned, "AC-1…AC-50 across four threads" — against a
  `STATUS.md` recording 35, 16 and 30 over AC-1…AC-111 and seven threads; `site/contribute.html`
  taught the superseded `python3 -m mission.compiler` entry path after `README.md` §9 and
  `site/index.html` had moved to `pip install -e .`; `site/nomenclature.html`, which declares
  itself normative for the site, defined neither the `RP-*` and `RH-*` risk families nor the gap
  register's `G-S`/`G-K`/`G-M`/`G-H`/`G-Z` rows that the roadmap page had begun to cite.
- `docs/SPEC.md` §9.0 indexed the LLM-embodiment risks as `RP-1..RP-3`;
  `docs/PLAN-M8-M16.md` §6 defines five.

### Changed
- The README is split: related work, architecture, roadmap and licensing move to `docs/`.
- Mascot images sized for the web (2.3 MB to 224 KB).

### Fixed
- The evaluation harness no longer fails on a clean clone when `results/` does not exist.
- `--api-key-env` defaulted to `CURSOR_API_KEY` for every provider, and the run evidence
  recorded that name even for runs that used no credential.
- `CITATION.cff` pointed at a repository name that does not exist, and carried an invalid
  top-level `year` key.
- The README scenario count (twelve; fourteen ship).
- The README's table of contents, deleted by the split that renumbered the sections, and the
  section references the split left behind in the README, `docs/ARCHITECTURE.md`,
  `docs/ROADMAP.md` and `docs/LICENSING.md`.
- The `cpp` CI job reported success while building and testing nothing, because `colcon`
  only warns when `--packages-select` names an undiscovered package and `colcon test-result`
  exits 0 on zero tests. It now asserts that both packages built and that tests ran.

---

## How to cut a release

1. Confirm the tree is clean and every check passes:
   ```bash
   python3 -m pytest scripts/tests -q
   python3 scripts/check_license_isolation.py
   python3 scripts/check_spdx.py
   python3 scripts/check_links.py
   ```
2. Move the `Unreleased` entries under a new version heading with the date.
3. Set `commit:` in `CITATION.cff` to the release commit, and add `version:` and
   `date-released:`.
4. Tag and push, then write the release notes from the section you just closed.

State in the notes which acceptance criteria were PASS at that commit, and name the evidence
directory behind each quantitative claim. Never restate a number in release notes without the
run directory that produced it — the same rule as everywhere else in this repository.
