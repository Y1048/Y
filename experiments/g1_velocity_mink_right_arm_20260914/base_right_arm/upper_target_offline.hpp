#pragma once
#include "validate_input.hpp"
#include <algorithm>
#include <optional>

// Memory-only candidate study. No transport, policy, SDK or physical output.
// Single caller; receipt and tick times share one simulated monotonic clock.
struct ReceivedInput
{
    std::string payload;
    double received_at;
};

class UpperTargetOffline
{
    InputValidator validator;
    std::array<double, 29> captured;
    std::array<double, 29> target;
    double last_tick;
    double maximum_delta;
    double speed_limit,acceleration_limit;
    std::array<double,7> velocity{};
    std::optional<double> last_received;
    std::string reason;
    std::optional<std::array<double, 7>> tick_goal;
    std::optional<std::array<double,7>> held_goal;
    double held_deadline=0;

    // Same model limits as arm_sdk_hold_contract.RIGHT_ARM_LIMITS_RAD.
    inline static constexpr std::array<double, 7> lower =
        {-3.0892, -2.2515, -2.6180, -1.0472, -1.97222, -1.61443, -1.61443};
    inline static constexpr std::array<double, 7> upper =
        {2.6704, 1.5882, 2.6180, 2.0944, 1.97222, 1.61443, 1.61443};

    std::string Stop(const std::string& error)
    {
        reason = error;
        return "stopped";
    }

public:
    UpperTargetOffline(const std::array<double, 29>& baseline,
                       double now, double maximum_delta_rad,
                       double speed=.08,double acceleration=0)
        : captured(baseline), target(baseline), last_tick(now),
          maximum_delta(maximum_delta_rad),speed_limit(speed),acceleration_limit(acceleration)
    {
        if (!std::isfinite(now) || now < 0 || !std::isfinite(maximum_delta)
            || maximum_delta <= 0 || !std::isfinite(speed) || speed<=0
            || !std::isfinite(acceleration) || acceleration<0)
            throw std::invalid_argument("invalid_study_parameters");
        for (double q : baseline)
            if (!std::isfinite(q)) throw std::invalid_argument("invalid_baseline");
        for (std::size_t i = 0; i < 7; ++i)
            if (baseline[i + 22] < lower[i] || baseline[i + 22] > upper[i])
                throw std::invalid_argument("baseline_joint_limit");
    }

    const std::array<double, 29>& Target() const { return target; }
    const std::optional<std::array<double, 7>>& Goal() const { return tick_goal; }
    const std::string& Reason() const { return reason; }

    // Missing packets freeze immediately. Timeout/errors latch until a new study.
    // New active packets alone move the candidate, at <= 0.08 rad/s, dt <= 20 ms.
    std::string Step(const std::optional<std::string>& payload, double now)
    {
        return Tick(payload ? std::vector<ReceivedInput>{{*payload, now}}
                            : std::vector<ReceivedInput>{}, now);
    }

    // Caller supplies every queued packet in receipt order, including releases.
    // Validate the whole batch before moving once toward its latest active goal.
    // Do not coalesce packets before validation: that could hide a stop event.
    std::string Tick(const std::vector<ReceivedInput>& packets, double now)
    {
        tick_goal.reset();
        if (!reason.empty()) return "stopped";
        if (!std::isfinite(now) || now <= last_tick) return Stop("non_increasing_clock");
        const double dt = std::min(now - last_tick, 0.02);
        last_tick = now;
        const auto timeout = validator.CheckTimeout(now);
        if (!timeout.empty()) return Stop(timeout);
        if (packets.empty() && !(acceleration_limit>0 && held_goal)) return "waiting";
        std::array<double, 7> arm{};
        bool active = false;
        for (const auto& packet : packets)
        {
            if (!std::isfinite(packet.received_at) || packet.received_at < 0
                || packet.received_at > now
                || (last_received && packet.received_at < *last_received))
                return Stop("invalid_receipt_time");
            const auto status = validator.Validate(packet.payload, now, &arm, packet.received_at);
            if (!status.empty() && status != "waiting") return Stop(status);
            last_received = packet.received_at;
            if (status == "waiting") continue;
            // Validate every packet, not just the latest goal in this tick.
            for (std::size_t i = 0; i < 7; ++i)
            {
                if (arm[i] < lower[i] || arm[i] > upper[i]) return Stop("right_arm_joint_limit");
                if (std::abs(arm[i] - captured[i + 22]) > maximum_delta)
                    return Stop("start_relative_limit");
            }
            active = true;
            if(acceleration_limit>0){
                held_goal=arm;
                held_deadline=packet.received_at+.25-
                    nlohmann::json::parse(packet.payload).at("input_packet_age_s").get<double>();
            }
        }
        if(acceleration_limit>0 && held_goal){
            if(now>held_deadline)return Stop("source_timeout");
            arm=*held_goal;active=true;
        }
        if (!active) return "waiting";
        auto next = target;
        const double step = speed_limit * dt;
        for (std::size_t i = 0; i < 7; ++i)
        {
            const double difference = arm[i] - target[i + 22];
            if(acceleration_limit>0){
                const double a=acceleration_limit,ad=a*dt;
                // Discrete stopping-distance envelope; changing goals may be
                // passed while braking. Stop/error freezes take priority.
                const double braking=std::sqrt(ad*ad+2*a*std::abs(difference))-ad;
                const double desired=std::copysign(std::min(speed_limit,braking),difference);
                velocity[i]+=std::clamp(desired-velocity[i],-ad,ad);
                next[i+22]=target[i+22]+velocity[i]*dt;
                if(next[i+22]<lower[i]||next[i+22]>upper[i])return Stop("limited_target_joint_limit");
                continue;
            }
            // Assign the goal exactly on the last step, without overshooting.
            next[i + 22] = std::abs(difference) <= step ? arm[i]
                : target[i + 22] + std::copysign(step, difference);
        }
        tick_goal = arm;
        target = next;
        return "active";
    }
};

