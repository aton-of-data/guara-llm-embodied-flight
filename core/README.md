<!-- SPDX-License-Identifier: Apache-2.0 -->
# `guara-core` — the host-free switching kernel and its conformance kit

Two of the five artifacts of [ADR 0014](../docs/adr/0014-delivery-model.md) live in this
directory: `guara-core`, the switching kernel with a C ABI (model D4), and `guara-ctk`, the
published input→decision vectors and their runners (model D6). They are released together, and
the ADR forbids releasing a host package whose conformance report is absent or failing.

> Passing the kit demonstrates behavioural equivalence to the reference decision core on the
> published vectors, and **nothing about the safety of the system that contains it**
> (ADR 0014 decision 4). The word "safe" is never used of Guará itself.

The ABI is **provisional** until three independent ports pass the kit — ROS 2, F´, and a
deliberately independent reimplementation (ADR 0014 decision 3). Two exist today: the C ABI and
the Python port under `guara/ctk/reference.py`.

## What is in here

| Path | Contents |
|---|---|
| `include/guara/guara.h` | the C ABI: the whole public surface, and the contract every entry point enforces |
| `include/guara_rta/`, `include/guara_geofence/` | the C++17 kernel — switching logic (SPEC §3), CF gateway (ADR 0010), monitor table (ADR 0002), geofence predictor (ADR 0004) |
| `src/` | the kernel and the four ABI translation units |
| `conformance/vectors/` | the published vectors; `guara-ctk` is the runner |
| `examples/consumer/` | a complete out-of-tree CMake project that links `guara::core` |
| `abi_symbols.txt` | the exported symbol baseline `scripts/check_abi.py` gates on every push |
| `CODING_SUBSET.md` | the subset the kernel actually uses. Not a MISRA or AUTOSAR qualification |

No ROS, no ament, no PX4, no Eigen, no heap after init, no clock, no I/O.

## Build, test and install

```bash
cmake -S core -B build/core -DCMAKE_BUILD_TYPE=Release
cmake --build build/core
ctest --test-dir build/core --output-on-failure
cmake --install build/core --prefix /your/prefix
```

`scripts/check_core_consumer.sh` runs exactly that and then builds
`core/examples/consumer` against the install prefix; it is AC-57, and CI runs it on Ubuntu,
macOS and Windows.

## Consume it

```cmake
find_package(guara_core REQUIRED)
target_link_libraries(your_target PRIVATE guara::core)
```

## The storage contract

The kernel allocates nothing. The caller owns the memory, sizes it with `*_storage_size()` and
aligns it to `*_storage_align()`. A buffer that is too short *or* under-aligned is refused with
`GUARA_ERR_STORAGE`, before anything is written.

```c
#include "guara/guara.h"

unsigned char raw[1024];
const size_t align = guara_core_storage_align();
unsigned char *buf = (unsigned char *)(((uintptr_t)raw + (align - 1U)) & ~(uintptr_t)(align - 1U));

guara_params p;
guara_params_default(&p);
if (guara_core_init(buf, sizeof raw - (size_t)(buf - raw), &p) != GUARA_OK) { /* refused */ }

guara_inputs in = { .t_s = 1.0, .in_charge = 1, .owned_mode_active = 1,
                    .t_daa_s = INFINITY, .t_gf_s = INFINITY,
                    .monitor_action = GUARA_RECOVERY_HOLD };
guara_output out;
guara_core_step(buf, &in, &out);
```

Two encodings of "action" share the header and differ by one:
`guara_inputs.monitor_action` is a `GUARA_RECOVERY_*` value (`NONE=0 … LAND=3`), while
`guara_monitor_sample.action` is the monitor wire contract (`GUARA_MONITOR_ACTION_HOLD=0 …
LAND=2`). `guara_core_step` refuses a value above `GUARA_RECOVERY_LAND` rather than rank it.

Likewise, `guara_monitor_observe` answers in the `GUARA_MONITOR_*` code space when the call
reached the table, and in the `GUARA_ERR_*` space when it did not; name its result with
`guara_monitor_accept_name`.

## Run the conformance kit

```bash
pip install -e .

guara ctk run --port python                     # the independent Python port
guara ctk run --port sil                        # the C ABI, through ctypes
guara ctk run --port python --report results/latest_ctk
guara ctk bench --port sil --report results/latest_bench
```

With no `--vectors`, both commands run the **whole published set** and report one result and one
`vectors_sha256` over it; `--vectors` narrows to one file or another directory. The report names
the core version, the ABI version, the port, the host, the architecture and the set hash, and
states in its own text what conformance does not mean (AC-66). `bench` records the worst observed
time of one kernel entry, labelled *measured, not a bound* — a real bound needs a WCET tool and an
RTOS, which is out of scope (AC-60, risk RH-9).

`scripts/ctk_mutation*.sh` inject a single behavioural mutation into a copy of a port and require
the kit to reject it (AC-64).

## Where the rest is written down

- Decision and scope: [ADR 0014](../docs/adr/0014-delivery-model.md)
- Switching rule and acceptance criteria: [`docs/SPEC.md`](../docs/SPEC.md) §3, §6
- Milestones and gaps: [`docs/PLAN-M17-M28.md`](../docs/PLAN-M17-M28.md) §1, §3, §4
- Criterion status: [`docs/milestones/STATUS.md`](../docs/milestones/STATUS.md)
- Findings against this code and their remediation:
  [`docs/reviews/2026-09-13-m17-m19-kernel-review.md`](../docs/reviews/2026-09-13-m17-m19-kernel-review.md)
