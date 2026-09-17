// Test-only protocol sink. No transport/SDK/publisher.
#include "mink_live_cycle_contract.hpp"
#include <iostream>
int main(){try{
 using C=MinkLiveCycleContract;using J=nlohmann::json;std::string line;
 if(!std::getline(std::cin,line))return 1;auto config=J::parse(line);
 C::Q home=config.at("home").get<C::Q>();C::Arm lo{},hi{};lo.fill(-3);hi.fill(3);
 C c(home,lo,hi,0,[](const auto&,const auto&){return true;},config.at("profile"));
 while(std::getline(std::cin,line)){
  auto x=J::parse(line);double now=x.at("now");C::Feedback f{x.at("q").get<C::Q>(),x.at("dq").get<C::Q>(),now};
  bool ok=c.Receive(x.at("packet").dump(),now,f,{false});
  const char* state=c.Mode()==C::State::Waiting?"waiting":c.Mode()==C::State::Returning?"returning":c.Mode()==C::State::Tracking?"tracking":"stopped";
  std::cout<<J{{"accepted",ok},{"reason",c.Reason()},{"state",state},{"epoch",c.Epoch()},{"session",c.Session()},{"q",c.Target()}}.dump()<<std::endl;
 }
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
