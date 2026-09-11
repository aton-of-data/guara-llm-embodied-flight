// SPDX-License-Identifier: Apache-2.0
//
// Monitor aggregation rules (review 2026-09-11 H-4, H-6). The table converts the stream of
// MonitorVerdict samples into the signals M(k), select(k) and the monitor share of V(k). Every
// failure mode of the monitor channel — a crashed monitor, an incomplete monitor, an out-of-range
// action, more monitors than the table holds — must set V(k) rather than stay silent.
#include <cstdio>
#include <string>

#include <gtest/gtest.h>

#include "guara_rta/monitor_table.hpp"

namespace
{

using guara_rta::MonitorAccept;
using guara_rta::MonitorEvaluation;
using guara_rta::MonitorTable;
using guara_rta::MonitorVerdictSample;
using guara_rta::Recovery;

constexpr std::uint8_t kClassLog = 0;
constexpr std::uint8_t kClassSwitch = 1;
constexpr std::uint8_t kActionHold = 0;
constexpr std::uint8_t kActionRtl = 1;
constexpr std::uint8_t kActionLand = 2;

MonitorVerdictSample sample(const char * id, bool violated, std::uint8_t action = kActionHold,
  std::uint8_t monitor_class = kClassSwitch, bool inputs_complete = true)
{
  MonitorVerdictSample s;
  s.id = id;
  s.monitor_class = monitor_class;
  s.action = action;
  s.violated = violated;
  s.inputs_complete = inputs_complete;
  return s;
}

MonitorTable makeTable(bool with_expected = true)
{
  MonitorTable t;
  t.configure(0.5);
  if (with_expected) {
    EXPECT_TRUE(t.expect("REQ-ALT-01"));
  }
  return t;
}

// A violating switch-class monitor sets M(k) and selects its action.
TEST(MonitorTable, ViolationSelectsHighestRankAction)
{
  MonitorTable t = makeTable();
  t.observe(sample("REQ-ALT-01", true, kActionHold), 1.0);
  t.observe(sample("REQ-GEO-02", true, kActionRtl), 1.0);
  const MonitorEvaluation e = t.evaluate(1.0);
  EXPECT_TRUE(e.violation);
  EXPECT_EQ(Recovery::kRtl, e.action);
  EXPECT_FALSE(e.invalid);
  EXPECT_STREQ("REQ-ALT-01", e.first_violating_id);
}

// A log-class monitor never enters M(k) (MonitorVerdict.msg CLASS_LOG).
TEST(MonitorTable, LogClassNeverSwitches)
{
  MonitorTable t = makeTable();
  t.observe(sample("REQ-ALT-01", false), 1.0);
  t.observe(sample("REQ-LOG-09", true, kActionLand, kClassLog), 1.0);
  const MonitorEvaluation e = t.evaluate(1.0);
  EXPECT_FALSE(e.violation);
  EXPECT_FALSE(e.invalid);
}

// H-4: an expected monitor that stops publishing sets V(k) instead of silently disappearing.
TEST(MonitorTable, ExpectedMonitorGoingStaleIsInvalid)
{
  MonitorTable t = makeTable();
  t.observe(sample("REQ-ALT-01", false), 1.0);
  EXPECT_FALSE(t.evaluate(1.4).invalid);
  const MonitorEvaluation e = t.evaluate(1.6);
  EXPECT_TRUE(e.invalid);
  EXPECT_STREQ("REQ-ALT-01", e.first_invalid_id);
}

// H-4: an expected monitor that has never published is invalid from the first tick.
TEST(MonitorTable, ExpectedMonitorNeverSeenIsInvalid)
{
  MonitorTable t = makeTable();
  EXPECT_TRUE(t.evaluate(0.0).invalid);
}

// H-4: inputs_complete = false means the monitor cannot decide; it must not read as "no violation".
TEST(MonitorTable, IncompleteInputsAreInvalid)
{
  MonitorTable t = makeTable();
  t.observe(sample("REQ-ALT-01", false, kActionHold, kClassSwitch, /*inputs_complete=*/false), 1.0);
  EXPECT_TRUE(t.evaluate(1.0).invalid);
}

// H-6: an action outside ACTION_HOLD..ACTION_LAND must not be mapped into Recovery(4); it is a
// corrupt or hostile publisher and sets V(k).
TEST(MonitorTable, OutOfRangeActionIsInvalid)
{
  MonitorTable t = makeTable();
  EXPECT_EQ(MonitorAccept::kInvalidField, t.observe(sample("REQ-ALT-01", true, 3), 1.0));
  const MonitorEvaluation e = t.evaluate(1.0);
  EXPECT_TRUE(e.invalid);
  EXPECT_LE(static_cast<int>(e.action), static_cast<int>(Recovery::kLand));
}

// H-6: the same rule for monitor_class.
TEST(MonitorTable, OutOfRangeClassIsInvalid)
{
  MonitorTable t = makeTable();
  EXPECT_EQ(MonitorAccept::kInvalidField, t.observe(sample("REQ-ALT-01", true, kActionHold, 7), 1.0));
  EXPECT_TRUE(t.evaluate(1.0).invalid);
}

// A valid sample from the same monitor clears the invalid mark; the table is not permanently poisoned.
TEST(MonitorTable, ValidSampleClearsTheInvalidMark)
{
  MonitorTable t = makeTable();
  t.observe(sample("REQ-ALT-01", false, 9), 1.0);
  ASSERT_TRUE(t.evaluate(1.0).invalid);
  t.observe(sample("REQ-ALT-01", false, kActionHold), 1.1);
  EXPECT_FALSE(t.evaluate(1.1).invalid);
}

// H-4: a full table drops verdicts. Dropping silently is fail-open, so the overflow sets V(k).
TEST(MonitorTable, OverflowIsInvalid)
{
  MonitorTable t = makeTable(/*with_expected=*/false);
  char ids[guara_rta::kMaxMonitors + 1][16];
  for (std::size_t i = 0; i <= guara_rta::kMaxMonitors; ++i) {
    std::snprintf(ids[i], sizeof(ids[i]), "REQ-%02zu", i);
    const MonitorAccept accept = t.observe(sample(ids[i], false), 1.0);
    if (i < guara_rta::kMaxMonitors) {
      EXPECT_EQ(MonitorAccept::kAccepted, accept) << i;
    } else {
      EXPECT_EQ(MonitorAccept::kTableFull, accept);
    }
  }
  EXPECT_TRUE(t.evaluate(1.0).invalid);
}

// Identifiers longer than the slot are distinguished, not silently merged into one monitor.
TEST(MonitorTable, LongIdentifiersAreNotConflated)
{
  MonitorTable t = makeTable(/*with_expected=*/false);
  const std::string too_long(guara_rta::kMonitorIdCapacity + 8, 'a');
  EXPECT_EQ(MonitorAccept::kInvalidField, t.observe(sample(too_long.c_str(), true), 1.0))
    << "an identifier that does not fit the slot must be reported, not truncated into another one";
  EXPECT_TRUE(t.evaluate(1.0).invalid);
}

}  // namespace
