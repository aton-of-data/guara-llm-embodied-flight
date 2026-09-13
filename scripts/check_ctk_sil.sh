#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# AC-64: run the published vectors through the C ABI (SIL port).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${root}${PYTHONPATH:+:${PYTHONPATH}}"

lib=""
for candidate in \
  "${root}/build/core/libguara_cabi.so" \
  "${root}/build/core/libguara_cabi.dylib" \
  "${root}/build/core/Release/guara_cabi.dll" \
  "${root}/build/core/Debug/guara_cabi.dll" \
  "${root}/build/core-prefix/lib/libguara_cabi.so" \
  "${root}/build/core-prefix/lib/libguara_cabi.dylib" \
  "${root}/build/core-prefix/bin/guara_cabi.dll"
do
  if [[ -f "${candidate}" ]]; then
    lib="${candidate}"
    break
  fi
done
if [[ -z "${lib}" ]]; then
  echo "FAIL ctk-sil: guara_cabi shared library not found; build core/ first" >&2
  exit 1
fi
export GUARA_CABI="${lib}"
export PATH="$(cd "$(dirname "${lib}")" && pwd):${PATH}"

py="python3"
if ! command -v python3 >/dev/null 2>&1; then
  py="python"
fi

"${py}" -m guara ctk run --port sil
"${py}" -m guara ctk run --port sil --vectors "${root}/core/conformance/vectors/adr0010_gateway.json"
"${py}" -m guara ctk run --port sil --vectors "${root}/core/conformance/vectors/monitor_table.json"
"${py}" -m guara ctk run --port sil --vectors "${root}/core/conformance/vectors/geofence.json"
"${py}" -m guara ctk run --port sil --vectors "${root}/core/conformance/vectors/core_params.json"
"${py}" -m guara ctk run --port sil --vectors "${root}/core/conformance/vectors/types.json"
bench="${TMPDIR:-/tmp}/guara-ctk-bench"
"${py}" -m guara ctk bench --port sil --report "${bench}"
"${py}" "${root}/scripts/check_ac.py" AC-60 "${bench}"
bash "${root}/scripts/ctk_mutation_sil.sh"
bash "${root}/scripts/ctk_mutation_geofence_sil.sh"
echo "PASS ctk-sil: C ABI port matched the published vectors via ${lib}"
