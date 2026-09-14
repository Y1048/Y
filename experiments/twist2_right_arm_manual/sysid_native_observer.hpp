#pragma once
// File-only observer: fixed-size SPSC copies; no SDK or transport dependencies.
#include "vendor/json.hpp"
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
#include <thread>
#include <type_traits>

namespace sysid {
struct Frame {
  std::uint64_t target_ns{}, write_begin_ns{}, write_end_ns{}, state_receive_ns{};
  std::array<float,29> target_q{},command_q{},command_dq{},kp{},kd{},tau_ff{},q{},dq{},tau{},temperature{};
  std::array<unsigned,29> status{};
  std::array<float,3> rpy{},gyro{},accel{};
  bool hold{};
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
                              const std::string& session,const std::string& source,const std::string& kind){
  const std::array<const char*,29> names={"left_hip_pitch","left_hip_roll","left_hip_yaw","left_knee","left_ankle_pitch","left_ankle_roll",
    "right_hip_pitch","right_hip_roll","right_hip_yaw","right_knee","right_ankle_pitch","right_ankle_roll","waist_yaw","waist_roll","waist_pitch",
    "left_shoulder_pitch","left_shoulder_roll","left_shoulder_yaw","left_elbow","left_wrist_roll","left_wrist_pitch","left_wrist_yaw",
    "right_shoulder_pitch","right_shoulder_roll","right_shoulder_yaw","right_elbow","right_wrist_roll","right_wrist_pitch","right_wrist_yaw"};
  const auto finite=[](const auto& a){for(auto v:a)if(!std::isfinite(v))throw std::runtime_error("nonfinite frame");};
  for(const auto* a:{&f.target_q,&f.command_q,&f.command_dq,&f.kp,&f.kd,&f.tau_ff,&f.q,&f.dq,&f.tau,&f.temperature})finite(*a);
  finite(f.rpy);finite(f.gyro);finite(f.accel);
  if(f.target_ns>f.write_begin_ns||f.write_begin_ns>f.write_end_ns)throw std::runtime_error("clock order");
  std::array<int,29> indices{};for(int i=0;i<29;++i)indices[i]=i;
  return {{"schema","g1.sysid.observation.v2"},{"session",session},{"episode",session},{"sequence",sequence},
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
}

class Observer {
  Ring<2048> ring;
  std::atomic<bool> closing{false},failed{false};
  std::atomic<std::size_t> offered{0},dropped{0};
  std::size_t written{0};
  std::FILE* stream{nullptr};
  std::string session,source,kind;
  std::thread worker;
  void Run() noexcept {
    try {
      for(;;){
        Frame f;
        if(ring.Pop(f)){const auto row=Encode(f,written,session,source,kind).dump()+"\n";
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
  Observer(const std::string& path,const std::string& id,const std::string& provenance,const std::string& origin):session(id),source(provenance),kind(origin){
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
