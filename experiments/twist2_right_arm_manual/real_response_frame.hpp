#pragma once
#include "periodic_csv.hpp"
#include "writer_frame.hpp"
#include <array>
#include <cctype>
#include <memory>
#include <ostream>
#include <stdexcept>
#include <string>

// A passive file sink for values already owned by the single LowCmd writer.
// This type has no SDK, DDS, socket, publisher, LowCmd, or gain mutation API.
struct RealResponseFrame {
 std::string session_id, binary_sha256;
 std::string state{"active"};
 WriterFrame writer;
 std::array<float,7> original_target{};
 std::array<float,3> imu_rpy{},imu_gyroscope{};
 std::array<float,7> temperature_c{};
 std::array<unsigned,7> motor_status{};
};

inline void RealResponseArray(std::ostream& s,const std::array<float,7>& a){
 s<<'[';for(std::size_t i=0;i<a.size();++i){if(i)s<<',';s<<a[i];}s<<']';
}
inline void RealResponseArray3(std::ostream& s,const std::array<float,3>& a){
 s<<'[';for(std::size_t i=0;i<a.size();++i){if(i)s<<',';s<<a[i];}s<<']';
}
inline void RealResponseSlice(std::ostream& s,const std::array<float,29>& a){
 s<<'[';for(std::size_t i=22;i<29;++i){if(i!=22)s<<',';s<<a[i];}s<<']';
}
inline void RealResponseRow(std::ostream& s,const RealResponseFrame& r){
 s<<"{\"schema\":\"g1.real-response.v1\",\"session_id\":\""<<r.session_id
  <<"\",\"sequence\":"<<r.writer.sequence<<",\"state\":\""<<r.state
  <<"\",\"source_provenance\":{\"binary_sha256\":\""<<r.binary_sha256
  <<"\"},\"target_monotonic_ns\":"<<static_cast<unsigned long long>(r.writer.desired_created_s*1e9)
  <<",\"command_monotonic_ns\":"<<static_cast<unsigned long long>(r.writer.write_returned_s*1e9)
  <<",\"lowstate_monotonic_ns\":"<<static_cast<unsigned long long>(r.writer.state_received_s*1e9)
  <<",\"write_returned_monotonic_ns\":"<<static_cast<unsigned long long>(r.writer.write_returned_s*1e9)
  <<",\"target_q_rad\":";RealResponseArray(s,r.original_target);
 s<<",\"command_q_rad\":";RealResponseSlice(s,r.writer.target);
 s<<",\"command_dq_rad_s\":";RealResponseSlice(s,r.writer.target_dq);
 s<<",\"kp_nm_rad\":";RealResponseSlice(s,r.writer.kp);
 s<<",\"kd_nm_s_rad\":";RealResponseSlice(s,r.writer.kd);
 s<<",\"tau_ff_nm\":";RealResponseSlice(s,r.writer.tau_ff);
 s<<",\"measured_q_rad\":";RealResponseSlice(s,r.writer.q);
 s<<",\"measured_dq_rad_s\":";RealResponseSlice(s,r.writer.dq);
 s<<",\"measured_tau_nm\":";RealResponseSlice(s,r.writer.tau_est);
 s<<",\"imu\":{\"rpy_rad\":";RealResponseArray3(s,r.imu_rpy);
 s<<",\"gyroscope_rad_s\":";RealResponseArray3(s,r.imu_gyroscope);
 s<<"},\"motor\":{\"temperature_c\":";RealResponseArray(s,r.temperature_c);
 s<<",\"status\":[";for(std::size_t i=0;i<7;++i){if(i)s<<',';s<<r.motor_status[i];}
 s<<"]}}\n";
}

inline bool RealResponseIdentifier(const std::string& value){
 if(value.empty()||value.size()>128)return false;
 for(unsigned char c:value)if(!std::isalnum(c)&&c!='-'&&c!='_'&&c!='.')return false;
 return true;
}

class RealResponseLog {
 std::string session_,binary_sha_;
 static std::string CheckedSession(std::string value){
  if(!RealResponseIdentifier(value))throw std::invalid_argument("invalid_real_response_provenance");
  return value;
 }
 static std::string CheckedSha(std::string value){
  if(value.size()!=64)throw std::invalid_argument("invalid_real_response_provenance");
  for(unsigned char c:value)if(!std::isxdigit(c))throw std::invalid_argument("invalid_real_response_sha256");
  return value;
 }
 PeriodicCsv<RealResponseFrame> sink;
public:
 RealResponseLog(const std::string& path,const std::string& session,const std::string& binary_sha)
   :session_(CheckedSession(session)),binary_sha_(CheckedSha(binary_sha)),sink(path,"",RealResponseRow,8192){}
 void Append(RealResponseFrame frame){frame.session_id=session_;frame.binary_sha256=binary_sha_;sink.Append(frame);}
 void Finish(){sink.Finish();}
};
