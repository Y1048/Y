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
  owner(home,low,high,0,{.01,.2,.2,4.,75.},[](const auto&,const auto&){return true;},
   [this](const auto& from,const auto& to){checked=true;Check(std::abs(from[22]-home[22])<1e-6,"not measured start");Check(to[0]!=home[0],"legs not composed");return full_path;}){
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
 unsigned count=0;
 {Fixture f;f.Start();auto q=f.owner.Candidate()->q;for(size_t i=0;i<29;++i)Check(q[i]==(i<12?f.home[i]+.01:f.home[i]),"joint ownership");Check(f.checked,"path not checked");++count;}
 {Fixture f;Check(!f.owner.Receive(f.Packet(),.01),"missing state accepted");f.Stopped("missing_measured_state");++count;}
 {Fixture f;f.bytes[80]^=1;Check(!f.Observe(),"bad crc");f.Stopped("crc_mismatch");++count;}
 {Fixture f;f.bytes[2034]=0;f.Crc();Check(!f.Observe(),"R1 release");f.Stopped("operator_stop");++count;}
 {Fixture f;f.bytes[2035]=2;f.Crc();Check(!f.Observe(),"B stop");f.Stopped("operator_stop");++count;}
 {Fixture f;f.U32(72+36,1);f.Crc();Check(!f.Observe(),"motor fault");f.Stopped("motor_health");++count;}
 {Fixture f;f.Start();Check(!f.owner.Poll(.031),"stale state");f.Stopped("state_timeout");++count;}
 {Fixture f;f.Start();Check(f.Observe(.02),"duplicate tick short");Check(!f.Observe(.031),"frozen tick");f.Stopped("robot_tick_stalled");++count;}
 {Fixture f;f.Start();f.Tick(0);Check(!f.Observe(.02),"reverse tick");f.Stopped("robot_tick_discontinuity");++count;}
 {Fixture f;f.Start();auto p=f.Policy();p.state_sequence=0;Check(!f.owner.Compose(p,.01),"stale policy state");f.Stopped("policy_state_mismatch");++count;}
 {Fixture f;f.Start();Check(!f.owner.Compose(f.Policy(.02),.01),"future policy");f.Stopped("policy_time");++count;}
 {Fixture f;f.Start();Check(!f.owner.Compose(f.Policy(),.021),"expired policy");f.Stopped("policy_time");++count;}
 {Fixture f;f.Start();f.full_path=false;Check(!f.owner.Compose(f.Policy(),.01),"unchecked full path");f.Stopped("full_body_path_rejected");++count;}
 {Fixture f;f.Start();auto p=f.Policy();p.q[1]=100;Check(!f.owner.Compose(p,.01),"bad leg target");f.Stopped("reference_joint_limit");++count;}
 {Fixture f;f.Start();Check(!f.owner.Poll(.011,true),"keyboard stop");f.Stopped("operator_stop");++count;}
 {Fixture f;f.Start();f.Tick(2);Check(f.Observe(.012),"new state");Check(!f.owner.Candidate(),"old reference retained");++count;}
 {Fixture f;f.Start();Check(!f.owner.Poll(.009),"reverse clock");f.Stopped("clock");++count;}
 {Fixture f;f.Start();bool stopped=false;for(unsigned i=2;i<=28;++i){f.Tick(i);if(!f.Observe(i*.01)){stopped=true;break;}}Check(stopped,"input timeout absent");f.Stopped("input_timeout");++count;}
 {Fixture f;f.Start();auto p=f.Policy();p.q[0]=std::numeric_limits<double>::quiet_NaN();Check(!f.owner.Compose(p,.01),"nan policy");f.Stopped("reference_joint_limit");++count;}
 {Fixture f;Check(!f.owner.Observe(f.bytes,"DDS_CDR",.01,.01),"wrong ABI profile");f.Stopped("unsupported_layout");++count;}
 std::cout<<"PASS "<<count<<" offline native-feedback / owner composition scenarios; no publisher\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
