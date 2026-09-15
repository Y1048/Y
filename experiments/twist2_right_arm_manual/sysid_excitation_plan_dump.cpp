#include "sysid_excitation_plan_adapter.hpp"

#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
  try {
    if (argc != 4) {
      throw std::invalid_argument(
          "usage: sysid_excitation_plan_dump PLAN.json "
          "training|validation OUTPUT.csv");
    }
    const std::filesystem::path output_path(argv[3]);
    if (std::filesystem::exists(output_path)) {
      throw std::runtime_error("output already exists");
    }
    std::ifstream input(argv[1], std::ios::binary);
    if (!input) {
      throw std::runtime_error("cannot open plan");
    }
    const auto plan = sysid_excitation::LoadPlan(
        sysid_excitation::Json::parse(input, nullptr, true, true));
    const std::string episode_name(argv[2]);
    const std::vector<sysid_excitation::Segment>* segments = nullptr;
    if (episode_name == "training") {
      segments = &plan.training;
    } else if (episode_name == "validation") {
      segments = &plan.validation;
    } else {
      throw std::invalid_argument("unknown episode");
    }
    const sysid_excitation::Sequence sequence(
        plan.start_q_rad, *segments, plan.sample_period_s);

    std::ofstream output(output_path, std::ios::binary);
    if (!output) {
      throw std::runtime_error("cannot create output");
    }
    output << "time_s,segment,active_joint";
    for (int joint = 22; joint <= 28; ++joint) {
      output << ",offset_" << joint << "_rad";
    }
    output << ",active_velocity_rad_s,active_acceleration_rad_s2\n";
    output << std::setprecision(17);
    for (std::uint64_t tick = 0; tick <= sequence.total_ticks(); ++tick) {
      const auto sample = sequence.AtTick(tick);
      output << sample.time_s << ',' << sample.segment_index << ',';
      if (sample.active_joint >= 0) {
        output << sample.active_joint;
      }
      for (int joint = 22; joint <= 28; ++joint) {
        output << ',' << sample.target_q_rad[joint] - plan.start_q_rad[joint];
      }
      output << ',' << sample.active_velocity_rad_s << ','
             << sample.active_acceleration_rad_s2 << '\n';
    }
    output.close();
    if (!output) {
      throw std::runtime_error("failed to finish output");
    }
    std::cout << "offline_dump_ok episode=" << episode_name
              << " samples=" << sequence.total_ticks() + 1 << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "offline_dump_rejected: " << error.what() << '\n';
    return 2;
  }
}
