#include "native_state_audit.hpp"
#include "native_stop_audit.hpp"
#include "hg_classes_only.hpp"
#include <cassert>
#include <sstream>
#include <string>
#include <vector>

std::vector<std::string> Split(const std::string& text) {
  std::istringstream stream(text);
  std::vector<std::string> result;
  std::string part;
  while(std::getline(stream,part,',')) result.push_back(part);
  return result;
}

int main() {
  unitree_hg::msg::dds_::LowState_ state;
  state.tick()=4294967295U; state.crc()=123456789U;
  state.mode_pr()=0; state.mode_machine()=5;
  state.wireless_remote()[2]=1; state.wireless_remote()[3]=2;
  state.imu_state().gyroscope()={.25F,-.5F,1.0F};
  for(std::size_t i=0;i<29;++i) {
    state.motor_state()[i].vol()=40.0F+static_cast<float>(i);
    state.motor_state()[i].temperature()={static_cast<std::int16_t>(i),static_cast<std::int16_t>(-1)};
    state.motor_state()[i].motorstate()=static_cast<std::uint32_t>(100+i);
  }
  const auto audit=NativeStateAudit::Capture(state);
  NativeStopAudit stop;
  state.motor_state()[22].q()=.3F;
  stop.CaptureFirst(state,true,4.5);
  state.tick()=0; state.motor_state()[22].vol()=0; // Copy must retain original snapshot.
  state.motor_state()[22].q()=0;
  stop.CaptureFirst(state,false,0);
  assert(stop.supplied_context && stop.snapshot_age_ms==4.5);
  assert(stop.state.tick==4294967295U && stop.q[22]==.3F);
  std::ostringstream stop_csv;
  stop.Csv(stop_csv,"R1 deadman released",false);
  const auto line_break=stop_csv.str().find('\n');
  assert(Split(stop_csv.str().substr(0,line_break)).size()==219);
  assert(Split(stop_csv.str().substr(line_break+1)).size()==219);
  std::ostringstream header,row;
  NativeStateAudit::Header(header); audit.Row(row);
  const auto names=Split(header.str()),values=Split(row.str());
  assert(names.size()==125 && values.size()==names.size());
  assert(values[1]=="4294967295" && values[5]=="513");
  assert(values[6]=="0.25" && values[7]=="-0.5");
  for(std::size_t i=0;i<29;++i) {
    const auto j=9+4*i;
    assert(names[j]=="motor_voltage_"+std::to_string(i));
    assert(std::stof(values[j])==40.0F+static_cast<float>(i));
    assert(std::stoi(values[j+1])==static_cast<int>(i));
    assert(values[j+2]=="-1");
    assert(std::stoul(values[j+3])==100+i);
  }
}
