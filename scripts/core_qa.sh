#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# AC-62: ASan, UBSan and clang-tidy over guara-core.
# Line coverage of core/src is measured when a GNU gcov build succeeds. The
# pass threshold is PARAMETER TBD and is not claimed here.
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

cov_status="skipped (GNU gcov build unavailable)"
if command -v gcov >/dev/null 2>&1; then
  cov_build="${GUARA_CORE_COV_BUILD:-${root}/build/core-cov}"
  if cmake -S "${root}/core" -B "${cov_build}" \
      -DCMAKE_BUILD_TYPE=Debug \
      -DGUARA_CORE_COVERAGE=ON \
      >/tmp/guara-core-cov-cmake.log 2>&1; then
    cmake --build "${cov_build}" -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"
    ctest --test-dir "${cov_build}" --output-on-failure
    python3 "${root}/scripts/core_coverage.py" --build "${cov_build}"
    cov_status="measured (not a bound)"
  else
    cov_status="skipped (GCC required; see /tmp/guara-core-cov-cmake.log)"
  fi
fi

echo "PASS core_qa: asan/ubsan clean on ABI tests; clang-tidy ${tidy_status}; coverage ${cov_status} (AC-62 PARAMETER TBD)"
