cmake_minimum_required(VERSION 3.16)
project(g1_regular_handoff_offline LANGUAGES CXX)

# Deliberately independent from all SDK/Torch/native build files. No network,
# policy loading, hardware targets, DDS discovery or SDK initialization.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(G1_OFFLINE_SANITIZERS "Enable ASan and UBSan for memory-only tests" OFF)
find_package(Threads REQUIRED)
enable_testing()

foreach(name pd_gain_options pd_small_signal_trial writer_frame
             verified_regular_handoff regular_handoff_safety periodic_csv_failure
             real_response_frame)
  add_executable(test_${name} "../test_${name}.cpp")
  target_link_libraries(test_${name} PRIVATE Threads::Threads)
  if(MSVC)
    target_compile_options(test_${name} PRIVATE /W4 /UNDEBUG)
  else()
    target_compile_options(test_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
    if(G1_OFFLINE_SANITIZERS)
      target_compile_options(test_${name} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer -fno-pie)
      target_link_options(test_${name} PRIVATE -fsanitize=address,undefined -no-pie)
    endif()
  endif()
  add_test(NAME ${name} COMMAND test_${name})
  set_tests_properties(${name} PROPERTIES TIMEOUT 15)
endforeach()
