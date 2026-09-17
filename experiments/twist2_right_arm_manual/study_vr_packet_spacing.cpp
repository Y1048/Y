#include "upper_target_offline.hpp"
#include <iostream>
#include <stdexcept>
void require(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
int main(){try{
 std::string line;std::getline(std::cin,line);const auto original=nlohmann::json::parse(line);
 nlohmann::json report={{"offline_only",true},{"physical_output",false},{"cases",nlohmann::json::array()}};
 for(double distance:{.05,.2,1.,3.})for(int schedule=0;schedule<3;++schedule){
  auto packet=original;auto q=packet["all_joint_q_rad"].get<std::array<double,29>>();q[22]=-1.;
  auto goal=q;goal[22]+=distance;
  packet["all_joint_q_rad"]=goal;std::array<double,7> arm{};std::copy(goal.begin()+22,goal.end(),arm.begin());
  packet["right_arm"]["joints"]=arm;packet["input_packet_age_s"]=0;
  UpperTargetOffline target(q,0,10,.7,10*.017453292519943295);
  double previous=q[22],old_v=0,peak=0,peak_a=0,settled=-1;int next_packet=1,number=0;
  const int spacing[]={1,3,1,6,2,4};
  for(int n=1;n<=1000;++n){
   std::optional<std::string> incoming;
   if(n==next_packet){packet["sequence"]=++number;incoming=packet.dump();
    next_packet+=schedule==0?1:schedule==1?3:spacing[(number-1)%6];}
   require(target.Step(incoming,n*.02)=="active","unexpected stop");
   const auto result=target.Target();const double v=(result[22]-previous)/.02;
   peak=std::max(peak,std::abs(v));peak_a=std::max(peak_a,std::abs(v-old_v)/.02);
   require(std::abs(v)<=.700000001,"speed exceeded");
   require(std::abs(v-old_v)/.02<=10*.017453292519943295+1e-8,"acceleration exceeded");
   require(result[22]<=goal[22]+1e-9,"fixed goal overshoot");
   for(int i=0;i<29;++i)if(i!=22)require(result[i]==q[i],"other joint moved");
   if(settled<0&&std::abs(result[22]-goal[22])<1e-5&&std::abs(v)<1e-4)settled=n*.02;
   previous=result[22];old_v=v;
  }
  require(settled>0,"did not converge");if(distance==3)require(peak>.699,"long move did not reach cap");
  report["cases"].push_back({{"distance_rad",distance},{"schedule",schedule},
   {"peak_rad_s",peak},{"peak_accel_rad_s2",peak_a},{"settled_s",settled},{"packets",number}});
  const auto frozen=target.Target();
  require(target.Step(std::nullopt,20.3)=="stopped","timeout missed");
  require(target.Target()==frozen,"moved on timeout");
  require(target.Step(packet.dump(),20.32)=="stopped","restarted after timeout");
 }
 std::cout<<report.dump(2)<<'\n';
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
