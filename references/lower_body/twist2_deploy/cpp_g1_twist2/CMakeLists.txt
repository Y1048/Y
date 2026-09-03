cmake_minimum_required(VERSION 3.16)
project(g1_twist2_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
option(BUILD_UNITREE_TARGETS "Build DDS shadow and physical stand binaries" ON)

if(NOT DEFINED UNITREE_SDK2_ROOT)
  set(UNITREE_SDK2_ROOT "$ENV{HOME}/unitree_sdk2-main")
endif()

if(NOT EXISTS "${UNITREE_SDK2_ROOT}/include/unitree")
  message(FATAL_ERROR
    "UNITREE_SDK2_ROOT does not contain include/unitree: "
    "${UNITREE_SDK2_ROOT}")
endif()

if(NOT DEFINED TORCH_PYTHON_ROOT)
  execute_process(
    COMMAND python3 -c
      "import pathlib, torch; print(pathlib.Path(torch.__file__).parent)"
    OUTPUT_VARIABLE TORCH_PYTHON_ROOT
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE TORCH_DISCOVERY_RESULT
  )
  if(NOT TORCH_DISCOVERY_RESULT EQUAL 0)
    message(FATAL_ERROR "Could not discover the Python torch package")
  endif()
endif()

if(NOT EXISTS "${TORCH_PYTHON_ROOT}/include/torch/script.h")
  message(FATAL_ERROR
    "Python torch package has no C++ headers: ${TORCH_PYTHON_ROOT}")
endif()

if(NOT DEFINED TORCH_CXX11_ABI)
  execute_process(
    COMMAND python3 -c
      "import torch; print(1 if torch.compiled_with_cxx11_abi() else 0)"
    OUTPUT_VARIABLE TORCH_CXX11_ABI
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE TORCH_ABI_RESULT
  )
  if(NOT TORCH_ABI_RESULT EQUAL 0)
    message(FATAL_ERROR
      "Could not detect the PyTorch C++ ABI; set -DTORCH_CXX11_ABI=0 or 1")
  endif()
endif()
if(NOT TORCH_CXX11_ABI MATCHES "^[01]$")
  message(FATAL_ERROR "TORCH_CXX11_ABI must be 0 or 1")
endif()
message(STATUS "PyTorch C++11 ABI: ${TORCH_CXX11_ABI}")

set(UNITREE_ARCH_LIB "${UNITREE_SDK2_ROOT}/lib/${CMAKE_SYSTEM_PROCESSOR}")
if(NOT EXISTS "${UNITREE_ARCH_LIB}/libunitree_sdk2.a")
  message(FATAL_ERROR
    "Unitree SDK library not found: ${UNITREE_ARCH_LIB}/libunitree_sdk2.a")
endif()

set(DDS_INCLUDE_DIRS /usr/local/include/ddscxx)
set(DDS_LIBRARY_DIRS /usr/local/lib)
if(EXISTS "${UNITREE_SDK2_ROOT}/thirdparty/include/ddsc")
  list(APPEND DDS_INCLUDE_DIRS
    "${UNITREE_SDK2_ROOT}/thirdparty/include"
    "${UNITREE_SDK2_ROOT}/thirdparty/include/ddscxx")
  list(APPEND DDS_LIBRARY_DIRS
    "${UNITREE_SDK2_ROOT}/thirdparty/lib/${CMAKE_SYSTEM_PROCESSOR}")
endif()

find_package(Threads REQUIRED)

function(configure_torch target)
  target_include_directories(
    ${target}
    PRIVATE
      "${TORCH_PYTHON_ROOT}/include"
      "${TORCH_PYTHON_ROOT}/include/torch/csrc/api/include"
  )
  target_link_libraries(
    ${target}
    PRIVATE
      "${TORCH_PYTHON_ROOT}/lib/libtorch.so"
      "${TORCH_PYTHON_ROOT}/lib/libtorch_cpu.so"
      "${TORCH_PYTHON_ROOT}/lib/libc10.so"
      Threads::Threads
  )
  if(EXISTS "${TORCH_PYTHON_ROOT}/lib/libtorch_cuda.so")
    target_link_libraries(
      ${target} PRIVATE "${TORCH_PYTHON_ROOT}/lib/libtorch_cuda.so")
  endif()
  if(EXISTS "${TORCH_PYTHON_ROOT}/lib/libc10_cuda.so")
    target_link_libraries(
      ${target} PRIVATE "${TORCH_PYTHON_ROOT}/lib/libc10_cuda.so")
  endif()
  target_compile_definitions(
    ${target} PRIVATE _GLIBCXX_USE_CXX11_ABI=${TORCH_CXX11_ABI})
  target_compile_options(
    ${target} PRIVATE -Wall -Wextra -Wpedantic -Werror=return-type)
  set_target_properties(
    ${target}
    PROPERTIES
      BUILD_RPATH "${TORCH_PYTHON_ROOT}/lib"
      INSTALL_RPATH "${TORCH_PYTHON_ROOT}/lib"
  )
endfunction()

function(add_twist2_executable target source)
  add_executable(${target} ${source})
  target_include_directories(
    ${target}
    PRIVATE
      "${UNITREE_SDK2_ROOT}/include"
      ${DDS_INCLUDE_DIRS}
  )
  target_link_directories(
    ${target}
    PRIVATE
      "${UNITREE_ARCH_LIB}"
      ${DDS_LIBRARY_DIRS}
  )
  target_link_libraries(
    ${target}
    PRIVATE
      unitree_sdk2
      ddsc
      ddscxx
  )
  configure_torch(${target})
endfunction()

add_executable(g1_twist2_cpp_self_test twist2_self_test.cpp)
target_include_directories(
  g1_twist2_cpp_self_test
  PRIVATE
    "${UNITREE_SDK2_ROOT}/include"
    ${DDS_INCLUDE_DIRS})
configure_torch(g1_twist2_cpp_self_test)

if(BUILD_UNITREE_TARGETS)
  add_twist2_executable(g1_twist2_cpp_shadow twist2_shadow.cpp)
  add_twist2_executable(g1_twist2_cpp_static_stand twist2_static_stand.cpp)
endif()
