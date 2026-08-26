# Unity G1 VR Frontend

이 Unity 프로젝트는 VR 오른손 tracking을 받아 G1 teleoperation target을 만들고, Mink/MuJoCo에서 돌아오는 G1 오른팔 state를 시각화한다.

## 현재 환경

```text
Unity            : 6000.5.4f1
Meta XR SDK      : 205.x
Target headset   : VR headset
Scene            : Assets/Scenes/SampleScene.unity
```

`com.unity.xr.oculus`가 아직 남아 있어 Unity 6에서 Oculus Plugin deprecation 경고가 표시될 수 있다. OpenXR migration은 wrist/frame 동작이 안정된 뒤 별도로 진행한다.

## 데이터 흐름

```text
VR right hand
   ↓
Unity hand/wrist source
   ↓ engagement/clutch
UDP 5005
   ↓
Mink/MuJoCo
   ↓
UDP 5006
   ↓
Unity G1 preview
```

## Frame 기준

외부 teleoperation wrist contract는 현재:

```text
right_wrist_yaw_link
```

이다.

Mink virtual-center controller 내부에서는 translation objective에 `right_wrist_roll_link`를 사용하지만 Unity가 수신/표시하는 actual wrist와 target 의미는 계속 `right_wrist_yaw_link`를 유지한다.

Unity와 MuJoCo의 동일 joint configuration에 대한 wrist-yaw FK parity 검증은 통과했다.

```powershell
.\tools\TEST_G1_MINK_FK_PARITY.bat
```

## VR wrist source

현재 위치와 orientation source의 역할을 구분한다.

- wrist position: VR rig의 `source_hand`를 우선 사용
- anatomical orientation: hand skeleton 기반 semantic orientation 사용
- skeleton wrist 위치가 palm 안쪽으로 보이던 문제 때문에 position source는 별도 compatibility layer로 처리

관련 코드:

```text
Assets/G1Teleop/G1WristSourceCompatibility.cs
Assets/G1Teleop/G1ExistingHandTargetBinder.cs
```

`G1ExistingHandTargetBinder.cs`는 local calibration/debug 변경 가능성이 높은 파일이므로 수정 전 현재 working tree를 반드시 확인한다.

## Marker 의미

현재 디버그 시각화 기준:

| Marker | 의미 |
| --- | --- |
| Cyan | 실제 VR wrist |
| Green | Mink target |
| Magenta | Unity에 replay된 실제 G1 `right_wrist_yaw_link` |

`G1DebugVisualFilter`는 axis/line debug object만 숨기고 engagement sphere는 유지한다.

## Engagement

사용자는 VR wrist marker를 G1 engagement target에 맞춘 뒤 일정 시간 유지해 clutch를 활성화한다.

Engage 순간의 VR pose와 G1 pose를 기준으로 저장하므로 controller가 absolute VR pose를 로봇에 바로 대입하지 않는다. Mink 측에서도 같은 철학으로 clutch-relative target을 생성한다.

```text
engage VR pose
engage G1 pose
      ↓
relative hand movement / rotation
      ↓
G1 target delta
```

이 방식은 teleoperation을 시작하는 순간 target이 튀는 zero-jump 문제를 줄인다.

## 좌표계

```text
Unity operator frame
+X = right
+Y = up
+Z = forward

MuJoCo G1 frame
+X = forward
+Y = left
+Z = up
```

Python 공통 변환 기준은 `g1_right_arm_common.py`의 `OPERATOR_TO_ROBOT_BASIS`에 정의되어 있다.

## UDP

### Unity → Mink: 5005

오른손 target position/orientation과 tracking validity를 전송한다.

### Mink → Unity: 5006

오른팔 7개 joint state와 wrist/target 상태를 수신한다.

Virtual-center live controller에서도 외부 state frame은 `right_wrist_yaw_link`로 유지한다.

## 실행

기본 통합 실행:

```powershell
.\START_VR_HAND_TO_MUJOCO.bat
```

현재 최신 virtual-center IK를 직접 시험할 때는 Mink controller를 별도로:

```powershell
.\START_MUJOCO_ONLY.bat
```

실행하고 Unity 프로젝트에서 Play한다.

UDP `5005`를 이미 다른 controller가 사용 중이면 새 controller를 동시에 실행하지 않는다.

## 주요 코드 위치

```text
Assets/G1Teleop/
```

여기에서 주로 확인할 항목:

```text
hand target binder
wrist source compatibility
UDP target sender
UDP robot-state receiver
G1 right-arm preview
actual wrist-yaw marker
debug visual filter
engagement target policy
```

## 디버깅할 때 구분할 것

### Green target과 Magenta actual wrist 위치가 어긋남

먼저 Mink runtime status의:

```text
position_error_m
orientation_error_deg
collision_limit_nearby
```

를 확인한다. Unity 표시 문제인지 IK 자체 tracking 문제인지 분리한다.

### 손목 방향만 가끔 크게 틀어짐

다음 순서로 확인한다.

```text
1. Mink orientation_error_deg
2. wrist joint-limit margin
3. collision status
4. VR anatomical orientation validity
```

Mink error가 작은데 Unity/VR visual만 다르면 frame/source 쪽 문제이고, Mink error 자체가 크면 IK feasibility/joint-limit/collision 쪽 문제다.

## 주의

Unity frontend에서 frame 기준을 임의로 `right_wrist_roll_link`로 바꾸지 않는다. 내부 IK virtual center와 외부 visualization frame은 의도적으로 분리되어 있다.
