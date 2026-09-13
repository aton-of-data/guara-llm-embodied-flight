#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# AC-64: a geofence port that ignores the uncertainty band must be rejected.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

cp -R "${root}/guara" "${tmp}/guara"
python="${PYTHON:-python3}"
"${python}" - "${tmp}/guara/ctk/geofence.py" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = "        if lateral > 0.0 and self._boundary_distance(pos) <= lateral:"
new = "        if False and lateral > 0.0 and self._boundary_distance(pos) <= lateral:"
if old not in text:
    raise SystemExit("FAIL ctk_mutation_geofence: mutation site not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY

set +e
"${python}" - "${tmp}" "${root}" <<'PY'
import sys
from pathlib import Path

tmp = Path(sys.argv[1]).resolve()
root = Path(sys.argv[2]).resolve()
cleaned = []
for p in sys.path:
    if p in ("", "."):
        continue
    try:
        if Path(p).resolve() == root:
            continue
    except OSError:
        pass
    cleaned.append(p)
sys.path = [str(tmp)] + cleaned
from guara.ctk import run as ctk
sys.exit(ctk.run([
    "run", "--port", "python",
    "--vectors", str(root / "core/conformance/vectors/geofence.json"),
]))
PY
rc=$?
set -e
if [[ "${rc}" -eq 0 ]]; then
  echo "FAIL ctk_mutation_geofence: kit accepted a port with the uncertainty band disabled" >&2
  exit 1
fi
echo "PASS ctk_mutation_geofence: uncertainty-band-disabled Python port rejected (exit ${rc})"
exit 0
