// SPDX-License-Identifier: Apache-2.0
//
// Lateral position uncertainty (review 2026-09-11 §4 "Lateral uncertainty is ignored"). The
// braking model subtracts k_sigma * eph only along the velocity ray, so a vehicle hovering inside
// the k_sigma * eph band of the boundary, or flying parallel to it, never triggered the geofence
// although its true position may already be outside the fence. The predictor therefore also bounds
// T_gf by the distance to the *nearest* boundary: when that distance is inside the uncertainty
// band, the sample is treated as a violation (T_gf = 0), independently of the heading.
#include <cmath>
#include <limits>

#include <gtest/gtest.h>

#include "guara_geofence/predictor.hpp"

namespace guara_geofence
{
namespace
{

Fence square100()
{
  const Vec2 v[] = {{-50, -50}, {50, -50}, {50, 50}, {-50, 50}};
  Fence f;
  EXPECT_EQ(f.polygon.set(v, 4), PolygonError::kNone);
  f.alt_min_m = 0.0;
  f.alt_max_m = 30.0;
  return f;
}

PredictorParameters params(double k_sigma = 2.0)
{
  PredictorParameters p;
  p.a_brake_h_m_s2 = 2.5;
  p.a_brake_v_m_s2 = 2.0;
  p.k_sigma = k_sigma;
  p.v_min_m_s = 0.2;
  p.horizon_s = 30.0;
  return p;
}

VehicleState at(double x, double y, double vx, double vy, double eph = 0.0, double alt = 10.0)
{
  VehicleState s;
  s.position = {x, y};
  s.velocity = {vx, vy};
  s.altitude_m = alt;
  s.eph_m = eph;
  return s;
}

// Hovering 2 m from the wall with eph = 3 m: the true position may be outside the fence.
TEST(PredictorUncertainty, HoverInsideTheUncertaintyBandIsAViolation)
{
  const Fence f = square100();
  EXPECT_EQ(0.0, predict(f, params(), at(48.0, 0.0, 0.0, 0.0, /*eph=*/3.0)).t_gf_s);
  EXPECT_EQ(kInf, predict(f, params(), at(48.0, 0.0, 0.0, 0.0, /*eph=*/0.5)).t_gf_s);
}

// Flying parallel to the wall inside the band: the velocity ray never meets the boundary, but the
// lateral bound still fires.
TEST(PredictorUncertainty, ParallelFlightInsideTheBandIsAViolation)
{
  const Fence f = square100();
  EXPECT_EQ(0.0, predict(f, params(), at(48.0, -40.0, 0.0, 5.0, /*eph=*/3.0)).t_gf_s);
}

// Away from the band the prediction is unchanged: 30 m to the wall at 10 m/s with
// d_stop = 100/5 + 2 * 0.5 = 21 m gives (30 - 21) / 10 = 0.9 s.
TEST(PredictorUncertainty, OutsideTheBandTheRayModelIsUnchanged)
{
  const Fence f = square100();
  const Prediction p = predict(f, params(), at(20.0, 0.0, 10.0, 0.0, /*eph=*/0.5));
  EXPECT_NEAR(0.9, p.t_gf_s, 0.05);
}

// The vertical channel uses epv the same way: hovering just under the ceiling with a large epv is a
// violation even with zero climb rate.
TEST(PredictorUncertainty, AltitudeBandUsesEpv)
{
  Fence f = square100();
  VehicleState s = at(0.0, 0.0, 0.0, 0.0, /*eph=*/0.1, /*alt=*/29.0);
  s.epv_m = 3.0;
  EXPECT_EQ(0.0, predict(f, params(), s).t_gf_s);
  s.epv_m = 0.2;
  EXPECT_EQ(kInf, predict(f, params(), s).t_gf_s);
}

// k_sigma = 0 disables the band, which keeps the analytic cases of AC-8 exact.
TEST(PredictorUncertainty, ZeroKSigmaDisablesTheBand)
{
  const Fence f = square100();
  EXPECT_EQ(kInf, predict(f, params(0.0), at(49.9, 0.0, 0.0, 0.0, /*eph=*/50.0)).t_gf_s);
}

}  // namespace
}  // namespace guara_geofence
