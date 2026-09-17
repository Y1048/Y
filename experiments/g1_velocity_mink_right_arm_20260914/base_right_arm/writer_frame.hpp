#pragma once
#include <array>
#include <cstdint>
#include <mutex>
#include <ostream>

// One completed publisher call paired with the exact LowState used to form it.
// This is NOT a device acknowledgement or a subsequent response measurement.
struct WriterFrame {
 int trial_phase=0,trial_cycle=0;
 bool valid=false;
 std::uint64_t sequence=0;
 std::uint32_t state_tick=0;
 double state_received_s=0, cycle_started_s=0, write_returned_s=0, desired_created_s=0;
 std::array<float,29> q{},dq{},tau_est{},target{},target_dq{},kp{},kd{},tau_ff{};
};
class WriterFrameStore {
 mutable std::mutex mutex;
 WriterFrame latest;
public:
 void Publish(WriterFrame frame){
  std::lock_guard<std::mutex> lock(mutex);
  frame.valid=true;frame.sequence=latest.sequence+1;latest=frame;
 }
 WriterFrame Read() const {std::lock_guard<std::mutex> lock(mutex);return latest;}
};
inline void WriterFrameHeader(std::ostream& s){
 s<<",writer_trial_phase,writer_trial_cycle,writer_valid,writer_sequence,writer_state_tick,writer_state_received_s,writer_cycle_started_s,writer_write_returned_s,writer_desired_created_s";
 for(int i=0;i<29;++i)s<<",writer_q_"<<i<<",writer_dq_"<<i<<",writer_tau_est_"<<i
   <<",writer_target_"<<i<<",writer_target_dq_"<<i<<",writer_kp_"<<i<<",writer_kd_"<<i<<",writer_tau_ff_"<<i;
}
inline void WriterFrameRow(std::ostream& s,const WriterFrame& f){
 s<<','<<f.trial_phase<<','<<f.trial_cycle<<','<<f.valid<<','<<f.sequence<<','<<f.state_tick<<','<<f.state_received_s
  <<','<<f.cycle_started_s<<','<<f.write_returned_s<<','<<f.desired_created_s;
 for(int i=0;i<29;++i)s<<','<<f.q[i]<<','<<f.dq[i]<<','<<f.tau_est[i]<<','<<f.target[i]
  <<','<<f.target_dq[i]<<','<<f.kp[i]<<','<<f.kd[i]<<','<<f.tau_ff[i];
}
