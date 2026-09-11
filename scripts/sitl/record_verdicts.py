#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Record /guara/monitors/verdict to JSONL for AC checkers (runs inside the SITL container)."""
from __future__ import annotations

import json
import sys

import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from guara_msgs.msg import MonitorVerdict


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: record_verdicts.py <path.jsonl>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    out = open(path, "a", encoding="utf-8")
    rclpy.init()
    node = rclpy.create_node("guara_verdict_recorder")
    qos = QoSProfile(depth=32, reliability=ReliabilityPolicy.BEST_EFFORT,
                     history=HistoryPolicy.KEEP_LAST)

    def on_msg(msg: MonitorVerdict) -> None:
        rec = {
            "monitor_id": msg.monitor_id,
            "violated": bool(msg.violated),
            "inputs_complete": bool(msg.inputs_complete),
            "step": int(msg.step),
            "monitor_class": int(msg.monitor_class),
            "action": int(msg.action),
        }
        out.write(json.dumps(rec) + "\n")
        out.flush()

    node.create_subscription(MonitorVerdict, "/guara/monitors/verdict", on_msg, qos)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        out.close()
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
