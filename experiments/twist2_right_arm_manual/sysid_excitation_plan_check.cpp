#include "sysid_excitation_plan_adapter.hpp"

#include <fstream>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
  try {
    if (argc != 2) {
      throw std::invalid_argument("usage: sysid_excitation_plan_check PLAN.json");
    }
    std::ifstream input(argv[1], std::ios::binary);
    if (!input) {
      throw std::runtime_error("cannot open plan");
    }
    const auto plan = sysid_excitation::LoadPlan(
        sysid_excitation::Json::parse(input, nullptr, true, true));
    const sysid_excitation::Sequence training(
        plan.start_q_rad, plan.training, plan.sample_period_s);
    const sysid_excitation::Sequence validation(
        plan.start_q_rad, plan.validation, plan.sample_period_s);
    std::cout << "offline_plan_ok training_ticks=" << training.total_ticks()
              << " validation_ticks=" << validation.total_ticks()
              << " sample_period_s=" << plan.sample_period_s << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "offline_plan_rejected: " << error.what() << '\n';
    return 2;
  }
}
