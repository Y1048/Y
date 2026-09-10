#pragma once
#include "vendor/json.hpp"
#include <cmath>
#include <array>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>

class InputValidator
{
    bool started = false;
    std::string session;
    std::uint64_t sequence = 0;
    double receipt = 0;
    std::optional<double> last_clock;
    std::string reason;

    static double GetNumber(const nlohmann::json& value)
    {
        if (!value.is_number() || !std::isfinite(value.get<double>()))
            throw std::runtime_error("invalid_number");
        return value.get<double>();
    }

    static std::string TrimSession(const std::string& value)
    {
        // Match Python strip for the ASCII session IDs emitted by Mink.
        const auto begin = value.find_first_not_of(" \t\r\n\v\f");
        if (begin == std::string::npos) return "";
        return value.substr(begin, value.find_last_not_of(" \t\r\n\v\f") - begin + 1);
    }

public:
    std::string CheckTimeout(double now)
    {
        if (reason.empty())
        {
            if (!std::isfinite(now) || now < 0 || (last_clock && now < *last_clock))
                reason = "invalid_clock";
            else
            {
                last_clock = now;
                if (started && now - receipt > 0.25) reason = "receiver_timeout";
            }
        }
        return reason;
    }

    // Write targets only after the entire packet has passed validation.
    std::string Validate(const std::string& payload, double now,
                         std::array<double, 7>* validated_arm = nullptr,
                         std::optional<double> received_at = std::nullopt,
                         std::array<double, 29>* validated_all = nullptr,
                         bool wait_for_first_active = false)
    {
        if (!CheckTimeout(now).empty()) return reason;
        try
        {
            const double received = received_at.value_or(now);
            if (!std::isfinite(now) || now < 0)
                throw std::runtime_error("invalid_clock");
            if (!std::isfinite(received) || received < 0 || received > now
                || (started && received < receipt))
                throw std::runtime_error("invalid_receipt_time");
            std::vector<std::set<std::string>> keys;
            auto callback = [&keys](int, nlohmann::json::parse_event_t event, nlohmann::json& item)
            {
                if (event == nlohmann::json::parse_event_t::object_start) keys.emplace_back();
                if (event == nlohmann::json::parse_event_t::key
                    && !keys.back().insert(item.get<std::string>()).second)
                    throw std::runtime_error("duplicate_key");
                if (event == nlohmann::json::parse_event_t::object_end) keys.pop_back();
                return true;
            };
            auto value = nlohmann::json::parse(payload, callback);
            if (!value.is_object()) throw std::runtime_error("invalid_root");
            if (value.at("schema") != "g1.mink.right_arm.state.v1"
                || value.at("state_source") != "mink_simulation")
                throw std::runtime_error("invalid_source");
            const auto& number = value.at("sequence");
            if (!number.is_number_integer() || number < 0)
                throw std::runtime_error("invalid_sequence");
            auto next = number.get<std::uint64_t>();
            const auto& q = value.at("all_joint_q_rad");
            const std::vector<std::string> names = {
                "left_hip_pitch", "left_hip_roll", "left_hip_yaw", "left_knee", "left_ankle_pitch", "left_ankle_roll",
                "right_hip_pitch", "right_hip_roll", "right_hip_yaw", "right_knee", "right_ankle_pitch", "right_ankle_roll",
                "waist_yaw", "waist_roll", "waist_pitch", "left_shoulder_pitch", "left_shoulder_roll", "left_shoulder_yaw",
                "left_elbow", "left_wrist_roll", "left_wrist_pitch", "left_wrist_yaw", "right_shoulder_pitch",
                "right_shoulder_roll", "right_shoulder_yaw", "right_elbow", "right_wrist_roll", "right_wrist_pitch", "right_wrist_yaw"};
            if (value.at("all_joint_names") != nlohmann::json(names))
                throw std::runtime_error("joint_order");
            const auto& right = value.at("right_arm");
            if (!right.is_object()) throw std::runtime_error("invalid_right_arm");
            const auto& arm = right.at("joints");
            if (!q.is_array() || q.size() != 29 || !arm.is_array() || arm.size() != 7)
                throw std::runtime_error("joint_count");
            for (const auto& angle : q) GetNumber(angle);
            for (int index = 0; index < 7; ++index)
                if (std::abs(GetNumber(arm[index]) - GetNumber(q[index + 22])) > 1e-7)
                    throw std::runtime_error("joint_mismatch");
            if (!right.at("active").is_boolean()) throw std::runtime_error("invalid_active");
            if (!right.at("workspace_limited").is_boolean()
                || !right.at("collision_limited").is_boolean())
                throw std::runtime_error("invalid_limit_flags");
            for (const char* name : {"nearest_collision_geoms", "nearest_collision_bodies"})
            {
                if (!right.contains(name)) continue;
                const auto& items = right.at(name);
                if (!items.is_array()) throw std::runtime_error("invalid_collision_names");
                for (const auto& item : items)
                    if (!item.is_string()) throw std::runtime_error("invalid_collision_names");
            }
            // Timestamp is schema data, never compared to the local monotonic clock.
            GetNumber(value.at("timestamp"));
            const auto mode = value.at("input_command_mode").get<std::string>();
            const auto state = right.at("command_state").get<std::string>();
            const std::set<std::string> modes =
                {"active", "idle", "workspace_exit", "pinch_disengaged", "tracking_disengaged"};
            const std::set<std::string> states = {"active", "hold", "idle", "workspace_fault"};
            if (modes.count(mode) == 0 || states.count(state) == 0)
                throw std::runtime_error("invalid_command_state");
            const bool active = right.at("active").get<bool>();
            if (active != (state == "active")) throw std::runtime_error("active_state_mismatch");

            std::string identity;
            if (value.contains("session_id") && !value.at("session_id").is_null())
            {
                identity = TrimSession(value.at("session_id").get<std::string>());
                if (identity.empty()) throw std::runtime_error("invalid_session");
            }
            std::optional<double> age;
            if (value.contains("input_packet_age_s") && !value.at("input_packet_age_s").is_null())
            {
                age = GetNumber(value.at("input_packet_age_s"));
                if (*age < 0) throw std::runtime_error("source_timeout");
            }
            std::optional<double> clearance;
            if (right.contains("minimum_clearance_m") && !right.at("minimum_clearance_m").is_null())
                clearance = GetNumber(right.at("minimum_clearance_m"));
            if (active && (identity.empty() || !age || !clearance))
                throw std::runtime_error("missing_active_metadata");
            // Idle still validates all supplied metadata before waiting.
            if (!started && mode == "idle" && !active && state == "idle") return "waiting";
            // A fresh simulation-baseline session may observe the previous
            // sender session's inactive state. Never use this after engagement.
            if (wait_for_first_active && !started && mode != "active" && !active) return "waiting";
            if (mode != "active" || !active) throw std::runtime_error("input_disengaged");
            if (started && (identity != session || next <= sequence))
                throw std::runtime_error("session_or_sequence");
            if (*age + (now - received) > 0.25)
                throw std::runtime_error("source_timeout");
            if (*clearance < 0) throw std::runtime_error("negative_clearance");
            session = identity;
            sequence = next;
            receipt = received;
            started = true;
            if (validated_arm)
                for (int i = 0; i < 7; ++i) (*validated_arm)[i] = GetNumber(arm[i]);
            if (validated_all)
                for (int i = 0; i < 29; ++i) (*validated_all)[i] = GetNumber(q[i]);
            return "";
        }
        catch (const nlohmann::json::parse_error&)
        {
            // Parser diagnostics can contain invalid UTF-8 from the datagram.
            // Raw bytes are preserved separately; the latch remains JSON-safe.
            reason = "parse_error";
            return reason;
        }
        catch (const std::exception& error)
        {
            reason = error.what();
            return reason;
        }
    }
};
