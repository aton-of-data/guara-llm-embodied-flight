#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# AC-64: a single injected behavioural mutation is detected by the kit.
# Disables T4 in a copy of the Python port; the published vectors must fail.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

cp -R "${root}/guara" "${tmp}/guara"
python="${PYTHON:-python3}"
"${python}" - "${tmp}/guara/ctk/reference.py" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = "            if switches >= p.n_max:"
new = "            if False and switches >= p.n_max:"
if old not in text:
    raise SystemExit("FAIL ctk_mutation: mutation site not found")
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
sys.exit(ctk.run(["run", "--port", "python"]))
PY
rc=$?
set -e
if [[ "${rc}" -eq 0 ]]; then
  echo "FAIL ctk_mutation: kit accepted a port with T4 disabled" >&2
  exit 1
fi
echo "PASS ctk_mutation: T4-disabled python port rejected (exit ${rc})"
exit 0
