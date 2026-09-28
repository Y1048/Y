# MuJoCo / Mink G1 Bimanual Controller

이 폴더의 현재 기본 상체 경로는 **G1 양팔 14축 differential QP IK**다.

예전 오른팔 전용 controller는 비교/reference와 공통 모델 helper로 일부 유지하지만, 기본 통합 런처는 `g1_bimanual_runtime.py`를 사용한다.

## 현재 진입점

```text
tools/START_G1_VR_TELEOP.bat
  -> tools/G1_VR_TELEOP_LAUNCH.py
  -> tools/G1_INPUT_OBSERVATION_LAUNCH.py
  -> MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py
  -> g1_bimanual_unity_sim.py
```

bimanual backend는 loopback UDP `5020`에서 Unity 양손 packet을 받고 60 Hz로 계산한다.

## 핵심 파일

| 파일 | 역할 |
| --- | --- |
| `scripts/g1_bimanual_runtime.py` | MuJoCo version/runtime guard, 실행 진입 |
| `scripts/g1_bimanual_unity_sim.py` | Unity packet decode, 60 Hz cycle, input filtering |
| `scripts/g1_bimanual_sim.py` | 양팔 QP, collision/boundary guard, braking, return 상태 |
| `scripts/g1_bimanual_motion_policy.py` | 팔별 FrameTask/posture/workspace projection/priority |
| `scripts/g1_bimanual_limits.py` | joint 속도·가속도·tracking rate |
| `scripts/g1_bimanual_return.py` | staged safe return |
| `scripts/g1_bimanual_session_report.py` | 기록 session replay/report 도구 |

## 제어 관절

각 팔 7축, 총 14축을 사용한다.

```text
left/right 각각:
shoulder pitch / roll / yaw
elbow
wrist roll / pitch / yaw
```

양팔은 같은 MuJoCo configuration 안에서 풀리며 inter-arm collision과 다른 robot geometry collision을 함께 검사한다.

## 현재 motion profile

`g1_bimanual_limits.py` 기준:

```text
proximal velocity limit = 90 deg/s
wrist velocity limit    = 180 deg/s
joint acceleration      = 90 deg/s²
IK tracking rate        = 1.0 /s
simulation dt           = 1/60 s
```

`ArmMotionPolicy.prepare()`의 현재 tracking gain:

```python
self.wrist_task.gain = min(
    base.FRAME_GAIN,
    self.dt_s * IK_TRACKING_RATE_S)
```

현재 60 Hz, rate 1.0에서는 약 `0.01667`이다. `base.FRAME_GAIN=0.35`는 상한 및 posture 상대비 계산에 남아 있다.

이전에 사용했던 Jacobian pseudo-inverse correction/rate heuristic은 production bimanual tracking 경로에서 제거됐다.

## Task 구조

각 팔은 기본적으로 다음 task를 준비한다.

```text
wrist FrameTask
posture task
damping task
wrist-priority task
shoulder-comfort task
optional elbow-clearance assist
```

wrist task frame은 각 팔의 `*_wrist_yaw_link`다. position과 orientation은 같은 FrameTask로 풀되 joint limit/collision 상황에서 보조 priority가 작동할 수 있다.

## Unity 입력

현재 world-frame packet:

```text
schema      = g1.bimanual.unity.sim.v4
input_frame = unity_display_world_v1
UDP         = 127.0.0.1:5020
```

legacy test path는 `g1.bimanual.unity.sim.v1 / legacy_relative`도 decode할 수 있지만 현재 scene은 v4 world-frame을 사용한다.

`g1_bimanual_unity_sim.py`는 packet size, JSON depth, duplicate key, session/sequence, sender time, 양손 tracked flag, position/quaternion, world frame/base yaw를 검증한다.

## Filtering

양손 모두 Python에서 동일한 filter를 쓴다.

```text
position tau = 60 ms
rotation tau = 50 ms
```

tracking gap은 smoothing을 우회하지 않으며 양손 중 하나가 invalid이면 정상 tracking update로 만들지 않는다.

## 상태와 return

개략적인 state:

```text
ready -> tracking -> returning -> ready
```

pinch, tracking loss, stale/fault 조건과 return 정책은 `g1_bimanual_unity_sim.py`, `g1_bimanual_sim.py`, `g1_bimanual_return.py`에서 관리한다.

return은 단순 관절 직선 복귀가 아니라 near-hands/collision 조건을 고려하는 staged return을 사용한다.

## 현재 알려진 reachability 이슈

최근 실제 session replay에서 큰 position error는 rate 부족만으로 설명되지 않았다.

정지 target hold, orientation 제거, posture/damping 제거, 다중 초기값 nonlinear IK를 비교한 결과 일부 world target은 현재 G1 팔 기하에서 실제로 도달 불가능한 영역에 있었다.

현재 결론:

```text
speed profile 문제    : 크게 개선됨
남은 큰 residual 문제 : human world target vs G1 workspace mismatch
```

따라서 production에는 dynamic pseudo-inverse rate, adaptive position gain, global movement compression, permanent reach clamp를 추가하지 않았다.

후속 retargeting이 필요하면 current controller와 분리된 mapping layer로 설계한다.

## 검증

현재 핵심 bimanual regression은 `backend/tests/test_bimanual_*.py`에 있다.

최근 기준:

```text
116 tests PASS
fixture historical exact replay max q diff = 0
G1.zip actual-session strict replay PASS; max q diff = 2.000621890374532e-13 rad
near-hands / return / rotation-quality gates PASS
```

## Deprecated single-arm code — 직접 실행 금지

다음 계열은 현재 default bimanual controller가 아니다.

```text
run_mink_g1_right_arm_*.py
START_VR_HAND_TO_MUJOCO*.bat
UDP 5005 / 5006 deprecated single-arm path
```

다만 bimanual code가 공통 model/joint constants와 일부 helper를 `run_mink_g1_right_arm_prototype.py`에서 가져오므로 파일을 임의 삭제하지 않는다.

현재 source of truth는 `g1_bimanual_*` 파일과 `tools/START_G1_VR_TELEOP.bat`이다.
