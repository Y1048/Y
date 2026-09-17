#include "offline_writer_study.hpp"
#include <iostream>
// File/stdin-only scheduler probe; state is an idealized previous-target fixture.
int main() {
 try {
  std::string line;std::getline(std::cin,line);auto config=nlohmann::json::parse(line);
  if(config.at("state_source")!="previous_target_zero_velocity_fixture")throw std::invalid_argument("fixture_required");
  const auto initial=config.at("baseline").get<std::array<float,29>>();
  OfflineWriterStudy writer(initial,config.at("start"));
  OfflineStateHealth health;health.crc_verified=true;health.mode_pr=0;health.mode_machine=5;
  health.deadman=true;health.emergency_stop=false;
  std::optional<OfflineDesiredPosition> desired;std::uint64_t commits=0,discarded=0;
  while(std::getline(std::cin,line)) {
   auto row=nlohmann::json::parse(line);
   // Stop wins over completions at the same scheduler instant.
   if(row.contains("stop"))writer.Stop(row.at("stop"));
   for(const auto& update:row.at("updates")) {
    if(!writer.Reason().empty()){++discarded;continue;}
    OfflineDesiredPosition next;next.q=update.at("q").get<std::array<float,29>>();
    next.created_at=update.at("created");desired=next;
   }
   const double now=row.at("now");
   OfflineStateSample state{};state.received_at=row.at("state_at");
   for(size_t i=0;i<29;++i)state.q[i]=writer.LastTarget()[i];
   bool accepted=writer.Tick(state,health,desired,now);commits+=accepted?1:0;
   bool damping=true;
   for(size_t i=0;i<35;++i) {
    const auto& m=writer.Diagnostics()[i];
    damping=damping&&m.kp==0&&m.feedforward==0&&m.kd==((i==3||i==9)?2:1);
   }
   std::cout<<nlohmann::json({{"accepted",accepted},{"reason",writer.Reason()},
    {"q",writer.LastTarget()},{"commits",commits},{"discarded",discarded},{"damping",damping}}).dump()<<std::endl;
  }
 }catch(const std::exception& e){std::cerr<<e.what();return 2;}
}
