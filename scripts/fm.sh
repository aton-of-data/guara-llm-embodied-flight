#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run a command inside the Guará formal-methods image (FRET/Ogma/Copilot).
# Usage: ./scripts/fm.sh <cmd> [args...]   (no args: interactive shell)
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${GUARA_FM_IMAGE:-guara-fm:m2}"

if [[ -f /.dockerenv && "${GUARA_FM_IN_CONTAINER:-}" == "1" ]]; then
  exec "$@"
fi

if ! docker image inspect "${image}" >/dev/null 2>&1; then
  docker build -t "${image}" -f "${root}/docker/Dockerfile.fm" "${root}/docker"
fi

tty_flags=()
[[ -t 0 && -t 1 ]] && tty_flags=(-it)
[[ $# -gt 0 ]] || set -- bash

exec docker run --rm ${tty_flags[@]+"${tty_flags[@]}"} \
  -v "${root}:/work" -w /work \
  -e GUARA_FM_IN_CONTAINER=1 \
  "${image}" \
  bash -c 'exec "$@"' bash "$@"
