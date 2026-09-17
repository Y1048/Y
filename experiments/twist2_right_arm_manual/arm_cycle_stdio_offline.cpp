// Local pipe adapter for synthetic integration tests. No SDK/socket/robot access.
#include "arm_cycle_offline.hpp"
#include "vendor/json.hpp"
#include <iostream>
int main(){
 using C=ArmCycleOffline;using J=nlohmann::json;
 C::Q home{},zero{};C cycle(home,0);
 std::string line;
 try{
  while(std::getline(std::cin,line)){
   const auto x=J::parse(line);
   const auto event=x.at("event").get<std::string>();
   C::Event e=C::Event::Fault;
   if(event=="idle")e=C::Event::Idle;
   else if(event=="active")e=C::Event::Active;
   else if(event=="pinch")e=C::Event::Pinch;
   else if(event=="none")e=C::Event::None;
   const auto input=x.at("joints").get<C::Arm>();
   // Ideal previous-target feedback ONLY. This is not LowState simulation.
   cycle.Tick(x.at("time").get<double>(),e,input,cycle.Target(),zero);
   const auto state=cycle.State();
   const char* name=state==C::Mode::Waiting?"waiting":state==C::Mode::Tracking?"tracking":state==C::Mode::Returning?"returning":"stopped";
   std::cout<<J{{"state",name},{"q",cycle.Target()},{"reason",cycle.Reason()}}.dump()<<std::endl;
  }
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
