#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Recreate third_party/ shallow clones at the commits pinned in versions.env.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="${root}/third_party"

# Pins live in versions.env (M17 / G-S2). Sourcing it is the only way this
# script learns a commit; check_reproducible.py --pins refuses hardcoded hashes.
# shellcheck disable=SC1091
source "${root}/versions.env"

# name|remote|ref|commit
repos=(
  "PX4-Autopilot|${PX4_REMOTE}|${PX4_REF}|${PX4_COMMIT}"
  "px4_msgs|${PX4_MSGS_REMOTE}|${PX4_MSGS_REF}|${PX4_MSGS_COMMIT}"
  "px4-ros2-interface-lib|${PX4_ROS2_INTERFACE_LIB_REMOTE}|${PX4_ROS2_INTERFACE_LIB_REF}|${PX4_ROS2_INTERFACE_LIB_COMMIT}"
  "ogma|${OGMA_REMOTE}|${OGMA_REF}|${OGMA_COMMIT}"
  "daidalus|${DAIDALUS_REMOTE}|${DAIDALUS_REF}|${DAIDALUS_COMMIT}"
  "fret|${FRET_REMOTE}|${FRET_REF}|${FRET_COMMIT}"
  "copilot|${COPILOT_REMOTE}|${COPILOT_REF}|${COPILOT_COMMIT}"
  "fprime|${FPRIME_REMOTE}|${FPRIME_REF}|${FPRIME_COMMIT}"
)

for entry in "${repos[@]}"; do
  IFS='|' read -r name remote ref commit <<<"${entry}"
  dir="${dest}/${name}"
  if [[ "${GUARA_OFFLINE:-}" == "1" ]]; then
    if [[ ! -d "${dir}/.git" ]]; then
      echo "FAIL ${name}: missing (GUARA_OFFLINE=1; clone is not cached)" >&2
      exit 1
    fi
    head="$(git -C "${dir}" rev-parse HEAD)"
    if [[ "${head}" != "${commit}" ]]; then
      echo "FAIL ${name}: ${head} != ${commit} (GUARA_OFFLINE=1; will not fetch)" >&2
      exit 1
    fi
    echo "ok ${name} ${head}"
    continue
  fi
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
