# G1 Teleop Architecture

이 문서는 현재 `main`의 기본 실행 구조를 설명한다. 과거 single-arm, Gate 실험, validation 산출물은 기본 구조와 분리해서 본다.

## 1. 기본 원칙

- 기본 upper-body runtime은 **양팔 14축**이다.
- `tools/START_G1_VR_TELEOP.bat`은 observation/simulation 경로이며 motor output이 없다.
- Unity와 Python bimanual backend는 PC loopback UDP `5020`을 사용한다.
- Omni yaw와 upper-body wrist target은 `unity_display_world_v1` 계약을 사용한다.
- 실제 G1 motor authority는 `hardware/g1_arm_bridge/`의 별도 경계다.

## 2. 구성도

```text
Quest hands
   |
   v
Unity_G1_VR / G1BimanualSimulationSender
   | UDP 5020, v4 world frame
   v
g1_bimanual_runtime.py
   |
   v
g1_bimanual_unity_sim.py
   |
   v
BimanualSimulation
   |
   +-- left ArmMotionPolicy (7 DoF)
   +-- right ArmMotionPolicy (7 DoF)
   +-- inter-arm / robot collision
   +-- checked braking
   `-- staged return

Omni Connect ws://127.0.0.1:32123
   `-- g1_omni_velocity_gateway.py --dry-run

G1 LowState
   `-- read-only observation / display

G1 VideoClient
   `-- SSH -> PC -> TCP 5011 -> Unity PiP (RobotRoot parent)
```

## 3. 기본 launcher

```text
tools/START_G1_VR_TELEOP.bat
  -> dependency check
  -> G1_VR_TELEOP_LAUNCH.py
     -> lowstate observation
     -> input send observation
     -> Omni dry-run observation
     -> bimanual arm simulation worker
     -> camera worker
     -> Unity editor open/reuse
```

동일 옵션의 기존 process가 있으면 보존하고 중복 실행하지 않는다. 기존 process의 옵션이 다르면 자동 종료하지 않고 오류로 중단한다.

## 4. Bimanual backend

`g1_bimanual_runtime.py`가 검증된 MuJoCo 환경을 선택한 뒤 mode에 따라 bimanual module을 import한다.

기본 Unity mode:

```text
g1_bimanual_runtime.py --mode unity --headless --compute-hz 60
  -> g1_bimanual_unity_sim.py
```

`g1_bimanual_unity_sim.py`는 UDP `127.0.0.1:5020`에 bind한다. packet provenance, schema, frame, sequence, timestamp, 양손 pose를 검증한 뒤 60 Hz simulation cycle로 전달한다.

## 5. QP 구조

현재 bimanual simulation은 하나의 MuJoCo configuration에서 양팔을 함께 푼다.

팔별 기본 task:

```text
wrist FrameTask
posture
damping
wrist priority
shoulder comfort
optional elbow assist
```

양팔 사이와 다른 robot geometry의 collision/boundary를 함께 검사한다.

현재 controller bounds:

```text
proximal velocity = 90 deg/s
wrist velocity    = 180 deg/s
acceleration      = 90 deg/s²
tracking rate     = 1.0 /s
dt                = 1/60 s
```

## 6. Unity world-frame contract

현재 scene은 양손 absolute aligned world wrist pose를 보낸다.

```text
schema      = g1.bimanual.unity.sim.v4
input_frame = unity_display_world_v1
base_yaw    = Omni initial-relative yaw
```

Python은 Unity world position을 `BASIS`로 MuJoCo 축에 대응시키고 base yaw를 적용한다.

legacy `g1.bimanual.unity.sim.v1 / legacy_relative`는 test/backward compatibility 용도다.

## 7. Timing

- bimanual compute: 60 Hz
- input send observation: 60 Hz
- observation console display: 100 Hz
- camera: 별도 저대역폭 read-only transport

`sender_time_s`는 packet ordering/filtering에 쓰며 다른 host의 freshness를 wall-clock subtraction으로 계산하지 않는다. receipt freshness는 local monotonic time 기준이다.

## 8. Return / braking

tracking이 끝나면 즉시 home joint linear interpolation을 하지 않는다.

near-hands, collision, tracking-loss reason에 따라 separation / safe waypoint / home / settle stage를 사용할 수 있다.

checked braking은 unsafe candidate가 그대로 적용되는 것을 막는다.

## 9. Observation과 motor authority 분리

기본 통합 launcher에서 실행되는 arm/Omni/LowState/camera worker는 motor publisher를 만들지 않는다.

`hardware/g1_arm_bridge/`에는 별도의 physical path가 있다. 현재 physical control 목표도 **양팔 14축만 지원**한다. 소스에 남은 right-arm-only bounded/live contract는 deprecated이며 current authority path로 사용하지 않는다.

## 10. PiP

PiP는 생성 순간 사용자 시야 앞 pose를 사용하지만 이후 parent는 `G1 RobotRoot`다.

따라서 HMD head movement가 PiP parent transform이 아니다.

## 11. 현재 남은 구조적 문제

속도 controller는 fixed rate 1.0으로 단순화했고 실제 체감 속도가 개선됐다.

남은 큰 wrist residual은 상당 부분 human absolute world target과 G1 reachable workspace 차이로 분류한다. 이를 speed gain 문제와 섞지 않는다.

retargeting을 추가한다면 Unity world-frame/Omni 계약을 유지하면서 별도의 mapping layer로 구현한다.

## 12. Legacy 경로

다음은 기본 경로가 아니다.

- `START_VR_HAND_TO_MUJOCO*.bat`
- `run_mink_g1_right_arm_*` controller
- UDP `5005/5006` deprecated single-arm Unity-Mink path (직접 실행 금지)
- 과거 Gate/PD/sysid 실험

legacy 코드는 regression/reference 또는 specialized physical tooling 때문에 남아 있을 수 있다.

## 13. 검증

현재 bimanual regression baseline은 116 tests PASS다. `backend/tests/test_bimanual_*.py`를 source of truth로 사용한다.
