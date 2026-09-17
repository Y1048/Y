#pragma once
#include "upper_target_offline.hpp"
#include <vector>

// Single-owner queue: Enqueue, Tick and Stop must run on the same event loop.
// No background worker, locks, transport or robot commands in this class.
class QueuedInputOffline
{
    std::optional<UpperTargetOffline> study;
    InputValidator bootstrap;
    std::optional<std::array<double, 29>> baseline;
    std::vector<ReceivedInput> pending;
    std::size_t capacity;
    std::size_t peak = 0;
    double last_received;
    double last_tick;
    double maximum_delta;
    std::string reason;

public:
    static constexpr std::size_t kMaximumCapacity = 64;
    static constexpr std::size_t kMaximumPayloadBytes = 16384;

    QueuedInputOffline(std::optional<std::array<double, 29>> initial_baseline, double now,
                       double maximum_delta_rad, std::size_t queue_capacity = kMaximumCapacity)
        : baseline(initial_baseline), capacity(queue_capacity), last_received(now),
          last_tick(now), maximum_delta(maximum_delta_rad)
    {
        if (capacity == 0 || capacity > kMaximumCapacity)
            throw std::invalid_argument("invalid_queue_capacity");
        if (!std::isfinite(now) || now < 0 || !std::isfinite(maximum_delta) || maximum_delta <= 0)
            throw std::invalid_argument("invalid_study_parameters");
        if (baseline) study.emplace(*baseline, now, maximum_delta);
        pending.reserve(capacity);
    }

    bool HasBaseline() const { return study.has_value(); }
    const std::optional<std::array<double, 29>>& Baseline() const { return baseline; }
    const std::array<double, 29>& Target() const { return study.value().Target(); }
    std::optional<std::array<double, 7>> Goal() const
    { return reason.empty() && study ? study->Goal() : std::nullopt; }
    const std::string& Reason() const { return reason; }
    std::size_t Depth() const { return pending.size(); }
    std::size_t Peak() const { return peak; }

    void Stop(const std::string& error)
    {
        if (reason.empty()) reason = error.empty() ? "external_stop" : error;
        pending.clear();
    }

    bool Enqueue(std::string payload, double received_at)
    {
        if (!reason.empty()) return false;
        if (!std::isfinite(received_at) || received_at < last_received)
        {
            Stop("invalid_receipt_time");
            return false;
        }
        if (payload.size() > kMaximumPayloadBytes)
        {
            Stop("datagram_too_large");
            return false;
        }
        if (pending.size() == capacity)
        {
            // Never drop oldest/newest and continue: a discarded release matters.
            Stop("queue_overflow");
            return false;
        }
        pending.push_back({std::move(payload), received_at});
        last_received = received_at;
        peak = std::max(peak, pending.size());
        return true;
    }

    std::string Tick(double now)
    {
        if (!reason.empty()) return "stopped";
        if (!std::isfinite(now) || now <= last_tick)
        {
            Stop("non_increasing_clock");
            return "stopped";
        }
        const double previous_tick = last_tick;
        last_tick = now;
        if (!study)
        {
            for (std::size_t i = 0; i < pending.size(); ++i)
            {
                std::array<double, 29> captured{};
                const auto status = bootstrap.Validate(pending[i].payload, now, nullptr,
                                                       pending[i].received_at, &captured, true);
                if (status == "waiting") continue;
                if (!status.empty()) { Stop(status); return "stopped"; }
                try { study.emplace(captured, previous_tick, maximum_delta); }
                catch (const std::exception& error) { Stop(error.what()); return "stopped"; }
                baseline = captured;
                // Discard only already-validated idle packets. The first active
                // and all later packets still undergo full atomic tick checks.
                pending.erase(pending.begin(), pending.begin() + static_cast<std::ptrdiff_t>(i));
                break;
            }
            if (!study) { pending.clear(); return "waiting"; }
        }
        const auto mode = study->Tick(pending, now);
        pending.clear();
        if (mode == "stopped") Stop(study->Reason());
        return mode;
    }
};
