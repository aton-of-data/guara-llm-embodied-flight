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
 * kit (ADR 0014 decision 3). Passing the published vectors through this
 * interface demonstrates behavioural equivalence to the reference core; it
 * says nothing about the safety of the system that contains it
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
#  if defined(GUARA_BUILD_SHARED)
#    define GUARA_API __declspec(dllexport)
#  else
#    define GUARA_API
#  endif
#else
#define GUARA_API __attribute__((visibility("default")))
#endif

#define GUARA_ABI_VERSION "0.17.0-provisional"
#define GUARA_CORE_VERSION "0.17.0-dev"

#define GUARA_OK 0
#define GUARA_ERR_NULL 1
#define GUARA_ERR_STORAGE 2
#define GUARA_ERR_PARAMS 3
#define GUARA_ERR_UNINIT 4

#define GUARA_PARAM_DIGEST_LEN 8

/* Switching states, in the encoding of guara_output.state and of the `state`
 * argument of guara_gateway_on_core_state (SPEC 3). */
#define GUARA_STATE_INACTIVE 0
#define GUARA_STATE_CF 1
#define GUARA_STATE_RF 2
#define GUARA_STATE_LATCHED 3
#define GUARA_STATE_MAX GUARA_STATE_LATCHED

/* Recovery functions, ranked HOLD < RTL < LAND (SPEC 3.5, ADR 0005 item 4).
 * This is the encoding of guara_output.recovery and of guara_inputs.monitor_action.
 * It is NOT the GUARA_MONITOR_ACTION_* encoding used on the monitor wire
 * contract, which starts at HOLD = 0; a host that aggregates verdicts itself
 * must shift by one. guara_core_step rejects a value above GUARA_RECOVERY_LAND. */
#define GUARA_RECOVERY_NONE 0
#define GUARA_RECOVERY_HOLD 1
#define GUARA_RECOVERY_RTL 2
#define GUARA_RECOVERY_LAND 3
#define GUARA_RECOVERY_MAX GUARA_RECOVERY_LAND

/* Mode requests emitted towards the actuator. */
#define GUARA_COMMAND_NONE 0
#define GUARA_COMMAND_HOLD 1
#define GUARA_COMMAND_RTL 2
#define GUARA_COMMAND_LAND 3
#define GUARA_COMMAND_OWNED_MODE 4

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
GUARA_API const char * guara_state_name(uint8_t state);
GUARA_API const char * guara_recovery_name(uint8_t recovery);
GUARA_API const char * guara_command_name(uint8_t command);
GUARA_API const char * guara_transition_name(uint8_t id);
GUARA_API const char * guara_cause_name(uint32_t bits);
GUARA_API const char * guara_err_name(int code);
GUARA_API void guara_params_default(guara_params * params);
GUARA_API const char * guara_params_error(const guara_params * params);
GUARA_API void guara_params_digest(const guara_params * params, uint8_t out[GUARA_PARAM_DIGEST_LEN]);

GUARA_API int guara_core_init(void * storage, size_t n, const guara_params * params);
GUARA_API int guara_core_step(void * storage, const guara_inputs * in, guara_output * out);
GUARA_API int guara_core_latch_on_actuation_failure(void * storage, double t_s, guara_output * out);
GUARA_API int guara_core_param_digest(void * storage, uint8_t out[GUARA_PARAM_DIGEST_LEN]);

#define GUARA_GATEWAY_GUARD_OFF 0
#define GUARA_GATEWAY_GUARD_ALLOW 1
#define GUARA_GATEWAY_GUARD_DENY 2

typedef struct guara_gateway_limits {
  double max_speed_h_m_s;
  double max_climb_rate_m_s;
  double max_descent_rate_m_s;
  double max_yaw_rate_rad_s;
  double future_stamp_tolerance_s;
  double cf_timeout_s;
} guara_gateway_limits;

typedef struct guara_gateway_output {
  float velocity_ned_m_s[3];
  float yaw_ned_rad;
  uint8_t forwarding_cf;
  uint32_t rejected_non_finite;
  uint32_t rejected_implausible_stamp;
  uint32_t rejected_yaw;
  uint32_t rejected_by_guard;
  uint32_t clamped;
} guara_gateway_output;

GUARA_API size_t guara_gateway_storage_size(void);
GUARA_API size_t guara_gateway_storage_align(void);
GUARA_API void guara_gateway_limits_default(guara_gateway_limits * limits);
GUARA_API const char * guara_gateway_limits_error(const guara_gateway_limits * limits);
GUARA_API int guara_gateway_init(void * storage, size_t n, const guara_gateway_limits * limits);
GUARA_API int guara_gateway_set_guard(void * storage, uint8_t mode);
GUARA_API const char * guara_gateway_guard_name(uint8_t mode);
GUARA_API int guara_gateway_on_core_state(void * storage, uint8_t state, double t_s);
GUARA_API int guara_gateway_on_cf_setpoint(void * storage, double t_recv_s, double stamp_s,
  const float velocity_ned_m_s[3], float yaw_ned_rad);
GUARA_API int guara_gateway_compute(void * storage, double t_s, guara_gateway_output * out);

#define GUARA_MONITOR_ID_MAX 47

/* guara_monitor_observe returns one of these, NOT a GUARA_ERR_* code, whenever
 * the call reached the table; GUARA_ERR_NULL and GUARA_ERR_UNINIT are returned
 * only when it did not. Name them with guara_monitor_accept_name, never with
 * guara_err_name. */
#define GUARA_MONITOR_ACCEPTED 0
#define GUARA_MONITOR_INVALID_FIELD 1
#define GUARA_MONITOR_TABLE_FULL 2
#define GUARA_MONITOR_CLASS_LOG 0
#define GUARA_MONITOR_CLASS_SWITCH 1
#define GUARA_MONITOR_ACTION_HOLD 0
#define GUARA_MONITOR_ACTION_RTL 1
#define GUARA_MONITOR_ACTION_LAND 2

typedef struct guara_monitor_sample {
  const char * id;
  uint8_t monitor_class;
  uint8_t action;
  uint8_t violated;
  uint8_t inputs_complete;
} guara_monitor_sample;

typedef struct guara_monitor_eval {
  uint8_t violation;
  uint8_t action;
  uint8_t invalid;
  char first_violating_id[GUARA_MONITOR_ID_MAX + 1];
  char first_invalid_id[GUARA_MONITOR_ID_MAX + 1];
} guara_monitor_eval;

GUARA_API size_t guara_monitor_storage_size(void);
GUARA_API size_t guara_monitor_storage_align(void);
GUARA_API int guara_monitor_init(void * storage, size_t n, double max_age_s);
GUARA_API const char * guara_monitor_max_age_error(double max_age_s);
GUARA_API int guara_monitor_expect(void * storage, const char * id);
GUARA_API int guara_monitor_observe(void * storage, const guara_monitor_sample * sample,
  double t_recv_s);
GUARA_API int guara_monitor_evaluate(void * storage, double t_s, guara_monitor_eval * out);
GUARA_API const char * guara_monitor_class_name(uint8_t monitor_class);
GUARA_API const char * guara_monitor_action_name(uint8_t action);
GUARA_API const char * guara_monitor_accept_name(int code);

#define GUARA_GF_MAX_VERTICES 64
#define GUARA_GF_POLY_NONE 0
#define GUARA_GF_POLY_TOO_FEW 1
#define GUARA_GF_POLY_TOO_MANY 2
#define GUARA_GF_POLY_NON_FINITE 3
#define GUARA_GF_POLY_DEGENERATE 4
#define GUARA_GF_POLY_SELF_INTERSECT 5
#define GUARA_GF_POLY_ZERO_AREA 6

typedef struct guara_gf_params {
  double a_brake_h_m_s2;
  double a_brake_v_m_s2;
  double k_sigma;
  double v_min_m_s;
  double horizon_s;
} guara_gf_params;

typedef struct guara_gf_state {
  double north_m;
  double east_m;
  double altitude_m;
  double vn_m_s;
  double ve_m_s;
  double climb_rate_m_s;
  double eph_m;
  double epv_m;
} guara_gf_state;

typedef struct guara_gf_prediction {
  double t_gf_s;
  double t_horizontal_s;
  double t_vertical_s;
  uint8_t inside;
  double exit_distance_m;
} guara_gf_prediction;

GUARA_API void guara_gf_params_default(guara_gf_params * p);
GUARA_API const char * guara_gf_params_error(const guara_gf_params * p);
GUARA_API int guara_gf_predict(const double * vertices_ne, size_t n_vertices, double alt_min_m,
  double alt_max_m, const guara_gf_params * params, const guara_gf_state * state,
  guara_gf_prediction * out);
GUARA_API int guara_gf_project_to_local(double lat_deg, double lon_deg, double ref_lat_deg,
  double ref_lon_deg, double * north_m, double * east_m);
GUARA_API int guara_gf_polygon_error(const double * vertices_ne, size_t n_vertices);
GUARA_API const char * guara_gf_polygon_error_name(int code);

#ifdef __cplusplus
}
#endif

#endif /* GUARA_GUARA_H */
