# SPDX-License-Identifier: Apache-2.0
"""Independent Python port of GatewayLogic (ADR 0010 / M19).

Does not import `core/` or the C ABI. Written from the ADR and the published
vectors; SPEC §3 does not specify the gateway envelope.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

PI = math.pi
CF = 1


@dataclass
class GatewayLimits:
    max_speed_h_m_s: float = 5.0
    max_climb_rate_m_s: float = 3.0
    max_descent_rate_m_s: float = 2.0
    max_yaw_rate_rad_s: float = 1.0
    future_stamp_tolerance_s: float = 0.05
    cf_timeout_s: float = 0.5


def validate_gateway_limits(limits: GatewayLimits) -> str | None:
    if not (limits.cf_timeout_s > 0.0):
        return "cf_timeout_s must be > 0"
    if not (limits.max_speed_h_m_s > 0.0):
        return "max_speed_h_m_s must be > 0"
    if not (limits.max_climb_rate_m_s > 0.0):
        return "max_climb_rate_m_s must be > 0"
    if not (limits.max_descent_rate_m_s > 0.0):
        return "max_descent_rate_m_s must be > 0"
    if not (limits.max_yaw_rate_rad_s > 0.0):
        return "max_yaw_rate_rad_s must be > 0"
    if not (limits.future_stamp_tolerance_s >= 0.0):
        return "future_stamp_tolerance_s must be >= 0"
    return None


GUARD_NAMES = ("OFF", "ALLOW", "DENY")


def gateway_guard_name(code: int) -> str:
    n = int(code)
    if 0 <= n < len(GUARD_NAMES):
        return GUARD_NAMES[n]
    return "UNKNOWN"


@dataclass
class GatewayOutput:
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    yaw: float = math.nan
    forwarding_cf: int = 0
    rejected_non_finite: int = 0
    rejected_stamp: int = 0
    rejected_yaw: int = 0
    rejected_guard: int = 0
    clamped: int = 0


@dataclass
class ReferenceGateway:
    limits: GatewayLimits = field(default_factory=GatewayLimits)
    state: int = 0
    t_enter_cf_s: float = math.inf
    have_cf: bool = False
    t_recv_s: float = -math.inf
    cf_vx: float = 0.0
    cf_vy: float = 0.0
    cf_vz: float = 0.0
    cf_yaw: float = math.nan
    yaw_cmd: float = math.nan
    t_yaw_s: float = math.nan
    guard_mode: int = 0  # 0 off, 1 allow, 2 deny
    rejected_non_finite: int = 0
    rejected_stamp: int = 0
    rejected_yaw: int = 0
    rejected_guard: int = 0
    clamped: int = 0

    def set_guard(self, mode: int) -> None:
        self.guard_mode = mode

    def limits_error(self, limits: GatewayLimits) -> str | None:
        return validate_gateway_limits(limits)

    def on_core_state(self, state: int, t_s: float) -> None:
        if state == CF and self.state != CF:
            self.t_enter_cf_s = t_s
            self.yaw_cmd = math.nan
            self.t_yaw_s = math.nan
        self.state = state

    def on_cf_setpoint(self, t_recv_s: float, stamp_s: float, v: tuple[float, float, float],
                       yaw: float) -> None:
        if any(not math.isfinite(x) for x in v):
            self.rejected_non_finite += 1
            return
        timeout = self.limits.cf_timeout_s
        if (not math.isfinite(stamp_s) or not math.isfinite(t_recv_s) or
                stamp_s > t_recv_s + self.limits.future_stamp_tolerance_s or
                t_recv_s - stamp_s > timeout):
            self.rejected_stamp += 1
            return
        self.cf_vx, self.cf_vy, self.cf_vz = self._clamp(v)
        if math.isfinite(yaw) and abs(yaw) <= PI + 1e-3:
            self.cf_yaw = yaw
        else:
            if math.isfinite(yaw):
                self.rejected_yaw += 1
            self.cf_yaw = math.nan
        self.t_recv_s = t_recv_s
        self.have_cf = True

    def compute(self, t_s: float) -> GatewayOutput:
        out = GatewayOutput(
            rejected_non_finite=self.rejected_non_finite,
            rejected_stamp=self.rejected_stamp,
            rejected_yaw=self.rejected_yaw,
            rejected_guard=self.rejected_guard,
            clamped=self.clamped,
        )
        fresh = (self.have_cf and self.t_recv_s > self.t_enter_cf_s and
                 t_s - self.t_recv_s <= self.limits.cf_timeout_s)
        if self.state != CF or not fresh:
            return out
        if self.guard_mode == 2:
            self.rejected_guard += 1
            out.rejected_guard = self.rejected_guard
            return out
        out.vx, out.vy, out.vz = self.cf_vx, self.cf_vy, self.cf_vz
        out.yaw = self._slew_yaw(t_s)
        out.forwarding_cf = 1
        return out

    def _clamp(self, v: tuple[float, float, float]) -> tuple[float, float, float]:
        vx, vy, vz = v
        changed = False
        speed = math.hypot(vx, vy)
        if speed > self.limits.max_speed_h_m_s and speed > 0.0:
            scale = self.limits.max_speed_h_m_s / speed
            vx *= scale
            vy *= scale
            changed = True
        lo = -self.limits.max_climb_rate_m_s
        hi = self.limits.max_descent_rate_m_s
        if vz < lo:
            vz = lo
            changed = True
        elif vz > hi:
            vz = hi
            changed = True
        if changed:
            self.clamped += 1
        return vx, vy, vz

    def _slew_yaw(self, t_s: float) -> float:
        if not math.isfinite(self.cf_yaw):
            self.yaw_cmd = math.nan
            self.t_yaw_s = t_s
            return math.nan
        if not math.isfinite(self.yaw_cmd) or not math.isfinite(self.t_yaw_s):
            self.yaw_cmd = self.cf_yaw
        else:
            dt = max(0.0, t_s - self.t_yaw_s)
            max_step = self.limits.max_yaw_rate_rad_s * dt
            error = self.cf_yaw - self.yaw_cmd
            while error > PI:
                error -= 2.0 * PI
            while error < -PI:
                error += 2.0 * PI
            error = min(max_step, max(-max_step, error))
            self.yaw_cmd += error
            while self.yaw_cmd > PI:
                self.yaw_cmd -= 2.0 * PI
            while self.yaw_cmd < -PI:
                self.yaw_cmd += 2.0 * PI
        self.t_yaw_s = t_s
        return self.yaw_cmd
