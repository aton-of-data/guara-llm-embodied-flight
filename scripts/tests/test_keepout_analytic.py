#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-47: attitude keep-out predictor, analytic cases (ADR 0012).

Expected values are derived by hand from the planar closed form: T = (θ − θ_min) / ω
when the boresight rotates toward the forbidden direction at constant rate ω, else
+∞ or 0. Tolerance ±0.05 s, the same number AC-8 uses for the geofence predictor.
"""
import math
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from space import keepout as ko  # noqa: E402

TOL = ko.TOL_S


def test_approaching_closed_form():
    # θ = 0.40 rad, θ_min = 0.10 rad, ω = 0.05 rad/s → T = 6.0 s.
    t = ko.time_to_cone_violation(0.40, 0.10, 0.05, horizon_s=30.0)
    assert t == pytest.approx(6.0, abs=TOL)


def test_receding_is_infinity():
    t = ko.time_to_cone_violation(0.40, 0.10, omega_close_rad_s=-0.05, horizon_s=30.0)
    assert t == math.inf


def test_zero_rate_outside_the_cone_is_infinity():
    t = ko.time_to_cone_violation(0.40, 0.10, omega_close_rad_s=0.0, horizon_s=30.0)
    assert t == math.inf


def test_already_inside_the_cone_is_zero():
    t = ko.time_to_cone_violation(0.05, 0.10, omega_close_rad_s=0.05, horizon_s=30.0)
    assert t == 0.0


def test_on_the_cone_boundary_is_zero():
    t = ko.time_to_cone_violation(0.10, 0.10, omega_close_rad_s=0.05, horizon_s=30.0)
    assert t == 0.0


def test_beyond_horizon_is_infinity():
    # T = (1.0 - 0.1) / 0.02 = 45 s > horizon 30 s.
    t = ko.time_to_cone_violation(1.0, 0.10, 0.02, horizon_s=30.0)
    assert t == math.inf


def test_non_finite_fails_closed():
    assert ko.time_to_cone_violation(math.nan, 0.1, 0.05, 30.0) == 0.0
    assert ko.time_to_cone_violation(0.4, 0.1, math.inf, 30.0) == 0.0
    assert ko.predict((1, 0, 0), (0, 1, 0), (math.nan, 0, 0), 0.1, 30.0) == 0.0


def test_vector_form_matches_closed_form_in_the_plane():
    theta = 0.40
    theta_min = 0.10
    omega = 0.05
    boresight = (1.0, 0.0, 0.0)
    forbidden = (math.cos(theta), math.sin(theta), 0.0)
    # Rate about +z closes the angle (boresight × forbidden is +z).
    rate = (0.0, 0.0, omega)
    t = ko.predict(boresight, forbidden, rate, theta_min, horizon_s=30.0)
    assert t == pytest.approx((theta - theta_min) / omega, abs=TOL)


def test_vector_form_receding():
    theta = 0.40
    boresight = (1.0, 0.0, 0.0)
    forbidden = (math.cos(theta), math.sin(theta), 0.0)
    rate = (0.0, 0.0, -0.05)
    assert ko.predict(boresight, forbidden, rate, 0.10, 30.0) == math.inf


def test_vector_form_zero_rate():
    boresight = (1.0, 0.0, 0.0)
    forbidden = (0.0, 1.0, 0.0)
    assert ko.predict(boresight, forbidden, (0.0, 0.0, 0.0), 0.10, 30.0) == math.inf


def test_degenerate_boresight_fails_closed():
    assert ko.predict((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.05), 0.1, 30.0) == 0.0
