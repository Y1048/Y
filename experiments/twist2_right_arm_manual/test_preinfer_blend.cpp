#include "offline_blend.hpp"
#include "guarded_composition_offline.hpp"
#include <iostream>
void Check(bool ok) {if(!ok) throw std::runtime_error("check_failed");}
int main()
{
 try
 {
  std::array<double,29> baseline{},hybrid{};
  for(std::size_t i=0;i<29;++i) {baseline[i]=offline_twist2::kDefault[i];hybrid[i]=baseline[i]+.1;}
  for(int n=0;n<=600;++n)
  {
   const double elapsed=n*.01;
   float x=std::clamp(static_cast<float>((elapsed-1)/4),0.0F,1.0F);
   float alpha=x*x*(3-2*x);
   Check(OfflineBlendAlpha(elapsed,1,4)==alpha);
   auto mimic=OfflineMimic(baseline,hybrid,alpha);auto desired=OfflineBlendDesired(baseline,hybrid,alpha);
   for(std::size_t i=0;i<29;++i)
   {
    Check(mimic[i]==(i<12?(1-alpha)*static_cast<float>(baseline[i])+alpha*offline_twist2::kDefault[i]:static_cast<float>(hybrid[i])));
    Check(desired[i]==(1-alpha)*static_cast<float>(baseline[i])+alpha*static_cast<float>(hybrid[i]));
   }
  }
  std::string input;std::getline(std::cin,input);auto packet=nlohmann::json::parse(input);
  packet["all_joint_q_rad"]=baseline;std::array<double,7> goal{};
  for(std::size_t i=0;i<7;++i) {goal[i]=baseline[i+22]+.01;packet["all_joint_q_rad"][i+22]=goal[i];}
  packet["right_arm"]["joints"]=goal;
  OfflineStateHealth h;h.crc_verified=true;h.mode_pr=0;h.mode_machine=5;h.deadman=true;h.emergency_stop=false;
  for(const std::string fault:{"none","late","duplicate","policy","abort","early_policy"})
  {
   GuardedCompositionOffline study({.03,.039,.1,.01,.025,.25,.17},{.01,.15,.15,1.5,75});
   for(std::uint64_t n=1;n<=3;++n)
   {
    const double now=static_cast<double>(n)*.02;
    OfflineStateSample state{baseline,{},n,now};OfflinePolicySample policy{{},n,n,now};
    Check(study.Tick(state,h,policy,{},now)!="stopped");
   }
   OfflineStateSample state{baseline,{},4,.08};OfflinePolicySample policy{{},4,4,.081};
   Check(study.Prepare(state,h,{{packet.dump(),.08}},.081)=="active");
   Check(!study.Candidate() && study.PreparedUpper());
   const auto prepared=*study.PreparedUpper();Check(prepared[22]>baseline[22]);
   auto mimic=OfflineMimic(baseline,prepared,1);Check(mimic[22]==static_cast<float>(prepared[22]));
   std::string result;
   if(fault=="late") result=study.Finish(policy,.12);
   else if(fault=="duplicate") result=study.Prepare(state,h,{},.082);
   else if(fault=="policy") {policy.action[0]=3;result=study.Finish(policy,.081);}
   else if(fault=="abort") result=study.Abort("release_during_inference");
   else if(fault=="early_policy") {policy.created_at=.08;result=study.Finish(policy,.081);}
   else result=study.Finish(policy,.081);
   if(fault=="none") {Check(result=="active" && study.Candidate());Check((*study.Candidate())[22]==prepared[22]);}
   else {Check(result=="stopped" && !study.Candidate());Check(study.Finish(policy,.082)=="stopped");}
  }
  std::cout<<"PASS 601 blend points; 6 transactional prepare/finish cases\n";
 }
 catch(const std::exception& e) {std::cerr<<e.what();return 2;}
}
