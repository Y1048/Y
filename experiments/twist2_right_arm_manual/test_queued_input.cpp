#include "queued_input_offline.hpp"
#include <iostream>

double TimeValue(const nlohmann::json& value)
{
    return value.is_string() ? std::stod(value.get<std::string>()) : value.get<double>();
}

// Deterministic queue tests, no sockets or real-time sleeps.
int main()
{
    try
    {
        std::string line;
        if (!std::getline(std::cin, line)) return 2;
        const auto config = nlohmann::json::parse(line);
        std::optional<std::array<double, 29>> q;
        if (!config.at("baseline").is_null())
        {
            const auto baseline = config.at("baseline").get<std::vector<double>>();
            if (baseline.size() != 29) throw std::invalid_argument("baseline_count");
            q.emplace();
            std::copy(baseline.begin(), baseline.end(), q->begin());
        }
        QueuedInputOffline queue(q, 0, config.at("maximum_delta"), config.at("capacity"));
        while (std::getline(std::cin, line))
        {
            const auto event = nlohmann::json::parse(line);
            std::string mode;
            if (event.at("op") == "push")
            {
                std::string payload;
                if (event.contains("payload_hex"))
                {
                    const auto hex = event.at("payload_hex").get<std::string>();
                    if (hex.size() % 2) throw std::invalid_argument("invalid_hex");
                    for (std::size_t i = 0; i < hex.size(); i += 2)
                    {
                        const auto pair = hex.substr(i, 2);
                        if (pair.find_first_not_of("0123456789abcdef") != std::string::npos)
                            throw std::invalid_argument("invalid_hex");
                        payload.push_back(static_cast<char>(std::stoi(pair, nullptr, 16)));
                    }
                }
                else payload = event.at("payload").get<std::string>();
                mode = queue.Enqueue(payload, TimeValue(event.at("at"))) ? "queued" : "stopped";
            }
            else if (event.at("op") == "stop")
            {
                queue.Stop(event.at("reason"));
                mode = "stopped";
            }
            else if (event.at("op") == "tick") mode = queue.Tick(TimeValue(event.at("at")));
            else throw std::invalid_argument("unknown_operation");
            std::cout << nlohmann::json({{"mode", mode}, {"reason", queue.Reason()},
                {"q", queue.HasBaseline() ? nlohmann::json(queue.Target()) : nlohmann::json(nullptr)},
                {"baseline", queue.Baseline() ? nlohmann::json(*queue.Baseline()) : nlohmann::json(nullptr)},
                {"validated_goal", queue.Goal() ? nlohmann::json(*queue.Goal()) : nlohmann::json(nullptr)},
                {"depth", queue.Depth()}, {"peak", queue.Peak()}}).dump()
                << std::endl;
        }
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << std::endl;
        return 2;
    }
}
