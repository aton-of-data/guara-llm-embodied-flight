// SPDX-License-Identifier: Apache-2.0
//
// C ABI for GatewayLogic (ADR 0010). Caller-supplied storage; no heap, no I/O.
#include "guara/guara.h"

#include <array>
#include <cstdint>
#include <new>

#include "guara_rta/gateway_logic.hpp"

namespace
{

constexpr std::uint32_t kGwMagic = 0x47574757u;  // 'GWGW'

class CannedGuard final : public guara_rta::SetpointGuard
{
public:
  bool ok{true};
  bool admissible(const std::array<float, 3> &, double) const noexcept override {return ok;}
};

struct GwStorage
{
  std::uint32_t magic;
  CannedGuard guard;
  alignas(guara_rta::GatewayLogic) unsigned char gw[sizeof(guara_rta::GatewayLogic)];
};

GwStorage * as_gw(void * p) noexcept
{
  return static_cast<GwStorage *>(p);
}

// True if p meets the alignment guara_gateway_storage_align() publishes.
bool aligned_for_gw(const void * p) noexcept
{
  return (reinterpret_cast<std::uintptr_t>(p) % alignof(GwStorage)) == 0U;
}

guara_rta::GatewayLogic * gw_of(GwStorage * s) noexcept
{
  return reinterpret_cast<guara_rta::GatewayLogic *>(s->gw);
}

int require_gw(void * storage) noexcept
{
  if (storage == nullptr) {
    return GUARA_ERR_NULL;
  }
  if (as_gw(storage)->magic != kGwMagic) {
    return GUARA_ERR_UNINIT;
  }
  return GUARA_OK;
}

guara_rta::GatewayLimits from_c(const guara_gateway_limits & in) noexcept
{
  guara_rta::GatewayLimits o;
  o.max_speed_h_m_s = in.max_speed_h_m_s;
  o.max_climb_rate_m_s = in.max_climb_rate_m_s;
  o.max_descent_rate_m_s = in.max_descent_rate_m_s;
  o.max_yaw_rate_rad_s = in.max_yaw_rate_rad_s;
  o.future_stamp_tolerance_s = in.future_stamp_tolerance_s;
  return o;
}

}  // namespace

extern "C" {

size_t guara_gateway_storage_size(void)
{
  return sizeof(GwStorage);
}

size_t guara_gateway_storage_align(void)
{
  return alignof(GwStorage);
}

void guara_gateway_limits_default(guara_gateway_limits * limits)
{
  if (limits == nullptr) {
    return;
  }
  const guara_rta::GatewayLimits d{};
  limits->max_speed_h_m_s = d.max_speed_h_m_s;
  limits->max_climb_rate_m_s = d.max_climb_rate_m_s;
  limits->max_descent_rate_m_s = d.max_descent_rate_m_s;
  limits->max_yaw_rate_rad_s = d.max_yaw_rate_rad_s;
  limits->future_stamp_tolerance_s = d.future_stamp_tolerance_s;
  limits->cf_timeout_s = 0.5;
}

const char * guara_gateway_limits_error(const guara_gateway_limits * limits)
{
  if (limits == nullptr) {
    return "limits is null";
  }
  if (!(limits->cf_timeout_s > 0.0)) {
    return "cf_timeout_s must be > 0";
  }
  if (!(limits->max_speed_h_m_s > 0.0)) {
    return "max_speed_h_m_s must be > 0";
  }
  if (!(limits->max_climb_rate_m_s > 0.0)) {
    return "max_climb_rate_m_s must be > 0";
  }
  if (!(limits->max_descent_rate_m_s > 0.0)) {
    return "max_descent_rate_m_s must be > 0";
  }
  if (!(limits->max_yaw_rate_rad_s > 0.0)) {
    return "max_yaw_rate_rad_s must be > 0";
  }
  if (!(limits->future_stamp_tolerance_s >= 0.0)) {
    return "future_stamp_tolerance_s must be >= 0";
  }
  return nullptr;
}

int guara_gateway_init(void * storage, size_t n, const guara_gateway_limits * limits)
{
  if (storage == nullptr || limits == nullptr) {
    return GUARA_ERR_NULL;
  }
  if (n < sizeof(GwStorage) || !aligned_for_gw(storage)) {
    return GUARA_ERR_STORAGE;
  }
  if (guara_gateway_limits_error(limits) != nullptr) {
    return GUARA_ERR_PARAMS;
  }
  GwStorage * s = as_gw(storage);
  s->magic = 0;
  new (static_cast<void *>(&s->guard)) CannedGuard();
  new (static_cast<void *>(s->gw)) guara_rta::GatewayLogic(limits->cf_timeout_s, from_c(*limits));
  s->magic = kGwMagic;
  return GUARA_OK;
}

int guara_gateway_set_guard(void * storage, uint8_t mode)
{
  const int rc = require_gw(storage);
  if (rc != GUARA_OK) {
    return rc;
  }
  GwStorage * s = as_gw(storage);
  if (mode == GUARA_GATEWAY_GUARD_OFF) {
    gw_of(s)->setGuard(nullptr);
    return GUARA_OK;
  }
  if (mode == GUARA_GATEWAY_GUARD_ALLOW) {
    s->guard.ok = true;
    gw_of(s)->setGuard(&s->guard);
    return GUARA_OK;
  }
  if (mode == GUARA_GATEWAY_GUARD_DENY) {
    s->guard.ok = false;
    gw_of(s)->setGuard(&s->guard);
    return GUARA_OK;
  }
  return GUARA_ERR_PARAMS;
}

int guara_gateway_on_core_state(void * storage, uint8_t state, double t_s)
{
  const int rc = require_gw(storage);
  if (rc != GUARA_OK) {
    return rc;
  }
  if (state > GUARA_STATE_MAX) {
    return GUARA_ERR_PARAMS;
  }
  gw_of(as_gw(storage))->onCoreState(static_cast<guara_rta::State>(state), t_s);
  return GUARA_OK;
}

int guara_gateway_on_cf_setpoint(void * storage, double t_recv_s, double stamp_s,
  const float velocity_ned_m_s[3], float yaw_ned_rad)
{
  const int rc = require_gw(storage);
  if (rc != GUARA_OK) {
    return rc;
  }
  if (velocity_ned_m_s == nullptr) {
    return GUARA_ERR_NULL;
  }
  const std::array<float, 3> v{velocity_ned_m_s[0], velocity_ned_m_s[1], velocity_ned_m_s[2]};
  gw_of(as_gw(storage))->onCfSetpoint(t_recv_s, stamp_s, v, yaw_ned_rad);
  return GUARA_OK;
}

int guara_gateway_compute(void * storage, double t_s, guara_gateway_output * out)
{
  const int rc = require_gw(storage);
  if (rc != GUARA_OK) {
    return rc;
  }
  if (out == nullptr) {
    return GUARA_ERR_NULL;
  }
  guara_rta::GatewayLogic * g = gw_of(as_gw(storage));
  const guara_rta::GatewaySetpoint sp = g->compute(t_s);
  out->velocity_ned_m_s[0] = sp.velocity_ned_m_s[0];
  out->velocity_ned_m_s[1] = sp.velocity_ned_m_s[1];
  out->velocity_ned_m_s[2] = sp.velocity_ned_m_s[2];
  out->yaw_ned_rad = sp.yaw_ned_rad;
  out->forwarding_cf = sp.forwarding_cf ? 1 : 0;
  out->rejected_non_finite = g->rejectedNonFinite();
  out->rejected_implausible_stamp = g->rejectedImplausibleStamp();
  out->rejected_yaw = g->rejectedYaw();
  out->rejected_by_guard = g->rejectedByGuard();
  out->clamped = g->clamped();
  return GUARA_OK;
}

const char * guara_gateway_guard_name(uint8_t mode)
{
  switch (mode) {
    case GUARA_GATEWAY_GUARD_OFF: return "OFF";
    case GUARA_GATEWAY_GUARD_ALLOW: return "ALLOW";
    case GUARA_GATEWAY_GUARD_DENY: return "DENY";
    default: return "UNKNOWN";
  }
}

}  // extern "C"
