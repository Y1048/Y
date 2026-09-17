#include "mink_cycle_owner_offline.hpp"
#include <iostream>
using O=MinkCycleOwnerOffline;
void Check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
struct Fixture {
 O::Q home{};O::Cycle::Arm low{},high{};
 bool full_path=true,checked=false;
 std::vector<std::uint8_t> bytes=std::vector<std::uint8_t>(2092);
 O owner;
 static O::Q Home(){O::Q q{};for(size_t i=0;i<29;++i)q[i]=(offline_twist2::kLower[i]+offline_twist2::kUpper[i])/2.;return q;}
 static O::Cycle::Arm Bounds(bool upper){O::Cycle::Arm a{};for(size_t i=0;i<7;++i)a[i]=(upper?offline_twist2::kUpper[i+22]:offline_twist2::kLower[i+22])+(upper?-.01:.01);return a;}
 Fixture():home(Home()),low(Bounds(false)),high(Bounds(true)),
  owner(home,low,high,0,{.025,.2,.2,4.,75.},[](const auto&,const auto&){return true;},
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


void StartPolicy(Fixture& f){Check(f.Observe(0),"initial state");auto ticket=f.owner.BeginPolicy(0);Check(bool(ticket),"begin");Check(f.owner.SubmitPolicy(ticket->id,f.Policy(0),0),"submit");Check(f.owner.ComposeHeldPolicy(0),"initial output");}
int main(){try{
 unsigned tests=0;
 {Fixture f;unsigned input=1,tick_state=0,requests=0;double observed=-1;
  std::optional<O::PolicyTicket> pending;O::PolicyPositions submitted;
  auto observe=[&](double now){if(now>observed){f.Tick(++tick_state);Check(f.Observe(now),"observe");observed=now;}};
  for(unsigned tick=0;tick<=200;++tick){double now=tick*.002;
   while(input/60.<=now){double source=input/60.;observe(source);auto packet=nlohmann::json::parse(f.Packet());packet["sequence"]=input;Check(f.owner.Receive(packet.dump(),source),"input");++input;}
   observe(now);
   if(tick%10==0){pending=f.owner.BeginPolicy(now);Check(bool(pending),"policy start");++requests;}
   if(pending&&(tick==0||tick%10==1)){
    auto policy=f.Policy(now);policy.state_sequence=pending->snapshot.sample.sequence;
    for(auto& q:policy.q)q+=requests*.0001;
    Check(f.owner.SubmitPolicy(pending->id,policy,now),"delayed policy completion");submitted=policy;pending.reset();
   }
   Check(f.owner.ComposeHeldPolicy(now),"500Hz held output");auto r=*f.owner.Candidate();
   Check(r.state_sequence==f.owner.StateSequence(),"output feedback not fresh");
   Check(r.policy_state_sequence==submitted.state_sequence&&r.policy_created==submitted.created,"policy provenance restamped");
   for(size_t i=0;i<29;++i){double expected=i<12?submitted.q[i]:f.home[i];Check(i<22?r.q[i]==expected:std::abs(r.q[i]-expected)<1e-12,"ownership");}
  }
  Check(requests==21,"not 50Hz requests");++tests;
 }
 {Fixture f;StartPolicy(f);f.Tick(2);Check(f.Observe(.01),"state");f.Tick(3);Check(f.Observe(.02),"state");f.Tick(4);Check(f.Observe(.026),"state");Check(!f.owner.ComposeHeldPolicy(.026),"expired reused");f.Stopped("policy_expired");++tests;}
 {Fixture f;Check(f.Observe(0),"state");Check(!f.owner.ComposeHeldPolicy(0),"missing policy");f.Stopped("missing_policy");++tests;}
 {Fixture f;StartPolicy(f);Check(!f.owner.SubmitPolicy(1,f.Policy(0),0),"duplicate completion");f.Stopped("policy_request_mismatch");++tests;}
 {Fixture f;Check(f.Observe(0),"state");auto t=f.owner.BeginPolicy(0);auto p=f.Policy(0);p.state_sequence=999;Check(!f.owner.SubmitPolicy(t->id,p,0),"wrong snapshot");f.Stopped("policy_state_mismatch");++tests;}
 {Fixture f;Check(f.Observe(0),"state");auto t=f.owner.BeginPolicy(0);Check(!f.owner.SubmitPolicy(t->id,f.Policy(.001),0),"future result");f.Stopped("policy_time");++tests;}
 {Fixture f;StartPolicy(f);f.Tick(2);Check(f.Observe(.002),"fresh state");f.full_path=false;Check(!f.owner.ComposeHeldPolicy(.002),"geometry not refreshed");f.Stopped("full_body_path_rejected");++tests;}
 {Fixture f;StartPolicy(f);f.bytes[2034]=0;f.Tick(2);Check(!f.Observe(.002),"R1 ignored during reuse");f.Stopped("operator_stop");++tests;}
 {Fixture f;Check(f.Observe(0),"state");Check(bool(f.owner.BeginPolicy(0)),"begin");Check(!f.owner.BeginPolicy(0),"overlapping request");f.Stopped("policy_request_pending");++tests;}
 {Fixture f;Check(f.Observe(0),"state");auto t=f.owner.BeginPolicy(0);auto p=f.Policy(0);p.q[0]=100;Check(!f.owner.SubmitPolicy(t->id,p,0),"invalid policy cached");f.Stopped("reference_joint_limit");++tests;}
 {Fixture f;Check(f.Observe(0),"state");auto t=f.owner.BeginPolicy(.018);f.Tick(2);Check(f.Observe(.02),"new state");auto p=f.Policy(.024);p.state_sequence=t->snapshot.sample.sequence;Check(f.owner.SubmitPolicy(t->id,p,.024),"inference input preserved");f.Tick(3);Check(f.Observe(.026),"new state");Check(!f.owner.ComposeHeldPolicy(.026),"age based only on completion");f.Stopped("policy_expired");++tests;}
 std::cout<<"PASS "<<tests<<" 50Hz-policy / 500Hz-owner scenarios; 201 output ticks; no inference or publisher\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
