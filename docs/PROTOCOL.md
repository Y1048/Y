# Teleoperation UDP Protocol

## 1. 문서 상태

이 문서는 현재 동작 중인 Unity–MuJoCo UDP packet과 `backend/g1_teleop/protocol.py`에 정의된 versioned contract의 차이를 기록한다.

현재 상태는 다음과 같다.

- **Live command path:** legacy packet을 사용한다.
- **Live state feedback:** 별도의 legacy state packet을 사용한다.
- **Python foundation:** `PosePacketV1`, `StatePacketV1`이 구현되어 있지만 live path와 완전히 연결되지는 않았다.
- **Migration requirement:** session ownership과 workspace-exit 의미를 보존하면서 단계적으로 통합해야 한다.

따라서 이 문서에서 **Current**는 실제 실행 경로를, **Target**은 향후 통합 계약을 뜻한다.

---

## 2. Transport

| 방향 | 현재 주소 | 용도 |
| --- | --- | --- |
| Unity → MuJoCo | UDP `:5005` | 오른손 목표 command |
| MuJoCo → Unity | UDP `127.0.0.1:5006` | `mink_simulation` 29관절 pose와 오른팔 제어/안전 feedback |
| MuJoCo → Gate 7 | UDP `127.0.0.1:5008` | 순번·원본 해제 원인이 포함된 잠긴 Arm SDK 후보 입력 |
| LowState viewer → Unity | UDP `127.0.0.1:5010` | `g1_lowstate_read_only` 실제/저장 29관절 표시 상태 |
| Gate 7 → MuJoCo | UDP `127.0.0.1:5012` | HOLD와 Regular 복귀 후보를 시뮬레이션에만 반영 |

UDP 5006은 `G1ExistingTargetUdpSender`가 참조하는 제어 피드백이다. UDP 5010은
`G1UnityRightArmPreview`만 사용하는 전신 표시 입력이며 안전 판정이나 command
생성에는 사용하지 않는다.

현재 MuJoCo command socket은 `0.0.0.0:5005`에 bind한다. 같은 PC에서만 사용할 때는 local bind 또는 firewall 제한을 권장한다.

UDP 특성상 다음을 보장하지 않는다.

- 전달 성공
- 순서 유지
- 중복 방지
- 송신자 인증
- 암호화

따라서 sequence, session, timeout, validation은 application layer에서 처리해야 한다.

현재 receiver buffer는 `4096 bytes`이므로 command packet은 이 크기보다 작게 유지해야 한다.

---

## 3. 공통 표현 규칙

### 숫자와 단위

| 데이터 | 형식 | 단위 |
| --- | --- | --- |
| 위치 | JSON number 배열 길이 3 | meter |
| quaternion | JSON number 배열 길이 4 | unit quaternion |
| 관절각 | JSON number 배열 | radian |
| sequence | 0 이상의 integer | packet counter |
| source time | integer 또는 number | 계약별 정의 |

### Quaternion

모든 quaternion 배열 순서는 다음과 같다.

```text
[x, y, z, w]
```

수신 측은 다음을 검사해야 한다.

- 배열 길이 4
- 모든 값이 finite
- norm이 0에 가깝지 않음
- 사용 전 normalize

### 좌표계

현재 operator 입력 축은 다음과 같다.

```text
Unity operator frame: +X right, +Y up, +Z forward
```

MuJoCo G1 축은 다음과 같다.

```text
G1 frame: +X forward, +Y left, +Z up
```

현재 위치 변환은 다음과 같다.

```text
robot = [operator.z, -operator.x, operator.y]
```

향후 packet에는 반드시 `frame_id`를 포함해 송신 데이터가 어느 좌표계인지 명확히 해야 한다.

---

## 4. Current command packet — Legacy V0

현재 Unity의 `G1ExistingTargetUdpSender`가 송신하고 MuJoCo의 `receive_target()`이 수신하는 형식이다.

### 예시

```json
{
  "session_id": "2f7b8b6df2c34ff3be20bbad9a233a3d",
  "sequence": 1542,
  "command_state": "active",
  "right": {
    "pos": [0.42125, -0.16310, 1.04820],
    "rot": [0.01230, -0.02110, 0.10520, 0.99400],
    "valid": true
  },
  "timestamp": 128.425136,
  "source": "quest3s_head_relative"
}
```

### 필드

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `session_id` | 예 | Unity sender가 시작될 때 생성하는 UUID 문자열 |
| `sequence` | 예 | session 내부에서 증가하는 packet 번호 |
| `command_state` | 예 | `active`, `idle`, `workspace_exit`, `pinch_disengaged`, `tracking_disengaged` |
| `right.pos` | active일 때 예 | 현재 오른손 목표 위치 |
| `right.rot` | active일 때 예 | 현재 오른손 목표 quaternion XYZW |
| `right.valid` | 예 | command를 새 목표로 적용할 수 있는지 여부 |
| `timestamp` | 아니오 | Unity `realtimeSinceStartup` 기반 시간 |
| `source` | 아니오 | 송신 경로 설명 문자열 |

### 상태 조합 규칙

| `command_state` | `right.valid` | 의미 |
| --- | ---: | --- |
| `active` | `true` | 새 목표를 받아 제어 활성화 |
| `idle` | `false` | 마지막 안전 목표 유지 |
| `workspace_exit` | `false` | workspace fault 처리 및 재정렬 요구 |
| `pinch_disengaged` | `false` | 사용자가 엄지-검지 pinch로 의도적으로 연동 해제 |
| `tracking_disengaged` | `false` | Quest가 손 추적을 잃어 연동 해제 |

그 외 조합은 수신 측에서 거부한다.

### Session/sequence 규칙

현재 `SessionSequenceWatchdog`가 다음을 담당한다.

1. 빈 session ID 거부
2. boolean을 integer sequence로 잘못 사용하는 경우 거부
3. 동일·과거 sequence 거부
4. 현재 active session이 있는 동안 다른 session 거부
5. 현재 session이 stale 상태가 된 뒤 새 session takeover 허용
6. 현재 session의 정상 disengage packet 허용

이 기능은 여러 Unity instance 또는 재실행된 sender가 동시에 command를 보내는 상황을 방지한다.

---

## 5. Current state packet — Legacy V0

현재 MuJoCo controller가 Unity의 `127.0.0.1:5006`으로 보내는 형식이다.

### 예시

```json
{
  "state_source": "mink_simulation",
  "all_joint_names": [
    "left_hip_pitch", "left_hip_roll", "left_hip_yaw",
    "left_knee", "left_ankle_pitch", "left_ankle_roll",
    "right_hip_pitch", "right_hip_roll", "right_hip_yaw",
    "right_knee", "right_ankle_pitch", "right_ankle_roll",
    "waist_yaw", "waist_roll", "waist_pitch",
    "left_shoulder_pitch", "left_shoulder_roll", "left_shoulder_yaw",
    "left_elbow", "left_wrist_roll", "left_wrist_pitch", "left_wrist_yaw",
    "right_shoulder_pitch", "right_shoulder_roll", "right_shoulder_yaw",
    "right_elbow", "right_wrist_roll", "right_wrist_pitch", "right_wrist_yaw"
  ],
  "all_joint_q_rad": [
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0,
    0.17, 0.38, 0.01, 0.96, 0.02, 0.01, 0.03,
    0.17, -0.38, 0.01, 0.96, 0.02, -0.01, 0.03
  ],
  "right_arm": {
    "joints": [0.17, -0.38, 0.01, 0.96, 0.02, -0.01, 0.03],
    "active": true,
    "wrist_delta": [0.03, -0.02, 0.01],
    "target_delta": [0.04, -0.02, 0.01],
    "position_error": 0.012,
    "workspace_limited": false,
    "collision_limited": false
  },
  "timestamp": 1787212345.25
}
```

### 필드

| 필드 | 의미 |
| --- | --- |
| `state_source` | `mink_simulation`; Unity가 수신 출처를 구분하는 문자열 |
| `all_joint_names` | Unitree motor index 0~28 순서의 G1 관절 이름 29개 |
| `all_joint_q_rad` | 같은 순서의 다리·허리·양팔 관절 위치, radian |
| `right_arm.joints` | 오른팔 7개 관절 qpos, radian |
| `right_arm.active` | 현재 command가 활성 상태인지 여부 |
| `right_arm.wrist_delta` | engagement 기준 실제 손목 변위 |
| `right_arm.target_delta` | engagement 기준 목표 변위 |
| `right_arm.position_error` | 목표와 실제 손목 위치 오차, meter |
| `right_arm.workspace_limited` | controller workspace 제한 여부 |
| `right_arm.collision_limited` | 충돌 때문에 step이 제한되었는지 여부 |
| `timestamp` | controller wall-clock time |

기존 `right_arm` 필드는 하위 호환과 오른팔 제어 진단을 위해 유지한다. Unity는
29개 이름의 개수와 정확한 순서를 확인한 뒤 전신 프리뷰에 적용하고, 구형 패킷은
오른팔 7축만 표시한다. 현재 state packet에는 schema, sequence,
acknowledgement가 없으므로 Unity가 packet ordering이나 command–state 대응을
엄격히 검증하기 어렵다.

### 5.1 Read-only G1 display packet

UDP 5010은 위 상태 구조를 재사용하지만 다음 계약을 반드시 만족한다.

```json
{
  "state_source": "g1_lowstate_read_only",
  "session_id": "bridge-session-id",
  "sequence": 1234,
  "all_joint_names": ["canonical Unitree motor index 0..28 order"],
  "all_joint_q_rad": ["29 finite joint positions in radians"],
  "all_joint_dq_rad_s": ["29 finite joint velocities in radians/second"],
  "base_state": {
    "valid": true,
    "topic": "rt/odommodestate",
    "received_packets": 1234,
    "last_packet_age_s": 0.002,
    "position_m": [0.12, -0.03, 0.0],
    "quaternion_xyzw": [0.0, 0.0, 0.05, 0.9987],
    "velocity_mps": [0.10, 0.0, 0.0],
    "yaw_speed_rad_s": 0.04
  },
  "mirror_diagnostics": {
    "source_base_position_m": [0.125, -0.031, 0.0],
    "source_base_quaternion_xyzw": [0.0, 0.0, 0.052, 0.9986],
    "displayed_base_position_m": [0.12, -0.03, 0.0],
    "displayed_base_quaternion_xyzw": [0.0, 0.0, 0.05, 0.9987],
    "base_position_error_m": 0.0051,
    "base_orientation_error_deg": 0.23,
    "max_joint_position_error_rad": 0.004
  },
  "right_arm": {
    "joints": ["indices 22..28"],
    "active": false,
    "workspace_limited": false,
    "collision_limited": false
  },
  "timestamp": 1787212345.25
}
```

`all_joint_names`, `all_joint_q_rad`, `all_joint_dq_rad_s`는 모두 필수이며 정확히
29개여야 한다. 관절 이름은 canonical 순서와 완전히 일치해야 한다. Unity의
5010 수신기는 출처가 없거나 `g1_lowstate_read_only`가 아닌 패킷을 거부한다.
상태가 0.5초 이상 stale이면 5010 상태 적용을 중단한다. 이때 신선한 UDP 5006
Mink 상태가 있으면 프리뷰가 그 상태로 돌아가고, 두 출처 모두 없으면 마지막
표시 자세를 유지한다. 이 packet은 관찰용이며 로봇 명령 권한을 부여하지 않는다.

라이브 MuJoCo 미러가 5010을 보낼 때 `all_joint_q_rad`와 `base_state`는 5009의
원본 목표가 아니라 **그 프레임에 MuJoCo가 실제 표시한 보간 자세**다. 따라서
Unity와 MuJoCo는 동일한 29관절/base 표시값을 사용한다. `mirror_diagnostics`는
5009 원본과 표시 자세를 함께 보존하고 위치·회전·관절 보간 오차를 제공한다.
Unity는 수신한 표시 자세와 실제 G1 root transform의 오차도 별도로 계산한다.
저장 재생이나 구형 송신기처럼 이 필드가 없는 패킷도 계속 허용한다.

`base_state`는 실기 read-only 경로의 선택 필드다. `rt/odommodestate`의 첫 유효
sample을 위치 원점과 회전 identity로 정규화하므로 실행 시 G1의 절대 odometry
값이 Unity/MuJoCo 모델을 멀리 이동시키지 않는다. 위치/속도는 첫 yaw 기준 G1
좌표계(+X forward, +Y left, +Z up), quaternion은 XYZW이다. `valid=false`이거나
base packet이 250 ms 이상 stale이면 관절 상태는 계속 표시하되 마지막 base
pose를 유지한다. 저장 상태 등 기존 packet에 `base_state`가 없어도 고정 base로
재생해 하위 호환한다.

### 5.2 Read-only WSL telemetry packet

UDP 5007/5009의 source packet은 기존 schema 이름
`g1.lowstate.right_arm.v1`을 호환 목적으로 유지한다. `mode`는
`READ_ONLY_LOWSTATE`, `topic`은 `rt/lowstate`이며
`publisher_present=false`, `command_output_enabled=false`가 아니면 수신기가
거부한다. 오른팔 7축 필드와 canonical 29관절 필드에 위 `base_state`를 선택적으로
추가한다. base 내부 `topic`은 반드시 `rt/odommodestate`여야 하고 quaternion
norm 오차는 0.001 이하여야 한다. base field가 잘못되면 packet 전체를 거부하지만,
field가 아예 없는 기존 저장 packet은 허용한다.

### 5.3 Mink → Gate 7 locked packet

UDP 5008은 5006과 같은 계산 자세를 사용하지만, 향후 하드웨어 어댑터가 원본
입력 원인을 잃지 않도록 다음 필드를 추가한 strict schema를 사용한다.

```text
schema                  = g1.mink.right_arm.state.v1
sequence                = 송신 상태 packet 순번
input_command_mode      = Unity가 보낸 원본 command_state
right_arm.command_state = Mink가 계산한 active/hold/idle/workspace_fault
right_arm.minimum_clearance_m = 현재 충돌 pair 최소 거리
```

2026-09-03부터 `right_arm`에 선택적 진단 필드가 추가된다. 기존 수신기는
이 필드 없이도 동작하며, 실제 모터 명령의 허가나 제한을 바꾸지 않는다.

- `target_rotation_matrix_robot`: 로봇 모델 기준, 목표 yaw 손목 프레임의 3x3 회전행렬.
- `wrist_rotation_matrix_robot`: 같은 기준의 계산된 실제 yaw 손목 회전행렬.
- `orientation_solver_policy`: `exact_jacobian_weighted_posture_v1`.

행렬은 행별 중첩 배열이며 센서 원본이나 실제 G1 실측이 아니라 Mink 목표/계산값이다.
캡처 프록시는 원본 UDP payload를 보존하므로 회전 오차의 크기뿐 아니라 목표 방향도
다음 기록부터 복원할 수 있다. 예전 캡처에 없던 회전값을 추정해서 채워 넣지는 않는다.
`orientation_assist_gain`은 손목 제한 접근의 호환용 표시값이며, 더 이상
어깨/팔꿈치 Jacobian 열을 곱하는 계수가 아니다.

`input_command_mode`와 `right_arm.command_state`는 의미가 다르다. 예를 들어
`pinch_disengaged`와 `tracking_disengaged`는 Mink 내부에서는 모두 `idle`로 보일
수 있으므로, Gate 7은 반드시 원본 `input_command_mode`를 사용해 두 상황을
구분한다.

현재 잠긴 Gate 7 정책은 다음과 같다.

| 입력 원인 | 후보 동작 |
| --- | --- |
| `active` | 오른팔 Mink 관절 목표를 속도 제한해 추종 |
| active 이후 `pinch_disengaged` | 저장된 Regular 양팔 자세로 충돌 검증된 minimum-jerk 복귀 |
| `tracking_disengaged`, stale/누락 packet | 측정된 현재 양팔 자세를 최대 10초 HOLD |
| `workspace_exit`, 실제 최소 충돌 여유 12 mm 미만 | 측정된 현재 양팔 자세를 최대 10초 HOLD |
| 의도치 않은 해제가 10초 지속 | 저장된 Regular 양팔 자세로 동일한 검증 복귀 |
| 10초 안에 정상 `active` 복구 | HOLD 타이머 취소 후 추종 재개 |

이 packet과 정책은 오프라인 후보 계약이다. 현재 repository 설정은
`hardware_output_authorized=false`이며 UDP 5008 수신 결과를 실제
`rt/arm_sdk` publisher로 전달하지 않는다.

`gate7_live_dry_run.py`는 이 packet을 실시간으로 수신해 35-slot Arm SDK 후보와
검증 이유를 JSONL로 남긴다. 기본 측정 source는 Mink shadow state이며, 선택적으로
UDP 5007의 strict 29-joint LowState를 사용할 수 있다. 두 경우 모두 DDS entity와
publisher는 존재하지 않는다.

### 5.4 Gate 7 → MuJoCo simulation feedback

UDP `127.0.0.1:5012`는 Gate 7의 후보 관절값을 기존 MuJoCo 창에만 되돌린다.
실제 SDK/DDS 출력과 구분하기 위해 다음 필드를 강제한다.

```text
schema                       = g1.gate7.simulation_feedback.v1
stream_id                    = Gate 7 프로세스별 고유 ID
sequence                     = stream 내부 증가 순번
dual_arm_joint_indices       = 정확히 15..28
dual_arm_q_rad               = 양팔 14개 후보 관절값
simulation_only              = true
hardware_output_authorized   = false
```

MuJoCo는 localhost에서 온 유효한 최신 packet 중 `REGULAR_RETURN`과
`REGULAR_HOLD`만 적용한다. Unity command가 active이거나 packet age가 250 ms를
넘으면 적용하지 않는다. 나머지 15개 관절은 변경하지 않는다.

---

## 6. Existing Python contract — PosePacketV1

`backend/g1_teleop/protocol.py`에는 다음 schema가 정의되어 있다.

```text
g1.teleop.pose.v1
```

### 예시

```json
{
  "schema": "g1.teleop.pose.v1",
  "sequence": 1542,
  "source_time_ns": 128425136000,
  "frame_id": "unity_ovr_tracking",
  "armed": true,
  "clutch": true,
  "calibration_request": 0,
  "head": {
    "valid": true,
    "confidence": "high",
    "position_m": [0.0, 1.65, 0.0],
    "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]
  },
  "right_wrist": {
    "valid": true,
    "confidence": "high",
    "position_m": [0.31, 1.22, 0.42],
    "quaternion_xyzw": [0.01, -0.02, 0.10, 0.99]
  },
  "left_wrist": {
    "valid": false,
    "confidence": "unknown",
    "position_m": [0.0, 0.0, 0.0],
    "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]
  }
}
```

### V1의 장점

- `schema`로 계약 버전을 구분
- `frame_id`로 좌표계 명시
- head/right/left pose 형식 통일
- confidence 표현
- strict boolean validation
- finite vector와 quaternion validation
- source nanosecond timestamp
- calibration request counter

### Live path와의 차이

| 기능 | Legacy V0 | PosePacketV1 |
| --- | --- | --- |
| schema | 없음 | 있음 |
| frame ID | source 문자열만 있음 | `frame_id` 있음 |
| session ID | 있음 | 없음 |
| command state | `active/idle/workspace_exit` | 직접 대응 필드 없음 |
| head pose | 없음 | 있음 |
| left wrist | 없음 | 있음 |
| confidence | 없음 | 있음 |
| calibration request | 없음 | 있음 |

**중요:** 현재 session watchdog은 `session_id`에 의존한다. 따라서 V1 parser를 live path에 바로 연결하면 multi-sender ownership이 약해질 수 있다.

---

## 7. Existing Python contract — StatePacketV1

정의된 schema:

```text
g1.teleop.state.v1
```

### 예시

```json
{
  "schema": "g1.teleop.state.v1",
  "sequence": 931,
  "robot_time_ns": 1787212345250000000,
  "acknowledged_source_sequence": 1542,
  "mode": "active",
  "armed": true,
  "watchdog": "ok",
  "ik_status": "tracking",
  "calibration_status": "ready",
  "right_arm_q_rad": [0.17, -0.38, 0.01, 0.96, 0.02, -0.01, 0.03],
  "left_arm_q_rad": [0.17, 0.38, 0.01, 0.96, 0.02, -0.01, 0.03]
}
```

V1은 sequence와 source acknowledgement를 제공한다. 그러나 current feedback의 `position_error`, `workspace_limited`, `collision_limited`, wrist/target delta는 포함하지 않는다.

따라서 state 통합 시 V1에 필요한 diagnostic을 추가하거나 새 version을 정의해야 한다.

---

## 8. Target contract 권장안

현재 V0와 V1의 필수 기능을 합치려면 기존 V1을 의미 변경 없이 덮어쓰기보다 새 schema를 정의하는 편이 안전하다.

권장 schema 이름:

```text
g1.teleop.pose.v2
g1.teleop.state.v2
```

### Pose V2 권장 필드

```json
{
  "schema": "g1.teleop.pose.v2",
  "session_id": "2f7b8b6df2c34ff3be20bbad9a233a3d",
  "sequence": 1542,
  "source_time_ns": 128425136000,
  "frame_id": "unity_ovr_tracking",
  "mode": "active",
  "armed": true,
  "clutch": true,
  "calibration_request": 0,
  "head": {
    "valid": true,
    "confidence": "high",
    "position_m": [0.0, 1.65, 0.0],
    "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]
  },
  "right_wrist": {
    "valid": true,
    "confidence": "high",
    "position_m": [0.31, 1.22, 0.42],
    "quaternion_xyzw": [0.01, -0.02, 0.10, 0.99]
  },
  "left_wrist": {
    "valid": false,
    "confidence": "unknown",
    "position_m": [0.0, 0.0, 0.0],
    "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]
  }
}
```

권장 `mode` 값:

| 값 | 의미 |
| --- | --- |
| `idle` | 아직 engagement되지 않음 |
| `active` | 새 target 적용 요청 |
| `hold` | 추적 유실 등으로 마지막 안전 target 유지 요청 |
| `workspace_exit` | 사용자 측 workspace exit 감지, 재정렬 요구 |
| `shutdown` | 정상 송신 종료 알림. 최종 safety 결정은 receiver가 수행 |

`mode`와 `valid` 의미를 중복시키지 않는 것이 좋다. 권장 방식은 pose별 `valid`는 tracking quality를 나타내고, top-level `mode`는 control intent를 나타내는 것이다.

### State V2 권장 필드

```json
{
  "schema": "g1.teleop.state.v2",
  "sequence": 931,
  "robot_time_ns": 1787212345250000000,
  "active_session_id": "2f7b8b6df2c34ff3be20bbad9a233a3d",
  "acknowledged_source_sequence": 1542,
  "mode": "active",
  "armed": true,
  "watchdog": "ok",
  "ik_status": "tracking",
  "calibration_status": "ready",
  "workspace_status": "inside",
  "collision_limited": false,
  "position_error_m": 0.012,
  "right_arm_q_rad": [0.17, -0.38, 0.01, 0.96, 0.02, -0.01, 0.03],
  "left_arm_q_rad": [0.17, 0.38, 0.01, 0.96, 0.02, -0.01, 0.03]
}
```

상태 문자열은 자유 텍스트보다 enum 집합을 문서화하고 검증하는 것이 좋다.

---

## 9. Validation 규칙

수신기는 packet을 적용하기 전에 다음을 모두 검사해야 한다.

### Envelope

- UTF-8 JSON object
- 지원하는 `schema`
- session ID 형식과 길이
- non-negative integer sequence
- non-negative timestamp
- 알려진 `mode`
- 알려진 `frame_id`

### Pose

- object 존재
- `valid`는 실제 JSON boolean
- confidence enum
- position 길이 3, finite
- quaternion 길이 4, finite, normalize 가능

### Ordering/session

- 같은 session의 sequence는 단조 증가
- duplicate/older packet 거부
- active session 소유권 유지
- stale timeout 이후에만 다른 session takeover
- receiver 도착 시간은 wall-clock이 아니라 monotonic clock 사용

### Safety

packet validation을 통과해도 바로 로봇에 적용하지 않는다.

```text
protocol validation
→ session/timeout validation
→ coordinate conversion
→ clutch mapping
→ workspace/rate limit
→ IK/joint/collision validation
→ accepted robot state
```

---

## 10. 호환 마이그레이션 순서

### Step 1 — Legacy parser 분리

현재 `receive_target()` 내부의 JSON parsing을 독립 모듈로 이동한다.

```text
transport/legacy_v0.py
```

출력은 packet 형식과 무관한 내부 command model로 변환한다.

### Step 2 — Internal command model 도입

예시:

```python
@dataclass(frozen=True)
class TeleopCommand:
    session_id: str
    sequence: int
    source_time_ns: int | None
    mode: str
    frame_id: str
    right_wrist_pose: np.ndarray | None
    right_tracking_valid: bool
```

V0와 V2 parser가 모두 동일한 model을 반환하도록 한다.

### Step 3 — Backend dual-read

backend가 일정 기간 다음 두 형식을 모두 수신한다.

- legacy V0
- pose V2

로그에는 수신 schema와 deprecation warning을 기록한다.

### Step 4 — Unity V2 송신

Unity sender를 구조화된 serializable DTO로 교체한다. 현재처럼 `string.Format`으로 JSON을 직접 조립하지 않고 다음 중 하나를 사용한다.

- Unity `JsonUtility`에 맞춘 serializable class
- 명시적 JSON writer
- 검증된 JSON package

locale에 따라 decimal separator가 달라지는 문제와 escaping 오류를 방지해야 한다.

### Step 5 — State V2 적용

controller는 `acknowledged_source_sequence`와 `active_session_id`를 포함해 Unity가 stale feedback을 구분하도록 한다.

### Step 6 — Legacy 제거

다음 조건을 모두 만족한 뒤 V0 parser를 제거한다.

- Unity V2 sender 통합 테스트 완료
- fake sender V2 전환 완료
- state receiver V2 전환 완료
- session takeover 테스트 통과
- workspace exit/re-engagement no-jump 테스트 통과

---

## 11. 필수 회귀 테스트

```text
test_invalid_utf8_is_rejected
test_unknown_schema_is_rejected
test_non_finite_position_is_rejected
test_zero_norm_quaternion_is_rejected
test_boolean_sequence_is_rejected
test_duplicate_sequence_is_rejected
test_foreign_session_is_rejected_until_stale
test_current_session_can_disengage
test_hold_keeps_last_safe_target
test_workspace_exit_requires_continuous_violation
test_reengagement_preserves_robot_pose
test_state_ack_matches_applied_command
```

Protocol 변경은 단순 serialization 변경이 아니라 safety state machine 변경으로 취급해야 한다.

---

## 12. 네트워크 안전 주의사항

현재 packet에는 인증이나 암호화가 없다. 따라서 다음 원칙을 따른다.

- 인터넷에 UDP 5005/5006을 직접 노출하지 않는다.
- 같은 PC 실행이면 loopback bind를 사용한다.
- 여러 장비 연결이면 전용 신뢰 네트워크 또는 VPN을 사용한다.
- 실물 G1 적용 전 sender allowlist, message authentication 또는 안전 gateway를 검토한다.
- 어떤 packet도 joint command로 직접 변환하지 않고 controller의 workspace/joint/collision 검증을 거친다.

## 13. Feasible Target Feedback (2026-09-03)

The active virtual-center controller adds these optional fields inside
`right_arm` of the existing `g1.mink.right_arm.state.v1` packet:

```json
{
  "feasible_target_position": [0.30, -0.20, 1.00],
  "feasible_target_delta": [0.01, 0.00, 0.00],
  "feasible_target_valid": true,
  "feasible_target_status": "following",
  "feasible_target_policy": "checked_local_lookahead_v1"
}
```

- Position is the robot-model-frame wrist-yaw origin, in meters. Delta is
  relative to the same fixed engage wrist position as `target_delta`.
- Existing `target_position`, `target_delta`, and `target_rotation_matrix_robot`
  remain the raw mapped operator goal. Existing position/orientation errors
  remain raw-goal-to-actual errors; feasible projection never hides them.
- The feasible point is FK of a locally validated look-ahead configuration,
  not a clipped sphere/box and not a certificate that the raw goal is reachable.
  The simulation executes only the first accepted joint step of that path.
- `following` means accepted progress; `local_limit` means no further local
  improving step was found; `settled` means the local pose objective is tiny.
  `invalid_start` / `invalid_goal` have `valid=false`. `invalid_velocity` holds
  the unchanged valid current pose. `inactive` has `valid=false`.
- Unity uses the optional feasible delta only for its green marker, with a
  fresh active response, matching sender session and a post-calibration state
  revision. Missing/invalid/stale feedback hides the active green marker; it
  must not be replaced by the unvalidated raw hand goal.
- White/yellow engage feedback, cyan tracked wrist, magenta displayed robot
  wrist and the white hand-to-robot discrepancy line keep their roles. The
  straight white line is NOT a collision-free Cartesian trajectory.
- Three IK steps are planned at 1/60 s; one is executed. Intermediate joint
  path samples are checked against model geometry. This is not continuous
  collision detection, force control, physical dynamics, or robot permission.
