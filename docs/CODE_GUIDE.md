# G1 Teleop Code Guide

현재 코드를 읽을 때는 **bimanual 기본 경로**와 **legacy/specialized 경로**를 먼저 구분한다.

## 1. 기본 실행 시작점

```text
tools/START_G1_VR_TELEOP.bat
  -> tools/G1_VR_TELEOP_LAUNCH.py
  -> tools/G1_INPUT_OBSERVATION_LAUNCH.py
```

현재 기본 launcher는 bilateral IK, Omni observation, LowState observation, camera를 묶지만 motor output은 하지 않는다.

## 2. 양팔 IK 코드

| 파일 | 먼저 볼 함수/역할 |
| --- | --- |
| `MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py` | `main`, engine guard |
| `.../g1_bimanual_unity_sim.py` | `decode`, `UnityCycle`, `main` |
| `.../g1_bimanual_sim.py` | `BimanualSimulation`, `step`, collision/boundary guards |
| `.../g1_bimanual_motion_policy.py` | `ArmMotionPolicy`, `prepare`, workspace projection |
| `.../g1_bimanual_limits.py` | current velocity/acceleration/rate constants |
| `.../g1_bimanual_return.py` | staged return |

현재 수치를 바꾸기 전에 `g1_bimanual_limits.py`와 `ArmMotionPolicy.prepare()`를 같이 확인한다.

## 3. 현재 speed profile

```text
PROXIMAL_VELOCITY_LIMIT_DEG_S = 90
WRIST_VELOCITY_LIMIT_DEG_S = 180
JOINT_ACCELERATION_LIMIT_DEG_S2 = 90
IK_TRACKING_RATE_S = 1.0
```

tracking gain은 `min(base.FRAME_GAIN, dt * IK_TRACKING_RATE_S)`다.

과거 pseudo-inverse correction/rate heuristic을 다시 넣지 않는다. 최근 실제 로그에서는 fixed 1.0이 체감 속도를 크게 개선했고 추가 rate 증가 이득은 작았다.

## 4. Unity 양손 입력

현재 중심 파일:

```text
Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs
Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs
Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs
```

sender 기본값:

```text
port = 5020
schema = g1.bimanual.unity.sim.v4
input_frame = unity_display_world_v1
```

현재 `useExistingScene` path에서 `position_m`은 aligned absolute world wrist pose다.

`OperatorTargetDelta`는 binder helper에 남아 있지만 현재 v4 world sender 계약과 같은 의미가 아니다.

## 5. PiP

관련 파일:

```text
G1HeadCameraPiP.cs
G1HeadLockedCamera.cs
G1UnityRightArmPreview.cs
```

현재 parent는 `RobotRoot`. `CenterEyeAnchor`는 초기 화면 배치 계산에만 관여할 수 있고 지속 parent가 아니다.

## 6. Omni

`hardware/g1_arm_bridge/g1_omni_velocity_gateway.py`는 기본 launcher에서 `--dry-run --process-hz 60`으로 실행한다.

Omni Connect endpoint는 `ws://127.0.0.1:32123`이다.

현재 launcher의 Omni worker는 observation 경로이며 motor command transport를 활성화하지 않는다.

## 7. G1 observation

`tools/g1_lowstate_view.py`, `tools/G1_INPUT_RECEIVE_AUDIT.py`, camera SSH tooling은 기본 launcher의 observation 구성이다.

read-only LowState display와 motor authority를 동일한 것으로 취급하지 않는다.

## 8. Physical hardware code

`hardware/g1_arm_bridge/`는 별도 authority boundary다.

여기에는 과거 right-arm-only bounded/live contract와 양팔 Arm SDK/HOLD foundation이 함께 남아 있다. **현재 지원 정책은 bilateral-only**이므로 right-arm-only path는 실행하지 않고 historical/deprecated로 취급한다.

실제 출력 변경 전에는 해당 hardware README/checklist와 config authorization을 별도로 검증한다.

## 9. Deprecated single-arm 코드 — 직접 실행 금지

`run_mink_g1_right_arm_prototype.py`는 bimanual code가 model constants/helper를 재사용하므로 아직 중요하다.

하지만 다음은 기본 실행 설명이 아니다.

```text
START_VR_HAND_TO_MUJOCO*.bat
UDP 5005/5006
right-hand-only Unity sender
virtual-center single-arm controller
```

새 기능을 넣을 때 legacy 경로를 default로 착각하지 않는다.

## 10. Known workspace issue

최근 분석으로 큰 position residual의 상당 부분이 speed가 아니라 reachability 문제임을 확인했다.

다음 실험은 production에 반영하지 않았다.

- adaptive position gain
- permanent reach sphere clamp
- global movement scaling
- relative mapping rollback

retargeting을 구현할 경우 별도 layer로 분리하고 world-frame/Omni invariance를 회귀로 고정한다.

## 11. 테스트

현재 핵심 회귀:

```text
test_bimanual_boundaries
test_bimanual_marker_feedback
test_bimanual_motion_quality
test_bimanual_near_hands_sweep
test_bimanual_quest_reengage
test_bimanual_recorded_session
test_bimanual_return
test_bimanual_runtime
test_bimanual_session_report
test_bimanual_sim
test_bimanual_unity_sim
```

정상 기준은 116 tests PASS.

## 12. 변경 전 확인 순서

1. 증상을 로그/코드로 먼저 재현한다.
2. 첫 원인을 사실로 가정하지 않는다.
3. 단일 변수 offline 실험으로 분리한다.
4. current-profile regression과 historical exact replay를 구분한다.
5. 실제 code 변경 전 수정 파일, 현재 동작, 변경 내용, 이유, 예상 효과를 사용자에게 제시한다.
6. 승인 후에만 source를 수정한다.
7. 기존 dirty/untracked 파일을 reset/clean하지 않는다.
