#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run one SITL scenario twice (RTA geofence on, then off) and point results/latest_pair at both.
# Usage: ./scripts/sitl_pair.sh --scenario <name> --seed <int>
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scenario=""
seed=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario) scenario="$2"; shift 2 ;;
    --seed) seed="$2"; shift 2 ;;
    *) echo "usage: $0 --scenario <name> --seed <int>" >&2; exit 2 ;;
  esac
done
[[ -n "${scenario}" && -n "${seed}" ]] || { echo "usage: $0 --scenario <name> --seed <int>" >&2; exit 2; }

cd "${root}"
./scripts/sitl_run.sh --scenario "${scenario}" --seed "${seed}" --headless --run-suffix _rta_on
on_id="$(readlink results/latest)"
# The predictor and its input channel are switched together: since the review of 2026-09-11 the
# arbiter refuses a configuration in which only one of the two is set (finding H-5).
./scripts/sitl_run.sh --scenario "${scenario}" --seed "${seed}" --headless --run-suffix _rta_off \
  --param geofence.enabled:=false --param inputs.geofence.enabled:=false
off_id="$(readlink results/latest)"

pair_id="$(date -u +%Y%m%dT%H%M%SZ)_${scenario}_s${seed}_pair"
pair_dir="${root}/results/${pair_id}"
mkdir -p "${pair_dir}"
ln -sfn "../${on_id}" "${pair_dir}/rta_on"
ln -sfn "../${off_id}" "${pair_dir}/rta_off"
cat > "${pair_dir}/pair.yaml" <<EOF
scenario: ${scenario}
seed: ${seed}
rta_on: ${on_id}
rta_off: ${off_id}
EOF
ln -sfn "${pair_id}" "${root}/results/latest_pair"
echo "pair ${pair_id}  on=${on_id}  off=${off_id}"
