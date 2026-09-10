#pragma once
#include <cstdint>

// Accept wraparound advances, but never refresh freshness on duplicates/backward ticks.
inline bool NativeStateTickAdvances(std::uint32_t previous,std::uint32_t current){
 const auto delta=static_cast<std::uint32_t>(current-previous);
 return delta!=0U&&delta<0x80000000U;
}
