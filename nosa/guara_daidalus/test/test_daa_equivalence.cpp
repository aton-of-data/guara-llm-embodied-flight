// SPDX-License-Identifier: Apache-2.0
//
// AC-10: T_daa from guara_daidalus matches standalone DAIDALUS ±0.1 s on the same recorded
// inputs, including the TransponderReport conversion used by the node [G 5.3, 5.4, A.14].
#include "guara_daidalus/convert.hpp"
#include "guara_daidalus/daidalus_node.hpp"
#include "guara_daidalus/evaluate.hpp"

#include <chrono>
#include <cmath>
#include <iostream>
#include <limits>
#include <string>

#include <gtest/gtest.h>
#include <guara_msgs/msg/daa_status.hpp>
#include <px4_msgs/msg/transponder_report.hpp>
#include <px4_msgs/msg/vehicle_global_position.hpp>
#include <px4_msgs/msg/vehicle_local_position.hpp>
#include <px4_ros2/utils/message_version.hpp>
#include <rclcpp/rclcpp.hpp>

#include "Daidalus.h"

namespace
{

constexpr double kTolS = 0.1;  // AC-10
constexpr double kFtToM = 0.3048;
constexpr double kKnotToMps = 1852.0 / 3600.0;
constexpr double kFpmToMps = 0.3048 / 60.0;
constexpr double kDegToRad = 3.14159265358979323846 / 180.0;

// Recorded geometry from daidalus C++/examples/DaidalusExample.cpp (commit 0647596).
constexpr double kOwnLat = 33.95;
constexpr double kOwnLon = -96.7;
constexpr double kOwnAltFt = 8700.0;
constexpr double kOwnTrkDeg = 206.0;
constexpr double kOwnGsKnot = 151.0;
constexpr double kOwnVsFpm = 0.0;
constexpr double kIntLat = 33.86191658;
constexpr double kIntLon = -96.73272601;
constexpr double kIntAltFt = 9000.0;
constexpr double kIntTrkDeg = 0.0;
constexpr double kIntGsKnot = 210.0;
constexpr double kIntVsFpm = 0.0;
constexpr std::uint32_t kIntIcao = 0xABCDEFu;
constexpr std::uint64_t kStampUs = 1000000ULL;

double standaloneTdaa()
{
  larcfm::Daidalus daa;
  daa.set_DO_365B();
  const larcfm::Position so =
    larcfm::Position::makeLatLonAlt(kOwnLat, "deg", kOwnLon, "deg", kOwnAltFt, "ft");
  const larcfm::Velocity vo =
    larcfm::Velocity::makeTrkGsVs(kOwnTrkDeg, "deg", kOwnGsKnot, "knot", kOwnVsFpm, "fpm");
  daa.setOwnshipState("ownship", so, vo, 0.0);
  const larcfm::Position si =
    larcfm::Position::makeLatLonAlt(kIntLat, "deg", kIntLon, "deg", kIntAltFt, "ft");
  const larcfm::Velocity vi =
    larcfm::Velocity::makeTrkGsVs(kIntTrkDeg, "deg", kIntGsKnot, "knot", kIntVsFpm, "fpm");
  const int idx = daa.addTrafficState(std::to_string(kIntIcao), si, vi);
  return daa.timeToCorrectiveVolume(idx);
}

guara_daidalus::OwnshipSi recordedOwnship()
{
  guara_daidalus::OwnshipSi own;
  own.time_s = 0.0;
  own.lat_deg = kOwnLat;
  own.lon_deg = kOwnLon;
  own.alt_m_amsl = kOwnAltFt * kFtToM;
  own.track_rad = kOwnTrkDeg * kDegToRad;
  own.gs_mps = kOwnGsKnot * kKnotToMps;
  own.vs_mps_up = kOwnVsFpm * kFpmToMps;
  own.valid = true;
  return own;
}

guara_daidalus::TrafficSi recordedTraffic()
{
  guara_daidalus::TrafficSi tr;
  tr.icao = kIntIcao;
  tr.lat_deg = kIntLat;
  tr.lon_deg = kIntLon;
  tr.alt_m_amsl = kIntAltFt * kFtToM;
  tr.track_rad = kIntTrkDeg * kDegToRad;
  tr.gs_mps = kIntGsKnot * kKnotToMps;
  tr.vs_mps_up = kIntVsFpm * kFpmToMps;
  return tr;
}

px4_msgs::msg::VehicleGlobalPosition recordedGlobal()
{
  px4_msgs::msg::VehicleGlobalPosition g;
  g.timestamp = kStampUs;
  g.timestamp_sample = kStampUs;
  g.lat = kOwnLat;
  g.lon = kOwnLon;
  g.alt = static_cast<float>(kOwnAltFt * kFtToM);
  g.lat_lon_valid = true;
  g.alt_valid = true;
  return g;
}

px4_msgs::msg::VehicleLocalPosition recordedLocal()
{
  const double gs = kOwnGsKnot * kKnotToMps;
  const double trk = kOwnTrkDeg * kDegToRad;
  px4_msgs::msg::VehicleLocalPosition l;
  l.timestamp = kStampUs;
  l.timestamp_sample = kStampUs;
  l.vx = static_cast<float>(gs * std::cos(trk));
  l.vy = static_cast<float>(gs * std::sin(trk));
  l.vz = static_cast<float>(-(kOwnVsFpm * kFpmToMps));
  l.heading = static_cast<float>(trk);
  l.v_xy_valid = true;
  l.v_z_valid = true;
  l.xy_valid = true;
  l.z_valid = true;
  return l;
}

px4_msgs::msg::TransponderReport recordedReport()
{
  using TR = px4_msgs::msg::TransponderReport;
  px4_msgs::msg::TransponderReport r;
  r.timestamp = kStampUs;
  r.icao_address = kIntIcao;
  r.lat = kIntLat;
  r.lon = kIntLon;
  r.altitude = static_cast<float>(kIntAltFt * kFtToM);
  r.heading = static_cast<float>(kIntTrkDeg * kDegToRad);
  r.hor_velocity = static_cast<float>(kIntGsKnot * kKnotToMps);
  r.ver_velocity = static_cast<float>(kIntVsFpm * kFpmToMps);
  r.flags = TR::PX4_ADSB_FLAGS_VALID_COORDS | TR::PX4_ADSB_FLAGS_VALID_ALTITUDE |
    TR::PX4_ADSB_FLAGS_VALID_HEADING | TR::PX4_ADSB_FLAGS_VALID_VELOCITY;
  return r;
}

}  // namespace

TEST(DaaEquivalence, WrapperMatchesStandaloneExample)
{
  const double expected = standaloneTdaa();
  ASSERT_TRUE(std::isfinite(expected)) << "example geometry must enter corrective volume";

  guara_daidalus::Evaluator eval;
  const auto own = recordedOwnship();
  const auto tr = recordedTraffic();
  const guara_daidalus::DaaEvaluation got = eval.evaluate(own, &tr, 1);

  EXPECT_TRUE(got.ownship_valid);
  EXPECT_EQ(got.num_intruders, 1);
  EXPECT_EQ(got.critical_intruder_icao, kIntIcao);
  EXPECT_NEAR(got.t_daa_s, expected, kTolS)
    << "wrapper T_daa=" << got.t_daa_s << " standalone=" << expected;
  std::cout << "[daa_equivalence] standalone_T_daa_s=" << expected
            << " wrapper=" << got.t_daa_s << std::endl;
}

TEST(DaaEquivalence, TransponderReportConversionMatchesStandalone)
{
  const double expected = standaloneTdaa();
  px4_msgs::msg::TransponderReport report = recordedReport();
  guara_daidalus::TrafficSi tr{};
  ASSERT_TRUE(guara_daidalus::trafficFromReport(report, &tr));

  guara_daidalus::OwnshipSi own{};
  guara_daidalus::ownshipFromPx4(recordedGlobal(), recordedLocal(), &own);
  own.time_s = 0.0;
  ASSERT_TRUE(own.valid);

  guara_daidalus::Evaluator eval;
  const guara_daidalus::DaaEvaluation got = eval.evaluate(own, &tr, 1);
  EXPECT_NEAR(got.t_daa_s, expected, kTolS);
}

TEST(DaaEquivalence, NoTrafficYieldsInfinity)
{
  guara_daidalus::Evaluator eval;
  const auto own = recordedOwnship();
  const guara_daidalus::DaaEvaluation got = eval.evaluate(own, nullptr, 0);
  EXPECT_TRUE(std::isinf(got.t_daa_s));
  EXPECT_EQ(got.num_intruders, 0);
  EXPECT_EQ(got.critical_intruder_icao, 0);
}

TEST(DaaEquivalence, NodePublishesDaaStatusFromTransponder)
{
  rclcpp::init(0, nullptr);
  auto daa = std::make_shared<guara_daidalus::DaidalusNode>();
  auto helper = std::make_shared<rclcpp::Node>("daa_equivalence_helper");
  const auto qos = rclcpp::SensorDataQoS();

  auto pub_g = helper->create_publisher<px4_msgs::msg::VehicleGlobalPosition>(
    "fmu/out/vehicle_global_position" +
      px4_ros2::getMessageNameVersion<px4_msgs::msg::VehicleGlobalPosition>(),
    qos);
  auto pub_l = helper->create_publisher<px4_msgs::msg::VehicleLocalPosition>(
    "fmu/out/vehicle_local_position" +
      px4_ros2::getMessageNameVersion<px4_msgs::msg::VehicleLocalPosition>(),
    qos);
  auto pub_t = helper->create_publisher<px4_msgs::msg::TransponderReport>(
    "fmu/out/transponder_report" +
      px4_ros2::getMessageNameVersion<px4_msgs::msg::TransponderReport>(),
    qos);

  guara_msgs::msg::DaaStatus latest;
  bool got = false;
  auto sub = helper->create_subscription<guara_msgs::msg::DaaStatus>(
    "/guara/daa/status", rclcpp::QoS(1).best_effort(),
    [&](const guara_msgs::msg::DaaStatus & msg) {
      latest = msg;
      got = true;
    });

  rclcpp::executors::SingleThreadedExecutor exec;
  exec.add_node(daa);
  exec.add_node(helper);

  const double expected = standaloneTdaa();
  const auto t_end = std::chrono::steady_clock::now() + std::chrono::seconds(3);
  while (rclcpp::ok() && std::chrono::steady_clock::now() < t_end) {
    pub_g->publish(recordedGlobal());
    pub_l->publish(recordedLocal());
    pub_t->publish(recordedReport());
    exec.spin_some();
    if (got && latest.ownship_valid && latest.num_intruders >= 1) {
      break;
    }
  }

  EXPECT_TRUE(got);
  EXPECT_TRUE(latest.ownship_valid);
  EXPECT_GE(latest.num_intruders, 1);
  EXPECT_EQ(latest.critical_intruder_icao, kIntIcao);
  EXPECT_NEAR(latest.time_to_corrective_volume_s, expected, kTolS)
    << "node T_daa=" << latest.time_to_corrective_volume_s << " standalone=" << expected;
  std::cout << "[daa_equivalence] node_T_daa_s=" << latest.time_to_corrective_volume_s
            << " standalone=" << expected << std::endl;

  daa.reset();
  helper.reset();
  rclcpp::shutdown();
}
