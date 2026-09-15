#pragma once
// File-only observer: fixed-size SPSC copies; no SDK or transport dependencies.
#include "vendor/json.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <cstdio>
#include <fcntl.h>
#include <unistd.h>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <type_traits>
#include <utility>

namespace sysid {
enum class ExcitationRuntimeState : std::uint8_t {
  kDisarmed,
  kRunning,
  kCompleteHold,
  kFaultHold,
};

struct ExcitationContext {
  bool present{};
  std::string plan_file_sha256;
  std::string request_sha256;
  std::string contract_id;
  std::string termination_owner_status;
  std::string episode;
};

struct ExcitationTag {
  bool present{};
  ExcitationRuntimeState runtime_state{ExcitationRuntimeState::kDisarmed};
  std::uint64_t plan_tick{};
  std::uint64_t segment_index{};
  int active_joint{-1};
  std::array<double,7> right_arm_target_q_rad{};
  double active_velocity_rad_s{};
  double active_acceleration_rad_s2{};
  std::array<char,96> fault_reason{};
};

struct Frame {
  std::uint64_t target_ns{}, write_begin_ns{}, write_end_ns{}, state_receive_ns{};
  std::array<float,29> target_q{},command_q{},command_dq{},kp{},kd{},tau_ff{},q{},dq{},tau{},temperature{};
  std::array<unsigned,29> status{};
  std::array<float,3> rpy{},gyro{},accel{};
  bool hold{};
  ExcitationTag excitation{};
};
static_assert(std::is_trivially_copyable<Frame>::value,"fixed copy only");
static_assert(std::atomic<std::size_t>::is_always_lock_free,"lock-free indices required");

template<std::size_t N> class Ring {
  static_assert(N>1,"capacity");
  std::array<Frame,N> data{};
  alignas(64) std::atomic<std::size_t> head{0};
  alignas(64) std::atomic<std::size_t> tail{0};
public:
  bool Push(const Frame& f) noexcept {
    const auto h=head.load(std::memory_order_relaxed), next=(h+1)%N;
    if(next==tail.load(std::memory_order_acquire)) return false;
    data[h]=f;head.store(next,std::memory_order_release);return true;
  }
  bool Pop(Frame& f) noexcept {
    const auto t=tail.load(std::memory_order_relaxed);
    if(t==head.load(std::memory_order_acquire)) return false;
    f=data[t];tail.store((t+1)%N,std::memory_order_release);return true;
  }
};

inline nlohmann::json Encode(const Frame& f,std::uint64_t sequence,
                              const std::string& session,const std::string& source,const std::string& kind,
                              const ExcitationContext* excitation_context=nullptr){
  const std::array<const char*,29> names={"left_hip_pitch","left_hip_roll","left_hip_yaw","left_knee","left_ankle_pitch","left_ankle_roll",
    "right_hip_pitch","right_hip_roll","right_hip_yaw","right_knee","right_ankle_pitch","right_ankle_roll","waist_yaw","waist_roll","waist_pitch",
    "left_shoulder_pitch","left_shoulder_roll","left_shoulder_yaw","left_elbow","left_wrist_roll","left_wrist_pitch","left_wrist_yaw",
    "right_shoulder_pitch","right_shoulder_roll","right_shoulder_yaw","right_elbow","right_wrist_roll","right_wrist_pitch","right_wrist_yaw"};
  const auto finite=[](const auto& a){for(auto v:a)if(!std::isfinite(v))throw std::runtime_error("nonfinite frame");};
  for(const auto* a:{&f.target_q,&f.command_q,&f.command_dq,&f.kp,&f.kd,&f.tau_ff,&f.q,&f.dq,&f.tau,&f.temperature})finite(*a);
  finite(f.rpy);finite(f.gyro);finite(f.accel);
  if(f.target_ns>f.write_begin_ns||f.write_begin_ns>f.write_end_ns)throw std::runtime_error("clock order");
  std::array<int,29> indices{};for(int i=0;i<29;++i)indices[i]=i;
  nlohmann::json result={{"schema","g1.sysid.observation.v2"},{"session",session},{"episode",session},{"sequence",sequence},
    {"state",f.hold?"hold":"active"},{"mode",nullptr},{"acceptance","unknown"},{"dropped_samples",0},
    {"provenance",{{"kind",kind},{"source",source}}},
    {"clock",{{"source","std::chrono::steady_clock"},{"domain",session}}},
    {"joint_indices",indices},{"joint_names",names},
    {"units",{{"q","rad"},{"dq","rad/s"},{"tau","Nm"},{"kp","Nm/rad"},{"kd","Nm*s/rad"},{"time","ns"},
      {"temperature","degC"},{"imu_rpy","rad"},{"imu_gyro","rad/s"},{"imu_accel","m/s^2"}}},
    {"target_ns",f.target_ns},{"write_begin_ns",f.write_begin_ns},{"write_end_ns",f.write_end_ns},{"state_receive_ns",f.state_receive_ns},
    {"target_q",f.target_q},{"command_q",f.command_q},{"command_dq",f.command_dq},{"kp",f.kp},{"kd",f.kd},{"tau_ff",f.tau_ff},
    {"measured_q",f.q},{"measured_dq",f.dq},{"torque_estimate",f.tau},{"temperature",f.temperature},{"motor_status",f.status},
    {"imu_rpy",f.rpy},{"imu_gyro",f.gyro},{"imu_accel",f.accel}};
  const bool context_present=excitation_context&&excitation_context->present;
  if(context_present!=f.excitation.present)throw std::runtime_error("excitation context/tag mismatch");
  if(!context_present)return result;
  const auto valid_hash=[](const std::string& text){
    if(text.size()!=64)return false;
    for(const char value:text)if(!((value>='0'&&value<='9')||(value>='a'&&value<='f')))return false;
    return true;
  };
  if(!valid_hash(excitation_context->plan_file_sha256)||
     !valid_hash(excitation_context->request_sha256)||
     excitation_context->contract_id.empty()||
     (excitation_context->termination_owner_status!="unresolved"&&
      excitation_context->termination_owner_status!="reviewed")||
     (excitation_context->episode!="training"&&excitation_context->episode!="validation"))
    throw std::runtime_error("invalid excitation context");
  finite(f.excitation.right_arm_target_q_rad);
  if(!std::isfinite(f.excitation.active_velocity_rad_s)||
     !std::isfinite(f.excitation.active_acceleration_rad_s2)||
     (f.excitation.active_joint!=-1&&
      (f.excitation.active_joint<22||f.excitation.active_joint>28)))
    throw std::runtime_error("invalid excitation tag");
  const auto state=[](ExcitationRuntimeState value){
    switch(value){
      case ExcitationRuntimeState::kDisarmed:return "disarmed";
      case ExcitationRuntimeState::kRunning:return "running";
      case ExcitationRuntimeState::kCompleteHold:return "complete_hold";
      case ExcitationRuntimeState::kFaultHold:return "fault_hold";
    }
    throw std::runtime_error("invalid excitation state");
  }(f.excitation.runtime_state);
  const auto end=std::find(f.excitation.fault_reason.begin(),f.excitation.fault_reason.end(),'\0');
  if(end==f.excitation.fault_reason.end())throw std::runtime_error("unterminated excitation fault reason");
  const std::string fault_reason(f.excitation.fault_reason.begin(),end);
  result["excitation"]={{"plan_file_sha256",excitation_context->plan_file_sha256},
    {"request_sha256",excitation_context->request_sha256},{"contract_id",excitation_context->contract_id},
    {"termination_owner_status",excitation_context->termination_owner_status},{"episode",excitation_context->episode},
    {"runtime_state",state},{"plan_tick",f.excitation.plan_tick},{"segment_index",f.excitation.segment_index},
    {"active_joint",f.excitation.active_joint},{"right_arm_target_q_rad",f.excitation.right_arm_target_q_rad},
    {"active_velocity_rad_s",f.excitation.active_velocity_rad_s},
    {"active_acceleration_rad_s2",f.excitation.active_acceleration_rad_s2},{"fault_reason",fault_reason}};
  return result;
}

class Observer {
  Ring<2048> ring;
  std::atomic<bool> closing{false},failed{false};
  std::atomic<std::size_t> offered{0},dropped{0};
  std::size_t written{0};
  std::FILE* stream{nullptr};
  std::string session,source,kind;
  ExcitationContext excitation_context;
  std::thread worker;
  void Run() noexcept {
    try {
      for(;;){
        Frame f;
        if(ring.Pop(f)){const auto row=Encode(f,written,session,source,kind,
            excitation_context.present?&excitation_context:nullptr).dump()+"\n";
          if(std::fwrite(row.data(),1,row.size(),stream)!=row.size())throw std::runtime_error("write failed");
          ++written;continue;}
        if(closing.load(std::memory_order_acquire))break;
        std::this_thread::sleep_for(std::chrono::milliseconds(2));
      }
      if(std::fflush(stream)!=0)throw std::runtime_error("flush failed");
      const auto status=std::fclose(stream);stream=nullptr;
      if(status!=0)throw std::runtime_error("close failed");
    }catch(...){failed.store(true);if(stream){std::fclose(stream);stream=nullptr;}}
  }
public:
  Observer(const std::string& path,const std::string& id,const std::string& provenance,const std::string& origin,
           ExcitationContext excitation={}):session(id),source(provenance),kind(origin),excitation_context(std::move(excitation)){
    const int fd=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL,0600);
    if(fd<0)throw std::runtime_error("exclusive capture open failed");
    stream=::fdopen(fd,"w");
    if(!stream){::close(fd);throw std::runtime_error("fdopen failed");}
    try{worker=std::thread([this]{Run();});}
    catch(...){std::fclose(stream);stream=nullptr;throw;}

  }
  bool Offer(const Frame& f) noexcept {
    offered.fetch_add(1,std::memory_order_relaxed);
    if(closing.load(std::memory_order_relaxed)||failed.load(std::memory_order_relaxed)||!ring.Push(f)){
      dropped.fetch_add(1,std::memory_order_relaxed);return false;
    }
    return true;
  }
  nlohmann::json Finish(){
    // Caller must detach producer first; never join while holding writer mutex.
    closing.store(true,std::memory_order_release);if(worker.joinable())worker.join();
    return {{"complete",!failed.load()&&dropped.load()==0&&offered.load()==written},
      {"offered",offered.load()},{"written",written},{"dropped",dropped.load()},{"error",failed.load()?"writer_failed":""}};
  }
  ~Observer(){closing.store(true);if(worker.joinable())worker.join();}
};
} // namespace sysid
