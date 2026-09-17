#pragma once
#include "guarded_composition_offline.hpp"

// Diagnostic values only: no LowCmd serialization, socket or SDK dependency.
// predicted_torque is calculated only after a successful Tick for joints 0..28.
// In damping/unused slots its zero is a placeholder, NOT a zero-torque assertion.
struct OfflineMotorDiagnostic { float q=0,kp=0,kd=0,feedforward=0,predicted_torque=0; };
struct OfflineDesiredPosition
{
    std::array<float,29> q{},feedforward{};
    double created_at=0;
};
inline std::array<float,29> OfflineTorqueFade(const std::array<float,29>& measured_tau,float alpha)
{
    if(!std::isfinite(alpha)||alpha<0||alpha>1) throw std::invalid_argument("alpha");
    std::array<float,29> result{};
    for(std::size_t i=0;i<29;++i)
    {
        if(!std::isfinite(measured_tau[i])) throw std::invalid_argument("torque");
        const float limit=offline_twist2::kTorqueLimit[i]*.5F;
        result[i]=(1-alpha)*std::clamp(measured_tau[i],-limit,limit);
    }
    return result;
}
class OfflineWriterStudy
{
    std::array<float,29> last;
    double activated,last_tick;
    std::string reason;
    std::array<OfflineMotorDiagnostic,35> diagnostic{};
    void Damping(const std::string& why)
    {
        if(reason.empty()) reason=why;
        for(std::size_t i=0;i<35;++i) diagnostic[i]={0,0,(i==3||i==9)?2.0F:1.0F,0,0};
    }
public:
    OfflineWriterStudy(const std::array<float,29>& captured,double now):last(captured),activated(now),last_tick(now)
    {
        if(!std::isfinite(now)||now<0) throw std::invalid_argument("start_time");
        for(std::size_t i=0;i<29;++i)
            if(!std::isfinite(last[i])||last[i]<offline_twist2::kLower[i]+offline_twist2::kJointLimitMargin
                ||last[i]>offline_twist2::kUpper[i]-offline_twist2::kJointLimitMargin)
                throw std::invalid_argument("captured_position");
    }
    const auto& Diagnostics() const {return diagnostic;}
    const auto& Reason() const {return reason;}
    const auto& LastTarget() const {return last;}
    void Stop(const std::string& why) {Damping(why.empty()?"external_stop":why);}
    bool Tick(const OfflineStateSample& state,const OfflineStateHealth& health,
              const std::optional<OfflineDesiredPosition>& desired,double now)
    {
        using namespace offline_twist2;
        if(!reason.empty()) return false;
        const auto Fail=[&](const std::string& why){Damping(why);return false;};
        if(!std::isfinite(now)||now-last_tick<.002-1e-12) return Fail("writer_clock");
        last_tick=now;
        if(!std::isfinite(state.received_at)||state.received_at<0||state.received_at>now
            ||now-state.received_at>.02) return Fail("state_timeout");
        if(!health.crc_verified||health.mode_pr!=0||health.mode_machine!=5) return Fail("state_provenance_or_mode");
        if(!health.deadman||health.emergency_stop) return Fail("operator_stop");
        for(double v:health.rpy) if(!std::isfinite(v)) return Fail("invalid_imu");
        if(std::abs(health.rpy[0])>.35||std::abs(health.rpy[1])>.35) return Fail("attitude_limit");
        if(!desired) return Fail("missing_desired");
        if(!std::isfinite(desired->created_at)||desired->created_at<activated||desired->created_at>now)
            return Fail("desired_time");
        if(now-desired->created_at>.06 && now-activated>.25) return Fail("command_timeout");
        auto next=diagnostic;
        auto next_target=last;
        for(std::size_t i=0;i<35;++i)
        {
            if(i>=29) {next[i]={0,0,1,0,0};continue;}
            const float q=static_cast<float>(state.q[i]),dq=static_cast<float>(state.dq[i]);
            const float low=kLower[i]+kJointLimitMargin,high=kUpper[i]-kJointLimitMargin;
            if(!std::isfinite(q)||!std::isfinite(dq)||!std::isfinite(health.torque[i])
                ||!std::isfinite(health.temperature[i])||!std::isfinite(desired->q[i])
                ||!std::isfinite(desired->feedforward[i])) return Fail("invalid_motor_number");
            if(q<low||q>high||std::abs(dq)>12||health.temperature[i]>75||health.faults[i])
                return Fail("motor_limit_or_fault");
            const float delta=(i<12?2.0F:.8F)*.002F;
            const float soft=kTorqueLimit[i]*.5F;
            const float ff=std::clamp(desired->feedforward[i],-soft,soft);
            const float non_position=-kKd[i]*dq+ff;
            const float lower=std::max({last[i]-delta,low,q+(-soft-non_position)/kKp[i]});
            const float upper=std::min({last[i]+delta,high,q+(soft-non_position)/kKp[i]});
            if(lower>upper) return Fail("incompatible_rate_joint_torque_limits");
            const float target=std::clamp(desired->q[i],lower,upper);
            const float predicted=kKp[i]*(target-q)-kKd[i]*dq+ff;
            if(!std::isfinite(predicted)||std::abs(predicted)>soft+1e-4F) return Fail("predicted_torque_limit");
            next[i]={target,kKp[i],kKd[i],ff,predicted};next_target[i]=target;
        }
        diagnostic=next;last=next_target;return true;
    }
};
