#include "offline_observation_history.hpp"
#include "observation_reference.hpp"
#include <iostream>
#include <limits>
void Check(bool b) {if(!b) throw std::runtime_error("check_failed");}
int main()
{
 try
 {
  OfflineObservationHistory h;reference::ObservationHistory ref;reference::Policy policy;
  reference::LowState state;
  for(int n=0;n<200;++n)
  {
   std::array<float,29> q{},dq{},mimic{};std::array<float,3> gyro{},rpy{};
   std::array<double,29> candidate{};std::array<float,29> applied{};
   for(std::size_t i=0;i<29;++i)
   {
    q[i]=std::sin(static_cast<float>(n+i))*(n%2?200.0F:.5F);
    dq[i]=q[i]*2;mimic[i]=q[i]*.25F;
    state.motor_state()[i].q(q[i]);state.motor_state()[i].dq(dq[i]);
    candidate[i]=q[i];applied[i]=std::clamp((q[i]-offline_twist2::kDefault[i])/.5F,-2.0F,2.0F);
   }
   for(std::size_t i=0;i<3;++i) {gyro[i]=q[i];rpy[i]=q[i]*.1F;state.imu_state().gyroscope()[i]=gyro[i];state.imu_state().rpy()[i]=rpy[i];}
   auto frame=h.Build(q,dq,gyro,rpy,mimic);
   auto expected=ref.infer(policy,state,mimic);
   Check(frame.current==expected.current && frame.observation==policy.observed);
   h.Commit(candidate);ref.commit(expected.current,applied);
  }
  Check(h.Commits()==200);
  const auto prior=h.History();h.Build({}, {}, {}, {}, {});h.Discard();Check(h.History()==prior && h.Commits()==200);
  h.Build({}, {}, {}, {}, {});std::array<double,29> invalid{};invalid[0]=std::numeric_limits<double>::quiet_NaN();
  try {h.Commit(invalid);Check(false);} catch(const std::invalid_argument&) {}
  Check(h.History()==prior && h.Commits()==200);
  h.Stop();bool rejected=false;try {h.Build({}, {}, {}, {}, {});} catch(const std::runtime_error&) {rejected=true;}Check(rejected);
  std::cout<<"PASS 200 exact reference frames; history rollover, clipping, feedback, discard, invalid commit, stop\n";
 }
 catch(const std::exception& e) {std::cerr<<e.what();return 2;}
}
