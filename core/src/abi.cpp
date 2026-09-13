// SPDX-License-Identifier: Apache-2.0
//
// C ABI implementation: placement-new of DecisionCore into caller storage.
// After init, this translation unit performs no heap allocation and no I/O.
#include "guara/guara.h"

#include <new>

#include "guara_rta/decision_core.hpp"

namespace
{

constexpr std::uint32_t kMagic = 0x47554152u;  // 'GUAR'

struct Storage
{
  std::uint32_t magic;
  alignas(guara_rta::DecisionCore) unsigned char core[sizeof(guara_rta::DecisionCore)];
};

Storage * as_storage(void * p) noexcept
{
  return static_cast<Storage *>(p);
}

guara_rta::DecisionCore * core_of(Storage * s) noexcept
{
  return reinterpret_cast<guara_rta::DecisionCore *>(s->core);
}

guara_rta::Parameters from_c(const guara_params & p) noexcept
{
  guara_rta::Parameters o;
  o.tau_daa_s = p.tau_daa_s;
  o.tau_gf_s = p.tau_gf_s;
  o.h_daa_s = p.h_daa_s;
  o.h_gf_s = p.h_gf_s;
  o.dwell_s = p.dwell_s;
  o.n_max = p.n_max;
  o.window_s = p.window_s;
  o.return_enabled = p.return_enabled != 0;
  o.escalation_enabled = p.escalation_enabled != 0;
  o.escalation_s = p.escalation_s;
  return o;
}

guara_rta::Inputs from_c(const guara_inputs & in) noexcept
{
  guara_rta::Inputs o;
  o.t_s = in.t_s;
  o.in_charge = in.in_charge != 0;
  o.owned_mode_active = in.owned_mode_active != 0;
  o.t_daa_s = in.t_daa_s;
  o.t_gf_s = in.t_gf_s;
  o.monitor_violation = in.monitor_violation != 0;
  o.monitor_action = static_cast<guara_rta::Recovery>(in.monitor_action);
  o.input_invalid = in.input_invalid != 0;
  o.cf_intent_unsafe = in.cf_intent_unsafe != 0;
  return o;
}

void to_c(const guara_rta::Output & in, guara_output * out) noexcept
{
  out->state = static_cast<std::uint8_t>(in.state);
  out->recovery = static_cast<std::uint8_t>(in.recovery);
  out->command = static_cast<std::uint8_t>(in.command);
  out->transition.id = in.transition.id;
  out->transition.from = static_cast<std::uint8_t>(in.transition.from);
  out->transition.to = static_cast<std::uint8_t>(in.transition.to);
  out->transition.rf_from = static_cast<std::uint8_t>(in.transition.rf_from);
  out->transition.rf_to = static_cast<std::uint8_t>(in.transition.rf_to);
  out->transition.cause = in.transition.cause;
  out->unsafe_causes = in.unsafe_causes;
  out->clear = in.clear ? 1 : 0;
  out->clear_duration_s = in.clear_duration_s;
  out->switches_in_window = in.switches_in_window;
}

int require_init(void * storage) noexcept
{
  if (storage == nullptr) {
    return GUARA_ERR_NULL;
  }
  if (as_storage(storage)->magic != kMagic) {
    return GUARA_ERR_UNINIT;
  }
  return GUARA_OK;
}

}  // namespace

extern "C" {

size_t guara_core_storage_size(void)
{
  return sizeof(Storage);
}

size_t guara_core_storage_align(void)
{
  return alignof(Storage);
}

const char * guara_core_version(void)
{
  return GUARA_CORE_VERSION;
}

const char * guara_abi_version(void)
{
  return GUARA_ABI_VERSION;
}

void guara_params_default(guara_params * params)
{
  if (params == nullptr) {
    return;
  }
  const guara_rta::Parameters d{};
  params->tau_daa_s = d.tau_daa_s;
  params->tau_gf_s = d.tau_gf_s;
  params->h_daa_s = d.h_daa_s;
  params->h_gf_s = d.h_gf_s;
  params->dwell_s = d.dwell_s;
  params->n_max = d.n_max;
  params->window_s = d.window_s;
  params->return_enabled = d.return_enabled ? 1 : 0;
  params->escalation_enabled = d.escalation_enabled ? 1 : 0;
  params->escalation_s = d.escalation_s;
}

int guara_core_init(void * storage, size_t n, const guara_params * params)
{
  if (storage == nullptr || params == nullptr) {
    return GUARA_ERR_NULL;
  }
  if (n < sizeof(Storage)) {
    return GUARA_ERR_STORAGE;
  }
  const guara_rta::Parameters p = from_c(*params);
  if (guara_rta::validate(p) != nullptr) {
    return GUARA_ERR_PARAMS;
  }
  Storage * s = as_storage(storage);
  s->magic = 0;
  new (static_cast<void *>(s->core)) guara_rta::DecisionCore(p);
  if (!core_of(s)->valid()) {
    return GUARA_ERR_PARAMS;
  }
  s->magic = kMagic;
  return GUARA_OK;
}

int guara_core_step(void * storage, const guara_inputs * in, guara_output * out)
{
  const int rc = require_init(storage);
  if (rc != GUARA_OK) {
    return rc;
  }
  if (in == nullptr || out == nullptr) {
    return GUARA_ERR_NULL;
  }
  const guara_rta::Output result = core_of(as_storage(storage))->step(from_c(*in));
  to_c(result, out);
  return GUARA_OK;
}

int guara_core_latch_on_actuation_failure(void * storage, double t_s, guara_output * out)
{
  const int rc = require_init(storage);
  if (rc != GUARA_OK) {
    return rc;
  }
  if (out == nullptr) {
    return GUARA_ERR_NULL;
  }
  const guara_rta::Output result =
    core_of(as_storage(storage))->latchOnActuationFailure(t_s);
  to_c(result, out);
  return GUARA_OK;
}

}  // extern "C"
