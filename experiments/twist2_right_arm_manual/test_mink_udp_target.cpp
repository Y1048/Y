#include "mink_udp_target.hpp"
#include <iostream>
void check(bool value,const char* why){if(!value)throw std::runtime_error(why);}
int main(){try{
 std::string line;std::getline(std::cin,line);auto packet=nlohmann::json::parse(line);
 auto q=packet.at("all_joint_q_rad").get<std::array<double,29>>();
 // Deterministic scheduling: an older pre-lock timestamp enters after a poll.
 MinkUdpTarget old_clock(q,0);
 check(old_clock.Poll(.02).empty(),"clock setup");
 check(old_clock.Poll(.01)=="invalid_clock","old race not reproduced");
 double locked_now=0;
 MinkUdpTarget serialized(q,0,[&](){return locked_now;});
 for(int n=1;n<=1600;++n){locked_now=n*.02;serialized.Update(0,true);}
 locked_now=32.005;check(serialized.Poll(32.004).empty(),"serialized poll");
 locked_now=32.006;check(serialized.Receive(line,32.001),"stale caller receipt rejected");
 locked_now=32.02;serialized.Update(31,true);
 locked_now=32.021;check(serialized.Poll(30).empty(),"stale caller poll rejected");
 locked_now=32.3;check(serialized.Poll(0)=="receiver_timeout","serialized timeout missed");
 MinkUdpTarget backwards(q,0,[&](){return locked_now;});
 locked_now=1;check(backwards.Poll(0).empty(),"backwards setup");
 locked_now=.9;check(backwards.Poll(0)=="invalid_clock","real clock reversal accepted");
 MinkUdpTarget target(q,0);auto previous=q;double now=0;
 for(int step=1;step<=1600;++step){now=step*.02;auto next=target.Update(now,true);
  for(unsigned i=0;i<29;++i){check(std::abs(next[i]-previous[i])<=.00160000001,"initial rate exceeded");if(i<15)check(next[i]==q[i],"lower/waist changed");}previous=next;
 }
 check(target.Ready(),"initial pose not reached");
 auto goal=previous;goal[22]+=.1; // No input/desired error gate; move gradually.
 packet["all_joint_q_rad"]=goal;packet["right_arm"]["joints"]=std::array<double,7>{goal[22],goal[23],goal[24],goal[25],goal[26],goal[27],goal[28]};
 check(target.Receive(packet.dump(),now+.005),"absolute input rejected");
 auto next=target.Update(now+.02,true);check(std::abs(next[22]-previous[22]-.0016)<1e-9,"absolute rate");
 for(unsigned i=0;i<29;++i)if(i!=22)check(next[i]==previous[i],"unrelated axis changed");
 for(int n=1;n<=70;++n){packet["sequence"]=packet.at("sequence").get<unsigned long long>()+1;now+=.02;check(target.Receive(packet.dump(),now+.005),"refresh");next=target.Update(now+.02,true);check(next[22]<=goal[22],"overshoot");}
 check(std::abs(next[22]-goal[22])<1e-12,"goal not reached");
 packet["sequence"]=packet.at("sequence").get<unsigned long long>()+1;packet["input_command_mode"]="pinch_disengaged";
 check(!target.Receive(packet.dump(),now+.025),"release accepted");check(!target.Poll(now+.03).empty(),"release not latched");
 bool stopped=false;try{target.Update(now+.04,true);}catch(...){stopped=true;}check(stopped,"updated after stop");
 MinkUdpTarget early(q,0);check(!early.Receive(line,.01),"early engage accepted");
 for(int scenario=0;scenario<2;++scenario){
  MinkUdpTarget trial(q,0);for(int n=1;n<=1600;++n)trial.Update(n*.02,true);
  check(trial.Receive(line,32.005),"watch input");trial.Update(32.02,true);
  if(scenario==0)check(!trial.Poll(32.3).empty(),"timeout missed");
  else check(!trial.Receive("{",32.025),"malformed accepted");
  bool latched=false;try{trial.Update(32.32,true);}catch(...){latched=true;}check(latched,"error restart");
 }
 std::cout<<"PASS initial rate, ready, absolute input gap, right-only motion, no overshoot, release latch, early engage\n";
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
