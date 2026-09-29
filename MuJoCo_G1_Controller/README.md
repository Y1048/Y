# MuJoCo / Mink G1 Bimanual Controller

현재 controller는 bilateral-only다.

## 핵심 파일

```text
g1_bimanual_runtime.py
g1_bimanual_unity_sim.py
g1_bimanual_sim.py
g1_bimanual_motion_policy.py
g1_bimanual_return.py
g1_bimanual_limits.py
g1_mink_shared.py
g1_arm_common.py
```

## Solve 구조

좌/우 팔마다 별도 configuration을 풀지 않는다. G1 current configuration 하나에서 left/right FrameTask를 같은 QP에 넣어 동시에 solve한다.

## Current profile

- 14 arm joints
- proximal 90 deg/s
- wrist 180 deg/s
- acceleration 90 deg/s^2
- compute 60 Hz
- IK tracking rate 1.0 s

## Unity input

```text
UDP 5020
schema g1.bimanual.unity.sim.v4
input_frame unity_display_world_v1
```

저장된 regression fixture를 위해 v1/legacy-relative decode만 compatibility boundary로 유지한다.

## Shared helpers

`g1_mink_shared.py`는 model/collision/math helper만 포함한다. CLI/UDP/motor output/standalone single-arm controller는 없다.

`g1_arm_common.py`는 양팔 joint/model/frame 정의를 제공한다.

## Return

return은 `g1_bimanual_return.py`의 staged motion을 사용하며 limits는 `g1_bimanual_limits.py`에 모여 있다.

## Validation

```bat
.venv-teleop\Scripts\python.exe -B -m unittest discover -s backend\tests -p "test_bimanual*.py"
```

실제 세션 재현은 `g1_bimanual_session_report.py --replay --strict`를 사용한다.
