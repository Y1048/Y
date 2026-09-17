#pragma once
#include "measured_composition_offline.hpp"
#include "offline_twist2_constants.hpp"

struct OfflineStateHealth
{
    // Adapter assertion only: this class cannot compute DDS CRC without raw bytes.
    bool crc_verified = false;
    int mode_pr = -1;
    int mode_machine = -1;
    bool deadman = false;
    bool emergency_stop = true;
    std::array<double, 3> rpy{};
    std::array<double, 29> torque{};
    std::array<double, 29> temperature{};
    std::array<unsigned, 29> faults{};
};
struct OfflinePolicySample
{
    // Output of local Policy::infer: clipped [-2,2], motor order, NOT positions.
    std::array<float, 29> action;
    std::uint64_t sequence;
    std::uint64_t state_sequence;
    double created_at;
};
struct OfflineHealthLimits
{
    double policy_age, roll, pitch, velocity, temperature;
};
inline std::string CheckOfflineStateHealth(const OfflineStateSample& state,
    const OfflineStateHealth& health,const OfflineHealthLimits& limits)
{
    using namespace offline_twist2;
    if(!health.crc_verified)return "unverified_crc";
    if(health.mode_pr!=0||health.mode_machine!=5)return "unexpected_mode";
    if(!health.deadman||health.emergency_stop)return "operator_stop";
    for(double v:health.rpy)if(!std::isfinite(v))return "invalid_imu";
    if(std::abs(health.rpy[0])>limits.roll||std::abs(health.rpy[1])>limits.pitch)return "attitude_limit";
    for(std::size_t i=0;i<29;++i){
        if(!std::isfinite(state.q[i])||!std::isfinite(state.dq[i])||!std::isfinite(health.torque[i])
           ||!std::isfinite(health.temperature[i]))return "nonfinite_state";
        if(state.q[i]<kLower[i]+kJointLimitMargin||state.q[i]>kUpper[i]-kJointLimitMargin)return "state_soft_limit";
        if(std::abs(state.dq[i])>limits.velocity)return "velocity_limit";
        if(health.temperature[i]>limits.temperature||health.faults[i])return "motor_health";
    }
    return "";
}
class GuardedCompositionOffline
{
    MeasuredCompositionOffline composition;
    OfflineHealthLimits limits;
    std::optional<OfflinePolicySample> previous;
    std::optional<std::array<double, 29>> candidate;
    std::string reason;
    std::optional<MeasuredCompositionOffline> staged;
    std::optional<OfflineStateSample> prepared_state;
    double prepared_at=0;
    double state_age;
    std::string prepared_mode;
    std::string Stop(const std::string& why)
    {
        if (reason.empty()) reason = why;
        candidate.reset();staged.reset();prepared_state.reset();
        return "stopped";
    }
public:
    GuardedCompositionOffline(CompositionLimits c, OfflineHealthLimits h, bool prealignment=false) : composition(c,prealignment), limits(h), state_age(c.state_age)
    {
        for (double v : {h.policy_age,h.roll,h.pitch,h.velocity,h.temperature})
            if (!std::isfinite(v) || v <= 0) throw std::invalid_argument("invalid_health_limits");
    }
    std::string Abort(const std::string& why) { return Stop(why.empty()?"external_stop":why); }
    const auto& Candidate() const { return candidate; }
    const auto& Reason() const { return reason; }
    // Prepare is provisional. Only Finish with a valid policy commits the new upper state.
    const std::optional<std::array<double,29>>& PreparedUpper() const
    {
        if(!staged) throw std::runtime_error("not_prepared");
        return staged->Candidate();
    }
    std::string Prepare(const OfflineStateSample& state,const OfflineStateHealth& health,
                        const std::vector<ReceivedInput>& packets,double now)
    {
        using namespace offline_twist2;
        candidate.reset();
        if (!reason.empty()) return "stopped";
        if(staged) return Stop("unfinished_prepare");
        if (!std::isfinite(now)) return Stop("invalid_clock");
        const auto health_error=CheckOfflineStateHealth(state,health,limits);
        if(!health_error.empty())return Stop(health_error);
        staged=composition;
        prepared_mode=staged->Tick(state,{},packets,now);
        if(prepared_mode=="stopped") return Stop(staged->Reason());
        if(staged->Candidate())
            for(std::size_t i=12;i<29;++i)
                if((*staged->Candidate())[i]<kLower[i]+kJointLimitMargin
                    || (*staged->Candidate())[i]>kUpper[i]-kJointLimitMargin)
                    return Stop("candidate_soft_limit");
        prepared_state=state;prepared_at=now;
        return prepared_mode;
    }
    std::string Finish(const std::optional<OfflinePolicySample>& policy,double now)
    {
        using namespace offline_twist2;
        if(!reason.empty()) return "stopped";
        if(!staged || !prepared_state) return Stop("not_prepared");
        const auto& state=*prepared_state;
        if(!std::isfinite(now) || now<prepared_at || now-state.received_at>state_age)
            return Stop("state_expired_during_inference");
        if (!policy) return Stop("missing_policy");
        if (!std::isfinite(policy->created_at) || policy->created_at < 0
            || policy->created_at < prepared_at || policy->created_at < state.received_at || policy->created_at > now
            || now-policy->created_at > limits.policy_age)
            return Stop("policy_time");
        if (policy->state_sequence != state.sequence) return Stop("policy_state_mismatch");
        if (previous && (policy->sequence <= previous->sequence || policy->created_at <= previous->created_at))
            return Stop("policy_discontinuity");
        for (float a : policy->action)
            if (!std::isfinite(a) || std::abs(a) > kActionLimit) return Stop("invalid_policy_action");
        std::array<double,12> legs{};
        for (std::size_t i=0;i<12;++i)
            legs[i]=std::clamp(kDefault[i]+kActionScale*policy->action[i],
                              kLower[i]+kJointLimitMargin,kUpper[i]-kJointLimitMargin);
        const auto mode=prepared_mode;
        if (staged->Candidate())
        {
            auto next=*staged->Candidate();
            std::copy(legs.begin(),legs.end(),next.begin());
            for (std::size_t i=0;i<29;++i)
                if (next[i]<kLower[i]+kJointLimitMargin || next[i]>kUpper[i]-kJointLimitMargin)
                    return Stop("candidate_soft_limit");
            candidate=next;
        }
        composition=std::move(*staged);staged.reset();prepared_state.reset();
        previous=policy;
        return mode;
    }
    std::string Tick(const OfflineStateSample& state,const OfflineStateHealth& health,
                     const std::optional<OfflinePolicySample>& policy,
                     const std::vector<ReceivedInput>& packets,double now)
    {
        if(Prepare(state,health,packets,now)=="stopped") return "stopped";
        return Finish(policy,now);
    }
};
