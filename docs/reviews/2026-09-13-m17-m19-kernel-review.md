# Review — the extracted kernel, its C ABI and the conformance kit (M17–M19)

Date: 2026-09-13 · Branch `feat/2026-09-13-adr0014-guara-core` at `700612c` · Scope: everything
ADR 0014 added below `core/`, `guara/`, `scripts/` and `.github/workflows/` between `22ab122` and
`700612c` — 110 files, ~12.7 kLOC · Method: read the code; build and run it (CMake 4.4.3 /
AppleClang 17 on arm64, CPython 3.14 in a clean venv); drive the C ABI through `ctypes` to observe
behaviour rather than infer it; re-read the two failing CI jobs. Findings cite `file:line` at the
post-fix revision.

Every finding below is closed on this branch. The remediation is one commit per finding, and each
behavioural finding carries a test that fails without its fix (CLAUDE.md, Engineering).

Nothing in this review is a claim about flight. Conformance is necessary and not sufficient
(ADR 0014 decision 4).

---

## 1. Blocking — the pull request could not go green

### B-1 · MSVC rejected the kernel: C4324 under `/W4 /WX`

`core/src/abi.cpp:22` and `core/src/monitor_abi.cpp:18` declare storage structs whose embedded byte
array is `alignas`-ed to the kernel object placed in it. MSVC reports C4324, "structure was padded
due to alignment specifier", which `/WX` turns into an error; the `host-free kernel
(windows-latest)` job failed at `guara_cabi.vcxproj` on every push. The padding is the purpose of
the declaration, so the warning has nothing to report.

**Fix.** `/wd4324` alongside `/W4 /WX` in the standalone MSVC branch of `core/CMakeLists.txt:47`.
GCC and Clang keep `-Wall -Wextra -Wpedantic -Werror` unchanged.

### B-2 · clang-tidy rejected the kernel: three errors under `WarningsAsErrors: '*'`

The `kernel sanitizers` job ran `scripts/core_qa.sh --require-tidy` and exited 1 on:

| Site | Check |
|---|---|
| `core/include/guara_rta/monitor_table.hpp:117` | `bugprone-branch-clone` |
| `core/src/types.cpp` `transitionName` | `bugprone-switch-missing-default-case` |
| `core/src/types.cpp` `causeName` | `bugprone-switch-missing-default-case` |

The branch clone was real duplication, not a false positive: the `expected` arm and the `malformed`
arm had byte-identical bodies. The two switches dispatch on a *wire value*, not on an enumerator, so
an unlisted code fell out of the switch to a trailing `return "UNKNOWN"` that the check could not
see.

**Fix.** `monitor_table.hpp:117` states the condition once —
`(s.expected && (stale || !s.inputs_complete)) || s.malformed`, which is exactly the union the two
arms computed. `types.cpp:54` and `types.cpp:72` move the fallthrough into a `default:` label.

Verified with clang-tidy 23.1.1 over `core/src/*.cpp` against the project `.clang-tidy`: clean. That
run also surfaced **B-3**, below, which the older clang-tidy in CI does not yet report.

### B-3 · `bugprone-signed-bitwise` in the parameter digest

`write_le64` shifted by `8 * i` with `i` declared `int`. Pre-existing, benign at every reachable
value, and a gate failure the moment CI's clang-tidy is updated.

**Fix.** `core/src/param_digest.cpp:29` iterates over `unsigned`.

---

## 2. High — the C ABI accepted input it must refuse

### H-1 · An out-of-contract monitor action produced RF with no command

`guara_core_step` cast `guara_inputs.monitor_action` straight to `guara_rta::Recovery` with no range
check. `DecisionCore::select` then ranked the unnamed enumerator through `maxRank`, and
`commandFor` — a switch over the four real enumerators — fell through to `Command::kNone`.

Observed on the built library before the fix, driving the C ABI directly:

```
step monitor_action=200 rc=0 state=2 recovery=200 command=0
```

That is the worst available outcome: the arbiter takes the vehicle away from the complex function
and then commands nothing. It is also inconsistent with the rest of the codebase —
`MonitorTable::observe` already refuses a verdict outside its message contract
(`monitor_table.hpp:92`), and `guara_gateway_on_core_state` already refuses a state above
`GUARA_STATE_MAX`.

**Fix.** `core/src/abi.cpp:192` returns `GUARA_ERR_PARAMS` for `monitor_action > GUARA_RECOVERY_MAX`
and changes no state. The independent Python port refuses identically at
`guara/ctk/reference.py:235`, raising `CoreRejected("PARAMS")`, so the two ports stay comparable on
refusals as well as on decisions; `SilCore.step` raises the same exception carrying the
`guara_err_name` of the return code.

```
step monitor_action=200 rc=3 state=0 recovery=0 command=0
```

**Tests.** `core/test/test_abi_step.c` (200 and `GUARA_RECOVERY_MAX + 1` rejected, `LAND` still
accepted and still commanding `LAND`); `scripts/tests/test_ctk.py::
test_a_monitor_action_outside_the_recovery_encoding_is_refused`.

### H-2 · Storage alignment was published but never enforced

The ABI publishes `guara_core_storage_align()`, `guara_gateway_storage_align()` and
`guara_monitor_storage_align()`, and the header told the caller to honour them — but no init
function checked. Placement-new into an under-aligned buffer is undefined behaviour, and on a
strict-alignment target it faults on the first store. Before the fix:

```
core storage size 400 align 8
init on misaligned addr (off 1): rc=0
```

A published requirement that the implementation does not enforce is not a contract; on x86 and
arm64 it is a bug that will not appear until the kernel reaches the OBC-class board of G-Z2.

**Fix.** `core/src/abi.cpp:165`, `core/src/gateway_abi.cpp:127` and `core/src/monitor_abi.cpp:88`
reject a misaligned buffer with `GUARA_ERR_STORAGE`, in the same test as the short-buffer check and
before anything is written. The header states the contract in its file comment.

**Tests.** `core/test/test_abi_storage.c` asserts `buf + 1` is refused whenever the required
alignment exceeds 1.

**Consequence.** Six ABI tests and the published consumer example passed storage that happened to be
aligned. They now align it explicitly through `core/test/storage.h`, and
`core/examples/consumer/main.c` shows the rounding inline — the example is the one place an
integrator copies from, so it has to demonstrate the contract rather than rely on the allocator.

### H-3 · The parameter digest was not byte-order independent

`feed_f64` byte-swapped on big-endian hosts *after* `memcpy`-ing the double into a `uint64_t`. The
copy already yields the IEEE-754 pattern as an integer on both byte orders — a host stores doubles
and integers the same way round — and `write_le64` then serialises it identically everywhere. The
extra swap reintroduced exactly the host dependence it appears to remove, so `guara-core` on a
POWER, s390x or SPARC host would have computed a different `param_digest` for the same parameter set
and the arming gate of G-H6 would have rejected a correct configuration.

Unreachable on every CI runner, which is why it was never caught.

**Fix.** `core/src/param_digest.cpp:38` drops the swap. The golden digest in
`core/test/test_abi_digest.c` and `guara.params.DEFAULT_DIGEST_HEX` are unchanged, which is the
point: little-endian behaviour is identical.

---

## 3. High — the conformance kit could pass without checking

### K-1 · `ctk run` could not run the published set

`guara ctk run --vectors core/conformance/vectors` — the form `docs/PLAN-M17-M28.md` AC-63 and AC-64
write — failed with `Is a directory`. `run` accepted exactly one file and defaulted to `spec_s3.json`
alone; only `bench` walked the directory. The consequence was structural: the CI job and
`scripts/check_ctk_sil.sh` enumerated files by hand, the report's `vectors_sha256` identified one
file rather than the set, and `guara ctk run --port python` — the command AC-65 names — claimed a
pass over 11 of the 94 published vectors.

**Fix.** `guara/ctk/run.py:532` `run_suite` runs a file or a directory and aggregates;
`run.py:549` `suite_digest` hashes each file's name and bytes in name order, so a set has one hash.
`run` now defaults to the whole published set. Both ports agree:

```
port           python-reference        port           sil-cabi
vectors        adr0010_gateway.json,core_params.json,gateway_limits.json,geofence.json,
               monitor_max_age.json,monitor_table.json,spec_s3.json,types.json
vectors_sha256 14c9eed6cba2d22a05a4cd4802ef805a665c844a100a1a1cd6ab54b50c4780ad
result         PASS 94/94              result         PASS 94/94
```

The workflow and `check_ctk_sil.sh` lose their hand-written file lists, and the SIL job now writes a
report and runs `check_ac.py AC-66` against it. Both mutation scripts inherit the wider default and
therefore now have to survive the whole set.

**Tests.** `scripts/tests/test_ctk.py::test_python_port_passes_the_whole_published_set_by_default`,
`::test_a_named_vector_directory_equals_the_default_run`,
`::test_spec_s3_alone_still_runs_and_is_a_strict_subset`.

### K-2 · An unrecognised expectation key was silently skipped

Every comparator — `_check`, `_check_geofence`, `_check_project`, `_check_gateway`, `_check_monitor`
— iterated the vector's `expect` map and did `if key not in mapping: continue`. A misspelled key was
not a failure and not a warning; it was a vector that checked nothing and reported PASS. For a kit
whose entire product is "this port behaves like the reference", a silent vacuous pass is worse than
no kit.

**Fix.** `guara/ctk/run.py:78` `_known` raises `CtkError` naming the key and the fields that vector
set does compare. Applied at all five comparators. The published set passes unchanged, which
confirms no vector currently relies on the old leniency.

**Test.** `scripts/tests/test_ctk.py::test_an_unknown_expectation_key_is_refused_not_skipped`.

---

## 4. Medium — the CLI wrote to the wrong stream

### M-1 · `sys.stdout` / `sys.stderr` bound at import time

`doctor.run`, `params.run` and `ctk.run` took `out=sys.stdout, err=sys.stderr` as default arguments,
which Python evaluates once, at `def` time. Any caller that replaces the streams after the module is
imported — a test harness, or a host embedding the CLI — was silently bypassed.
`scripts/tests/test_doctor.py::test_doctor_fails_when_the_clone_cannot_be_found` passed only because
nothing had imported `guara.doctor` before it ran; adding one unrelated in-process test broke it.

**Fix.** `guara/doctor.py:74`, `guara/params.py:148` and `guara/ctk/run.py` default to `None` and
resolve the stream at call time.

### M-2 · The SIL script picked a library for the wrong platform

`scripts/check_ctk_sil.sh` searched `build/` for a `guara_cabi` in filename order, `.so` first, and
ignored an already-set `GUARA_CABI`. `find_cabi` in `guara/ctk/sil.py` filters by the platform's
suffix; the shell script did not. A developer whose `build/` still holds a Linux artifact from
`scripts/dev.sh` — the documented container path — got
`dlopen(...libguara_cabi.so): slice is not valid mach-o file` on macOS.

**Fix.** The script honours `GUARA_CABI` when it is set and otherwise accepts only a candidate whose
suffix matches `uname -s`.

---

## 5. Documentation defects

### D-1 · The header claimed the wrong thing

`core/include/guara/guara.h` said passing the interface "demonstrates behavioural **access** to the
reference core". The word required by ADR 0014 decision 4, and used by the CTK report and
`check_ac.py::check_ac66`, is **equivalence**. Corrected, and the sentence now matches the report
text it is supposed to mirror.

### D-2 · Two "action" encodings, one header, no names

`guara_inputs.monitor_action` is a `Recovery` (`NONE=0, HOLD=1, RTL=2, LAND=3`).
`guara_monitor_sample.action` is the wire contract (`HOLD=0, RTL=1, LAND=2`). Only the second had
named constants; the first was a bare `uint8_t` an integrator had to reverse-engineer from
`abi.cpp`, and an off-by-one between the two is precisely H-1. The header now defines
`GUARA_STATE_*`, `GUARA_RECOVERY_*` and `GUARA_COMMAND_*`, states that the two encodings differ by
one, and `abi.cpp` uses the names in place of the bare literals it dispatched on.

### D-3 · `guara_monitor_observe` returns a different code space

It returns `GUARA_MONITOR_ACCEPTED` / `_INVALID_FIELD` / `_TABLE_FULL` (0/1/2) when the call reached
the table, and `GUARA_ERR_NULL` / `GUARA_ERR_UNINIT` (1/4) when it did not — so `1` means two
different things. The behaviour is deliberate and is kept; the header now says so, and says to name
the result with `guara_monitor_accept_name` and never with `guara_err_name`.

### D-4 · `docs/milestones/STATUS.md` did not define thread **K**

Ten rows were filed under thread `K`, which the legend did not list; `docs/PLAN-M17-M28.md:314`
defines it as "kernel and delivery". Rows for **AC-59** (the no-alloc and freestanding probes, which
exist and run) and **AC-61** (the symbol baseline, which CI enforces on every push) were missing
altogether, so implemented work was invisible in the tracker. Both added, legend corrected.

### D-5 · Nothing about the delivery model reached a reader

ADR 0014 re-scopes the extraction as "the project's main product surface", and the branch shipped
`guara-core`, a C ABI, a CMake package, published vectors and two port runners — with no page a
third party could read. `site/integrate.html` still offered three integration seams and three paths.
A fourth seam and a new section **K · Embedding the kernel without ROS** were added, covering the
storage contract, the CMake consumption path, the CTK commands, and what conformance does not mean.

---

## 6. Accepted, not fixed

| # | Observation | Why it stands |
|---|---|---|
| A-1 | `guara_gf_predict` does not check `guara_gf_state` for finiteness; a NaN state yields NaN times | The host channel gate already maps a non-finite estimate to `V(k)` before the predictor is reached (`channel_gating`). Filed as a candidate vector set for M19's remaining coverage work, not a defect at this seam |
| A-2 | `guara_gf_polygon_error(NULL, n>0)` answers `GUARA_GF_POLY_NON_FINITE` rather than a null error | The function's return space is polygon errors only. Changing it would widen the C ABI before three ports exist (ADR 0014 decision 3) |
| A-3 | The CTK dispatches on the shape of `data[0]` rather than a declared kind | A declared kind changes every vector file's bytes and therefore every published `vectors_sha256`. It belongs with the next ABI version bump, not inside it |
| A-4 | `guara_rta` and `guara_geofence` both compile `core/src/geofence_predictor.cpp`, so the arbiter links two archives defining the same symbols | ODR-identical, and static archives contribute only the objects the link needs. Noted for M20, when the packages are released separately |
| A-5 | `GUARA_API` has no `__declspec(dllimport)` branch for a Windows consumer of the shared build | Every published path uses the static `guara_core`; the shared `guara_cabi` exists for the SIL port, which loads it through `ctypes` |

---

## 7. What was executed

```
cmake -S core -B build/core -DCMAKE_BUILD_TYPE=Release && cmake --build build/core
ctest --test-dir build/core --output-on-failure        # 11/11 passed
cmake --install build/core --prefix build/core-prefix  # out-of-tree consumer links guara::core
python3 -m pytest scripts/tests -q                     # 217 passed, 1 skipped
guara ctk run --port python                            # PASS 94/94
guara ctk run --port sil                               # PASS 94/94, same vectors_sha256
clang-tidy -p build/tidy core/src/*.cpp                # clean (clang-tidy 23.1.1)
```

`scripts/core_qa.sh` is Linux-gated in CI: `detect_leaks` is unsupported by ASan on macOS, so the
sanitizer evidence for this branch is the `kernel sanitizers` job, not the local run.
