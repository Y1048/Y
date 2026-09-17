#include "offline_dispatch.hpp"
#include "offline_lag_fixture.hpp"
#include "hg_classes_only.hpp"
#include <iostream>
#include <chrono>
#include <atomic>
#include <mutex>
#include <thread>
#define NOMINMAX
#include <Windows.h>
using unitree_hg::msg::dds_::LowState_;
class OfflinePeriodicWait {
 HANDLE timer;
public:
 OfflinePeriodicWait():timer(CreateWaitableTimerExW(nullptr,nullptr,CREATE_WAITABLE_TIMER_HIGH_RESOLUTION,TIMER_ALL_ACCESS)){
  if(!timer)throw std::runtime_error("high_resolution_timer_create");
 }
 ~OfflinePeriodicWait(){CloseHandle(timer);}
 void Wait(){
  LARGE_INTEGER due;due.QuadPart=-20000; // Relative 2 ms, no global timer-resolution change.
  if(!SetWaitableTimer(timer,&due,0,nullptr,nullptr,FALSE)||WaitForSingleObject(timer,INFINITE)!=WAIT_OBJECT_0)
   throw std::runtime_error("high_resolution_timer_wait");
 }
};
struct OfflineThreadLifetime {
 std::atomic<bool> stop{false};std::thread thread;
 ~OfflineThreadLifetime(){stop=true;if(thread.joinable())thread.join();}
};
// Synthetic state fixture. The only external IO is local stdin/stdout JSON.
int main(){try{
 OfflineOwner owner;LowState_ state;state.mode_machine(5);state.wireless_remote()[2]=1;
 OfflineMemorySink sink;std::optional<OfflineDispatch> dispatch;bool use_dispatch=false;
 state.imu_state().quaternion()[0]=1;std::uint32_t tick=0;
 std::array<double,29> q{};for(std::size_t i=0;i<29;++i){q[i]=offline_twist2::kDefault[i];state.motor_state()[i].q(static_cast<float>(q[i]));}
 auto bytes=[&](){state.tick(++tick);std::vector<std::uint8_t>b(sizeof(state));std::memcpy(b.data(),&state,sizeof(state));
  state.crc(OfflineWordCrc({b.begin(),b.end()-4}));std::memcpy(b.data(),&state,sizeof(state));return b;};
 std::string line;
 bool realtime=false;std::chrono::steady_clock::time_point epoch;
 bool startup=false;double clock_base=2.02;
 nlohmann::json active_packet;
 std::mutex owner_mutex;bool autonomous=false,initialized=false;
 bool tracking_fixture=false;std::uint64_t active_steps=0;
 std::uint64_t background_ticks=0;
 double previous_background=0,max_background_gap=0,max_lock_wait=0;
 const auto Clock=[&](){return clock_base+std::chrono::duration<double>(std::chrono::steady_clock::now()-epoch).count();};
 OfflineThreadLifetime background; // Joined before captured state is destroyed.
 while(std::getline(std::cin,line)){
  auto in=nlohmann::json::parse(line);nlohmann::json out;const auto op=in.at("op").get<std::string>();
  std::unique_lock<std::mutex> owner_lock(owner_mutex);
  double now=in.value("now",0.);
  if(realtime)now=clock_base+std::chrono::duration<double>(std::chrono::steady_clock::now()-epoch).count();
  if(op=="init"){
   if(initialized)throw std::runtime_error("duplicate init");
   initialized=true;autonomous=in.value("autonomous_tick",false);
   tracking_fixture=in.value("tracking_fixture",false);
   if(tracking_fixture&&!autonomous)throw std::runtime_error("tracking fixture requires autonomous tick");
   if(autonomous&&(!in.value("dispatch",false)||!in.value("wall_clock",false)))
    throw std::runtime_error("autonomous tick requires wall clock and memory dispatch");
   dispatch.reset();sink=OfflineMemorySink{};use_dispatch=in.value("dispatch",false);
   startup=in.value("startup_blend",false);
   const bool fade=in.value("torque_fade",false);
   if(fade&&!tracking_fixture)throw std::runtime_error("torque fixture requires tracking fixture");
   owner=OfflineOwner(startup,fade);clock_base=startup?1:2.02;
   if(fade)for(std::size_t i=0;i<29;++i)state.motor_state()[i].tau_est(i%2?-.5F:.5F);
   for(int n=0;!startup&&n<102;++n){double t=1+n*.01;auto token=owner.Begin(bytes(),"hg_native_le2092_9754cd15",t,{},t);
    if(!token||!owner.Finish(*token,{},t+.001))throw std::runtime_error("fixture settle failed");}
   auto packet=in.at("packet");packet["all_joint_q_rad"]=q;
   packet["right_arm"]["joints"]=std::vector<double>(q.begin()+22,q.end());
   active_packet=packet;
   realtime=in.value("wall_clock",false);epoch=std::chrono::steady_clock::now();
   now=clock_base;
   auto token=owner.Begin(bytes(),"hg_native_le2092_9754cd15",now,
    startup?std::vector<ReceivedInput>{}:std::vector<ReceivedInput>{{packet.dump(),now}},now);
   if(!token||!owner.Observation())throw std::runtime_error("fixture begin failed");
   out["token"]=*token;out["observation"]=owner.Observation()->observation;
   if(autonomous)background.thread=std::thread([&](){try{
    OfflinePeriodicWait periodic;
    while(!background.stop){
     periodic.Wait();
     if(background.stop)break;
     const auto waiting=std::chrono::steady_clock::now();
     std::lock_guard<std::mutex> lock(owner_mutex);
     const double current=Clock();
     const double dt=background_ticks?current-previous_background:current-clock_base;
     max_lock_wait=std::max(max_lock_wait,std::chrono::duration<double>(std::chrono::steady_clock::now()-waiting).count());
     if(background_ticks)max_background_gap=std::max(max_background_gap,current-previous_background);
     previous_background=current;++background_ticks;
     if(!owner.Reason().empty())continue;
     try{
      // Synthetic sensor, NOT a cache refresh of real robot data.
      if(tracking_fixture&&sink.Last()){
       for(std::size_t i=0;i<29;++i){
        const double measured=state.motor_state()[i].q();
        const double step=OfflineLagStep(measured,sink.Last()->motors[i].q,dt);
        state.motor_state()[i].q(static_cast<float>(measured+step));
        state.motor_state()[i].dq(static_cast<float>(step/dt));
       }
      }
      owner.ReceiveState(bytes(),"hg_native_le2092_9754cd15",current,current);
      if(dispatch)dispatch->Pump(current);else owner.Tick(current);
     }catch(const std::exception& e){owner.Stop(e.what());}
    }
   }catch(const std::exception& e){std::lock_guard<std::mutex> lock(owner_mutex);owner.Stop(e.what());}});
  }else if(op=="begin"){
   active_packet["sequence"]=active_packet.at("sequence").get<std::uint64_t>()+1;
   const bool engage=!startup||owner.Phase()=="awaiting_alignment"||owner.Phase()=="active";
   if(tracking_fixture&&owner.Phase()=="active"){
    ++active_steps;active_packet["all_joint_q_rad"][22]=q[22]+.02;
    active_packet["right_arm"]["joints"][0]=q[22]+.02;
   }
   auto token=owner.Begin(bytes(),"hg_native_le2092_9754cd15",now,
    engage?std::vector<ReceivedInput>{{active_packet.dump(),now}}:std::vector<ReceivedInput>{},now);
   if(token){out["token"]=*token;out["observation"]=owner.Observation()->observation;}
  }else if(op=="state")out["accepted"]=owner.ReceiveState(bytes(),"hg_native_le2092_9754cd15",now,now);
  else if(op=="vr")out["accepted"]=owner.ReceiveVR(in.at("packet").dump(),now);
  else if(op=="release"){
   auto release=active_packet;release["sequence"]=release.at("sequence").get<std::uint64_t>()+1;
   release["input_command_mode"]="pinch_disengaged";
   out["accepted"]=owner.ReceiveVR(release.dump(),now);
  }
  else if(op=="status")out["accepted"]=false;
  else if(op=="tick")out["accepted"]=autonomous?false:(dispatch?dispatch->Pump(now):owner.Tick(now));
  else if(op=="finish"){
   out["accepted"]=owner.Finish(in.at("token"),in.at("action").get<std::array<float,29>>(),now);
   if(use_dispatch&&!dispatch&&owner.Writer()&&owner.Reason().empty())dispatch.emplace(owner,sink,now);
  }
  else throw std::runtime_error("unknown op");
  out["reason"]=owner.Reason();out["commits"]=owner.HistoryCommits();
  out["desired"]=owner.Desired()?nlohmann::json(owner.Desired()->q):nlohmann::json(nullptr);
  out["request_state"]=owner.RequestStateSequence();out["latest_state"]=owner.LatestStateSequence();
  out["writer_present"]=owner.Writer().has_value();
  out["event_time"]=now;
  out["phase"]=owner.Phase();
  out["tracking_fixture"]=tracking_fixture;out["active_steps"]=active_steps;
  std::array<float,29> measured{};for(std::size_t i=0;i<29;++i)measured[i]=state.motor_state()[i].q();
  out["measured_q"]=measured;
  std::array<float,29> feedforward{};
  if(owner.Writer())for(std::size_t i=0;i<29;++i)feedforward[i]=owner.Writer()->Diagnostics()[i].feedforward;
  out["writer_feedforward"]=feedforward;
  out["dispatch_enabled"]=use_dispatch;out["dispatch_count"]=sink.Count();
  out["dispatch_time"]=sink.Last()?nlohmann::json(sink.Last()->created_at):nlohmann::json(nullptr);
  out["dispatch_state"]=sink.Last()?nlohmann::json(sink.Last()->state_sequence):nlohmann::json(nullptr);
  out["handoff_required"]=!owner.Reason().empty()||(dispatch&&dispatch->HandoffRequired());
  out["autonomous_tick"]=autonomous;out["background_ticks"]=background_ticks;
  out["background_gap_ms_max"]=max_background_gap*1000;out["owner_lock_wait_ms_max"]=max_lock_wait*1000;
  out["dispatch_gap_ms_min"]=sink.Count()>1?nlohmann::json(sink.MinimumGap()*1000):nlohmann::json(nullptr);
  out["dispatch_gap_ms_max"]=sink.Count()>1?nlohmann::json(sink.MaximumGap()*1000):nlohmann::json(nullptr);
  owner_lock.unlock(); // Never block the periodic thread on stdout or JSON serialization.
  std::cout<<out.dump()<<std::endl;
 }
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
