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
| MuJoCo → Unity | UDP `127.0.0.1:5006` | 오른팔 상태 feedback |

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
| `command_state` | 예 | `active`, `idle`, `workspace_exit` |
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
| `right_arm.joints` | 오른팔 7개 관절 qpos, radian |
| `right_arm.active` | 현재 command가 활성 상태인지 여부 |
| `right_arm.wrist_delta` | engagement 기준 실제 손목 변위 |
| `right_arm.target_delta` | engagement 기준 목표 변위 |
| `right_arm.position_error` | 목표와 실제 손목 위치 오차, meter |
| `right_arm.workspace_limited` | controller workspace 제한 여부 |
| `right_arm.collision_limited` | 충돌 때문에 step이 제한되었는지 여부 |
| `timestamp` | controller wall-clock time |

현재 state packet에는 schema, sequence, acknowledgement가 없으므로 Unity가 packet ordering이나 command–state 대응을 엄격히 검증하기 어렵다.

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
