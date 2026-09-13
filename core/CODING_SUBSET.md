# SPDX-License-Identifier: Apache-2.0
#
# Coding subset of `core/` (M18). Status: [REVIEW]
#
# This is a description of the subset the kernel actually uses, not a MISRA or
# AUTOSAR qualification. Passing clang-tidy and the no-alloc tests does not
# make a containing system safe (ADR 0014 decision 4).

## Language

- C++17, no GNU extensions (`CMAKE_CXX_EXTENSIONS OFF`).
- The public surface is a C11 ABI (`include/guara/guara.h`).
- The decision path is `noexcept`. The kernel does not throw.

## What the kernel does not do

- No ROS, ament, PX4, Eigen, iostream, RTTI or C++ exceptions on the step path.
- No heap after `guara_core_init`. Construction is placement-new into caller
  storage. `malloc` / `free` / `write` are trapped by the ABI tests.
- No clock: `t_s` is an input.
- No filesystem, network, threads or locale.
- No `std::string`, containers that allocate, or `new`/`delete` in `src/`.
- The only loop in `DecisionCore::step` walks a fixed-capacity switch history
  (`kSwitchHistoryCapacity == 32`). The geofence predictor walks at most
  `kMaxVertices == 64` vertices, O(N^2).
- `<algorithm>` is used only for `std::clamp` / `std::min` / `std::max` in the
  geofence predictor.

## Allowed library

- `<array>`, `<algorithm>`, `<cstddef>`, `<cstdint>`, `<cstring>`, `<cmath>`, `<limits>`, `<new>`
  (placement new at init only).
- C ABI: `<stddef.h>`, `<stdint.h>`.

## Build gates

- `-Wall -Wextra -Wpedantic -Werror` (standalone CMake).
- Hidden ELF visibility; `GUARA_API` is the export set (`core/abi_symbols.txt`).
- `scripts/core_qa.sh`: ASan, UBSan, clang-tidy over `core/src`. Line coverage
  of `core/src` is measured with gcov when GCC is available; the pass
  threshold is PARAMETER TBD.
