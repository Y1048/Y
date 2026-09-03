"""Local source-contract and extracted C++ math tests. No robot/network access."""

import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback


experiment_path = Path(__file__).resolve().parent
project_path = experiment_path.parents[1]
reference_path = project_path / "references/lower_body/twist2_deploy/cpp_g1_twist2"
source_hash = "10e2ddec853b33b9033ee7c343d21ac5d6a3c7986ba6aa96be859ed29048dca4"
common_hash = "4b6a6842ab8ff8701c6d8a99e1342f6f6c78856b50288cbf22ec2339a882e53a"


def CheckCondition(condition, message):
    if not condition:
        raise RuntimeError(message)


def GetFunction(source, name):
    start = source.index("inline float " + name + "(")
    opening = source.index("{", start)
    depth = 1
    cursor = opening + 1
    while depth:
        depth += (source[cursor] == "{") - (source[cursor] == "}")
        cursor += 1
    return source[start:cursor]


def GetDeclaration(source, name):
    pattern = r"(?:constexpr|const) [^;\n]*\b" + re.escape(name) + r"\s*=.*?;"
    match = re.search(pattern, source, re.DOTALL)
    CheckCondition(match is not None, "Missing declaration: " + name)
    return match.group(0)


def GetLinuxPath(path):
    if os.name != "nt":
        return str(path)
    result = subprocess.run(
        ["wsl.exe", "-d", "Ubuntu", "--", "wslpath", "-a", path.as_posix()],
        capture_output=True, text=True, check=True, timeout=20,
    )
    return result.stdout.strip()


def RunLocal(command, expected_code=0):
    prefix = ["wsl.exe", "-d", "Ubuntu", "--"] if os.name == "nt" else []
    result = subprocess.run(prefix + command, capture_output=True, text=True, timeout=60)
    CheckCondition(
        result.returncode == expected_code,
        f"Local command failed ({result.returncode}): {command}\n"
        + result.stdout + result.stderr,
    )
    return result.stdout.strip()


def CheckSources(output_path):
    for name, digest in (("twist2_static_stand.cpp", source_hash), ("twist2_common.hpp", common_hash)):
        CheckCondition(hashlib.sha256((reference_path / name).read_bytes()).hexdigest() == digest,
                       "Reference changed; re-review before testing: " + name)
    original = (reference_path / "twist2_static_stand.cpp").read_text(encoding="utf-8")
    source = (experiment_path / "twist2_right_arm_trial.cpp").read_text(encoding="utf-8")
    expected = original.replace("Left", "Right").replace("left", "right")
    expected = expected.replace("kRightShoulderPitch = 15;", "kRightShoulderPitch = 22;")
    expected = expected.replace("kRightArmBegin = 15;", "kRightArmBegin = 22;")
    expected = expected.replace("captured waist/right arm held;", "captured waist/left arm held;")
    expected = expected.replace("g1_twist2_static_stand_", "g1_twist2_right_arm_trial_")
    expected = expected.replace("=== G1 TWIST2 STATIC STAND ===", "=== G1 TWIST2 RIGHT ARM TRIAL ===")
    CheckCondition(source.rstrip() == expected.rstrip(), "Unexpected derivative changes")
    CheckCondition('ChannelPublisher<LowCmd>' in source and '"rt/lowcmd"' in source,
                   "Reference command owner was lost")
    CheckCondition('"rt/arm_sdk"' not in source, "Competing Arm SDK path added")
    cmake = (experiment_path / "CMakeLists.txt").read_text(encoding="utf-8")
    CheckCondition("G1_REVIEWED_RIGHT_ARM_TRIAL" not in cmake and
                   "ENABLE_REVIEWED_PHYSICAL_TRIAL" not in cmake,
                   "Added build gate must not remain")
    diff = "".join(difflib.unified_diff(original.splitlines(keepends=True),
                                      source.splitlines(keepends=True),
                                      fromfile="reference/twist2_static_stand.cpp",
                                      tofile="experiment/twist2_right_arm_trial.cpp"))
    (output_path / "source_changes.diff").write_text(diff, encoding="utf-8")
    return source


def CheckMath(source, output_path):
    common = (reference_path / "twist2_common.hpp").read_text(encoding="utf-8")
    declarations = "\n".join(GetDeclaration(common, name) for name in
                              ("kDofs", "kJointLimitMargin", "kLower", "kUpper"))
    declarations += "\n" + "\n".join(GetDeclaration(source, name) for name in
                                      ("kRightArmBegin", "kRightArmDofs", "kKeyboardIncrement",
                                       "kKeyboardBaseTargetRate", "kKeyboardPlusKeys",
                                       "kKeyboardZeroKeys", "kKeyboardMinusKeys"))
    fixture = "#include <algorithm>\n#include <array>\n#include <cassert>\n#include <cmath>\n#include <iostream>\n"
    fixture += declarations + "\n" + GetFunction(common, "update_keyboard_joint_command")
    fixture += "\n" + GetFunction(common, "rate_limited_target")
    fixture += r'''
int main()
{
    static_assert(kRightArmBegin == 22 && kRightArmDofs == 7 && kDofs == 29);
    assert(std::abs(kLower[23] - (-2.2515F)) < 1e-6F);
    assert(std::abs(kUpper[23] - 1.5882F) < 1e-6F);
    assert(kLower[23] != kLower[16] && kUpper[23] != kUpper[16]);
    for (std::size_t arm = 0; arm < kRightArmDofs; ++arm)
    {
        const auto joint = kRightArmBegin + arm;
        const float lower = kLower[joint] + kJointLimitMargin;
        const float upper = kUpper[joint] - kJointLimitMargin;
        std::array<float, kDofs> commands{};
        commands.fill(0.3F);
        const auto baseline = commands;
        commands[joint] = update_keyboard_joint_command(
            kKeyboardPlusKeys[arm], kKeyboardPlusKeys[arm], kKeyboardZeroKeys[arm],
            kKeyboardMinusKeys[arm], commands[joint], lower, upper, kKeyboardIncrement);
        assert(commands[joint] > baseline[joint]);
        assert(std::abs(commands[joint] - baseline[joint] - 0.02F) < 1e-6F);
        for (std::size_t index = 0; index < kDofs; ++index)
        {
            if (index != joint) { assert(commands[index] == baseline[index]); }
        }
        const auto minus = update_keyboard_joint_command(
            kKeyboardMinusKeys[arm], kKeyboardPlusKeys[arm], kKeyboardZeroKeys[arm],
            kKeyboardMinusKeys[arm], baseline[joint], lower, upper, kKeyboardIncrement);
        assert(minus < baseline[joint]);
        const auto zero = update_keyboard_joint_command(
            kKeyboardZeroKeys[arm], kKeyboardPlusKeys[arm], kKeyboardZeroKeys[arm],
            kKeyboardMinusKeys[arm], baseline[joint], lower, upper, kKeyboardIncrement);
        assert(zero == 0.0F);
        for (int step = 0; step < 2000; ++step)
        {
            commands[joint] = update_keyboard_joint_command(
                kKeyboardPlusKeys[arm], kKeyboardPlusKeys[arm], kKeyboardZeroKeys[arm],
                kKeyboardMinusKeys[arm], commands[joint], lower, upper, kKeyboardIncrement);
        }
        assert(commands[joint] == upper);
        for (int step = 0; step < 2000; ++step)
        {
            commands[joint] = update_keyboard_joint_command(
                kKeyboardMinusKeys[arm], kKeyboardPlusKeys[arm], kKeyboardZeroKeys[arm],
                kKeyboardMinusKeys[arm], commands[joint], lower, upper, kKeyboardIncrement);
        }
        assert(commands[joint] == lower);
        for (int multiplier = 1; multiplier <= 9; ++multiplier)
        {
            for (const float goal : {lower, upper, 0.3001F, 0.2999F})
            {
                float target = baseline[joint];
                const float rate = kKeyboardBaseTargetRate * multiplier;
                for (int step = 0; step < 5000; ++step)
                {
                    const float previous = target;
                    target = rate_limited_target(target, goal, rate, 0.02F);
                    assert(std::abs(target - previous) <= rate * 0.02F + 1e-6F);
                    assert(target >= std::min(previous, goal) - 1e-6F);
                    assert(target <= std::max(previous, goal) + 1e-6F);
                }
                assert(std::abs(target - goal) < 1e-5F);
            }
        }
        std::cout << "PASS right joint " << joint << "\n";
    }
}
'''
    fixture_path = output_path / "extracted_keyboard_math.cpp"
    fixture_path.write_text(fixture, encoding="utf-8")
    binary_path = output_path / "extracted_keyboard_math"
    RunLocal(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", GetLinuxPath(fixture_path), "-o", GetLinuxPath(binary_path)])
    return RunLocal([GetLinuxPath(binary_path)])


def RunVerification():
    output_path = project_path / "logs/test_results" / ("twist2_right_arm_offline_" + time.strftime("%Y%m%d_%H%M%S"))
    output_path.mkdir(parents=True, exist_ok=False)
    result_path = output_path / "result.json"
    result = {"status": "FAIL", "robot_access": False, "dds_publisher": False,
              "full_controller_build_verified": False, "physical_sign_verified": False,
              "reference_sha256": source_hash, "common_sha256": common_hash}
    try:
        source = CheckSources(output_path)
        result["source_contract"] = "PASS"
        result["compiled_math"] = CheckMath(source, output_path)
        result["status"] = "PASS"
        print(result["compiled_math"])
        print("PASS: reference preserved; only right-arm indices and names changed")
        print("Full controller build / real joint direction: NOT VERIFIED")
        return 0
    except Exception as error:
        result["error"] = str(error)
        traceback.print_exc()
        print("[ACTION] Check the first error. These tests require local WSL Ubuntu and g++ on Windows.")
        print("[ACTION] Do not change the G1 or unlock physical output to resolve an offline failure.")
        return 1
    finally:
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Result saved to: " + str(result_path))


if __name__ == "__main__":
    sys.exit(RunVerification())
