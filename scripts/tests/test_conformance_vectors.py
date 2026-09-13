#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M19: the published SPEC §3 vectors name every kernel transition."""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
VECTORS = ROOT / "core/conformance/vectors/spec_s3.json"


def test_spec_s3_vectors_cover_every_kernel_transition():
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    ids = [v["id"] for v in data]
    assert len(ids) == len(set(ids))
    seen: set[int] = set()
    for vec in data:
        for step in vec["steps"]:
            if step.get("action") == "latch":
                seen.add(9)
            trans = step.get("expect", {}).get("transition")
            if trans:
                seen.add(int(trans))
    assert seen == {1, 2, 3, 4, 5, 6, 7, 8, 9}
    assert "hysteresis_band_blocks_return" in ids
    assert "t5_blocked_by_cf_intent" in ids


def test_conformance_readme_states_necessary_not_sufficient():
    text = (ROOT / "core/conformance/README.md").read_text(encoding="utf-8")
    assert "necessary and not sufficient" in text
    assert "C ABI" in text


def test_adr0010_vectors_cover_trusted_time_envelope_and_shadow():
    data = json.loads(
        (ROOT / "core/conformance/vectors/adr0010_gateway.json").read_text(encoding="utf-8")
    )
    ids = {v["id"] for v in data}
    assert "future_stamp_rejected" in ids
    assert "age_from_reception" in ids
    assert "velocity_clamped" in ids
    assert "non_finite_rejected" in ids
    assert "shadow_guard_blocks" in ids
    tags = {tag for v in data for tag in v.get("adr", [])}
    assert tags == {"0010-1", "0010-2", "0010-3"}
