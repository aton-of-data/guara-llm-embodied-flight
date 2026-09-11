// SPDX-License-Identifier: Apache-2.0
//
// Unit-level behaviour of the Ogma-generated REQ-ALT-01 Copilot C: a non-negative
// NED z does not fire, a climb (negative z) does.
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

TEST(CopilotAlt, NonNegativeZDoesNotFire)
{
  g_fired = false;
  input_signal = 0.0F;
  step();
  EXPECT_FALSE(g_fired);
  input_signal = 0.4F;
  step();
  EXPECT_FALSE(g_fired);
}

TEST(CopilotAlt, ClimbFiresHandler)
{
  g_fired = false;
  input_signal = -0.01F;
  step();
  EXPECT_TRUE(g_fired);
  g_fired = false;
  input_signal = -2.5F;
  step();
  EXPECT_TRUE(g_fired);
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
