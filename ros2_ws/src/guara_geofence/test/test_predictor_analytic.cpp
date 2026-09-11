// SPDX-License-Identifier: Apache-2.0
//
// AC-8: the predictor returns T_gf within +/-0.05 s of closed-form values on analytic cases (convex
// and concave polygons, zero velocity, tangent trajectory) and +inf when no violation is predicted
// within the horizon. Expected values are derived by hand in each test from the model of ADR 0004.
#include <gtest/gtest.h>

#include <cmath>
#include <limits>

#include "guara_geofence/predictor.hpp"

namespace guara_geofence
{
namespace
{

constexpr double kTol = 0.05;  // AC-8 tolerance [s]

Fence square100()
{
  const Vec2 v[] = {{-50, -50}, {50, -50}, {50, 50}, {-50, 50}};
  Fence f;
  EXPECT_EQ(f.polygon.set(v, 4), PolygonError::kNone);
  f.alt_min_m = 0.0;
  f.alt_max_m = 30.0;
  return f;
}

// U-shaped concave polygon: 100 m x 100 m square with a notch x in (40, 60), y in (40, 100].
Fence notched()
{
  const Vec2 v[] = {{0, 0}, {100, 0}, {100, 100}, {60, 100}, {60, 40}, {40, 40}, {40, 100}, {0, 100}};
  Fence f;
  EXPECT_EQ(f.polygon.set(v, 8), PolygonError::kNone);
  return f;
}

PredictorParameters params(double a_h = 2.5, double a_v = 2.0, double k_sigma = 2.0)
{
  PredictorParameters p;
  p.a_brake_h_m_s2 = a_h;
  p.a_brake_v_m_s2 = a_v;
  p.k_sigma = k_sigma;
  p.v_min_m_s = 0.2;
  p.horizon_s = 30.0;
  return p;
}

VehicleState at(double x, double y, double vx, double vy, double alt = 10.0, double climb = 0.0)
{
  VehicleState s;
  s.position = {x, y};
  s.velocity = {vx, vy};
  s.altitude_m = alt;
  s.climb_rate_m_s = climb;
  return s;
}

TEST(PredictorAnalytic, ConvexStraightApproach)
{
  // D = 50 m, |v| = 5 m/s, d_stop = 25 / (2 * 2.5) = 5 m  =>  T = (50 - 5) / 5 = 9.0 s.
  const Prediction pr = predict(square100(), params(), at(0, 0, 5, 0));
  EXPECT_TRUE(pr.inside);
  EXPECT_NEAR(pr.exit_distance_m, 50.0, 1e-6);
  EXPECT_NEAR(pr.t_gf_s, 9.0, kTol);
}

TEST(PredictorAnalytic, ConvexDiagonalApproachWithPositionUncertainty)
{
  // Ray (3, 4)/5 from the origin exits the square at y = 50: s = 50 / 0.8 = 62.5 m.
  // |v| = 5, d_stop = 25 / 5 + 2 * 1.5 = 8 m  =>  T = (62.5 - 8) / 5 = 10.9 s.
  VehicleState s = at(0, 0, 3, 4);
  s.eph_m = 1.5;
  const Prediction pr = predict(square100(), params(), s);
  EXPECT_NEAR(pr.exit_distance_m, 62.5, 1e-6);
  EXPECT_NEAR(pr.t_gf_s, 10.9, kTol);
}

TEST(PredictorAnalytic, ConcaveRayEntersNotch)
{
  // From (20, 50) moving +x at 4 m/s the notch edge x = 40 is reached after 20 m.
  // d_stop = 16 / 5 = 3.2 m  =>  T = (20 - 3.2) / 4 = 4.2 s.
  const Prediction pr = predict(notched(), params(), at(20, 50, 4, 0));
  EXPECT_NEAR(pr.exit_distance_m, 20.0, 1e-6);
  EXPECT_NEAR(pr.t_gf_s, 4.2, kTol);
}

TEST(PredictorAnalytic, ConcaveTangentThroughReflexVertexDoesNotCountAsExit)
{
  // From (30, 50) along (1, -1)/sqrt(2) the ray touches the reflex vertex (40, 40) and stays inside
  // (x < 40 before, y < 40 after); it leaves through y = 0 at (80, 0): s = 50 sqrt(2) = 70.7107 m.
  // |v| = sqrt(18), d_stop = 18 / 5 = 3.6 m  =>  T = (70.7107 - 3.6) / 4.24264 = 15.8184 s.
  const Prediction pr = predict(notched(), params(), at(30, 50, 3, -3));
  EXPECT_NEAR(pr.exit_distance_m, 50.0 * std::sqrt(2.0), 1e-6);
  EXPECT_NEAR(pr.t_gf_s, (50.0 * std::sqrt(2.0) - 3.6) / std::sqrt(18.0), kTol);
}

TEST(PredictorAnalytic, ConcaveTrajectoryAlongCollinearBoundaryEdge)
{
  // Along y = 40 the ray runs on the notch bottom edge between x = 40 and x = 60, which belongs to the
  // closed polygon; the exit is at x = 100: s = 80 m, d_stop = 16 / 5 = 3.2 m  =>  T = 19.2 s.
  const Prediction pr = predict(notched(), params(), at(20, 40, 4, 0));
  EXPECT_NEAR(pr.exit_distance_m, 80.0, 1e-6);
  EXPECT_NEAR(pr.t_gf_s, 19.2, kTol);
}

TEST(PredictorAnalytic, TangentParallelToEdgeUsesFarBoundary)
{
  // Moving +y at x = 49 (1 m from the east edge x = 50, never crossing it): exit at y = 50, s = 50 m.
  // d_stop = 4 / 5 = 0.8 m  =>  T = (50 - 0.8) / 2 = 24.6 s.
  const Prediction pr = predict(square100(), params(), at(49, 0, 0, 2));
  EXPECT_NEAR(pr.t_gf_s, 24.6, kTol);
}

TEST(PredictorAnalytic, ZeroVelocityIsInfinite)
{
  const Prediction pr = predict(square100(), params(), at(49.9, 49.9, 0, 0));
  EXPECT_TRUE(std::isinf(pr.t_gf_s));
  EXPECT_GT(pr.t_gf_s, 0.0);
}

TEST(PredictorAnalytic, SlowMotionBeyondHorizonIsInfinite)
{
  // T = (50 - 0.05) / 0.5 = 99.9 s > T_hor = 30 s  =>  +inf.
  const Prediction pr = predict(square100(), params(), at(0, 0, 0.5, 0));
  EXPECT_TRUE(std::isinf(pr.t_gf_s));
}

TEST(PredictorAnalytic, InsideStoppingDistanceIsZero)
{
  // D = 5 m < d_stop = 100 / 5 = 20 m  =>  T = 0.
  const Prediction pr = predict(square100(), params(), at(45, 0, 10, 0));
  EXPECT_NEAR(pr.t_gf_s, 0.0, kTol);
}

TEST(PredictorAnalytic, OutsideIsZero)
{
  const Prediction pr = predict(square100(), params(), at(60, 0, 0, 0));
  EXPECT_FALSE(pr.inside);
  EXPECT_EQ(pr.t_gf_s, 0.0);
  const Prediction above = predict(square100(), params(), at(0, 0, 0, 0, 31.0, 0.0));
  EXPECT_FALSE(above.inside);
  EXPECT_EQ(above.t_gf_s, 0.0);
}

TEST(PredictorAnalytic, VerticalCeilingApproach)
{
  // Altitude 10 m, ceiling 30 m, climb 4 m/s, a_v = 2: d_stop = 16 / 4 = 4 m  =>  T = (20 - 4) / 4 = 4 s.
  const Prediction pr = predict(square100(), params(), at(0, 0, 0, 0, 10.0, 4.0));
  EXPECT_NEAR(pr.t_vertical_s, 4.0, kTol);
  EXPECT_NEAR(pr.t_gf_s, 4.0, kTol);
}

TEST(PredictorAnalytic, VerticalFloorApproachWithUncertainty)
{
  // Altitude 12 m, floor 0 m, descent 3 m/s, epv = 0.5: d_stop = 9 / 4 + 1 = 3.25 m  =>  T = 2.9167 s.
  VehicleState s = at(0, 0, 0, 0, 12.0, -3.0);
  s.epv_m = 0.5;
  const Prediction pr = predict(square100(), params(), s);
  EXPECT_NEAR(pr.t_gf_s, (12.0 - 3.25) / 3.0, kTol);
}

TEST(PredictorAnalytic, MinimumOfHorizontalAndVertical)
{
  // Horizontal T = 9.0 s (ConvexStraightApproach), vertical T = 4.0 s (VerticalCeilingApproach).
  const Prediction pr = predict(square100(), params(), at(0, 0, 5, 0, 10.0, 4.0));
  EXPECT_NEAR(pr.t_horizontal_s, 9.0, kTol);
  EXPECT_NEAR(pr.t_gf_s, 4.0, kTol);
}

TEST(PolygonValidation, RejectsInvalidPolygons)
{
  Polygon p;
  const Vec2 two[] = {{0, 0}, {1, 0}};
  EXPECT_EQ(p.set(two, 2), PolygonError::kTooFewVertices);
  const Vec2 bowtie[] = {{0, 0}, {10, 10}, {10, 0}, {0, 10}};
  EXPECT_EQ(p.set(bowtie, 4), PolygonError::kSelfIntersecting);
  const Vec2 duplicate[] = {{0, 0}, {0, 0}, {10, 0}, {0, 10}};
  EXPECT_EQ(p.set(duplicate, 4), PolygonError::kDegenerateEdge);
  const Vec2 collinear[] = {{0, 0}, {5, 0}, {10, 0}};
  EXPECT_EQ(p.set(collinear, 3), PolygonError::kZeroArea);
  const double nan = std::numeric_limits<double>::quiet_NaN();
  const Vec2 bad[] = {{0, 0}, {nan, 0}, {0, 10}};
  EXPECT_EQ(p.set(bad, 3), PolygonError::kNonFiniteVertex);
  EXPECT_EQ(p.size(), 0U);
}

TEST(Projection, MatchesSmallDistanceApproximation)
{
  // 0.001 deg of latitude ~ 111.19 m on a sphere of radius 6371 km.
  const Vec2 north = projectToLocal(-22.001, -47.89, -22.0, -47.89);
  EXPECT_NEAR(north.x, -111.195, 0.01);
  EXPECT_NEAR(north.y, 0.0, 1e-6);
  const Vec2 east = projectToLocal(-22.0, -47.889, -22.0, -47.89);
  EXPECT_NEAR(east.y, 111.195 * std::cos(22.0 * M_PI / 180.0), 0.01);
}

}  // namespace
}  // namespace guara_geofence
