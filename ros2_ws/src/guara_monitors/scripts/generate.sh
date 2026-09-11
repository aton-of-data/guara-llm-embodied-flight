#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Generate Copilot C for Guará monitors via Ogma (runs inside guara-fm:m2).
# Outputs are copied to ros2_ws/src/guara_monitors/generated/ and must be committed.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "${root}"

# The FM image copies the ogma binary without `cabal install`, so Paths_ogma_core
# still points at an empty cabal share dir. Stage the data-files the binary expects.
ogma_share="$(strings "$(command -v ogma)" | grep -E '/ogma-core-1\.15\.0$' | grep '/share/' | head -1)"
if [[ -z "${ogma_share}" ]]; then
  echo "could not locate ogma-core datadir baked into $(command -v ogma)" >&2
  exit 1
fi
mkdir -p "${ogma_share}"
if [[ ! -f "${ogma_share}/data/variable-db.json" ]]; then
  cp -a /opt/fm/ogma/ogma-core/data "${ogma_share}/"
  cp -a /opt/fm/ogma/ogma-core/templates "${ogma_share}/"
fi

out="${root}/ros2_ws/src/guara_monitors/.ogma_out"
gen="${root}/ros2_ws/src/guara_monitors/generated"
rm -rf "${out}"
mkdir -p "${gen}" "${out}"

ogma ros \
  --project "${root}/ros2_ws/src/guara_monitors/specs/project.ogma" \
  --target-dir "${out}" \
  --template-dir "${root}/ros2_ws/src/guara_monitors/template" \
  --variable-file "${root}/ros2_ws/src/guara_monitors/specs/variables" \
  --variable-db "${root}/ros2_ws/src/guara_monitors/specs/vars-db.json" \
  --template-vars "${root}/ros2_ws/src/guara_monitors/specs/extra-vars.json"

src_hs="${out}/copilot/src"
if [[ ! -f "${src_hs}/Copilot.hs" ]]; then
  # Ogma may nest the package one directory deeper depending on template layout.
  src_hs="$(find "${out}" -name Copilot.hs -print -quit | xargs dirname)"
fi
if [[ -z "${src_hs}" || ! -f "${src_hs}/Copilot.hs" ]]; then
  echo "ogma did not write Copilot.hs under ${out}" >&2
  find "${out}" -type f >&2 || true
  exit 1
fi

( cd "${src_hs}" && copilot-runghc Copilot.hs )

shopt -s nullglob
copied=0
for f in "${src_hs}"/*.c "${src_hs}"/*.h "${src_hs}"/Copilot.hs; do
  cp -f "${f}" "${gen}/"
  copied=$((copied + 1))
done
if [[ "${copied}" -eq 0 ]]; then
  echo "no Copilot C outputs in ${src_hs}" >&2
  ls -la "${src_hs}" >&2
  exit 1
fi
echo "generated ${copied} files into ${gen}"
ls -la "${gen}"
