# G1 VR/Mink/Omni 통합 프로토콜 메모

작성일: 2026-09-16  
목적: 현재 구현된 VR 오른팔 경로와 하체 속도 입력 경로, 앞으로 Omni를
연결할 방법을 다른 개발자가 검토할 수 있도록 구체적으로 설명한다.

## 1. 먼저 구분해야 할 현재 상태

- **구현·시험됨(PC 프로토콜):** Quest 손목 → Unity → Mink IK → 오른팔 7축
  JSON, Unity 키패드 → 속도 JSON, Windows relay의 스키마/순서/범위 검사.
- **과거 물리 후보:** G1의 단일 C++ 프로세스가 하체 12축과 오른팔 7축을
  합쳐 하나의 `rt/lowcmd` publisher로 송신하는 후보가 있었다.
- **현재 차단:** `START_G1_VELOCITY_MINK_KEYPAD.ps1`의 `Robot`/`All`은
  continuous-gait 낙상 이후 의도적으로 차단되어 있다. 아래 설명은 실행 승인이나
  실기 안전성 검증이 아니다.
- **새 학습 정책:** mjlab에서 상체 목표를 관측하는 12축 하체 정책을 학습 중이다.
  아직 ONNX/TorchScript로 export하거나 G1 C++ owner에 연결하지 않았다.
- **Omni:** Omni Connect 1.2.93과 Omni One의 로컬 WebSocket 수신 및 CSV 기록은
  확인했다. Omni → G1 실시간 송신 어댑터는 아직 구현하지 않았다.

## 2. 전체 목표 구조

```text
Quest hand tracking
  → Unity (손목 6D 목표)
  → UDP 127.0.0.1:5005
  → Python Mink/MuJoCo IK
  → 오른팔 관절 22..28 + 상태 이벤트
  → UDP 127.0.0.1:5008
  → Windows arm relay
  → UDP 192.168.123.164:5014
                         ┐
                         │
Omni One                 │
  → Omni Connect         │
  → WS 127.0.0.1:32123   │
  → Unity Omni adapter   │
  → UDP 127.0.0.1:5016   │
  → Windows velocity relay
  → UDP 192.168.123.164:5017
                         ┘
             G1 단일 full-body owner
             ├─ 하체 정책 출력: joints 0..11
             ├─ waist: joints 12..14
             ├─ left arm: joints 15..21
             └─ Mink right arm: joints 22..28
                         ↓
                  단 하나의 rt/lowcmd publisher
```

핵심 원칙은 **팔과 다리에 별도 LowCmd publisher를 만들지 않는 것**이다. 최종
29축 명령은 항상 하나의 full-body owner가 합성한다.

## 3. 포트와 송수신 주체

| 포트 | 전송 방향 | 프로토콜 | 상태/용도 |
|---:|---|---|---|
| `32123/TCP` | Omni Connect → Unity | WebSocket JSON | Omni 로컬 원본 입력, 확인됨 |
| `5005/UDP` | Unity → PC Mink | JSON, 약 60 Hz | Quest 오른손 6D 목표 |
| `5006/UDP` | PC Mink → Unity | JSON | 계산된 팔/FK/target 시각화 |
| `5008/UDP` | PC Mink → Windows arm relay | `g1.mink.cycle.live.v1` | 검증된 오른팔 7축 목표 |
| `5014/UDP` | Windows arm relay → G1 | 같은 JSON + `relay_token` | G1 arm receiver 후보 |
| `5015/UDP` | G1 → relay → PC Mink | `g1.mink.cycle.ack.v1` | 초기화/ready/tracking/return ACK |
| `5016/UDP` | Unity → Windows velocity relay | 현재 `g1.velocity.keypad.v1`, 50 Hz | 키패드 하체 입력; Omni도 이 로컬 경계로 연결 예정 |
| `5017/UDP` | Windows velocity relay → G1 | velocity JSON + `relay_token` | G1 velocity receiver 후보 |
| `5011/TCP` | G1 camera bridge → Unity | JPEG frame stream | read-only 전면 카메라 PiP |

`5005`, `5008`, `5016`은 단일 수신 포트이므로 같은 포트를 쓰는 shadow/dry-run/
중복 launcher를 동시에 실행하면 안 된다. 실행기는 점유 프로세스를 자동 종료하지
않는다.

## 4. Quest → Unity → Mink 입력

Unity 코드: `Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs`

- 송신 주소: `127.0.0.1:5005`
- 주기: 기본 60 Hz
- 위치 단위: m
- 회전: quaternion `[x,y,z,w]`
- engage 순간 Quest 손목과 G1 손목을 각각 기준으로 잡는 clutch-relative 방식이다.
  Quest의 절대 월드 pose를 G1에 그대로 넣지 않는다.
- 0.5초 sustained thumb-index pinch는 해제 요청이다.

현재 패킷 예:

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

`command_state`에는 `active`, `idle`, `pinch_disengaged`, tracking/workspace
상태가 반영된다. 이 패킷은 손목 task 입력이며 관절 명령이 아니다.

## 5. Mink IK와 오른팔 관절 패킷

Python 진입점은
`MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py`,
실제 controller는 `run_mink_g1_right_arm_virtual_center_live.py`다.

- solver: vanilla Mink QP
- position 내부 frame: `right_wrist_roll_link`
- orientation 및 외부 표시 frame: `right_wrist_yaw_link`
- 충돌 회피와 관절 한계 검사 후 오른팔 절대 관절각 7개를 만든다.
- 관절 순서와 단위:

```text
22 right_shoulder_pitch  rad
23 right_shoulder_roll   rad
24 right_shoulder_yaw    rad
25 right_elbow           rad
26 right_wrist_roll      rad
27 right_wrist_pitch     rad
28 right_wrist_yaw       rad
```

Mink → relay 패킷 예:

```json
{
  "schema": "g1.mink.cycle.live.v1",
  "command_provenance": "live_mink",
  "simulation_only": false,
  "profile": "today",
  "session": "0123456789abcdef0123456789abcdef",
  "sequence": 1001,
  "epoch": 0,
  "sample_time_s": 16.683333,
  "source_age_s": 0.012,
  "event": "active",
  "joints": [0.3, -0.2, 0.1, 1.0, -0.1, 0.0, 0.0],
  "clearance_m": 0.031
}
```

검사 항목은 schema/provenance, non-replay session, 증가 sequence, epoch,
finite 값, source age 최대 250 ms, 7축 개수, 최소 clearance 5 mm, 관절 한계,
속도 및 가속도다. `today` 프로필의 목표 제한은 proximal 4축 90 deg/s,
wrist 3축 180 deg/s, 전 축 60 deg/s²다. 이는 명령 제한이며 실제 관절이 같은
속도를 달성한다는 보장은 아니다.

이벤트 의미:

| event | 의미 |
|---|---|
| `idle` | engage 전 대기, 관절 목표 변경 금지 |
| `active` | 오른팔 목표 추종 |
| `pinch` | 안전 경유 자세를 통한 복귀 시작 |
| `tracking_disengaged` | 추적 상실로 복귀 시작 |
| `return` | 복귀 궤적 계속 |
| `fault` | PC 측 fault 통지; native 정책은 별도 분류 |

현재 Windows relay validator는 `fault` 문자열을 전달할 수 있지만, 검토한 native
cycle contract의 정상 이벤트 목록에는 `fault`가 없다. 따라서 현재 후보에서는
`fault`가 정상 복귀 이벤트가 아니라 receiver 거부/stop으로 이어질 수 있다. 최종
owner에 연결하기 전에 이 의미를 하나로 통일해야 한다.

## 6. G1 cycle ACK

G1 후보 receiver가 relay에 보내고 relay가 `127.0.0.1:5015`로 전달한다.

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

state는 `initializing`, `waiting`, `tracking`, `returning`, `stopped` 중 하나다.
Unity/PC에서 `[G1 ROBOT] READY`를 표시하는 것은 fresh ACK가 `waiting`이고
session/epoch가 일치할 때뿐이다. ACK가 250 ms 이상 끊기면 ready로 간주하지
않는다.

## 7. 현재 키패드 하체 속도 프로토콜

Unity 코드: `G1KeypadLocomotionUdpSender.cs`  
relay: `hardware/g1_arm_bridge/g1_velocity_keypad_relay.py`

- Unity → `127.0.0.1:5016`, 50 Hz heartbeat
- relay → `192.168.123.164:5017`
- 키 8/2: forward/back, 4/6: left/right, 7/9: left/right yaw
- 키를 한 번 누를 때 해당 성분을 0.2씩 누적, 범위 ±0.8
- 키 5만 세 성분을 0으로 만든다.

```json
{
  "schema": "g1.velocity.keypad.v1",
  "command_provenance": "unity_keypad",
  "simulation_only": false,
  "session": "fedcba9876543210fedcba9876543210",
  "sequence": 220,
  "source_monotonic_s": 4567.123,
  "velocity": [0.4, 0.2, -0.2]
}
```

`velocity=[vx,vy,wz]`이며 의도 단위는 각각 m/s, m/s, rad/s다. 현재 relay와
receiver의 절대 범위는 각 성분 ±0.8이다. relay는 localhost만 받고 duplicate
JSON key, 비유한값, session/sequence 역행을 거부한다. G1 receiver는 sender IP와
run별 token을 다시 검사한다. 마지막 유효 패킷 후 250 ms가 지나면 속도 요청을
0으로 만든다.

## 8. Omni 원본 프로토콜: 현재 확인된 것

Omni Connect 1.2.93은 Omni One과 Bluetooth로 연결되고 PC 로컬 WebSocket을
연다.

- endpoint: `ws://127.0.0.1:32123`
- 확인한 원본 필드:

```json
{
  "armYaw": 112.62,
  "movementXY": [-0.25, 0.75]
}
```

- `movementXY[0]`: 오른쪽 positive인 정규화 lateral 입력
- `movementXY[1]`: 앞으로 positive인 정규화 forward 입력
- `armYaw`: degree
- PC 기록기는 source JSON과 receive monotonic timestamp를 손실 없이 CSV에
  보존한다. 현재 확인한 CSV schema에는 `movement_x`, `movement_y`,
  `movement_magnitude`, `arm_yaw_deg`, `arm_yaw_rate_deg_s` 등이 있다.

Omni Connect 자체 JSON에는 프로젝트용 session/sequence와 명시적인 source
timestamp가 없으므로, Unity adapter가 수신 즉시 monotonic timestamp와 증가
sequence를 부여해야 한다.

## 9. Omni → G1 연결 계획

키패드 schema를 Omni 데이터에 거짓으로 재사용하지 않는다. Unity에 별도 Omni
adapter를 만들고 다음 canonical packet을 `127.0.0.1:5016`으로 보낼 계획이다.

```json
{
  "schema": "g1.velocity.omni.v1",
  "command_provenance": "omni_connect",
  "simulation_only": false,
  "session": "NEW_GUID_PER_UNITY_PLAY",
  "sequence": 0,
  "source_monotonic_s": 7890.123,
  "source_age_s": 0.008,
  "connected": true,
  "movement_xy": [-0.25, 0.75],
  "arm_yaw_deg": 112.62,
  "velocity": [0.60, -0.20, 0.0]
}
```

초기 변환식 후보는 다음과 같다.

```text
vx = clamp(movement_y × forward_max_m_s)
vy = clamp(-movement_x × lateral_max_m_s)
wz = clamp(yaw_controller(wrap(armYaw - neutralYaw)))
```

그러나 부호, scale, dead zone, `armYaw`를 yaw-rate 명령으로 사용할지 여부는 아직
확정하지 않는다. CSV에서는 초기 yaw가 약 112도인 사례가 있었고, 이를 단순히
월드 0도로 빼는 것은 시각화 기준 보정일 뿐 로봇 회전 명령의 정답이 아니다.
PC-only 화면에서 전진/후진/좌우/좌회전/우회전 여섯 동작으로 다음을 먼저 고정한다.

1. `movementXY` 축과 부호
2. neutral dead zone과 disconnect 시 값
3. 실제 update rate와 packet gap 분포
4. `armYaw` wrap 및 회전 의도와의 관계
5. normalized input을 m/s 및 rad/s로 바꾸는 scale

disconnect, stale 또는 nonfinite 입력은 **속도 0 요청**으로 바꾸되 full-body owner
프로세스를 종료하지 않는다. reconnect는 새 session의 sequence 0에서만 허용한다.

## 10. 새 하체 정책과의 결합 계획

현재 학습 중인 정책은 다음 계약을 목표로 한다.

- action: 다리 12축만
- observation: 기존 G1 상태 + `[vx,vy,wz]` + 상체 목표 17축
- 상체 17축: waist 3 + left arm 7 + right arm 7
- 오른팔 실제 command는 계속 Mink가 담당
- 하체 정책은 팔 목표를 관측하여 정지/보행 중 균형을 보정

현재 학습 fixture는 오른팔 Mink 기록을 사용하고 있으며, 새 정책은 아직 export,
C++ observation parity, 추론 주기, G1 writer 결합을 완료하지 않았다. 따라서 기존
`g1_velocity_12dof_motion.pt`와 새 mjlab checkpoint를 같은 정책으로 보면 안 된다.

최종 단일 owner의 주기 계획은 다음과 같다.

```text
LowState 수신 / LowCmd writer: 500 Hz
하체 정책 추론: 목표 50 Hz, 마지막 유효 출력을 writer 사이에서 hold
Mink arm target: 약 60 Hz 입력, 500 Hz writer에서 제한·보간
Omni velocity request: 약 50 Hz heartbeat, 250 ms stale → zero request
```

## 11. relay token과 신뢰 경계

launcher는 실행마다 16~128자의 영숫자 token을 만들고 arm relay, velocity relay,
G1 receiver에 동일하게 전달한다. token은 우발적인 다른 sender 혼입을 막는 run
binding이며 암호학적 인증이 아니다. source IP, localhost bind, schema,
provenance, session, sequence, freshness 검사를 함께 사용한다.

## 12. 카메라

카메라는 제어 프로토콜과 분리된 read-only 경로다.

```text
G1 SDK2 VideoClient.GetImageSample
  → WSL g1_camera_tcp_bridge.py
  → TCP 5011
  → Unity PiP
```

모터, mode, 카메라 설정 명령을 보내지 않는다. 카메라 프레임 손실이 팔/하체
명령을 바꾸거나 owner를 종료하게 해서는 안 된다.

## 13. 남은 완료 조건

1. Omni Unity adapter 및 `g1.velocity.omni.v1` validator 구현
2. Omni 여섯 방향 PC-only calibration과 stale/disconnect replay 시험
3. 학습 정책의 frozen validation 통과
4. 정책 export 및 Python↔C++ observation/action 수치 parity
5. 단일 owner에 새 하체 policy + Mink arm + Omni request 합성
6. publisher 없이 offline/replay 시험
7. 지지대를 포함한 별도 물리 승인 단계

현재 이 메모는 **인터페이스 설명과 구현 계획**이다. 기존 PC packet 시험이나
시뮬레이션 학습을 실제 G1 안전성 검증으로 표현하지 않는다.
