#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run a command inside the Guará dev container with the repository mounted at /work.
# Usage: ./scripts/dev.sh <cmd> [args...]   (no args: interactive shell)
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${GUARA_IMAGE:-guara-dev:m1}"

if [[ -f /.dockerenv && "${GUARA_IN_CONTAINER:-}" == "1" ]]; then
  exec "$@"
fi

if ! docker image inspect "${image}" >/dev/null 2>&1; then
  docker build -t "${image}" -f "${root}/docker/Dockerfile" "${root}/docker"
fi

for dep in px4_msgs px4-ros2-interface-lib; do
  [[ -d "${root}/third_party/${dep}/.git" ]] || { echo "missing third_party/${dep}: run scripts/fetch_third_party.sh" >&2; exit 1; }
done

guara_sha="$(git -C "${root}" rev-parse HEAD)"
guara_dirty="false"
[[ -z "$(git -C "${root}" status --porcelain)" ]] || guara_dirty="true"

tty_flags=()
[[ -t 0 && -t 1 ]] && tty_flags=(-it)

# Variables the caller explicitly allows into the container, by name only:
#   GUARA_PASS_ENV=CURSOR_API_KEY ./scripts/dev.sh python3 scripts/llm/eval.py ...
# Nothing is forwarded by default, so a credential enters the container only when the
# command that needs it asks for it (ADR 0013 decision 7).
pass_env=()
if [[ -n "${GUARA_PASS_ENV:-}" ]]; then
  IFS=',' read -r -a names <<<"${GUARA_PASS_ENV}"
  for name in "${names[@]}"; do
    [[ -n "${name}" ]] && pass_env+=(-e "${name}")
  done
fi
[[ $# -gt 0 ]] || set -- bash

exec docker run --rm ${tty_flags[@]+"${tty_flags[@]}"} \
  -v "${root}:/work" -w /work \
  -e GUARA_IN_CONTAINER=1 \
  -e GUARA_SHA="${guara_sha}" \
  -e GUARA_DIRTY="${guara_dirty}" \
  -e GUARA_IMAGE_ID="$(docker image inspect --format '{{.Id}}' "${image}")" \
  -e COLCON_DEFAULTS_FILE=/work/ros2_ws/colcon_defaults.yaml \
  -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}" \
  ${pass_env[@]+"${pass_env[@]}"} \
  "${image}" \
  bash -c 'source /opt/ros/humble/setup.bash; [[ -f install/setup.bash ]] && source install/setup.bash; exec "$@"' bash "$@"
