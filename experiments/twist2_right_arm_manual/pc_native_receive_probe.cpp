// Receive-only PC probe. No command publisher or MotionSwitcher is constructed.
#include "twist2_common.hpp"
#include "native_state_tick.hpp"
#include <unitree/robot/channel/channel_subscriber.hpp>
#include <atomic>
#include <fstream>
#include <iostream>
#include <mutex>
#include <thread>
using namespace twist2;
struct Snapshot {LowState state{};Clock::time_point receipt{};bool present=false;};
int main(int argc,char** argv){try{
 if(argc!=4)throw std::runtime_error("Usage: probe interface policy.pt NEW_OUTPUT_DIRECTORY");
 const std::filesystem::path output(argv[3]);
 if(!std::filesystem::create_directory(output))throw std::runtime_error("new output directory required");
 Policy policy{std::filesystem::path(argv[2])};
 std::mutex mutex;Snapshot latest;unsigned long accepted=0,bad_crc=0,old_tick=0;
 auto snapshot=[&](){std::lock_guard<std::mutex> lock(mutex);return latest;};
 unitree::robot::ChannelFactory::Instance()->Init(0,argv[1]);
 // Destroy the subscriber before the callback's captured storage.
 unitree::robot::ChannelSubscriber<LowState> subscriber("rt/lowstate");
 subscriber.InitChannel([&](const void* message){
  const auto& state=*static_cast<const LowState*>(message);
  std::lock_guard<std::mutex> lock(mutex);
  if(!valid_crc(state)){++bad_crc;return;}
  if(latest.present&&!NativeStateTickAdvances(latest.state.tick(),state.tick())){++old_tick;return;}
  latest={state,Clock::now(),true};++accepted;
 },1);
 auto deadline=Clock::now()+std::chrono::seconds(10);
 while(!snapshot().present&&Clock::now()<deadline)std::this_thread::sleep_for(std::chrono::milliseconds(10));
 auto first=snapshot();if(!first.present)throw std::runtime_error("no LowState in 10 seconds");
 std::array<float,kDofs> mimic{};for(unsigned i=0;i<kDofs;++i)mimic[i]=first.state.motor_state()[i].q();
 ObservationHistory history;
 for(int i=0;i<20;++i){auto state=snapshot();auto result=history.infer(policy,state.state,mimic);history.commit(result.current,target_as_action(hybrid_target(result.action,mimic)));}
 history.reset();
 struct Sample{double elapsed,age,late;};
 std::vector<Sample> clock_samples;clock_samples.reserve(6000);
 std::atomic<bool> running{true};const auto start=Clock::now();
 std::thread sampler([&](){auto next=start;while(running.load()){
  std::this_thread::sleep_until(next);const auto state=snapshot();const auto now=Clock::now();
  clock_samples.push_back({std::chrono::duration<double>(now-start).count(),std::chrono::duration<double,std::milli>(now-state.receipt).count(),std::chrono::duration<double,std::milli>(now-next).count()});
  next+=std::chrono::milliseconds(2);if(now>next)next=now+std::chrono::milliseconds(2);
 }});
 std::string error;unsigned count=0,stale=0,slow=0;double maximum=0;
 try{
  std::ofstream csv(output/"policy.csv");csv<<"elapsed_s,state_age_ms,inference_ms\n";
  auto next=start;
  while(Clock::now()-start<std::chrono::seconds(10)){
   std::this_thread::sleep_until(next);const auto state=snapshot();const auto now=Clock::now();
   const auto age=std::chrono::duration<double,std::milli>(now-state.receipt).count();
   if(age>20){++stale;}else{
    const auto result=history.infer(policy,state.state,mimic);
    history.commit(result.current,target_as_action(hybrid_target(result.action,mimic)));
    ++count;maximum=std::max(maximum,result.inference_ms);slow+=result.inference_ms>20;
    csv<<std::chrono::duration<double>(now-start).count()<<','<<age<<','<<result.inference_ms<<'\n';
   }
   next+=std::chrono::milliseconds(20);if(Clock::now()>next)next=Clock::now();
  }
 }catch(const std::exception& e){error=e.what();}
 running=false;sampler.join();
 std::ofstream ticks(output/"clock_500hz.csv");ticks<<"elapsed_s,state_age_ms,lateness_ms\n";
 double max_age=0,max_late=0;unsigned stale500=0;
 for(const auto& row:clock_samples){ticks<<row.elapsed<<','<<row.age<<','<<row.late<<'\n';max_age=std::max(max_age,row.age);max_late=std::max(max_late,row.late);stale500+=row.age>20;}
 std::lock_guard<std::mutex> lock(mutex);
 std::ofstream summary(output/"summary.txt");
 summary<<"publisher_created=false\nmode_changed=false\nclock_loop_is_not_command_writer=true\n"
 <<"accepted="<<accepted<<"\nbad_crc="<<bad_crc<<"\nold_tick="<<old_tick<<"\npolicy_iterations="<<count
 <<"\npolicy_stale_skips="<<stale<<"\ninference_ms_max="<<maximum<<"\ninference_over_20ms="<<slow
 <<"\nclock_samples="<<clock_samples.size()<<"\nclock_state_age_ms_max="<<max_age<<"\nclock_lateness_ms_max="<<max_late
 <<"\nclock_stale_over20ms="<<stale500<<"\nerror="<<error<<'\n';
 summary.close();std::cout<<"Receive-only probe finished: "<<output<<"; policy_iterations="<<count<<"; error="<<error<<'\n';
 return error.empty()?0:1;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
