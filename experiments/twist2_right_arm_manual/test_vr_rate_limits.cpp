#include "upper_target_offline.hpp"
#include <iostream>
#define check(ok) if(!(ok))throw std::runtime_error("rate test failed line "+std::to_string(__LINE__))
int main(){try{
 std::string line;std::getline(std::cin,line);auto packet=nlohmann::json::parse(line);
 auto q=packet["all_joint_q_rad"].get<std::array<double,29>>();
 const double a=10*.017453292519943295,dt=.02;
 UpperTargetOffline limiter(q,0,10,.7,a);double last=q[22],vlast=0,peak=0;
 for(int n=1;n<=1100;++n){
  auto goal=q;goal[22]=n<=650?2.0:-1.0;
  packet["sequence"]=n;packet["all_joint_q_rad"]=goal;
  std::array<double,7> arm{};std::copy(goal.begin()+22,goal.end(),arm.begin());packet["right_arm"]["joints"]=arm;
  check(limiter.Step(n%3==1?std::optional<std::string>(packet.dump()):std::nullopt,n*dt)=="active");
  auto next=limiter.Target();const double v=(next[22]-last)/dt;
  check(std::abs(v)<=.7+1e-9);check(std::abs(v-vlast)/dt<=a+1e-8);
  if(n<=650)check(next[22]<=2.+1e-9);
  for(int i=0;i<29;++i)if(i!=22)check(next[i]==q[i]);
  peak=std::max(peak,std::abs(v));last=next[22];vlast=v;
 }
 check(peak>.69);
 packet["input_command_mode"]="pinch_disengaged";
 check(limiter.Step(packet.dump(),22.02)=="stopped");auto frozen=limiter.Target();
 check(limiter.Step(packet.dump(),22.04)=="stopped");check(limiter.Target()==frozen);
 packet["input_command_mode"]="active";packet["sequence"]=1;packet["input_packet_age_s"]=.20;
 UpperTargetOffline stale(q,0,10,.7,a);
 check(stale.Step(packet.dump(),.02)=="active");
 check(stale.Step(std::nullopt,.04)=="active");auto before=stale.Target();
 check(stale.Step(std::nullopt,.08)=="stopped");check(stale.Target()==before);
 check(stale.Step(packet.dump(),.10)=="stopped");
 std::cout<<"PASS speed, acceleration, fixed goal no overshoot, reversal, other joints, release latch\n";
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
