#pragma once
#include "guarded_composition_offline.hpp"
#include "offline_word_crc.hpp"
#include <cstring>
#include <limits>

// Pinned official hg classes, native little-endian 4-byte-aligned layout only.
// NOT CDR/network bytes; deployment ABI equivalence is not yet verified.
// Second profile is the separately reviewed installed Python SDK CRC packing.
struct DecodedOfflineHgState
{
    OfflineStateSample sample;
    OfflineStateHealth health;
    std::uint32_t robot_tick;
    std::array<double,4> quaternion;
    std::array<double,3> gyro, acceleration;
};
inline DecodedOfflineHgState DecodeOfflineHgNative(const std::vector<std::uint8_t>& bytes,
    const std::string& profile, std::uint64_t receipt_sequence, double received_at)
{
    if(profile!="hg_native_le2092_9754cd15" && profile!="hg_sdk_crc_le2092_b95a5304") throw std::invalid_argument("unsupported_layout");
    if(bytes.size()!=2092) throw std::invalid_argument("state_byte_count");
    if(!std::isfinite(received_at) || received_at<0) throw std::invalid_argument("receipt_time");
    const auto U32=[&](std::size_t i) {
        return static_cast<std::uint32_t>(bytes[i]) | (static_cast<std::uint32_t>(bytes[i+1])<<8)
            | (static_cast<std::uint32_t>(bytes[i+2])<<16) | (static_cast<std::uint32_t>(bytes[i+3])<<24);
    };
    const auto Float=[&](std::size_t i) {
        static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559);
        const auto bits=U32(i);float value;std::memcpy(&value,&bits,4);
        if(!std::isfinite(value)) throw std::invalid_argument("nonfinite_decoded_state");
        return static_cast<double>(value);
    };
    const auto I16=[&](std::size_t i) {
        const int value=bytes[i]+(static_cast<int>(bytes[i+1])<<8);
        return value>=32768 ? value-65536 : value;
    };
    if(OfflineWordCrc({bytes.begin(),bytes.end()-4})!=U32(2088)) throw std::invalid_argument("crc_mismatch");
    DecodedOfflineHgState result{};
    result.sample.sequence=receipt_sequence;result.sample.received_at=received_at;
    result.robot_tick=U32(12);
    result.health.mode_pr=bytes[8];result.health.mode_machine=bytes[9];
    for(std::size_t i=0;i<4;++i) result.quaternion[i]=Float(16+i*4);
    for(std::size_t i=0;i<3;++i)
    {
        result.gyro[i]=Float(32+i*4);result.acceleration[i]=Float(44+i*4);
        result.health.rpy[i]=Float(56+i*4);
    }
    for(std::size_t i=0;i<29;++i)
    {
        const auto offset=72+i*56;
        result.sample.q[i]=Float(offset+4);result.sample.dq[i]=Float(offset+8);
        result.health.torque[i]=Float(offset+16);
        result.health.temperature[i]=std::max(I16(offset+20),I16(offset+22));
        result.health.faults[i]=U32(offset+36);
    }
    const unsigned buttons=bytes[2034]+(static_cast<unsigned>(bytes[2035])<<8);
    result.health.deadman=(buttons&1)!=0;
    result.health.emergency_stop=(buttons&(0x0008|0x0200))!=0;
    result.health.crc_verified=true;
    return result;
}
