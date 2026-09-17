#pragma once
#include <cstdint>
#include <stdexcept>
#include <vector>

// CRC of native little-endian uint32 words, as used by local TWIST2 crc32_core.
// NOT a DDS/CDR decoder. Caller must establish layout and remove the stored CRC.
inline std::uint32_t OfflineWordCrc(const std::vector<std::uint8_t>& bytes)
{
    if (bytes.empty() || bytes.size()%4) throw std::invalid_argument("crc_word_alignment");
    std::uint32_t crc=0xffffffffU;
    for(std::size_t offset=0;offset<bytes.size();offset+=4)
    {
        std::uint32_t word=0;
        for(unsigned i=0;i<4;++i) word |= static_cast<std::uint32_t>(bytes[offset+i])<<(8*i);
        crc ^= word;
        for(unsigned bit=0;bit<32;++bit)
            crc=(crc&0x80000000U) ? (crc<<1)^0x04c11db7U : crc<<1;
    }
    return crc;
}
