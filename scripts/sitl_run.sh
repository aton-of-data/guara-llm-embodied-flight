#!/usr/bin/env bash
# Run one headless PX4 SITL (SIH) scenario and write results/{run_id}/ (SPEC §6, AC-2).
# Usage: ./scripts/sitl_run.sh --scenario <name> --seed <int> --headless
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${root}/scripts/dev.sh" python3 scripts/sitl/run_scenario.py "$@"
