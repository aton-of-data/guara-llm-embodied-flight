#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Generate a hash-pinned requirements.lock on the CI Python (PYTHON_VERSION in
# versions.env). Run from a clone with Docker. The lock is third-party only:
# `pip install --require-hashes -r requirements.lock` then
# `pip install -e . --no-deps` (AC-52).
#
# The input file is written by Python so a `Package>=version` spec cannot be
# parsed as a bash redirection.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${root}/versions.env"

in="${root}/.requirements.in"
python3 - "${root}" "${in}" <<'PY'
import pathlib, sys
root, dest = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
pins = {}
for raw in (root / "versions.env").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    pins[key] = value.strip().strip("'\"")
keys = ("PY_PYYAML", "PY_JSONSCHEMA", "PY_PYTEST", "PY_PYULOG")
dest.write_text("\n".join(pins[k] for k in keys) + "\n", encoding="utf-8")
PY
trap 'rm -f "${in}"' EXIT

image="python:${PYTHON_VERSION}-slim"
echo "locking with ${image}" >&2
docker run --rm -v "${root}:/src" -w /src "${image}" bash -ceu '
  pip install -q "pip-tools>=7.4"
  pip-compile --generate-hashes --strip-extras --output-file=requirements.lock .requirements.in
  pip install --require-hashes -r requirements.lock
'
echo "wrote ${root}/requirements.lock"
