# G1 VR Bimanual Teleoperation

Quest 양손 추적, Unity, Mink/MuJoCo, Omni 입력, G1 LowState/카메라 관찰을 하나의 개발 프로젝트로 묶은 G1 텔레오퍼레이션 저장소다.

> 현재 기본 경로는 **양팔 14축 IK + Omni 관찰 + G1 LowState 표시 + 전면 카메라**다.
> 기본 통합 런처 `tools\START_G1_VR_TELEOP.bat`은 **모터 명령을 보내지 않는다**.
> 실제 G1 출력은 `hardware/g1_arm_bridge/`의 별도 승인·검증 경로다.

## 현재 기준

- Unity: `6000.5.4f1`
- Python: `3.11`
- 양팔 IK 계산: `60 Hz`
- 관찰 콘솔 표시: `100 Hz`
- 기본 양팔 UDP: `127.0.0.1:5020`
- 입력 schema: `g1.bimanual.unity.sim.v4`
- 입력 frame: `unity_display_world_v1`
- 제어 관절: 왼팔 7축 + 오른팔 7축 = 14축
- proximal velocity cap: `90 deg/s`
- wrist velocity cap: `180 deg/s`
- acceleration cap: `90 deg/s²`
- `IK_TRACKING_RATE_S = 1.0`
- PiP parent: G1 `RobotRoot`
- 최근 bimanual 회귀: `116/116 PASS`

## 기본 실행

새 PC라면 먼저 [G1_TELEOP_NEW_PC_SETUP.md](G1_TELEOP_NEW_PC_SETUP.md)를 따른다.

```powershell
.\tools\START_G1_VR_TELEOP.bat
```

이 런처는 프로젝트 Python 의존성을 확인하고, 이미 실행 중인 동일 worker는 재사용하며, 필요한 경우 `Unity_G1_VR`을 연다. Unity Play는 자동으로 켜지 않는다.

```powershell
# 시작 계획과 환경만 검사
.\tools\START_G1_VR_TELEOP.bat --check-only

# Unity를 열지 않고 관찰 worker만
.\tools\START_G1_VR_TELEOP.bat --no-unity
```

`--check-only`도 `--host auto` 사용 시 G1 후보 주소의 TCP 22 연결 가능성을 검사하므로 로봇 네트워크가 끊겨 있으면 그 단계에서 실패할 수 있다.

## 현재 데이터 흐름

```text
Quest left/right hand tracking
        |
        v
Unity 6000.5.4f1
G1BimanualSimulationSender
        | UDP 127.0.0.1:5020
        | schema g1.bimanual.unity.sim.v4
        | frame  unity_display_world_v1
        v
g1_bimanual_runtime.py
        |
        v
BimanualSimulation + Mink
left 7 DoF + right 7 DoF
        |
        +-- collision / boundary / return
        +-- 60 Hz IK observation
        `-- feedback to Unity

Omni Connect ws://127.0.0.1:32123
        `-- g1_omni_velocity_gateway.py --dry-run

G1 front camera (eth0)
        | SSH
        v
PC g1_camera_ssh.py
        | TCP 127.0.0.1:5011
        v
Unity PiP, parent = G1 RobotRoot
```

## 양팔 IK

현재 기본 상체 controller는 `MuJoCo_G1_Controller/scripts/g1_bimanual_*` 계열이다.

| 파일 | 역할 |
| --- | --- |
| `g1_bimanual_runtime.py` | MuJoCo 환경 guard와 runtime 진입 |
| `g1_bimanual_unity_sim.py` | UDP 5020 Unity 양손 입력, filtering, state machine |
| `g1_bimanual_sim.py` | 14축 simulation, collision/boundary guard, braking, return |
| `g1_bimanual_motion_policy.py` | 좌/우 ArmMotionPolicy, workspace projection, Mink task |
| `g1_bimanual_limits.py` | 90/180 deg/s, 90 deg/s², tracking rate 1.0 |
| `g1_bimanual_return.py` | staged safe return |

양쪽 wrist position/orientation은 각 팔의 `*_wrist_yaw_link` FrameTask로 푼다. 실제 QP는 양팔을 함께 풀며 inter-arm collision과 return 경계를 공유한다.

예전 `run_mink_g1_right_arm_*` 파일은 공통 모델/상수와 비교 reference로 일부 남아 있다. **현재 기본 실행 controller가 아니다.**

## 현재 tracking profile

`g1_bimanual_motion_policy.py`의 일반 tracking gain은 다음과 같다.

```python
self.wrist_task.gain = min(
    base.FRAME_GAIN, self.dt_s * IK_TRACKING_RATE_S)
```

60 Hz, rate 1.0에서 약 `0.01667`이다. 이전 Jacobian pseudo-inverse correction/rate heuristic은 production bimanual 경로에서 제거됐다.

## 입력 좌표계

현재 Unity scene은 양손의 absolute aligned world wrist pose를 보낸다.

```text
schema      = g1.bimanual.unity.sim.v4
input_frame = unity_display_world_v1
base_yaw    = Omni 초기 yaw 대비 변화량
```

Quest tracking space는 Play 시작 정렬 이후 고정되고, G1 root/MuJoCo base는 Omni yaw를 따른다. 예전 engage-relative `5005` single-arm 계약과 혼용하지 않는다.

상세 계약은 [docs/PROTOCOL.md](docs/PROTOCOL.md)와 [docs/OMNI_WORLD_UPPER_BODY_20260922.md](docs/OMNI_WORLD_UPPER_BODY_20260922.md)를 참고한다.

## 알려진 상체 제한

최근 실제 세션 분석에서 큰 wrist position residual의 상당 부분은 단순한 IK 속도 부족이 아니라 **사람의 world-space 손 위치와 G1 팔의 reachable workspace 차이**로 확인됐다.

- fixed rate `1.0` 적용 후 실제 체감 추종 속도는 크게 개선됐다.
- rate 또는 acceleration을 더 올리는 실험은 이득이 작았다.
- 큰 position error 상태에서 목표를 오래 고정해도 오차가 남는 구간이 있었다.
- orientation/posture/damping을 제거해도 일부 큰 residual이 사라지지 않았다.
- adaptive gain, permanent reach clamp, global workspace compression은 production에 적용하지 않았다.

따라서 현재 speed profile은 유지하고, 필요하면 이후 **human-to-G1 workspace retargeting**을 독립 문제로 다룬다.

## 카메라 PiP

PiP는 더 이상 `CenterEyeAnchor`를 따라가지 않는다.

```text
생성 시: 사용자 시야 앞 world pose 계산
이후 parent: G1 RobotRoot
```

따라서 사용자가 머리를 돌려도 PiP가 HMD를 따라 움직이지 않고 G1/Omni 기준을 유지한다.

## 포트 요약

| Port | 현재 용도 |
| ---: | --- |
| `5020/UDP` | Unity 양손 bimanual input/feedback loopback |
| `55071/UDP` | observation tap 내부 localhost copy |
| `5011/TCP` | G1 camera -> Unity PiP loopback |
| `32123/WebSocket` | Omni Connect localhost input |
| `5009/UDP` | read-only G1 state -> MuJoCo display |
| `5010/UDP` | measured/recorded G1 state -> Unity display |

`5005/5006`은 deprecated single-arm Unity-Mink 경로에 남아 있는 포트다. 현재 bilateral-only 운영에서는 직접 사용하지 않는다.

## 물리 G1 출력

기본 통합 런처는 motor publisher를 만들지 않는다.

`hardware/g1_arm_bridge/`에는 read-only LowState, Gate 5/6/7, Arm SDK 등 서로 다른 세대의 물리 안전 경로가 있다. **현재 지원 정책은 bilateral-only**이며, 소스에 남아 있는 오른팔 전용 trial/contract는 deprecated라 실행하지 않는다.

## 검증

현재 양팔 회귀는 `backend/tests/test_bimanual_*.py` 계열이며 최근 기준은 `116 tests PASS`다.

2026-09-28에는 외부 증거 묶음 `G1.zip`의 2026-09-23 실제 G1 session을 current `main`에서 다시 replay했다. 공식 `--mode report --replay --strict` 경로가 PASS했고, accepted input `7,836`, state row `46,570`, input/state/reason mismatch `0`, 최대 14-joint `q` 차이는 `2.000621890374532e-13 rad`였다. raw source hash 경고는 `g1_bimanual_limits.py`와 `g1_bimanual_unity_sim.py`의 newline 차이였고 normalized content는 snapshot과 동일했다.

```powershell
.venv-teleop\Scripts\python.exe backend\tools\build_code_index.py --check
```

## 문서

1. [docs/CHAT_HANDOFF.md](docs/CHAT_HANDOFF.md) — 현재 상태와 다음 작업
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 현재 시스템 구조
3. [docs/CODE_GUIDE.md](docs/CODE_GUIDE.md) — 현재 코드 경로
4. [docs/PROTOCOL.md](docs/PROTOCOL.md) — bimanual/world-frame 통신 계약
5. [docs/OMNI_WORLD_UPPER_BODY_20260922.md](docs/OMNI_WORLD_UPPER_BODY_20260922.md) — Omni/world upper-body 기준
6. [docs/PORTABLE_TELEOP_SETUP.md](docs/PORTABLE_TELEOP_SETUP.md) — 다른 PC 설치/실행

과거 validation/review 산출물은 저장소에서 정리했다. 필요한 과거 내용은 Git history에서 확인한다.
