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
| G1 → PC | UDP JSON | PC `127.0.0.1:5015` | 초기화·ready·tracking·return 상태 | 후보 구현 |
| Omni One → Omni Connect | Bluetooth | PC 로컬 연결 | Omni 이동·방향 입력 | 사용 중 |
| Omni Connect → Omni Gateway | WebSocket JSON | PC `127.0.0.1:32123` | `movementXY`, `armYaw` | 수신 확인 |
| G1 → Omni Gateway | UDP broadcast JSON | PC `0.0.0.0:5018` | G1 식별자와 velocity 수신 포트 | 구현됨, 미배포 |
| Omni Gateway → G1 | UDP JSON | 자동 발견된 G1의 `5017` | 보정된 `vx`, `vy`, `yaw_rate` | Gateway 구현 예정 |
| G1 카메라 → Unity | TCP JPEG | PC `5011` | 전면 카메라 영상 | 사용 중 |

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

`movementXY`는 현재 기록상 이미 `X=오른쪽`, `Y=전방`인 이동 벡터다. 여기에
`armYaw` 회전을 다시 적용하지 않고 다음처럼 축, 부호, 영점과 크기만 보정한다.

```text
vx = forward_gain × deadzone(movementXY.y - forward_zero)
vy = -lateral_gain × deadzone(movementXY.x - lateral_zero)
```

`forward_zero`와 `lateral_zero`는 시작 시 정지 샘플의 평균으로 정한다. Omni의
오른쪽 양수 X를 G1 정책의 왼쪽 양수 Y로 바꾸기 위해 lateral 부호를 반전한다. 통신 재연결 때는 이동
영점과 이전 yaw 샘플을 다시 잡고, 보정이 끝나기 전까지 이동 목표는 0으로 둔다.

독립 Omni Gateway와 UDP 자동 발견 계약은 구현했으며 합성 입력 기반 PC 오프라인 시험을 통과했다. 실제 Omni 연결 시험과 G1 배포·실행은 아직 하지 않았다. Omni 경로에서는 UDP `5016`과 기존 키패드용 Velocity Relay를 사용하지 않는다. Gateway가 보정과 검증을 마친 이동 목표를 자동 발견된 G1의 UDP `5017`로 직접 전송한다.
