#pragma once
#include <array>
#include <cmath>
#include <stdexcept>
#include <algorithm>

// SDK-free hypothesis; explicit research settings, no physical-ready authority.
struct SplitSettleLimits { double window, excursion, attitude_excursion, speed, gyro, attitude; };
class SplitSettleWindow {
  struct Frame {double t; std::array<double,29> q; std::array<double,3> rpy;};
  SplitSettleLimits limits;
  std::array<Frame,128> frames{};
  std::size_t count=0;
  double previous=-1;
public:
  explicit SplitSettleWindow(SplitSettleLimits value):limits(value) {
    for(double x:{value.window,value.excursion,value.attitude_excursion,value.speed,value.gyro,value.attitude})
      if(!std::isfinite(x)||x<=0)throw std::invalid_argument("study_limits");
  }
  bool Update(const std::array<double,29>& q,const std::array<double,29>& dq,
              const std::array<double,3>& rpy,const std::array<double,3>& gyro,
              double receipt,bool blend) {
    if(!std::isfinite(receipt)||receipt<0||receipt<=previous)throw std::runtime_error("study_receipt");
    if(previous>=0 && receipt-previous>.05)count=0;
    previous=receipt;
    bool quiet=blend;
    for(std::size_t i=0;i<29;++i){
      if(!std::isfinite(q[i])||!std::isfinite(dq[i]))throw std::runtime_error("study_nonfinite");
      quiet=quiet&&std::abs(dq[i])<=limits.speed;
    }
    for(std::size_t i=0;i<3;++i){
      if(!std::isfinite(rpy[i])||!std::isfinite(gyro[i]))throw std::runtime_error("study_nonfinite");
      quiet=quiet&&std::abs(gyro[i])<=limits.gyro;
      if(i<2)quiet=quiet&&std::abs(rpy[i])<=limits.attitude;
    }
    if(!quiet){count=0;return false;}
    std::size_t remove=0;
    while(remove+1<count&&frames[remove+1].t<=receipt-limits.window)++remove;
    if(remove){for(std::size_t i=remove;i<count;++i)frames[i-remove]=frames[i];count-=remove;}
    if(count==frames.size())throw std::runtime_error("study_window_overflow");
    frames[count++]={receipt,q,rpy};
    if(receipt-frames[0].t<limits.window)return false;
    for(std::size_t i=0;i<31;++i){
      double lo=1e300,hi=-1e300;
      for(std::size_t n=0;n<count;++n){const auto& f=frames[n];const double x=i<29?f.q[i]:f.rpy[i-29];lo=std::min(lo,x);hi=std::max(hi,x);}
      if(hi-lo>(i<29?limits.excursion:limits.attitude_excursion))return false;
    }
    return true;
  }
};
