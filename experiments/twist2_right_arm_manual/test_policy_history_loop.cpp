#include "offline_observation_history.hpp"
#include "offline_blend.hpp"
#include "guarded_composition_offline.hpp"
#include <iostream>

int main()
{
    try
    {
        std::string line;std::getline(std::cin,line);auto config=nlohmann::json::parse(line);
        if(config.at("state_source")!="frozen_virtual_baseline_not_g1") throw std::invalid_argument("fixture_required");
        const auto baseline=config.at("baseline").get<std::array<double,29>>();
        GuardedCompositionOffline study({.03,1,.1,.01,.025,.25,.17453292519943295},{.01,.15,.15,1.5,75});
        OfflineObservationHistory history;
        std::optional<nlohmann::json> event;
        const double blend_start=config.value("blend_start_s",0.0);
        float alpha=0;
        std::uint64_t sequence=0;
        bool stopped=false;
        while(std::getline(std::cin,line))
        {
            const auto request=nlohmann::json::parse(line);
            if(request.at("op")=="build")
            {
                if(event || stopped) throw std::runtime_error("build_phase");
                ++sequence;const double now=request.at("now");
                OfflineStateSample state{baseline,{},sequence,now};
                OfflineStateHealth health;health.crc_verified=true;health.mode_pr=0;health.mode_machine=5;
                health.deadman=true;health.emergency_stop=false;
                if(request.value("tilt",false)) health.rpy[0]=.2;
                std::vector<ReceivedInput> packets;
                for(const auto& p:request.at("packets"))
                {
                    const auto hex=p.at("hex").get<std::string>();
                    if(hex.size()%2 || hex.find_first_not_of("0123456789abcdef")!=std::string::npos) throw std::invalid_argument("hex");
                    std::string raw;
                    for(std::size_t i=0;i<hex.size();i+=2) raw.push_back(static_cast<char>(std::stoi(hex.substr(i,2),nullptr,16)));
                    packets.push_back({raw,p.at("at")});
                }
                alpha=OfflineBlendAlpha(std::max(0.0,now-blend_start),1,4);
                auto mode=study.Prepare(state,health,packets,now);
                if(mode=="active" && alpha<1) mode=study.Abort("vr_before_blend_complete");
                if(mode=="stopped")
                {
                    history.Stop();stopped=true;
                    std::cout<<nlohmann::json({{"mode",mode},{"reason",study.Reason()},
                        {"candidate",nullptr},{"previous_action",history.PreviousAction()},
                        {"commits",history.Commits()}}).dump()<<std::endl;
                    continue;
                }
                const auto upper=study.PreparedUpper().value_or(baseline);
                const auto mimic=OfflineMimic(baseline,upper,alpha);
                std::array<float,29> q{};for(std::size_t i=0;i<29;++i) q[i]=static_cast<float>(baseline[i]);
                const auto frame=history.Build(q,{}, {}, {},mimic);
                event=request;
                std::cout<<nlohmann::json({{"observation",frame.observation},
                    {"previous_action",history.PreviousAction()},{"commits",history.Commits()},
                    {"prepared_upper",upper},{"alpha",alpha}}).dump()<<std::endl;
            }
            else if(request.at("op")=="apply")
            {
                if(!event || stopped) throw std::runtime_error("apply_phase");
                const double now=event->at("now");
                OfflinePolicySample policy{request.at("action").get<std::array<float,29>>(),sequence,sequence,now};
                const auto mode=study.Finish(policy,now);
                std::optional<std::array<double,29>> desired;
                if(mode=="stopped") {history.Stop();stopped=true;}
                else if(study.Candidate())
                {
                    desired=OfflineBlendDesired(baseline,*study.Candidate(),alpha);
                    history.Commit(*desired);
                }
                else history.Discard();
                event.reset();
                std::cout<<nlohmann::json({{"mode",mode},{"reason",study.Reason()},
                    {"candidate",desired?nlohmann::json(*desired):nlohmann::json(nullptr)},
                    {"hybrid",study.Candidate()?nlohmann::json(*study.Candidate()):nlohmann::json(nullptr)},{"alpha",alpha},
                    {"previous_action",history.PreviousAction()},{"commits",history.Commits()}}).dump()<<std::endl;
            }
            else throw std::invalid_argument("operation");
        }
    }
    catch(const std::exception& e) {std::cerr<<e.what();return 2;}
}
