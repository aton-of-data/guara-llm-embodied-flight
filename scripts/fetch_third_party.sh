#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Recreate third_party/ shallow clones at the commits pinned in third_party/VERSIONS.md.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="${root}/third_party"

# name|remote|ref|commit
repos=(
  "PX4-Autopilot|https://github.com/PX4/PX4-Autopilot.git|v1.17.0|d6f12ad1c4f70ad3230afd7d86e971421e02fef4"
  "px4_msgs|https://github.com/PX4/px4_msgs.git|release/1.17|86d8239e962f6939e05c3737784f60c02fa884db"
  "px4-ros2-interface-lib|https://github.com/Auterion/px4-ros2-interface-lib.git|release/1.17|4a3370f084ac6f1ef001a4afa2b007845ffd0837"
  "ogma|https://github.com/nasa/ogma.git|v1.15.0|69485b3442d76c48faaee30b37f9cbee212ceca6"
  "daidalus|https://github.com/nasa/daidalus.git|DAIDALUSv2.0.3a|0647596edb218f8e8c7731ff800396297bbace99"
  "fret|https://github.com/NASA-SW-VnV/fret.git|v3.1.0|58db455be35182a015e607232d9f4e3c86731932"
  "copilot|https://github.com/Copilot-Language/copilot.git|v4.8.1|365fb21429aa0b880f81d72dcaa9f207f5ea2d0a"
)

for entry in "${repos[@]}"; do
  IFS='|' read -r name remote ref commit <<<"${entry}"
  dir="${dest}/${name}"
  if [[ ! -d "${dir}/.git" ]]; then
    git -c advice.detachedHead=false clone --quiet --depth 1 --branch "${ref}" "${remote}" "${dir}"
  fi
  head="$(git -C "${dir}" rev-parse HEAD)"
  if [[ "${head}" != "${commit}" ]]; then
    # Branch refs may have moved since pinning; fetch the exact commit.
    git -C "${dir}" fetch --quiet --depth 1 origin "${commit}"
    git -C "${dir}" -c advice.detachedHead=false checkout --quiet "${commit}"
    head="$(git -C "${dir}" rev-parse HEAD)"
  fi
  [[ "${head}" == "${commit}" ]] || { echo "FAIL ${name}: ${head} != ${commit}" >&2; exit 1; }
  echo "ok ${name} ${head}"
done
