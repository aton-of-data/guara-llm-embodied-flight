# SPDX-License-Identifier: Apache-2.0
"""Independent Python port of SPEC §3, written for the conformance kit (M19 / AC-65).

This module does not import `core/` or the C ABI. Where SPEC §3 is silent and the
published vectors require a choice, the choice is listed in SPEC §3.6.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geofence import polygon_error_name
from .gateway import gateway_guard_name
from .monitors import monitor_accept_name, monitor_action_name, monitor_class_name

INACTIVE, CF, RF, LATCHED = 0, 1, 2, 3
NONE, HOLD, RTL, LAND = 0, 1, 2, 3
CMD_NONE, CMD_HOLD, CMD_RTL, CMD_LAND, CMD_OWNED = 0, 1, 2, 3, 4
T_NONE, T1, T2, T3, T4, T5, T6, T7, T2B, T_ACTUATION = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9

CAUSE_DAA = 1 << 0
CAUSE_GF = 1 << 1
CAUSE_MONITOR = 1 << 2
CAUSE_INPUT = 1 << 3
CAUSE_LATCH = 1 << 4
CAUSE_RETURN = 1 << 5
CAUSE_NOT_IN_CHARGE = 1 << 6
CAUSE_ESCALATION = 1 << 7
CAUSE_ACTUATION = 1 << 8

SWITCH_HISTORY_CAPACITY = 32
TIME_EPS_S = 1e-9

STATE_NAMES = ("INACTIVE", "CF", "RF", "LATCHED")
RECOVERY_NAMES = ("NONE", "HOLD", "RTL", "LAND")
COMMAND_NAMES = ("NONE", "HOLD", "RTL", "LAND", "OWNED_MODE")
TRANSITION_NAMES = ("NONE", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T2B", "ACTUATION")
CAUSE_NAMES = {
    0: "NONE",
    CAUSE_DAA: "DAA",
    CAUSE_GF: "GEOFENCE",
    CAUSE_MONITOR: "MONITOR",
    CAUSE_INPUT: "INPUT",
    CAUSE_LATCH: "LATCH",
    CAUSE_RETURN: "RETURN",
    CAUSE_NOT_IN_CHARGE: "NOT_IN_CHARGE",
    CAUSE_ESCALATION: "ESCALATION",
    CAUSE_ACTUATION: "ACTUATION",
}
ERR_NAMES = ("OK", "NULL", "STORAGE", "PARAMS", "UNINIT")


def vocabulary_name(kind: str, code: int) -> str:
    n = int(code)
    if kind == "cause":
        return CAUSE_NAMES.get(n, "UNKNOWN")
    if kind == "polygon":
        return polygon_error_name(n)
    if kind == "monitor_class":
        return monitor_class_name(n)
    if kind == "monitor_action":
        return monitor_action_name(n)
    if kind == "monitor_accept":
        return monitor_accept_name(n)
    if kind == "err":
        if 0 <= n < len(ERR_NAMES):
            return ERR_NAMES[n]
        return "UNKNOWN"
    if kind == "guard":
        return gateway_guard_name(n)
    table = {
        "state": STATE_NAMES,
        "recovery": RECOVERY_NAMES,
        "command": COMMAND_NAMES,
        "transition": TRANSITION_NAMES,
    }.get(kind)
    if table is None:
        return "UNKNOWN"
    if 0 <= n < len(table):
        return table[n]
    return "UNKNOWN"


def command_for(recovery: int) -> int:
    return {HOLD: CMD_HOLD, RTL: CMD_RTL, LAND: CMD_LAND}.get(recovery, CMD_NONE)


@dataclass
class Params:
    tau_daa_s: float = 30.0
    tau_gf_s: float = 1.0
    h_daa_s: float = 5.0
    h_gf_s: float = 1.0
    dwell_s: float = 5.0
    n_max: int = 3
    window_s: float = 120.0
    return_enabled: bool = True
    escalation_enabled: bool = False
    escalation_s: float = 30.0


def validate_params(p: Params) -> str | None:
    def finite_non_negative(v: float) -> bool:
        return math.isfinite(v) and v >= 0.0

    if not finite_non_negative(p.tau_daa_s):
        return "tau_daa_s must be finite and >= 0"
    if not finite_non_negative(p.tau_gf_s):
        return "tau_gf_s must be finite and >= 0"
    if not finite_non_negative(p.h_daa_s):
        return "h_daa_s must be finite and >= 0"
    if not finite_non_negative(p.h_gf_s):
        return "h_gf_s must be finite and >= 0"
    if not finite_non_negative(p.dwell_s):
        return "dwell_s must be finite and >= 0"
    if not (math.isfinite(p.window_s) and p.window_s > 0.0):
        return "window_s must be finite and > 0"
    if int(p.n_max) == 0:
        return "n_max must be >= 1"
    if int(p.n_max) > SWITCH_HISTORY_CAPACITY:
        return "n_max exceeds kSwitchHistoryCapacity"
    if not (math.isfinite(p.escalation_s) and p.escalation_s > 0.0):
        return "escalation_s must be finite and > 0"
    return None


@dataclass
class Inputs:
    t_s: float = 0.0
    in_charge: int = 0
    owned_mode_active: int = 0
    t_daa_s: float = math.inf
    t_gf_s: float = math.inf
    monitor_violation: int = 0
    monitor_action: int = HOLD
    input_invalid: int = 0
    cf_intent_unsafe: int = 0


@dataclass
class Output:
    state: int = INACTIVE
    recovery: int = NONE
    command: int = CMD_NONE
    transition: int = T_NONE
    unsafe_causes: int = 0
    clear: bool = False
    clear_duration_s: float = 0.0
    switches_in_window: int = 0


@dataclass
class ReferenceCore:
    """SPEC §3.5 table, evaluated in row order, at most one transition per tick."""

    params: Params = field(default_factory=Params)
    state: int = INACTIVE
    recovery: int = NONE
    t_switch_s: float = -math.inf
    t_prev_s: float = -math.inf
    clear_since_s: float = math.nan
    unsafe_since_s: float = math.nan
    switch_times: list[float] = field(default_factory=list)

    def params_error(self, params: Params) -> str | None:
        return validate_params(params)

    def vocabulary_name(self, kind: str, code: int) -> str:
        return vocabulary_name(kind, code)

    def _switches(self, t_s: float) -> int:
        w = self.params.window_s
        n = 0
        for ts in self.switch_times:
            if ts > t_s - w:
                n += 1
        return n

    def _record_switch(self, t_s: float) -> None:
        self.switch_times.append(t_s)
        if len(self.switch_times) > SWITCH_HISTORY_CAPACITY:
            self.switch_times = self.switch_times[-SWITCH_HISTORY_CAPACITY:]

    def _causes(self, inp: Inputs, time_valid: bool) -> int:
        causes = 0
        if math.isnan(inp.t_daa_s) or math.isnan(inp.t_gf_s) or inp.input_invalid or not time_valid:
            causes |= CAUSE_INPUT
        if inp.t_daa_s <= self.params.tau_daa_s:
            causes |= CAUSE_DAA
        if inp.t_gf_s <= self.params.tau_gf_s:
            causes |= CAUSE_GF
        if inp.monitor_violation:
            causes |= CAUSE_MONITOR
        return causes

    def _clear(self, inp: Inputs, time_valid: bool) -> bool:
        p = self.params
        return (
            time_valid
            and not inp.input_invalid
            and not inp.monitor_violation
            and inp.t_daa_s > p.tau_daa_s + p.h_daa_s
            and inp.t_gf_s > p.tau_gf_s + p.h_gf_s
        )

    def _select(self, inp: Inputs, causes: int) -> int:
        r = NONE
        if causes & (CAUSE_INPUT | CAUSE_GF | CAUSE_DAA):
            r = HOLD
        if causes & CAUSE_MONITOR:
            action = HOLD if inp.monitor_action == NONE else inp.monitor_action
            r = action if action >= r else r
        p = self.params
        if (
            p.escalation_enabled
            and causes
            and not math.isnan(self.unsafe_since_s)
            and inp.t_s - self.unsafe_since_s > p.escalation_s
        ):
            r = LAND
        return r

    def step(self, inp: Inputs) -> Output:
        time_valid = math.isfinite(inp.t_s) and inp.t_s > self.t_prev_s
        causes = self._causes(inp, time_valid)
        unsafe = causes != 0
        clear = self._clear(inp, time_valid)
        if clear:
            if math.isnan(self.clear_since_s):
                self.clear_since_s = inp.t_s
        else:
            self.clear_since_s = math.nan
        if unsafe:
            if math.isnan(self.unsafe_since_s):
                self.unsafe_since_s = inp.t_s
        else:
            self.unsafe_since_s = math.nan
        if time_valid:
            self.t_prev_s = inp.t_s

        cdur = (inp.t_s - self.clear_since_s) if clear else 0.0
        switches = self._switches(inp.t_s)
        selected = self._select(inp, causes) if unsafe else NONE

        out = Output(unsafe_causes=causes, clear=clear, clear_duration_s=cdur)
        trans = T_NONE

        if not inp.in_charge:
            if self.state != INACTIVE:
                trans = T1
            self.state = INACTIVE
            self.recovery = NONE
        elif self.state == INACTIVE:
            if inp.owned_mode_active:
                if unsafe:
                    trans = T2B
                    self.state = RF
                    self.recovery = selected
                    self.t_switch_s = inp.t_s
                    self._record_switch(inp.t_s)
                    out.command = command_for(selected)
                else:
                    trans = T2
                    self.state = CF
        elif self.state == CF:
            if unsafe:
                trans = T3
                self.state = RF
                self.recovery = selected
                self.t_switch_s = inp.t_s
                self._record_switch(inp.t_s)
                out.command = command_for(selected)
        elif self.state == RF:
            p = self.params
            if switches >= p.n_max:
                trans = T4
                self.state = LATCHED
            elif (
                self.recovery == HOLD
                and clear
                and not inp.cf_intent_unsafe
                and cdur >= p.dwell_s - TIME_EPS_S
                and inp.t_s - self.t_switch_s >= p.dwell_s - TIME_EPS_S
                and p.return_enabled
            ):
                trans = T5
                self.state = CF
                self.recovery = NONE
                out.command = CMD_OWNED
            elif unsafe and selected > self.recovery:
                trans = T6
                self.recovery = selected
                out.command = command_for(selected)
        elif self.state == LATCHED:
            if unsafe and selected > self.recovery:
                trans = T7
                self.recovery = selected
                out.command = command_for(selected)

        out.state = self.state
        out.recovery = self.recovery
        out.switches_in_window = self._switches(inp.t_s)
        out.transition = trans
        return out

    def latch_on_actuation_failure(self, t_s: float) -> Output:
        out = Output(state=self.state, recovery=self.recovery,
                     switches_in_window=self._switches(t_s))
        if self.state == RF:
            self.state = LATCHED
            out.state = self.state
            out.transition = T_ACTUATION
        return out
