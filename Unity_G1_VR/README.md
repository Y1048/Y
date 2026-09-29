# Unity G1 VR Frontend

현재 SampleScene은 bilateral path를 사용한다.

## 핵심 component

- `G1BimanualSimulationSender`
- `G1ExistingHandTargetBinder`
- `G1UnityRightArmPreview` — 이름은 과거 명칭이지만 current bimanual preview component
- `G1OfficialRig`
- `G1RobotStateUdpReceiver`
- `G1LowStateLegView`
- `G1OmniBodyHeading`
- `G1HeadLockedCamera`
- `G1HeadCameraPiP`

## Bilateral input

```text
G1BimanualSimulationSender.useExistingScene = true
UDP = 5020
schema = g1.bimanual.unity.sim.v4
input_frame = unity_display_world_v1
```

## Omni / robot root

Quest tracking origin과 robot root는 Omni body heading 기준으로 정렬한다. upper-body world target과 rotating G1 base가 같은 world alignment를 사용한다.

## Camera PiP

카메라 입력은 TCP loopback 5011이다.

현재 기준:

- JPEG native resolution 사용
- G1 source 1920×1080
- 16:9 유지
- 320×180 PiP
- parent = G1 RobotRoot

## Display source

bimanual mode에서는 5020 feedback joint state를 G1 preview에 적용한다. read-only measured LowState는 별도 source로 유지한다.

## Compatibility wiring

SampleScene에는 기존 5005/5006 component reference 일부가 남아 있다. current bimanual sender는 5005 sender를 Awake에서 비활성화한다. 새 기능은 5020 path를 기준으로 구현한다.

## Validation

`Assets/Editor/G1TeleopBatchValidator.cs`가 current scene/component contract를 검사한다. Remote Commander로 Unity batchmode를 띄울 때 Package Manager IPC가 실패할 수 있으므로 일반 Unity Editor compile/Play 확인이 최종 기준이다.
