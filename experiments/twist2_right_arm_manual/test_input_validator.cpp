#include "validate_input.hpp"
#include <iostream>
int main()
{
    InputValidator validator;
    std::string line;
    while (std::getline(std::cin, line))
    {
        auto envelope = nlohmann::json::parse(line);
        const auto& time = envelope.at("now");
        double now = time.is_string() ? std::stod(time.get<std::string>()) : time.get<double>();
        auto reason = envelope.contains("payload")
            ? validator.Validate(envelope.at("payload").get<std::string>(), now)
            : validator.CheckTimeout(now);
        std::cout << (reason.empty() ? "ok" : reason == "waiting" ? "waiting" : "stopped") << std::endl;
    }
}
