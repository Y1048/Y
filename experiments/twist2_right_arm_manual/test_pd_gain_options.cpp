#include "pd_gain_options.hpp"
#include <iostream>
#include <vector>
void check(bool b){if(!b)throw std::runtime_error("check failed");}
int main(){try{
 std::array<float,29> kp{},kd{};kp.fill(40);kd.fill(5);
 auto parse=[&](std::vector<const char*> args){return ParsePdGainOptions(static_cast<int>(args.size()),args.data(),kp,kd);};
 const std::vector<const char*> base={"test","eth0","policy","--enable-actuation","--policy-seconds","300","--pd-reach-trial"};
 auto g=parse(base);check(g.kp==kp&&g.kd==kd);
 auto args=base;args.insert(args.end(),{"--right-shoulder-kd","6","--right-shoulder-kp","48"});
 g=parse(args);check(g.kp[22]==48&&g.kd[22]==6);
 for(int i=0;i<29;++i)if(i!=22)check(g.kp[i]==kp[i]&&g.kd[i]==kd[i]);
 int rejected=0;
 for(const auto value:{"nan","inf","0","-1","101","48junk","1e999"}){
  args=base;args.insert(args.end(),{"--right-shoulder-kp",value});
  try{parse(args);}catch(const std::exception&){++rejected;}
 }
 check(rejected==7);
 for(int kind=0;kind<5;++kind){
  args=base;
  if(kind==0)args.push_back("--right-shoulder-kp");
  if(kind==1)args.insert(args.end(),{"--unknown","48"});
  if(kind==2)args.insert(args.end(),{"--right-shoulder-kp","48","--right-shoulder-kp","40"});
  if(kind==3){args[6]="--udp-right-arm";args.insert(args.end(),{"--right-shoulder-kp","48"});}
  if(kind==4)args.insert(args.end(),{"--right-shoulder-kd","0"});
  bool failed=false;try{parse(args);}catch(const std::exception&){failed=true;}check(failed);
 }
 args=base;args[6]="--udp-right-arm";g=parse(args);check(g.kp==kp&&g.kd==kd);
 args=base;args[6]="--handoff-only-trial";g=parse(args);check(g.kp==kp&&g.kd==kd);
 args.push_back("--right-shoulder-kp");args.push_back("48");
 {bool failed=false;try{parse(args);}catch(const std::exception&){failed=true;}check(failed);}
 args=base;args.insert(args.end(),{"--pd-gain","22:48:5","--pd-gain","25:45:5","--pd-gain","28:20:1"});
 g=parse(args);check(g.kp[22]==48&&g.kp[25]==45&&g.kp[28]==20&&g.kd[28]==1);
 for(int i=0;i<29;++i)if(i!=22&&i!=25&&i!=28)check(g.kp[i]==kp[i]&&g.kd[i]==kd[i]);
 for(const auto value:{"21:40:5","29:40:5","22:40","22::5","22:40:","22:40:5:6","22x:40:5","22:nan:5","22:40:inf","22:101:5","22:40:0"}){
  args=base;args.insert(args.end(),{"--pd-gain",value});bool failed=false;
  try{parse(args);}catch(const std::exception&){failed=true;}check(failed);
 }
 for(int kind=0;kind<4;++kind){
  args=base;args.insert(args.end(),{"--pd-gain","22:48:5"});
  if(kind==0)args.insert(args.end(),{"--pd-gain","22:40:5"});
  if(kind==1)args.insert(args.end(),{"--right-shoulder-kp","40"});
  if(kind==2)args.insert(args.begin()+7,{"--right-shoulder-kd","5"});
  if(kind==3)args[6]="--udp-right-arm";
  bool failed=false;try{parse(args);}catch(const std::exception&){failed=true;}check(failed);
 }
 std::cout<<"PASS: defaults, overrides, untouched joints, invalid/duplicate/missing options, UDP isolation\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
