/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Smoke the geofence C ABI on the AC-8 convex straight-approach case.
 * Golden JSON comes later; the kernel never sees JSON.
 */
#include "guara/guara.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      return 1; \
    } \
  } while (0)

int main(void)
{
  /* 100 m square, origin at the centre. D=50 m, |v|=5, d_stop=5 m => T=9.0 s. */
  const double verts[] = {-50.0, -50.0, 50.0, -50.0, 50.0, 50.0, -50.0, 50.0};
  guara_gf_params p;
  guara_gf_params_default(&p);
  p.a_brake_h_m_s2 = 2.5;
  p.a_brake_v_m_s2 = 2.0;
  p.k_sigma = 2.0;
  p.v_min_m_s = 0.2;
  p.horizon_s = 30.0;
  guara_gf_state s;
  memset(&s, 0, sizeof s);
  s.altitude_m = 10.0;
  s.vn_m_s = 5.0;
  guara_gf_prediction out;
  memset(&out, 0, sizeof out);
  CHECK(guara_gf_predict(verts, 4, 0.0, 30.0, &p, &s, &out) == GUARA_OK);
  CHECK(out.inside == 1);
  CHECK(fabs(out.exit_distance_m - 50.0) < 1e-6);
  CHECK(fabs(out.t_gf_s - 9.0) < 0.05);
  CHECK(guara_gf_predict(NULL, 4, 0.0, 30.0, &p, &s, &out) == GUARA_ERR_NULL);
  {
    double north = 0.0;
    double east = 1.0;
    CHECK(guara_gf_project_to_local(-22.001, -47.89, -22.0, -47.89, &north, &east) == GUARA_OK);
    CHECK(fabs(north + 111.195) < 0.01);
    CHECK(fabs(east) < 1e-6);
  }
  {
    const double two[] = {0.0, 0.0, 1.0, 0.0};
    CHECK(guara_gf_polygon_error(two, 2) == GUARA_GF_POLY_TOO_FEW);
    const double bowtie[] = {0.0, 0.0, 10.0, 10.0, 10.0, 0.0, 0.0, 10.0};
    CHECK(guara_gf_polygon_error(bowtie, 4) == GUARA_GF_POLY_SELF_INTERSECT);
    const double nanv[] = {0.0, 0.0, NAN, 0.0, 0.0, 10.0};
    CHECK(guara_gf_polygon_error(nanv, 3) == GUARA_GF_POLY_NON_FINITE);
    CHECK(guara_gf_polygon_error(NULL, 3) == GUARA_GF_POLY_NON_FINITE);
    CHECK(strcmp(guara_gf_polygon_error_name(GUARA_GF_POLY_TOO_FEW), "too_few_vertices") == 0);
    CHECK(strcmp(guara_gf_polygon_error_name(99), "unknown") == 0);
    {
      guara_gf_params gp;
      guara_gf_params_default(&gp);
      CHECK(guara_gf_params_error(&gp) == NULL);
      gp.a_brake_h_m_s2 = 0.0;
      CHECK(strcmp(guara_gf_params_error(&gp), "a_brake_h_m_s2 must be > 0") == 0);
      CHECK(guara_gf_params_error(NULL) != NULL);
    }
  }
  printf("PASS abi_geofence\n");
  return 0;
}
