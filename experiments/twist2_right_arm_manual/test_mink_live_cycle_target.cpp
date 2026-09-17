#include "mink_live_cycle_target.hpp"
#include <iostream>
int main(){try{
#ifdef _WIN32
 _putenv_s("G1_MINK_SPEED_PROFILE","today");
#else
 setenv("G1_MINK_SPEED_PROFILE","today",1);
#endif
 using C=MinkLiveCycleContract;C::Q q{},dq{};constexpr double r=.017453292519943295;
 const std::array<double,14> pose={10*r,22*r,0,55*r,0,0,0,10*r,-22*r,0,55*r,0,0,0};
 for(size_t i=15;i<29;++i)q[i]=pose[i-15];double now=0;
 MinkLiveCycleTarget t(q,now,[&](){return now;},true);
 for(int n=1;n<=40;++n){now=n*.02;auto lag=q;lag[22]+=.1;t.Feedback(lag,dq,now);t.Update(now,true);}
 auto blocked=t.Acknowledgement(std::string(32,'a'));
 if(blocked.at("ready_blockers").empty()||blocked.at("ready_blockers")[0].at("joint")!=22)throw std::runtime_error("missing blocker diagnostic");
 if(t.Ready())throw std::runtime_error("initial ready used model instead of measured state");
 for(int n=41;n<=75;++n){now=n*.02;auto offset=q;offset[16]-=.0692;offset[23]+=.0768;offset[18]+=.0266;offset[25]+=.0268;offset[26]-=.020062;t.Feedback(offset,dq,now);t.Update(now,true);}
 if(!t.Ready()||t.Phase()!="udp_ready")throw std::runtime_error("measured initialization did not settle");
 auto ack=t.Acknowledgement(std::string(32,'a'));
 if(ack.at("state")!="waiting"||ack.at("profile")!="today")throw std::runtime_error("ack");
 now+=.06;if(t.Poll(now)!="feedback_timeout")throw std::runtime_error("stale measured feedback continued");
 std::cout<<"PASS measured initialization, ACK and stale feedback wrapper checks; no output\n";
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
