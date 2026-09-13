#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Record RtaEvent and RtaState JSONL for M7 latency stages (runs inside the SITL container)."""
from __future__ import annotations

import json
import math
import sys

import rclpy
from guara_msgs.msg import RtaEvent, RtaState


def _f(value: float) -> float | None:
    return None if not math.isfinite(value) else float(value)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: record_latency.py <events.jsonl> <states.jsonl>", file=sys.stderr)
        return 2
    events_path, states_path = sys.argv[1], sys.argv[2]
    events_out = open(events_path, "a", encoding="utf-8")
    states_out = open(states_path, "a", encoding="utf-8")
    rclpy.init()
    node = rclpy.create_node("guara_latency_recorder")

    def on_event(msg: RtaEvent) -> None:
        rec = {
            "tick": int(msg.tick),
            "transition": int(msg.transition),
            "state_from": int(msg.state_from),
            "state_to": int(msg.state_to),
            "rf_to": int(msg.rf_to),
            "cause_mask": int(msg.cause_mask),
            "t_decide_s": _f(msg.t_decide_s),
            "t_input_recv_s": _f(msg.t_input_recv_s),
            "t_input_stamp_s": _f(msg.t_input_stamp_s),
            "t_px4_timestamp_s": _f(msg.t_px4_timestamp_s),
            "t_ros_recv_s": _f(msg.t_ros_recv_s),
            "t_cmd_pub_s": _f(msg.t_cmd_pub_s),
            "t_cmd_pub_ros_s": _f(msg.t_cmd_pub_ros_s),
            "t_ack_s": _f(msg.t_ack_s),
            "l0_s": _f(msg.l0_s),
            "clock_err_s": _f(msg.clock_err_s),
            "l2_s": _f(msg.l2_s),
            "l3_s": _f(msg.l3_s),
            "monitor_id": msg.monitor_id,
        }
        events_out.write(json.dumps(rec) + "\n")
        events_out.flush()

    def on_state(msg: RtaState) -> None:
        rec = {
            "tick": int(msg.tick),
            "t_s": _f(msg.t_s),
            "state": int(msg.state),
            "t_last_ack_s": _f(msg.t_last_ack_s),
            "l0_s": _f(msg.l0_s),
            "clock_err_s": _f(msg.clock_err_s),
            "t_px4_timestamp_s": _f(msg.t_px4_timestamp_s),
            "t_ros_recv_s": _f(msg.t_ros_recv_s),
            "core_version": msg.core_version,
            "abi_version": msg.abi_version,
            "param_digest": bytes(msg.param_digest).hex(),
        }
        states_out.write(json.dumps(rec) + "\n")
        states_out.flush()

    node.create_subscription(RtaEvent, "/guara/rta/event", on_event, 64)
    node.create_subscription(RtaState, "/guara/rta/state", on_state, 32)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        events_out.close()
        states_out.close()
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
