#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M18: the kernel coding-subset statement exists and does not overclaim."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOC = ROOT / "core/CODING_SUBSET.md"


def test_coding_subset_is_review_not_a_qualification():
    text = DOC.read_text(encoding="utf-8")
    assert "[REVIEW]" in text
    assert "C++17" in text
    assert "placement-new" in text or "placement new" in text
    assert "MISRA" in text
    assert "qualification" in text.lower()
    lower = text.lower()
    assert "compliant" not in lower
    assert "certified" not in lower
