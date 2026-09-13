# SPDX-License-Identifier: Apache-2.0
"""SIL port: drive published vectors through the C ABI via ctypes (M19 / AC-64)."""
from __future__ import annotations

import ctypes
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

from .geofence import GfParams, GfPrediction, GfState, Vec2, polygon_error_name
from .gateway import GatewayLimits, GatewayOutput
from .monitors import MonitorEval
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


class CMonitorSample(ctypes.Structure):
    _fields_ = [
        ("id", c_char_p),
        ("monitor_class", c_uint8),
        ("action", c_uint8),
        ("violated", c_uint8),
        ("inputs_complete", c_uint8),
    ]


class CMonitorEval(ctypes.Structure):
    _fields_ = [
        ("violation", c_uint8),
        ("action", c_uint8),
        ("invalid", c_uint8),
        ("first_violating_id", ctypes.c_char * 48),
        ("first_invalid_id", ctypes.c_char * 48),
    ]


class CGfParams(ctypes.Structure):
    _fields_ = [
        ("a_brake_h_m_s2", c_double),
        ("a_brake_v_m_s2", c_double),
        ("k_sigma", c_double),
        ("v_min_m_s", c_double),
        ("horizon_s", c_double),
    ]


class CGfState(ctypes.Structure):
    _fields_ = [
        ("north_m", c_double),
        ("east_m", c_double),
        ("altitude_m", c_double),
        ("vn_m_s", c_double),
        ("ve_m_s", c_double),
        ("climb_rate_m_s", c_double),
        ("eph_m", c_double),
        ("epv_m", c_double),
    ]


class CGfPrediction(ctypes.Structure):
    _fields_ = [
        ("t_gf_s", c_double),
        ("t_horizontal_s", c_double),
        ("t_vertical_s", c_double),
        ("inside", c_uint8),
        ("exit_distance_m", c_double),
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
    lib.guara_state_name.argtypes = [c_uint8]
    lib.guara_state_name.restype = c_char_p
    lib.guara_recovery_name.argtypes = [c_uint8]
    lib.guara_recovery_name.restype = c_char_p
    lib.guara_command_name.argtypes = [c_uint8]
    lib.guara_command_name.restype = c_char_p
    lib.guara_params_default.argtypes = [POINTER(CParams)]
    lib.guara_params_error.argtypes = [POINTER(CParams)]
    lib.guara_params_error.restype = c_char_p
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
    lib.guara_monitor_storage_size.restype = c_size_t
    lib.guara_monitor_storage_align.restype = c_size_t
    lib.guara_monitor_init.argtypes = [c_void_p, c_size_t, c_double]
    lib.guara_monitor_init.restype = c_int
    lib.guara_monitor_expect.argtypes = [c_void_p, c_char_p]
    lib.guara_monitor_expect.restype = c_int
    lib.guara_monitor_observe.argtypes = [c_void_p, POINTER(CMonitorSample), c_double]
    lib.guara_monitor_observe.restype = c_int
    lib.guara_monitor_evaluate.argtypes = [c_void_p, c_double, POINTER(CMonitorEval)]
    lib.guara_monitor_evaluate.restype = c_int
    lib.guara_gf_params_default.argtypes = [POINTER(CGfParams)]
    lib.guara_gf_params_error.argtypes = [POINTER(CGfParams)]
    lib.guara_gf_params_error.restype = c_char_p
    lib.guara_gf_predict.argtypes = [
        POINTER(c_double), c_size_t, c_double, c_double,
        POINTER(CGfParams), POINTER(CGfState), POINTER(CGfPrediction)]
    lib.guara_gf_predict.restype = c_int
    lib.guara_gf_project_to_local.argtypes = [
        c_double, c_double, c_double, c_double, POINTER(c_double), POINTER(c_double)]
    lib.guara_gf_project_to_local.restype = c_int
    lib.guara_gf_polygon_error.argtypes = [POINTER(c_double), c_size_t]
    lib.guara_gf_polygon_error.restype = c_int
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

    def params_error(self, params: Params) -> str | None:
        raw = self._lib.guara_params_error(ctypes.byref(_c_params(params)))
        return None if raw is None else raw.decode("utf-8")

    def vocabulary_name(self, kind: str, code: int) -> str:
        fn = {
            "state": self._lib.guara_state_name,
            "recovery": self._lib.guara_recovery_name,
            "command": self._lib.guara_command_name,
        }.get(kind)
        if fn is None:
            return "UNKNOWN"
        raw = fn(c_uint8(code))
        return "UNKNOWN" if raw is None else raw.decode("utf-8")

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


def _cstr(buf: bytes) -> str:
    return buf.split(b"\x00", 1)[0].decode("utf-8", errors="replace")


class SilMonitor:
    def __init__(self, lib: ctypes.CDLL, max_age_s: float) -> None:
        self._lib = lib
        size = int(lib.guara_monitor_storage_size())
        align = int(lib.guara_monitor_storage_align())
        self._buf = _Aligned(size, align)
        rc = lib.guara_monitor_init(self._buf.addr, size, c_double(max_age_s))
        if rc != GUARA_OK:
            raise OSError(f"guara_monitor_init returned {rc}")

    def expect(self, ident: str) -> int:
        rc = self._lib.guara_monitor_expect(self._buf.addr, ident.encode("utf-8"))
        return int(rc)

    def observe(self, ident: str, monitor_class: int, action: int, violated: int,
                complete: int, t_recv_s: float) -> int:
        raw = ident.encode("utf-8")
        sample = CMonitorSample()
        sample.id = raw
        sample.monitor_class = monitor_class
        sample.action = action
        sample.violated = violated
        sample.inputs_complete = complete
        return int(self._lib.guara_monitor_observe(
            self._buf.addr, ctypes.byref(sample), c_double(t_recv_s)))

    def evaluate(self, t_s: float) -> MonitorEval:
        out = CMonitorEval()
        rc = self._lib.guara_monitor_evaluate(
            self._buf.addr, c_double(t_s), ctypes.byref(out))
        if rc != GUARA_OK:
            raise OSError(f"guara_monitor_evaluate returned {rc}")
        return MonitorEval(
            violation=int(out.violation),
            action=int(out.action),
            invalid=int(out.invalid),
            first_violating_id=_cstr(bytes(out.first_violating_id)),
            first_invalid_id=_cstr(bytes(out.first_invalid_id)),
        )


class SilGeofence:
    def __init__(self, lib: ctypes.CDLL) -> None:
        self._lib = lib
        self._verts: list[float] = []
        self._alt_min = 0.0
        self._alt_max = 1.0e9

    def configure(self, vertices_ne: list[float], alt_min_m: float, alt_max_m: float) -> None:
        self._verts = list(vertices_ne)
        self._alt_min = alt_min_m
        self._alt_max = alt_max_m

    def predict(self, params: GfParams, state: GfState) -> GfPrediction:
        n = len(self._verts) // 2
        arr = (c_double * len(self._verts))(*self._verts)
        cp = CGfParams(
            a_brake_h_m_s2=params.a_brake_h_m_s2,
            a_brake_v_m_s2=params.a_brake_v_m_s2,
            k_sigma=params.k_sigma,
            v_min_m_s=params.v_min_m_s,
            horizon_s=params.horizon_s,
        )
        cs = CGfState(
            north_m=state.north_m,
            east_m=state.east_m,
            altitude_m=state.altitude_m,
            vn_m_s=state.vn_m_s,
            ve_m_s=state.ve_m_s,
            climb_rate_m_s=state.climb_rate_m_s,
            eph_m=state.eph_m,
            epv_m=state.epv_m,
        )
        out = CGfPrediction()
        rc = self._lib.guara_gf_predict(
            arr, n, c_double(self._alt_min), c_double(self._alt_max),
            ctypes.byref(cp), ctypes.byref(cs), ctypes.byref(out))
        if rc != GUARA_OK:
            raise OSError(f"guara_gf_predict returned {rc}")
        return GfPrediction(
            t_gf_s=float(out.t_gf_s),
            t_horizontal_s=float(out.t_horizontal_s),
            t_vertical_s=float(out.t_vertical_s),
            inside=int(out.inside),
            exit_distance_m=float(out.exit_distance_m),
        )

    def project(self, lat_deg: float, lon_deg: float, ref_lat_deg: float,
                ref_lon_deg: float):
        north = c_double()
        east = c_double()
        rc = self._lib.guara_gf_project_to_local(
            c_double(lat_deg), c_double(lon_deg),
            c_double(ref_lat_deg), c_double(ref_lon_deg),
            ctypes.byref(north), ctypes.byref(east))
        if rc != GUARA_OK:
            raise OSError(f"guara_gf_project_to_local returned {rc}")
        return Vec2(float(north.value), float(east.value))

    def polygon_error(self, vertices_ne: list[float]) -> str:
        n = len(vertices_ne) // 2
        if n == 0:
            rc = int(self._lib.guara_gf_polygon_error(None, 0))
        else:
            arr = (c_double * len(vertices_ne))(*vertices_ne)
            rc = int(self._lib.guara_gf_polygon_error(arr, n))
        return polygon_error_name(rc)

    def params_error(self, params: GfParams) -> str | None:
        cp = CGfParams(
            a_brake_h_m_s2=params.a_brake_h_m_s2,
            a_brake_v_m_s2=params.a_brake_v_m_s2,
            k_sigma=params.k_sigma,
            v_min_m_s=params.v_min_m_s,
            horizon_s=params.horizon_s,
        )
        raw = self._lib.guara_gf_params_error(ctypes.byref(cp))
        return None if raw is None else raw.decode("utf-8")
