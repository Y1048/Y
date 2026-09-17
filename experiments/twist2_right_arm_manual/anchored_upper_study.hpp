// Relative-input OFFLINE STUDY. No native integration.
#pragma once
#include "upper_target_offline.hpp"
#include <algorithm>
#include <optional>

// Memory-only candidate study. No transport, policy, SDK or physical output.
// Single caller; receipt and tick times share one simulated monotonic clock.
class AnchoredUpperStudy
{
    InputValidator validator;
    std::optional<std::array<double,7>> anchor;
    std::array<double, 29> captured;
    std::array<double, 29> target;
    double last_tick;
    double maximum_delta;
    std::optional<double> last_received;
    std::string reason;
    std::optional<std::array<double, 7>> tick_goal;

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
    bool BindCommandReference(const std::array<double,29>& reference) {
        if(anchor || !reason.empty())return false;
        for(std::size_t i=0;i<7;++i)
            if(!std::isfinite(reference[i+22]) || reference[i+22]<lower[i]+.05 || reference[i+22]>upper[i]-.05)return false;
        // Policy legs and captured waist/left arm remain owned by their original path.
        for(std::size_t i=22;i<29;++i)captured[i]=target[i]=reference[i];
        return true;
    }
    AnchoredUpperStudy(const std::array<double, 29>& baseline,
                       double now, double maximum_delta_rad)
        : captured(baseline), target(baseline), last_tick(now),
          maximum_delta(maximum_delta_rad)
    {
        if (!std::isfinite(now) || now < 0 || !std::isfinite(maximum_delta)
            || maximum_delta <= 0)
            throw std::invalid_argument("invalid_study_parameters");
        for (double q : baseline)
            if (!std::isfinite(q)) throw std::invalid_argument("invalid_baseline");
        for (std::size_t i = 0; i < 7; ++i)
            if (baseline[i + 22] < lower[i]+.05 || baseline[i + 22] > upper[i]-.05)
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
        if (packets.empty()) return "waiting";
        std::array<double, 7> arm{};
        bool active = false;
        const bool first_tick = !anchor;
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
            // Raw packets have passed the unchanged validator. Map only numeric goals.
            if (!anchor) anchor=arm;
            for (std::size_t i = 0; i < 7; ++i)
            {
                if (arm[i] < lower[i]+.05 || arm[i] > upper[i]-.05) return Stop("right_arm_joint_limit");
                const double delta=arm[i]-(*anchor)[i];
                if (std::abs(delta) > maximum_delta) return Stop("start_relative_limit");
                arm[i]=captured[i+22]+delta;
                if (arm[i] < lower[i]+.05 || arm[i] > upper[i]-.05) return Stop("mapped_joint_limit");
            }
            active = true;
        }
        if (!active) return "waiting";
        if(first_tick){tick_goal=arm;return "active";} // Anchor only; no first-tick command change.
        auto next = target;
        const double step = 0.08 * dt;
        for (std::size_t i = 0; i < 7; ++i)
        {
            const double difference = arm[i] - target[i + 22];
            // Assign the goal exactly on the last step, without overshooting.
            next[i + 22] = std::abs(difference) <= step ? arm[i]
                : target[i + 22] + std::copysign(step, difference);
        }
        tick_goal = arm;
        target = next;
        return "active";
    }
};
