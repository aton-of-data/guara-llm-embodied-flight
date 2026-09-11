// SPDX-License-Identifier: Apache-2.0
//
// T_daa evaluation (SPEC §3.1): min over intruders of Daidalus::timeToCorrectiveVolume
// after set_DO_365B [G 5.4, 5.7, A.14]. Wrapper only; DAIDALUS sources are unmodified.
#ifndef GUARA_DAIDALUS_EVALUATE_HPP_
#define GUARA_DAIDALUS_EVALUATE_HPP_

#include <cstddef>
#include <cstdint>
#include <limits>

namespace guara_daidalus
{

inline constexpr std::size_t kMaxTraffic = 16;

struct TrafficSi
{
  std::uint32_t icao{0};
  // Observation time of this report on the same clock as OwnshipSi::time_s. DAIDALUS projects each
  // state from its own time, so a report is never re-dated to the ownship instant (review H-7).
  double time_s{0.0};
  double lat_deg{0.0};
  double lon_deg{0.0};
  double alt_m_amsl{0.0};
  double track_rad{0.0};  // 0 = north, clockwise
  double gs_mps{0.0};
  double vs_mps_up{0.0};
};

struct OwnshipSi
{
  double time_s{0.0};
  double lat_deg{0.0};
  double lon_deg{0.0};
  double alt_m_amsl{0.0};
  double track_rad{0.0};
  double gs_mps{0.0};
  double vs_mps_up{0.0};
  bool valid{false};
};

struct DaaEvaluation
{
  double t_daa_s{std::numeric_limits<double>::infinity()};
  std::int32_t alert_level{0};
  std::uint16_t num_intruders{0};
  std::uint32_t critical_intruder_icao{0};
  bool ownship_valid{false};
};

// Reuses one DAIDALUS instance; setOwnshipState clears traffic each call.
class Evaluator
{
public:
  Evaluator();
  ~Evaluator();
  Evaluator(const Evaluator &) = delete;
  Evaluator & operator=(const Evaluator &) = delete;
  DaaEvaluation evaluate(const OwnshipSi & own, const TrafficSi * traffic, std::size_t n);

private:
  struct Impl;
  Impl * impl_;
};

}  // namespace guara_daidalus

#endif  // GUARA_DAIDALUS_EVALUATE_HPP_
