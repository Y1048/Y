#include "periodic_csv.hpp"
#include "regular_handoff_safety.hpp"
#include <filesystem>
#include <iostream>

int main() {
  const auto path = std::filesystem::temp_directory_path() /
      ("g1-csv-offline-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) + ".csv");
  try {
    {
      PeriodicCsv<int> csv(path.string(), "value\n", [](std::ostream&, const int&) {
        throw std::runtime_error("injected encoder/write failure");
      });
      csv.Append(1);
      if (regular_handoff::TryArtifact([&] { csv.Finish(); }))
        throw std::runtime_error("worker failure not reported");
      // A repeated Finish and destructor after the error must be contained.
      if (regular_handoff::TryArtifact([&] { csv.Finish(); }))
        throw std::runtime_error("latched worker error lost");
    }
    std::filesystem::remove(path);
    std::cout << "PASS real CSV worker error, guarded Finish, repeated Finish, destructor\n";
  } catch (const std::exception& error) {
    std::error_code ignored; std::filesystem::remove(path, ignored);
    std::cerr << error.what() << '\n'; return 1;
  }
}
