#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# AC-57: install guara-core and consume it from an out-of-tree CMake project.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config="${CMAKE_BUILD_TYPE:-Release}"
core_build="${GUARA_CORE_BUILD:-${root}/build/core}"
prefix="${GUARA_CORE_PREFIX:-${root}/build/core-prefix}"
consumer_build="${GUARA_CORE_CONSUMER_BUILD:-${root}/build/consumer}"

cmake -S "${root}/core" -B "${core_build}" -DCMAKE_BUILD_TYPE="${config}"
cmake --build "${core_build}" --config "${config}"
ctest --test-dir "${core_build}" -C "${config}" --output-on-failure
cmake --install "${core_build}" --config "${config}" --prefix "${prefix}"

rm -rf "${consumer_build}"
cmake -S "${root}/core/examples/consumer" -B "${consumer_build}" \
  -DCMAKE_BUILD_TYPE="${config}" \
  -DCMAKE_PREFIX_PATH="${prefix}"
cmake --build "${consumer_build}" --config "${config}"

exe=""
for candidate in \
  "${consumer_build}/guara_core_consumer" \
  "${consumer_build}/${config}/guara_core_consumer" \
  "${consumer_build}/${config}/guara_core_consumer.exe"
do
  if [[ -x "${candidate}" ]]; then
    exe="${candidate}"
    break
  fi
done
if [[ -z "${exe}" ]]; then
  echo "FAIL core-consumer: installed package did not produce a runnable binary" >&2
  exit 1
fi

out="$("${exe}")"
printf '%s\n' "${out}"
if [[ "${out}" != guara-core\ *\ abi\ *\ storage=* ]]; then
  echo "FAIL core-consumer: unexpected stdout" >&2
  exit 1
fi
echo "PASS core-consumer: out-of-tree project linked guara::core from ${prefix}"
