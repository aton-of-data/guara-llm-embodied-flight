// SPDX-License-Identifier: Apache-2.0
//
// Traffic bookkeeping of the DAA node (review 2026-09-11 H-7). Apache-2.0 wrapper code: it holds no
// DAIDALUS symbol, so it is unit-testable without the NOSA library (ADR 0003).
//
// Rules
//   * Each intruder keeps the observation time of its own report; the evaluator adds it to DAIDALUS
//     at that time instead of pretending every report was taken at the ownship instant (at 50 m/s a
//     5 s error is ~250 m).
//   * A report older than the configured maximum age is not evaluated.
//   * A full table evicts the oldest entry instead of dropping the new intruder: in a busy sector
//     the aircraft that appears last is often the one that matters.
//   * The ownship gate: a status message is only valid while the ownship sample it is derived from
//     is fresh, so a stopped local-position stream invalidates the DAA channel instead of being
//     republished every 200 ms as if it were current.
#ifndef GUARA_DAIDALUS_TRAFFIC_TABLE_HPP_
#define GUARA_DAIDALUS_TRAFFIC_TABLE_HPP_

#include <cmath>
#include <cstddef>

#include "guara_daidalus/evaluate.hpp"

namespace guara_daidalus
{

class TrafficTable
{
public:
  // Inserts or updates the entry of `sample.icao` observed at `t_s`. Returns true if the sample is
  // held by the table (evicting the oldest entry if needed).
  bool upsert(const TrafficSi & sample, double t_s) noexcept
  {
    TrafficSi stored = sample;
    stored.time_s = t_s;
    for (std::size_t i = 0; i < n_; ++i) {
      if (entries_[i].icao == sample.icao) {
        entries_[i] = stored;
        return true;
      }
    }
    if (n_ < kMaxTraffic) {
      entries_[n_++] = stored;
      return true;
    }
    std::size_t oldest = 0;
    for (std::size_t i = 1; i < n_; ++i) {
      if (entries_[i].time_s < entries_[oldest].time_s) {
        oldest = i;
      }
    }
    if (entries_[oldest].time_s >= t_s) {
      return false;  // every held report is at least as recent as this one
    }
    entries_[oldest] = stored;
    return true;
  }

  // Copies the entries no older than `max_age_s` into `out` (capacity kMaxTraffic) and returns how
  // many were copied. Insertion order is preserved.
  std::size_t collect(double now_s, double max_age_s, TrafficSi * out) const noexcept
  {
    std::size_t m = 0;
    for (std::size_t i = 0; i < n_; ++i) {
      if (now_s - entries_[i].time_s > max_age_s) {
        continue;
      }
      out[m++] = entries_[i];
    }
    return m;
  }

  std::size_t size() const noexcept {return n_;}

private:
  TrafficSi entries_[kMaxTraffic]{};
  std::size_t n_{0};
};

// True if an ownship sample received at `t_recv_s` is still usable at `t_now_s`.
inline bool ownshipFresh(double t_recv_s, double t_now_s, double max_age_s) noexcept
{
  return std::isfinite(t_recv_s) && t_recv_s >= 0.0 && std::isfinite(t_now_s) &&
         t_now_s - t_recv_s <= max_age_s;
}

}  // namespace guara_daidalus

#endif  // GUARA_DAIDALUS_TRAFFIC_TABLE_HPP_
