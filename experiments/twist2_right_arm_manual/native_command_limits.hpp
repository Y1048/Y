#pragma once
#include <algorithm>
#include <cmath>
#include <optional>
inline std::optional<float> NativeLimitedPosition(float goal,float last,float measured,
 float step,float low,float high,float kp,float non_position_torque,float torque_limit){
 for(float value:{goal,last,measured,step,low,high,kp,non_position_torque,torque_limit})
  if(!std::isfinite(value))return {};
 if(step<=0||kp<=0||torque_limit<=0||low>high)return {};
 const float lower=std::max({last-step,low,measured+(-torque_limit-non_position_torque)/kp});
 const float upper=std::min({last+step,high,measured+(torque_limit-non_position_torque)/kp});
 if(lower>upper)return {};
 const float target=std::clamp(goal,lower,upper);
 const float predicted=kp*(target-measured)+non_position_torque;
 if(!std::isfinite(predicted)||std::abs(predicted)>torque_limit+1e-4F)return {};
 return target;
}
