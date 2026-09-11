// SPDX-License-Identifier: Apache-2.0
//
// Calls unmodified DAIDALUS v2.0.3a (NOSA). See LICENSE and CHANGES.md.
#include "guara_daidalus/evaluate.hpp"

#include <cmath>
#include <string>

#include "Daidalus.h"

namespace guara_daidalus
{
namespace
{

constexpr double kMToFt = 3.280839895013123;
constexpr double kMpsToKnot = 1.9438444924406046;
constexpr double kMpsToFpm = 196.8503937007874;  // 60 * m_to_ft
constexpr double kRadToDeg = 180.0 / 3.14159265358979323846;

larcfm::Position positionSi(double lat_deg, double lon_deg, double alt_m)
{
  return larcfm::Position::makeLatLonAlt(lat_deg, "deg", lon_deg, "deg", alt_m * kMToFt, "ft");
}

larcfm::Velocity velocitySi(double track_rad, double gs_mps, double vs_mps_up)
{
  return larcfm::Velocity::makeTrkGsVs(
    track_rad * kRadToDeg, "deg", gs_mps * kMpsToKnot, "knot", vs_mps_up * kMpsToFpm, "fpm");
}

}  // namespace

struct Evaluator::Impl
{
  larcfm::Daidalus daa;
  Impl()
  {
    daa.set_DO_365B();
  }
};

Evaluator::Evaluator()
: impl_(new Impl)
{
}

Evaluator::~Evaluator()
{
  delete impl_;
}

DaaEvaluation Evaluator::evaluate(
  const OwnshipSi & own, const TrafficSi * traffic, std::size_t n)
{
  DaaEvaluation out;
  out.ownship_valid = own.valid;
  if (!own.valid || impl_ == nullptr) {
    return out;
  }

  const larcfm::Position so = positionSi(own.lat_deg, own.lon_deg, own.alt_m_amsl);
  const larcfm::Velocity vo = velocitySi(own.track_rad, own.gs_mps, own.vs_mps_up);
  impl_->daa.setOwnshipState("ownship", so, vo, own.time_s);

  const std::size_t count = n < kMaxTraffic ? n : kMaxTraffic;
  for (std::size_t i = 0; i < count; ++i) {
    const TrafficSi & tr = traffic[i];
    const larcfm::Position si = positionSi(tr.lat_deg, tr.lon_deg, tr.alt_m_amsl);
    const larcfm::Velocity vi = velocitySi(tr.track_rad, tr.gs_mps, tr.vs_mps_up);
    // Each intruder is added at the time its report was observed [G A.14]; DAIDALUS projects it to
    // the ownship time itself.
    impl_->daa.addTrafficState(std::to_string(tr.icao), si, vi,
      std::isfinite(tr.time_s) ? tr.time_s : own.time_s);
  }

  out.num_intruders = static_cast<std::uint16_t>(
    impl_->daa.lastTrafficIndex() > 0 ? impl_->daa.lastTrafficIndex() : 0);

  double best = std::numeric_limits<double>::infinity();
  std::uint32_t best_icao = 0;
  for (int idx = 1; idx <= impl_->daa.lastTrafficIndex(); ++idx) {
    const double t = impl_->daa.timeToCorrectiveVolume(idx);
    if (!std::isfinite(t) || t >= best) {
      continue;
    }
    best = t;
    best_icao = 0;
    for (char c : impl_->daa.getAircraftStateAt(idx).getId()) {
      if (c < '0' || c > '9') {
        best_icao = 0;
        break;
      }
      best_icao = best_icao * 10U + static_cast<std::uint32_t>(c - '0');
    }
  }
  out.t_daa_s = best;
  const int alert = impl_->daa.alertLevelAllTraffic();
  out.alert_level = alert > 0 ? alert : 0;
  out.critical_intruder_icao = std::isfinite(best) ? best_icao : 0;
  return out;
}

}  // namespace guara_daidalus
