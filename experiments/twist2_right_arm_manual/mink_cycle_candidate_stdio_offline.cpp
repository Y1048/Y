// Local test pipe only. "path_checked" is supplied by the offline model harness,
// never a trustworthy authorization field for a network/hardware adapter.
#include "mink_cycle_candidate_offline.hpp"
#include <iostream>
int main(){try{
 using C=MinkCycleCandidateOffline;using J=nlohmann::json;
 std::string line;if(!std::getline(std::cin,line))return 1;
 auto init=J::parse(line);bool checked=false;
 C cycle(init.at("home").get<C::Q>(),init.at("lower").get<C::Arm>(),
  init.at("upper").get<C::Arm>(),0,[&](const C::Q&,const C::Q&){return checked;});
 while(std::getline(std::cin,line)){
  auto x=J::parse(line);checked=x.at("path_checked").get<bool>();
  C::Feedback f{x.at("measured").get<C::Q>(),x.at("dq").get<C::Q>(),x.at("feedback_received").get<double>()};
  C::Controls controls{x.at("r1").get<bool>(),x.at("stop").get<bool>()};
  const bool accepted=cycle.Receive(x.at("packet").dump(),x.at("time").get<double>(),f,controls);
  const auto state=cycle.Mode();
  std::cout<<J{{"accepted",accepted},{"epoch",cycle.Epoch()},{"reason",cycle.Reason()},
   {"state",state==C::State::Waiting?"waiting":state==C::State::Tracking?"tracking":state==C::State::Returning?"returning":"stopped"},
   {"q",cycle.Target()},{"velocity",cycle.Velocity()}}.dump()<<std::endl;
 }
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
