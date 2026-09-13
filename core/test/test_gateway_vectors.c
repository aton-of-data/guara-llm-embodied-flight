/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Drive GatewayLogic through the C ABI from ADR 0010 vectors.
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

#define EPS 1e-4

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
    char tmp[64];
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

static int parse_limits_fields(Cursor *c, guara_gateway_limits *p)
{
  if (!take(c, '{')) {
    return 0;
  }
  if (take(c, '}')) {
    return 1;
  }
  for (;;) {
    char key[40];
    double v = 0.0;
    if (!parse_string(c, key, sizeof key) || !take(c, ':') || !parse_number(c, &v)) {
      return 0;
    }
    if (strcmp(key, "max_speed_h_m_s") == 0) {
      p->max_speed_h_m_s = v;
    } else if (strcmp(key, "max_climb_rate_m_s") == 0) {
      p->max_climb_rate_m_s = v;
    } else if (strcmp(key, "max_descent_rate_m_s") == 0) {
      p->max_descent_rate_m_s = v;
    } else if (strcmp(key, "max_yaw_rate_rad_s") == 0) {
      p->max_yaw_rate_rad_s = v;
    } else if (strcmp(key, "future_stamp_tolerance_s") == 0) {
      p->future_stamp_tolerance_s = v;
    } else if (strcmp(key, "cf_timeout_s") == 0) {
      p->cf_timeout_s = v;
    }
    if (take(c, ',')) {
      continue;
    }
    return take(c, '}');
  }
}

static int check_limits_error(const char *id, int step_i, Cursor *c, const char *got)
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
    if (strcmp(key, "limits_error") == 0) {
      if (parse_null(c)) {
        ok = got == NULL;
        if (!ok) {
          fprintf(stderr, "FAIL %s step %d limits_error got %s want null\n",
                  id, step_i, got ? got : "null");
          return 0;
        }
      } else {
        char want[80] = {0};
        ok = parse_string(c, want, sizeof want) && got != NULL && strcmp(got, want) == 0;
        if (!ok) {
          fprintf(stderr, "FAIL %s step %d limits_error got %s want %s\n",
                  id, step_i, got ? got : "null", want);
          return 0;
        }
      }
    } else if (!skip_value(c)) {
      ok = 0;
    }
    if (!ok) {
      return 0;
    }
    if (take(c, ',')) {
      continue;
    }
    return take(c, '}');
  }
}

static int run_limits_step(Cursor *c, const guara_gateway_limits *base, const char *id, int step_i)
{
  guara_gateway_limits step_p = *base;
  int has_expect = 0;
  Cursor expect_at;
  memset(&expect_at, 0, sizeof expect_at);
  char op[32] = {0};
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
    if (strcmp(key, "op") == 0) {
      ok = parse_string(c, op, sizeof op);
    } else if (strcmp(key, "limits") == 0) {
      ok = parse_limits_fields(c, &step_p);
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
  if (strcmp(op, "check_gateway_limits") != 0) {
    fprintf(stderr, "FAIL %s step %d: unknown op %s\n", id, step_i, op);
    return 0;
  }
  const char *err = guara_gateway_limits_error(&step_p);
  if (has_expect) {
    Cursor ec = expect_at;
    if (!check_limits_error(id, step_i, &ec, err)) {
      return 0;
    }
  }
  return 1;
}

static int run_limits_vector(Cursor *c)
{
  char id[80] = "unknown";
  guara_gateway_limits limits;
  guara_gateway_limits_default(&limits);
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
    } else if (strcmp(key, "limits") == 0) {
      if (!parse_limits_fields(c, &limits)) {
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
  if (!has_steps) {
    fprintf(stderr, "FAIL %s: missing steps\n", id);
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
    if (!run_limits_step(&sc, &limits, id, step_i)) {
      return 0;
    }
    ++step_i;
    if (take(&sc, ',')) {
      continue;
    }
    return take(&sc, ']');
  }
}

static int parse_float_token(Cursor *c, float *out)
{
  skip_ws(c);
  if (peek(c) == '"') {
    char tok[8];
    if (!parse_string(c, tok, sizeof tok)) {
      return 0;
    }
    if (strcmp(tok, "nan") == 0) {
      *out = NAN;
      return 1;
    }
    if (strcmp(tok, "inf") == 0) {
      *out = INFINITY;
      return 1;
    }
    return 0;
  }
  double v;
  if (!parse_number(c, &v)) {
    return 0;
  }
  *out = (float)v;
  return 1;
}

static int parse_velocity(Cursor *c, float v[3])
{
  if (!take(c, '[')) {
    return 0;
  }
  for (int i = 0; i < 3; ++i) {
    if (i > 0 && !take(c, ',')) {
      return 0;
    }
    if (!parse_float_token(c, &v[i])) {
      return 0;
    }
  }
  return take(c, ']');
}

static int near_eq(float got, double want)
{
  if (isnan(got) && isnan(want)) {
    return 1;
  }
  return fabs((double)got - want) <= EPS;
}

static int check_expect(const char *id, int step_i, Cursor *c, const guara_gateway_output *out)
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
    if (strcmp(key, "forwarding_cf") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && out->forwarding_cf == (uint8_t)want;
      if (!ok) {
        fprintf(stderr, "FAIL %s step %d forwarding_cf got %u\n", id, step_i, out->forwarding_cf);
        return 0;
      }
    } else if (strcmp(key, "vx") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && near_eq(out->velocity_ned_m_s[0], want);
    } else if (strcmp(key, "vz") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && near_eq(out->velocity_ned_m_s[2], want);
    } else if (strcmp(key, "speed_h") == 0) {
      double want = 0.0;
      const double speed = hypot((double)out->velocity_ned_m_s[0], (double)out->velocity_ned_m_s[1]);
      ok = parse_number(c, &want) && fabs(speed - want) <= EPS;
    } else if (strcmp(key, "yaw") == 0) {
      if (parse_null(c)) {
        ok = isnan(out->yaw_ned_rad);
      } else {
        double want = 0.0;
        ok = parse_number(c, &want) && near_eq(out->yaw_ned_rad, want);
      }
    } else if (strcmp(key, "rejected_stamp") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && out->rejected_implausible_stamp == (uint32_t)want;
    } else if (strcmp(key, "rejected_non_finite") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && out->rejected_non_finite == (uint32_t)want;
    } else if (strcmp(key, "rejected_yaw") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && out->rejected_yaw == (uint32_t)want;
    } else if (strcmp(key, "rejected_guard") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && out->rejected_by_guard == (uint32_t)want;
    } else if (strcmp(key, "clamped") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && out->clamped == (uint32_t)want;
    } else {
      ok = skip_value(c);
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

static int run_step(Cursor *c, void *storage, const char *id, int step_i)
{
  char op[16] = {0};
  uint8_t state = 0;
  uint8_t guard_mode = 0;
  double t_s = 0.0;
  double t_recv_s = 0.0;
  double stamp_s = 0.0;
  float v[3] = {0.0F, 0.0F, 0.0F};
  float yaw = NAN;
  int has_expect = 0;
  Cursor expect_at;
  memset(&expect_at, 0, sizeof expect_at);

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
    if (strcmp(key, "op") == 0) {
      ok = parse_string(c, op, sizeof op);
    } else if (strcmp(key, "state") == 0) {
      double n = 0.0;
      ok = parse_number(c, &n);
      state = (uint8_t)n;
    } else if (strcmp(key, "mode") == 0) {
      double n = 0.0;
      ok = parse_number(c, &n);
      guard_mode = (uint8_t)n;
    } else if (strcmp(key, "t_s") == 0) {
      ok = parse_number(c, &t_s);
    } else if (strcmp(key, "t_recv_s") == 0) {
      ok = parse_number(c, &t_recv_s);
    } else if (strcmp(key, "stamp_s") == 0) {
      ok = parse_number(c, &stamp_s);
    } else if (strcmp(key, "v") == 0) {
      ok = parse_velocity(c, v);
    } else if (strcmp(key, "yaw") == 0) {
      if (parse_null(c)) {
        yaw = NAN;
      } else {
        double n = 0.0;
        ok = parse_number(c, &n);
        yaw = (float)n;
      }
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

  int rc = GUARA_OK;
  guara_gateway_output out;
  memset(&out, 0, sizeof out);
  if (strcmp(op, "state") == 0) {
    rc = guara_gateway_on_core_state(storage, state, t_s);
  } else if (strcmp(op, "guard") == 0) {
    rc = guara_gateway_set_guard(storage, guard_mode);
  } else if (strcmp(op, "setpoint") == 0) {
    rc = guara_gateway_on_cf_setpoint(storage, t_recv_s, stamp_s, v, yaw);
  } else if (strcmp(op, "compute") == 0) {
    rc = guara_gateway_compute(storage, t_s, &out);
  } else {
    fprintf(stderr, "FAIL %s step %d: unknown op %s\n", id, step_i, op);
    return 0;
  }
  if (rc != GUARA_OK) {
    fprintf(stderr, "FAIL %s step %d: ABI %s rc=%d\n", id, step_i, op, rc);
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
  char id[64] = "unknown";
  double timeout_s = 0.5;
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
    } else if (strcmp(key, "timeout_s") == 0) {
      if (!parse_number(c, &timeout_s)) {
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
  if (!has_steps) {
    fprintf(stderr, "FAIL %s: missing steps\n", id);
    return 0;
  }
  guara_gateway_limits limits;
  guara_gateway_limits_default(&limits);
  limits.cf_timeout_s = timeout_s;
  unsigned char raw[1024 + 64];
  unsigned char *buf = raw;
  {
    const size_t a = guara_gateway_storage_align();
    const uintptr_t addr = (uintptr_t)raw;
    const uintptr_t aligned = (addr + (a - 1U)) & ~(uintptr_t)(a - 1U);
    buf = (unsigned char *)aligned;
  }
  const size_t cap = (size_t)((raw + sizeof raw) - buf);
  if (guara_gateway_storage_size() > cap) {
    fprintf(stderr, "FAIL %s: storage %zu > %zu\n", id,
            guara_gateway_storage_size(), cap);
    return 0;
  }
  if (guara_gateway_init(buf, cap, &limits) != GUARA_OK) {
    fprintf(stderr, "FAIL %s: init rejected\n", id);
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
    if (!run_step(&sc, buf, id, step_i)) {
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
  const char *path = GUARA_VECTORS_DIR "/adr0010_gateway.json";
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
  if (nvec < 9) {
    fprintf(stderr, "FAIL expected at least 9 ADR 0010 vectors, got %d\n", nvec);
    return 1;
  }
  printf("PASS conformance_adr0010_gateway vectors=%d\n", nvec);

  const char *lim_path = GUARA_VECTORS_DIR "/gateway_limits.json";
  size_t ln = 0;
  char *lim_text = read_file(lim_path, &ln);
  CHECK(lim_text != NULL);
  Cursor lc = {lim_text, ln, 0};
  CHECK(take(&lc, '['));
  int nlim = 0;
  CHECK(!take(&lc, ']'));
  for (;;) {
    if (!run_limits_vector(&lc)) {
      free(lim_text);
      return 1;
    }
    ++nlim;
    if (take(&lc, ',')) {
      continue;
    }
    if (!take(&lc, ']')) {
      fprintf(stderr, "FAIL trailing JSON after gateway-limits vectors\n");
      free(lim_text);
      return 1;
    }
    break;
  }
  skip_ws(&lc);
  if (lc.i != lc.n) {
    fprintf(stderr, "FAIL trailing bytes after gateway-limits JSON\n");
    free(lim_text);
    return 1;
  }
  free(lim_text);
  if (nlim < 7) {
    fprintf(stderr, "FAIL expected at least 7 gateway-limits vectors, got %d\n", nlim);
    return 1;
  }
  printf("PASS conformance_gateway_limits vectors=%d\n", nlim);
  return 0;
}
