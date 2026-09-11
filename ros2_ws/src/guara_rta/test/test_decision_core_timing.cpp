// SPDX-License-Identifier: Apache-2.0
//
// AC-6 (property P-5, time): maximum observed execution time of DecisionCore::step over 10^6
// pseudo-random inputs with a fixed seed must not exceed B_dec = 1 ms. This is a measurement on the
// container host, not a worst-case execution time bound (SPEC §7 item 9).
#include <gtest/gtest.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <vector>

#include "guara_rta/decision_core.hpp"
#include "random_inputs.hpp"

namespace guara_rta
{
namespace
{

constexpr std::uint64_t kTicks = 1000000;
constexpr double kTs = 0.05;
constexpr std::int64_t kBDecNs = 1000000;  // B_dec = 1 ms (SPEC §3.5 P-5)

TEST(DecisionCoreTiming, MaximumObservedTickDurationWithinBound)
{
  Parameters p{};
  p.escalation_enabled = true;
  DecisionCore core(p);
  RandomInputs gen(42);

  std::vector<Inputs> inputs;
  inputs.reserve(kTicks);
  for (std::uint64_t k = 0; k < kTicks; ++k) {
    inputs.push_back(gen.next(static_cast<double>(k) * kTs));
  }
  std::vector<std::int64_t> durations(kTicks);

  for (std::uint64_t k = 0; k < kTicks; ++k) {
    const auto t0 = std::chrono::steady_clock::now();
    const Output out = core.step(inputs[k]);
    const auto t1 = std::chrono::steady_clock::now();
    (void)out;
    durations[k] = std::chrono::duration_cast<std::chrono::nanoseconds>(t1 - t0).count();
  }

  std::vector<std::int64_t> sorted = durations;
  std::sort(sorted.begin(), sorted.end());
  const auto pct = [&sorted](double q) {
      return sorted[static_cast<std::size_t>(q * static_cast<double>(sorted.size() - 1))];
    };
  const std::int64_t max_ns = sorted.back();
  const auto over = std::count_if(durations.begin(), durations.end(),
      [](std::int64_t d) {return d > kBDecNs;});

  std::printf(
    "[timing] ticks=%llu p50_ns=%lld p99_ns=%lld p999_ns=%lld max_ns=%lld over_bound=%lld\n",
    static_cast<unsigned long long>(kTicks), static_cast<long long>(pct(0.5)),
    static_cast<long long>(pct(0.99)), static_cast<long long>(pct(0.999)),
    static_cast<long long>(max_ns), static_cast<long long>(over));
  EXPECT_LE(max_ns, kBDecNs);
}

}  // namespace
}  // namespace guara_rta
