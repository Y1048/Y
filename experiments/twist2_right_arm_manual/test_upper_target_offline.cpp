#include "upper_target_offline.hpp"
#include <iostream>

double ClockValue(const nlohmann::json& value)
{
    return value.is_string() ? std::stod(value.get<std::string>()) : value.get<double>();
}

// stdin/stdout only: first line config, subsequent lines simulated input ticks.
int main()
{
    try
    {
        std::string line;
        if (!std::getline(std::cin, line)) return 2;
        const auto config = nlohmann::json::parse(line);
        const auto baseline = config.at("baseline").get<std::vector<double>>();
        if (baseline.size() != 29) throw std::invalid_argument("baseline_count");
        std::array<double, 29> q{};
        std::copy(baseline.begin(), baseline.end(), q.begin());
        UpperTargetOffline study(q, config.at("now"), config.at("maximum_delta"));
        while (std::getline(std::cin, line))
        {
            const auto event = nlohmann::json::parse(line);
            const std::optional<std::string> payload = event.contains("payload")
                ? std::make_optional(event.at("payload").get<std::string>()) : std::nullopt;
            // Named nonfinite clocks let strict JSON fixtures exercise the C++ API.
            const double now = ClockValue(event.at("now"));
            std::string mode;
            if (event.contains("packets"))
            {
                if (payload) throw std::invalid_argument("ambiguous_tick_input");
                std::vector<ReceivedInput> packets;
                for (const auto& packet : event.at("packets"))
                    packets.push_back({packet.at("payload").get<std::string>(),
                                       ClockValue(packet.at("received_at"))});
                mode = study.Tick(packets, now);
            }
            else mode = study.Step(payload, now);
            std::cout << nlohmann::json({{"mode", mode}, {"reason", study.Reason()},
                {"q", study.Target()}, {"offline_only", true},
                {"hardware_output_authorized", false}}).dump() << std::endl;
        }
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << std::endl;
        return 2;
    }
}
