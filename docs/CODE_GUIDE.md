# G1 코드 읽기와 설명 가이드

이 문서는 G1 텔레오퍼레이션 코드의 데이터 흐름과 주요 함수,
IK 계산 방식, 설정값의 의미를 설명한다.

기준: 2026-09-03 코드 및 Mink 1.3.0.

## 0. 처음 읽을 때

이 문서는 주요 경로의 연결과 계산을 설명한다. 모든 파일의 전체 함수 설명이
완료된 것은 아니다. [파일 색인](CODE_INDEX.md)에서 파일별 목록과 확인 범위를 구분한다.

1. 아래 세 경로 중 작업 대상을 먼저 고른다. BAT는 진입점이지 제어 계산 본체가 아니다.
2. 입력을 받는 파일부터 계산·출력 순서로 읽는다. 파일명의 `prototype`, `dry_run`만 보고 사용 여부를 판단하지 않는다.
3. 수정 전 해당 입력의 단위·좌표·출처와 호출자를 확인한다.
4. 관련 테스트를 실행하고, 결과를 기구학 검증/통신 검증/실물 검증으로 구분한다.

### 사용하는 구성요소

| 구성요소 | 이 프로젝트에서 하는 일 | 하지 않는 일 |
| --- | --- | --- |
| Meta XR / OVR | 손과 머리 추적값 제공 | G1 관절각 계산 |
| Unity / C# | 입력 처리, 상태 표시, UDP 송수신 | 실제 모터 PD 제어 |
| NumPy | 벡터·행렬·회전 계산 | 로봇 통신 |
| MuJoCo | 모델, FK, Jacobian에 필요한 기구학 및 거리 계산 | 현재 qpos 갱신만으로 실제 모터 응답 보장 |
| Mink | task와 제한을 differential IK QP로 구성 | 모터 명령 발행 |
| qpsolvers / DAQP | 구성된 QP의 수치해 계산 | 의미 있는 인간 자세 자동 보장 |
| Unitree SDK2 / CycloneDDS | 로봇 상태 수신과 명령 토픽 통신 | VR 손목 목표의 IK 계산 |
| TorchScript / TWIST2 .pt | 별도 C++ 경로의 하체 정책 추론 | 현재 Mink 경로의 손목 IK |

Python의 import는 코드 의존성, 함수 호출은 처리 순서, UDP/DDS는 프로세스 사이
전송이다. Unity의 public 참조는 Inspector/씬에서 연결되므로 import 검색만으로
모든 연결을 확인할 수 없다.

## 1. 먼저 구분할 세 경로

### A. 현재 VR 시뮬레이션

```text
START_VR_HAND_TO_MUJOCO.bat
  Unity: 손목 추적/engage -> G1ExistingTargetUdpSender -> UDP 5005
  Python: MinkCommandStream.poll -> clutch 상대 목표
          -> FeasibleTargetPlanner.Plan -> Mink QP -> DAQP
          -> 검증한 첫 관절 단계 -> MuJoCo FK
  UDP 5006 -> Unity: 시뮬레이션 관절 상태/목표 표시
  UDP 5008 -> 별도 Gate 7: 관절 후보와 진단 정보
```

기본 실행기는 `run_mink_g1_right_arm_virtual_center_live.py`다.
`run_mink_g1_right_arm_prototype.py`는 이름과 달리 공통 모듈로 계속 사용하며,
`--baseline` 비교 실행도 제공한다. 삭제 대상이 아니다.
MuJoCo에서 관절 상태를 갱신하고 FK를 계산하는 것은 실제 모터 PD 응답을
재현했다는 뜻이 아니다. 현재 주 경로는 기구학적 검증이다.

### B. 기존 Arm SDK 하드웨어 경로

```text
Mink 후보 UDP 5008 -> Windows relay -> WSL UDP 5013
  -> gate7_live_arm_sdk.py + 직접 읽은 rt/lowstate + 검증/권한 확인
  -> rt/arm_sdk
실제 rt/lowstate -> MuJoCo 미러 UDP 5009 -> Unity 표시 UDP 5010
Gate 7 live adapter -> 직접 읽은 실측을 Unity UDP 5010으로 전송
```

Unity의 hardware 표시 모드는 실측 상태를 표시한다. Mink 계산값을 실제
로봇이 수행한 값으로 대신 표시하면 안 된다. UDP 전송 성공도 모터 추종 성공과 다르다.
Gate 7/카메라/읽기 전용/회귀 시험 도구는 아직 필요한 경로이므로 유지한다.
Unity 표시 모드는 simulation/hardware/recorded를 명시적으로 선택한다.
hardware 입력이 끊겼다고 시뮬레이션 값을 실측 대신 표시하지 않는다.

### C. 기존 왼팔 제어 코드를 기반으로 한 오른팔 수동 시험

```text
twist2_right_arm_trial.cpp
  키보드 -> 오른팔 22..28 목표 -> 속도 제한
  LowState + 상체 목표 + 상태 이력 -> TWIST2 .pt 추론 (50 Hz)
  hybrid_target: 하체 정책 출력 + 상체 직접 목표
  Controller::write_cycle (500 Hz) -> 전체 rt/lowcmd
```

이 경로에는 Mink와 VR 소켓이 아직 연결되지 않았다. 오른팔 인덱스와 이름만
바꾼 최소 변형이며, 원본 비교를 위해 C++ 본문에 설명 주석도 추가하지 않았다.
두 물리 경로 B/C를 동시에 실행하지 않는다. C++ 생성자는 DDS publisher를
생성하고, 프로그램 종료 시 CSV를 저장하므로 읽기 전용 프로그램이 아니다.

## 2. 먼저 읽을 파일과 함수

경로는 프로젝트 루트 기준이다. 줄 번호 대신 함수명을 검색하면 편집 후에도 찾을 수 있다.

| 순서 | 파일 / 검색할 이름 | 설명할 핵심 |
| --- | --- | --- |
| 1 | `Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs` | 손 추적 유효성, 사용자 입력 기준, engage/pinch 상태 |
| 2 | `Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs` | 목표 단위/축, session/sequence, active/idle/disengage 패킷 |
| 3 | `backend/g1_teleop/mink_command_stream.py` / `poll` | 패킷 검증과 clutch 재설정 조건; 입력 유실과 의도적 해제 구분 |
| 4 | `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py` / `main` | task/limit 생성, 손목 목표 계산, 결과 표시·송신 |
| 5 | 같은 파일 / `VirtualCenterOrientationTask` | 회전 Jacobian 유지, 손목 한계 근처 cost/오차 완화 |
| 6 | `MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py` / `Plan` | QP 후보, backtracking, 중간 충돌 검사, 첫 단계 적용 |
| 7 | `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py` | `_build_collision_pairs`, `_initial_configuration`, `_state_packet`, `_select_solver` |
| 8 | `MuJoCo_G1_Controller/scripts/g1_right_arm_common.py` | 모델 생성, 관절 이름/주소, `operator_rotation_to_robot_matrix` |
| 9 | `hardware/g1_arm_bridge/arm_sdk_teleop_contract.py` | 물리 출력 전 목표/상태 계약과 HOLD·복귀 상태 머신 |
| 10 | `hardware/g1_arm_bridge/gate7_live_arm_sdk.py` | WSL 수신, 실측 검사, 승인 후 publisher 출력·해제 |

### 오른팔 C++를 설명할 때

파일: `experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp`.
공통 정의: `references/lower_body/twist2_deploy/cpp_g1_twist2/twist2_common.hpp`.

| 코드 단위 | 입력 -> 처리 -> 출력 |
| --- | --- |
| `TerminalKeyboard` | 터미널 입력 -> 즉시 키 읽기; 소멸 시 터미널 설정 복원 |
| `Controller` 생성자 / `on_state` / `snapshot` | DDS 초기화, LowState 수신 -> 스레드 간 공유할 상태 스냅샷 |
| `validate_state` / `wait_for_preflight` | 모드·통신·자세·속도 등의 기존 조건 -> 진행 또는 중단 |
| `capture` / `capture_q` / `capture_tau` | 시작 실측 자세/토크를 이후 기준으로 보관 |
| 키보드 처리 / `update_keyboard_joint_command` | 선택 키 -> 오른팔 인덱스 -> 요청 각도 갱신 및 soft limit |
| `rate_limited_target` | 요청 각도 -> 주기당 이동량 제한 -> 적용할 목표 |
| `ObservationHistory::infer` | 목표/IMU/관절/이전 action/이력 -> 1432차원 입력 -> 정책 action |
| `Policy::infer` | TorchScript 추론; 이 코드에서 정책을 새로 학습하지 않음 |
| `hybrid_target` | 다리 `kDefault + 0.5 * action`, 허리·팔은 전달받은 상체 목표 |
| `set_desired` / `desired` | 50 Hz 계산 결과를 500 Hz 출력 스레드로 전달 |
| `start_writer` / `write_cycle` | 목표 속도·범위·예측 토크 제한 -> q/dq/kp/kd/tau/CRC -> LowCmd |
| `handoff_and_activate` | 기존 motion service에서 제어권 인계; 단순 읽기가 아님 |
| `latch` / `finish` / `signal_handler` | 중단 사유 고정, damping 종료 처리; 서 있는 자세 복원을 보장하지 않음 |
| 통계·CSV 저장 | 전달 주기와 후보/실측 기록; G1에서 실행하면 G1 파일 생성 |

`kRightArmBegin=22`, `kRightArmDofs=7`, `joint=kRightArmBegin+selected`가
오른팔 선택의 핵심이다. 22~28 순서는 shoulder pitch/roll/yaw, elbow,
wrist roll/pitch/yaw다. MuJoCo `qpos` 주소와 SDK 인덱스는 별개이므로 이름으로 매핑한다.

## 3. 손목만 받아서 어깨·팔꿈치까지 계산하는 이유

목표는 손목 위치 3개(m)와 회전 quaternion 4개(x,y,z,w)다. Quaternion은
정규화 조건이 있어 회전 자유도는 3개이며, 총 목표 자유도는 6개다.
로봇 모델에는 각 관절의 축, 링크 길이, 부모·자식 관계가 있으므로 현재 관절각에서
손목 자세를 계산할 수 있다. 이것이 FK다. IK는 목표 자세를 만족할 관절각을 찾는다.

7개 관절로 6D 목표를 맞추므로 일반적인 비특이 자세에서는 여자유도가 1개 생긴다.
같은 손목 자세에도 팔꿈치 방향이 다른 해가 가능하다. 현재 코드는 자세 비용과
관절 이동 비용으로 해 선택에 편향을 준다. 사람 팔꿈치를 직접 측정한 것도,
모든 자세에서 인간다운 해를 보장한 것도 아니다. 비용은 엄격한 우선순위가 아니다.

## 4. Jacobian, gain, cost를 구분하기

`J(q)`는 현재 자세에서 관절을 조금 바꿀 때 task 오차가 얼마나 변하는지 나타낸다.
기본 관계는 `e(q + delta_q) ~= e(q) + J(q) delta_q`다.
FrameTask는 MuJoCo의 기하학적 Jacobian에 SE(3) 오차의 log 미분을 적용한다.
단순 XYZ 차이뿐 아니라 회전 오차와 기준 프레임을 함께 처리한다.

| 이름 | 역할 | 크게 하면 |
| --- | --- | --- |
| task `gain` (`alpha`) | 한 IK 단계에서 줄이려는 오차 비율 | 더 적극적으로 오차를 줄이려 하지만 속도 제한은 그대로 |
| task `cost` | 오차 성분의 상대 중요도·단위 스케일 | 다른 task에 비해 해당 오차 감소를 더 선호 |
| `PostureTask` cost | 기준 관절 자세에서 멀어지는 것을 억제 | 손목 추종보다 기준 자세 유지가 강해질 수 있음 |
| `DampingTask` cost | 관절 변화량 자체에 비용 | 해당 관절이 움직이기 어려워짐; 모터 Kd가 아님 |
| task `lm_damping` | task 오차 크기에 따른 수치 정규화 | 큰 오차에서 관절 변화가 더 억제될 수 있음 |
| solve `damping` | 모든 task를 합친 QP의 대각 정규화 | 수치 안정성과 추종 속도의 절충 |
| `CollisionAvoidanceLimit.gain` | 거리 제약에서 허용하는 접근량에 영향 | PD/FrameTask gain과 다른 용도; 임의 증가는 금물 |

“Jacobian weight를 조정했다”보다는 **어느 task의 어떤 cost인지** 말해야 한다.
현재 `VirtualCenterOrientationTask.compute_jacobian`은 원래 FrameTask의
Jacobian을 반환한다. 어깨/팔꿈치 열을 임의로 줄이지 않는다. 손목 우선 선택은
별도 자세/이동 비용으로 유도한다. 손목 한계 근처의 오차 크기 제한과 cost 변경은
우리 코드의 추가 정책이며, Mink 원본 그 자체라고 설명하면 안 된다.

## 5. Mink가 실제로 푸는 계산

설치된 `mink/tasks/task.py`의 `_weighted_residual` 기준:

```text
C = diag(cost)
A = C J
b = -C alpha e
mu = lm_damping * (b^T b)

H_task = A^T A + mu I
c_task = -A^T b
```

여러 task의 `H`, `c`를 합치고 solve-level damping을 대각에 더한다.
`ConfigurationLimit`, `VelocityLimit`, `CollisionAvoidanceLimit`는 부등식으로,
`DofFreezingTask`는 비오른팔 DOF를 고정하는 등식으로 들어간다.

```text
minimize_delta_q   1/2 delta_q^T H delta_q + c^T delta_q
subject to        G delta_q <= h
                  E delta_q  = f
```

Mink는 문제를 조립하고 `qpsolvers.solve_problem`을 호출한다. 프로젝트는
`_select_solver()`에서 DAQP를 우선 선택한다. 반환값은 `delta_q / dt`, 즉
관절 속도다. 제한이 없는 의사역행렬 해를 계산한 뒤 마지막에만 각도를 자르는
방식과 다르다. 로컬 선형화이므로 임의의 먼 목표까지 도달을 보장하지 않는다.

**cost 예시:** cost가 2이면 Jacobian과 오차에 각각 2를 곱하므로 해당 항의
제곱 비용 기여는 4배가 된다. 따라서 8/2를 단순히 “위치를 회전보다 4배
정확히 맞춘다”라고 설명할 수 없다. 위치와 회전의 단위, 현재 오차, 제약도 다르다.

## 6. 현재 기본 virtual-center 값

아래는 Python 소스에서 확인한 값이다. 공식 최적값이나 물리 안전 인증값이 아니다.

| 설정 | 현재 값 | 적용 위치 / 이유 |
| --- | --- | --- |
| `CONTROL_HZ`, `DT` | 60 Hz, 1/60 s | QP 한 단계 시간; 실제 수행 주파수 보장은 아님 |
| `POSITION_COST` | 8.0 | wrist-roll 중심 위치 task |
| `ORIENTATION_COST` | 2.0 | wrist-yaw 회전 task의 기본 cost |
| `FRAME_GAIN` | 0.35 | 위치·회전 task 오차 피드백 |
| `POSTURE_COST` | 0.04 | 기준 관절 자세 비용 |
| `VIRTUAL_CENTER_WRIST_POSTURE_COST_SCALE` | 0.05 | 손목 3축 자세 비용은 0.002; 손목이 회전을 담당하기 쉽게 함 |
| virtual-center proximal / wrist damping cost | 0.03 / 0.015 | 어깨·팔꿈치 움직임에 더 큰 비용 |
| `LM_DAMPING`, `QP_DAMPING` | 1e-5 / 1e-8 | task별 / QP 전체 정규화 |
| proximal / wrist velocity cap | 각각 0.08 rad/s (약 4.58 deg/s) | static stand 키보드 기본 1배와 동일한 수치의 상한; 추종 동작 동일 보장은 아님 |
| local `mink-default` clearance / detection | 5 / 10 mm | Mink 1.3.0 기본값; Unity/MuJoCo 로컬 실행의 기본 프로필 |
| physical `hardware-guarded` clearance / detection | 20 / 40 mm | 실제 출력 후보 경로에서 명시적으로 강제하는 추가 여유 |
| Gate 7 command hard stop | 12 mm | 실제 출력 어댑터의 독립 검사; Mink 목표 거리와 별도 |
| `COLLISION_GAIN` | 0.85 | 거리 기반 접근 제한 |
| assist enter / release / full margin | 18 / 28 / 5 deg | 손목 한계 접근 시 히스테리시스 |
| orientation cost 최소 배율 | 0.25 | 한계 근처 회전 추종을 완화 |
| orientation error cap | 정상 180, 한계 근처 12 deg | 큰 회전 요구의 한 단계 피드백 크기 완화 |

`PostureTask` 기준은 engage 때의 configuration으로 갱신된다. 항상 하나의
고정된 “인간 기본 자세”를 향하는 것은 아니다.
`prototype.py`의 proximal damping 0.25와 75 deg/s는 baseline용이다.
기본 virtual-center의 0.03과 0.08 rad/s 제한을 설명할 때 섞지 않는다.
`config/teleop.json`에는 옛 DLS/voxel 필드가 남아 있지만 현재 Mink task 값을
덮어쓰지 않는다. 기존 설정 계약과 런처 참조를 보존했으며 설정 통합은 하지 않았다.

## 7. 초록 목표와 팔이 별도로 움직이는 이유

`FeasibleTargetPlanner.Plan(current_q, goal)`은 현재 관절각에서 시작해 최대
3단계 QP를 예측한다. 후보가 좋아지는지 `GetMerit`으로 검사하고, 필요하면
단계 크기를 1, 1/2, 1/4 ... 1/32로 줄인다. 각 단계의 25/50/75/100% 지점에서
관절 범위와 충돌 여유를 확인한다.

- `next_q`: 검사를 통과한 첫 단계. 이번 프레임에 MuJoCo가 적용한다.
- `target_q`, `target_position`: 통과한 마지막 예측 자세와 wrist-yaw FK. 초록 표시용이다.
- 원래 손 목표는 따로 보존한다. 초록 목표가 사용자 입력을 대체하거나 기준점을 바꾸지 않는다.
- `local_limit`: 이 국소 탐색에서 더 나은 허용 단계를 못 찾았다는 뜻이다.
  사람 눈에 가능해 보여도 다른 경로까지 탐색한 결과가 아니므로 완전한 작업범위 판정이 아니다.
- 중간 샘플 검사는 연속 충돌 검증이나 실제 로봇의 동역학 안전 보장이 아니다.

따라서 “Mink가 못 따라온다”를 분석할 때는 입력, QP, backtracking, 충돌,
하드웨어 제한, 표시 출처를 나누어 봐야 한다. 최근 기록의 local-limit 정체는
정리 작업으로 해결했다고 주장하지 않는다.

## 8. PD 게인은 어느 단계에 있는가

오른팔 C++의 `Controller::write_cycle()`은 아래 식으로 예측 토크를 계산한다.

```text
tau_predicted = Kp * (q_target - q_measured)
                + Kd * (dq_target - dq_measured) + tau_feedforward
dq_target = 0  # 현재 이 C++ 출력의 설정
```

`Kp`는 Nm/rad, `Kd`는 Nm/(rad/s)로 해석한다. 내부 로봇 제어기의 전체 구현을
이 식만으로 검증한 것은 아니다. 예측 토크와 실측 토크는 구분한다.

`twist2_common.hpp`에서 오른팔 22~28의 `kKp=[40,40,40,40,20,20,20]`,
`kKd=[5,5,5,5,1,1,1]`이다. 기존 코드에서 임의로 설정한 값으로,
왼팔 코드와의 비교를 위해 그대로 사용한다. 최적화된 값은 아니며 추후 튜닝이 필요하다.

예: 어깨 Kp=40, 각도 오차 0.1 rad, 속도와 feedforward가 0이면 예측 위치
토크항은 4 Nm다. Kp를 올리면 같은 오차에서 토크가 커지고, Kd를 올리면 현재
속도를 억제하는 항이 커진다. 무조건 강할수록 좋은 값이 아니다.

키보드 `0.02 rad`는 목표 증분이고, `0.08 rad/s * 1..9`는 목표 이동률이다.
PD 게인이 아니다. 요청 목표와 최종 `motor.q()` 사이에는 속도·관절·예측 토크
제한이 있다. `predicted_torque`는 상태 기반 추정이며 실측 보증값이 아니다.
Arm SDK의 gain/weight는 다른 파일·프로필에서 구성되므로 위 값과 혼동하지 않는다.

## 9. 예상 질문과 답변 연습

| 질문 | 답변의 핵심 |
| --- | --- |
| Mink를 그대로 썼나? | QP/task/limit은 Mink. 가상 중심, 적응 cost, 예측/backtracking은 우리 코드다. |
| 왜 어깨가 움직이나? | 손목 목표에 여러 관절 해가 존재하고 비용을 함께 최소화한다. 손목만 움직이라는 등식 제약은 없다. |
| 왜 gain이 0.35인가? | 현재 채택한 추종 완화 값이다. 모든 조건에서 최적이라는 근거는 없다. |
| weight를 올리면 정확해지나? | 다른 목표와의 절충이 바뀐다. 충돌·속도·기구학적 한계는 없어지지 않는다. |
| 왜 정체되나? | 입력 유효성, 목표 오차, QP 결과, merit, 충돌 rejection, 상태 모드를 각각 확인한다. |
| 충돌을 100% 막나? | 등록 geom과 모델, 선형화와 이산 경로 검사 범위 안의 보호다. 실측·연속 안전 보장은 별도다. |
| 시뮬레이션 성공이면 실제도 성공인가? | 아니다. 모터 추종, PD, 통신 지연, 균형과 접촉을 실물에서 별도로 확인한다. |
| static stand도 Mink인가? | 아니다. 키보드 상체 목표와 TWIST2 하체 정책을 결합해 LowCmd를 보낸다. |
| 이미 VR이 static stand에 연결됐나? | 아니다. 소켓 입력 통합과 실제 부호/응답 확인은 다음 단계다. |

## 10. 공동 유지보수 기준

코드 주석에는 비직관적인 선택의 이유·단위·부작용만 1~2줄 남긴다.
수식, 튜닝 근거, 실패 사례는 이 문서에 둔다. 원본·최소 변형 C++는 변경하지 않는다.
한 함수를 설명할 때 아래 틀을 사용한다.

```text
함수명 / 호출자:
입력 (단위·좌표계·배열 순서):
계산과 제한:
출력 / 다음 수신자:
이 방식을 선택한 이유:
값을 바꾸면 생기는 영향:
검증한 범위 / 아직 검증하지 않은 범위:
```

Mink 자체를 추적할 순서: `FrameTask.compute_error/compute_jacobian`
-> `Task._weighted_residual` -> `build_ik` -> `qpsolvers.solve_problem`
-> `solve_ik`의 `delta_q / dt` 반환. 설치 위치는
`C:/Users/user/AppData/Local/Programs/Python/Python311/Lib/site-packages/mink/`다.
패키지 내부는 읽기만 하고 수정하지 않는다. 검토한 로컬 소스가 실행 기준이며
인터넷 최신 main과 설치 버전이 항상 같다고 가정하지 않는다.

## 11. 손을 움직인 한 주기를 따라가기

아래는 현재 기본 시뮬레이션 경로다. 하드웨어 명령이 자동으로 함께 발생하지 않는다.

| 순서 | 코드 | 다음 단계로 넘기는 것 |
| --- | --- | --- |
| 1 | `G1ExistingHandTargetBinder` | 추적 유효성, engage 기준의 손목 이동·회전 |
| 2 | `G1ExistingTargetUdpSender` | 위치 m, quaternion xyzw, session/sequence/command_state를 UDP 5005로 전송 |
| 3 | `MinkCommandStream.poll` -> `receive_available_commands` | 소켓에 쌓인 패킷을 읽고 최신 유효 명령 선택 |
| 4 | `parse_command_packet` / watchdog / runtime state | 형식·유효성·송신 순서·상태 전이를 검사한 입력 |
| 5 | virtual-center `main` | engage 때 저장한 입력/로봇 손목 기준으로 상대 목표 생성 |
| 6 | `FeasibleTargetPlanner.Plan` -> `mink.solve_ik` | 위치·회전·자세·이동 비용과 제한으로 후보 생성 |
| 7 | `Plan`의 중간 FK/충돌/merit 검사 | 이번 주기 `next_q`와 표시할 예측 위치 구분 |
| 8 | `configuration.update(next_q)` -> `mj_forward` | 시뮬레이션 자세와 손목 FK 갱신 |
| 9 | 공용 `_state_packet`과 송신 코드 | UDP 5006 상태 표시, UDP 5008 Gate 7 후보 |
| 10 | `G1RobotStateUdpReceiver` -> `G1UnityRightArmPreview` | 선택한 표시 모드의 관절값을 G1 모델에 반영 |

같은 위치처럼 보여도 **사용자 목표 / 검증된 예측 목표 / 현재 계산 손목 / 실제
측정 손목**은 다른 값이다. 변수명과 `state_source`를 함께 확인한다.
`FeasiblePlan.valid=True`만으로 목표 도달이라고 판단하지 않는다.

### 현재 UDP 5005의 좌표 계약

일반적인 Binder 연결 경로를 기준으로 다음처럼 나뉜다.

| 필드 | 송신 시 의미 | 수신 후 처리 |
| --- | --- | --- |
| `right.pos` | Sender의 `OperatorToRobot`을 거친 로봇 목표 좌표, m | engage 입력 위치와의 차이를 당시 로봇 손목 위치에 더함 |
| `right.rot` | `Inverse(OperatorHeading) * TrackedWristRotation`을 필터링한 quaternion xyzw | `operator_rotation_to_robot_matrix`로 로봇 축으로 변환한 뒤 engage 기준 상대 회전을 적용 |

따라서 패킷의 position과 rotation을 모두 동일한 변환이 끝난 값이라고
가정하면 안 된다. `MinkCommandStream` 자체는 이 축 변환을 하지 않는다.
`pos`는 손목 위치이며 점검 도구 끝점이 아니다. quaternion은 각도 4개가 아니라
회전을 표현하는 4성분이므로 degree/radian 값처럼 직접 더하지 않는다.

### 수정 위치 찾기

| 바꾸려는 동작 | 먼저 볼 곳 | 확인할 영향 |
| --- | --- | --- |
| engage/pinch 입력 | Binder와 Sender, 씬의 저장 필드 | 상대 기준 재설정, 해제 이유 보존 |
| 패킷 형식 | Sender, command_adapter, protocol | 기존 수신기/캡처 재생 호환성 |
| 회전 추종/손목 선호 | VirtualCenterOrientationTask, task cost 함수 | 위치·회전 절충, 한계 근처 움직임 |
| 관절 이동 속도 | virtual-center velocity limits | 시뮬레이션 속도만인지 물리 프로필도 대상인지 구분 |
| 몸통 충돌 | 공용 `_build_collision_pairs`, planner, Gate 7 검사 | 등록 geom, 최소거리, 이산 검사 간격 |
| 실제 출력 | gate7_live_arm_sdk와 선택된 config | 실측 watchdog, 제어권, 해제 동작 |
| Unity가 보여주는 자세 | Receiver, Preview, display mode | 계산값을 실측으로 오인하지 않는지 |

### 설정값을 읽는 순서

- Python 상수, JSON 로더, 함수 인자를 따라 실제 소비 지점을 확인한다.
  `config/teleop.json` 하나가 모든 Mink/물리 설정을 통제하는 구조는 아니다.
- Unity C# 필드의 초기값은 기본값이다. 씬/prefab의 직렬화 값이나 초기화 코드가
  덮어쓸 수 있으므로 런타임 값과 함께 확인한다.
- IK cost, IK gain, 모터 Kp/Kd, Arm SDK weight, 속도 제한은 서로 다른 역할이다.
  출처가 없는 튜닝값을 라이브러리의 공식 권장값으로 적지 않는다.
- 기존 C++의 최소 변경 비교는 유지한다. 이 경로의 설명은 원본을 늘리지 않고
  이 문서와 실험 폴더 README에 둔다.
