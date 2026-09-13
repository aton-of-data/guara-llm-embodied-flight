/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Drive the geofence C ABI from published AC-8 / uncertainty vectors.
 * The parser lives in this test. The kernel never sees JSON.
 */
#include "guara/guara.h"

#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef GUARA_VECTORS_DIR
#error "GUARA_VECTORS_DIR must be the source conformance/vectors directory"
#endif

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      return 1; \
    } \
  } while (0)

#define TIME_TOL 0.05
#define DIST_TOL 1e-6
#define MAX_VERTS 64

typedef struct {
  const char *s;
  size_t n;
  size_t i;
} Cursor;

static void skip_ws(Cursor *c)
{
  while (c->i < c->n && isspace((unsigned char)c->s[c->i])) {
    ++c->i;
  }
}

static int peek(Cursor *c)
{
  skip_ws(c);
  return c->i < c->n ? (unsigned char)c->s[c->i] : -1;
}

static int take(Cursor *c, char ch)
{
  if (peek(c) != (unsigned char)ch) {
    return 0;
  }
  ++c->i;
  return 1;
}

static int parse_string(Cursor *c, char *out, size_t cap)
{
  skip_ws(c);
  if (!take(c, '"')) {
    return 0;
  }
  size_t k = 0;
  while (c->i < c->n && c->s[c->i] != '"') {
    if (c->s[c->i] == '\\' || k + 1 >= cap) {
      return 0;
    }
    out[k++] = c->s[c->i++];
  }
  if (!take(c, '"')) {
    return 0;
  }
  out[k] = 0;
  return 1;
}

static int parse_number(Cursor *c, double *out)
{
  skip_ws(c);
  char *end = NULL;
  const double v = strtod(c->s + c->i, &end);
  if (end == c->s + c->i) {
    return 0;
  }
  c->i = (size_t)(end - c->s);
  *out = v;
  return 1;
}

static int parse_null(Cursor *c)
{
  skip_ws(c);
  if (c->i + 4 <= c->n && memcmp(c->s + c->i, "null", 4) == 0) {
    c->i += 4;
    return 1;
  }
  return 0;
}

static int skip_value(Cursor *c);

static int skip_object_or_array(Cursor *c, char open, char close)
{
  if (!take(c, open)) {
    return 0;
  }
  if (take(c, close)) {
    return 1;
  }
  for (;;) {
    if (open == '{') {
      char key[32];
      if (!parse_string(c, key, sizeof key) || !take(c, ':')) {
        return 0;
      }
    }
    if (!skip_value(c)) {
      return 0;
    }
    if (take(c, ',')) {
      continue;
    }
    return take(c, close);
  }
}

static int skip_value(Cursor *c)
{
  const int ch = peek(c);
  if (ch == '"') {
    char tmp[80];
    return parse_string(c, tmp, sizeof tmp);
  }
  if (ch == '{') {
    return skip_object_or_array(c, '{', '}');
  }
  if (ch == '[') {
    return skip_object_or_array(c, '[', ']');
  }
  if (ch == 'n') {
    return parse_null(c);
  }
  if (ch == 't' || ch == 'f') {
    skip_ws(c);
    if (c->i + 4 <= c->n && memcmp(c->s + c->i, "true", 4) == 0) {
      c->i += 4;
      return 1;
    }
    if (c->i + 5 <= c->n && memcmp(c->s + c->i, "false", 5) == 0) {
      c->i += 5;
      return 1;
    }
    return 0;
  }
  double v;
  return parse_number(c, &v);
}

static int parse_want_time(Cursor *c, double *out, int *is_inf)
{
  if (peek(c) == '"') {
    char tok[8];
    if (!parse_string(c, tok, sizeof tok)) {
      return 0;
    }
    if (strcmp(tok, "inf") == 0) {
      *is_inf = 1;
      *out = INFINITY;
      return 1;
    }
    return 0;
  }
  *is_inf = 0;
  return parse_number(c, out);
}

static int time_ok(double got, double want, int want_inf)
{
  if (want_inf) {
    return isinf(got) && got > 0.0;
  }
  return fabs(got - want) <= TIME_TOL;
}

static int dist_ok(double got, double want)
{
  return fabs(got - want) <= DIST_TOL;
}

static int parse_vertices(Cursor *c, double *out, size_t cap, size_t *n)
{
  if (!take(c, '[')) {
    return 0;
  }
  *n = 0;
  if (take(c, ']')) {
    return 1;
  }
  for (;;) {
    if (*n >= cap) {
      return 0;
    }
    if (!parse_number(c, &out[*n])) {
      return 0;
    }
    ++*n;
    if (take(c, ',')) {
      continue;
    }
    return take(c, ']');
  }
}

static int parse_params(Cursor *c, guara_gf_params *p)
{
  guara_gf_params_default(p);
  if (!take(c, '{')) {
    return 0;
  }
  if (take(c, '}')) {
    return 1;
  }
  for (;;) {
    char key[32];
    double v = 0.0;
    if (!parse_string(c, key, sizeof key) || !take(c, ':') || !parse_number(c, &v)) {
      return 0;
    }
    if (strcmp(key, "a_brake_h_m_s2") == 0) {
      p->a_brake_h_m_s2 = v;
    } else if (strcmp(key, "a_brake_v_m_s2") == 0) {
      p->a_brake_v_m_s2 = v;
    } else if (strcmp(key, "k_sigma") == 0) {
      p->k_sigma = v;
    } else if (strcmp(key, "v_min_m_s") == 0) {
      p->v_min_m_s = v;
    } else if (strcmp(key, "horizon_s") == 0) {
      p->horizon_s = v;
    }
    if (take(c, ',')) {
      continue;
    }
    return take(c, '}');
  }
}

static int check_expect(const char *id, int step_i, Cursor *c, const guara_gf_prediction *got)
{
  if (!take(c, '{')) {
    return 0;
  }
  if (take(c, '}')) {
    return 1;
  }
  for (;;) {
    char key[32];
    if (!parse_string(c, key, sizeof key) || !take(c, ':')) {
      return 0;
    }
    int ok = 1;
    if (strcmp(key, "inside") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && got->inside == (uint8_t)want;
    } else if (strcmp(key, "exit_distance_m") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && dist_ok(got->exit_distance_m, want);
    } else if (strcmp(key, "t_gf_s") == 0 || strcmp(key, "t_horizontal_s") == 0 ||
               strcmp(key, "t_vertical_s") == 0) {
      double want = 0.0;
      int inf = 0;
      const double gotv = strcmp(key, "t_gf_s") == 0 ? got->t_gf_s :
                          strcmp(key, "t_horizontal_s") == 0 ? got->t_horizontal_s :
                          got->t_vertical_s;
      ok = parse_want_time(c, &want, &inf) && time_ok(gotv, want, inf);
      if (!ok) {
        fprintf(stderr, "FAIL %s step %d %s got %g\n", id, step_i, key, gotv);
        return 0;
      }
    } else if (!skip_value(c)) {
      ok = 0;
    }
    if (!ok) {
      fprintf(stderr, "FAIL %s step %d field %s\n", id, step_i, key);
      return 0;
    }
    if (take(c, ',')) {
      continue;
    }
    return take(c, '}');
  }
}

static int run_step(Cursor *c, const double *verts, size_t nflat, double alt_min,
                    double alt_max, const guara_gf_params *params, const char *id,
                    int step_i)
{
  guara_gf_state st;
  memset(&st, 0, sizeof st);
  int has_expect = 0;
  Cursor expect_at;
  memset(&expect_at, 0, sizeof expect_at);
  char op[16] = {0};
  if (!take(c, '{')) {
    return 0;
  }
  if (take(c, '}')) {
    return 0;
  }
  for (;;) {
    char key[32];
    if (!parse_string(c, key, sizeof key) || !take(c, ':')) {
      return 0;
    }
    int ok = 1;
    double v = 0.0;
    if (strcmp(key, "op") == 0) {
      ok = parse_string(c, op, sizeof op);
    } else if (strcmp(key, "north_m") == 0) {
      ok = parse_number(c, &v);
      st.north_m = v;
    } else if (strcmp(key, "east_m") == 0) {
      ok = parse_number(c, &v);
      st.east_m = v;
    } else if (strcmp(key, "altitude_m") == 0) {
      ok = parse_number(c, &v);
      st.altitude_m = v;
    } else if (strcmp(key, "vn_m_s") == 0) {
      ok = parse_number(c, &v);
      st.vn_m_s = v;
    } else if (strcmp(key, "ve_m_s") == 0) {
      ok = parse_number(c, &v);
      st.ve_m_s = v;
    } else if (strcmp(key, "climb_rate_m_s") == 0) {
      ok = parse_number(c, &v);
      st.climb_rate_m_s = v;
    } else if (strcmp(key, "eph_m") == 0) {
      ok = parse_number(c, &v);
      st.eph_m = v;
    } else if (strcmp(key, "epv_m") == 0) {
      ok = parse_number(c, &v);
      st.epv_m = v;
    } else if (strcmp(key, "expect") == 0) {
      expect_at = *c;
      ok = skip_value(c);
      has_expect = 1;
    } else {
      ok = skip_value(c);
    }
    if (!ok) {
      fprintf(stderr, "FAIL %s step %d: bad field %s\n", id, step_i, key);
      return 0;
    }
    if (take(c, ',')) {
      continue;
    }
    if (!take(c, '}')) {
      return 0;
    }
    break;
  }
  if (strcmp(op, "predict") != 0) {
    fprintf(stderr, "FAIL %s step %d: unknown op %s\n", id, step_i, op);
    return 0;
  }
  guara_gf_prediction out;
  memset(&out, 0, sizeof out);
  if (guara_gf_predict(verts, nflat / 2U, alt_min, alt_max, params, &st, &out) != GUARA_OK) {
    fprintf(stderr, "FAIL %s step %d: predict rejected\n", id, step_i);
    return 0;
  }
  if (has_expect) {
    Cursor ec = expect_at;
    if (!check_expect(id, step_i, &ec, &out)) {
      return 0;
    }
  }
  return 1;
}

static int run_vector(Cursor *c)
{
  char id[80] = "unknown";
  double verts[2 * MAX_VERTS];
  size_t nflat = 0;
  double alt_min = 0.0;
  double alt_max = 1.0e9;
  guara_gf_params params;
  guara_gf_params_default(&params);
  int has_steps = 0;
  Cursor steps_at;
  memset(&steps_at, 0, sizeof steps_at);
  if (!take(c, '{')) {
    return 0;
  }
  if (take(c, '}')) {
    return 0;
  }
  for (;;) {
    char key[32];
    if (!parse_string(c, key, sizeof key) || !take(c, ':')) {
      return 0;
    }
    if (strcmp(key, "id") == 0) {
      if (!parse_string(c, id, sizeof id)) {
        return 0;
      }
    } else if (strcmp(key, "vertices") == 0) {
      if (!parse_vertices(c, verts, sizeof verts / sizeof verts[0], &nflat)) {
        return 0;
      }
    } else if (strcmp(key, "alt_min_m") == 0) {
      if (!parse_number(c, &alt_min)) {
        return 0;
      }
    } else if (strcmp(key, "alt_max_m") == 0) {
      if (!parse_number(c, &alt_max)) {
        return 0;
      }
    } else if (strcmp(key, "params") == 0) {
      if (!parse_params(c, &params)) {
        return 0;
      }
    } else if (strcmp(key, "steps") == 0) {
      steps_at = *c;
      if (!skip_value(c)) {
        return 0;
      }
      has_steps = 1;
    } else if (!skip_value(c)) {
      return 0;
    }
    if (take(c, ',')) {
      continue;
    }
    if (!take(c, '}')) {
      return 0;
    }
    break;
  }
  if (!has_steps || nflat < 6U || (nflat % 2U) != 0U) {
    fprintf(stderr, "FAIL %s: missing vertices or steps\n", id);
    return 0;
  }
  Cursor sc = steps_at;
  if (!take(&sc, '[')) {
    return 0;
  }
  int step_i = 0;
  if (take(&sc, ']')) {
    fprintf(stderr, "FAIL %s: no steps\n", id);
    return 0;
  }
  for (;;) {
    if (!run_step(&sc, verts, nflat, alt_min, alt_max, &params, id, step_i)) {
      return 0;
    }
    ++step_i;
    if (take(&sc, ',')) {
      continue;
    }
    return take(&sc, ']');
  }
}

static char *read_file(const char *path, size_t *n)
{
  FILE *f = fopen(path, "rb");
  if (f == NULL) {
    fprintf(stderr, "FAIL cannot open %s\n", path);
    return NULL;
  }
  if (fseek(f, 0, SEEK_END) != 0) {
    fclose(f);
    return NULL;
  }
  const long sz = ftell(f);
  if (sz < 0 || sz > 1024L * 1024L) {
    fclose(f);
    return NULL;
  }
  if (fseek(f, 0, SEEK_SET) != 0) {
    fclose(f);
    return NULL;
  }
  char *buf = (char *)malloc((size_t)sz + 1U);
  if (buf == NULL) {
    fclose(f);
    return NULL;
  }
  if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) {
    free(buf);
    fclose(f);
    return NULL;
  }
  fclose(f);
  buf[sz] = 0;
  *n = (size_t)sz;
  return buf;
}

int main(void)
{
  const char *path = GUARA_VECTORS_DIR "/geofence.json";
  size_t n = 0;
  char *text = read_file(path, &n);
  CHECK(text != NULL);
  Cursor c = {text, n, 0};
  CHECK(take(&c, '['));
  int nvec = 0;
  CHECK(!take(&c, ']'));
  for (;;) {
    if (!run_vector(&c)) {
      free(text);
      return 1;
    }
    ++nvec;
    if (take(&c, ',')) {
      continue;
    }
    if (!take(&c, ']')) {
      fprintf(stderr, "FAIL trailing JSON after vectors\n");
      free(text);
      return 1;
    }
    break;
  }
  skip_ws(&c);
  if (c.i != c.n) {
    fprintf(stderr, "FAIL trailing bytes after JSON array\n");
    free(text);
    return 1;
  }
  free(text);
  if (nvec < 18) {
    fprintf(stderr, "FAIL expected at least 18 geofence vectors, got %d\n", nvec);
    return 1;
  }
  printf("PASS conformance_geofence vectors=%d\n", nvec);
  return 0;
}
