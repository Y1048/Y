#include "offline_word_crc.hpp"
#include "vendor/json.hpp"
#include <iostream>
int main()
{
    std::string line;
    while(std::getline(std::cin,line))
    {
        try
        {
            const auto v=nlohmann::json::parse(line).get<std::vector<unsigned>>();
            std::vector<std::uint8_t> bytes;
            for(auto x:v) { if(x>255) throw std::invalid_argument("byte_range");bytes.push_back(static_cast<std::uint8_t>(x)); }
            std::cout<<nlohmann::json({{"crc",OfflineWordCrc(bytes)}}).dump()<<'\n';
        }
        catch(const std::exception&) { std::cout<<"{\"error\":true}\n"; }
    }
}
