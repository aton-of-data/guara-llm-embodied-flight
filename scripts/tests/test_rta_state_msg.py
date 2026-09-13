#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""G-K8: RtaState names the linked kernel and the loaded parameter digest."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MSG = ROOT / "ros2_ws/src/guara_msgs/msg/RtaState.msg"


def test_rta_state_carries_core_identity_and_param_digest():
    text = MSG.read_text(encoding="utf-8")
    assert "string core_version" in text
    assert "string abi_version" in text
    assert "uint8[8] param_digest" in text
