// SPDX-License-Identifier: Apache-2.0
//
// AC-5 (property P-5, allocation): the global allocation functions are replaced by counting
// wrappers; after construction the decision core must perform zero allocations over 10^6 ticks.
#include <gtest/gtest.h>

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <new>

#include "guara_rta/decision_core.hpp"
#include "random_inputs.hpp"

namespace
{
std::atomic<std::uint64_t> g_allocations{0};
}  // namespace

void * operator new(std::size_t size)
{
  g_allocations.fetch_add(1, std::memory_order_relaxed);
  if (void * p = std::malloc(size == 0 ? 1 : size)) {
    return p;
  }
  throw std::bad_alloc();
}

void * operator new[](std::size_t size)
{
  g_allocations.fetch_add(1, std::memory_order_relaxed);
  if (void * p = std::malloc(size == 0 ? 1 : size)) {
    return p;
  }
  throw std::bad_alloc();
}

void operator delete(void * p) noexcept {std::free(p);}
void operator delete[](void * p) noexcept {std::free(p);}
void operator delete(void * p, std::size_t) noexcept {std::free(p);}
void operator delete[](void * p, std::size_t) noexcept {std::free(p);}

namespace guara_rta
{
namespace
{

constexpr std::uint64_t kTicks = 1000000;
constexpr double kTs = 0.05;

TEST(DecisionCoreNoAlloc, ZeroAllocationsAfterInitialisation)
{
  Parameters p{};
  p.escalation_enabled = true;  // exercise every branch, including persistence escalation
  DecisionCore core(p);
  RandomInputs gen(42);

  // Sanity check of the instrumentation itself.
  const std::uint64_t before_probe = g_allocations.load();
  delete new int(7);
  ASSERT_EQ(g_allocations.load(), before_probe + 1);

  std::uint64_t transitions = 0;
  const std::uint64_t before = g_allocations.load();
  for (std::uint64_t k = 0; k < kTicks; ++k) {
    const Output out = core.step(gen.next(static_cast<double>(k) * kTs));
    transitions += out.transition.id != transition::kNone ? 1U : 0U;
    if ((k % 1000U) == 999U) {
      (void)core.latchOnActuationFailure(static_cast<double>(k) * kTs);
    }
  }
  const std::uint64_t after = g_allocations.load();

  std::printf("[no_alloc] ticks=%llu transitions=%llu allocations=%llu\n",
    static_cast<unsigned long long>(kTicks), static_cast<unsigned long long>(transitions),
    static_cast<unsigned long long>(after - before));
  EXPECT_EQ(after - before, 0U);
  EXPECT_GT(transitions, 0U) << "input generator did not exercise the transition table";
}

}  // namespace
}  // namespace guara_rta
