#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# AC-64: a C ABI that ignores the geofence uncertainty band must be rejected.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v cmake >/dev/null 2>&1; then
  echo "FAIL ctk_mutation_geofence_sil: cmake is required" >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
cp -R "${root}/core" "${tmp}/core"

src="${tmp}/core/src/geofence_predictor.cpp"
old='  if (inside_lateral_band || inside_vertical_band)'
new='  if (false && (inside_lateral_band || inside_vertical_band))'
if ! grep -F -q "${old}" "${src}"; then
  echo "FAIL ctk_mutation_geofence_sil: mutation site not found" >&2
  exit 1
fi
python="${PYTHON:-python3}"
"${python}" - "${src}" "${old}" "${new}" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
old, new = sys.argv[2], sys.argv[3]
text = path.read_text(encoding="utf-8")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY

config="${CMAKE_BUILD_TYPE:-Release}"
cmake -S "${tmp}/core" -B "${tmp}/build" -DCMAKE_BUILD_TYPE="${config}" >/dev/null
cmake --build "${tmp}/build" --config "${config}" --target guara_cabi -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"

lib=""
for candidate in \
  "${tmp}/build/libguara_cabi.so" \
  "${tmp}/build/libguara_cabi.dylib" \
  "${tmp}/build/${config}/guara_cabi.dll"
do
  if [[ -f "${candidate}" ]]; then
    lib="${candidate}"
    break
  fi
done
if [[ -z "${lib}" ]]; then
  echo "FAIL ctk_mutation_geofence_sil: mutated guara_cabi was not produced" >&2
  exit 1
fi

export PYTHONPATH="${root}${PYTHONPATH:+:${PYTHONPATH}}"
set +e
"${python}" -m guara ctk run --port sil --lib "${lib}" \
  --vectors "${root}/core/conformance/vectors/geofence.json" \
  >"${tmp}/out" 2>"${tmp}/err"
rc=$?
set -e
if [[ "${rc}" -eq 0 ]]; then
  echo "FAIL ctk_mutation_geofence_sil: kit accepted a C ABI with the uncertainty band disabled" >&2
  cat "${tmp}/out" "${tmp}/err" >&2 || true
  exit 1
fi
echo "PASS ctk_mutation_geofence_sil: uncertainty-band-disabled C ABI rejected (exit ${rc})"
exit 0
