// SPDX-License-Identifier: Apache-2.0
#include "guara_geofence/predictor.hpp"

#include <algorithm>
#include <cmath>

namespace guara_geofence
{
namespace
{

constexpr double kGeomEps = 1e-9;       // [m] geometric tolerance for intersection tests
constexpr double kEarthRadiusM = 6371000.0;  // px4_ros2_cpp/src/utils/map_projection_impl.hpp:15

double cross(const Vec2 & a, const Vec2 & b) noexcept {return a.x * b.y - a.y * b.x;}
double dot(const Vec2 & a, const Vec2 & b) noexcept {return a.x * b.x + a.y * b.y;}
Vec2 sub(const Vec2 & a, const Vec2 & b) noexcept {return {a.x - b.x, a.y - b.y};}
double norm(const Vec2 & a) noexcept {return std::hypot(a.x, a.y);}

double pointSegmentDistance(const Vec2 & q, const Vec2 & a, const Vec2 & b) noexcept
{
  const Vec2 ab = sub(b, a);
  const double len2 = dot(ab, ab);
  double t = len2 > 0.0 ? dot(sub(q, a), ab) / len2 : 0.0;
  t = std::clamp(t, 0.0, 1.0);
  return norm(sub(q, {a.x + t * ab.x, a.y + t * ab.y}));
}

int orientation(const Vec2 & a, const Vec2 & b, const Vec2 & c) noexcept
{
  const double v = cross(sub(b, a), sub(c, a));
  if (v > kGeomEps) {return 1;}
  if (v < -kGeomEps) {return -1;}
  return 0;
}

bool onSegment(const Vec2 & a, const Vec2 & b, const Vec2 & q) noexcept
{
  return q.x <= std::max(a.x, b.x) + kGeomEps && q.x >= std::min(a.x, b.x) - kGeomEps &&
         q.y <= std::max(a.y, b.y) + kGeomEps && q.y >= std::min(a.y, b.y) - kGeomEps;
}

// True if closed segments [p1, p2] and [q1, q2] share at least one point.
bool segmentsTouch(const Vec2 & p1, const Vec2 & p2, const Vec2 & q1, const Vec2 & q2) noexcept
{
  const int o1 = orientation(p1, p2, q1);
  const int o2 = orientation(p1, p2, q2);
  const int o3 = orientation(q1, q2, p1);
  const int o4 = orientation(q1, q2, p2);
  if (o1 != o2 && o3 != o4) {return true;}
  if (o1 == 0 && onSegment(p1, p2, q1)) {return true;}
  if (o2 == 0 && onSegment(p1, p2, q2)) {return true;}
  if (o3 == 0 && onSegment(q1, q2, p1)) {return true;}
  if (o4 == 0 && onSegment(q1, q2, p2)) {return true;}
  return false;
}

double channelTime(double distance_m, double speed_m_s, double a_brake, double margin_m,
  double horizon_s) noexcept
{
  if (!std::isfinite(distance_m)) {return kInf;}
  const double d_stop = speed_m_s * speed_m_s / (2.0 * a_brake) + margin_m;
  const double t = std::max(0.0, (distance_m - d_stop) / speed_m_s);
  return t > horizon_s ? kInf : t;
}

}  // namespace

const char * toString(PolygonError e) noexcept
{
  switch (e) {
    case PolygonError::kNone: return "none";
    case PolygonError::kTooFewVertices: return "fewer than 3 vertices";
    case PolygonError::kTooManyVertices: return "more than kMaxVertices vertices";
    case PolygonError::kNonFiniteVertex: return "non-finite vertex coordinate";
    case PolygonError::kDegenerateEdge: return "zero-length edge";
    case PolygonError::kSelfIntersecting: return "self-intersecting boundary";
    case PolygonError::kZeroArea: return "zero enclosed area";
  }
  return "unknown";
}

PolygonError Polygon::set(const Vec2 * vertices, std::size_t n) noexcept
{
  n_ = 0;
  if (n < 3U) {return PolygonError::kTooFewVertices;}
  if (n > kMaxVertices) {return PolygonError::kTooManyVertices;}
  for (std::size_t i = 0; i < n; ++i) {
    if (!std::isfinite(vertices[i].x) || !std::isfinite(vertices[i].y)) {
      return PolygonError::kNonFiniteVertex;
    }
  }
  double twice_area = 0.0;
  for (std::size_t i = 0; i < n; ++i) {
    const Vec2 & a = vertices[i];
    const Vec2 & b = vertices[(i + 1U) % n];
    if (norm(sub(b, a)) <= kGeomEps) {return PolygonError::kDegenerateEdge;}
    twice_area += cross(a, b);
  }
  // Every pair of non-adjacent edges must be disjoint (O(N^2), configuration time only).
  for (std::size_t i = 0; i < n; ++i) {
    for (std::size_t j = i + 1U; j < n; ++j) {
      const bool adjacent = j == i + 1U || (i == 0U && j == n - 1U);
      if (adjacent) {
        continue;
      }
      if (segmentsTouch(vertices[i], vertices[(i + 1U) % n], vertices[j], vertices[(j + 1U) % n])) {
        return PolygonError::kSelfIntersecting;
      }
    }
  }
  if (std::fabs(twice_area) <= kGeomEps) {return PolygonError::kZeroArea;}
  std::copy(vertices, vertices + n, v_.begin());
  n_ = n;
  return PolygonError::kNone;
}

double Polygon::boundaryDistance(const Vec2 & q) const noexcept
{
  double d = kInf;
  for (std::size_t i = 0; i < n_; ++i) {
    d = std::min(d, pointSegmentDistance(q, v_[i], v_[(i + 1U) % n_]));
  }
  return d;
}

bool Polygon::contains(const Vec2 & q, double tolerance_m) const noexcept
{
  if (n_ == 0U) {return false;}
  if (boundaryDistance(q) <= tolerance_m) {return true;}
  // Even-odd crossing number with the half-open vertex rule.
  bool inside = false;
  for (std::size_t i = 0, j = n_ - 1U; i < n_; j = i++) {
    const Vec2 & a = v_[i];
    const Vec2 & b = v_[j];
    if ((a.y > q.y) != (b.y > q.y)) {
      const double x_cross = a.x + (q.y - a.y) * (b.x - a.x) / (b.y - a.y);
      if (q.x < x_cross) {
        inside = !inside;
      }
    }
  }
  return inside;
}

double Polygon::exitDistance(const Vec2 & p, const Vec2 & u) const noexcept
{
  // Parameters s > 0 at which the ray meets the boundary, including endpoints of collinear edges.
  std::array<double, 2U * kMaxVertices> events{};
  std::size_t m = 0;
  const auto push = [&events, &m](double s) {
      if (s > kGeomEps && m < events.size()) {
        events[m++] = s;
      }
    };
  for (std::size_t i = 0; i < n_; ++i) {
    const Vec2 & a = v_[i];
    const Vec2 & b = v_[(i + 1U) % n_];
    const Vec2 e = sub(b, a);
    const Vec2 ap = sub(a, p);
    const double denom = cross(u, e);
    if (std::fabs(denom) > kGeomEps * norm(e)) {
      const double s = cross(ap, e) / denom;
      const double t = cross(ap, u) / denom;
      if (t >= -kGeomEps && t <= 1.0 + kGeomEps) {
        push(s);
      }
    } else if (std::fabs(cross(ap, u)) <= kGeomEps * std::max(1.0, norm(ap))) {
      push(dot(ap, u));
      push(dot(sub(b, p), u));
    }
  }
  // Insertion sort; m <= 2 * kMaxVertices.
  for (std::size_t i = 1; i < m; ++i) {
    const double key = events[i];
    std::size_t j = i;
    while (j > 0U && events[j - 1U] > key) {
      events[j] = events[j - 1U];
      --j;
    }
    events[j] = key;
  }
  // The ray leaves the closed polygon at the first event after which the open interval up to the next
  // event lies outside. Beyond the last event the ray is outside, since the polygon is bounded.
  double previous = 0.0;
  for (std::size_t i = 0; i < m; ++i) {
    const double s = events[i];
    if (s - previous <= kGeomEps) {
      continue;
    }
    const double mid = 0.5 * (previous + s);
    if (!contains({p.x + mid * u.x, p.y + mid * u.y}, kGeomEps * 10.0)) {
      return previous;
    }
    previous = s;
  }
  return m > 0U ? previous : kInf;
}

const char * validate(const PredictorParameters & p) noexcept
{
  if (!(std::isfinite(p.a_brake_h_m_s2) && p.a_brake_h_m_s2 > 0.0)) {return "a_brake_h_m_s2 must be > 0";}
  if (!(std::isfinite(p.a_brake_v_m_s2) && p.a_brake_v_m_s2 > 0.0)) {return "a_brake_v_m_s2 must be > 0";}
  if (!(std::isfinite(p.k_sigma) && p.k_sigma >= 0.0)) {return "k_sigma must be >= 0";}
  if (!(std::isfinite(p.v_min_m_s) && p.v_min_m_s > 0.0)) {return "v_min_m_s must be > 0";}
  if (!(p.horizon_s > 0.0)) {return "horizon_s must be > 0";}
  return nullptr;
}

Prediction predict(
  const Fence & fence, const PredictorParameters & params, const VehicleState & s) noexcept
{
  Prediction out;
  const bool inside_h = fence.polygon.contains(s.position);
  const bool inside_v = s.altitude_m >= fence.alt_min_m - kGeomEps &&
    s.altitude_m <= fence.alt_max_m + kGeomEps;
  out.inside = inside_h && inside_v;
  if (!out.inside) {
    out.t_gf_s = out.t_horizontal_s = out.t_vertical_s = 0.0;
    out.exit_distance_m = 0.0;
    return out;
  }

  // Lateral (heading-independent) uncertainty bound. The ray model subtracts k_sigma * eph only
  // along the velocity, so hovering inside the uncertainty band of the boundary, or flying parallel
  // to it, produced T_gf = +inf although the true position may already be outside the fence
  // (review 2026-09-11 §4 "Lateral uncertainty is ignored"). A sample whose horizontal or vertical
  // uncertainty band reaches the boundary is a violation at this tick.
  const double lateral_margin_m = params.k_sigma * std::max(0.0, s.eph_m);
  const double vertical_margin_m = params.k_sigma * std::max(0.0, s.epv_m);
  const bool inside_lateral_band = lateral_margin_m > 0.0 &&
    fence.polygon.boundaryDistance(s.position) <= lateral_margin_m;
  const bool inside_vertical_band = vertical_margin_m > 0.0 &&
    (s.altitude_m - fence.alt_min_m <= vertical_margin_m ||
    fence.alt_max_m - s.altitude_m <= vertical_margin_m);
  if (inside_lateral_band || inside_vertical_band)
  {
    out.t_gf_s = out.t_horizontal_s = out.t_vertical_s = 0.0;
    out.exit_distance_m = 0.0;
    return out;
  }

  const double speed = norm(s.velocity);
  if (speed >= params.v_min_m_s) {
    const Vec2 u{s.velocity.x / speed, s.velocity.y / speed};
    out.exit_distance_m = fence.polygon.exitDistance(s.position, u);
    out.t_horizontal_s = channelTime(out.exit_distance_m, speed, params.a_brake_h_m_s2,
      params.k_sigma * std::max(0.0, s.eph_m), params.horizon_s);
  }

  const double climb = s.climb_rate_m_s;
  if (std::fabs(climb) >= params.v_min_m_s) {
    const double distance = climb > 0.0 ? fence.alt_max_m - s.altitude_m : s.altitude_m - fence.alt_min_m;
    out.t_vertical_s = channelTime(distance, std::fabs(climb), params.a_brake_v_m_s2,
      params.k_sigma * std::max(0.0, s.epv_m), params.horizon_s);
  }

  out.t_gf_s = std::min(out.t_horizontal_s, out.t_vertical_s);
  return out;
}

Vec2 projectToLocal(double lat_deg, double lon_deg, double ref_lat_deg, double ref_lon_deg) noexcept
{
  // Azimuthal equidistant projection, px4_ros2_cpp/src/utils/map_projection_impl.cpp:28-58.
  const double deg2rad = M_PI / 180.0;
  const double lat = lat_deg * deg2rad;
  const double lon = lon_deg * deg2rad;
  const double ref_lat = ref_lat_deg * deg2rad;
  const double ref_lon = ref_lon_deg * deg2rad;
  const double sin_lat = std::sin(lat);
  const double cos_lat = std::cos(lat);
  const double cos_d_lon = std::cos(lon - ref_lon);
  const double arg = std::clamp(std::sin(ref_lat) * sin_lat + std::cos(ref_lat) * cos_lat * cos_d_lon,
    -1.0, 1.0);
  const double c = std::acos(arg);
  const double k = std::fabs(c) > 0.0 ? c / std::sin(c) : 1.0;
  return {k * (std::cos(ref_lat) * sin_lat - std::sin(ref_lat) * cos_lat * cos_d_lon) * kEarthRadiusM,
    k * cos_lat * std::sin(lon - ref_lon) * kEarthRadiusM};
}

}  // namespace guara_geofence
