#include "native_composition_offline.hpp"
#include <fstream>
#include <iostream>
void Check(bool ok){if(!ok)throw std::runtime_error("check");}
int main(int argc,char** argv){
 try{
  Check(argc==2);std::ifstream file(argv[1]);Check(file.good());
  std::string line;std::getline(file,line);auto meta=nlohmann::json::parse(line);
  Check(meta.at("representation")=="sdk_crc_packed_le2092_not_cdr");
  Check(meta.at("crc_source_sha256")=="b95a530423f72c5acc96811f75677699cb3a185b6327353e7c44b355a425a20e");
  OfflineStateContinuity continuity;NativeCompositionOffline control;
  size_t count=0,duplicates=0;std::optional<std::uint32_t> last;bool ended=false;
  while(std::getline(file,line)){
   auto row=nlohmann::json::parse(line);
   if(row.at("event")=="end"){Check(row.at("samples")==count);ended=true;break;}
   auto hex=row.at("packed_hex").get<std::string>();std::vector<std::uint8_t> bytes;
   for(size_t i=0;i<hex.size();i+=2)bytes.push_back(static_cast<std::uint8_t>(std::stoul(hex.substr(i,2),nullptr,16)));
   const double at=row.at("received_at_s");
   auto decoded=DecodeOfflineHgNative(bytes,"hg_sdk_crc_le2092_b95a5304",++count,at);
   Check(continuity.Check(decoded.robot_tick,at,at).empty());
   if(last&&*last==decoded.robot_tick)++duplicates;last=decoded.robot_tick;
   if(count==1){
    Check(control.Prepare(bytes,"hg_sdk_crc_le2092_b95a5304",at,{},at)=="stopped");
    Check(control.Reason()=="operator_stop"&&!control.Candidate());
   }
  }
  Check(ended&&count==6000&&duplicates==291);
  OfflineStateContinuity stall;
  Check(stall.Check(1,1,1).empty());Check(stall.Check(1,1.01,1.01).empty());
  Check(stall.Check(1,1.019,1.019).empty());Check(stall.Check(1,1.021,1.021)=="robot_tick_stalled");
  Check(stall.Check(2,1.022,1.022)=="robot_tick_stalled");
  OfflineStateContinuity receipt;Check(receipt.Check(1,1,1).empty());
  Check(receipt.Check(2,1,1.001)=="state_receipt_discontinuity");
  OfflineStateContinuity late;Check(late.Check(1,1,1.021)=="stale_or_invalid_state_time");
  std::cout<<"PASS 6000 real samples CRC+continuity; 291 duplicate ticks accepted; original R1-off still operator_stop; stall/replay/stale latch checks\n";
 }catch(const std::exception& e){std::cerr<<e.what();return 1;}
}
