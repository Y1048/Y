# G1 VR·Mink·Omni 통신 아키텍처

작성일: 2026-09-16

## 전체 연결

```text
Quest
  │ 손목 위치·회전
  ▼
Unity
  │ UDP 5005 / JSON
  ▼
Mink IK
  │ 오른팔 관절 목표 22~28
  │ UDP 5008 / JSON
  ▼
Arm Relay
  │ UDP 5014 / JSON
  │
  ├───────────────────────────────┐
  │                               ▼
  │                      G1 전신 제어기
  │                      ├─ 하체 정책 출력
  │                      ├─ 오른팔 관절 목표
  │                      └─ 단일 LowCmd 송신
  │                               ▲
  │                               │
Omni One                          │
  │ Bluetooth                     │
  ▼                               │
Omni Connect                      │
  │ WebSocket 32123 / JSON         │
  ▼                               │
Omni Gateway                      │
  ├─ 시작 yaw 원점 설정           │
  ├─ vx·vy 영점/축/크기 보정      │
  ├─ 패킷 검증                    │
  ├─ UDP 5018에서 G1 자동 발견    │
  │ UDP 5017 / JSON               │
  └───────────────────────────────┘

G1 카메라
  │ TCP 5011 / JPEG
  ▼
Unity 화면
```

## 통신 목록

| 구간 | 프로토콜 | 기본 주소·포트 | 전달 데이터 | 상태 |
|---|---|---|---|---|
| Quest → Unity | Unity XR | Unity 내부 | 손목 위치·회전, engage/pinch | 사용 중 |
| Unity → Mink | UDP JSON | PC `127.0.0.1:5005` | 손목 위치와 quaternion | 사용 중 |
| Mink → Arm Relay | UDP JSON | PC `127.0.0.1:5008` | 오른팔 관절 22~28 목표와 상태 | 사용 중 |
| Arm Relay → G1 | UDP JSON | `${G1_HOST}:5014` | 검증된 오른팔 관절 목표 | 후보 구현 |
| G1 → PC | UDP JSON | G1 `5014` 응답 → relay → PC `127.0.0.1:5015` | 초기화·ready·tracking·return 상태 | 후보 구현 |
| Omni One → Omni Connect | Bluetooth | PC 로컬 연결 | Omni 이동·방향 입력 | 사용 중 |
| Omni Connect → Omni Gateway | WebSocket JSON | PC `127.0.0.1:32123` | `movementXY`, `armYaw` | 수신 확인 |
| G1 → Omni Gateway | UDP broadcast JSON | PC `0.0.0.0:5018` | G1 식별자와 velocity 수신 포트 | 구현됨, 미배포 |
| Omni Gateway → G1 | UDP JSON | 자동 발견된 G1의 `5017` | 보정된 `vx`, `vy`, `yaw_rate` | Gateway 구현됨, 실제 G1 미검증 |
| G1 카메라 → Unity | TCP JPEG | PC `5011` | 전면 카메라 영상 | 사용 중 |

## 전달 데이터 형식

| 구간 | 데이터 형식 | 좌표·단위 및 배열 순서 |
|---|---|---|
| Quest → Unity | Unity XR 객체: 손목 `Vector3`, `Quaternion`, 손 추적 `bool`, index pinch `bool` | Unity 좌표계 `+X=오른쪽`, `+Y=위`, `+Z=앞`; 위치 m; quaternion은 Unity 필드 순서 `x,y,z,w` |
| Unity → Mink | UTF-8 JSON 객체 | `right.pos=[x,y,z]`는 G1/MuJoCo 목표 위치 m, `right.rot=[x,y,z,w]`는 정규화 quaternion, `right.valid`는 추적·engage 유효 여부 |
| Mink → Arm Relay | UTF-8 JSON 객체 `g1.mink.cycle.live.v1` | `joints`는 오른팔 22~28번의 절대 목표각 7개, 단위 rad; `clearance_m`는 최소 충돌 여유 m |
| Arm Relay → G1 | 위 Mink JSON에 `relay_token` 문자열을 추가 | 관절 배열과 단위는 변경하지 않음. relay가 schema·session·sequence·freshness를 검증한 뒤 G1 `5014`로 전달 |
| G1 → PC | UTF-8 JSON 객체 `g1.mink.cycle.ack.v1` | 로봇 cycle 상태 문자열과 해당 session/epoch/sequence. relay가 받은 ACK를 PC loopback `5015`로 전달 |
| Omni Connect → Omni Gateway | WebSocket text JSON | `movementXY=[mx,my]`: 월드 이동 벡터, 현재 계약상 yaw 0에서 `mx=전진`, `my=왼쪽`; `armYaw`: degree |
| G1 → Omni Gateway | UDP JSON 객체 `g1.velocity.discovery.v1` | G1 식별자, `velocity_port` 정수, 증가 sequence, 실행별 token. UDP datagram의 실제 송신 IP를 G1 주소로 사용 |
| Omni Gateway → G1 | UDP JSON 객체 `g1.velocity.command.v1` | `velocity=[vx,vy,yaw_rate]`; `vx,vy` m/s, `yaw_rate` rad/s |
| G1 카메라 → Unity | TCP binary: 24-byte big-endian header 뒤 JPEG 원본 bytes | header=`magic(4) + version(u32) + sequence(u32) + timestamp_ns(u64) + jpeg_size(u32)`; magic=`G1CM`, version=`1` |

아래 JSON은 공백과 줄바꿈을 넣은 설명용 예다. 실제 UDP 송신은 같은 필드를
compact JSON으로 직렬화한다. JSON 숫자는 finite number만 허용하고 quaternion은
정규화된 값을 사용한다.

### Quest → Unity

네트워크 패킷이 아니라 Unity XR 런타임 내부 값이다.

```text
wrist_position : Vector3(float x, float y, float z)  // m
wrist_rotation : Quaternion(float x, float y, float z, float w)
tracked        : bool
index_pinching : bool
```

### Unity → Mink: UDP 5005

별도 `schema` 필드가 없는 현재 Unity 입력 계약이다.

```json
{
  "session_id": "0123456789abcdef0123456789abcdef",
  "sequence": 42,
  "command_state": "active",
  "right": {
    "pos": [0.42, -0.16, 1.05],
    "rot": [0.0, 0.0, 0.0, 1.0],
    "valid": true
  },
  "timestamp": 1234.567890,
  "source": "quest3s_head_relative"
}
```

- `session_id`: Unity Play마다 새로 만드는 문자열 ID.
- `sequence`: 같은 session에서 0부터 증가하는 정수.
- `command_state`: `active`, `idle`, `workspace_exit`,
  `pinch_disengaged`, `tracking_disengaged` 중 하나.
- `timestamp`: Unity `realtimeSinceStartup` 기반 초. 다른 장치의 시계와 직접
  비교하는 Unix timestamp가 아니다.
- `right.pos`: Unity 손목 절대 위치가 아니라 engage 기준 상대 이동을 G1 좌표로
  변환한 손목 task 목표다.

### Mink → Arm Relay: UDP 5008

Mink 내부 상태 `g1.mink.right_arm.state.v1`에서 실제 cycle relay가 필요한 필드만
추출해 다음 형식으로 보낸다.

```json
{
  "schema": "g1.mink.cycle.live.v1",
  "command_provenance": "live_mink",
  "profile": "today",
  "session": "0123456789abcdef0123456789abcdef",
  "sequence": 1001,
  "epoch": 0,
  "sample_time_s": 16.683333,
  "source_age_s": 0.012,
  "event": "active",
  "joints": [0.30, -0.20, 0.10, 1.00, -0.10, 0.00, 0.00],
  "clearance_m": 0.031
}
```

- `joints[0..6]`: `right_shoulder_pitch`, `right_shoulder_roll`,
  `right_shoulder_yaw`, `right_elbow`, `right_wrist_roll`,
  `right_wrist_pitch`, `right_wrist_yaw`; 모두 rad.
- `event`: `idle`, `active`, `pinch`, `tracking_disengaged`, `return`,
  `fault` 중 하나. `fault`의 최종 G1 처리 의미는 아직 통일되지 않았다.
- `source_age_s`: Unity 원본 입력의 경과 시간. 현재 relay 허용 범위는
  `0..0.25 s`다.
- `sample_time_s`: stream 내부 시간축의 초 단위 값이며 PC의 현재 시각이 아니다.

### Arm Relay → G1: UDP 5014

relay는 위 패킷을 검증한 뒤 실행별 token을 추가한다. 나머지 필드는 그대로다.

```json
{
  "schema": "g1.mink.cycle.live.v1",
  "command_provenance": "live_mink",
  "profile": "today",
  "session": "0123456789abcdef0123456789abcdef",
  "sequence": 1001,
  "epoch": 0,
  "sample_time_s": 16.683333,
  "source_age_s": 0.012,
  "event": "active",
  "joints": [0.30, -0.20, 0.10, 1.00, -0.10, 0.00, 0.00],
  "clearance_m": 0.031,
  "relay_token": "PER_RUN_TOKEN"
}
```

`relay_token`은 실행 묶음을 구분하는 영숫자 문자열이다. 암호학적 인증값은 아니다.

### G1 → PC 상태: UDP 5014 응답 → PC 5015 전달

```json
{
  "schema": "g1.mink.cycle.ack.v1",
  "relay_token": "PER_RUN_TOKEN",
  "profile": "today",
  "sequence": 55,
  "epoch": 0,
  "session": "0123456789abcdef0123456789abcdef",
  "state": "waiting"
}
```

`state`는 `initializing`, `waiting`, `tracking`, `returning`, `stopped` 중 하나다.
`initializing`에는 구현에 따라 관절별 정렬 오차를 담은 `ready_blockers` 배열이
추가될 수 있다. `waiting`이며 session/epoch가 맞고 ACK가 250 ms 이내일 때만
새 engage가 가능한 ready로 취급한다.

### Omni Connect → Omni Gateway: WebSocket 32123

```json
{
  "armYaw": 112.62,
  "movementXY": [-0.25, 0.75]
}
```

- `movementXY[0:2]`: 월드 기준 이동 벡터 `mx,my` (무차원).
- 2026-09-21 사용자 입력 계약: yaw 0에서 `mx→전진`, `my→왼쪽`, 양의 yaw는 +X→+Y.
- `armYaw`: degree. Gateway가 연속 샘플 차이를 시간으로 나눠 회전 속도를 만든다.
- Omni 원본에는 프로젝트용 session, sequence, source timestamp가 없다. Gateway가
  수신 시 monotonic timestamp와 sequence를 부여한다.

### G1 discovery: UDP broadcast 5018

```json
{
  "schema": "g1.velocity.discovery.v1",
  "robot_id": "g1-hostname",
  "velocity_port": 5017,
  "sequence": 12,
  "relay_token": "PER_RUN_TOKEN"
}
```

Gateway는 `robot_id` 문자열보다 UDP datagram의 실제 송신 IP를 목적지 주소로
사용한다. 따라서 G1 IP를 코드에 고정할 필요가 없다.

### Omni Gateway → G1: UDP 5017

```json
{
  "schema": "g1.velocity.command.v1",
  "command_provenance": "omni_gateway",
  "simulation_only": false,
  "session": "fedcba9876543210fedcba9876543210",
  "sequence": 220,
  "source_monotonic_s": 4567.123,
  "velocity": [0.60, -0.20, 0.30],
  "relay_token": "PER_RUN_TOKEN"
}
```

- `velocity=[vx,vy,yaw_rate]`: 각각 전후 m/s, 좌우 m/s, 회전 rad/s.
- G1 수신기 계약은 현재 각 성분의 절댓값을 `0.8` 이하로 제한한다.
- 현재 Gateway 설정의 `yaw_max_rad_s` 기본값은 `1.6`이어서 수신기 상한 `0.8`과
  일치하지 않는다. 실제 통합 전에 둘 중 하나로 명시적으로 통일해야 한다.
- 마지막 유효 입력이 250 ms 이상 없으면 Gateway 또는 수신기는 zero velocity를
  사용한다.

### G1 카메라 → Unity: TCP 5011

카메라 경로는 JSON이 아니다. TCP stream에서 매 프레임을 다음 순서로 읽는다.

| 바이트 | 형식 | 의미 |
|---:|---|---|
| 0..3 | ASCII 4 bytes | magic `G1CM` |
| 4..7 | big-endian `uint32` | version, 현재 `1` |
| 8..11 | big-endian `uint32` | frame sequence |
| 12..19 | big-endian `uint64` | Unix epoch nanoseconds |
| 20..23 | big-endian `uint32` | 뒤따르는 JPEG byte 수 |
| 24.. | raw bytes | 완전한 JPEG, SOI `FF D8`부터 EOI `FF D9`까지 |

JPEG 최대 크기는 현재 4 MiB다. 이 경로는 읽기 전용 영상이며 제어 명령과
동일한 packet/session 계약을 사용하지 않는다.

`127.0.0.1`은 특정 PC 주소가 아니라 프로그램이 실행 중인 PC 자신을 뜻한다.
따라서 Unity, Mink, relay, Omni Connect와 Omni Gateway를 같은 PC에서 실행하면
다른 PC로 옮겨도 loopback 주소는 바꾸지 않는다.

하체 이동 경로는 G1 주소를 코드나 실행 인자로 고정하지 않는다. G1 수신기가 UDP
`5018`로 discovery 패킷을 보내면 Gateway는 패킷의 실제 송신 IP와 안내된 velocity
포트를 사용한다. 같은 실행의 token이 일치하는 G1만 선택하며, 첫 번째 G1을 선택한
뒤 다른 로봇의 discovery 패킷은 무시한다.

## G1에서 합치는 값

```text
하체 정책 출력  +  오른팔 관절 목표  =  29축 LowCmd
```

G1에서는 하나의 전신 제어 프로세스만 LowCmd를 송신한다. Mink와 Omni Gateway는 로봇 모터 명령을 직접 송신하지 않고 목표값만 전달한다.

## 주요 데이터

### Mink 오른팔 목표

```text
22 right_shoulder_pitch
23 right_shoulder_roll
24 right_shoulder_yaw
25 right_elbow
26 right_wrist_roll
27 right_wrist_pitch
28 right_wrist_yaw
```

관절 목표 단위는 rad이다.

### Omni 원본

```json
{"armYaw":112.62,"movementXY":[-0.25,0.75]}
```

Omni Gateway는 이 값을 다음 이동 목표로 변환한다.

```text
vx        전후 속도
vy        좌우 속도
yaw_rate  회전 속도
```

## Omni 시작 방향 보정

Omni Gateway는 시작 시 사용자가 잠시 정지해 있는 동안 `vx/vy` 영점을 측정한다.
회전은 Omni와 G1의 절대 방향을 맞추지 않고 연속 Omni 샘플 사이의 각도 변화량을
각속도로 변환한다.

```text
delta_yaw = unwrap(current_armYaw - previous_armYaw)
yaw_rate = clamp(low_pass(yaw_gain × delta_yaw / dt))
```

따라서 Omni와 G1이 시작할 때 서로 다른 방향을 보고 있어도 된다. 사용자가 Omni
arm을 돌리는 동안 G1이 같은 방향으로 회전하고, arm이 멈추면 회전 명령도 0으로
수렴한다. G1의 실제 yaw 피드백은 사용하지 않으므로 회전량은 대략적으로 일치한다.

2026-09-21 수정: `movementXY`는 사용자가 확인한 월드 기준 이동 벡터로 취급한다.
현재 **절대** `armYaw`로 역회전한 뒤 몸체 전진·왼쪽 축별 deadzone과 scale을 적용한다.
이전의 단순 축 교환·부호 반전은 사용하지 않는다.

```text
x = mx - zero_x
y = my - zero_y
theta = radians(current_armYaw)
vx = forward_gain × deadzone(cos(theta) × x + sin(theta) × y)
vy = lateral_gain × deadzone(-sin(theta) × x + cos(theta) × y)
```

`zero_x/zero_y`는 시작 1초의 정지 샘플 평균이다. 방향 정렬 calibration은 필요 없으며,
이동 영점 평균은 별도로 유지한다. 시작각을 뺀 상대 yaw만으로 월드 벡터를 변환하지 않는다.
기존 `vx/vy` 필드 및 `velocity=[vx,vy,yaw_rate]` 앞 두 값에 변환 결과를 담는다.
scale/상한 0.8 m/s, yaw-rate 처리, 원본 CSV는 유지한다. 센서 축·부호와 실제 G1 이동은
이번 수학·프로토콜 시험만으로 검증됐다고 주장하지 않는다.

독립 Omni Gateway와 UDP 자동 발견 계약은 구현했으며 합성 입력 기반 PC 오프라인 시험을 통과했다. 실제 Omni 연결 시험과 G1 배포·실행은 아직 하지 않았다. Omni 경로에서는 UDP `5016`과 기존 키패드용 Velocity Relay를 사용하지 않는다. Gateway가 보정과 검증을 마친 이동 목표를 자동 발견된 G1의 UDP `5017`로 직접 전송한다.
