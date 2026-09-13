/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Drive guara_params_error from published core-parameter vectors.
 * The parser lives in this test. The kernel never sees JSON.
 */
#include "guara/guara.h"

#include <ctype.h>
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

static int parse_params_fields(Cursor *c, guara_params *p)
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
    double v = 0.0;
    if (strcmp(key, "return_enabled") == 0 || strcmp(key, "escalation_enabled") == 0) {
      if (!skip_value(c)) {
        return 0;
      }
    } else if (!parse_number(c, &v)) {
      return 0;
    } else if (strcmp(key, "tau_daa_s") == 0) {
      p->tau_daa_s = v;
    } else if (strcmp(key, "tau_gf_s") == 0) {
      p->tau_gf_s = v;
    } else if (strcmp(key, "h_daa_s") == 0) {
      p->h_daa_s = v;
    } else if (strcmp(key, "h_gf_s") == 0) {
      p->h_gf_s = v;
    } else if (strcmp(key, "dwell_s") == 0) {
      p->dwell_s = v;
    } else if (strcmp(key, "n_max") == 0) {
      p->n_max = (uint16_t)v;
    } else if (strcmp(key, "window_s") == 0) {
      p->window_s = v;
    } else if (strcmp(key, "escalation_s") == 0) {
      p->escalation_s = v;
    }
    if (take(c, ',')) {
      continue;
    }
    return take(c, '}');
  }
}

static int check_params_error(const char *id, int step_i, Cursor *c, const char *got)
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
    if (strcmp(key, "params_error") == 0) {
      if (parse_null(c)) {
        ok = got == NULL;
        if (!ok) {
          fprintf(stderr, "FAIL %s step %d params_error got %s want null\n",
                  id, step_i, got ? got : "null");
          return 0;
        }
      } else {
        char want[80] = {0};
        ok = parse_string(c, want, sizeof want) && got != NULL && strcmp(got, want) == 0;
        if (!ok) {
          fprintf(stderr, "FAIL %s step %d params_error got %s want %s\n",
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

static int run_step(Cursor *c, const guara_params *base, const char *id, int step_i)
{
  guara_params step_p = *base;
  int has_expect = 0;
  Cursor expect_at;
  memset(&expect_at, 0, sizeof expect_at);
  char op[24] = {0};
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
    } else if (strcmp(key, "params") == 0) {
      ok = parse_params_fields(c, &step_p);
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
  if (strcmp(op, "check_core_params") != 0) {
    fprintf(stderr, "FAIL %s step %d: unknown op %s\n", id, step_i, op);
    return 0;
  }
  const char *err = guara_params_error(&step_p);
  if (has_expect) {
    Cursor ec = expect_at;
    if (!check_params_error(id, step_i, &ec, err)) {
      return 0;
    }
  }
  return 1;
}

static int run_vector(Cursor *c)
{
  char id[80] = "unknown";
  guara_params params;
  guara_params_default(&params);
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
    } else if (strcmp(key, "params") == 0) {
      if (!parse_params_fields(c, &params)) {
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
    if (!run_step(&sc, &params, id, step_i)) {
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
  const char *path = GUARA_VECTORS_DIR "/core_params.json";
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
  if (nvec < 10) {
    fprintf(stderr, "FAIL expected at least 10 core-params vectors, got %d\n", nvec);
    return 1;
  }
  printf("PASS conformance_core_params vectors=%d\n", nvec);
  return 0;
}
