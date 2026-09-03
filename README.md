# G1 VR Teleoperation

처음 읽는 순서: [코드 연결·주요 함수·Mink 해설](docs/CODE_GUIDE.md)
 -> [파일 색인과 검토 범위](docs/CODE_INDEX.md).
 [미사용 코드 정리 기록](docs/CLEANUP_20260903.md)은 변경 이력이다.

VR 오른손 hand tracking을 Unity에서 수집하고, Mink + MuJoCo 기반 differential QP IK로 Unitree G1 오른팔 7DoF를 제어하는 텔레오퍼레이션 프로젝트다.

> **현재 구조:** Unity/VR ↔ Mink/MuJoCo 시뮬레이션, Gate 7의 `rt/arm_sdk` 물리 출력, 기존 TWIST2 C++의 `rt/lowcmd` 수동 제어가 별도 경로로 있다. 기본 실행기는 시뮬레이션이며 물리 출력은 별도 설정과 검사로 제어한다. TWIST2 오른팔 코드에는 아직 VR/Mink 입력을 통합하지 않았다. 시험 결과와 남은 문제는 [CHAT_HANDOFF](docs/CHAT_HANDOFF.md)의 최신 항목을 참고한다.

## 현재 시스템

```text
VR headset
    │ right-hand pose
    ▼
Unity 6.5 / Meta XR
    │ UDP 5005: hand target
    ▼
Mink + MuJoCo + DAQP
    │ G1 right-arm 7DoF differential QP IK
    ├─ UDP 5006: 29-joint robot state → Unity
    └─ UDP 5008: Gate 7 candidate (dry-run or separate hardware relay)

Hardware read-only paths:
G1 rt/lowstate + rt/odommodestate → WSL2 Unitree SDK2/DDS
                                      ├→ UDP 5007 → Windows initial sync/Gate 5
                                      └→ UDP 5009 → live MuJoCo joint/base mirror
                                                        └→ UDP 5010 → Unity hardware preview
Saved 29-joint JSON ──────────────────→ UDP 5009 → offline MuJoCo replay
                                                        └→ UDP 5010 → Unity hardware preview

Gate 6 prepared path (hardware output locked):
G1 rt/lowstate → dual-arm HOLD contract → [authorization gate] → rt/arm_sdk

Gate 7 offline candidate path (hardware output locked):
UDP 5008 Mink state → watchdog/safety → right-arm tracking candidate
                                      ├→ intentional pinch → immediate Regular dual-arm return
                                      └→ unintended loss → HOLD 10 s → Regular dual-arm return

Gate 7 separate physical path:
UDP 5008 → Windows validated relay → WSL UDP 5013
                                      → live adapter + direct rt/lowstate → rt/arm_sdk
                                      └→ actual joint state UDP 5010 → Unity
```

### 통신 포트

빠른 암기용 한 장 요약은 [`docs/NETWORK_QUICK_REFERENCE.md`](docs/NETWORK_QUICK_REFERENCE.md)를 참고한다.

| Port | 방향 | 용도 |
| ---: | --- | --- |
| `5005` | Unity → Mink | VR 오른손 position/orientation target |
| `5006` | Mink → Unity | G1 29관절 pose + 오른팔 wrist/control state |
| `5007` | WSL/G1 → Windows | 실제 G1 LowState 초기 동기화용 telemetry |
| `5008` | Mink → locked Gate 7 | 원본 해제 원인과 최소 충돌 여유가 포함된 Arm SDK 후보 입력 |
| `5009` | WSL/G1 → MuJoCo | 실제 G1 29관절과 첫 sample 기준 상대 base pose의 실시간 읽기 전용 표시 |
| `5010` | LowState viewer → Unity | 실제/저장 29관절 및 선택적 상대 base pose의 읽기 전용 Unity 표시 |
| `5011` | WSL camera bridge → Unity | G1 `VideoClient`가 반환한 JPEG의 로컬 TCP PiP 표시 |
| `5012` | Gate 7 모의 피드백 → Mink/MuJoCo | 오프라인 HOLD·복귀 결과 반영용 UDP |
| `5013` | Windows relay → WSL Gate 7 | 검증·축약된 관절 후보 UDP, 실측 상태가 아님 |

Unity의 `5006` 수신기는 Mink 제어·안전 피드백 전용이고, `5010` 수신기는 실제
G1 또는 저장 LowState의 전신 **표시 전용**이다. 실제 상태를 `5006`에 섞지
않으므로 workspace/collision 판정의 피드백 출처는 바뀌지 않는다. Unity 전신
프리뷰는 `logs/runtime/unity_display_mode.json`에서 선택한 simulation/hardware/recorded
모드에 맞는 상태만 표시한다. hardware 모드에서 실측이 끊겨도 simulation으로
자동 대체하지 않는다. Gate 7 live adapter는 직접 읽은 실측을 `5010`으로 보낼 수도 있다.

`5011`은 위 UDP 상태 경로와 별개인 카메라 전용 TCP 포트다. G1 카메라는
Unitree SDK2/CycloneDDS `videohub` API로 읽고, WSL 브리지가 완전한 JPEG만
`127.0.0.1:5011`로 전달한다. 영상 상태는 engagement나 로봇 명령을 바꾸지 않는다.

G1을 연결할 수 없을 때는 다음 런처로 저장 자세를 동일한 UDP `5009` 수신
경로에 재생할 수 있다. Unity가 Play 상태이면 같은 자세가 UDP `5010`을 통해
Unity 공식 G1 모델에도 표시된다. SDK2, DDS, WSL, Ethernet 및 로봇 명령을
사용하지 않는다.

```powershell
.\tools\VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat
```

재생 데이터가 실제 캡처인지 검증용 자세인지는 실행 시 선택된 파일과 출처를
확인한다. 저장 자세 재생은 실시간 실측과 구분한다.

## 현재 IK

현재 기본 IK는 **Virtual-Wrist-Center Role-Separated Differential QP IK**다.

```text
Translation objective : right_wrist_roll_link
Orientation objective : right_wrist_yaw_link
External Unity frame  : right_wrist_yaw_link
Solver formulation    : Mink differential QP
QP backend             : DAQP preferred
Controlled joints      : right arm 7DoF only
Other G1 DOFs          : frozen
```

핵심 아이디어는 wrist pitch/roll 회전 때문에 `right_wrist_yaw_link` 위치가 변하고 shoulder/elbow가 불필요하게 보정하는 coupling을 줄이기 위해, **내부 위치 task만 upstream인 `right_wrist_roll_link`에 두는 것**이다. 회전과 Unity 외부 frame 계약은 계속 `right_wrist_yaw_link`를 사용한다.

회전 task는 원래 FrameTask의 Jacobian을 유지한다. 어깨·팔꿈치 열을 0으로
만들지 않으며, 손목 사용 선호는 자세 비용으로 유도한다. 손목 관절 한계 근처에서는
히스테리시스에 따라 회전 비용과 오차 상한을 완화한다. 항상 사람과 동일한 팔꿈치
자세가 선택된다는 뜻은 아니다.

상세 구현과 QP 수식은 [`MuJoCo_G1_Controller/README.md`](MuJoCo_G1_Controller/README.md)를 참고한다.

## G1 오른팔 Joint 순서

| 순서 | Hardware index | Joint |
| ---: | ---: | --- |
| 0 | 22 | `right_shoulder_pitch_joint` |
| 1 | 23 | `right_shoulder_roll_joint` |
| 2 | 24 | `right_shoulder_yaw_joint` |
| 3 | 25 | `right_elbow_joint` |
| 4 | 26 | `right_wrist_roll_joint` |
| 5 | 27 | `right_wrist_pitch_joint` |
| 6 | 28 | `right_wrist_yaw_joint` |

## 실행

### 기본 통합 런처

```powershell
.\START_VR_HAND_TO_MUJOCO.bat
```

이 런처는 현재 기본 정책인 `run_mink_g1_right_arm_virtual_center_live.py`를 실행한다. 환경 점검만 하려면:

```powershell
.\START_VR_HAND_TO_MUJOCO.bat --check
```

실제 G1 명령 없이 Unity→Mink→Gate 7→35-slot Arm SDK 후보까지 실시간으로
검증하려면 다음 런처를 사용한다.

```powershell
.\tools\START_G1_GATE7_LIVE_DRY_RUN.bat
```

Bounded physical interactive right-arm experiment (requires connected G1,
fresh precheck and explicit operator confirmation):

```powershell
.\tools\START_G1_RIGHT_ARM_JOG_MUJOCO.bat
```

During one run, keys `1..7` select one active right-arm joint at a time
(hardware indices 22..28). Up/Down changes its target in 1-degree steps. The
shoulder/elbow rate is limited to 2.5 deg/s and wrist rate to 5 deg/s; a new
step is ignored if its candidate target would lead the measured joint by more
than 2 degrees. The Jog-only Arm SDK weight is capped at 0.25. Before publisher
creation, MuJoCo scans outward in 1-degree
steps and derives a separate negative/positive safe range for every joint inside
the configured +/-20-degree cap. Switching joints first returns the previous
joint to the precheck pose. The remaining dual-arm targets are seeded from
LowState, all non-arm gains stay zero, and the actual 29-joint LowState is
mirrored into MuJoCo.

Before the first `1..7` selection, published hold frames keep Arm SDK weight at
zero. The selected joint is revalidated against the permit pose, then the
0-to-0.25 ramp and 30-second active timer begin. No selection for 15 seconds
ends the run without acquiring arm authority.

별도 Gate 7 창은 UDP 5008을 받아 상태·거부 이유·양팔 후보를 JSONL로 기록한다.
Ctrl+C로 종료하면 정확한 이벤트 로그와 결과 JSON 경로를 표시한다. 이 프로세스는
Unitree SDK와 DDS publisher를 만들지 않는다.

Gate 7 후보는 localhost UDP `5012`를 통해 같은 MuJoCo 창에 시뮬레이션으로만
되돌아간다. 따라서 G1 없이도 연동 해제 후 10초 HOLD와 Regular 양팔 복귀를
눈으로 확인할 수 있다. 실제 로봇 명령은 계속 잠겨 있다.

### Baseline 비교 실행

```powershell
.\START_VR_HAND_TO_MUJOCO.bat --baseline
```

이 옵션을 명시한 경우에만 비교용 기준 제어기인:

```text
MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py
```

를 실행한다. 옵션이 없으면 virtual-center가 기본이다.

## 핵심 코드 경로

| 경로 | 역할 |
| --- | --- |
| `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py` | 최신 virtual-center IK 정책 |
| `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py` | Mink QP, UDP, collision 등 공통 기반 |
| `MuJoCo_G1_Controller/scripts/g1_right_arm_common.py` | G1 model/joint/frame/좌표계 공통 정의 |
| `Unity_G1_VR/Assets/G1Teleop/` | VR wrist target, engagement, UDP, G1 preview |
| `hardware/g1_arm_bridge/` | 실제 G1 LowState, pose sync, safety gate, dry-run |
| `hardware/g1_arm_bridge/gate6_arm_sdk_hold.py` | 잠긴 Gate 6 양팔 HOLD / `rt/arm_sdk` 경계 |
| `hardware/g1_arm_bridge/arm_sdk_teleop_contract.py` | Gate 7 watchdog, 10초 안전 HOLD, Regular 복귀, Arm SDK 후보 계약 |
| `hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py` | publisher 없는 Gate 7 collision/trajectory 통합 검증 |
| `hardware/g1_arm_bridge/gate7_live_dry_run.py` | UDP 5008 실시간 Gate 7 후보 및 JSONL 로그, 물리 출력 없음 |
| `tools/` | 실행/회귀/진단용 BAT |

## Collision avoidance

Self-collision 회피는 별도 사후처리가 아니라 Mink QP의 inequality constraint인 `CollisionAvoidanceLimit`으로 들어간다.

현재 주요 값:

```text
minimum clearance   = 12 mm
detection distance  = 40 mm
collision gain      = 0.85
```

MuJoCo collision geometry 사이 거리를 사용하며, 오른팔과 다른 robot geom 사이 pair를 구성하되 구조적으로 바로 붙어 있는 neighbor link는 제외한다.

오프라인 진단에서 큰 positive wrist yaw에서 `right_rubber_hand`와 `right_hip_roll_link`가 실제로 관통하는 것을 확인했다. 따라서 해당 영역에서 collision avoidance 때문에 shoulder/elbow가 움직이는 것은 정상적인 안전 동작이다.

## Offline IK 검증

VR을 매번 켜지 않고 Python + MuJoCo + Mink만으로 회귀 테스트한다.

현재 유지하는 대표 검증 도구:

```powershell
.\tools\TEST_MINK_WRIST_FRAME.bat
.\tools\TEST_G1_MINK_FK_PARITY.bat
.\tools\TEST_MINK_SAFETY_PIPELINE.bat
.\tools\TEST_G1_STARTUP_RECOVERY_OFFLINE.bat
```

여러 합성 초기 자세에서 Startup Recovery 성공 범위를 표본 지도 형태로 확인하려면:

```powershell
.\experiments\startup_recovery_posture_sweep\RUN_POSTURE_SWEEP.bat
```

기본 지도는 캡처 자세를 중심으로 어깨 roll과 팔꿈치를 각각 `-15, 0, +15도`로
변경한 9개 자세를 검사한다. 결과는
`logs/experiments/startup_recovery_posture_sweep/latest_map.html`에 저장된다.
초록 셀은 검사한 정확한 자세가 통과했다는 의미이며 셀 사이의 연속 영역까지
안전하다는 의미는 아니다.

자세한 도구 분류는 [`tools/README.md`](tools/README.md)를 참고한다.

## Unity

Unity 프로젝트:

```text
Unity_G1_VR/
```

현재 기준:

- Unity `6000.5.4f1`
- Meta XR SDK `205.x`
- VR wrist position source와 anatomical orientation을 분리해 사용
- cyan = VR wrist
- green = Mink target
- magenta = Unity-replayed G1 `right_wrist_yaw_link`
- Unity/MuJoCo wrist-yaw FK parity 검증 통과

자세한 내용은 [`Unity_G1_VR/README.md`](Unity_G1_VR/README.md)를 참고한다.

## 실제 G1 Hardware 상태

실제 하드웨어 경로는 fail-closed 순서로 준비 중이다.

```text
READ ONLY → STARTUP PRECHECK → INITIAL SYNC → SAFETY DRY RUN → HOLD → TELEOP
```

현재 구현된 것은 LowState read-only, Regular Mode startup precheck, pose
synchronization, safety gate, Gate 6 양팔 measured-pose HOLD 계약과 분리된
`rt/arm_sdk` publisher 경계까지다. 실제 출력은
`config/g1_gate6_hold.json`의 `hardware_output_authorized=false`로 잠겨 있다.
연결된 G1에서 읽기 전용 Gate 6 준비 검사는 `HOLD_READY`를 반환했지만 실제
출력은 별도의 1회용 승인 설정에서만 수행했다. 첫 measured-pose HOLD는
`2275`프레임 후 weight `0`, publisher 없음, fault 없음으로 종료됐다.
이 결과는 매달린 상태에서 얻은 읽기 전용 통신/계약 검증이므로, 지상 자립
Regular Mode의 실제 출력 승인은 아니다. 물리 출력에는 별도 지상 자립 확인이
필수다.
Gate 7에서는 UDP 5008의 strict Mink state와 원본 해제 원인을 검사한다.
사용자가 의도적으로 pinch 해제하면 즉시, ACTIVE 이후 추적 손실·packet stale·
workspace exit·충돌 제한이 10초간 지속되면 저장된 Regular 양팔 자세로 돌아가는
minimum-jerk 후보를 만든다. 10초 안에 정상 입력이 돌아오면 타이머를 취소한다.
이 경로 역시
`hardware_output_authorized=false`이며 실제 G1에 전송되지 않는다.
현재 자세가 모드·정지·관절·충돌 검사를 모두 통과하면 Startup Recovery를
조건부로 생략하고, 그렇지 않으면 기존 Recovery를 유지한다. 하드웨어 단계는
[`hardware/g1_arm_bridge/README.md`](hardware/g1_arm_bridge/README.md)와
`HARDWARE_BRINGUP_CHECKLIST.md`를 따른다.

## 저장소 구조

```text
.
├─ Unity_G1_VR/               # VR / Unity frontend
├─ MuJoCo_G1_Controller/      # Mink + MuJoCo IK controller
├─ backend/                   # shared Python utilities
├─ config/                    # runtime/calibration config
├─ docs/                      # architecture/protocol/camera docs
├─ hardware/g1_arm_bridge/    # physical G1 safety boundary
├─ tools/                     # launch/test/diagnostic scripts
├─ START_VR_HAND_TO_MUJOCO.bat
└─ README.md
```

## README 구성

- [`README.md`](README.md): 전체 프로젝트와 현재 상태
- [`MuJoCo_G1_Controller/README.md`](MuJoCo_G1_Controller/README.md): IK/QP/MuJoCo 상세
- [`Unity_G1_VR/README.md`](Unity_G1_VR/README.md): VR/Unity/frame/marker 상세
- [`hardware/g1_arm_bridge/README.md`](hardware/g1_arm_bridge/README.md): 실제 G1 안전 bring-up
- [`tools/README.md`](tools/README.md): 실행 및 진단 도구

`MuJoCo_G1_Controller/external/` 등 외부 코드에 포함된 README/라이선스 문서는 upstream 자료이므로 프로젝트 README 재정리 대상에서 제외한다.
