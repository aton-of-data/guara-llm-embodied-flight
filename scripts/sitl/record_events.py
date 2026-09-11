#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Record /guara/rta/event to JSONL for AC checkers (runs inside the SITL container)."""
from __future__ import annotations

import json
import sys

import rclpy
from guara_msgs.msg import RtaEvent


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: record_events.py <path.jsonl>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    out = open(path, "a", encoding="utf-8")
    rclpy.init()
    node = rclpy.create_node("guara_event_recorder")

    def on_msg(msg: RtaEvent) -> None:
        rec = {
            "tick": int(msg.tick),
            "transition": int(msg.transition),
            "state_from": int(msg.state_from),
            "state_to": int(msg.state_to),
            "rf_to": int(msg.rf_to),
            "cause_mask": int(msg.cause_mask),
            "t_decide_s": float(msg.t_decide_s),
            "t_input_recv_s": float(msg.t_input_recv_s),
        }
        out.write(json.dumps(rec) + "\n")
        out.flush()

    node.create_subscription(RtaEvent, "/guara/rta/event", on_msg, 64)
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
