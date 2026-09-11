// SPDX-License-Identifier: Apache-2.0
//
// Deterministic pseudo-random input generator shared by AC-5 and AC-6. Generation does not allocate.
#pragma once

#include <cstdint>
#include <limits>
#include <random>

#include "guara_rta/decision_core.hpp"

namespace guara_rta
{

class RandomInputs
{
public:
  explicit RandomInputs(std::uint64_t seed)
  : rng_(seed) {}

  Inputs next(double t_s)
  {
    Inputs in;
    in.t_s = t_s;
    in.in_charge = bit(0.98);
    in.owned_mode_active = bit(0.9);
    in.t_daa_s = timeSignal(60.0);
    in.t_gf_s = timeSignal(5.0);
    in.monitor_violation = bit(0.02);
    in.monitor_action = static_cast<Recovery>(1 + (rng_() % 3U));
    in.input_invalid = bit(0.01);
    return in;
  }

private:
  bool bit(double p_true) {return uniform_(rng_) < p_true;}

  double timeSignal(double scale)
  {
    const double u = uniform_(rng_);
    if (u < 0.3) {
      return std::numeric_limits<double>::infinity();
    }
    return scale * uniform_(rng_);
  }

  std::mt19937_64 rng_;
  std::uniform_real_distribution<double> uniform_{0.0, 1.0};
};

}  // namespace guara_rta
