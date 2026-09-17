#pragma once
#include "offline_twist2_constants.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

inline float OfflineBlendAlpha(double elapsed,double capture_seconds,double blend_seconds)
{
    if(!std::isfinite(elapsed)||elapsed<0||!std::isfinite(capture_seconds)||capture_seconds<0
        ||!std::isfinite(blend_seconds)||blend_seconds<=0) throw std::invalid_argument("blend_time");
    const float x=std::clamp(static_cast<float>((elapsed-capture_seconds)/blend_seconds),0.0F,1.0F);
    return x*x*(3.0F-2.0F*x);
}
inline std::array<float,29> OfflineMimic(const std::array<double,29>& captured,
    const std::array<double,29>& upper,float alpha)
{
    if(!std::isfinite(alpha)||alpha<0||alpha>1) throw std::invalid_argument("blend_alpha");
    std::array<float,29> result{};
    for(std::size_t i=0;i<29;++i)
    {
        const float a=static_cast<float>(captured[i]),b=static_cast<float>(upper[i]);
        if(!std::isfinite(a)||!std::isfinite(b)) throw std::invalid_argument("blend_number");
        result[i]=i<12 ? (1.0F-alpha)*a+alpha*offline_twist2::kDefault[i]:b;
    }
    return result;
}
inline std::array<double,29> OfflineBlendDesired(const std::array<double,29>& captured,
    const std::array<double,29>& hybrid,float alpha)
{
    if(!std::isfinite(alpha)||alpha<0||alpha>1) throw std::invalid_argument("blend_alpha");
    std::array<double,29> result{};
    for(std::size_t i=0;i<29;++i)
    {
        const float a=static_cast<float>(captured[i]),b=static_cast<float>(hybrid[i]);
        if(!std::isfinite(a)||!std::isfinite(b)) throw std::invalid_argument("blend_number");
        result[i]=(1.0F-alpha)*a+alpha*b;
    }
    return result;
}
