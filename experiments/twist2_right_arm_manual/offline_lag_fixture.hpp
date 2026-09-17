#pragma once
#include <algorithm>
#include <cmath>
#include <stdexcept>
// Synthetic first-order response only. No mass, contacts, balance or actuator model.
inline double OfflineLagStep(double q,double target,double dt){
 if(!std::isfinite(q)||!std::isfinite(target)||!std::isfinite(dt)||dt<=0||dt>.02)
  throw std::invalid_argument("lag_fixture_input");
 const double response=(target-q)*(-std::expm1(-dt/.2));
 return std::clamp(response,-.08*dt,.08*dt);
}
