// SPDX-License-Identifier: Apache-2.0
//
// C ABI for MonitorTable (SPEC §3.1, ADR 0002). Caller-supplied storage.
#include "guara/guara.h"

#include <new>

#include "guara_rta/monitor_table.hpp"

namespace
{

constexpr std::uint32_t kMonMagic = 0x4D4F4E54u;  // 'MONT'

struct MonStorage
{
  std::uint32_t magic;
  alignas(guara_rta::MonitorTable) unsigned char table[sizeof(guara_rta::MonitorTable)];
};

MonStorage * as_mon(void * p) noexcept
{
  return static_cast<MonStorage *>(p);
}

guara_rta::MonitorTable * table_of(MonStorage * s) noexcept
{
  return reinterpret_cast<guara_rta::MonitorTable *>(s->table);
}

int require_mon(void * storage) noexcept
{
  if (storage == nullptr) {
    return GUARA_ERR_NULL;
  }
  if (as_mon(storage)->magic != kMonMagic) {
    return GUARA_ERR_UNINIT;
  }
  return GUARA_OK;
}

void copy_id(char * dst, const char * src) noexcept
{
  dst[0] = '\0';
  if (src == nullptr) {
    return;
  }
  std::size_t i = 0;
  for (; i < GUARA_MONITOR_ID_MAX && src[i] != '\0'; ++i) {
    dst[i] = src[i];
  }
  dst[i] = '\0';
}

}  // namespace

extern "C" {

size_t guara_monitor_storage_size(void)
{
  return sizeof(MonStorage);
}

size_t guara_monitor_storage_align(void)
{
  return alignof(MonStorage);
}

const char * guara_monitor_max_age_error(double max_age_s)
{
  if (!(max_age_s > 0.0)) {
    return "max_age_s must be > 0";
  }
  return nullptr;
}

int guara_monitor_init(void * storage, size_t n, double max_age_s)
{
  if (storage == nullptr) {
    return GUARA_ERR_NULL;
  }
  if (n < sizeof(MonStorage)) {
    return GUARA_ERR_STORAGE;
  }
  if (guara_monitor_max_age_error(max_age_s) != nullptr) {
    return GUARA_ERR_PARAMS;
  }
  MonStorage * s = as_mon(storage);
  s->magic = 0;
  new (static_cast<void *>(s->table)) guara_rta::MonitorTable();
  table_of(s)->configure(max_age_s);
  s->magic = kMonMagic;
  return GUARA_OK;
}

int guara_monitor_expect(void * storage, const char * id)
{
  const int rc = require_mon(storage);
  if (rc != GUARA_OK) {
    return rc;
  }
  if (id == nullptr) {
    return GUARA_ERR_NULL;
  }
  return table_of(as_mon(storage))->expect(id) ? GUARA_OK : GUARA_ERR_PARAMS;
}

int guara_monitor_observe(void * storage, const guara_monitor_sample * sample, double t_recv_s)
{
  const int rc = require_mon(storage);
  if (rc != GUARA_OK) {
    return rc;
  }
  if (sample == nullptr) {
    return GUARA_ERR_NULL;
  }
  guara_rta::MonitorVerdictSample s;
  s.id = sample->id;
  s.monitor_class = sample->monitor_class;
  s.action = sample->action;
  s.violated = sample->violated != 0;
  s.inputs_complete = sample->inputs_complete != 0;
  const guara_rta::MonitorAccept acc = table_of(as_mon(storage))->observe(s, t_recv_s);
  return static_cast<int>(acc);
}

int guara_monitor_evaluate(void * storage, double t_s, guara_monitor_eval * out)
{
  const int rc = require_mon(storage);
  if (rc != GUARA_OK) {
    return rc;
  }
  if (out == nullptr) {
    return GUARA_ERR_NULL;
  }
  const guara_rta::MonitorEvaluation e = table_of(as_mon(storage))->evaluate(t_s);
  out->violation = e.violation ? 1 : 0;
  out->action = static_cast<std::uint8_t>(e.action);
  out->invalid = e.invalid ? 1 : 0;
  copy_id(out->first_violating_id, e.first_violating_id);
  copy_id(out->first_invalid_id, e.first_invalid_id);
  return GUARA_OK;
}

const char * guara_monitor_class_name(uint8_t monitor_class)
{
  switch (monitor_class) {
    case GUARA_MONITOR_CLASS_LOG: return "LOG";
    case GUARA_MONITOR_CLASS_SWITCH: return "SWITCH";
    default: return "UNKNOWN";
  }
}

const char * guara_monitor_action_name(uint8_t action)
{
  switch (action) {
    case GUARA_MONITOR_ACTION_HOLD: return "HOLD";
    case GUARA_MONITOR_ACTION_RTL: return "RTL";
    case GUARA_MONITOR_ACTION_LAND: return "LAND";
    default: return "UNKNOWN";
  }
}

const char * guara_monitor_accept_name(int code)
{
  switch (code) {
    case GUARA_MONITOR_ACCEPTED: return "ACCEPTED";
    case GUARA_MONITOR_INVALID_FIELD: return "INVALID_FIELD";
    case GUARA_MONITOR_TABLE_FULL: return "TABLE_FULL";
    default: return "UNKNOWN";
  }
}

}  // extern "C"
