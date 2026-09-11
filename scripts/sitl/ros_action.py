#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One-shot ROS 2 actions for SITL scenarios (user mode switch, monitor injection)."""
from __future__ import annotations

import argparse
import sys
import time

import rclpy
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from guara_msgs.msg import CfSetpoint, MonitorVerdict, RtaState
from px4_msgs.msg import VehicleCommand, VehicleStatus

# Topic suffixes follow message MESSAGE_VERSION (GROUNDING 3.5): command v0, status v1.
CMD_TOPIC = "fmu/in/vehicle_command"
STATUS_TOPIC = "fmu/out/vehicle_status_v1"


def init():
    rclpy.init()
    return rclpy.create_node("guara_sitl_action")


def set_nav_state(nav: int, repeats: int = 5) -> None:
    node = init()
    topic = CMD_TOPIC
    pub = node.create_publisher(VehicleCommand, topic, 1)
    time.sleep(0.3)
    for _ in range(repeats):
        cmd = VehicleCommand()
        cmd.command = VehicleCommand.VEHICLE_CMD_SET_NAV_STATE
        cmd.param1 = float(nav)
        cmd.param2 = cmd.param3 = cmd.param4 = cmd.param7 = float("nan")
        cmd.param5 = cmd.param6 = float("nan")
        cmd.from_external = True
        cmd.source_system = 1
        cmd.source_component = 1
        cmd.target_system = 1
        cmd.target_component = 1
        pub.publish(cmd)
        rclpy.spin_once(node, timeout_sec=0.1)
        time.sleep(0.2)
    node.destroy_node()
    rclpy.shutdown()


def inject_verdict(monitor_id: str, duration_s: float) -> None:
    node = init()
    qos = QoSProfile(depth=32, reliability=ReliabilityPolicy.BEST_EFFORT,
                     history=HistoryPolicy.KEEP_LAST)
    pub = node.create_publisher(MonitorVerdict, "/guara/monitors/verdict", qos)
    time.sleep(0.3)
    deadline = time.monotonic() + duration_s
    step = 0
    while time.monotonic() < deadline:
        msg = MonitorVerdict()
        msg.stamp = node.get_clock().now().to_msg()
        msg.monitor_id = monitor_id
        msg.monitor_class = MonitorVerdict.CLASS_SWITCH
        msg.action = MonitorVerdict.ACTION_HOLD
        msg.violated = True
        msg.inputs_complete = True
        msg.step = step
        pub.publish(msg)
        step += 1
        rclpy.spin_once(node, timeout_sec=0.05)
        time.sleep(0.1)
    node.destroy_node()
    rclpy.shutdown()


def inject_cf(vn: float, ve: float, vd: float, duration_s: float) -> None:
    node = init()
    qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                     history=HistoryPolicy.KEEP_LAST)
    pub = node.create_publisher(CfSetpoint, "/guara/cf/setpoint", qos)
    time.sleep(0.3)
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline:
        msg = CfSetpoint()
        msg.stamp = node.get_clock().now().to_msg()
        msg.velocity_ned_m_s = [float(vn), float(ve), float(vd)]
        msg.yaw_ned_rad = float("nan")
        pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.05)
        time.sleep(0.1)
    node.destroy_node()
    rclpy.shutdown()


def wait_nav(want: int, timeout_s: float) -> int:
    node = init()
    got = {"v": None}
    topic = STATUS_TOPIC
    node.create_subscription(
        VehicleStatus, topic, lambda m: got.__setitem__("v", int(m.nav_state)),
        QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                   history=HistoryPolicy.KEEP_LAST))
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)
        if got["v"] == want:
            node.destroy_node()
            rclpy.shutdown()
            return 0
    node.destroy_node()
    rclpy.shutdown()
    print(f"timeout waiting for nav_state={want}, last={got['v']}", file=sys.stderr)
    return 1


def wait_rta(state: int, timeout_s: float) -> int:
    node = init()
    got = {"v": None}
    node.create_subscription(
        RtaState, "/guara/rta/state", lambda m: got.__setitem__("v", int(m.state)), 10)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)
        if got["v"] == state:
            node.destroy_node()
            rclpy.shutdown()
            return 0
    node.destroy_node()
    rclpy.shutdown()
    print(f"timeout waiting for RtaState.state={state}, last={got['v']}", file=sys.stderr)
    return 1


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set-nav-state")
    s.add_argument("nav", type=int)
    i = sub.add_parser("inject-verdict")
    i.add_argument("monitor_id")
    i.add_argument("--duration", type=float, default=3.0)
    c = sub.add_parser("inject-cf")
    c.add_argument("vn", type=float)
    c.add_argument("ve", type=float)
    c.add_argument("vd", type=float)
    c.add_argument("--duration", type=float, default=10.0)
    w = sub.add_parser("wait-nav")
    w.add_argument("nav", type=int)
    w.add_argument("--timeout", type=float, default=15.0)
    r = sub.add_parser("wait-rta")
    r.add_argument("state", type=int)
    r.add_argument("--timeout", type=float, default=15.0)
    args = p.parse_args()
    if args.cmd == "set-nav-state":
        set_nav_state(args.nav)
        return 0
    if args.cmd == "inject-verdict":
        inject_verdict(args.monitor_id, args.duration)
        return 0
    if args.cmd == "inject-cf":
        inject_cf(args.vn, args.ve, args.vd, args.duration)
        return 0
    if args.cmd == "wait-nav":
        return wait_nav(args.nav, args.timeout)
    if args.cmd == "wait-rta":
        return wait_rta(args.state, args.timeout)
    return 2


if __name__ == "__main__":
    sys.exit(main())
