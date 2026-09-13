// SPDX-License-Identifier: Apache-2.0
//
// guara_rta_node: the Guará arbiter process (SPEC §2, ADR 0001).
//
// Structure
//   GuaraCfGateway  px4_ros2::ModeBase, the owned mode. Forwards CF setpoints according to
//                   GatewayLogic and reports a stalled decision core through the arming check.
//   GuaraExecutor   px4_ros2::ModeExecutorBase. Tracks IC(k) through onActivate/onDeactivate.
//   ArbiterNode     rclcpp::Node owning both, the input subscriptions, the decision timer and the
//                   actuator publisher.
//
// Threading
//   The interface library's callbacks (vehicle status, arming checks, setpoint updates) and the CF
//   setpoint subscription run in the node's default mutually exclusive callback group. The decision
//   timer, the input subscriptions and the acknowledgement subscription run in a second mutually
//   exclusive group. The two groups communicate only through atomics, so a stalled decision group
//   leaves the arming-check replies alive and the heartbeat check observable by PX4 (SPEC FM-4).
//
// Actuation
//   Mode requests are published as VEHICLE_CMD_SET_NAV_STATE on fmu/in/vehicle_command_mode_executor
//   with source_component = COMPONENT_MODE_EXECUTOR_START + executor id, the wire format produced by
//   ModeExecutorBase::scheduleMode [G 1.3, A.2; G D.1]. The blocking acknowledgement wait of
//   sendCommandSync [G A.1] is replaced by ActuatorLogic and an asynchronous acknowledgement
//   subscription, so no call on the decision path blocks.
#include <array>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <thread>

#include <Eigen/Core>
#include <rclcpp/rclcpp.hpp>

#include <px4_msgs/msg/vehicle_command.hpp>
#include <px4_msgs/msg/vehicle_command_ack.hpp>
#include <px4_msgs/msg/vehicle_local_position.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>
#include <px4_ros2/components/events.hpp>
#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/components/mode_executor.hpp>
#include <px4_ros2/control/setpoint_types/experimental/trajectory.hpp>
#include <px4_ros2/utils/message_version.hpp>

#include <guara_msgs/msg/cf_setpoint.hpp>
#include <guara_msgs/msg/daa_status.hpp>
#include <guara_msgs/msg/monitor_verdict.hpp>
#include <guara_msgs/msg/rta_event.hpp>
#include <guara_msgs/msg/rta_state.hpp>

#include "guara_rta/actuator_logic.hpp"
#include "guara_rta/decision_core.hpp"
#include "guara_rta/gateway_logic.hpp"
#include "guara_rta/geofence_channel.hpp"
#include "guara_rta/input_manager.hpp"
#include "guara_rta/monitor_table.hpp"
#include "guara_rta/param_digest.hpp"
#include "guara_rta/safety_profile.hpp"
#include "guara/guara.h"

namespace guara_rta
{
namespace
{

constexpr const char * kModeName = "Guara CF Gateway";
constexpr double kInf = std::numeric_limits<double>::infinity();

// The encodings the MonitorTable assumes must equal the message constants.
static_assert(monitor::kClassLog == guara_msgs::msg::MonitorVerdict::CLASS_LOG, "CLASS_LOG");
static_assert(monitor::kClassSwitch == guara_msgs::msg::MonitorVerdict::CLASS_SWITCH, "CLASS_SWITCH");
static_assert(monitor::kActionHold == guara_msgs::msg::MonitorVerdict::ACTION_HOLD, "ACTION_HOLD");
static_assert(monitor::kActionRtl == guara_msgs::msg::MonitorVerdict::ACTION_RTL, "ACTION_RTL");
static_assert(monitor::kActionLand == guara_msgs::msg::MonitorVerdict::ACTION_LAND, "ACTION_LAND");

double steadySeconds() noexcept
{
  return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

std::int64_t steadyNanoseconds() noexcept
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count();
}

px4_ros2::ModeBase::ModeID navStateFor(Command c) noexcept
{
  switch (c) {
    case Command::kHold: return px4_ros2::ModeBase::kModeIDLoiter;  // Hold = AUTO_LOITER [G 1.2]
    case Command::kRtl: return px4_ros2::ModeBase::kModeIDRtl;
    case Command::kLand: return px4_ros2::ModeBase::kModeIDLand;
    case Command::kOwnedMode:
    case Command::kNone: break;
  }
  return px4_ros2::ModeBase::kModeIDInvalid;
}

// State shared between the default callback group and the decision callback group. Every field is
// an atomic: the two groups never hold a lock in common, so a stalled decision group keeps the
// arming-check replies alive (SPEC FM-4).
struct SharedState
{
  std::atomic<std::uint8_t> core_state{static_cast<std::uint8_t>(State::kInactive)};
  std::atomic<std::int64_t> last_tick_ns{0};
  std::atomic<bool> in_charge{false};
  std::atomic<bool> owned_mode_active{false};
  // Set when a mode request was neither accepted nor confirmed within the budget (SPEC FM-7). The
  // owned mode then fails its own arming check, so PX4's fallback chain takes the vehicle instead of
  // leaving it hovering in a mode the arbiter can no longer steer (review 2026-09-11 §4).
  std::atomic<bool> actuation_failed{false};
  // Latest CF proposal, republished by the gateway for the decision group's shadow check.
  std::atomic<float> cf_vx{0.0F};
  std::atomic<float> cf_vy{0.0F};
  std::atomic<float> cf_vz{0.0F};
  std::atomic<double> cf_recv_s{-kInf};
  // Gateway rejection counters, for telemetry and for the CF-behaviour evidence of an LLM run.
  std::atomic<std::uint32_t> cf_rejected_stamp{0};
  std::atomic<std::uint32_t> cf_rejected_non_finite{0};
  std::atomic<std::uint32_t> cf_rejected_guard{0};
  std::atomic<std::uint32_t> cf_clamped{0};
};

class GuaraCfGateway : public px4_ros2::ModeBase
{
public:
  GuaraCfGateway(rclcpp::Node & node, SharedState & shared, double cf_timeout_s,
    double heartbeat_max_age_s, const GatewayLimits & limits)
  : ModeBase(node, Settings{kModeName}), shared_(shared), logic_(cf_timeout_s, limits),
    heartbeat_max_age_ns_(static_cast<std::int64_t>(heartbeat_max_age_s * 1e9))
  {
    setpoint_ = std::make_shared<px4_ros2::TrajectorySetpointType>(*this);
    cf_sub_ = node.create_subscription<guara_msgs::msg::CfSetpoint>(
      "/guara/cf/setpoint", rclcpp::QoS(1).best_effort(),
      [this](const guara_msgs::msg::CfSetpoint & msg) {
        // Freshness and ordering are measured from this reception instant on the gateway clock; the
        // CF-supplied stamp is only checked for plausibility (review 2026-09-11 H-1).
        const double t_recv_s = this->node().get_clock()->now().seconds();
        const std::array<float, 3> v{msg.velocity_ned_m_s[0], msg.velocity_ned_m_s[1],
          msg.velocity_ned_m_s[2]};
        logic_.onCfSetpoint(t_recv_s, rclcpp::Time(msg.stamp).seconds(), v, msg.yaw_ned_rad);
        shared_.cf_vx.store(v[0]);
        shared_.cf_vy.store(v[1]);
        shared_.cf_vz.store(v[2]);
        shared_.cf_recv_s.store(t_recv_s);
        publishCounters();
      });
  }

  void setGuard(const SetpointGuard * guard) noexcept {logic_.setGuard(guard);}

  void onActivate() override {shared_.owned_mode_active.store(true);}

  void onDeactivate() override {shared_.owned_mode_active.store(false);}

  void checkArmingAndRunConditions(px4_ros2::HealthAndArmingCheckReporter & reporter) override
  {
    // SPEC FM-4: a decision core that has not ticked within H_max makes the owned mode unable to
    // run, which PX4 resolves with its mode fallback [G A.5, A.6].
    const std::int64_t last = shared_.last_tick_ns.load();
    if (last == 0 || steadyNanoseconds() - last > heartbeat_max_age_ns_) {
      reporter.armingCheckFailureExt(
        px4_ros2::events::ID("guara_decision_core_stalled"), px4_ros2::events::Log::Error,
        "Guara decision core stalled");
    }
    // SPEC FM-7: the arbiter can no longer actuate the recovery. Failing the owned mode's check
    // hands the vehicle to PX4's fallback chain [G A.5, A.6] instead of latching in a mode nobody
    // steers (review 2026-09-11 §4).
    if (shared_.actuation_failed.load()) {
      reporter.armingCheckFailureExt(
        px4_ros2::events::ID("guara_actuation_failed"), px4_ros2::events::Log::Error,
        "Guara mode request not effective");
    }
  }

  void updateSetpoint(float /*dt_s*/) override
  {
    const double now_s = node().get_clock()->now().seconds();
    logic_.onCoreState(static_cast<State>(shared_.core_state.load()), now_s);
    const GatewaySetpoint sp = logic_.compute(now_s);
    publishCounters();
    const Eigen::Vector3f v{sp.velocity_ned_m_s[0], sp.velocity_ned_m_s[1], sp.velocity_ned_m_s[2]};
    if (std::isfinite(sp.yaw_ned_rad)) {
      setpoint_->update(v, std::nullopt, sp.yaw_ned_rad);
    } else {
      setpoint_->update(v);
    }
  }

private:
  void publishCounters() noexcept
  {
    shared_.cf_rejected_stamp.store(logic_.rejectedImplausibleStamp());
    shared_.cf_rejected_non_finite.store(logic_.rejectedNonFinite());
    shared_.cf_rejected_guard.store(logic_.rejectedByGuard());
    shared_.cf_clamped.store(logic_.clamped());
  }

  SharedState & shared_;
  GatewayLogic logic_;
  std::int64_t heartbeat_max_age_ns_;
  std::shared_ptr<px4_ros2::TrajectorySetpointType> setpoint_;
  rclcpp::Subscription<guara_msgs::msg::CfSetpoint>::SharedPtr cf_sub_;
};

class GuaraExecutor : public px4_ros2::ModeExecutorBase
{
public:
  GuaraExecutor(GuaraCfGateway & owned_mode, SharedState & shared)
  : ModeExecutorBase(Settings{}, owned_mode), shared_(shared) {}

  void onActivate() override {shared_.in_charge.store(true);}

  void onDeactivate(DeactivateReason /*reason*/) override {shared_.in_charge.store(false);}

private:
  SharedState & shared_;
};

class ArbiterNode : public rclcpp::Node
{
public:
  ArbiterNode()
  : Node("guara_rta")
  {
    loadParameters();
    const char * invalid = validate(params_);
    if (invalid != nullptr) {
      throw std::invalid_argument(std::string("invalid RTA parameters: ") + invalid);
    }
    {
      std::uint8_t digest[kParamDigestLen];
      paramDigest(params_, digest);
      char hex[2 * kParamDigestLen + 1];
      for (std::size_t i = 0; i < kParamDigestLen; ++i) {
        std::snprintf(hex + (2U * i), 3, "%02x", static_cast<unsigned>(digest[i]));
      }
      RCLCPP_INFO(get_logger(), "guara-core %s abi %s digest=%s",
        GUARA_CORE_VERSION, GUARA_ABI_VERSION, hex);
    }
    // The geofence channel exists only if the predictor is configured; the two switches must agree,
    // otherwise a fence is either evaluated without being checked for freshness (review H-5) or a
    // channel is checked that never publishes.
    if (geofence_.enabled() != input_config_[static_cast<std::size_t>(Channel::kGeofence)].enabled) {
      throw std::invalid_argument(
        "geofence.enabled and inputs.geofence.enabled must be set together");
    }
    if (const char * bad = validateProfile(profile_, input_config_, expected_monitors_, omissions_)) {
      throw std::invalid_argument(std::string("safety profile rejected the configuration: ") + bad);
    }
    core_ = std::make_unique<DecisionCore>(params_);
    actuator_ = std::make_unique<ActuatorLogic>(actuator_params_);
    inputs_ = std::make_unique<InputManager>(input_config_);

    gateway_ = std::make_unique<GuaraCfGateway>(*this, shared_, cf_timeout_s_, heartbeat_max_age_s_,
      gateway_limits_);
    if (geofence_.enabled() && shadow_check_) {
      // Shadow check of every forwarded setpoint against the fence (review 2026-09-11 §4).
      guard_ = std::make_unique<GeofenceSetpointGuard>(geofence_, params_.tau_gf_s + params_.h_gf_s);
      gateway_->setGuard(guard_.get());
    }
    executor_ = std::make_unique<GuaraExecutor>(*gateway_, shared_);
    if (!executor_->doRegister()) {
      throw std::runtime_error("registration of executor and owned mode failed");
    }
    source_component_ = static_cast<std::uint16_t>(
      px4_msgs::msg::VehicleCommand::COMPONENT_MODE_EXECUTOR_START + executor_->id());
    RCLCPP_INFO(get_logger(), "registered '%s' (executor id %d, nav_state %u)", kModeName,
      executor_->id(), static_cast<unsigned>(gateway_->id()));

    decision_group_ = create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
    rclcpp::SubscriptionOptions opts;
    opts.callback_group = decision_group_;
    const auto sensor_qos = rclcpp::QoS(1).best_effort();

    lpos_sub_ = create_subscription<px4_msgs::msg::VehicleLocalPosition>(
      "fmu/out/vehicle_local_position" +
      px4_ros2::getMessageNameVersion<px4_msgs::msg::VehicleLocalPosition>(), sensor_qos,
      [this](const px4_msgs::msg::VehicleLocalPosition & msg) {onLocalPosition(msg);}, opts);
    status_sub_ = create_subscription<px4_msgs::msg::VehicleStatus>(
      "fmu/out/vehicle_status" + px4_ros2::getMessageNameVersion<px4_msgs::msg::VehicleStatus>(),
      sensor_qos, [this](const px4_msgs::msg::VehicleStatus & msg) {
        const double t = steadySeconds();
        inputs_->onReceive(Channel::kVehicleStatus, t, true);
        nav_state_ = msg.nav_state;
        actuator_->onNavState(msg.nav_state, t);
      }, opts);
    ack_sub_ = create_subscription<px4_msgs::msg::VehicleCommandAck>(
      "fmu/out/vehicle_command_ack" +
      px4_ros2::getMessageNameVersion<px4_msgs::msg::VehicleCommandAck>(), sensor_qos,
      [this](const px4_msgs::msg::VehicleCommandAck & msg) {onAck(msg);}, opts);
    verdict_sub_ = create_subscription<guara_msgs::msg::MonitorVerdict>(
      "/guara/monitors/verdict", rclcpp::QoS(32).best_effort(),
      [this](const guara_msgs::msg::MonitorVerdict & msg) {onVerdict(msg);}, opts);
    daa_sub_ = create_subscription<guara_msgs::msg::DaaStatus>(
      "/guara/daa/status", sensor_qos,
      [this](const guara_msgs::msg::DaaStatus & msg) {
        const double t = steadySeconds();
        // An invalid ownship is an invalid input on the enabled channel, never "no conflict".
        t_daa_s_ = msg.ownship_valid ? msg.time_to_corrective_volume_s : kInf;
        inputs_->onReceive(Channel::kDaa, t, msg.ownship_valid &&
          !std::isnan(msg.time_to_corrective_volume_s));
        last_input_recv_s_ = t;
      }, opts);

    command_pub_ = create_publisher<px4_msgs::msg::VehicleCommand>(
      "fmu/in/vehicle_command_mode_executor" +
      px4_ros2::getMessageNameVersion<px4_msgs::msg::VehicleCommand>(), 1);
    event_pub_ = create_publisher<guara_msgs::msg::RtaEvent>("/guara/rta/event", rclcpp::QoS(64).reliable());
    state_pub_ = create_publisher<guara_msgs::msg::RtaState>("/guara/rta/state", rclcpp::QoS(10));

    const auto period = std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::duration<double>(period_s_));
    decision_timer_ = create_wall_timer(period, [this]() {onTick();}, decision_group_);
    t_start_s_ = steadySeconds();
#ifdef GUARA_SIM_FAULT_INJECTION
    if (hang_ros_executor_after_s_ >= 0.0) {
      fault_timer_ = create_wall_timer(std::chrono::milliseconds(50), [this]() {maybeHangRosExecutor();});
    }
#endif
  }

private:
  void loadParameters()
  {
    period_s_ = declare_parameter("decision.period_s", 0.05);
    params_.tau_daa_s = declare_parameter("core.tau_daa_s", params_.tau_daa_s);
    params_.tau_gf_s = declare_parameter("core.tau_gf_s", params_.tau_gf_s);
    params_.h_daa_s = declare_parameter("core.h_daa_s", params_.h_daa_s);
    params_.h_gf_s = declare_parameter("core.h_gf_s", params_.h_gf_s);
    params_.dwell_s = declare_parameter("core.dwell_s", params_.dwell_s);
    params_.n_max = static_cast<std::uint16_t>(declare_parameter("core.n_max",
      static_cast<int>(params_.n_max)));
    params_.window_s = declare_parameter("core.window_s", params_.window_s);
    params_.return_enabled = declare_parameter("core.return_enabled", params_.return_enabled);
    params_.escalation_enabled = declare_parameter("core.escalation_enabled",
      params_.escalation_enabled);
    params_.escalation_s = declare_parameter("core.escalation_s", params_.escalation_s);

    // An *enabled* channel is a channel the arbiter depends on; it contributes to V(k) when it is
    // missing, stale or invalid (review 2026-09-11 H-3, H-5). There is no "consumed but not
    // checked" channel any more.
    const auto channel = [this](Channel c, const std::string & name, bool enabled, double age) {
        input_config_[static_cast<std::size_t>(c)] = ChannelConfig{
          declare_parameter("inputs." + name + ".enabled", enabled),
          declare_parameter("inputs." + name + ".max_age_s", age)};
      };
    channel(Channel::kLocalPosition, "local_position", true, 0.2);
    channel(Channel::kVehicleStatus, "vehicle_status", true, 1.0);
    channel(Channel::kMonitor, "monitor", true, 0.5);
    channel(Channel::kDaa, "daa", false, 1.0);
    channel(Channel::kGeofence, "geofence", false, 0.2);

    const double monitor_age = input_config_[static_cast<std::size_t>(Channel::kMonitor)].max_age_s;
    monitors_.configure(monitor_age);
    for (const auto & id : declare_parameter("inputs.monitor.expected_ids",
      std::vector<std::string>{}))
    {
      if (!monitors_.expect(id.c_str())) {
        throw std::invalid_argument("inputs.monitor.expected_ids: '" + id +
          "' does not fit the monitor table");
      }
      ++expected_monitors_;
    }

    const std::string profile_name = declare_parameter("safety.profile", std::string("flight"));
    if (const char * bad = parseProfile(profile_name.c_str(), &profile_)) {
      throw std::invalid_argument(bad);
    }
    for (const auto & name : declare_parameter("safety.accepted_omissions",
      std::vector<std::string>{}))
    {
      const std::uint32_t bit = omissionBit(name.c_str());
      if (bit == 0U) {
        throw std::invalid_argument("safety.accepted_omissions: unknown protection '" + name + "'");
      }
      omissions_ |= bit;
      RCLCPP_WARN(get_logger(), "safety.accepted_omissions declares '%s': this protection is off",
        name.c_str());
    }

    actuator_params_.retry_period_s = declare_parameter("actuator.retry_period_s",
      actuator_params_.retry_period_s);
    actuator_params_.n_retry = static_cast<std::uint16_t>(declare_parameter("actuator.n_retry",
      static_cast<int>(actuator_params_.n_retry)));
    actuator_params_.confirm_timeout_s = declare_parameter("actuator.confirm_timeout_s",
      actuator_params_.confirm_timeout_s);
    cf_timeout_s_ = declare_parameter("gateway.cf_timeout_s", 0.5);
    gateway_limits_.max_speed_h_m_s = declare_parameter("gateway.max_speed_h_m_s",
      gateway_limits_.max_speed_h_m_s);
    gateway_limits_.max_climb_rate_m_s = declare_parameter("gateway.max_climb_rate_m_s",
      gateway_limits_.max_climb_rate_m_s);
    gateway_limits_.max_descent_rate_m_s = declare_parameter("gateway.max_descent_rate_m_s",
      gateway_limits_.max_descent_rate_m_s);
    gateway_limits_.max_yaw_rate_rad_s = declare_parameter("gateway.max_yaw_rate_rad_s",
      gateway_limits_.max_yaw_rate_rad_s);
    gateway_limits_.future_stamp_tolerance_s = declare_parameter(
      "gateway.future_stamp_tolerance_s", gateway_limits_.future_stamp_tolerance_s);
    shadow_check_ = declare_parameter("gateway.shadow_check", true);
    heartbeat_max_age_s_ = declare_parameter("gateway.heartbeat_max_age_s", 0.25);
    state_rate_hz_ = declare_parameter("telemetry.state_rate_hz", 5.0);
    geofence_.configure(*this);
#ifdef GUARA_SIM_FAULT_INJECTION
    hang_decision_after_s_ = declare_parameter("fault_injection.hang_decision_after_s", -1.0);
    hang_ros_executor_after_s_ = declare_parameter("fault_injection.hang_ros_executor_after_s", -1.0);
    drop_local_position_after_s_ = declare_parameter("fault_injection.drop_local_position_after_s", -1.0);
#endif
  }

#ifdef GUARA_SIM_FAULT_INJECTION
  void noteCf(double t)
  {
    std::int64_t expected = 0;
    const auto ns = static_cast<std::int64_t>(t * 1e9);
    t_cf_ns_.compare_exchange_strong(expected, ns);
  }

  bool pastCfDelay(double delay_s) const
  {
    const std::int64_t cf = t_cf_ns_.load();
    if (cf <= 0 || delay_s < 0.0) {
      return false;
    }
    return steadyNanoseconds() - cf > static_cast<std::int64_t>(delay_s * 1e9);
  }

  [[noreturn]] static void hangForever(const char * what)
  {
    RCLCPP_WARN(rclcpp::get_logger("guara_rta"), "fault injection: %s", what);
    for (;;) {
      std::this_thread::sleep_for(std::chrono::seconds(1));
    }
  }

  void maybeHangRosExecutor()
  {
    if (shared_.in_charge.load() && shared_.owned_mode_active.load()) {
      noteCf(steadySeconds());
    }
    if (pastCfDelay(hang_ros_executor_after_s_)) {
      hangForever("ROS executor hang");
    }
  }
#endif

  void onLocalPosition(const px4_msgs::msg::VehicleLocalPosition & msg)
  {
#ifdef GUARA_SIM_FAULT_INJECTION
    if (pastCfDelay(drop_local_position_after_s_)) {
      RCLCPP_WARN_ONCE(get_logger(), "fault injection: drop local position");
      return;
    }
#endif
    const double t = steadySeconds();
    const bool valid = msg.xy_valid && msg.z_valid && msg.v_xy_valid && msg.v_z_valid;
    inputs_->onReceive(Channel::kLocalPosition, t, valid);
    last_input_recv_s_ = t;
    const double ros_s = get_clock()->now().seconds();
    const double px4_s = static_cast<double>(msg.timestamp) * 1e-6;
    const double sample_s = static_cast<double>(msg.timestamp_sample) * 1e-6;
    l0_s_ = px4_s - sample_s;
    clock_err_s_ = ros_s - px4_s;
    t_ros_recv_s_ = ros_s;
    t_px4_timestamp_s_ = px4_s;
    t_input_stamp_s_ = sample_s;
    if (geofence_.enabled()) {
      const GeofenceSample s = geofence_.update(msg, valid);
      t_gf_s_ = s.t_gf_s;
      inputs_->onReceive(Channel::kGeofence, t, s.valid);
    }
  }

  void onVerdict(const guara_msgs::msg::MonitorVerdict & msg)
  {
    const double t = steadySeconds();
    const double ros_s = get_clock()->now().seconds();
    l2_s_ = msg.processing_s;
    const rclcpp::Time stamp(msg.stamp, get_clock()->get_clock_type());
    l3_s_ = ros_s - stamp.seconds();

    MonitorVerdictSample sample;
    sample.id = msg.monitor_id.c_str();
    sample.monitor_class = msg.monitor_class;
    sample.action = msg.action;
    sample.violated = msg.violated;
    sample.inputs_complete = msg.inputs_complete;
    const MonitorAccept accept = monitors_.observe(sample, t);
    // A malformed or undeliverable verdict is an invalid monitor input (review H-4, H-6); the table
    // records it and evaluate() reports it, so the arbiter still reacts.
    if (accept != MonitorAccept::kAccepted) {
      RCLCPP_ERROR_THROTTLE(get_logger(), *get_clock(), 5000,
        "monitor verdict from '%s' rejected (%s); monitor channel reported invalid",
        msg.monitor_id.c_str(),
        accept == MonitorAccept::kTableFull ? "table full" : "field out of contract");
    }
    inputs_->onReceive(Channel::kMonitor, t, accept == MonitorAccept::kAccepted);
    if (msg.violated && msg.monitor_class == guara_msgs::msg::MonitorVerdict::CLASS_SWITCH) {
      last_input_recv_s_ = t;
    }
  }

  void onAck(const px4_msgs::msg::VehicleCommandAck & msg)
  {
    if (msg.command != px4_msgs::msg::VehicleCommand::VEHICLE_CMD_SET_NAV_STATE ||
      msg.target_component != source_component_)
    {
      return;
    }
    const bool accepted = msg.result == px4_msgs::msg::VehicleCommandAck::VEHICLE_CMD_RESULT_ACCEPTED;
    // The acknowledgement does not carry the requested nav_state, so it is attributed to the pending
    // request; the *effect* is confirmed separately against vehicle_status.nav_state, and a request
    // that is accepted but never takes effect is failed by ActuatorLogic (review 2026-09-11 §4).
    actuator_->onAck(actuator_->pending(), accepted, steadySeconds());
  }

  void onTick()
  {
#ifdef GUARA_SIM_FAULT_INJECTION
    if (hang_decision_after_s_ >= 0.0 && pastCfDelay(hang_decision_after_s_)) {
      hangForever("decision thread hang");
    }
#endif
    const double t = steadySeconds();
    const std::int64_t t0_ns = steadyNanoseconds();

    Inputs in;
    in.t_s = t;
    in.in_charge = shared_.in_charge.load();
    in.owned_mode_active = shared_.owned_mode_active.load();
#ifdef GUARA_SIM_FAULT_INJECTION
    if (in.in_charge && in.owned_mode_active) {
      noteCf(t);
    }
#endif
    in.t_daa_s = input_config_[static_cast<std::size_t>(Channel::kDaa)].enabled ? t_daa_s_ : kInf;
    in.t_gf_s = geofence_.enabled() ? t_gf_s_ : kInf;
    std::uint32_t invalid = inputs_->invalidMask(t);

    const MonitorEvaluation monitors = monitors_.evaluate(t);
    first_violating_monitor_ = monitors.first_violating_id;
    in.monitor_violation = monitors.violation;
    in.monitor_action = monitors.action;
    if (monitors.invalid &&
      input_config_[static_cast<std::size_t>(Channel::kMonitor)].enabled)
    {
      invalid |= 1U << static_cast<unsigned>(Channel::kMonitor);
      if (monitors.first_invalid_id != nullptr) {
        RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 5000,
          "monitor '%s' missing, stale or incomplete: V(k) set", monitors.first_invalid_id);
      }
    }
    in.cf_intent_unsafe = cfIntentUnsafe(t);
    in.input_invalid = invalid != 0U;
    input_invalid_mask_ = invalid;

    const Output out = core_->step(in);
    const std::int64_t t1_ns = steadyNanoseconds();
    max_tick_s_ = std::max(max_tick_s_, static_cast<double>(t1_ns - t0_ns) * 1e-9);

    shared_.core_state.store(static_cast<std::uint8_t>(out.state));
    shared_.last_tick_ns.store(t1_ns);

    if (out.transition.id == transition::kT1) {
      actuator_->cancel();
    }
    actuator_->request(out.command, expectedNavState(out.command), t);
    actuate(t);

    if (out.transition.id != transition::kNone) {
      publishEvent(out.transition, in, t);
    }
    ++tick_;
    if (state_rate_hz_ > 0.0 && t - t_last_state_pub_s_ >= 1.0 / state_rate_hz_) {
      publishState(out, in, t);
    }
  }

  // nav_state the request must produce, for the effect confirmation of ActuatorLogic.
  std::uint8_t expectedNavState(Command c) const noexcept
  {
    if (c == Command::kOwnedMode) {
      return static_cast<std::uint8_t>(gateway_->id());
    }
    const px4_ros2::ModeBase::ModeID id = navStateFor(c);
    return id == px4_ros2::ModeBase::kModeIDInvalid ? kNavStateUnknown :
           static_cast<std::uint8_t>(id);
  }

  // Shadow check of the setpoint the CF is currently proposing (review 2026-09-11 §4). It only
  // withholds the return T5; while the vehicle is in CF the gateway already filters the setpoint.
  bool cfIntentUnsafe(double t)
  {
    if (!geofence_.enabled() || !shadow_check_) {
      return false;
    }
    const double t_recv_ros_s = shared_.cf_recv_s.load();
    const double age = get_clock()->now().seconds() - t_recv_ros_s;
    if (!std::isfinite(t_recv_ros_s) || age > cf_timeout_s_) {
      return false;  // no live CF proposal: nothing to shadow-check
    }
    const std::array<float, 3> v{shared_.cf_vx.load(), shared_.cf_vy.load(), shared_.cf_vz.load()};
    bool have_state = false;
    const double t_gf = geofence_.predictWithVelocity(v, &have_state);
    if (!have_state) {
      return false;  // the geofence channel is invalid; V(k) already covers it
    }
    cf_intent_t_gf_s_ = t_gf;
    (void)t;
    return t_gf <= params_.tau_gf_s + params_.h_gf_s;
  }

  void actuate(double t)
  {
    const Command pending = actuator_->pending();
    const ActuatorAction action = actuator_->tick(t);
    if (action == ActuatorAction::kPublish) {
      px4_msgs::msg::VehicleCommand cmd{};
      cmd.command = px4_msgs::msg::VehicleCommand::VEHICLE_CMD_SET_NAV_STATE;
      cmd.param1 = static_cast<float>(pending == Command::kOwnedMode ? gateway_->id() :
        navStateFor(pending));
      cmd.param2 = cmd.param3 = cmd.param4 = cmd.param5 = cmd.param6 = cmd.param7 = NAN;
      cmd.source_component = source_component_;
      cmd.timestamp = 0;  // set by PX4
      command_pub_->publish(cmd);
      t_last_cmd_pub_s_ = t;
      t_cmd_pub_ros_s_ = get_clock()->now().seconds();
    } else if (action == ActuatorAction::kFailed) {
      RCLCPP_ERROR(get_logger(),
        "mode request %s not accepted after %u publications, or accepted without taking effect "
        "within %.2f s (nav_state=%u)", toString(pending),
        static_cast<unsigned>(actuator_params_.n_retry), actuator_params_.confirm_timeout_s,
        static_cast<unsigned>(nav_state_));
      // The owned mode now fails its arming check, so PX4 falls back on its own (SPEC FM-7).
      shared_.actuation_failed.store(true);
      const Output latched = core_->latchOnActuationFailure(t);
      shared_.core_state.store(static_cast<std::uint8_t>(latched.state));
      if (latched.transition.id != transition::kNone) {
        Inputs none;
        none.t_daa_s = t_daa_s_;
        none.t_gf_s = t_gf_s_;
        publishEvent(latched.transition, none, t);
      }
    }
  }

  void publishEvent(const Transition & tr, const Inputs & in, double t)
  {
    guara_msgs::msg::RtaEvent ev;
    ev.tick = tick_;
    ev.transition = tr.id;
    ev.state_from = static_cast<std::uint8_t>(tr.from);
    ev.state_to = static_cast<std::uint8_t>(tr.to);
    ev.rf_from = static_cast<std::uint8_t>(tr.rf_from);
    ev.rf_to = static_cast<std::uint8_t>(tr.rf_to);
    ev.cause_mask = tr.cause;
    ev.t_decide_s = t;
    ev.t_input_recv_s = last_input_recv_s_;
    ev.t_input_stamp_s = t_input_stamp_s_;
    ev.t_px4_timestamp_s = t_px4_timestamp_s_;
    ev.t_ros_recv_s = t_ros_recv_s_;
    ev.t_cmd_pub_s = t_last_cmd_pub_s_;
    ev.t_cmd_pub_ros_s = t_cmd_pub_ros_s_;
    ev.t_ack_s = actuator_->lastAck();
    ev.l0_s = l0_s_;
    ev.clock_err_s = clock_err_s_;
    ev.l2_s = l2_s_;
    ev.l3_s = l3_s_;
    ev.t_daa_s = in.t_daa_s;
    ev.t_gf_s = in.t_gf_s;
    if (first_violating_monitor_ != nullptr && (tr.cause & cause::kMonitor) != 0U) {
      ev.monitor_id = first_violating_monitor_;
    }
    event_pub_->publish(ev);
    RCLCPP_INFO(get_logger(), "T%u %s/%s -> %s/%s cause=0x%x invalid=0x%x", tr.id, toString(tr.from),
      toString(tr.rf_from), toString(tr.to), toString(tr.rf_to), tr.cause, input_invalid_mask_);
  }

  void publishState(const Output & out, const Inputs & in, double t)
  {
    guara_msgs::msg::RtaState st;
    st.tick = tick_;
    st.t_s = t;
    st.state = static_cast<std::uint8_t>(out.state);
    st.rf = static_cast<std::uint8_t>(out.recovery);
    st.cause_mask = out.unsafe_causes;
    st.t_daa_s = in.t_daa_s;
    st.t_gf_s = in.t_gf_s;
    st.clear_duration_s = out.clear_duration_s;
    st.switches_in_window = out.switches_in_window;
    st.in_charge = in.in_charge;
    st.owned_mode_active = in.owned_mode_active;
    st.max_tick_duration_s = max_tick_s_;
    st.t_last_cmd_pub_s = t_last_cmd_pub_s_;
    st.t_last_ack_s = actuator_->lastAck();
    st.l0_s = l0_s_;
    st.clock_err_s = clock_err_s_;
    st.t_px4_timestamp_s = t_px4_timestamp_s_;
    st.t_ros_recv_s = t_ros_recv_s_;
    st.invalid_mask = input_invalid_mask_;
    st.nav_state = nav_state_;
    st.safety_profile = static_cast<std::uint8_t>(profile_);
    st.accepted_omissions = omissions_;
    st.actuation_failed = shared_.actuation_failed.load();
    st.cf_intent_unsafe = in.cf_intent_unsafe;
    st.cf_intent_t_gf_s = cf_intent_t_gf_s_;
    st.cf_rejected_stamp = shared_.cf_rejected_stamp.load();
    st.cf_rejected_non_finite = shared_.cf_rejected_non_finite.load();
    st.cf_rejected_guard = shared_.cf_rejected_guard.load();
    st.cf_clamped = shared_.cf_clamped.load();
    state_pub_->publish(st);
    t_last_state_pub_s_ = t;
  }

  SharedState shared_;
  Parameters params_;
  ActuatorParameters actuator_params_;
  InputManager::Config input_config_{};
  GeofenceChannel geofence_;
  MonitorTable monitors_;
  std::size_t expected_monitors_{0};
  SafetyProfile profile_{SafetyProfile::kFlight};
  std::uint32_t omissions_{0};
  GatewayLimits gateway_limits_{};
  bool shadow_check_{true};
  double period_s_{0.05};
  double cf_timeout_s_{0.5};
  double heartbeat_max_age_s_{0.25};
  double state_rate_hz_{5.0};
#ifdef GUARA_SIM_FAULT_INJECTION
  double hang_decision_after_s_{-1.0};
  double hang_ros_executor_after_s_{-1.0};
  double drop_local_position_after_s_{-1.0};
  std::atomic<std::int64_t> t_cf_ns_{0};
  rclcpp::TimerBase::SharedPtr fault_timer_;
#endif

  std::unique_ptr<DecisionCore> core_;
  std::unique_ptr<ActuatorLogic> actuator_;
  std::unique_ptr<InputManager> inputs_;
  std::unique_ptr<GuaraCfGateway> gateway_;
  std::unique_ptr<GuaraExecutor> executor_;
  std::unique_ptr<GeofenceSetpointGuard> guard_;
  std::uint16_t source_component_{0};

  rclcpp::CallbackGroup::SharedPtr decision_group_;
  rclcpp::Subscription<px4_msgs::msg::VehicleLocalPosition>::SharedPtr lpos_sub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleStatus>::SharedPtr status_sub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleCommandAck>::SharedPtr ack_sub_;
  rclcpp::Subscription<guara_msgs::msg::MonitorVerdict>::SharedPtr verdict_sub_;
  rclcpp::Subscription<guara_msgs::msg::DaaStatus>::SharedPtr daa_sub_;
  rclcpp::Publisher<px4_msgs::msg::VehicleCommand>::SharedPtr command_pub_;
  rclcpp::Publisher<guara_msgs::msg::RtaEvent>::SharedPtr event_pub_;
  rclcpp::Publisher<guara_msgs::msg::RtaState>::SharedPtr state_pub_;
  rclcpp::TimerBase::SharedPtr decision_timer_;

  const char * first_violating_monitor_{nullptr};
  double t_daa_s_{kInf};
  double t_gf_s_{kInf};
  double cf_intent_t_gf_s_{kInf};
  double last_input_recv_s_{std::numeric_limits<double>::quiet_NaN()};
  double t_last_cmd_pub_s_{std::numeric_limits<double>::quiet_NaN()};
  double t_cmd_pub_ros_s_{std::numeric_limits<double>::quiet_NaN()};
  double t_input_stamp_s_{std::numeric_limits<double>::quiet_NaN()};
  double t_px4_timestamp_s_{std::numeric_limits<double>::quiet_NaN()};
  double t_ros_recv_s_{std::numeric_limits<double>::quiet_NaN()};
  double l0_s_{std::numeric_limits<double>::quiet_NaN()};
  double clock_err_s_{std::numeric_limits<double>::quiet_NaN()};
  double l2_s_{std::numeric_limits<double>::quiet_NaN()};
  double l3_s_{std::numeric_limits<double>::quiet_NaN()};
  double t_last_state_pub_s_{-kInf};
  double t_start_s_{0.0};
  double max_tick_s_{0.0};
  std::uint32_t input_invalid_mask_{0};
  std::uint8_t nav_state_{0};
  std::uint64_t tick_{0};
};

}  // namespace
}  // namespace guara_rta

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<guara_rta::ArbiterNode>();
  rclcpp::executors::MultiThreadedExecutor executor(rclcpp::ExecutorOptions(), 2);
  executor.add_node(node);
  executor.spin();
  rclcpp::shutdown();
  return 0;
}
