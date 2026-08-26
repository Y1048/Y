# G1 Right-Arm Hardware Bridge

이 폴더는 Windows의 Mink teleoperation controller와 실제 Unitree G1 사이의 **하드웨어 안전 경계**다.

> **현재 상태:** 실제 G1 command publisher는 아직 구현/활성화하지 않았다. 현재 코드는 LowState read-only, 초기 pose sync, Safety Gate, HOLD/Mink dry-run 검증 단계까지다.

실기 절차는 반드시 [`HARDWARE_BRINGUP_CHECKLIST.md`](HARDWARE_BRINGUP_CHECKLIST.md)를 따른다.

## 목표 구조

```text
Windows
Quest / Unity / Mink / MuJoCo
          │
          │ target + state validation
          ▼
WSL2 Linux
Unitree SDK2 / DDS bridge
          │ Ethernet
          ▼
Physical G1
```

실제 G1 DDS는 Linux 환경에서 처리하고 Windows teleoperation과 필요한 state를 UDP로 연결하는 구조를 준비하고 있다.

## 오른팔 Joint mapping

| Hardware index | Joint |
| ---: | --- |
| 22 | `right_shoulder_pitch_joint` |
| 23 | `right_shoulder_roll_joint` |
| 24 | `right_shoulder_yaw_joint` |
| 25 | `right_elbow_joint` |
| 26 | `right_wrist_roll_joint` |
| 27 | `right_wrist_pitch_joint` |
| 28 | `right_wrist_yaw_joint` |

## 1. Read-only LowState

```text
read_only_lowstate.py
```

이 프로세스는 의도적으로 command를 보낼 수 없게 유지한다.

- Unitree DDS `rt/lowstate` subscribe
- DDS publisher 없음
- right-arm 7 joints 측정
- position / velocity / estimated torque 확인
- stale LowState fault 처리
- 필요 시 Windows로 UDP 5007 telemetry forward

예상 사용:

```bash
python3 hardware/g1_arm_bridge/read_only_lowstate.py eth0
```

실제 G1이 연결된 interface 이름으로 `eth0`를 바꾼다.

## 2. Hardware initial pose sync

실제 G1을 command하기 전에 Mink/Unity의 초기 자세를 실측 G1 pose와 맞춘다.

WSL/Linux:

```bash
python3 hardware/g1_arm_bridge/read_only_lowstate.py eth0 --forward-host <WINDOWS_IP>
```

Windows:

```powershell
.\tools\ALLOW_G1_LOWSTATE_TO_WINDOWS.bat
.\tools\START_MINK_G1_HARDWARE_SYNC.bat
```

흐름:

```text
G1 rt/lowstate
→ read_only_lowstate.py
→ UDP 5007
→ receive_initial_state.py
→ logs/runtime/g1_hardware_initial_state.json
→ Mink initial q
→ UDP 5006
→ Unity G1 preview
```

이 단계에서도 G1 command output은 없다.

`verify_initial_pose_sync.py`는 viewer나 DDS publisher를 만들지 않고,
캡처한 7개 관절값이 현재 Mink 모델과 Unity state packet까지 그대로
유지되는지 검사한다.

## 3. Safety Gate

```text
safety_gate.py
```

Safety Gate는 DDS와 독립적인 pure-Python fail-closed 검사기다.

현재 주요 조건:

```text
LowState stale threshold        : 250 ms
right-arm target length         : exactly 7
all joint values                : finite only
joint-limit inward margin       : 2°
elbow operational range         : 5°..120° before margin
max measured-target difference  : 10°
initial command rate limit       : 15°/s
failure                         : command_q_rad = None
```

즉 검사 하나라도 실패하면 command vector를 반환하지 않는다.

Offline test:

```powershell
.\tools\TEST_G1_HARDWARE_SAFETY_GATE.bat
```

## 4. Runtime hardware state

```text
hardware_state.py
```

bring-up 상태를 명시적인 phase로 기록한다.

```text
OFFLINE
READ_ONLY_WAIT
READ_ONLY_ACTIVE
SYNCED
HOLD_READY
HOLD_ACTIVE
TELEOP_READY
TELEOP_ACTIVE
FAULT
```

Read-only 단계에서는 항상:

```text
publisher_present = false
command_output_enabled = false
```

여야 한다.

Test:

```powershell
.\tools\TEST_G1_HARDWARE_STATE.bat
```

## 5. Dry-run 경로

실제 publisher 없이 command pipeline의 판단만 검증한다.

주요 파일:

```text
hold_dry_run.py
mink_target_dry_run.py
generate_fake_mink_targets.py
test_fake_mink_safety_e2e.py
test_mink_safety_pipeline.py
```

대표 도구:

```powershell
.\tools\START_MINK_G1_SAFETY_DRY_RUN.bat
.\tools\TEST_FAKE_MINK_SAFETY_E2E.bat
```

현재까지 HOLD dry-run과 synthetic Mink target safety pipeline을 command publisher 없이 검증했다.

### 실제 rest pose에서 startup recovery 검증

```powershell
.\tools\TEST_G1_STARTUP_RECOVERY_OFFLINE.bat
```

이 검사는 캡처된 실제 G1 관절값으로 Mink를 초기화한 뒤 다음 상태를
오프라인으로 재현한다.

```text
REST_HOLD
→ Cartesian escape_body
→ initial proximity group clears 40 mm
→ escape_brake_hold
→ transition_to_ready
→ ready_brake_hold
→ ready_fine_positioning
→ TELEOP_READY 후보
```

QP가 제안한 각 스텝은 startup 전용 0.001도 swept-path 검사로 확인한다.
초기 proximity group 밖의 새 body pair가 12 mm 안으로 들어오거나,
40 mm recovery latch 이후 어떤 pair가 12 mm 안으로 재진입하면 중단한다.
결과는 `logs/runtime/g1_startup_mink_recovery.json`에 기록된다.

현재 캡처 자세에 대한 500 Hz dry-run은 속도 8 deg/s, 가속도 30 deg/s^2,
jerk 300 deg/s^3 제한과 독립 replay를 통과했다. 이 수치는 아직 실제 G1
승인 기준이 아니므로 결과의 `hardware_ready`는 `false`이며 실제
publisher나 command output은 없다.

## Mink → Safety mirror

Windows Mink controller는 하드웨어 safety dry-run 검증을 위해 robot state/target 정보를 UDP `5008`에도 mirror할 수 있다.

```text
Mink
 ├─ UDP 5006 → Unity
 └─ UDP 5008 → Safety dry-run
```

## 실제 command 단계 전 필수 순서

```text
1. WSL/Unitree SDK2 정상화
2. 실제 G1 Ethernet/DDS 연결
3. rt/lowstate read-only 검증
4. joint index / sign / range 검증
5. measured pose → Mink/Unity 초기 sync
6. 실제 LowState 기반 Safety Gate dry-run
7. q_target = q_measured HOLD dry-run
8. 별도 command publisher 구현 및 검토
9. 제한된 HOLD 실기
10. 그 이후에만 Mink target 연결
```

이 순서를 건너뛰지 않는다.

## Command publisher 정책

현재 repository에는 실제 모터 command publisher가 없다.

향후 publisher를 추가할 때도:

- `read_only_lowstate.py`에 publisher를 추가하지 않는다.
- command publisher는 별도 프로세스로 만든다.
- Safety Gate가 `allowed=True`와 유효 `command_q_rad`를 반환한 경우만 사용한다.
- stale state/fault 시 fail closed한다.
- acquire/release lifecycle을 명시적으로 관리한다.

Unitree arm control topic/SDK 경로는 실제 read-only bring-up을 통과한 뒤 확정한다.

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| `read_only_lowstate.py` | G1 DDS LowState read-only |
| `receive_initial_state.py` | UDP 5007 초기 pose 수신 |
| `verify_initial_pose_sync.py` | G1 pose → Mink → Unity packet 일치 검사 |
| `safety_gate.py` | fail-closed target safety validation |
| `hardware_state.py` | phase/fault schema |
| `hold_dry_run.py` | measured pose HOLD 검증 |
| `mink_target_dry_run.py` | Mink target safety dry-run |
| `simulate_startup_recovery.py` | measured rest-to-ready Mink QP offline recovery |
| `HARDWARE_BRINGUP_CHECKLIST.md` | 실제 하드웨어 단계별 체크리스트 |

## 금지 사항

실제 G1 연결 전에는 다음을 임의로 하지 않는다.

```text
- read-only 파일에 publisher 추가
- Safety Gate 우회
- 초기 measured pose sync 없이 target 전송
- 큰 joint step으로 첫 command 전송
- simulation에서 통과했다는 이유만으로 real command 활성화
```
