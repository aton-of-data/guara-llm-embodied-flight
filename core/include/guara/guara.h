/* SPDX-License-Identifier: Apache-2.0 */
/*
 * C ABI of the Guará switching kernel (ADR 0014 / M18).
 *
 * The kernel allocates nothing and owns no clock. The caller supplies storage
 * of at least guara_core_storage_size() bytes, aligned to
 * guara_core_storage_align(). After guara_core_init returns GUARA_OK, step
 * and latch perform no libc I/O and no heap traffic.
 *
 * ABI v0 is provisional until three independent ports pass the conformance
 * kit (ADR 0014 decision 3). Passing this interface demonstrates behavioural
 * access to the reference core; it does not make a containing system safe
 * (ADR 0014 decision 4).
 */
#ifndef GUARA_GUARA_H
#define GUARA_GUARA_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32)
#define GUARA_API
#else
#define GUARA_API __attribute__((visibility("default")))
#endif

#define GUARA_ABI_VERSION "0.1.0-provisional"
#define GUARA_CORE_VERSION "0.17.0-dev"

#define GUARA_OK 0
#define GUARA_ERR_NULL 1
#define GUARA_ERR_STORAGE 2
#define GUARA_ERR_PARAMS 3
#define GUARA_ERR_UNINIT 4

typedef struct guara_params {
  double tau_daa_s;
  double tau_gf_s;
  double h_daa_s;
  double h_gf_s;
  double dwell_s;
  uint16_t n_max;
  double window_s;
  uint8_t return_enabled;
  uint8_t escalation_enabled;
  double escalation_s;
} guara_params;

typedef struct guara_inputs {
  double t_s;
  uint8_t in_charge;
  uint8_t owned_mode_active;
  double t_daa_s;
  double t_gf_s;
  uint8_t monitor_violation;
  uint8_t monitor_action;
  uint8_t input_invalid;
  uint8_t cf_intent_unsafe;
} guara_inputs;

typedef struct guara_transition {
  uint8_t id;
  uint8_t from;
  uint8_t to;
  uint8_t rf_from;
  uint8_t rf_to;
  uint32_t cause;
} guara_transition;

typedef struct guara_output {
  uint8_t state;
  uint8_t recovery;
  uint8_t command;
  guara_transition transition;
  uint32_t unsafe_causes;
  uint8_t clear;
  double clear_duration_s;
  uint16_t switches_in_window;
} guara_output;

GUARA_API size_t guara_core_storage_size(void);
GUARA_API size_t guara_core_storage_align(void);
GUARA_API const char * guara_core_version(void);
GUARA_API const char * guara_abi_version(void);
GUARA_API void guara_params_default(guara_params * params);

GUARA_API int guara_core_init(void * storage, size_t n, const guara_params * params);
GUARA_API int guara_core_step(void * storage, const guara_inputs * in, guara_output * out);
GUARA_API int guara_core_latch_on_actuation_failure(void * storage, double t_s, guara_output * out);

#ifdef __cplusplus
}
#endif

#endif /* GUARA_GUARA_H */
