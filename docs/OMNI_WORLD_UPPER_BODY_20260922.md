# Omni World-Frame Upper Body

이 문서는 현재 bimanual upper-body에서 사용하는 Omni/world-frame 계약을 설명한다.

## 현재 기준

Unity Play 시작 후 Quest tracking과 Omni yaw가 안정되면 초기 정렬을 만든다.

그 이후:

- Quest tracking world는 고정된다.
- Unity G1 `RobotRoot`는 Omni 초기-relative yaw를 따른다.
- MuJoCo base도 같은 yaw 변화를 사용한다.
- 양손 IK target은 aligned absolute world wrist pose다.

## 현재 bimanual packet

```text
schema      = g1.bimanual.unity.sim.v4
input_frame = unity_display_world_v1
UDP         = 127.0.0.1:5020
```

양손 위치와 회전은 `G1BimanualSimulationSender`가 보낸다.

`base_yaw_rad`은 Unity/MuJoCo 축 convention 차이에 맞춰 변환된다.

## 손목 위치

현재 bimanual world path는 engage displacement가 아니라 **absolute aligned world wrist position**을 IK target으로 사용한다.

binder 내부에는 relative delta/body-translation helper가 남아 있지만 현재 v4 `position_m` 계약과 동일한 것은 아니다.

## 손목 회전

손 회전은 anatomical wrist frame을 기준으로 sender/backend가 quaternion으로 전달한다.

position과 orientation은 Python bimanual policy의 wrist FrameTask에서 함께 풀린다.

## 통합 시작 시 Omni 방향 보정

기존 PC 보행 매핑의 `120°`는 standalone 호환 기본값으로만 남긴다.

통합 launcher에서는 Unity가 localhost UDP `55074`로 별도 readiness
heartbeat를 보낸다. 이 heartbeat는 다음 조건이 모두 만족된 뒤에만
`aligned=true`가 된다.

- Quest head pose가 유효하고 안정됨
- `G1HeadLockedCamera`의 one-time alignment가 실제 적용됨
- `G1OmniBodyHeading`이 최초 Omni sample과 G1 shoulder frame을 확보함

PC Omni worker는 이 heartbeat가 fresh하지 않으면 `vx/vy/yaw_rate=0`을
유지한다. 새 Unity Play session에서 처음 fresh `aligned=true`를 받은 뒤,
차렷 자세의 **현재 Omni `armYaw`** 를 그 session의 runtime
`yaw_offset_deg`로 캡처하고 그 시점부터 movement bias calibration을
시작한다.

따라서 통합 경로는 더 이상 시작 순간을 무조건 `120°`로 가정하지 않는다.
Quest yaw 값은 readiness/진단에만 사용하고 Omni movement 식에 직접
혼합하지 않는다. `g1_omni_heading_controller.py --yaw-sign -1`의
상대 G1 yaw 방향 계약은 별개이며 변경하지 않는다.

Unity heartbeat가 stale해지면 PC Omni mapping output은 즉시 zero hold한다.
같은 Unity session이 다시 fresh해지면 기존 calibration을 유지하고,
새 Unity session이면 새 `armYaw`로 다시 calibration한다.

## Omni observation

Omni Connect endpoint:

```text
ws://127.0.0.1:32123
```

기본 통합 launcher에서는 `g1_omni_velocity_gateway.py --dry-run --process-hz 60`으로 읽는다.

이 default worker는 observation-only이며 G1 motor command transport를 활성화하지 않는다.

## PiP

카메라 PiP는 HMD가 아니라 G1 `RobotRoot`에 parent된다.

따라서 사용자가 머리를 돌려도 PiP parent가 따라가지 않고 G1/Omni 기준으로 유지된다.

## 현재 확인된 제한

이 world-frame 계약에는 사람 체격을 G1 팔 길이에 자동 retargeting하는 단계가 없다.

최근 실제 세션 분석에서는 상당수 absolute world wrist target이 G1 shoulder 기준 reachable workspace 밖에 있었다.

그 결과 큰 position residual이 speed tuning만으로 사라지지 않는 구간이 있었다.

현재 production에는 다음을 추가하지 않았다.

- adaptive position gain
- permanent reach clamp
- global movement compression
- relative mapping rollback

향후 retargeting을 추가할 경우 다음 invariant를 유지해야 한다.

1. Omni yaw를 바꿔도 body-relative 동작이 일관될 것
2. left/right symmetry
3. world schema/frame provenance 유지
4. motor authority와 observation mapping 분리
5. 기존 80-test bimanual regression 보존

## Legacy와의 차이

예전 single-arm/relative path:

```text
UDP 5005/5006
engage-relative target
right-hand/right-arm 중심
```

현재 default:

```text
UDP 5020
absolute aligned world target
left + right 14-DoF bimanual
```

두 계약을 혼용하지 않는다.
