# Guará — plan M17–M28: delivery, and the path to real hardware

Version: 0.1 (2026-09-13) · Status: proposed; no AC below has code

This plan continues `docs/PLAN-M8-M16.md` past the point where Guará stops being a
repository you clone and becomes something a third party installs, and past the point where
every number comes from a simulator. Its packaging decision is
[ADR 0014](adr/0014-delivery-model.md); the operation-level scope map remains
`docs/operations/README.md`; the acceptance-criteria inventory remains
`docs/milestones/STATUS.md`.

Conventions are SPEC's: **[HYPOTHESIS]**, **[REVIEW]**, **[UNKNOWN]**, **[PARAMETER TBD]**.
An acceptance criterion is PASS only with an executed command and an output excerpt in a
milestone report. Numbers come only from `results/` via `scripts/aggregate.py` (CLAUDE.md).

Acceptance criteria continue the single project sequence: AC-51 onward.

---

## 1. The gap register

What is missing today, grouped, each row owned by exactly one milestone. This is the answer
to "cover all gaps": the list is the contract, the milestones are the schedule.

### G-S · setup and reproducibility

| # | Gap | Owner |
|---|---|---|
| G-S1 | Python dependencies are floors (`PyYAML>=6.0`), not pins; no lockfile, no hashes — two machines resolve two environments | M17 |
| G-S2 | Pins are duplicated between `requirements*.txt` and `docker/Dockerfile` (the Dockerfile says so in a comment); nothing detects drift | M17 |
| G-S3 | No `pyproject.toml`; `mission/`, `space/` and `scripts/` are not installable, so the tier-0 path only works from a clone | M17, M20 |
| G-S4 | The dev image is built locally and amd64-only; first use compiles PX4 from source; the GHCR publish is manual, so there is no reliable pull path and none at all for arm64 | M17 |
| G-S5 | No preflight for the *workstation*: nothing checks arch, Docker, disk, RAM, clock skew, image digest or pinned clone commits before a run fails halfway | M17 |
| G-S6 | No offline path: `fetch_third_party.sh` and the image build both need the network, with no documented cached mode | M17 |
| G-S7 | CI tests only the Python layer. Nothing builds the C++ core on a pull request, so the arbiter can break silently | M17 |
| G-S8 | ROS 2 Humble is EOL 2027-05, inside this plan's horizon, and no migration is scheduled | M20 |

### G-K · the kernel and its delivery

| # | Gap | Owner |
|---|---|---|
| G-K1 | `guara_rta_core` is ROS-free in its code but ament-packaged in its build; no non-ROS host can consume it | M18 |
| G-K2 | No C ABI, no versioned interface, no storage-supplied construction — the shapes a flight-software integrator expects | M18 |
| G-K3 | No semantic version, no ABI gate, no behavioural-compatibility gate between releases | M18, M20 |
| G-K4 | No worst-case evidence: "bounded operations per tick" is asserted by construction and by a no-alloc test, never measured on a target | M18, M22 |
| G-K5 | No conformance vectors an integrator can run; AC-39/AC-40 promise host equivalence as an internal claim with no shippable artifact | M19 |
| G-K6 | No independent implementation has ever read the spec, so the spec's ambiguities are unknown | M19 |
| G-K7 | No binary distribution on any channel: no apt, no wheel, no F´ library, no multi-arch image, no SBOM, no provenance | M20 |
| G-K8 | Runtime configuration (`rta_params.yaml`) is loaded without a schema check or a hash recorded against the running core | M18, M23 |

### G-H · air, real hardware

| # | Gap | Owner |
|---|---|---|
| G-H1 | No hardware-in-the-loop stage at all: the step from SITL to flight is a cliff | M21 |
| G-H2 | Every latency number is x86 SITL; nothing has been measured on an arm companion under a general-purpose kernel | M21, M22 |
| G-H3 | No companion target: no arm64 image, no systemd bring-up, no scheduling policy, no CPU/memory isolation between the arbiter and the CF | M22 |
| G-H4 | No dead-man between companion and FCU on real hardware; PX4's offboard-loss failsafe is neither configured nor tested as a criterion | M22 |
| G-H5 | No black box: no single bundle correlating ULog, ROS data and RTA events on one timebase, and no measured clock offset between them | M23 |
| G-H6 | No arming gate: nothing refuses to fly when the loaded geofence, parameters, monitor build or core version differ from the declared set | M23 |
| G-H7 | The operator cannot see the RTA: no GCS annunciation of a switch or its cause channel | M23 |
| G-H8 | The override matrix (RC loss, GCS loss, companion loss, kill switch, pilot mode change, low battery) is untested on hardware | M23 |
| G-H9 | No operational safety dossier: no ConOps, no system-level FHA/FMEA folding in the FM-\* set, no SORA/OSO mapping, no ANAC RBAC-E 94 or EASA position, no explicit DO-178C/ARP4754A **non**-claim map | M24 |
| G-H10 | The hardware run has no evidence contract: aircraft, pilot, site, weather, battery, waiver and firmware hash are not required fields anywhere | M23, M25 |
| G-H11 | Transport authentication (M9b, AC-32/AC-33) is open, and it is a hard precondition for any LLM-driven CF on a real vehicle | M25 |
| G-H12 | No model-side runtime discipline on target: no request budget, no timeout, no watchdog on the model process, no defined degraded mode when it is unreachable | M25 |
| G-H13 | The adversarial corpus was written by the author of the compiler (RP-1) and has never been externally reviewed or coverage-measured | M25 |

### G-Z · space, real hardware

| # | Gap | Owner |
|---|---|---|
| G-Z1 | The F´ host is unextracted and the safe mode unwritten (M13, M14) — everything downstream is blocked on them | M13/M14, M26 |
| G-Z2 | No cross-compilation and no processor-in-the-loop: nothing has run on an OBC-class board | M26 |
| G-Z3 | "Released only by ground command" is a sentence, not an interface: no authenticated telecommand path, and no rejection test for a non-ground release | M27 |
| G-Z4 | No ECSS/PUS framing: the channels and events are not expressed as on-board monitoring, events or event-action definitions an operator would recognise | M27 |
| G-Z5 | No time system: TAI/UTC/spacecraft elapsed time undeclared, clock drift unbudgeted | M27 |
| G-Z6 | No orbital simulator is pinned in `third_party/VERSIONS.md`, so AC-48 has nothing to run against | M27 |
| G-Z7 | Only the analytic keep-out channel exists; `power_margin`, `momentum`, `inputs_valid`, `requirements` (ADR 0012) have no implementation | M26 |
| G-Z8 | No ECSS-E-ST-40C / Q-ST-80C non-claim map, the space sibling of G-H9 | M27 |

---

## 2. Ordering and two new rules

```
M17 (setup)  ─────────────────────────────────────────────────────────►  continuous
     │
     └─► M18 core ─► M19 conformance ─► M20 packages
                             │                │
                             │                ├─► air:   M21 HITL ─► M22 companion ─► M23 instrumentation ─► M24 dossier ─► M25 LLM flight
                             │                │
                             └────────────────┴─► space: (M13 ─► M14 ─► M15) ─► M26 target ─► M27 operations ─► M28 campaign
```

**Rule O** (from `PLAN-M8-M16.md`) is unchanged and already satisfied.

**Rule D (delivery).** Nothing is published whose conformance report is missing or failing,
and no published artifact claims safety of itself (ADR 0014 decisions 1 and 4). A release
without an SBOM, a provenance attestation and a licence-boundary check does not happen.

**Rule H (hardware gate).** A hardware milestone does not start until the same scenario
passes in SITL *and* in HITL, in that order, and no flight with a model in the loop occurs
before AC-32 and AC-33 pass on the same configuration that will fly. The order is
SITL → HITL → bench → tether → low-altitude VLOS → operational VLOS, and each step's
evidence bundle is a precondition of the next.

---

## 3. Track S — setup that works on any machine

### M17 — hermetic setup and one command

Four install tiers, each independently verified, so a newcomer picks the smallest one that
answers their question:

| Tier | What runs | Needs |
|---|---|---|
| T0 | mission and space compilers, corpus, CTK runner, `guara` CLI | `pip install guara` (M20); today `pip install -r requirements.txt` |
| T1 | the C++ core and its unit tests | a C++17 compiler and CMake — no ROS, no PX4, no Docker (new in M18) |
| T2 | SITL scenarios, batches, monitor generation | Docker, a pulled multi-arch image |
| T3 | HITL and vehicle | tier 2 plus hardware (M21+) |

Deliverables: `versions.env` as the single source of every pin, read by the Dockerfiles, the
lockfile generator and `check_reproducible.py`; `pyproject.toml` with a hash-pinned
`requirements.lock`; `guara doctor`; a devcontainer; a multi-arch published image; a CI job
that builds and tests the core with no ROS, PX4 or Docker.

| AC | Criterion (passes if…) | Verification command |
|---|---|---|
| AC-51 | On a clean machine on Linux, macOS and Windows/WSL, tier 0 installs and `guara doctor` exits 0, printing the resolved pins, the platform and the tier reached | `pip install -e . && guara doctor` |
| AC-52 | Dependencies are hash-pinned and reproduce byte-identically; a drift between `versions.env` and any Dockerfile `ARG` or requirements pin fails CI | `pip install --require-hashes -r requirements.lock && python3 scripts/check_reproducible.py --pins` |
| AC-53 | The dev image pulls for `linux/amd64` and `linux/arm64`, and a scenario runs from the pulled digest with no PX4 source build; the digest is recorded in the run contract | `docker pull ghcr.io/aton-of-data/guara-dev:<tag> && ./scripts/sitl_run.sh --scenario hover --seed 42 --headless` |
| AC-54 | Cold clone → first green SITL scenario is measured on a declared reference machine and recorded (a measured number, never an asserted one) | `./scripts/bench_setup.sh && python3 scripts/check_ac.py AC-54 results/latest_setup` |
| AC-55 | CI builds and unit-tests `guara-core` on Ubuntu, macOS and Windows with no ROS, no PX4 and no Docker | the `core` job in `.github/workflows/checks.yml` |
| AC-56 | With the image and the pinned clones already cached, the whole tier-2 path runs with the network disabled | `GUARA_OFFLINE=1 ./scripts/dev.sh colcon test --packages-select guara_rta` |

---

## 4. Track K — the kernel, the proof, the packages

### M18 — `guara-core`: the host-free safety kernel

Re-scoped from M13's extraction half (ADR 0014 consequence 1) and ordered before the F´
deployment, because F´ needs exactly this artifact.

Deliverables: `core/` as a plain-CMake library with no ament dependency; a C ABI
(`guara/guara.h`) with caller-supplied storage — `guara_core_storage_size()` plus
`guara_core_init(void *storage, size_t n, const guara_params *)` — so the kernel allocates
nothing and owns no clock; a coding-subset statement [REVIEW]; semantic versioning with an
ABI version string; a configuration loader that validates against a schema and records the
parameter-set hash alongside the core version.

| AC | Criterion | Verification command |
|---|---|---|
| AC-57 | `guara-core` configures, builds and tests with plain CMake and `-Wall -Wextra -Wpedantic -Werror`, with no ROS, ament, PX4 or Eigen present, and installs a package config an out-of-tree project consumes | `cmake -S core -B build/core && cmake --build build/core && ctest --test-dir build/core` then `cmake -S core/examples/consumer -B build/consumer` |
| AC-58 | The existing PX4 unit criteria (AC-4, AC-5, AC-6, AC-12, AC-13, AC-21) pass against the extracted core **with no edits to the test files** (this is the former AC-39, re-pointed at M18) | `./scripts/dev.sh colcon test --packages-select guara_rta --ctest-args -R 'decision_core\|hysteresis\|latch\|gateway'` |
| AC-59 | The C ABI performs no dynamic allocation and no libc I/O after init: verified through the ABI by the no-alloc harness and by linking the runner against a freestanding stub that traps `malloc`, `free` and `write` | `ctest --test-dir build/core -R 'abi_no_alloc\|abi_freestanding'` |
| AC-60 | Worst observed operation count and execution time per step over the whole vector suite are recorded, on x86 and on the arm64 target, with the bound stated as measured — not proven (G-K4 stays open until a WCET tool is used) | `guara-ctk bench --vectors core/conformance/vectors && python3 scripts/check_ac.py AC-60 results/latest_bench` |
| AC-61 | A release fails if the exported symbol set changes, or any golden decision changes, without the corresponding version bump | `python3 scripts/check_abi.py --baseline <last-tag>` |
| AC-62 | clang-tidy, UBSan and ASan are clean over the vector suite, and branch coverage of `core/` is at or above [PARAMETER TBD] | `./scripts/core_qa.sh` |

### M19 — `guara-ctk`: the conformance kit

The artifact nobody has published for ASTM F3269, and the one that turns "the two hosts
agree" from a claim into something a third party runs.

Deliverables: golden input→decision vectors covering the SPEC §3 transitions, the hysteresis
and dwell rules, the latch policy, the monitor table, the geofence channel and every gateway
rule of ADR 0010; a portable runner driving any port through the C ABI or a thin shim; a
signed report format; a deliberately independent Python reimplementation written from the
SPEC alone, to find out what the SPEC fails to say.

| AC | Criterion | Verification command |
|---|---|---|
| AC-63 | The vector set exercises every transition of SPEC §3 and every gateway rule of ADR 0010; branch coverage of the decision core *by the vectors alone* is at or above [PARAMETER TBD] | `guara-ctk coverage --vectors core/conformance/vectors` |
| AC-64 | `guara-ctk run` yields identical verdicts across the ROS 2, F´, SIL and Python ports; a single injected behavioural mutation in any port is detected by the kit | `guara-ctk run --port ros2 --port sil --port python && ./scripts/ctk_mutation.sh` |
| AC-65 | An implementation written from `docs/SPEC.md` and the header alone, by a path independent of `core/`, passes the kit; every SPEC ambiguity found while writing it is filed and resolved in the SPEC | `guara-ctk run --port reference-python` |
| AC-66 | Each run emits a report naming core version, ABI version, port, host, architecture, vector-set hash and result, and the report states in its own text that conformance is necessary and not sufficient (ADR 0014 decision 4) | `guara-ctk run --port ros2 --report results/latest_ctk && python3 scripts/check_ac.py AC-66 results/latest_ctk` |

### M20 — the published artifacts

Deliverables: `guara_rta`, `guara_msgs`, `guara_geofence` binary-released for ROS 2 Humble
(D2); `guara-fprime` as an F´ library with `library.cmake` and an fppm manifest (D5); the
`guara` wheel (T0); the `guara-companion` multi-arch OCI image (D3); SBOM and provenance on
every artifact; the Humble→Jazzy migration.

| AC | Criterion | Verification command |
|---|---|---|
| AC-67 | On a clean Ubuntu 22.04, installing the released ROS 2 packages brings the arbiter up and passes the kit, with no source build | `apt install ros-humble-guara-rta && guara-ctk run --port ros2` |
| AC-68 | An out-of-tree F´ deployment adds Guará with one `add_fprime_subdirectory` (or one fppm install), builds, and passes the kit | `./scripts/fprime.sh test --target conformance` |
| AC-69 | `pip install guara` provides the compilers, the CTK runner and the CLI, and the README's 60-second path runs from the wheel in a fresh virtualenv | `pip install guara && guara compile --intent mission/intents/survey_north_3.json` |
| AC-70 | Every published artifact carries an SPDX SBOM and a provenance attestation, and the release job refuses to publish anything that embeds NOSA-licensed code (ADR 0003) | the `release` job; `python3 scripts/check_license_isolation.py --artifacts dist/` |
| AC-71 | The ROS 2 packages build and pass the kit on Jazzy before Humble's EOL (2027-05), or a dated decision to accept the EOL risk is recorded in this plan | `guara-ctk run --port ros2 --distro jazzy` |

---

## 5. Track H — air, on real hardware

### M21 — hardware in the loop

A real flight controller, PX4 in HIL against the simulator, the existing scenarios re-run.
Nothing new is claimed here; the point is to discover what SITL was hiding before anything
leaves the bench.

| AC | Criterion | Verification command |
|---|---|---|
| AC-72 | Every SITL scenario that carries an AC re-runs in HITL at the same seed with the same verdict; each divergence is enumerated with its cause, and none is left unexplained | `./scripts/hitl_run.sh --scenario <name> --seed 42 && python3 scripts/check_ac.py AC-72 results/latest_hitl` |
| AC-73 | The decision-path latency is measured across the real link (p50/p99 per stage) and compared with the SITL budget of AC-18; the difference is reported in the milestone, not absorbed | `./scripts/hitl_batch.sh --runs 30 && python3 scripts/aggregate.py results/batch_hitl` |
| AC-74 | The FCU firmware hash, board id, parameter set and link configuration are required fields of the HITL run contract; a run whose read-back parameters drift from the declared set fails the check | `python3 scripts/check_run_contract.py --profile hitl results/latest_hitl` |

### M22 — the companion computer

A documented generic arm64 board is the reference target (ADR 0014 decision 7); the class is
a Raspberry Pi 5 or Jetson Orin Nano [PARAMETER TBD, decided in the milestone with the
measurement that decided it].

| AC | Criterion | Verification command |
|---|---|---|
| AC-75 | From power-on, the target reaches an armed-capable RTA within [PARAMETER TBD] s as a systemd unit, with no interactive step and no login | `guara preflight --target <host> && python3 scripts/check_ac.py AC-75 results/latest_boot` |
| AC-76 | Arbiter tick jitter is measured on target over at least one hour under representative load: p99 and maximum, with scheduling policy, priority, CPU isolation and memory locking recorded; deadline misses are zero or reported with their cause | `./scripts/target_jitter.sh --hours 1 && python3 scripts/check_ac.py AC-76 results/latest_jitter` |
| AC-77 | The CF (including any model client) runs in a cgroup that cannot starve the arbiter: a stress test saturating CPU, memory and I/O in the CF cgroup leaves AC-76's deadline-miss count unchanged | `./scripts/target_stress.sh && python3 scripts/check_ac.py AC-77 results/latest_stress` |
| AC-78 | Companion power loss and arbiter process kill on real hardware put PX4 into its configured failsafe within the declared timeout — the hardware analogue of `kill_arbiter_in_cf` | `./scripts/hitl_run.sh --scenario companion_power_loss && python3 scripts/check_ac.py AC-78 results/latest_hitl` |

### M23 — the instrumentation a flight needs

| AC | Criterion | Verification command |
|---|---|---|
| AC-79 | `guara preflight` refuses to arm and names the failing check when any of these differs from the declared set: geofence hash as loaded into PX4, PX4 parameter set, monitor build hash, core version and its CTK report, parameter-set hash, clock synchronisation, battery model | `guara preflight --site mission/site/demo_farm.yaml --expect docs/evidence/<bundle>` |
| AC-80 | Every RTA event is recoverable from one bundle correlating the ULog, the recorded topics and the RTA event log on a single timebase; the offset between the sources is measured and within [PARAMETER TBD] | `guara bundle results/latest && python3 scripts/check_ac.py AC-80 results/latest` |
| AC-81 | An RTA switch is annunciated to the ground station with its cause channel within [PARAMETER TBD] ms and is visible in QGroundControl | `./scripts/hitl_run.sh --scenario monitor_trigger_hold && python3 scripts/check_ac.py AC-81 results/latest_hitl` |
| AC-82 | The override matrix — RC loss, GCS loss, companion loss, kill switch, pilot mode change, low battery — is exercised on hardware, one test per row, and every observed outcome matches the declared one or the row is marked failing | `./scripts/override_matrix.sh && python3 scripts/check_ac.py AC-82 results/latest_matrix` |
| AC-83 | A bundle verifies offline: hashes, versions, the CTK report of the core that flew, and the declared-versus-observed configuration | `guara verify docs/evidence/<bundle>` |

### M24 — the operational safety dossier ([REVIEW] throughout)

ConOps; a system-level FHA and FMEA that folds in the FM-\* set; a SORA / JARUS OSO mapping;
the ANAC RBAC-E 94 position for Brazil and its EASA equivalence; the LGPD data policy; and —
the load-bearing document — a **non-claim map** stating exactly which DO-178C, DO-330 and
ARP4754A objectives are addressed, partially evidenced, or not addressed at all.

| AC | Criterion | Verification command |
|---|---|---|
| AC-84 | Every FM-\* failure mode maps to a mitigation, a monitor or an explicitly accepted risk, and to a test that exercises it; unmapped modes are listed as unmapped | `python3 scripts/check_fmea.py docs/safety/fmea.yaml` |
| AC-85 | The SORA/OSO mapping names, per objective, the artifact that would be offered and its maturity; no objective is marked met without an artifact that exists in the repository | `python3 scripts/check_links.py --profile safety` |
| AC-86 | The non-claim map is published in the README and on the site, and no document, package description or artifact metadata asserts an assurance level or the word "safe" of Guará itself | `python3 scripts/check_claims.py` |

### M25 — the bounded-LLM flight campaign

The goal of `docs/research/LLM-EMBODIMENT.md`, executed. Gated by Rule H and by M9b.

| AC | Criterion | Verification command |
|---|---|---|
| AC-87 | No flight with a model in the loop occurs unless AC-32 and AC-33 are PASS on the same configuration that flies, recorded in the bundle | `python3 scripts/check_run_contract.py --profile flight results/latest_flight` |
| AC-88 | Across the campaign, the number of adversarial utterances producing a flyable plan is 0 (AC-28 on hardware), and every refusal names its checks | `python3 scripts/check_ac.py AC-88 results/campaign_flight` |
| AC-89 | Stop word → recovery function active is measured on hardware with the model process killed (AC-34 on hardware), p50/p99 | `python3 scripts/check_ac.py AC-89 results/campaign_flight` |
| AC-90 | The model client on target has a request budget, a hard timeout, a watchdog and a defined degraded mode; exceeding any of them yields a refusal, never a stale plan, and the run records the event | `python3 scripts/check_ac.py AC-90 results/campaign_flight` |
| AC-91 | Each flight bundle carries the verbatim exchange, the compiled plan, the site hash, the aircraft, the pilot, the site, the weather, the battery state and the waiver reference; a missing field fails the flight run contract | `guara verify --profile flight docs/evidence/<flight-bundle>` |
| AC-92 | The adversarial corpus has been reviewed by someone who did not write the compiler (RP-1), and the review, the added cases and the coverage measure are published | `python3 scripts/check_ac.py AC-92 mission/corpus` |

---

## 6. Track Z — space, on real hardware

M13, M14 and M15 stay as specified in `PLAN-M8-M16.md` §3; M18 and M19 now supply their
core and their conformance kit. What follows is their hardware half.

### M26 — the F´ host on a target

| AC | Criterion | Verification command |
|---|---|---|
| AC-93 | The F´ deployment cross-compiles for the OBC-class arm64 target and passes the conformance kit on target with verdicts identical to x86 | `./scripts/fprime.sh test --target conformance --platform <target>` |
| AC-94 | `Svc::Health` detects a hung decision core on target and the detection time is measured (AC-41 on hardware) | `./scripts/fprime.sh scenario hang_decision_thread --platform <target> && python3 scripts/check_ac.py AC-94 results/latest` |
| AC-95 | The remaining space channels of ADR 0012 — `power_margin`, `momentum`, `inputs_valid`, `requirements` — are implemented, each with a test that failed before its implementation, and each mapped to the safe mode's entry condition | `./scripts/fprime.sh test --target space_channels` |
| AC-96 | Safe-mode entry is exercised on target against the simulated ADCS and the declared load shed, with the commanded attitude and the shed set observed rather than asserted | `./scripts/fprime.sh scenario safe_mode_entry --platform <target>` |

### M27 — the space operational interface

| AC | Criterion | Verification command |
|---|---|---|
| AC-97 | The arbiter's channels, events and safe-mode entries are expressed as ECSS-E-ST-70-41 on-board monitoring, event reporting and event-action definitions, and the mapping table is complete [REVIEW] | `python3 scripts/check_pus_map.py space/pus/mapping.yaml` |
| AC-98 | Releasing the safe-mode latch requires an authenticated ground telecommand; no on-board path releases it, and an attempted release from any other source is rejected and logged — the space analogue of AC-32 | `./scripts/fprime.sh test --target safe_mode_release_auth` |
| AC-99 | The time system (TAI, UTC, spacecraft elapsed time) is declared, and the on-board clock drift budget is stated and measured against the simulator's truth | `python3 scripts/check_ac.py AC-99 results/latest_space` |
| AC-100 | An orbital simulator is pinned in `third_party/VERSIONS.md` and AC-48 runs against it | `./scripts/space_pair.sh --scenario keepout_slew --seed 42 && python3 scripts/check_ac.py AC-48 results/latest_pair` |
| AC-101 | An ECSS-E-ST-40C / Q-ST-80C non-claim map exists, the space sibling of AC-86, and no space document asserts a software criticality category | `python3 scripts/check_claims.py --domain space` |

### M28 — the space campaign

M16 executed on the target host: the orbital latency budget (AC-49) and the space RQ6b
(AC-50) re-measured with the F´ host on hardware rather than in a desktop build. No new
criteria; the existing two are re-run and re-reported with the target named.

---

## 7. Risks this plan adds

| # | Risk | Impact | Action |
|---|---|---|---|
| RH-1 | ROS 2 Humble is EOL 2027-05, inside this plan's horizon, while PX4 v1.17 recommends it | The air packages age out mid-programme | AC-71: Jazzy passes the kit before EOL, or the risk is accepted in writing with a date |
| RH-2 | Publishing installable binaries changes the posture from "research repository" to "something people fly" | Apache-2.0 disclaims warranty; reputational and regulatory exposure does not disclaim | Rule D; AC-86; the limits travel inside every artifact, not only in the SPEC |
| RH-3 | A vendor companion platform is the fastest route to flying hardware and the fastest route to capture | The architecture claim becomes one company's | ADR 0014 decision 7: generic arm64 is the reference target, vendor images are variants |
| RH-4 | The conformance kit will be cited by others as if it were an assurance argument | Overclaim by third parties, attributed to Guará | AC-66: the report says what it does not mean, in its own text; the kit is versioned |
| RH-5 | A single maintainer cannot run a release programme and a flight-test programme at once | Both degrade; the safety-critical one degrades silently | Rule H staging; M24 before M25; no hardware milestone runs concurrently with a release train |
| RH-6 | Freezing a C ABI before independent implementations exist bakes in the author's assumptions | A wrong interface, forever | ADR 0014 decision 3: ABI v1 is provisional until three ports pass the kit, one of them independent (AC-65) |
| RH-7 | Real flights involve real people, real airspace and real insurance | Harm, and a programme stop | M24 precedes M25; [REVIEW] by a qualified human, not by this plan |
| RH-8 | An appliance that can talk to a model provider invites credentials into a flying image | Key exfiltration, and a flight that depends on a network | The image ships with the `mock` provider selected and no credential path; a hosted provider is opt-in per run and recorded (ADR 0013 decision 7) |
| RH-9 | Measuring on a general-purpose Linux kernel yields distributions, not bounds; a reader may read AC-76 as a guarantee | Overclaim of timing | AC-60 and AC-76 report measured worst observed values and say so; a real bound needs a WCET tool and an RTOS, which is out of scope here |

## 8. Traceability

| Track | Gap rows | Milestones | ACs | ADRs |
|---|---|---|---|---|
| S — setup | G-S1..G-S8 | M17 | AC-51..AC-56 | 0014 |
| K — kernel and delivery | G-K1..G-K8 | M18, M19, M20 | AC-57..AC-71 | 0014, 0011, 0003 |
| H — air hardware | G-H1..G-H13 | M21..M25 | AC-72..AC-92 | 0001, 0004, 0009, 0010, 0013 |
| Z — space hardware | G-Z1..G-Z8 | M26..M28 | AC-93..AC-101 | 0011, 0012 |
