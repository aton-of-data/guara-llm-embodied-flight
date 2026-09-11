// SPDX-License-Identifier: Apache-2.0
//
// Braking-aware geofence time-to-violation predictor (ADR 0004, SPEC §3.1 signal T_gf).
//
// Model. The inclusion fence F is the Cartesian product of a simple polygon P in the local
// north-east plane and an altitude interval [a_min, a_max]; F is closed, so boundary points are
// admissible. The vehicle is modelled at constant velocity v from position p. For the horizontal
// channel, D_h is the length of the shortest ray segment p + s v/|v| (s > 0) whose continuation leaves
// P, and the stopping distance is d_stop(v) = |v|^2 / (2 a_brake) + k_sigma * eph. The predicted time
// to violation is
//     T_h = max(0, (D_h - d_stop) / |v|),
// the latest instant at which a constant deceleration a_brake, initiated with no further delay, still
// keeps the vehicle inside P. The vertical channel is analogous with the vertical speed, the ceiling
// or floor distance, a_brake_v and k_sigma * epv. T_gf = min(T_h, T_v); values above the horizon are
// reported as +inf, and a position outside F yields T_gf = 0. Latency is not part of the model; it is
// covered by the threshold (SPEC obligation O-1).
//
// Implementation constraints (CLAUDE.md, Engineering): fixed capacity and no dynamic allocation. A
// prediction computes at most 2N ray-boundary events, sorts them by insertion and classifies each
// inter-event interval with one O(N) containment query, so its cost is O(N^2) with N <= kMaxVertices.
#pragma once

#include <array>
#include <cstddef>
#include <limits>

namespace guara_geofence
{

inline constexpr std::size_t kMaxVertices = 64;
inline constexpr double kInf = std::numeric_limits<double>::infinity();

struct Vec2
{
  double x{0.0};  // north [m]
  double y{0.0};  // east [m]
};

enum class PolygonError
{
  kNone,
  kTooFewVertices,
  kTooManyVertices,
  kNonFiniteVertex,
  kDegenerateEdge,
  kSelfIntersecting,
  kZeroArea,
};

const char * toString(PolygonError e) noexcept;

// Simple polygon (convex or concave) with at most kMaxVertices vertices, in either orientation.
class Polygon
{
public:
  // Validates and stores the vertices. On error the polygon is left empty.
  PolygonError set(const Vec2 * vertices, std::size_t n) noexcept;

  std::size_t size() const noexcept {return n_;}
  const Vec2 & vertex(std::size_t i) const noexcept {return v_[i];}

  // True if q lies in the closed polygon (boundary within `tolerance_m` counts as inside).
  bool contains(const Vec2 & q, double tolerance_m = 1e-6) const noexcept;

  // Distance from q to the nearest point of the boundary.
  double boundaryDistance(const Vec2 & q) const noexcept;

  // Length s* > 0 of the shortest ray segment from p along unit direction u after which the ray
  // leaves the closed polygon; +inf if the ray never leaves it. Precondition: contains(p).
  double exitDistance(const Vec2 & p, const Vec2 & u) const noexcept;

private:
  std::array<Vec2, kMaxVertices> v_{};
  std::size_t n_{0};
};

struct Fence
{
  Polygon polygon;
  double alt_min_m{-kInf};  // altitude above the local origin, i.e. -z in NED
  double alt_max_m{kInf};
};

struct PredictorParameters
{
  double a_brake_h_m_s2{3.0};  // [HYPOTHESIS] horizontal braking deceleration; measured in SITL (M4)
  double a_brake_v_m_s2{2.0};  // [HYPOTHESIS] vertical braking deceleration
  double k_sigma{2.0};         // [HYPOTHESIS] position uncertainty multiplier (ADR 0004 item 2)
  double v_min_m_s{0.2};       // below this speed a channel is considered stationary
  double horizon_s{30.0};      // T_hor
};

const char * validate(const PredictorParameters & p) noexcept;

struct VehicleState
{
  Vec2 position;               // local NE [m]
  double altitude_m{0.0};      // -z [m]
  Vec2 velocity;               // local NE [m/s]
  double climb_rate_m_s{0.0};  // -vz [m/s]
  double eph_m{0.0};
  double epv_m{0.0};
};

struct Prediction
{
  double t_gf_s{kInf};
  double t_horizontal_s{kInf};
  double t_vertical_s{kInf};
  bool inside{true};
  double exit_distance_m{kInf};  // D_h
};

Prediction predict(
  const Fence & fence, const PredictorParameters & params, const VehicleState & state) noexcept;

// Azimuthal equidistant projection of (lat, lon) [deg] about a reference point, returning north/east
// metres; the same formulation and Earth radius as PX4's map projection (GROUNDING D.4).
Vec2 projectToLocal(double lat_deg, double lon_deg, double ref_lat_deg, double ref_lon_deg) noexcept;

}  // namespace guara_geofence
