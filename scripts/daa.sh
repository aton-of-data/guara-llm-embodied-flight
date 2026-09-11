#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Build or test the NOSA-isolated guara_daidalus package (ADR 0003).
# nosa/ is not on the default colcon base-paths.
# Usage: ./scripts/daa.sh build|test [extra colcon args...]
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "${root}/third_party/daidalus/C++/include/Daidalus.h" ]] || {
  echo "missing third_party/daidalus: run scripts/fetch_third_party.sh" >&2
  exit 1
}

cmd="${1:-build}"
shift || true
paths=(ros2_ws/src nosa third_party/px4_msgs third_party/px4-ros2-interface-lib/px4_ros2_cpp)

case "${cmd}" in
  build)
    exec "${root}/scripts/dev.sh" colcon build --symlink-install --base-paths "${paths[@]}" \
      --packages-up-to guara_daidalus "$@"
    ;;
  test)
    exec "${root}/scripts/dev.sh" colcon test --base-paths "${paths[@]}" \
      --packages-select guara_daidalus --event-handlers console_direct+ \
      --ctest-args -R daa_equivalence "$@"
    ;;
  *)
    exec "${root}/scripts/dev.sh" colcon "${cmd}" --base-paths "${paths[@]}" "$@"
    ;;
esac
