#pragma once
#include "upper_target_offline.hpp"

// Position-only composition study. Caller supplies snapshots in motor order.
// No LowState subscriber, policy execution, torque/gain command or publisher.
struct OfflineStateSample
{
    std::array<double, 29> q;
    std::array<double, 29> dq;
    std::uint64_t sequence;
    double received_at;
};

struct CompositionLimits
{
    double state_age;
    double settle_seconds;
    double settle_velocity;
    double settle_drift;
    double initial_arm_error;
    double tracking_error;
    double maximum_arm_delta;
};

class MeasuredCompositionOffline
{
    CompositionLimits limits;
    std::optional<OfflineStateSample> last_state;
    std::optional<OfflineStateSample> settle_start;
    std::optional<std::array<double, 29>> baseline;
    std::optional<UpperTargetOffline> upper;
    InputValidator alignment_validator;
    bool aligned = false;
    bool allow_unaligned_candidate = false;
    std::optional<double> last_input_time;
    double last_tick = 0;
    std::string reason;
    std::optional<std::array<double, 29>> candidate;

    std::string Stop(const std::string& error)
    {
        if (reason.empty()) reason = error;
        candidate.reset();
        return "stopped";
    }

public:
    explicit MeasuredCompositionOffline(CompositionLimits settings, bool prealignment=false) : limits(settings),allow_unaligned_candidate(prealignment)
    {
        for (double value : {limits.state_age, limits.settle_seconds, limits.settle_velocity,
             limits.settle_drift, limits.initial_arm_error, limits.tracking_error,
             limits.maximum_arm_delta})
            if (!std::isfinite(value) || value <= 0) throw std::invalid_argument("invalid_limits");
    }
    const auto& Candidate() const { return candidate; }
    const auto& Baseline() const { return baseline; }
    const auto& Reason() const { return reason; }

    // leg_q is already decoded absolute radians for motor indices 0..11.
    // It is NOT the raw/reordered/scaled policy action tensor.
    std::string Tick(const std::optional<OfflineStateSample>& state,
                     const std::array<double, 12>& leg_q,
                     const std::vector<ReceivedInput>& packets, double now)
    {
        candidate.reset();
        if (!reason.empty()) return "stopped";
        if (!std::isfinite(now) || now <= last_tick) return Stop("invalid_tick_clock");
        const double previous_tick = last_tick;
        last_tick = now;
        if (!state) return Stop("missing_state");
        if (!std::isfinite(state->received_at) || state->received_at < 0
            || state->received_at > now || now - state->received_at > limits.state_age)
            return Stop("stale_or_invalid_state_time");
        if (last_state && (state->sequence <= last_state->sequence
            || state->received_at <= last_state->received_at
            || state->received_at - last_state->received_at > limits.state_age))
            return Stop("state_discontinuity");
        for (std::size_t i = 0; i < 29; ++i)
            if (!std::isfinite(state->q[i]) || !std::isfinite(state->dq[i]))
                return Stop("invalid_state_number");
        for (double q : leg_q)
            if (!std::isfinite(q)) return Stop("invalid_policy_position");
        if (packets.size() > 64) return Stop("input_batch_overflow");
        for (const auto& packet : packets)
        {
            if (packet.payload.size() > 16384 || !std::isfinite(packet.received_at)
                || packet.received_at < 0 || packet.received_at > now
                || (last_input_time && packet.received_at < *last_input_time))
                return Stop("invalid_input_envelope");
            last_input_time = packet.received_at;
        }
        last_state = state;
        if (!baseline)
        {
            bool stable = true;
            for (std::size_t i = 0; i < 29; ++i)
                if (std::abs(state->dq[i]) > limits.settle_velocity
                    || (settle_start && std::abs(state->q[i] - settle_start->q[i]) > limits.settle_drift))
                    stable = false;
            if (!stable) { settle_start.reset(); return "settling"; }
            if (!settle_start) settle_start = state;
            if (state->received_at - settle_start->received_at < limits.settle_seconds)
                return "settling";
            try { upper.emplace(state->q, previous_tick, limits.maximum_arm_delta); }
            catch (const std::exception& error) { return Stop(error.what()); }
            baseline = state->q;
        }
        // Monitor captured waist/left arm and the previously applied right candidate.
        for (std::size_t i = 12; i < 29; ++i)
            if (std::abs(state->q[i] - upper->Target()[i]) > limits.tracking_error)
                return Stop("upper_tracking_error");
        std::size_t first_active = 0;
        if (!aligned)
        {
            for (const auto& packet : packets)
            {
                std::array<double, 7> goal{};
                const auto status = alignment_validator.Validate(packet.payload, now, &goal,
                                                                  packet.received_at, nullptr, true);
                if (status == "waiting") { ++first_active; continue; }
                if (!status.empty()) return Stop(status);
                for (std::size_t i = 0; i < 7; ++i)
                    if (std::abs(goal[i] - state->q[i + 22]) > limits.initial_arm_error)
                        return Stop("initial_arm_mismatch");
                aligned = true;
                break;
            }
            if (!aligned) {
                if(allow_unaligned_candidate){auto next=upper->Target();
                    std::copy(leg_q.begin(),leg_q.end(),next.begin());candidate=next;}
                return "awaiting_alignment";
            }
        }
        const std::vector<ReceivedInput> active_batch(
            packets.begin() + static_cast<std::ptrdiff_t>(first_active), packets.end());
        const auto mode = upper->Tick(active_batch, now);
        if (mode == "stopped") return Stop(upper->Reason());
        auto next = upper->Target();
        std::copy(leg_q.begin(), leg_q.end(), next.begin());
        candidate = next;
        return mode;
    }
};
