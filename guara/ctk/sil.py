# SPDX-License-Identifier: Apache-2.0
"""SIL port: drive published vectors through the C ABI via ctypes (M19 / AC-64)."""
from __future__ import annotations

import ctypes
import math
import os
import sys
from ctypes import (
    POINTER,
    c_char_p,
    c_double,
    c_float,
    c_int,
    c_size_t,
    c_uint8,
    c_uint16,
    c_uint32,
    c_void_p,
)
from pathlib import Path

from .gateway import GatewayLimits, GatewayOutput
from .reference import Inputs, Output, Params

GUARA_OK = 0


class CParams(ctypes.Structure):
    _fields_ = [
        ("tau_daa_s", c_double),
        ("tau_gf_s", c_double),
        ("h_daa_s", c_double),
        ("h_gf_s", c_double),
        ("dwell_s", c_double),
        ("n_max", c_uint16),
        ("window_s", c_double),
        ("return_enabled", c_uint8),
        ("escalation_enabled", c_uint8),
        ("escalation_s", c_double),
    ]


class CInputs(ctypes.Structure):
    _fields_ = [
        ("t_s", c_double),
        ("in_charge", c_uint8),
        ("owned_mode_active", c_uint8),
        ("t_daa_s", c_double),
        ("t_gf_s", c_double),
        ("monitor_violation", c_uint8),
        ("monitor_action", c_uint8),
        ("input_invalid", c_uint8),
        ("cf_intent_unsafe", c_uint8),
    ]


class CTransition(ctypes.Structure):
    _fields_ = [
        ("id", c_uint8),
        ("frm", c_uint8),
        ("to", c_uint8),
        ("rf_from", c_uint8),
        ("rf_to", c_uint8),
        ("cause", c_uint32),
    ]


class COutput(ctypes.Structure):
    _fields_ = [
        ("state", c_uint8),
        ("recovery", c_uint8),
        ("command", c_uint8),
        ("transition", CTransition),
        ("unsafe_causes", c_uint32),
        ("clear", c_uint8),
        ("clear_duration_s", c_double),
        ("switches_in_window", c_uint16),
    ]


class CGatewayLimits(ctypes.Structure):
    _fields_ = [
        ("max_speed_h_m_s", c_double),
        ("max_climb_rate_m_s", c_double),
        ("max_descent_rate_m_s", c_double),
        ("max_yaw_rate_rad_s", c_double),
        ("future_stamp_tolerance_s", c_double),
        ("cf_timeout_s", c_double),
    ]


class CGatewayOutput(ctypes.Structure):
    _fields_ = [
        ("velocity_ned_m_s", c_float * 3),
        ("yaw_ned_rad", c_float),
        ("forwarding_cf", c_uint8),
        ("rejected_non_finite", c_uint32),
        ("rejected_implausible_stamp", c_uint32),
        ("rejected_yaw", c_uint32),
        ("rejected_by_guard", c_uint32),
        ("clamped", c_uint32),
    ]


class _Aligned:
    def __init__(self, size: int, align: int) -> None:
        align = max(int(align), 1)
        self._raw = (ctypes.c_ubyte * (size + align))()
        addr = ctypes.addressof(self._raw)
        self.addr = (addr + (align - 1)) & ~(align - 1)


def _bind(lib: ctypes.CDLL) -> ctypes.CDLL:
    lib.guara_core_storage_size.restype = c_size_t
    lib.guara_core_storage_align.restype = c_size_t
    lib.guara_core_version.restype = c_char_p
    lib.guara_abi_version.restype = c_char_p
    lib.guara_params_default.argtypes = [POINTER(CParams)]
    lib.guara_core_init.argtypes = [c_void_p, c_size_t, POINTER(CParams)]
    lib.guara_core_init.restype = c_int
    lib.guara_core_step.argtypes = [c_void_p, POINTER(CInputs), POINTER(COutput)]
    lib.guara_core_step.restype = c_int
    lib.guara_core_latch_on_actuation_failure.argtypes = [
        c_void_p, c_double, POINTER(COutput)]
    lib.guara_core_latch_on_actuation_failure.restype = c_int
    lib.guara_gateway_storage_size.restype = c_size_t
    lib.guara_gateway_storage_align.restype = c_size_t
    lib.guara_gateway_limits_default.argtypes = [POINTER(CGatewayLimits)]
    lib.guara_gateway_init.argtypes = [c_void_p, c_size_t, POINTER(CGatewayLimits)]
    lib.guara_gateway_init.restype = c_int
    lib.guara_gateway_set_guard.argtypes = [c_void_p, c_uint8]
    lib.guara_gateway_set_guard.restype = c_int
    lib.guara_gateway_on_core_state.argtypes = [c_void_p, c_uint8, c_double]
    lib.guara_gateway_on_core_state.restype = c_int
    lib.guara_gateway_on_cf_setpoint.argtypes = [
        c_void_p, c_double, c_double, POINTER(c_float), c_float]
    lib.guara_gateway_on_cf_setpoint.restype = c_int
    lib.guara_gateway_compute.argtypes = [c_void_p, c_double, POINTER(CGatewayOutput)]
    lib.guara_gateway_compute.restype = c_int
    return lib


def cabi_candidates(root: Path) -> list[Path]:
    names = (
        "libguara_cabi.so",
        "libguara_cabi.dylib",
        "guara_cabi.dll",
        "libguara_cabi.dll",
    )
    dirs = (
        root / "build" / "core",
        root / "build" / "core" / "Release",
        root / "build" / "core" / "Debug",
        root / "build" / "core-prefix" / "lib",
        root / "build" / "core-prefix" / "bin",
        root / "build" / "core-prefix" / "lib64",
    )
    return [d / n for d in dirs for n in names]


def find_cabi(root: Path, explicit: Path | None = None) -> Path | None:
    if explicit is not None and explicit.is_file():
        return explicit
    env = os.environ.get("GUARA_CABI")
    if env:
        p = Path(env)
        if p.is_file():
            return p
    if sys.platform == "darwin":
        suffixes = (".dylib",)
    elif sys.platform == "win32":
        suffixes = (".dll",)
    else:
        suffixes = (".so",)
    for p in cabi_candidates(root):
        if p.is_file() and p.suffix in suffixes:
            return p
    return None


def load_cabi(path: Path) -> ctypes.CDLL:
    return _bind(ctypes.CDLL(str(path)))


def _c_params(p: Params) -> CParams:
    return CParams(
        tau_daa_s=p.tau_daa_s,
        tau_gf_s=p.tau_gf_s,
        h_daa_s=p.h_daa_s,
        h_gf_s=p.h_gf_s,
        dwell_s=p.dwell_s,
        n_max=int(p.n_max),
        window_s=p.window_s,
        return_enabled=1 if p.return_enabled else 0,
        escalation_enabled=1 if p.escalation_enabled else 0,
        escalation_s=p.escalation_s,
    )


def _c_inputs(inp: Inputs) -> CInputs:
    return CInputs(
        t_s=inp.t_s,
        in_charge=inp.in_charge,
        owned_mode_active=inp.owned_mode_active,
        t_daa_s=inp.t_daa_s,
        t_gf_s=inp.t_gf_s,
        monitor_violation=inp.monitor_violation,
        monitor_action=inp.monitor_action,
        input_invalid=inp.input_invalid,
        cf_intent_unsafe=inp.cf_intent_unsafe,
    )


def _py_output(o: COutput) -> Output:
    return Output(
        state=int(o.state),
        recovery=int(o.recovery),
        command=int(o.command),
        transition=int(o.transition.id),
        unsafe_causes=int(o.unsafe_causes),
        clear=bool(o.clear),
        clear_duration_s=float(o.clear_duration_s),
        switches_in_window=int(o.switches_in_window),
    )


class SilCore:
    def __init__(self, lib: ctypes.CDLL, params: Params) -> None:
        self._lib = lib
        size = int(lib.guara_core_storage_size())
        align = int(lib.guara_core_storage_align())
        self._buf = _Aligned(size, align)
        rc = lib.guara_core_init(self._buf.addr, size, ctypes.byref(_c_params(params)))
        if rc != GUARA_OK:
            raise OSError(f"guara_core_init returned {rc}")

    def step(self, inp: Inputs) -> Output:
        out = COutput()
        rc = self._lib.guara_core_step(
            self._buf.addr, ctypes.byref(_c_inputs(inp)), ctypes.byref(out))
        if rc != GUARA_OK:
            raise OSError(f"guara_core_step returned {rc}")
        return _py_output(out)

    def latch_on_actuation_failure(self, t_s: float) -> Output:
        out = COutput()
        rc = self._lib.guara_core_latch_on_actuation_failure(
            self._buf.addr, c_double(t_s), ctypes.byref(out))
        if rc != GUARA_OK:
            raise OSError(f"guara_core_latch_on_actuation_failure returned {rc}")
        return _py_output(out)


class SilGateway:
    def __init__(self, lib: ctypes.CDLL, limits: GatewayLimits) -> None:
        self._lib = lib
        size = int(lib.guara_gateway_storage_size())
        align = int(lib.guara_gateway_storage_align())
        self._buf = _Aligned(size, align)
        cl = CGatewayLimits(
            max_speed_h_m_s=limits.max_speed_h_m_s,
            max_climb_rate_m_s=limits.max_climb_rate_m_s,
            max_descent_rate_m_s=limits.max_descent_rate_m_s,
            max_yaw_rate_rad_s=limits.max_yaw_rate_rad_s,
            future_stamp_tolerance_s=limits.future_stamp_tolerance_s,
            cf_timeout_s=limits.cf_timeout_s,
        )
        rc = lib.guara_gateway_init(self._buf.addr, size, ctypes.byref(cl))
        if rc != GUARA_OK:
            raise OSError(f"guara_gateway_init returned {rc}")

    def set_guard(self, mode: int) -> None:
        rc = self._lib.guara_gateway_set_guard(self._buf.addr, c_uint8(mode))
        if rc != GUARA_OK:
            raise OSError(f"guara_gateway_set_guard returned {rc}")

    def on_core_state(self, state: int, t_s: float) -> None:
        rc = self._lib.guara_gateway_on_core_state(
            self._buf.addr, c_uint8(state), c_double(t_s))
        if rc != GUARA_OK:
            raise OSError(f"guara_gateway_on_core_state returned {rc}")

    def on_cf_setpoint(self, t_recv_s: float, stamp_s: float,
                       v: tuple[float, float, float], yaw: float) -> None:
        arr = (c_float * 3)(v[0], v[1], v[2])
        rc = self._lib.guara_gateway_on_cf_setpoint(
            self._buf.addr, c_double(t_recv_s), c_double(stamp_s), arr, c_float(yaw))
        if rc != GUARA_OK:
            raise OSError(f"guara_gateway_on_cf_setpoint returned {rc}")

    def compute(self, t_s: float) -> GatewayOutput:
        out = CGatewayOutput()
        rc = self._lib.guara_gateway_compute(
            self._buf.addr, c_double(t_s), ctypes.byref(out))
        if rc != GUARA_OK:
            raise OSError(f"guara_gateway_compute returned {rc}")
        return GatewayOutput(
            vx=float(out.velocity_ned_m_s[0]),
            vy=float(out.velocity_ned_m_s[1]),
            vz=float(out.velocity_ned_m_s[2]),
            yaw=float(out.yaw_ned_rad),
            forwarding_cf=int(out.forwarding_cf),
            rejected_non_finite=int(out.rejected_non_finite),
            rejected_stamp=int(out.rejected_implausible_stamp),
            rejected_yaw=int(out.rejected_yaw),
            rejected_guard=int(out.rejected_by_guard),
            clamped=int(out.clamped),
        )
