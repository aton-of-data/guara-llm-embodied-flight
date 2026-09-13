/* SPDX-License-Identifier: Apache-2.0 */
/*
 * M19 start: drive the C ABI from published SPEC §3 vectors.
 * The parser lives in this test. The kernel never sees JSON.
 */
#include "guara/guara.h"

#include <ctype.h>
#include <math.h>
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
    if (c->s[c->i] == '\\') {
      return 0;
    }
    if (k + 1 >= cap) {
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

static int parse_bool(Cursor *c, int *out)
{
  skip_ws(c);
  if (c->i + 4 <= c->n && memcmp(c->s + c->i, "true", 4) == 0) {
    c->i += 4;
    *out = 1;
    return 1;
  }
  if (c->i + 5 <= c->n && memcmp(c->s + c->i, "false", 5) == 0) {
    c->i += 5;
    *out = 0;
    return 1;
  }
  return 0;
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

static int skip_object_or_array(Cursor *c, char open_ch, char close_ch)
{
  if (!take(c, open_ch)) {
    return 0;
  }
  if (take(c, close_ch)) {
    return 1;
  }
  for (;;) {
    if (open_ch == '{') {
      char key[64];
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
    return take(c, close_ch);
  }
}

static int skip_value(Cursor *c)
{
  const int ch = peek(c);
  if (ch == '"') {
    char tmp[256];
    return parse_string(c, tmp, sizeof tmp);
  }
  if (ch == '{') {
    return skip_object_or_array(c, '{', '}');
  }
  if (ch == '[') {
    return skip_object_or_array(c, '[', ']');
  }
  if (ch == 't' || ch == 'f') {
    int b;
    return parse_bool(c, &b);
  }
  if (ch == 'n') {
    return parse_null(c);
  }
  double v;
  return parse_number(c, &v);
}

static int parse_time_signal(Cursor *c, double *out)
{
  if (parse_null(c)) {
    *out = INFINITY;
    return 1;
  }
  return parse_number(c, out);
}

static int parse_u8_number(Cursor *c, uint8_t *out)
{
  double v;
  if (!parse_number(c, &v) || v < 0.0 || v > 255.0 || v != (double)(unsigned)v) {
    return 0;
  }
  *out = (uint8_t)v;
  return 1;
}

enum {
  HAS_STATE = 1,
  HAS_RECOVERY = 2,
  HAS_COMMAND = 4,
  HAS_TRANS = 8,
  HAS_CAUSES = 16
};

typedef struct {
  unsigned has;
  uint8_t state;
  uint8_t recovery;
  uint8_t command;
  uint8_t transition;
  uint32_t unsafe_causes;
} Expect;

static int parse_expect(Cursor *c, Expect *e)
{
  memset(e, 0, sizeof *e);
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
    if (strcmp(key, "state") == 0) {
      if (!parse_u8_number(c, &e->state)) {
        return 0;
      }
      e->has |= HAS_STATE;
    } else if (strcmp(key, "recovery") == 0) {
      if (!parse_u8_number(c, &e->recovery)) {
        return 0;
      }
      e->has |= HAS_RECOVERY;
    } else if (strcmp(key, "command") == 0) {
      if (!parse_u8_number(c, &e->command)) {
        return 0;
      }
      e->has |= HAS_COMMAND;
    } else if (strcmp(key, "transition") == 0) {
      if (!parse_u8_number(c, &e->transition)) {
        return 0;
      }
      e->has |= HAS_TRANS;
    } else if (strcmp(key, "unsafe_causes") == 0) {
      double v;
      if (!parse_number(c, &v) || v < 0.0 || v > 4294967295.0) {
        return 0;
      }
      e->unsafe_causes = (uint32_t)v;
      e->has |= HAS_CAUSES;
    } else if (!skip_value(c)) {
      return 0;
    }
    if (take(c, ',')) {
      continue;
    }
    return take(c, '}');
  }
}

static int parse_inputs(Cursor *c, guara_inputs *in)
{
  memset(in, 0, sizeof *in);
  in->t_daa_s = INFINITY;
  in->t_gf_s = INFINITY;
  in->monitor_action = 1;
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
    if (strcmp(key, "t_s") == 0) {
      ok = parse_number(c, &in->t_s);
    } else if (strcmp(key, "in_charge") == 0) {
      ok = parse_u8_number(c, &in->in_charge);
    } else if (strcmp(key, "owned_mode_active") == 0) {
      ok = parse_u8_number(c, &in->owned_mode_active);
    } else if (strcmp(key, "t_daa_s") == 0) {
      ok = parse_time_signal(c, &in->t_daa_s);
    } else if (strcmp(key, "t_gf_s") == 0) {
      ok = parse_time_signal(c, &in->t_gf_s);
    } else if (strcmp(key, "monitor_violation") == 0) {
      ok = parse_u8_number(c, &in->monitor_violation);
    } else if (strcmp(key, "monitor_action") == 0) {
      ok = parse_u8_number(c, &in->monitor_action);
    } else if (strcmp(key, "input_invalid") == 0) {
      ok = parse_u8_number(c, &in->input_invalid);
    } else if (strcmp(key, "cf_intent_unsafe") == 0) {
      ok = parse_u8_number(c, &in->cf_intent_unsafe);
    } else {
      ok = skip_value(c);
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

static int apply_params_key(guara_params *p, const char *key, Cursor *c)
{
  if (strcmp(key, "tau_daa_s") == 0) {return parse_number(c, &p->tau_daa_s);}
  if (strcmp(key, "tau_gf_s") == 0) {return parse_number(c, &p->tau_gf_s);}
  if (strcmp(key, "h_daa_s") == 0) {return parse_number(c, &p->h_daa_s);}
  if (strcmp(key, "h_gf_s") == 0) {return parse_number(c, &p->h_gf_s);}
  if (strcmp(key, "dwell_s") == 0) {return parse_number(c, &p->dwell_s);}
  if (strcmp(key, "window_s") == 0) {return parse_number(c, &p->window_s);}
  if (strcmp(key, "escalation_s") == 0) {return parse_number(c, &p->escalation_s);}
  if (strcmp(key, "n_max") == 0) {
    double v;
    if (!parse_number(c, &v) || v < 1.0 || v > 65535.0) {return 0;}
    p->n_max = (uint16_t)v;
    return 1;
  }
  if (strcmp(key, "return_enabled") == 0) {
    int b;
    if (!parse_bool(c, &b)) {return 0;}
    p->return_enabled = (uint8_t)b;
    return 1;
  }
  if (strcmp(key, "escalation_enabled") == 0) {
    int b;
    if (!parse_bool(c, &b)) {return 0;}
    p->escalation_enabled = (uint8_t)b;
    return 1;
  }
  return skip_value(c);
}

static int parse_params_obj(Cursor *c, guara_params *p)
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
    if (!apply_params_key(p, key, c)) {
      return 0;
    }
    if (take(c, ',')) {
      continue;
    }
    return take(c, '}');
  }
}

static int check_expect(const char *id, int step_i, const Expect *e, const guara_output *out)
{
  if ((e->has & HAS_STATE) && out->state != e->state) {
    fprintf(stderr, "FAIL %s step %d state got %u want %u\n", id, step_i, out->state, e->state);
    return 0;
  }
  if ((e->has & HAS_RECOVERY) && out->recovery != e->recovery) {
    fprintf(stderr, "FAIL %s step %d recovery got %u want %u\n",
            id, step_i, out->recovery, e->recovery);
    return 0;
  }
  if ((e->has & HAS_COMMAND) && out->command != e->command) {
    fprintf(stderr, "FAIL %s step %d command got %u want %u\n",
            id, step_i, out->command, e->command);
    return 0;
  }
  if ((e->has & HAS_TRANS) && out->transition.id != e->transition) {
    fprintf(stderr, "FAIL %s step %d transition got %u want %u\n",
            id, step_i, out->transition.id, e->transition);
    return 0;
  }
  if ((e->has & HAS_CAUSES) && out->unsafe_causes != e->unsafe_causes) {
    fprintf(stderr, "FAIL %s step %d causes got %u want %u\n",
            id, step_i, out->unsafe_causes, e->unsafe_causes);
    return 0;
  }
  return 1;
}

static int parse_step_and_run(Cursor *c, void *storage, const char *id, int step_i,
                              unsigned *seen)
{
  char action[16] = {0};
  double latch_t = 0.0;
  int has_in = 0;
  int has_latch_t = 0;
  guara_inputs in;
  Expect expect;
  memset(&in, 0, sizeof in);
  memset(&expect, 0, sizeof expect);
  if (!take(c, '{')) {
    return 0;
  }
  if (take(c, '}')) {
    fprintf(stderr, "FAIL %s step %d: empty step\n", id, step_i);
    return 0;
  }
  for (;;) {
    char key[32];
    if (!parse_string(c, key, sizeof key) || !take(c, ':')) {
      return 0;
    }
    int ok = 1;
    if (strcmp(key, "action") == 0) {
      ok = parse_string(c, action, sizeof action);
    } else if (strcmp(key, "t_s") == 0) {
      ok = parse_number(c, &latch_t);
      has_latch_t = 1;
    } else if (strcmp(key, "in") == 0) {
      ok = parse_inputs(c, &in);
      has_in = 1;
    } else if (strcmp(key, "expect") == 0) {
      ok = parse_expect(c, &expect);
    } else {
      ok = skip_value(c);
    }
    if (!ok) {
      fprintf(stderr, "FAIL %s step %d: bad field '%s'\n", id, step_i, key);
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

  guara_output out;
  memset(&out, 0, sizeof out);
  if (strcmp(action, "latch") == 0) {
    if (!has_latch_t) {
      fprintf(stderr, "FAIL %s step %d: latch needs t_s\n", id, step_i);
      return 0;
    }
    if (guara_core_latch_on_actuation_failure(storage, latch_t, &out) != GUARA_OK) {
      fprintf(stderr, "FAIL %s step %d: latch rejected\n", id, step_i);
      return 0;
    }
  } else {
    if (!has_in) {
      fprintf(stderr, "FAIL %s step %d: missing in\n", id, step_i);
      return 0;
    }
    if (guara_core_step(storage, &in, &out) != GUARA_OK) {
      fprintf(stderr, "FAIL %s step %d: step rejected\n", id, step_i);
      return 0;
    }
  }
  if (!check_expect(id, step_i, &expect, &out)) {
    return 0;
  }
  if (out.transition.id != 0) {
    *seen |= 1u << out.transition.id;
  }
  return 1;
}

static int parse_steps(Cursor *c, void *storage, const char *id, unsigned *seen)
{
  if (!take(c, '[')) {
    return 0;
  }
  int step_i = 0;
  if (take(c, ']')) {
    fprintf(stderr, "FAIL %s: no steps\n", id);
    return 0;
  }
  for (;;) {
    if (!parse_step_and_run(c, storage, id, step_i, seen)) {
      return 0;
    }
    ++step_i;
    if (take(c, ',')) {
      continue;
    }
    return take(c, ']');
  }
}

static int run_vector(Cursor *c, unsigned *seen)
{
  char id[64] = "unknown";
  guara_params params;
  guara_params_default(&params);
  int has_steps = 0;
  if (!take(c, '{')) {
    return 0;
  }
  /* First pass is a single object: parse keys as they appear, run steps last-or-when seen. */
  Cursor steps_at;
  memset(&steps_at, 0, sizeof steps_at);
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
      if (!parse_params_obj(c, &params)) {
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
  unsigned char buf[1024];
  if (guara_core_init(buf, sizeof buf, &params) != GUARA_OK) {
    fprintf(stderr, "FAIL %s: init rejected\n", id);
    return 0;
  }
  Cursor sc = steps_at;
  return parse_steps(&sc, buf, id, seen);
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
  const char *path = GUARA_VECTORS_DIR "/spec_s3.json";
  size_t n = 0;
  char *text = read_file(path, &n);
  CHECK(text != NULL);
  Cursor c = {text, n, 0};
  CHECK(take(&c, '['));
  unsigned seen = 0;
  int nvec = 0;
  CHECK(!take(&c, ']'));
  for (;;) {
    if (!run_vector(&c, &seen)) {
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
  const unsigned need = 0x3FEu; /* transition ids 1..9 */
  if ((seen & need) != need) {
    fprintf(stderr, "FAIL missing SPEC transitions seen=0x%x need=0x%x\n", seen, need);
    return 1;
  }
  printf("PASS conformance_spec_s3 vectors=%d transitions=1..9\n", nvec);
  return 0;
}
