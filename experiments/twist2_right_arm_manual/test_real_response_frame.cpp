#include "real_response_frame.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
void check(bool value,const char* why){if(!value)throw std::runtime_error(why);}
int main(){
 const auto path=std::filesystem::temp_directory_path()/"g1-real-response-offline.jsonl";
 try{
  RealResponseFrame frame;frame.writer.sequence=7;frame.writer.desired_created_s=1.;frame.writer.cycle_started_s=1.001;
  frame.writer.state_received_s=1.002;frame.writer.write_returned_s=1.003;
  for(int i=0;i<29;++i){frame.writer.q[i]=i;frame.writer.dq[i]=i+.1F;frame.writer.target[i]=i+.2F;
   frame.writer.target_dq[i]=0;frame.writer.kp[i]=40;frame.writer.kd[i]=5;frame.writer.tau_ff[i]=0;frame.writer.tau_est[i]=i+.3F;}
  for(int i=0;i<7;++i)frame.original_target[i]=i+.4F;
  {RealResponseLog log(path.string(),"fixture-session",std::string(64,'a'));log.Append(frame);log.Finish();}
  std::ifstream input(path);std::stringstream buffer;buffer<<input.rdbuf();const auto text=buffer.str();
  check(text.find("\"schema\":\"g1.real-response.v1\"")!=std::string::npos,"schema missing");
  check(text.find("\"sequence\":7")!=std::string::npos,"sequence missing");
  check(text.find("\"target_q_rad\":[0.4,1.4,2.4,3.4,4.4,5.4,6.4]")!=std::string::npos,"original target wrong");
  check(text.find("\"command_q_rad\":[22.2,23.2,24.2,25.2,26.2,27.2,28.2]")!=std::string::npos,"command slice wrong");
  bool refused=false;try{RealResponseLog bad(path.string(),"bad session",std::string(64,'a'));}catch(const std::invalid_argument&){refused=true;}
  check(refused,"unsafe identifier accepted");std::filesystem::remove(path);
  std::cout<<"PASS response schema, exact right-arm slices, provenance refusal, async finish\n";
 }catch(...){std::error_code ignored;std::filesystem::remove(path,ignored);throw;}
}
