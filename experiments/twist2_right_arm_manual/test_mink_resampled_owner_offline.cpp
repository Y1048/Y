#include "mink_cycle_owner_offline.hpp"
#include <iostream>
using O=MinkCycleOwnerOffline;
void Check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
struct IntegratedFixture {
 O::Q home{};O::Cycle::Arm low{},high{};
 bool full_path=true,checked=false;
 std::vector<std::uint8_t> bytes=std::vector<std::uint8_t>(2092);
 O owner;
 static O::Q Home(){O::Q q{};for(size_t i=0;i<29;++i)q[i]=(offline_twist2::kLower[i]+offline_twist2::kUpper[i])/2.;return q;}
 static O::Cycle::Arm Bounds(bool upper){O::Cycle::Arm a{};for(size_t i=0;i<7;++i)a[i]=(upper?offline_twist2::kUpper[i+22]:offline_twist2::kLower[i+22])+(upper?-.01:.01);return a;}
 IntegratedFixture():home(Home()),low(Bounds(false)),high(Bounds(true)),
  owner(home,low,high,0,{.01,.2,.2,4.,75.},[](const auto&,const auto&){return true;},
   [this](const auto& from,const auto& to){checked=true;Check(std::abs(from[22]-home[22])<1e-6,"not measured start");Check(to[0]!=home[0],"legs not composed");return full_path;},true){
  bytes[9]=5;bytes[2034]=1;
  for(size_t i=0;i<29;++i)Float(72+i*56+4,home[i]);
  Float(16,1.);Tick(1);
 }
 void U32(size_t at,std::uint32_t v){for(size_t i=0;i<4;++i)bytes[at+i]=static_cast<std::uint8_t>((v>>(i*8))&255);}
 void Float(size_t at,double d){float f=static_cast<float>(d);std::uint32_t v;std::memcpy(&v,&f,4);U32(at,v);}
 void Tick(std::uint32_t tick){U32(12,tick);Crc();}
 void Crc(){U32(2088,OfflineWordCrc({bytes.begin(),bytes.end()-4}));}
 bool Observe(double now=.01){return owner.Observe(bytes,"hg_native_le2092_9754cd15",now,now);}
 std::string Packet(){O::Cycle::Arm q{};for(size_t i=0;i<7;++i)q[i]=home[i+22];
  return nlohmann::json{{"schema","g1.mink.cycle.offline.v1"},{"provenance","offline_only"},
   {"profile","right_arm_90_180_a60"},{"session","owner"},{"sequence",1},{"epoch",0},
   {"source_age_s",0.},{"event","idle"},{"joints",q}}.dump();}
 O::PolicyPositions Policy(double at=.01){O::PolicyPositions p;p.created=at;p.state_sequence=owner.StateSequence();for(size_t i=0;i<12;++i)p.q[i]=home[i]+.01;return p;}
 void Start(){Check(Observe(),"observe");Check(owner.Receive(Packet(),.01),"receive");Check(owner.Compose(Policy(),.01),"compose");}
 void Stopped(const char* reason){Check(owner.Reason()==reason,"wrong stop reason");Check(!owner.Candidate(),"reference survives stop");Check(!owner.Compose(Policy(),.011),"stop not latched");}
};

int main(){try{
 unsigned scenarios=0;
 for(const std::string release:{"pinch","tracking_disengaged"})for(bool moving_feedback:{false,true}){
  IntegratedFixture f;unsigned input=1,state_tick=0;double observed=-1,output_home=-1,waiting=-1;
  bool returned=false,reengaged=false,idle_sent=false;O::Cycle::Arm previous_velocity{};
  auto observe=[&](double now){if(now>observed){f.Float(72+22*56+8,moving_feedback&&now<2.7?.1:0.);f.Tick(++state_tick);Check(f.Observe(now),"integrated observe");observed=now;}};
  for(unsigned tick=0;tick<=2000;++tick){double now=tick*.002;
   while(input/60.<=now){double source=input/60.;observe(source);
    auto packet=nlohmann::json::parse(f.Packet());packet["sequence"]=input;packet["epoch"]=f.owner.Epoch();
    std::string event;
    if(input==1)event="idle";
    else if(input==2)event="active";
    else if(!returned){
     event=input<62?"active":input==62?release:"return";
     double t=std::min((input-2)/60.,2.);packet["joints"][0]=f.home[22]+.03*(1-std::cos(3.141592653589793*t));
    }else event=reengaged?"active":"idle";
    if(returned&&!reengaged&&idle_sent){event="active";reengaged=true;}
    packet["event"]=event;
    if(!f.owner.Receive(packet.dump(),source))throw std::runtime_error("input "+std::to_string(input)+" "+f.owner.Reason());
    if(!returned&&input>62&&f.owner.Mode()==O::Cycle::State::Waiting){
     returned=true;waiting=source;if(moving_feedback)Check(waiting>=3.18,"moving feedback ACK");Check(output_home>=0&&waiting-output_home>=.49,"premature return ACK");
    }
    if(returned&&event=="idle")idle_sent=true;
    ++input;
   }
   observe(now);
   if(!f.owner.Compose(f.Policy(now),now))throw std::runtime_error("compose "+std::to_string(tick)+" "+f.owner.Reason());
   const auto& reference=*f.owner.Candidate();
   for(size_t i=0;i<29;++i)if(i<22)Check(reference.q[i]==(i<12?f.home[i]+.01:f.home[i]),"ownership");
   for(size_t i=0;i<7;++i){Check(std::abs(reference.velocity[i]-previous_velocity[i])<=O::Cycle::acceleration*.002+1e-6,"composed acceleration");}
   previous_velocity=reference.velocity;
   if(now>1.&&std::abs(reference.q[22]-f.home[22])<1e-6&&std::abs(reference.velocity[0])<1e-6&&output_home<0)output_home=now;
  }
  Check(returned&&reengaged&&f.owner.Mode()==O::Cycle::State::Tracking,"cycle not reengaged");++scenarios;
 }
 {IntegratedFixture f;Check(f.Observe(0),"initial state");Check(f.owner.Compose(f.Policy(0),0),"initial compose");f.Tick(2);Check(f.Observe(.004),"state");Check(!f.owner.Compose(f.Policy(.004),.004),"missed tick accepted");f.Stopped("output_grid");++scenarios;}
 {IntegratedFixture f;Check(f.Observe(0),"initial state");Check(f.owner.Compose(f.Policy(0),0),"initial compose");f.full_path=false;f.Tick(2);Check(f.Observe(.002),"state");Check(!f.owner.Compose(f.Policy(.002),.002),"full geometry bypassed");f.Stopped("full_body_path_rejected");++scenarios;}
 {IntegratedFixture f;Check(f.Observe(0),"initial state");Check(f.owner.Compose(f.Policy(0),0),"initial compose");Check(!f.owner.Poll(.001,true),"emergency stop bypassed");f.Stopped("operator_stop");++scenarios;}
 {IntegratedFixture f;Check(f.Observe(0),"initial state");Check(f.owner.Compose(f.Policy(0),0),"initial compose");
  for(unsigned n=1;n<=40;++n){double now=n/60.;f.Tick(n+1);Check(f.Observe(now),"fresh feedback");
   auto packet=nlohmann::json::parse(f.Packet());packet["sequence"]=n;packet["epoch"]=f.owner.Epoch();
   packet["event"]=n==1?"idle":n==2?"active":n==3?"pinch":"return";
   Check(f.owner.Receive(packet.dump(),now),"return hold input");
  }
  Check(f.owner.Mode()==O::Cycle::State::Returning,"stale output acknowledged return");++scenarios;
 }
 std::cout<<"PASS "<<scenarios<<" resampled owner scenarios; four return ACK/re-engage cycles; no publisher\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
