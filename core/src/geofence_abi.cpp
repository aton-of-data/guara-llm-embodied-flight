// SPDX-License-Identifier: Apache-2.0
//
// C ABI for the braking-aware geofence predictor (ADR 0004). Stateless.
#include "guara/guara.h"

#include "guara_geofence/predictor.hpp"

extern "C" {

void guara_gf_params_default(guara_gf_params * p)
{
  if (p == nullptr) {
    return;
  }
  const guara_geofence::PredictorParameters d;
  p->a_brake_h_m_s2 = d.a_brake_h_m_s2;
  p->a_brake_v_m_s2 = d.a_brake_v_m_s2;
  p->k_sigma = d.k_sigma;
  p->v_min_m_s = d.v_min_m_s;
  p->horizon_s = d.horizon_s;
}

const char * guara_gf_params_error(const guara_gf_params * p)
{
  if (p == nullptr) {
    return "params is null";
  }
  guara_geofence::PredictorParameters gp;
  gp.a_brake_h_m_s2 = p->a_brake_h_m_s2;
  gp.a_brake_v_m_s2 = p->a_brake_v_m_s2;
  gp.k_sigma = p->k_sigma;
  gp.v_min_m_s = p->v_min_m_s;
  gp.horizon_s = p->horizon_s;
  return guara_geofence::validate(gp);
}

int guara_gf_predict(const double * vertices_ne, size_t n_vertices, double alt_min_m,
  double alt_max_m, const guara_gf_params * params, const guara_gf_state * state,
  guara_gf_prediction * out)
{
  if (vertices_ne == nullptr || params == nullptr || state == nullptr || out == nullptr) {
    return GUARA_ERR_NULL;
  }
  if (n_vertices > GUARA_GF_MAX_VERTICES) {
    return GUARA_ERR_PARAMS;
  }
  guara_geofence::PredictorParameters p;
  p.a_brake_h_m_s2 = params->a_brake_h_m_s2;
  p.a_brake_v_m_s2 = params->a_brake_v_m_s2;
  p.k_sigma = params->k_sigma;
  p.v_min_m_s = params->v_min_m_s;
  p.horizon_s = params->horizon_s;
  if (guara_geofence::validate(p) != nullptr) {
    return GUARA_ERR_PARAMS;
  }
  guara_geofence::Vec2 verts[GUARA_GF_MAX_VERTICES];
  for (size_t i = 0; i < n_vertices; ++i) {
    verts[i].x = vertices_ne[2U * i];
    verts[i].y = vertices_ne[2U * i + 1U];
  }
  guara_geofence::Fence fence;
  fence.alt_min_m = alt_min_m;
  fence.alt_max_m = alt_max_m;
  if (fence.polygon.set(verts, n_vertices) != guara_geofence::PolygonError::kNone) {
    return GUARA_ERR_PARAMS;
  }
  guara_geofence::VehicleState s;
  s.position = {state->north_m, state->east_m};
  s.altitude_m = state->altitude_m;
  s.velocity = {state->vn_m_s, state->ve_m_s};
  s.climb_rate_m_s = state->climb_rate_m_s;
  s.eph_m = state->eph_m;
  s.epv_m = state->epv_m;
  const guara_geofence::Prediction pr = guara_geofence::predict(fence, p, s);
  out->t_gf_s = pr.t_gf_s;
  out->t_horizontal_s = pr.t_horizontal_s;
  out->t_vertical_s = pr.t_vertical_s;
  out->inside = pr.inside ? 1 : 0;
  out->exit_distance_m = pr.exit_distance_m;
  return GUARA_OK;
}

int guara_gf_project_to_local(double lat_deg, double lon_deg, double ref_lat_deg,
  double ref_lon_deg, double * north_m, double * east_m)
{
  if (north_m == nullptr || east_m == nullptr) {
    return GUARA_ERR_NULL;
  }
  const guara_geofence::Vec2 p = guara_geofence::projectToLocal(
    lat_deg, lon_deg, ref_lat_deg, ref_lon_deg);
  *north_m = p.x;
  *east_m = p.y;
  return GUARA_OK;
}

int guara_gf_polygon_error(const double * vertices_ne, size_t n_vertices)
{
  static_assert(static_cast<int>(guara_geofence::PolygonError::kNone) == GUARA_GF_POLY_NONE);
  static_assert(
    static_cast<int>(guara_geofence::PolygonError::kTooFewVertices) == GUARA_GF_POLY_TOO_FEW);
  static_assert(
    static_cast<int>(guara_geofence::PolygonError::kTooManyVertices) == GUARA_GF_POLY_TOO_MANY);
  static_assert(
    static_cast<int>(guara_geofence::PolygonError::kNonFiniteVertex) == GUARA_GF_POLY_NON_FINITE);
  static_assert(
    static_cast<int>(guara_geofence::PolygonError::kDegenerateEdge) == GUARA_GF_POLY_DEGENERATE);
  static_assert(static_cast<int>(guara_geofence::PolygonError::kSelfIntersecting) ==
    GUARA_GF_POLY_SELF_INTERSECT);
  static_assert(
    static_cast<int>(guara_geofence::PolygonError::kZeroArea) == GUARA_GF_POLY_ZERO_AREA);
  if (n_vertices == 0U) {
    return GUARA_GF_POLY_TOO_FEW;
  }
  if (vertices_ne == nullptr) {
    return GUARA_GF_POLY_NON_FINITE;
  }
  if (n_vertices > GUARA_GF_MAX_VERTICES) {
    return GUARA_GF_POLY_TOO_MANY;
  }
  guara_geofence::Vec2 verts[GUARA_GF_MAX_VERTICES];
  for (size_t i = 0; i < n_vertices; ++i) {
    verts[i].x = vertices_ne[2U * i];
    verts[i].y = vertices_ne[2U * i + 1U];
  }
  guara_geofence::Polygon poly;
  return static_cast<int>(poly.set(verts, n_vertices));
}

}  // extern "C"
