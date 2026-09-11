// SPDX-License-Identifier: Apache-2.0
//
// Traffic bookkeeping of the DAA node (review 2026-09-11 H-7). Each intruder report carries its own
// observation time, a full table evicts the least useful entry instead of dropping every new
// intruder, and an ownship sample that stops arriving invalidates the DAA status instead of being
// republished every 200 ms as if it were fresh.
#include <gtest/gtest.h>

#include "guara_daidalus/traffic_table.hpp"

namespace guara_daidalus
{
namespace
{

TrafficSi intruder(std::uint32_t icao, double time_s, double lat = 33.9, double lon = -96.7)
{
  TrafficSi t;
  t.icao = icao;
  t.time_s = time_s;
  t.lat_deg = lat;
  t.lon_deg = lon;
  t.alt_m_amsl = 2700.0;
  t.gs_mps = 100.0;
  return t;
}

TEST(TrafficTable, KeepsTheObservationTimeOfEachReport)
{
  TrafficTable table;
  table.upsert(intruder(1, 10.0), 10.0);
  table.upsert(intruder(2, 12.5), 12.5);
  TrafficSi live[kMaxTraffic];
  const std::size_t n = table.collect(13.0, 5.0, live);
  ASSERT_EQ(2U, n);
  EXPECT_EQ(10.0, live[0].time_s);
  EXPECT_EQ(12.5, live[1].time_s) << "each state must be added to DAIDALUS at its own time";
}

TEST(TrafficTable, DropsReportsOlderThanTheMaximumAge)
{
  TrafficTable table;
  table.upsert(intruder(1, 1.0), 1.0);
  table.upsert(intruder(2, 9.0), 9.0);
  TrafficSi live[kMaxTraffic];
  ASSERT_EQ(1U, table.collect(10.0, 5.0, live));
  EXPECT_EQ(2U, live[0].icao);
}

TEST(TrafficTable, UpdatingAnIntruderDoesNotConsumeASlot)
{
  TrafficTable table;
  table.upsert(intruder(7, 1.0), 1.0);
  table.upsert(intruder(7, 2.0), 2.0);
  EXPECT_EQ(1U, table.size());
  TrafficSi live[kMaxTraffic];
  ASSERT_EQ(1U, table.collect(2.0, 5.0, live));
  EXPECT_EQ(2.0, live[0].time_s);
}

// H-7: before this change the table silently ignored every new intruder once full, which is the
// worst possible failure for a DAA function: the aircraft that appears last is the one closest to
// the ownship in a busy sector.
TEST(TrafficTable, FullTableEvictsTheOldestEntry)
{
  TrafficTable table;
  for (std::size_t i = 0; i < kMaxTraffic; ++i) {
    table.upsert(intruder(static_cast<std::uint32_t>(i + 1), 1.0 + static_cast<double>(i)),
      1.0 + static_cast<double>(i));
  }
  ASSERT_EQ(kMaxTraffic, table.size());
  const bool inserted = table.upsert(intruder(999, 100.0), 100.0);
  EXPECT_TRUE(inserted);
  EXPECT_EQ(kMaxTraffic, table.size());
  TrafficSi live[kMaxTraffic];
  const std::size_t n = table.collect(100.0, 1000.0, live);
  bool has_new = false;
  bool has_oldest = false;
  for (std::size_t i = 0; i < n; ++i) {
    has_new = has_new || live[i].icao == 999U;
    has_oldest = has_oldest || live[i].icao == 1U;
  }
  EXPECT_TRUE(has_new);
  EXPECT_FALSE(has_oldest);
}

// H-7: the ownship gate. A local-position stream that stops must invalidate the status.
TEST(OwnshipGate, StaleOwnshipIsInvalid)
{
  EXPECT_TRUE(ownshipFresh(/*t_recv_s=*/10.0, /*t_now_s=*/10.3, /*max_age_s=*/0.5));
  EXPECT_FALSE(ownshipFresh(10.0, 10.9, 0.5));
  EXPECT_FALSE(ownshipFresh(/*never received*/ -1.0, 10.0, 0.5));
}

}  // namespace
}  // namespace guara_daidalus
