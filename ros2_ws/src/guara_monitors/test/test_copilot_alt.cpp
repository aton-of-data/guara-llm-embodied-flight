// SPDX-License-Identifier: Apache-2.0
//
// Unit-level behaviour of the Ogma-generated REQ-ALT-01 Copilot C. The requirement is a 2.0 m
// altitude ceiling (NED z >= -2.0), so the ground and the first part of a climb do not fire and only
// crossing the ceiling does. Firing from the first sample made AC-3 vacuous (review of 2026-09-11).
#include <gtest/gtest.h>

extern "C" {
#include "copilot.h"
}

float input_signal = 0.0F;
namespace
{
bool g_fired = false;
}

extern "C" void handlerAltitudeBelowCeiling(void)
{
  g_fired = true;
}

TEST(CopilotAlt, BelowTheCeilingDoesNotFire)
{
  for (const float z : {0.4F, 0.0F, -0.01F, -1.5F, -2.0F}) {
    g_fired = false;
    input_signal = z;
    step();
    EXPECT_FALSE(g_fired) << "z=" << z;
  }
}

TEST(CopilotAlt, CrossingTheCeilingFiresHandler)
{
  for (const float z : {-2.01F, -2.5F, -30.0F}) {
    g_fired = false;
    input_signal = z;
    step();
    EXPECT_TRUE(g_fired) << "z=" << z;
  }
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
