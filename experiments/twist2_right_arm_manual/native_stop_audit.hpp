#pragma once
#include "native_state_audit.hpp"
#include <string>

// Caller serializes CaptureFirst. Preserve first latch context, not later damping states.
struct NativeStopAudit {
  bool captured=false, supplied_context=false;
  double snapshot_age_ms=-1;
  NativeStateAudit state;
  std::array<float,29> q{},dq{},tau{};
  std::array<float,3> rpy{};
  template<class State> void CaptureFirst(const State& source, bool supplied, double age) {
    if(captured)return;
    state=NativeStateAudit::Capture(source);
    rpy=source.imu_state().rpy();
    for(std::size_t i=0;i<29;++i) {
      q[i]=source.motor_state()[i].q(); dq[i]=source.motor_state()[i].dq();
      tau[i]=source.motor_state()[i].tau_est();
    }
    supplied_context=supplied; snapshot_age_ms=age; captured=true;
  }
  void Csv(std::ostream& out, const std::string& reason, bool planned) const {
    out << "reason,planned,captured,supplied_context,age_at_snapshot_ms,roll_rad,pitch_rad,yaw_rad";
    NativeStateAudit::Header(out);
    for(std::size_t i=0;i<29;++i)out << ",q_"<<i<<",dq_"<<i<<",tau_est_"<<i;
    out << '\n' << '"';
    for(char c:reason){if(c=='"')out << '"';out << c;}
    out << '"' << ',' << planned << ',' << captured << ',' << supplied_context << ',' << snapshot_age_ms;
    for(float x:rpy)out<<','<<x;
    state.Row(out);
    for(std::size_t i=0;i<29;++i)out<<','<<q[i]<<','<<dq[i]<<','<<tau[i];
    out<<'\n';
  }
};
