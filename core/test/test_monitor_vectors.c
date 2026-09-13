/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Drive MonitorTable through the C ABI from H-4/H-6 vectors.
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

static int check_expect(const char *id, int step_i, Cursor *c, const guara_monitor_eval *ev)
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
    if (strcmp(key, "violation") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && ev->violation == (uint8_t)want;
      if (!ok) {
        fprintf(stderr, "FAIL %s step %d violation got %u\n", id, step_i, ev->violation);
        return 0;
      }
    } else if (strcmp(key, "action") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && ev->action == (uint8_t)want;
      if (!ok) {
        fprintf(stderr, "FAIL %s step %d action got %u\n", id, step_i, ev->action);
        return 0;
      }
    } else if (strcmp(key, "invalid") == 0) {
      double want = 0.0;
      ok = parse_number(c, &want) && ev->invalid == (uint8_t)want;
      if (!ok) {
        fprintf(stderr, "FAIL %s step %d invalid got %u\n", id, step_i, ev->invalid);
        return 0;
      }
    } else if (strcmp(key, "first_violating_id") == 0) {
      char want[80];
      ok = parse_string(c, want, sizeof want) && strcmp(ev->first_violating_id, want) == 0;
      if (!ok) {
        fprintf(stderr, "FAIL %s step %d first_violating_id got %s\n",
                id, step_i, ev->first_violating_id);
        return 0;
      }
    } else if (strcmp(key, "first_invalid_id") == 0) {
      char want[80];
      ok = parse_string(c, want, sizeof want) && strcmp(ev->first_invalid_id, want) == 0;
      if (!ok) {
        fprintf(stderr, "FAIL %s step %d first_invalid_id got %s\n",
                id, step_i, ev->first_invalid_id);
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

static int run_step(Cursor *c, void *storage, const char *id, int step_i)
{
  char op[16] = {0};
  char mon_id[80] = {0};
  double t_s = 0.0;
  double t_recv_s = 0.0;
  double violated = 0.0;
  double action = 0.0;
  double monitor_class = 1.0;
  double complete = 1.0;
  int has_accept = 0;
  int want_accept = 0;
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
    } else if (strcmp(key, "id") == 0) {
      ok = parse_string(c, mon_id, sizeof mon_id);
    } else if (strcmp(key, "t_s") == 0) {
      ok = parse_number(c, &t_s);
    } else if (strcmp(key, "t_recv_s") == 0) {
      ok = parse_number(c, &t_recv_s);
    } else if (strcmp(key, "violated") == 0) {
      ok = parse_number(c, &violated);
    } else if (strcmp(key, "action") == 0) {
      ok = parse_number(c, &action);
    } else if (strcmp(key, "class") == 0) {
      ok = parse_number(c, &monitor_class);
    } else if (strcmp(key, "complete") == 0) {
      ok = parse_number(c, &complete);
    } else if (strcmp(key, "expect_accept") == 0) {
      double n = 0.0;
      ok = parse_number(c, &n);
      has_accept = 1;
      want_accept = (int)n;
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

  if (strcmp(op, "expect") == 0) {
    const int rc = guara_monitor_expect(storage, mon_id);
    if (rc != GUARA_OK) {
      fprintf(stderr, "FAIL %s step %d: expect rc=%d\n", id, step_i, rc);
      return 0;
    }
    return 1;
  }
  if (strcmp(op, "observe") == 0) {
    guara_monitor_sample s;
    memset(&s, 0, sizeof s);
    s.id = mon_id;
    s.monitor_class = (uint8_t)monitor_class;
    s.action = (uint8_t)action;
    s.violated = (uint8_t)violated;
    s.inputs_complete = (uint8_t)complete;
    const int acc = guara_monitor_observe(storage, &s, t_recv_s);
    if (has_accept && acc != want_accept) {
      fprintf(stderr, "FAIL %s step %d: accept got %d want %d\n",
              id, step_i, acc, want_accept);
      return 0;
    }
    return 1;
  }
  if (strcmp(op, "evaluate") == 0) {
    guara_monitor_eval ev;
    memset(&ev, 0, sizeof ev);
    const int rc = guara_monitor_evaluate(storage, t_s, &ev);
    if (rc != GUARA_OK) {
      fprintf(stderr, "FAIL %s step %d: evaluate rc=%d\n", id, step_i, rc);
      return 0;
    }
    if (has_expect) {
      Cursor ec = expect_at;
      if (!check_expect(id, step_i, &ec, &ev)) {
        return 0;
      }
    }
    return 1;
  }
  fprintf(stderr, "FAIL %s step %d: unknown op %s\n", id, step_i, op);
  return 0;
}

static int run_vector(Cursor *c)
{
  char id[80] = "unknown";
  double max_age_s = 0.5;
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
    } else if (strcmp(key, "max_age_s") == 0) {
      if (!parse_number(c, &max_age_s)) {
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
  unsigned char raw[4096];
  const size_t a = guara_monitor_storage_align();
  const uintptr_t addr = (uintptr_t)raw;
  unsigned char *buf = (unsigned char *)((addr + (a - 1U)) & ~(uintptr_t)(a - 1U));
  const size_t cap = (size_t)((raw + sizeof raw) - buf);
  if (guara_monitor_init(buf, cap, max_age_s) != GUARA_OK) {
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
  const char *path = GUARA_VECTORS_DIR "/monitor_table.json";
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
    fprintf(stderr, "FAIL expected at least 10 monitor vectors, got %d\n", nvec);
    return 1;
  }
  printf("PASS conformance_monitor_table vectors=%d\n", nvec);
  return 0;
}
