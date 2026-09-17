#include "guarded_composition_offline.hpp"
#include <iostream>
#include <limits>

void Check(bool ok) { if (!ok) throw std::runtime_error("check_failed"); }
int main(int argc,char** argv)
{
    try
    {
        if(argc!=2) return 2;
        const std::string fault=argv[1];
        std::string payload; std::getline(std::cin,payload);
        auto packet=nlohmann::json::parse(payload);
        GuardedCompositionOffline study({.021,.039,.1,.01,.025,.25,.17},{.01,.15,.15,1.5,75});
        std::array<double,29> baseline{};
        std::copy(offline_twist2::kDefault.begin(),offline_twist2::kDefault.end(),baseline.begin());
        if(fault=="candidate_limit") baseline[22]=offline_twist2::kUpper[22]-offline_twist2::kJointLimitMargin;
        packet["all_joint_q_rad"]=baseline;
        std::array<double,7> goal{};
        std::copy(baseline.begin()+22,baseline.end(),goal.begin());
        packet["right_arm"]["joints"]=goal;
        OfflineStateHealth h;
        h.crc_verified=true; h.mode_pr=0; h.mode_machine=5; h.deadman=true; h.emergency_stop=false;
        for(int n=1;n<=6;++n)
        {
            const double now=n*.02;
            OfflineStateSample state{baseline,{},static_cast<std::uint64_t>(n),now};
            auto health=h;
            std::optional<OfflinePolicySample> policy=OfflinePolicySample{{},static_cast<std::uint64_t>(n),state.sequence,now};
            for(std::size_t i=0;i<29;++i) policy->action[i]=(i%2 ? -2.0F:2.0F);
            if(n==5)
            {
                if(fault=="candidate_limit")
                {
                    packet["all_joint_q_rad"][22]=baseline[22]+.01;
                    packet["right_arm"]["joints"][0]=baseline[22]+.01;
                }
                if(fault=="crc") health.crc_verified=false;
                if(fault=="mode") health.mode_machine=4;
                if(fault=="deadman") health.deadman=false;
                if(fault=="emergency") health.emergency_stop=true;
                if(fault=="imu") health.rpy[2]=std::numeric_limits<double>::quiet_NaN();
                if(fault=="tilt") health.rpy[0]=.16;
                if(fault=="q") state.q[0]=10;
                if(fault=="dq") state.dq[0]=2;
                if(fault=="torque") health.torque[28]=std::numeric_limits<double>::infinity();
                if(fault=="temperature") health.temperature[0]=76;
                if(fault=="motor_fault") health.faults[28]=1;
                if(fault=="policy_missing") policy.reset();
                if(fault=="policy_old") { policy->created_at=now-.015;state.received_at=now-.02; }
                if(fault=="policy_future") policy->created_at=now+.01;
                if(fault=="policy_state") --policy->state_sequence;
                if(fault=="policy_repeat") --policy->sequence;
                if(fault=="action_nan") policy->action[28]=std::numeric_limits<float>::quiet_NaN();
                if(fault=="action_range") policy->action[0]=2.01F;
            }
            packet["sequence"]=n;
            std::vector<ReceivedInput> packets;
            if(n>=4) packets.push_back({packet.dump(),now});
            const auto mode=study.Tick(state,health,policy,packets,now);
            if(n<4) Check(!study.Candidate());
            if(n==4 || (n>=5 && fault=="valid"))
            {
                Check(mode=="active" && study.Candidate().has_value());
                for(std::size_t i=0;i<12;++i)
                {
                    using namespace offline_twist2;
                    const double expected=std::clamp(kDefault[i]+.5F*policy->action[i],kLower[i]+.05F,kUpper[i]-.05F);
                    Check((*study.Candidate())[i]==expected);
                }
                for(std::size_t i=12;i<29;++i) Check((*study.Candidate())[i]==baseline[i]);
            }
            if(n>=5 && fault!="valid") Check(mode=="stopped" && !study.Candidate() && !study.Reason().empty());
        }
        std::cout<<"PASS "<<fault<<" "<<study.Reason()<<std::endl;
    }
    catch(const std::exception& e) { std::cerr<<e.what();return 2; }
}
