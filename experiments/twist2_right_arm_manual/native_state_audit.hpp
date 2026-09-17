#pragma once
#include <array>
#include <cstdint>
#include <ostream>

// Snapshot-only diagnostics. No SDK, transport, or control decisions here.
struct NativeStateAudit {
  std::uint32_t tick{}, crc{};
  unsigned mode_pr{}, mode_machine{}, buttons{};
  std::array<float, 3> gyro{};
  std::array<float, 29> voltage{};
  std::array<std::array<std::int16_t, 2>, 29> temperature{};
  std::array<std::uint32_t, 29> motorstate{};

  template<class State> static NativeStateAudit Capture(const State& state) {
    NativeStateAudit out;
    out.tick=state.tick(); out.crc=state.crc();
    out.mode_pr=state.mode_pr(); out.mode_machine=state.mode_machine();
    const auto& remote=state.wireless_remote();
    out.buttons=static_cast<unsigned>(remote[2]) | (static_cast<unsigned>(remote[3])<<8U);
    out.gyro=state.imu_state().gyroscope();
    for (std::size_t i=0;i<29;++i) {
      const auto& motor=state.motor_state()[i];
      out.voltage[i]=motor.vol(); out.temperature[i]=motor.temperature();
      out.motorstate[i]=motor.motorstate();
    }
    return out;
  }

  static void Header(std::ostream& out) {
    out << ",state_tick,state_crc,state_mode_pr,state_mode_machine,remote_buttons"
           ",gyro_x_rad_s,gyro_y_rad_s,gyro_z_rad_s";
    for (std::size_t i=0;i<29;++i)
      out << ",motor_voltage_" << i << ",motor_temperature0_" << i
          << ",motor_temperature1_" << i << ",motorstate_" << i;
  }
  void Row(std::ostream& out) const {
    out << ',' << tick << ',' << crc << ',' << mode_pr << ',' << mode_machine << ',' << buttons;
    for (float v:gyro) out << ',' << v;
    for (std::size_t i=0;i<29;++i)
      out << ',' << voltage[i] << ',' << temperature[i][0] << ',' << temperature[i][1] << ',' << motorstate[i];
  }
};
