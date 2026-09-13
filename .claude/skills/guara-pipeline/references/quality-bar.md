# Quality bar — the ten invariants

Every stage copies this list into its artifact and marks each row
`HOLDS` / `VIOLATED` / `N/A`. A row is never deleted.

| # | Invariant | Enforced by |
|---|---|---|
| Q1 | No number without a run. Figures come from `results/` via `scripts/aggregate.py`; the reviewable part is published by `scripts/publish_evidence.py` into `docs/evidence/`. | `scripts/check_run_contract.py`, `scripts/check_ac.py` |
| Q2 | No API from memory. Behavioural claims about PX4, ROS 2, F´, Ogma, Copilot, DAIDALUS, FRET cite `repo@commit:file:line` against `third_party/` pinned in `third_party/VERSIONS.md`; the `GROUNDING.md` row lands **before** the code. | review |
| Q3 | Test first. Every safety function gets a test that is watched failing before the implementation exists. | review, `colcon test` / `pytest` |
| Q4 | The decision path allocates nothing and is bounded. `DecisionCore` and everything it calls per tick. | `test_decision_core_no_alloc.cpp`, `test_decision_core_timing.cpp` |
| Q5 | A new flight operation gets its document in `docs/operations/` before it gets code. | review |
| Q6 | Apache-2.0 SPDX header on every new source file; nothing NOSA outside `nosa/`; no GPL-2.0-only dependency. | `scripts/check_spdx.py`, `scripts/check_license_isolation.py` |
| Q7 | SITL headless and reproducible: seed + commit recorded in the run. | `scripts/check_reproducible.py` |
| Q8 | Rule O — space/F´ work never precedes the PX4 latency and batch results. | review |
| Q9 | Scope is civil flight safety. No target selection, no weapon function, no failsafe/geofence/Remote-ID defeat. | review, hard stop |
| Q10 | Granular commits, `type(scope): imperative summary`, author `aton-of-data`, no `Co-authored-by`, no mention of an assistant or AI anywhere in the tree. English everywhere. | review |

## Standing gates

Run from the repository root; containers only where the command needs them.

```bash
python3 -m pytest scripts/tests -q
python3 scripts/check_spdx.py
python3 scripts/check_license_isolation.py
python3 scripts/check_links.py
python3 scripts/check_reproducible.py --pins
guara doctor
```

Kernel / C ABI, when `core/` is touched:

```bash
./scripts/check_core_consumer.sh
./scripts/check_ctk_sil.sh
python3 scripts/check_abi.py --baseline core/abi_symbols.txt
./scripts/core_qa.sh
```

ROS 2 packages, when `ros2_ws/` is touched (inside the dev container):

```bash
./scripts/dev.sh colcon build --symlink-install --base-paths ros2_ws/src --packages-select <pkg>
./scripts/dev.sh colcon test --base-paths ros2_ws/src --packages-select <pkg>
./scripts/dev.sh colcon test-result --verbose
```

A gate that reports zero tests is a failure, not a pass.

## Stop rule

Three failed attempts at the same gate → stop, record the last command and its output
verbatim in the log, set the task `BLOCKED`. Never weaken a test, a threshold or an
acceptance criterion to make a gate pass; that is a `CHANGES` verdict by construction.
