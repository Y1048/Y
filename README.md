# G1 VR Teleoperation

VR 오른손 hand tracking을 Unity에서 수집하고, Mink + MuJoCo 기반 differential QP IK로 Unitree G1 오른팔 7DoF를 제어하는 텔레오퍼레이션 프로젝트다.

> **현재 상태:** Unity/VR ↔ Mink/MuJoCo 텔레오퍼레이션과 하드웨어 안전 dry-run 경로를 개발 중이다. **실제 G1 모터에 명령을 보내는 Unitree command publisher는 아직 구현/활성화하지 않았다.**

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
    ├─ UDP 5006: robot state → Unity
    └─ UDP 5008: safety dry-run mirror

Future hardware path:
G1 rt/lowstate → WSL2 Unitree SDK2/DDS → UDP 5007 → Windows teleop
```

### UDP 포트

| Port | 방향 | 용도 |
| ---: | --- | --- |
| `5005` | Unity → Mink | VR 오른손 position/orientation target |
| `5006` | Mink → Unity | G1 오른팔 joint/wrist state |
| `5007` | WSL/G1 → Windows | 실제 G1 LowState 초기 동기화용 telemetry |
| `5008` | Mink → Safety dry-run | 하드웨어 safety pipeline 검증 |

## 현재 IK

현재 실험 중인 IK는 **Virtual-Wrist-Center Role-Separated Differential QP IK**다.

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

평상시 orientation task에서 shoulder 3축 + elbow의 Jacobian contribution은 `0%`이며 wrist가 관절 한계에 가까워질 때만 hysteresis 기반 proximal assist를 허용한다.

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

이 런처는 현재 안정 기준인 `run_mink_g1_right_arm_prototype.py`를 실행한다. 환경 점검만 하려면:

```powershell
.\START_VR_HAND_TO_MUJOCO.bat --check
```

### 현재 Virtual-Center smooth 실험본

```powershell
.\START_VR_HAND_TO_MUJOCO.bat --smooth
```

이 런처가 현재 최신 IK 정책인:

```text
MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py
```

를 실행한다. 별도 BAT를 늘리지 않고 메인 런처 옵션으로 두 실행 경로를 구분한다.

## 핵심 코드 경로

| 경로 | 역할 |
| --- | --- |
| `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py` | 최신 virtual-center IK 정책 |
| `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py` | Mink QP, UDP, collision 등 공통 기반 |
| `MuJoCo_G1_Controller/scripts/g1_right_arm_common.py` | G1 model/joint/frame/좌표계 공통 정의 |
| `Unity_G1_VR/Assets/G1Teleop/` | VR wrist target, engagement, UDP, G1 preview |
| `hardware/g1_arm_bridge/` | 실제 G1 LowState, pose sync, safety gate, dry-run |
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

대표 도구:

```powershell
.\tools\TEST_MINK_ROLE_SPLIT_REGRESSION.bat
.\tools\TEST_MINK_VIRTUAL_WRIST_CENTER_COMPARE.bat
.\tools\TEST_MINK_VIRTUAL_WRIST_CENTER_SWEEP.bat
.\tools\TEST_MINK_BASELINE_COLLISIONS.bat
.\tools\TEST_MINK_COLLISION_INFLUENCE.bat
.\tools\TEST_MINK_VIRTUAL_CENTER_COLLISION_INFLUENCE.bat
.\tools\TEST_MINK_VIRTUAL_CENTER_YAW_COLLISION_GEOMETRY.bat
.\tools\TEST_G1_MINK_FK_PARITY.bat
```

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
READ ONLY → INITIAL SYNC → SAFETY DRY RUN → HOLD → TELEOP
```

현재 구현된 것은 LowState read-only, pose synchronization, safety gate와 dry-run까지이며 **실제 command publisher는 없다.** 하드웨어 단계는 [`hardware/g1_arm_bridge/README.md`](hardware/g1_arm_bridge/README.md)와 `HARDWARE_BRINGUP_CHECKLIST.md`를 따른다.

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
