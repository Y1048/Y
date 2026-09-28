# G1 Teleop Protocol

이 문서는 현재 기본 bimanual/world-frame 통신 계약을 설명한다.

## 1. 기본 bimanual UDP

```text
transport : UDP loopback
address   : 127.0.0.1
port      : 5020
sender    : Unity G1BimanualSimulationSender
receiver  : g1_bimanual_unity_sim.py
```

같은 UDP peer로 Python feedback이 Unity에 돌아간다.

이 경로는 simulation/observation 전용이며 G1 motor packet이 아니다.

## 2. 현재 input schema

현재 scene:

```text
schema      = g1.bimanual.unity.sim.v4
input_frame = unity_display_world_v1
simulation_only = true
```

필수 상위 필드의 핵심:

- `schema`
- `simulation_only`
- `session`
- `sequence`
- `sender_time_s`
- `engage`
- `return_home`
- `input_frame`
- `base_yaw_rad`
- `left`
- `right`

각 hand:

```text
tracked: bool
position_m: [x,y,z]
quaternion_wxyz: [w,x,y,z]
```

진단용으로 `raw_position_m`, `raw_quaternion_wxyz`, `engage_offset_m` 등이 포함될 수 있다.

## 3. Legacy schema

backend는 test/backward compatibility를 위해 다음도 decode할 수 있다.

```text
schema      = g1.bimanual.unity.sim.v1
input_frame = legacy_relative
```

현재 `useExistingScene` Unity path는 v4 world schema를 사용한다. v1 relative와 v4 world를 한 세션에서 혼용하지 않는다.

## 4. 좌표계

Python의 Unity->MuJoCo position basis:

```text
BASIS = [[ 0, 0, 1],
         [-1, 0, 0],
         [ 0, 1, 0]]
```

`base_yaw_rad`은 Unity +Y yaw와 MuJoCo +Z yaw의 부호 차이를 반영해 sender에서 변환된다.

현재 upper-body 계약은 absolute aligned world wrist pose다.

```text
Quest aligned world wrist
 -> Unity/G1 basis mapping
 -> world wrist target
 -> rotating G1/MuJoCo base
```

## 5. Packet validation

`decode()`는 다음을 fail-closed로 검사한다.

- packet size <= 8192 bytes
- JSON nesting depth <= 8
- duplicate JSON key 거부
- finite numeric values
- session length
- sequence range
- sender timestamp
- schema/frame pair
- 양손 tracked bool
- position length/range
- normalized quaternion
- world frame의 finite base yaw

잘못된 packet을 임의 보정해 정상 input으로 만들지 않는다.

## 6. Freshness / clocks

`sender_time_s`는 Unity sender 내부 sequence/filter ordering에 사용한다.

cross-host wall-clock subtraction으로 freshness를 계산하지 않는다. Python receiver는 local receipt monotonic time을 사용한다.

## 7. Filtering

Python bimanual filter:

```text
position tau = 0.060 s
rotation tau = 0.050 s
```

양손 tracking이 모두 유효하지 않으면 invalid input을 정상 pose update로 승격하지 않는다.

## 8. Feedback

Unity가 받는 bimanual feedback schema:

```text
g1.bimanual.unity.sim.state.v1
```

feedback에는 backend state, joint state, IK target validity, world IK target, operator delta, diagnostics가 포함될 수 있다.

Unity는 feedback source가 loopback peer/port와 일치하는지 확인한다.

## 9. Omni observation

Omni Connect source:

```text
ws://127.0.0.1:32123
```

기본 통합 launcher에서는 `g1_omni_velocity_gateway.py --dry-run --process-hz 60`을 사용한다.

observation tap 사용 시 sample copy는 localhost UDP `55071`로 전달된다. 이 경로는 motor command transport가 아니다.

## 10. Camera

```text
G1 VideoClient on eth0
 -> SSH stdout
 -> PC g1_camera_ssh.py
 -> TCP 127.0.0.1:5011
 -> Unity PiP
```

camera transport는 motor authority와 분리되어 있다.

## 11. Measured-state display

read-only measured/recorded display에서 사용하는 대표 포트:

```text
5009 : G1/read-only state -> MuJoCo display
5010 : measured/recorded state -> Unity display
```

simulation feedback과 measured-state display를 같은 provenance로 취급하지 않는다.

## 12. Deprecated single-arm ports

```text
5005 : legacy Unity -> single-arm Mink command
5006 : legacy Mink -> Unity simulation state
```

이 포트들은 저장소에 남아 있지만 현재 bimanual default protocol이 아니다.

## 13. Motor-output boundary

`5020`, `55071`, `5011`, Omni dry-run은 실제 G1 motor authority를 부여하지 않는다.

물리 출력은 `hardware/g1_arm_bridge/`의 별도 Gate/config/publisher 경로에서만 다룬다.

## 14. 변경 규칙

protocol field/frame/port를 변경할 때는 Unity sender와 Python decoder, feedback, tests를 같은 변경으로 맞춘다.

특히 다음 invariant를 회귀로 유지한다.

- left/right hand symmetry
- world-frame schema와 base yaw 일치
- stale/invalid packet fail-closed
- loopback bimanual path에서 motor output 없음
- Omni yaw 변경 시 body-relative 동작 일관성
