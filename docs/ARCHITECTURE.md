# Teleoperation Architecture

## 1. 목적과 범위

이 문서는 Quest 3S에서 추적한 사용자 손목 자세를 MuJoCo의 Unitree G1 오른팔 움직임으로 변환하는 현재 구조를 설명한다. 또한 실제 G1, 실제 D435i, 양팔 제어로 확장할 때 유지해야 할 책임 경계와 리팩터링 순서를 정의한다.

현재 프로젝트의 핵심 목표는 다음과 같다.

1. engagement 순간 목표가 튀지 않는 hand-to-robot mapping
2. tracking 지연·유실·중복 packet에 대한 예측 가능한 동작
3. workspace, 관절 범위, 몸통 충돌을 고려한 안전한 IK
4. Unity, MuJoCo, 실제 로봇이 공유할 수 있는 통신·좌표 계약
5. Quest나 실물 장비 없이도 핵심 로직을 테스트할 수 있는 구조

---

## 2. 시스템 컨텍스트

```mermaid
flowchart LR
    Operator[Operator]
    Quest[Meta Quest 3S]
    Unity[Unity XR application]
    Command[UDP command :5005]
    Controller[MuJoCo G1 controller]
    Model[Unitree G1 29DoF model]
    Feedback[UDP feedback :5006]
    Camera[Simulated / real D435i]

    Operator --> Quest --> Unity
    Unity --> Command --> Controller --> Model
    Controller --> Feedback --> Unity
    Controller --> Camera
```

### 현재 end-to-end 경로

```text
Quest right wrist pose
→ Unity hand binding and engagement UI
→ legacy UDP JSON command
→ strict legacy packet adapter
→ session/sequence ownership watchdog
→ active/hold/workspace-fault command state
→ clutch-relative target calculation
→ G1 right-arm Mink 6D QP IK
→ joint/velocity/collision constraints and non-arm DOF freeze
→ MuJoCo state update
→ UDP state feedback to Unity
```

루트의 `START_VR_HAND_TO_MUJOCO.bat`이 현재 실행 진입점이며, 다음 두 프로세스를 연다.

- Unity 프로젝트 `Unity_G1_VR`
- MuJoCo 실행기 `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py`

---

## 3. 계층별 책임

### 3.1 Unity operator layer

주요 경로:

```text
Unity_G1_VR/Assets/G1Teleop/
```

책임:

- Quest XR Hands 입력 획득
- 실제 손목과 engagement target 표시
- calibration/engagement 사용자 경험 제공
- 사용자 손 이동을 현재 로봇 목표로 mapping
- UDP command 송신
- MuJoCo state feedback 수신 및 HUD 반영

대표 구성요소:

| 구성요소 | 책임 |
| --- | --- |
| `G1ExistingHandTargetBinder` | 추적 손목과 target 연결, calibration 상태 관리 |
| `G1ExistingTargetUdpSender` | 목표 위치·회전, session, sequence, command state 송신 |
| `G1RobotStateUdpReceiver` | 오른팔 상태와 workspace/collision feedback 수신 |
| `G1OfficialRig` 및 관련 클래스 | Unity G1 모델과 관절 표시 |

Unity는 사용자의 입력과 피드백을 담당하지만, 장기적으로는 최종 안전 판정을 내리는 계층이 되어서는 안 된다. Unity가 중단되거나 packet이 조작되더라도 backend/controller가 독립적으로 안전 상태를 유지해야 한다.

### 3.2 Shared Python foundation

주요 경로:

```text
backend/g1_teleop/
```

| 모듈 | 책임 |
| --- | --- |
| `calibration.py` | 중립 pose, 안정성 검사, workspace scale, rigid registration |
| `transforms.py` | pose matrix, quaternion, 좌표 변환 |
| `protocol.py` | 버전이 명시된 command/state JSON 계약과 검증 |
| `command_adapter.py` | 현재 legacy command와 V2 packet을 공통 내부 명령으로 변환 |
| `live_receiver.py` | non-blocking UDP queue drain, strict parsing, session/sequence 적용 |
| `runtime_state.py` | idle, active, hold, workspace-fault 상태 전이 |
| `mink_command_stream.py` | Mink 실행기용 clutch 보존, timeout hold, session 인계 처리 |
| `watchdog.py` | sequence/session 감시, timeout, workspace debounce/fault latch |
| `camera.py` | 공통 camera frame/intrinsics 계약 |
| `camera_factory.py` | simulation과 real D435i source 선택 |
| `g1_camera_mount.py` | G1 D435i 장착 pose |
| `unitree_image_transport.py` | Unitree simulation image shared memory transport |

이 계층은 Unity 또는 MuJoCo에 종속되지 않는 순수 로직의 중심이어야 한다. 가능한 기능은 여기로 이동해 단위 테스트 가능성을 높인다.

### 3.3 MuJoCo control layer

현재 launcher가 사용하는 핵심 파일:

```text
MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py
```

별도 실험 실행기:

```text
MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py
```

현재 제어 계층의 책임:

- command-line argument 처리
- G1 XML 읽기와 demo scene 생성
- UDP socket과 공통 command stream 연결
- clutch reference 생성
- 오른팔 Mink QP task와 constraint 구성
- joint/velocity/collision 제한
- 비오른팔 DOF freeze
- runtime status 저장
- Unity state feedback
- MuJoCo viewer

packet 검증과 상태 관리는 `backend/g1_teleop`으로 분리되었다. scene 생성과
Mink task orchestration은 아직 실행기에 남아 있으므로 이후 단계에서 추가 분리한다.

### 3.4 Configuration and operations

```text
config/
tools/
docs/
```

- `config`: 카메라 source와 실행 프로필
- `tools`: build, fake input, camera verification, diagnostics
- `docs`: architecture, protocol, camera operation

현재 motion/workspace/network 값의 일부가 Unity Inspector와 Python 상수에 중복되어 있다. 이 값들은 공통 configuration으로 옮기되, Unity build에서 읽을 수 있는 배포 방식까지 함께 설계해야 한다.

---

## 4. 좌표계와 pose mapping

### 4.1 현재 축 정의

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

위치 변환은 다음 basis를 사용한다.

```text
robot.x = operator.z
robot.y = -operator.x
robot.z = operator.y
```

행렬 형태는 다음과 같다.

```text
[ 0  0  1 ]
[-1  0  0 ]
[ 0  1  0 ]
```

현재 이 변환 개념이 Unity와 Python 양쪽에 존재한다. 동일 변환을 두 번 적용하거나 한쪽만 수정하는 오류를 막기 위해 최종 구조에서는 다음 원칙을 권장한다.

```text
Unity     : 원본 operator-frame pose와 추적 상태 송신
Foundation: canonical robot-frame pose로 변환
Controller: robot-specific target와 safety 적용
```

### 4.2 Clutch-relative mapping

engagement 시 다음 기준을 저장한다.

- 사용자의 입력 위치와 회전
- 로봇의 실제 손목 위치와 회전
- shoulder-elbow-wrist로 계산한 elbow pole reference

이후 사용자의 상대 변화량만 로봇 기준 pose에 더한다.

```text
target_position
= robot_position_at_engagement
+ current_input_position
- input_position_at_engagement
```

회전도 engagement 이후의 상대 회전만 적용한다. 따라서 사용자가 target에 손을 맞추는 동안의 절대 오프셋이 로봇에 갑자기 전달되지 않는다.

G1 손목의 engagement marker에 손을 맞추고 0.55초 유지하면 engage한다.
Engagement 순간의 사용자 손 pose와 G1의 현재 손목 pose를 별도 기준으로
저장하므로 target jump가 없다. Engage 후 엄지-검지 pinch를 0.50초 유지하면
수동으로 disengage한다.

---

## 5. 오른팔 제어 구조

### 5.1 기본 6D task

launcher가 사용하는 prototype은 `right_wrist_yaw_link`에 하나의 Mink
`FrameTask`를 둔다.

- position cost: `8.0`
- orientation cost: `2.0`
- gain: `0.35`
- LM damping: `1e-5`
- solver: DAQP 우선

오른팔 7개 관절 전체로 손목 위치와 회전을 동시에 풀며, engagement 때 저장한
사용자 손목과 실제 G1 손목의 상대 변화만 목표로 사용한다.

### 5.2 자연스러운 해 선택

`PostureTask`가 engagement 시점 자세를 기준으로 불필요한 관절 이동을 줄인다.
별도 `DampingTask`는 shoulder/elbow 쪽 비용을 손목보다 크게 두어 단순 손목
회전에서 팔꿈치가 과도하게 따라오는 해를 억제한다.

### 5.3 QP 제약

각 60 Hz step에서 다음 제약을 함께 푼다.

1. MuJoCo 관절 위치 범위인 `ConfigurationLimit`
2. 오른팔 최대 관절 속도 75 deg/s인 `VelocityLimit`
3. geometry 간 최소 거리와 감지 거리를 사용하는 `CollisionAvoidanceLimit`
4. 오른팔 외 모든 DOF 속도를 0으로 만드는 `DofFreezingTask`

목표를 먼저 계산한 뒤 사후 clamp하는 구조가 아니라 task와 제한을 같은 QP에
포함한다.

### 5.4 Virtual-center 실험

`run_mink_g1_right_arm_virtual_center_live.py`는 위치 task를
`right_wrist_roll_link`, 회전 task를 `right_wrist_yaw_link`로 분리한다. 손목
한계 근처에서만 proximal orientation assist를 켜는 실험이며 현재 메인
launcher 경로는 아니다.

---

## 6. 안전 상태와 실패 처리

### 6.1 입력 상태

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Active: Unity alignment and calibration completed
    Active --> Hold: short tracking loss / idle packet
    Hold --> Active: tracking recovers
    Active --> Idle: sustained pinch manual disengage
```

`MinkCommandStream`은 hold에서 마지막 target과 clutch reference를 유지한다.
tracking loss나 packet timeout만으로 재정렬하지 않는다. 사용자의 sustained
pinch와 오래된 sender를 대체하는 새 session만 clutch reference를 초기화한다.

### 6.2 안전 메커니즘

| 메커니즘 | 목적 |
| --- | --- |
| sequence watchdog | 중복·역순 packet 거부 |
| session watchdog | 동시에 실행된 오래된 Unity sender와 충돌 방지 |
| timeout hold | 입력 중단 시 새 목표 갱신을 멈추고 마지막 관절 상태 유지 |
| continuous Cartesian reference | 초록 목표를 사용자 손 방향으로 끊김 없이 속도 제한하여 이동 |
| sustained pinch disengage | 사용자가 의도적으로 즉시 clutch를 해제 |
| direct Cartesian target | 초록 목표는 필터링된 사용자 손 목표를 즉시 표시하고 IK에 전달 |
| Mink velocity limit | 관절 속도를 QP 내부에서 제한 |
| configuration limit | MuJoCo 관절 범위 준수 |
| collision avoidance | 지정 geometry 간 거리를 QP 내부에서 제한 |
| non-arm DOF freeze | 오른팔 외 관절의 의도치 않은 이동 차단 |

### 6.3 현재 safety authority 문제

현재 live 경로는 Unity의 직육면체 workspace와 주황 경고를 사용하지 않는다.
backend는 초록 목표를 필터링된 사용자 손 목표에 즉시 배치한다. 별도의
Cartesian 속도 제한이나 오차 임계값으로 초록 목표를 지연·승인·되돌리지 않는다.
로봇만 Mink의 joint velocity, configuration, collision constraint 아래에서
초록 목표를 추종한다.

외부 위치 계약은 `right_wrist_yaw_link`이다. 내부 위치 Task는
`right_wrist_roll_link`를 사용하므로 매 제어 주기마다 현재
`yaw_position - roll_position` 오프셋을 외부 목표에서 빼 내부 중심 목표를
만든다. 따라서 손목 회전으로 링크 간 오프셋이 바뀌어도 초록 목표는 Unity가
보낸 손목 위치를 지나치거나 뒤처지지 않는다.
`use_rectangular_workspace_fallback=false`이면 Unity UDP 송신기 역시 직육면체
clamp를 적용하지 않으며, 화면에 표시한 목표와 같은 값을 보낸다.

Quest 손 추적이 재획득되며 손목 위치가 한 프레임에 20 cm를 넘게 순간이동하면
실제 손동작으로 사용하지 않는다. 중립 손목 기준을 동일한 이동량만큼 보정해
현재 로봇 목표를 유지한다. 같은 재획득 구간의 회전 중립 기준도 함께 보정하고,
이후 프레임부터 연속적인 상대 위치와 회전만 반영한다.

따라서 현재 동작 계약은 다음과 같다.

```text
tracking loss / idle / UDP timeout -> hold, clutch 유지
sustained pinch                    -> idle, clutch 초기화
return and explicit realignment     -> 새 clutch 기준으로 active
```

Unity 시각화는 파란 원을 사용자 손목, 초록 원을 필터링된 직접 명령 목표,
분홍 원을 실제 G1 손목으로 표시한다. 흰 선은 파란 원과 분홍 원을 연결해 현재
이동 방향을 보여준다.

목표 구조:

```text
Unity
- tracking validity
- operator UI
- warning display
- re-alignment interaction

Backend/controller
- packet validity
- session ownership
- workspace decision
- timeout state
- final target acceptance
- collision and joint safety
```

Unity가 보내는 `active` 요청은 명령일 뿐이며, controller가 최종적으로 허용한 상태만 로봇에 적용해야 한다.

---

## 7. 현재 통신 경계

현재 live command는 `G1ExistingTargetUdpSender.cs`가 생성하는 legacy packet을
사용한다. 이 packet도 `command_adapter.py`에서 `session_id`, `sequence`,
`command_state`, pose 형식까지 엄격하게 검증한다. 반면
`backend/g1_teleop/protocol.py`에는 versioned V1/V2 계약이 별도로 정의되어
있다.

두 계약은 아직 동일하지 않다.

- live packet에는 `session_id`, `command_state`, `right.pos`, `right.rot`이 있다.
- V2에는 `schema`, `session_id`, `frame_id`, head, 양쪽 wrist, `armed`, `clutch`가 있다.
- V2 packet은 strict parse할 수 있지만 현재 raw tracking-frame mapping이 완료되지 않아 live control 권한은 비활성화되어 있다.

따라서 V2를 즉시 live packet으로 교체하지 않는다. 좌표 mapping과 장비 회귀
검증을 마친 뒤 호환 마이그레이션을 [`PROTOCOL.md`](PROTOCOL.md)에 따라
진행한다.

또한 MuJoCo UDP receiver는 현재 `0.0.0.0:5005`에 bind한다. 로컬 PC에서만 사용할 경우 `127.0.0.1` bind 또는 firewall 제한이 더 안전하다. 현재 UDP packet에는 인증·암호화가 없으므로 외부 네트워크에 그대로 노출하면 안 된다.

---

## 8. 목표 구조

대규모 이동을 한 번에 수행하지 않고 다음 경계를 목표로 한다.

```text
backend/g1_teleop/
├─ calibration.py
├─ transforms.py
├─ protocol.py
├─ config.py
├─ watchdog.py
│
├─ control/
│  ├─ ik.py
│  ├─ trajectory.py
│  ├─ workspace.py
│  ├─ collision.py
│  └─ limits.py
│
├─ transport/
│  ├─ udp_command.py
│  ├─ udp_state.py
│  └─ unitree_image.py
│
└─ simulation/
   ├─ scene_builder.py
   ├─ model.py
   └─ camera.py

MuJoCo_G1_Controller/scripts/
└─ run_mink_g1_right_arm.py  # future orchestration-only entry point
```

목표 실행기의 책임은 다음 수준으로 줄인다.

```python
config = load_config()
model = create_simulation(config)
transport = create_transport(config)
controller = RightArmController(model, config)

while running:
    command = transport.receive_latest()
    state = controller.step(command)
    transport.publish_state(state)
```

---

## 9. 단계별 리팩터링 계획

### Phase 1 — 문서와 계약 고정

- README에서 core implementation과 third-party 영역 구분
- 현재/목표 architecture 문서화
- legacy packet과 versioned protocol 차이 명시

### Phase 2 — Protocol adapter

- backend에 legacy packet parser를 독립 모듈로 이동
- 신규 packet을 동시에 받을 수 있는 adapter 추가
- malformed, duplicate, stale-session 테스트 강화

### Phase 3 — Configuration 중앙화

- network, workspace, timeout, rate limit 값을 공통 schema로 정의
- Python loader와 Unity importer를 각각 구현
- 시작 시 effective configuration을 로그로 남김

### Phase 4 — Control 분리

- pure IK math 이동
- safe reference trajectory 이동
- workspace/collision 정책 이동
- scene XML generation 이동
- 기존 함수 기반 테스트를 새 모듈에 그대로 연결

### Phase 5 — Authority 정리

- backend/controller를 최종 safety authority로 지정
- Unity의 중복 safety 로직은 표시·사용자 interaction 중심으로 축소
- state feedback을 versioned contract로 통합

### Phase 6 — Automation

- Python unit test CI
- JSON/YAML schema 검증
- Unity batchmode compile validation
- 문서 링크와 핵심 파일 존재 여부 검사

---

## 10. 테스트 전략

### Unit tests

장비 없이 검증할 항목:

- pose/quaternion validation
- calibration stability와 neutral mapping
- coordinate conversion
- sequence/session watchdog
- workspace debounce와 latch
- rate limiter
- IK pseudoinverse, null-space posture, elbow pole
- collision step rollback

### Integration tests

프로세스 수준 검증:

- fake sender → MuJoCo controller
- Unity editor sender → MuJoCo controller
- controller → Unity state feedback
- simulated head camera → shared memory reader

### Manual hardware tests

- Quest Link tracking continuity
- engagement 시 target jump 여부
- workspace 경계에서 초록 목표 projection과 관절 제한 동작
- 실제 D435i frame와 simulation frame 교체
- 장시간 실행 중 session 재시작과 recovery

---

## 11. 외부 구성요소 경계

다음은 실행에 필요한 외부 코드·자산 영역이다.

```text
MuJoCo_G1_Controller/external/unitree_mujoco/
Unity Package Manager dependencies
```

리팩터링 시 이 영역을 프로젝트 고유 제어 코드와 섞지 않는다. 외부 파일을 수정해야 한다면 변경 이유와 upstream 기준 commit/tag를 별도 문서나 patch로 남기는 것이 좋다.
