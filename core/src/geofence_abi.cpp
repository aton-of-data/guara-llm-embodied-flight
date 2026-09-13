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

}  // extern "C"
