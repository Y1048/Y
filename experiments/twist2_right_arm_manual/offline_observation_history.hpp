#pragma once
#include "offline_twist2_constants.hpp"
#include <algorithm>
#include <cmath>
#include <optional>
#include <stdexcept>

struct OfflineObservationFrame
{
    std::array<float,127> current{};
    std::array<float,1432> observation{};
};
class OfflineObservationHistory
{
    std::array<float,1270> history{};
    std::array<float,29> previous{};
    std::optional<OfflineObservationFrame> pending;
    bool stopped=false;
    std::size_t commits=0;
public:
    const auto& History() const { return history; }
    const auto& PreviousAction() const { return previous; }
    std::size_t Commits() const { return commits; }
    void Stop() { pending.reset();stopped=true; }
    void Discard() { pending.reset(); }
    OfflineObservationFrame Build(const std::array<float,29>& q,const std::array<float,29>& dq,
        const std::array<float,3>& gyro,const std::array<float,3>& rpy,const std::array<float,29>& mimic_q)
    {
        if(stopped || pending) throw std::runtime_error("observation_phase");
        for(const auto& values:{q,dq,mimic_q})
            for(float v:values) if(!std::isfinite(v)) throw std::invalid_argument("nonfinite_observation_input");
        for(const auto& values:{gyro,rpy})
            for(float v:values) if(!std::isfinite(v)) throw std::invalid_argument("nonfinite_imu");
        OfflineObservationFrame frame;
        std::array<float,35> mimic{};mimic[2]=.8F;
        std::copy(mimic_q.begin(),mimic_q.end(),mimic.begin()+6);
        auto out=frame.current.begin();out=std::copy(mimic.begin(),mimic.end(),out);
        for(float v:gyro) *out++=v*.25F;
        *out++=rpy[0];*out++=rpy[1];
        for(std::size_t i=0;i<29;++i) *out++=q[i]-offline_twist2::kDefault[i];
        for(std::size_t i=0;i<29;++i) *out++=(i==4||i==5||i==10||i==11)?0.0F:dq[i]*.05F;
        std::copy(previous.begin(),previous.end(),out);
        auto obs=std::copy(frame.current.begin(),frame.current.end(),frame.observation.begin());
        obs=std::copy(history.begin(),history.end(),obs);
        std::copy(mimic.begin(),mimic.end(),obs);
        for(float& v:frame.observation)
        {
            if(!std::isfinite(v)) throw std::invalid_argument("nonfinite_observation");
            v=std::clamp(v,-100.0F,100.0F);
        }
        pending=frame;return frame;
    }
    void Commit(const std::array<double,29>& accepted_candidate)
    {
        if(stopped || !pending) throw std::runtime_error("commit_phase");
        std::array<float,29> action{};
        for(std::size_t i=0;i<29;++i)
        {
            const float q=static_cast<float>(accepted_candidate[i]);
            if(!std::isfinite(q)) throw std::invalid_argument("invalid_feedback");
            const float a=(q-offline_twist2::kDefault[i])/offline_twist2::kActionScale;
            if(!std::isfinite(a)) throw std::invalid_argument("invalid_feedback");
            action[i]=std::clamp(a,-offline_twist2::kActionLimit,offline_twist2::kActionLimit);
        }
        std::move(history.begin()+127,history.end(),history.begin());
        std::copy(pending->current.begin(),pending->current.end(),history.end()-127);
        previous=action;pending.reset();++commits;
    }
};
