#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run N headless latency_hold SITL members into results/batch_latency (SPEC AC-18).
# Usage: ./scripts/sitl_batch.sh [--runs 30] [--seed-start 1]
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runs=30
seed_start=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --runs) runs="$2"; shift 2 ;;
    --seed-start) seed_start="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 2 ;;
  esac
done

batch="${root}/results/batch_latency"
# Each batch is one measurement of one build: mixing members produced by different commits would
# make the aggregate meaningless, so the batch directory is rebuilt from scratch.
rm -rf "${batch}"
mkdir -p "${batch}"
fail=0
for ((i = 0; i < runs; i++)); do
  seed=$((seed_start + i))
  echo "[sitl_batch] run $((i + 1))/${runs} seed=${seed}"
  if ! "${root}/scripts/sitl_run.sh" --scenario latency_hold --seed "${seed}" --headless; then
    echo "[sitl_batch] FAIL seed=${seed}" >&2
    fail=$((fail + 1))
    continue
  fi
  run_id="$(basename "$(readlink "${root}/results/latest")")"
  ln -sfn "../${run_id}" "${batch}/${run_id}"
  echo "${run_id}" >> "${batch}/runs.txt"
done
echo "[sitl_batch] complete fail=${fail} of ${runs}"
exit "$([[ ${fail} -eq 0 ]] && echo 0 || echo 1)"
