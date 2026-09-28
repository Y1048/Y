# Unity G1 VR Frontend

현재 Unity 프로젝트는 Quest **양손** 입력, Omni 기준 G1 root, bimanual IK 표시, G1 LowState 표시, 전면 카메라 PiP를 담당한다.

Unity 고정 버전: `6000.5.4f1`.

## 현재 기본 경로

```text
Quest left/right hands
        |
        v
G1ExistingHandTargetBinder (L/R)
        |
        v
G1BimanualSimulationSender
        | UDP 127.0.0.1:5020
        v
Python bimanual Mink/MuJoCo
        `-- feedback -> Unity
```

기본 scene의 양팔 sender는 `useExistingScene` world-frame 경로를 사용한다.

```text
schema      = g1.bimanual.unity.sim.v4
input_frame = unity_display_world_v1
port        = 5020
```

## 양손 engagement

`G1BimanualSimulationSender`는 왼손과 오른손 binder를 모두 요구한다.

tracking 시작 조건은 양손 freshness/tracking/alignment, zone 상태, pinch 상태와 backend readiness를 함께 검사한다. 한 손만 유효하다고 양팔 tracking을 정상 상태로 만들지 않는다.

Unity marker와 status text는 raw tracked wrist, IK target, backend 상태를 구분해서 표시한다.

## World-frame 입력

현재 sender는 bimanual world schema에서 각 손의 absolute aligned world wrist pose를 보낸다.

- `left.position_m` / `left.quaternion_wxyz`
- `right.position_m` / `right.quaternion_wxyz`
- `base_yaw_rad`
- `input_frame=unity_display_world_v1`

`base_yaw_rad`은 Unity/MuJoCo 축 대응에 맞춰 Omni yaw 부호를 변환한다.

binder 안에는 engage-relative `OperatorTargetDelta`와 body-translation compensation 기능도 남아 있지만 현재 world-frame bimanual sender의 기본 `position_m` 계약은 absolute aligned wrist pose다. 두 계약을 혼용하지 않는다.

## Omni / robot root

`G1OmniBodyHeading`이 G1 root의 초기-relative yaw 기준을 제공한다.

upper-body world target과 rotating G1 base는 동일한 초기 정렬 계약을 사용한다. 자세한 내용은 [../docs/OMNI_WORLD_UPPER_BODY_20260922.md](../docs/OMNI_WORLD_UPPER_BODY_20260922.md)를 따른다.

## PiP 카메라

현재 PiP는 HMD에 붙지 않는다.

```text
생성 시: 사용자 시야 앞 world pose 계산
생성 후: parent = G1 RobotRoot
```

따라서 `CenterEyeAnchor`를 계속 따라가는 구조가 아니다.

관련 파일:

```text
Assets/G1Teleop/G1HeadCameraPiP.cs
Assets/G1Teleop/G1HeadLockedCamera.cs
Assets/G1Teleop/G1UnityRightArmPreview.cs
```

카메라 이미지 경로는 PC loopback TCP `5011`이다. camera stream은 motor authority와 무관하다.

## 표시 source

Unity에는 목적이 다른 simulation feedback, measured G1 LowState, recorded replay, camera PiP source가 존재한다.

measured state display와 simulation feedback을 같은 source로 취급하지 않는다. measured state 표시는 read-only이며 motor command를 의미하지 않는다.

## 핵심 컴포넌트

| 파일 | 역할 |
| --- | --- |
| `G1BimanualSimulationSender.cs` | 양손 packet 송수신, engagement, target/status |
| `G1ExistingHandTargetBinder.cs` | Quest wrist/head tracking, calibration/helper |
| `G1OmniBodyHeading.cs` | Omni yaw와 Unity G1 root 정렬 |
| `G1UnityRightArmPreview.cs` | G1 preview root와 arm visualization 공통부 |
| `G1HeadCameraPiP.cs` | G1 RobotRoot 기준 PiP |
| `G1HeadLockedCamera.cs` | camera/PiP 생성 wiring |
| `G1RobotStateUdpReceiver.cs` | simulation/measured state display source 처리 |

파일명에 `RightArm`이 남아 있어도 현재 bimanual scene의 shared preview 역할로 쓰이는 부분이 있다. 이름만 보고 현재 controller가 오른팔 전용이라고 판단하면 안 된다.

## Deprecated single-arm path — 지원하지 않음

다음 항목은 현재 기본 bimanual 경로가 아니다.

```text
G1ExistingTargetUdpSender
UDP 5005 / 5006
right-hand-only documentation
START_VR_HAND_TO_MUJOCO.bat 계열
```

legacy scene/tool 지원 때문에 코드가 남아 있을 수 있다. 현재 실행은 `tools/START_G1_VR_TELEOP.bat`을 기준으로 한다.

## 안전 경계

Unity 프로젝트는 현재 기본 통합 경로에서 G1 motor publisher를 만들지 않는다.

Unity가 보내는 것은 bimanual simulation/observation input이며 실제 G1 command authority는 별도의 `hardware/g1_arm_bridge/` 단계에서 관리한다.

## 현재 확인 사항

- 양손 input / bimanual backend: 사용 중
- world-frame Omni alignment: 사용 중
- PiP RobotRoot anchor: 적용됨
- fixed IK tracking rate 1.0: Python backend 기준
- 실제 G1에서 추종 속도 개선: 확인됨
- 큰 absolute wrist target의 workspace mismatch: 남은 문제
- reach clamp / adaptive gain: production 미적용
