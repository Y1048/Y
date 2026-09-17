#include "offline_hg_native_decoder.hpp"
#include "hg_classes_only.hpp"
#include <iostream>
#include <functional>

void Check(bool ok) { if(!ok) throw std::runtime_error("check_failed"); }
int main()
{
    try
    {
        using unitree_hg::msg::dds_::LowState_;
        static_assert(sizeof(LowState_)==2092);
        static_assert(sizeof(unitree_hg::msg::dds_::MotorState_)==56);
        static_assert(sizeof(unitree_hg::msg::dds_::IMUState_)==56);
        LowState_ state;
        state.mode_machine(5);state.tick(123);
        state.imu_state().quaternion()[0]=1;
        state.imu_state().gyroscope()[1]=.25F;
        state.wireless_remote()[2]=1;
        for(std::size_t i=0;i<35;++i)
        {
            state.motor_state()[i].q(static_cast<float>(i)*.01F);
            state.motor_state()[i].dq(static_cast<float>(i)*.02F);
            state.motor_state()[i].tau_est(static_cast<float>(i)*.03F);
            state.motor_state()[i].temperature()[0]=-10;
            state.motor_state()[i].temperature()[1]=40;
            state.motor_state()[i].motorstate(static_cast<std::uint32_t>(i));
        }
        std::vector<std::uint8_t> bytes(sizeof(state));
        std::memcpy(bytes.data(),&state,sizeof(state));
        // Confirm trailing CRC by official accessor address, not an assumed struct copy.
        Check(reinterpret_cast<const char*>(&state.crc())-reinterpret_cast<const char*>(&state)==2088);
        state.crc(OfflineWordCrc({bytes.begin(),bytes.end()-4}));
        std::memcpy(bytes.data(),&state,sizeof(state));
        auto result=DecodeOfflineHgNative(bytes,"hg_native_le2092_9754cd15",7,.02);
        Check(result.health.crc_verified && result.health.deadman && !result.health.emergency_stop);
        Check(result.robot_tick==123 && result.sample.sequence==7 && result.gyro[1]==.25);
        for(std::size_t i=0;i<29;++i)
        {
            Check(result.sample.q[i]==state.motor_state()[i].q());
            Check(result.sample.dq[i]==state.motor_state()[i].dq());
            Check(result.health.torque[i]==state.motor_state()[i].tau_est());
            Check(result.health.temperature[i]==40 && result.health.faults[i]==i);
        }
        int rejected=0;
        for(std::size_t i=0;i<bytes.size();++i)
        {
            auto corrupt=bytes;corrupt[i]^=1;
            try { DecodeOfflineHgNative(corrupt,"hg_native_le2092_9754cd15",7,.02); }
            catch(const std::invalid_argument&) { ++rejected; }
        }
        Check(rejected==2092);
        try { DecodeOfflineHgNative(bytes,"DDS_CDR",7,.02);Check(false); }
        catch(const std::invalid_argument&) {}
        state.wireless_remote()[3]=2;
        std::memcpy(bytes.data(),&state,sizeof(state));
        state.crc(OfflineWordCrc({bytes.begin(),bytes.end()-4}));
        std::memcpy(bytes.data(),&state,sizeof(state));
        Check(DecodeOfflineHgNative(bytes,"hg_native_le2092_9754cd15",7,.02).health.emergency_stop);
        state.motor_state()[0].q(std::numeric_limits<float>::quiet_NaN());
        std::memcpy(bytes.data(),&state,sizeof(state));
        state.crc(OfflineWordCrc({bytes.begin(),bytes.end()-4}));
        std::memcpy(bytes.data(),&state,sizeof(state));
        try { DecodeOfflineHgNative(bytes,"hg_native_le2092_9754cd15",7,.02);Check(false); }
        catch(const std::invalid_argument&) {}
        bytes.pop_back();
        try { DecodeOfflineHgNative(bytes,"hg_native_le2092_9754cd15",7,.02);Check(false); }
        catch(const std::invalid_argument&) {}
        std::cout<<"PASS official class fixture; 2092 byte corruption rejections; size check\n";
    }
    catch(const std::exception& e) { std::cerr<<e.what();return 2; }
}
