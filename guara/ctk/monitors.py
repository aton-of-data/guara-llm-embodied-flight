# SPDX-License-Identifier: Apache-2.0
"""Independent Python port of MonitorTable (SPEC §3.1 / ADR 0002).

Does not import `core/` or the C ABI.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

MAX_MONITORS = 16
ID_CAPACITY = 47
CLASS_LOG = 0
CLASS_SWITCH = 1
CLASS_MAX = CLASS_SWITCH
ACTION_MAX = 2
HOLD = 1

ACCEPTED = 0
INVALID_FIELD = 1
TABLE_FULL = 2

CLASS_NAMES = ("LOG", "SWITCH")
ACTION_NAMES = ("HOLD", "RTL", "LAND")
ACCEPT_NAMES = ("ACCEPTED", "INVALID_FIELD", "TABLE_FULL")


def monitor_class_name(code: int) -> str:
    n = int(code)
    if 0 <= n < len(CLASS_NAMES):
        return CLASS_NAMES[n]
    return "UNKNOWN"


def monitor_action_name(code: int) -> str:
    n = int(code)
    if 0 <= n < len(ACTION_NAMES):
        return ACTION_NAMES[n]
    return "UNKNOWN"


def monitor_accept_name(code: int) -> str:
    n = int(code)
    if 0 <= n < len(ACCEPT_NAMES):
        return ACCEPT_NAMES[n]
    return "UNKNOWN"


@dataclass
class MonitorEval:
    violation: int = 0
    action: int = HOLD
    invalid: int = 0
    first_violating_id: str = ""
    first_invalid_id: str = ""


@dataclass
class _Slot:
    ident: str = ""
    used: bool = False
    expected: bool = False
    malformed: bool = False
    violated: bool = False
    inputs_complete: bool = False
    monitor_class: int = CLASS_LOG
    action: int = HOLD
    t_recv_s: float = -math.inf


@dataclass
class ReferenceMonitor:
    max_age_s: float = 0.5
    slots: list[_Slot] = field(default_factory=lambda: [_Slot() for _ in range(MAX_MONITORS)])
    overflow: bool = False
    malformed: bool = False

    def expect(self, ident: str) -> int:
        slot = self._slot_for(ident, create=True)
        if slot is None:
            return TABLE_FULL if self._fits(ident) else INVALID_FIELD
        slot.expected = True
        return ACCEPTED

    def observe(self, ident: str, monitor_class: int, action: int, violated: int,
                complete: int, t_recv_s: float) -> int:
        if ident is None or not self._fits(ident):
            self.malformed = True
            return INVALID_FIELD
        slot = self._slot_for(ident, create=True)
        if slot is None:
            self.overflow = True
            return TABLE_FULL
        slot.t_recv_s = t_recv_s
        if monitor_class > CLASS_MAX or action > ACTION_MAX:
            slot.malformed = True
            slot.violated = False
            slot.inputs_complete = False
            return INVALID_FIELD
        slot.malformed = False
        slot.monitor_class = monitor_class
        slot.action = action + 1
        slot.violated = bool(violated)
        slot.inputs_complete = bool(complete)
        return ACCEPTED

    def evaluate(self, t_s: float) -> MonitorEval:
        out = MonitorEval(invalid=1 if self.overflow or self.malformed else 0)
        for s in self.slots:
            if not s.used:
                continue
            seen = s.t_recv_s > -math.inf
            stale = (not seen) or (t_s - s.t_recv_s > self.max_age_s)
            if s.expected and (stale or s.malformed or not s.inputs_complete):
                out.invalid = 1
                if not out.first_invalid_id:
                    out.first_invalid_id = s.ident
            elif s.malformed:
                out.invalid = 1
                if not out.first_invalid_id:
                    out.first_invalid_id = s.ident
            if (not stale and not s.malformed and s.violated and
                    s.monitor_class == CLASS_SWITCH):
                if not out.violation:
                    out.first_violating_id = s.ident
                    out.action = s.action
                else:
                    out.action = max(out.action, s.action)
                out.violation = 1
        return out

    def _fits(self, ident: str) -> bool:
        return bool(ident) and len(ident) <= ID_CAPACITY

    def _slot_for(self, ident: str, create: bool) -> _Slot | None:
        if not self._fits(ident):
            return None
        for s in self.slots:
            if s.used and s.ident == ident:
                return s
        if not create:
            return None
        for s in self.slots:
            if not s.used:
                s.used = True
                s.ident = ident
                return s
        return None
