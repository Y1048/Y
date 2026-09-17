#include "measured_composition_offline.hpp"
#include <iostream>

int main()
{
    try
    {
        std::string line;
        std::getline(std::cin, line);
        const auto c = nlohmann::json::parse(line);
        MeasuredCompositionOffline study({c.at("state_age"), c.at("settle_seconds"),
            c.at("settle_velocity"), c.at("settle_drift"), c.at("initial_arm_error"),
            c.at("tracking_error"), c.at("maximum_arm_delta")});
        while (std::getline(std::cin, line))
        {
            const auto e = nlohmann::json::parse(line);
            std::optional<OfflineStateSample> state;
            if (!e.at("state").is_null())
            {
                const auto& v = e.at("state");
                if (v.at("q").size() != 29 || v.at("dq").size() != 29)
                    throw std::invalid_argument("state_count");
                state = OfflineStateSample{v.at("q").get<std::array<double, 29>>(),
                    v.at("dq").get<std::array<double, 29>>(), v.at("sequence"), v.at("received_at")};
            }
            if (e.at("legs").size() != 12) throw std::invalid_argument("leg_count");
            std::vector<ReceivedInput> packets;
            for (const auto& p : e.at("packets")) packets.push_back({p.at("payload"), p.at("at")});
            const auto mode = study.Tick(state, e.at("legs").get<std::array<double, 12>>(), packets, e.at("now"));
            std::cout << nlohmann::json({{"mode",mode},{"reason",study.Reason()},
                {"candidate",study.Candidate() ? nlohmann::json(*study.Candidate()) : nlohmann::json(nullptr)},
                {"baseline",study.Baseline() ? nlohmann::json(*study.Baseline()) : nlohmann::json(nullptr)},
                {"hardware_output_authorized",false}}).dump() << std::endl;
        }
    }
    catch (const std::exception& error) { std::cerr << error.what(); return 2; }
}
