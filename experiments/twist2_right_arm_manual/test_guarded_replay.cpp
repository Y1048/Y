#include "guarded_composition_offline.hpp"
#include <iostream>

// Deliberately synthetic health/state/policy. Never accepts real transport input.
int main()
{
    try
    {
        std::string line; std::getline(std::cin,line);
        const auto config=nlohmann::json::parse(line);
        if(config.at("fixture_source")!="synthetic_state_and_policy_not_g1")
            throw std::invalid_argument("synthetic_fixture_required");
        const auto baseline=config.at("baseline").get<std::array<double,29>>();
        GuardedCompositionOffline study({.03,1.0,.1,.01,.025,.25,.17453292519943295},
                                        {.01,.15,.15,1.5,75});
        std::uint64_t sequence=0;
        while(std::getline(std::cin,line))
        {
            const auto event=nlohmann::json::parse(line);
            const double now=event.at("now");
            ++sequence;
            OfflineStateSample state{baseline,{},sequence,now};
            OfflineStateHealth health;
            health.crc_verified=true;health.mode_pr=0;health.mode_machine=5;
            health.deadman=true;health.emergency_stop=false;
            OfflinePolicySample policy{event.at("action").get<std::array<float,29>>(),sequence,sequence,now};
            const auto fault=event.value("fault",std::string{});
            if(fault=="tilt") health.rpy[0]=.2;
            else if(fault=="policy_stale") policy.created_at=now-.1;
            else if(fault=="state_stale") state.received_at=now-.1;
            else if(!fault.empty()) throw std::invalid_argument("unknown_fixture_fault");
            std::vector<ReceivedInput> packets;
            for(const auto& p:event.at("packets"))
            {
                const auto hex=p.at("hex").get<std::string>();
                if(hex.size()%2 || hex.find_first_not_of("0123456789abcdef")!=std::string::npos)
                    throw std::invalid_argument("invalid_hex");
                std::string raw;
                for(std::size_t i=0;i<hex.size();i+=2)
                    raw.push_back(static_cast<char>(std::stoi(hex.substr(i,2),nullptr,16)));
                packets.push_back({raw,p.at("at")});
            }
            const auto mode=study.Tick(state,health,policy,packets,now);
            std::cout<<nlohmann::json({{"mode",mode},{"reason",study.Reason()},
                {"candidate",study.Candidate()?nlohmann::json(*study.Candidate()):nlohmann::json(nullptr)}}).dump()<<'\n';
        }
    }
    catch(const std::exception& error) { std::cerr<<error.what();return 2; }
}
