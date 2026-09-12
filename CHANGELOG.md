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
- A manual workflow publishing the dev image to GHCR, with a guard refusing to publish an
  image that references NOSA-licensed software.
- Figures drawn from the published evidence by `scripts/plot_evidence.py`.

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
