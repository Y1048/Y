// Batch mathematical fixture generator. Outputs must be geometry-checked by
// the local replay before acceptance. Never a network/physical writer adapter.
#include "mink_resampler_offline.hpp"
#include <iostream>
int main(){try{
 using J=nlohmann::json;using R=MinkResamplerOffline;J input;std::cin>>input;
 R r(input.at("home").get<R::Q>(),input.at("lower").get<R::Arm>(),input.at("upper").get<R::Arm>(),0,
  [](const auto&,const auto&){return true;});
 const auto& samples=input.at("samples");size_t index=0;
 const auto ticks=static_cast<unsigned long long>(std::floor(static_cast<double>(samples.size())*R::input_dt/R::output_dt));
 J output=J::array();
 for(unsigned long long tick=0;tick<=ticks;++tick){double now=static_cast<double>(tick)*R::output_dt;
  while(index<samples.size()&&static_cast<double>(index+1)*R::input_dt<=now+1e-10){
   double source=static_cast<double>(index+1)*R::input_dt;
   if(!r.Push(samples[index].get<R::Arm>(),index+1,source,source))throw std::runtime_error(r.Reason());++index;
  }
  if(!r.Step(now,true))throw std::runtime_error(r.Reason());
  const auto& s=*r.Output();output.push_back(J{{"time",now},{"q",s.q},{"velocity",s.velocity},{"acceleration",s.acceleration}});
 }
 std::cout<<J{{"offline_only",true},{"geometry_checked",false},{"outputs",output}}.dump()<<'\n';
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
