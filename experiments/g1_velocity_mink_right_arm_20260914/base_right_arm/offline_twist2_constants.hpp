#pragma once
#include <array>
// Offline snapshot of local TWIST2 reference constants; no SDK dependency.
namespace offline_twist2 {
inline constexpr std::array<float, 29> kDefault = {
    -0.2F, 0, 0, 0.4F, -0.2F, 0,
    -0.2F, 0, 0, 0.4F, -0.2F, 0,
    0, 0, 0,
    0, 0.4F, 0, 1.2F, 0, 0, 0,
    0, -0.4F, 0, 1.2F, 0, 0, 0};
inline constexpr std::array<float, 29> kLower = {
    -2.5307F, -0.5236F, -2.7576F, -0.087267F, -0.87267F, -0.2618F,
    -2.5307F, -2.9671F, -2.7576F, -0.087267F, -0.87267F, -0.2618F,
    -2.618F, -0.52F, -0.52F,
    -3.0892F, -1.5882F, -2.618F, -1.0472F, -1.972222054F,
    -1.614429558F, -1.614429558F,
    -3.0892F, -2.2515F, -2.618F, -1.0472F, -1.972222054F,
    -1.614429558F, -1.614429558F};
inline constexpr std::array<float, 29> kUpper = {
    2.8798F, 2.9671F, 2.7576F, 2.8798F, 0.5236F, 0.2618F,
    2.8798F, 0.5236F, 2.7576F, 2.8798F, 0.5236F, 0.2618F,
    2.618F, 0.52F, 0.52F,
    2.6704F, 2.2515F, 2.618F, 2.0944F, 1.972222054F,
    1.614429558F, 1.614429558F,
    2.6704F, 1.5882F, 2.618F, 2.0944F, 1.972222054F,
    1.614429558F, 1.614429558F};
inline constexpr float kActionScale = 0.5F;
inline constexpr float kActionLimit = 2.0F;
inline constexpr float kJointLimitMargin = 0.05F;
inline constexpr std::array<float,29> kKp = {
    100, 100, 100, 150, 40, 40, 100, 100, 100, 150, 40, 40,
    150, 150, 150,
    40, 40, 40, 40, 20, 20, 20,
    40, 40, 40, 40, 20, 20, 20};
inline constexpr std::array<float,29> kKd = {
    2, 2, 2, 4, 2, 2, 2, 2, 2, 4, 2, 2,
    4, 4, 4,
    5, 5, 5, 5, 1, 1, 1,
    5, 5, 5, 5, 1, 1, 1};
inline constexpr std::array<float,29> kTorqueLimit = {
    88, 139, 88, 139, 50, 50, 88, 139, 88, 139, 50, 50,
    88, 50, 50,
    25, 25, 25, 25, 25, 5, 5,
    25, 25, 25, 25, 25, 5, 5};
}
