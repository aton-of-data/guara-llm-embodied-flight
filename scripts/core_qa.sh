#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# AC-62: ASan, UBSan and clang-tidy over guara-core.
# The conformance vector suite does not exist yet (M19); this run covers the
# ABI tests. Branch coverage is PARAMETER TBD and is not claimed here.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build="${GUARA_CORE_QA_BUILD:-${root}/build/core-qa}"
require_tidy=0
if [[ "${1:-}" == "--require-tidy" ]]; then
  require_tidy=1
fi

cmake -S "${root}/core" -B "${build}" \
  -DCMAKE_BUILD_TYPE=Debug \
  -DGUARA_CORE_SANITIZE=ON \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build "${build}" -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"

export ASAN_OPTIONS="detect_leaks=1:halt_on_error=1:abort_on_error=1"
export UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1"
ctest --test-dir "${build}" --output-on-failure

tidy_status="skipped"
if command -v clang-tidy >/dev/null 2>&1; then
  clang-tidy -p "${build}" --quiet "${root}/core/src/"*.cpp
  tidy_status="clean"
elif [[ "${require_tidy}" -eq 1 ]]; then
  echo "FAIL core_qa: clang-tidy is required but not on PATH" >&2
  exit 1
fi

echo "PASS core_qa: asan/ubsan clean on ABI tests; clang-tidy ${tidy_status}; coverage not measured (AC-62 PARAMETER TBD)"
