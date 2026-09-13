#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Copies the figures the project site displays out of docs/assets/, which is where they are
# generated and reviewed. The site does not keep its own copies: a duplicated evidence figure
# is a figure that can drift from the run it was plotted from, and the site itself makes that
# argument about geofence polygons.
#
# Run before previewing site/ locally; the pages workflow runs it before deploying.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="$root/docs/assets"
dst="$root/site/assets"

mkdir -p "$dst"
for f in guara-mascot.png guara-mascot-air.png latency-distribution.svg geofence-rta-pair.svg; do
  cp "$src/$f" "$dst/$f"
  echo "site/assets/$f <- docs/assets/$f"
done
