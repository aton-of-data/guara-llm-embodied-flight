#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""G-K8: host YAML is schema-checked and hashed with the kernel encoding."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return env


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "guara", "params", *args],
        cwd=str(ROOT), capture_output=True, text=True, env=_env(),
    )


def test_default_digest_matches_the_c_golden():
    sys.path.insert(0, str(ROOT))
    from guara.params import DEFAULT_DIGEST_HEX, digest_core

    core = {
        "core.tau_daa_s": 30.0,
        "core.tau_gf_s": 1.0,
        "core.h_daa_s": 5.0,
        "core.h_gf_s": 1.0,
        "core.dwell_s": 5.0,
        "core.n_max": 3,
        "core.window_s": 120.0,
        "core.return_enabled": True,
        "core.escalation_enabled": False,
        "core.escalation_s": 30.0,
    }
    assert digest_core(core).hex() == DEFAULT_DIGEST_HEX


def test_sitl_and_flight_files_validate():
    sitl = _cli("check", "config/rta_params.yaml")
    assert sitl.returncode == 0, sitl.stderr
    assert "digest=c9f82e52ea1d4469" in sitl.stdout
    assert "core=0.17.0-dev" in sitl.stdout
    assert "safe" not in (sitl.stdout + sitl.stderr).lower()

    flight = _cli("check", "config/rta_params_flight.yaml")
    assert flight.returncode == 0, flight.stderr
    assert "digest=" in flight.stdout
    assert "c9f82e52ea1d4469" not in flight.stdout  # escalation_enabled differs


def test_missing_core_field_is_refused(tmp_path):
    src = yaml.safe_load((ROOT / "config/rta_params.yaml").read_text())
    del src["guara_rta"]["ros__parameters"]["core.tau_daa_s"]
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(src), encoding="utf-8")
    r = _cli("check", str(bad))
    assert r.returncode == 1
    assert "FAIL params" in r.stderr
    assert "core.tau_daa_s" in r.stderr


def test_n_max_zero_is_refused(tmp_path):
    src = yaml.safe_load((ROOT / "config/rta_params.yaml").read_text())
    src["guara_rta"]["ros__parameters"]["core.n_max"] = 0
    bad = tmp_path / "zero.yaml"
    bad.write_text(yaml.safe_dump(src), encoding="utf-8")
    r = _cli("check", str(bad))
    assert r.returncode == 1
    assert "n_max" in r.stderr


def test_schema_file_is_draft_2020_12():
    import json
    import jsonschema

    schema = json.loads((ROOT / "config/rta_params.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)


def test_header_field_order_matches_core_keys():
    text = (ROOT / "core/include/guara/guara.h").read_text()
    block = text.split("typedef struct guara_params {", 1)[1].split("}", 1)[0]
    names = []
    for line in block.splitlines():
        line = line.strip().rstrip(";")
        if not line:
            continue
        names.append("core." + line.split()[-1])
    sys.path.insert(0, str(ROOT))
    from guara.params import CORE_KEYS
    assert tuple(names) == CORE_KEYS
