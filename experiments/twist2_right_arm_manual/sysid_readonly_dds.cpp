#include "vendor/json.hpp"

#include <unitree/idl/hg/LowCmd_.hpp>
#include <unitree/idl/hg/LowState_.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>

#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <functional>
#include <fcntl.h>
#include <iomanip>
#include <iostream>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <unistd.h>

namespace {
using Clock=std::chrono::steady_clock;
using LowCmd=unitree_hg::msg::dds_::LowCmd_;
using LowState=unitree_hg::msg::dds_::LowState_;
constexpr std::size_t kDofs=29,kCapacity=8192;
const std::array<const char*,kDofs> kNames={
 "left_hip_pitch","left_hip_roll","left_hip_yaw","left_knee","left_ankle_pitch","left_ankle_roll",
 "right_hip_pitch","right_hip_roll","right_hip_yaw","right_knee","right_ankle_pitch","right_ankle_roll",
 "waist_yaw","waist_roll","waist_pitch","left_shoulder_pitch","left_shoulder_roll","left_shoulder_yaw",
 "left_elbow","left_wrist_roll","left_wrist_pitch","left_wrist_yaw","right_shoulder_pitch",
 "right_shoulder_roll","right_shoulder_yaw","right_elbow","right_wrist_roll","right_wrist_pitch","right_wrist_yaw"};

std::atomic<bool> g_stop{false};
void signal_handler(int){g_stop.store(true);}
std::uint64_t ns(Clock::time_point t){return std::chrono::duration_cast<std::chrono::nanoseconds>(t.time_since_epoch()).count();}

struct Frame {
  std::uint64_t sequence{},state_ns{},command_ns{},state_tick{},command_age_ns{};
  std::uint32_t state_crc{},command_crc{}; bool has_command{};
  std::uint8_t mode_pr{},mode_machine{};
  std::array<float,kDofs> command_q{},command_dq{},kp{},kd{},tau_ff{},q{},dq{},tau_est{};
  std::array<std::int32_t,kDofs> temperature{},motor_status{};
  std::array<float,3> rpy{},gyro{},accel{};
};

template<std::size_t N> class Ring {
 public:
  bool push(const Frame& f) noexcept {const auto h=head_.load(std::memory_order_relaxed),n=(h+1)%N;
    if(n==tail_.load(std::memory_order_acquire))return false;data_[h]=f;head_.store(n,std::memory_order_release);return true;}
  bool pop(Frame& f) noexcept {const auto t=tail_.load(std::memory_order_relaxed);
    if(t==head_.load(std::memory_order_acquire))return false;f=data_[t];tail_.store((t+1)%N,std::memory_order_release);return true;}
 private: std::array<Frame,N> data_{};std::atomic<std::size_t> head_{0},tail_{0};
};

class Logger {
 public:
  Logger(std::string path,std::string session):path_(std::move(path)),session_(std::move(session)),ring_(std::make_unique<Ring<kCapacity>>()){
    if(std::filesystem::exists(path_)||std::filesystem::exists(path_+".receipt.json"))throw std::runtime_error("output exists");
    worker_=std::thread([this]{write_loop();});
  }
  ~Logger(){finish();}
  void start(const std::string& interface){
    unitree::robot::ChannelFactory::Instance()->Init(0,interface);
    command_.reset(new unitree::robot::ChannelSubscriber<LowCmd>("rt/lowcmd"));
    state_.reset(new unitree::robot::ChannelSubscriber<LowState>("rt/lowstate"));
    command_->InitChannel(std::bind(&Logger::on_command,this,std::placeholders::_1),1);
    state_->InitChannel(std::bind(&Logger::on_state,this,std::placeholders::_1),1);
  }
  void finish() noexcept {
    if(done_.exchange(true))return;state_.reset();command_.reset();stopping_.store(true);if(worker_.joinable())worker_.join();
    try {nlohmann::json r={{"schema","g1.sysid.readonly-dds.receipt.v1"},{"complete",!failed_.load()&&dropped_.load()==0},
      {"written",written_.load()},{"dropped",dropped_.load()},{"acceptance","unknown"}};
      const auto text=r.dump()+"\n";const auto receipt=path_+".receipt.json";const int fd=::open(receipt.c_str(),O_WRONLY|O_CREAT|O_EXCL,0600);
      if(fd<0)throw std::runtime_error("receipt open failed");const auto count=::write(fd,text.data(),text.size());const int closed=::close(fd);
      if(count!=static_cast<ssize_t>(text.size())||closed!=0)throw std::runtime_error("receipt write failed");
    }catch(...){failed_.store(true);}
  }
  std::uint64_t written()const{return written_.load();}std::uint64_t dropped()const{return dropped_.load();}
 private:
  void on_command(const void* p){std::lock_guard<std::mutex> lock(command_mutex_);latest_command_=*static_cast<const LowCmd*>(p);command_ns_=ns(Clock::now());has_command_=true;}
  void on_state(const void* p){
    const auto received=Clock::now();const auto& s=*static_cast<const LowState*>(p);Frame f;
    f.sequence=sequence_++;f.state_ns=ns(received);f.state_tick=s.tick();f.state_crc=s.crc();f.mode_pr=s.mode_pr();f.mode_machine=s.mode_machine();
    {std::lock_guard<std::mutex> lock(command_mutex_);f.has_command=has_command_;if(has_command_){f.command_ns=command_ns_;f.command_age_ns=f.state_ns>=command_ns_?f.state_ns-command_ns_:0;f.command_crc=latest_command_.crc();
      for(std::size_t i=0;i<kDofs;++i){const auto& c=latest_command_.motor_cmd()[i];f.command_q[i]=c.q();f.command_dq[i]=c.dq();f.kp[i]=c.kp();f.kd[i]=c.kd();f.tau_ff[i]=c.tau();}}}
    for(std::size_t i=0;i<kDofs;++i){const auto& m=s.motor_state()[i];f.q[i]=m.q();f.dq[i]=m.dq();f.tau_est[i]=m.tau_est();f.temperature[i]=m.temperature()[0];f.motor_status[i]=m.motorstate();}
    for(std::size_t i=0;i<3;++i){f.rpy[i]=s.imu_state().rpy()[i];f.gyro[i]=s.imu_state().gyroscope()[i];f.accel[i]=s.imu_state().accelerometer()[i];}
    if(!ring_->push(f))dropped_.fetch_add(1);
  }
  static void finite(const Frame& f){auto check=[](const auto& xs){for(const auto x:xs)if(!std::isfinite(x))throw std::runtime_error("nonfinite sample");};
    check(f.q);check(f.dq);check(f.tau_est);check(f.rpy);check(f.gyro);check(f.accel);if(f.has_command){check(f.command_q);check(f.command_dq);check(f.kp);check(f.kd);check(f.tau_ff);}}
  void write_loop() noexcept {try {const int fd=::open(path_.c_str(),O_WRONLY|O_CREAT|O_EXCL,0600);if(fd<0)throw std::runtime_error("output open failed");
    FILE* raw=::fdopen(fd,"wb");if(!raw){::close(fd);throw std::runtime_error("fdopen failed");}Frame f;
    while(true){if(!ring_->pop(f)){if(stopping_.load())break;std::this_thread::sleep_for(std::chrono::milliseconds(1));continue;}
      finite(f);
      nlohmann::json j={{"schema","g1.sysid.readonly-dds.v1"},{"session",session_},{"sequence",f.sequence},
        {"provenance",{{"kind","measured"},{"source","subscribed rt/lowcmd and rt/lowstate; no acceptance proof"}}},
        {"clock",{{"source","std::chrono::steady_clock"},{"domain","logger host monotonic"}}},
        {"joint_indices",nlohmann::json::array()},{"joint_names",kNames},{"units",{{"time","ns"},{"position","rad"},{"velocity","rad/s"},{"gain_kp","N*m/rad"},{"gain_kd","N*m*s/rad"},{"torque","N*m"},{"temperature","degC"}}},
        {"acceptance","unknown"},{"state_receive_ns",f.state_ns},{"state_tick",f.state_tick},{"state_crc",f.state_crc},
        {"mode_pr",f.mode_pr},{"mode_machine",f.mode_machine},{"has_command",f.has_command},
        {"command_receive_ns",f.has_command?nlohmann::json(f.command_ns):nlohmann::json(nullptr)},
        {"command_age_ns",f.has_command?nlohmann::json(f.command_age_ns):nlohmann::json(nullptr)},
        {"command_crc",f.has_command?nlohmann::json(f.command_crc):nlohmann::json(nullptr)},
        {"command_q",f.has_command?nlohmann::json(f.command_q):nlohmann::json(nullptr)},
        {"command_dq",f.has_command?nlohmann::json(f.command_dq):nlohmann::json(nullptr)},
        {"kp",f.has_command?nlohmann::json(f.kp):nlohmann::json(nullptr)},{"kd",f.has_command?nlohmann::json(f.kd):nlohmann::json(nullptr)},
        {"tau_ff",f.has_command?nlohmann::json(f.tau_ff):nlohmann::json(nullptr)},{"measured_q",f.q},{"measured_dq",f.dq},
        {"torque_estimate",f.tau_est},{"temperature",f.temperature},{"motor_status",f.motor_status},{"imu_rpy",f.rpy},{"imu_gyro",f.gyro},{"imu_accel",f.accel},
        {"dropped_samples",dropped_.load()}};
      for(std::size_t i=0;i<kDofs;++i)j["joint_indices"].push_back(i);
      const auto line=j.dump()+"\n";
      if(std::fwrite(line.data(),1,line.size(),raw)!=line.size()){std::fclose(raw);throw std::runtime_error("output write failed");}written_.fetch_add(1);
    }if(std::fclose(raw)!=0)throw std::runtime_error("output close failed");}catch(...){failed_.store(true);}}
  std::string path_,session_;std::unique_ptr<Ring<kCapacity>> ring_;std::thread worker_;std::atomic<bool> stopping_{false},done_{false},failed_{false};
  std::atomic<std::uint64_t> written_{0},dropped_{0};std::uint64_t sequence_{0};std::mutex command_mutex_;LowCmd latest_command_{};std::uint64_t command_ns_{};bool has_command_{false};
  unitree::robot::ChannelSubscriberPtr<LowCmd> command_;unitree::robot::ChannelSubscriberPtr<LowState> state_;
};
}

int main(int argc,char** argv){
  try {if(argc!=4)throw std::runtime_error("usage: g1_sysid_readonly_dds INTERFACE OUTPUT.jsonl SECONDS");
    std::size_t used=0;const double seconds=std::stod(argv[3],&used);if(used!=std::string(argv[3]).size()||!std::isfinite(seconds)||seconds<1||seconds>600)throw std::runtime_error("seconds must be 1..600");
    std::signal(SIGINT,signal_handler);std::signal(SIGTERM,signal_handler);Logger logger(argv[2],"readonly-dds-"+std::to_string(ns(Clock::now())));logger.start(argv[1]);
    const auto end=Clock::now()+std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));while(!g_stop.load()&&Clock::now()<end)std::this_thread::sleep_for(std::chrono::milliseconds(20));
    logger.finish();std::cout<<"read-only DDS capture complete: written="<<logger.written()<<" dropped="<<logger.dropped()<<'\n';return logger.dropped()==0?0:1;
  }catch(const std::exception& e){std::cerr<<"read-only DDS capture failed: "<<e.what()<<'\n';return 1;}
}
