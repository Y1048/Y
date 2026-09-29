# G1 Teleop Code Guide

## 1. Integrated launcher

- `tools/START_G1_VR_TELEOP.bat`: 기본 진입점
- `tools/G1_VR_TELEOP_LAUNCH.py`: worker/Unity/camera orchestration
- `tools/G1_INPUT_OBSERVATION_LAUNCH.py`: send/receive/Omni/arm worker command
- `tools/g1_quiet_observation.py`: background worker lifetime
- `tools/g1_process_lifetime.py`: reuse/duplicate protection

## 2. Bilateral IK

- `g1_bimanual_runtime.py`: 실행 wrapper
- `g1_bimanual_unity_sim.py`: UDP schema/state machine
- `g1_bimanual_sim.py`: shared MuJoCo configuration + paired tasks
- `g1_bimanual_motion_policy.py`: target shaping / limits
- `g1_bimanual_return.py`: staged return
- `g1_bimanual_limits.py`: bilateral limit source of truth
- `g1_mink_shared.py`: model/collision/math helper only
- `g1_arm_common.py`: G1 arm/model/frame definitions

`g1_mink_shared.py`에는 CLI, UDP sender, motor output, standalone right-arm controller가 없다.

## 3. Regression parity helpers

다음은 live single-arm controller가 아니라 bilateral regression에서 upstream/standard Mink와 비교하기 위한 helper다.

- `g1_standard_mink_planner.py`
- `g1_upstream_mink_tracking.py`
- `g1_mink_feasible_target.py`
- `g1_mink_trajectory.py`
- `g1_virtual_center_tasks.py`

## 4. Unity

현재 핵심:

- `G1BimanualSimulationSender.cs`
- `G1ExistingHandTargetBinder.cs`
- `G1UnityRightArmPreview.cs` — 이름은 과거 명칭이지만 현재 SampleScene의 bimanual preview component
- `G1OfficialRig.cs`
- `G1RobotStateUdpReceiver.cs`
- `G1LowStateLegView.cs`
- `G1HeadLockedCamera.cs`
- `G1HeadCameraPiP.cs`
- `G1OmniBodyHeading.cs`

## 5. Camera

- `tools/G1_CAMERA_LAUNCH.py`
- `tools/g1_camera_ssh.py`
- `tools/START_G1_CAMERA_TO_UNITY.bat`
- `Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs`

WSL camera fallback은 제거했다. 현재 camera transport는 SSH 하나다.

## 6. Omni

- `hardware/g1_arm_bridge/g1_omni_velocity_gateway.py`
- `hardware/g1_arm_bridge/g1_velocity_discovery.py`
- `hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py`

## 7. Setup / maintenance

- `tools/SETUP_G1_VR_TELEOP.bat/.py`
- `tools/requirements-teleop.txt`
- `tools/g1_teleop_dependencies.py`
- Ethernet configure/restore scripts
- `tools/BUILD_AND_INSTALL_VR_APK.bat`

## 8. Tests

현재 유지하는 테스트는 bilateral IK/replay/return, launcher/process/dependency, SSH camera, LowState/observation, Omni mapping/transport, current MuJoCo helper math만 검증한다.

과거 Gate5/6/7, PD/sysid, MJLab, right-arm jog, startup-recovery 실험은 제거했다.

## 9. 변경 원칙

1. current execution graph를 먼저 확인한다.
2. 사용자 dirty/untracked를 reset/clean하지 않는다.
3. 작은 변경 후 회귀를 실행한다.
4. `G1.zip --replay --strict` 재현성을 유지한다.
5. physical motor output은 별도 명시적 승인 전 추가하지 않는다.
