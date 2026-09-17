// Local pipe fixture: synthetic LowState and permissive geometry callback.
// Actual Torch inference runs in Python. No transport, SDK or physical output.
#include "mink_cycle_owner_offline.hpp"
#include "offline_observation_history.hpp"
#include <iostream>
using O=MinkCycleOwnerOffline;using J=nlohmann::json;
int main(){try{
 O::Q ready{};for(size_t i=0;i<29;++i)ready[i]=offline_twist2::kDefault[i];
 O::Cycle::Arm low{},high{};for(size_t i=0;i<7;++i){low[i]=offline_twist2::kLower[i+22]+.05;high[i]=offline_twist2::kUpper[i+22]-.05;}
 O owner(ready,low,high,0,{.025,.2,.2,4.,75.},[](const auto&,const auto&){return true;},[](const auto&,const auto&){return true;},true);
 OfflineObservationHistory history;O::Q measured=ready,mimic_target=ready,command=ready,velocity{};
 std::array<double,3> imu_gyro{},imu_rpy{},imu_acc{};std::array<double,4> imu_quat{1,0,0,0};bool dynamics=false;
 J arm_samples=J::array(),trace=J::array();bool combined=false;
 std::vector<std::uint8_t> bytes(2092);bytes[9]=5;bytes[2034]=1;
 auto u32=[&](size_t at,std::uint32_t v){for(size_t i=0;i<4;++i)bytes[at+i]=static_cast<std::uint8_t>((v>>(8*i))&255);};
 auto number=[&](size_t at,double x){float f=static_cast<float>(x);std::uint32_t v;std::memcpy(&v,&f,4);u32(at,v);};number(16,1.);
 unsigned ticks=0,input=1,state_tick=0,outputs=0;double observed=-1;
 auto require=[&](bool ok){if(!ok)throw std::runtime_error(owner.Reason());};
 auto observe=[&](double now){if(now<=observed)return;
  if(dynamics){
   std::cout<<J{{"dynamics",true},{"time",now},{"command",command},{"home",ready}}.dump()<<std::endl;
   std::string reply;if(!std::getline(std::cin,reply))throw std::runtime_error("missing dynamics state");
   auto state=J::parse(reply);if(std::abs(state.at("time").get<double>()-now)>1e-9)throw std::runtime_error("dynamics time");
   measured=state.at("q").get<O::Q>();velocity=state.at("dq").get<O::Q>();
   imu_gyro=state.at("gyro").get<std::array<double,3>>();imu_rpy=state.at("rpy").get<std::array<double,3>>();
   imu_acc=state.at("acc").get<std::array<double,3>>();imu_quat=state.at("quat").get<std::array<double,4>>();
  }
  for(size_t i=0;i<29;++i){number(72+i*56+4,measured[i]);number(72+i*56+8,velocity[i]);}
  for(size_t i=0;i<3;++i){number(32+i*4,imu_gyro[i]);number(44+i*4,imu_acc[i]);number(56+i*4,imu_rpy[i]);}
  for(size_t i=0;i<4;++i)number(16+i*4,imu_quat[i]);u32(12,++state_tick);u32(2088,OfflineWordCrc({bytes.begin(),bytes.end()-4}));require(owner.Observe(bytes,"hg_native_le2092_9754cd15",now,now));observed=now;};
 auto prepare=[&](double now){while(input/60.<=now){double source=input/60.;observe(source);O::Cycle::Arm arm{};for(size_t i=0;i<7;++i)arm[i]=ready[i+22];
  if(combined){if(input>arm_samples.size())throw std::runtime_error("arm fixture exhausted");arm=arm_samples[input-1].get<O::Cycle::Arm>();}
  for(size_t i=0;i<7;++i)mimic_target[i+22]=arm[i];
  J packet={{"schema","g1.mink.cycle.offline.v1"},{"provenance","offline_only"},{"profile","right_arm_90_180_a60"},{"session","torch-fixture"},{"sequence",input},{"epoch",0},{"source_age_s",0.},{"event",combined&&input>1?"active":"idle"},{"joints",arm}};
  require(owner.Receive(packet.dump(),source));++input;}observe(now);};
 auto output=[&](double now){require(owner.ComposeHeldPolicy(now));command=owner.Candidate()->q;if(!dynamics)measured=command;++outputs;if(combined)trace.push_back(J{{"time",now},{"q",command},{"measured_q",measured},{"measured_dq",velocity},{"rpy",imu_rpy}});};
 std::optional<O::PolicyTicket> ticket;std::string line;
 while(std::getline(std::cin,line)){
  auto request=J::parse(line);std::string op=request.at("op").get<std::string>();
  if(op=="configure_combined"){
   if(observed>=0||combined)throw std::runtime_error("late fixture configuration");
   ready=request.at("home").get<O::Q>();for(size_t i=0;i<12;++i)ready[i]=offline_twist2::kDefault[i];
   arm_samples=request.at("samples");if(!arm_samples.is_array()||arm_samples.empty())throw std::runtime_error("missing arm samples");
   measured=mimic_target=command=ready;combined=true;dynamics=request.value("dynamics",false);
   owner=O(ready,low,high,0,{.025,.2,.2,4.,75.},[](const auto&,const auto&){return true;},[](const auto&,const auto&){return true;},true);
   std::cout<<J{{"configured",true},{"geometry_checked",false},{"ready",ready}}.dump()<<std::endl;
  }else if(op=="begin"){
   if(ticket)throw std::runtime_error("pending fixture request");
   unsigned next=request.at("tick").get<unsigned>();if(next%10||next<ticks)throw std::runtime_error("policy grid");
   while(ticks<next){++ticks;prepare(ticks*.002);output(ticks*.002);}
   prepare(ticks*.002);ticket=owner.BeginPolicy(ticks*.002);require(bool(ticket));
   std::array<float,29> q{},dq{},mimic{};std::array<float,3> gyro{},rpy{};
   for(size_t i=0;i<29;++i){q[i]=static_cast<float>(ticket->snapshot.sample.q[i]);dq[i]=static_cast<float>(ticket->snapshot.sample.dq[i]);mimic[i]=static_cast<float>(mimic_target[i]);}
   for(size_t i=0;i<3;++i){gyro[i]=static_cast<float>(ticket->snapshot.gyro[i]);rpy[i]=static_cast<float>(ticket->snapshot.health.rpy[i]);}
   auto frame=history.Build(q,dq,gyro,rpy,mimic);
   std::cout<<J{{"observation",frame.observation},{"request_id",ticket->id},{"state_sequence",ticket->snapshot.sample.sequence}}.dump()<<std::endl;
  }else if(op=="finish"){
   if(!ticket)throw std::runtime_error("no request");
   unsigned latency=request.at("latency_ticks").get<unsigned>();if(latency>20)throw std::runtime_error("latency bound");
   unsigned finish=ticks+latency;
   while(ticks+1<finish){++ticks;prepare(ticks*.002);output(ticks*.002);}
   if(ticks<finish){++ticks;prepare(ticks*.002);}
   O::PolicyPositions policy;policy.state_sequence=ticket->snapshot.sample.sequence;policy.created=ticks*.002;
   const auto& action=request.at("action");if(!action.is_array()||action.size()!=29)throw std::runtime_error("action shape");
   for(size_t i=0;i<29;++i){if(!action[i].is_number())throw std::runtime_error("action type");float a=action[i].get<float>();if(!std::isfinite(a))throw std::runtime_error("action finite");a=std::clamp(a,-2.F,2.F);
    if(i<12)policy.q[i]=std::clamp(offline_twist2::kDefault[i]+offline_twist2::kActionScale*a,offline_twist2::kLower[i]+offline_twist2::kJointLimitMargin,offline_twist2::kUpper[i]-offline_twist2::kJointLimitMargin);}
   // Dynamics fixture reproduces a four-second leg reference blend, not an
   // instantaneous policy step. This is not the physical takeover implementation.
   if(dynamics){double a=std::clamp(ticks*.002/4.,0.,1.);a=a*a*(3.-2.*a);for(size_t i=0;i<12;++i)policy.q[i]=ready[i]+a*(policy.q[i]-ready[i]);}
   require(owner.SubmitPolicy(ticket->id,policy,ticks*.002));
   // Bootstrap defines output epoch after initial inference; subsequent finish
   // happens before that tick's output, with prior outputs continuing normally.
   if(latency||outputs==0)output(ticks*.002);
   history.Commit(command);ticket.reset();
   std::cout<<J{{"accepted",true},{"outputs",outputs},{"history_commits",history.Commits()},{"q",command},{"geometry_checked",false},{"trace",trace}}.dump()<<std::endl;trace=J::array();
  }else throw std::runtime_error("unknown op");
 }
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
