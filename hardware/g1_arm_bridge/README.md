# G1 Right-Arm Hardware Bridge

이 폴더는 Windows의 Mink teleoperation controller와 실제 Unitree G1 사이의 **하드웨어 안전 경계**다.

> **현재 상태:** 실제 G1 command publisher는 아직 구현/활성화하지 않았다. 현재 코드는 LowState read-only, 초기 pose sync, Safety Gate, HOLD/Mink dry-run, 실제 LowState 기반 Gate 5 read-only 모니터 단계까지다. Gate 5 구현은 오프라인 검증을 통과했지만 실제 G1 세션 검증은 아직 남아 있다.

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
→ contact_release_and_recovery (12 mm hard release + posture 동시 실행)
→ clearance_assist_and_recovery (20 mm까지 escape 보조 + posture 동시 실행)
→ transition_to_ready
→ terminal_ready_blend (현재 q/v/a에서 목표 q, v=0, a=0으로 연결)
→ TELEOP_READY 후보
```

QP가 제안한 각 스텝은 startup 전용 0.001도 swept-path 검사로 확인한다.
시작할 때 이미 12 mm 안에 있던 body pair만 접촉 해소 중 예외로 허용한다.
해당 pair가 12 mm를 확보한 뒤에는 어떤 pair도 12 mm 안으로 재진입할 수 없다.
Cartesian escape 목표는 준비자세 posture 목표와 처음부터 동시에 실행하며,
초기 접촉 쌍이 20 mm를 확보하면 중간 정지 없이 escape 목표만 제거한다.
준비자세 오차가 5도 이내가 되면 QP의 현재 위치·속도·가속도를 시작조건으로
사용하는 5차 종단 궤적으로 전환한다. 후보 궤적은 0.05초 단위로 길이를 늘려가며
관절범위, 속도·가속도·jerk, 0.001도 swept-path 검사를 모두 통과해야 채택된다.
결과는 `logs/runtime/g1_startup_mink_recovery.json`에 기록된다.

검증된 최신 경로를 실제 G1과 연결하지 않고 MuJoCo Viewer에서 설정된 속도로
확인하려면 다음을 실행한다.

```powershell
.\tools\VIEW_G1_STARTUP_RECOVERY.bat
```

Viewer는 저장된 관절 경로만 재생하며 Unitree SDK, DDS, UDP, command publisher를
사용하지 않는다.

준비자세와 Viewer 재생 속도는 `config/startup_recovery.json`에서 변경한다.
준비자세 변경 후에는 반드시 `TEST_G1_STARTUP_RECOVERY_OFFLINE.bat`을 다시
실행해 새 경로가 통과한 뒤 Viewer를 실행한다. Viewer 속도는 시각 재생에만
영향을 주며 실제 회복 경로의 속도·가속도·jerk 제한을 바꾸지 않는다.

JSON 값을 직접 수정하는 대신 MuJoCo에서 관절을 하나씩 보며 준비자세를 만들려면
다음을 실행한다.

```powershell
.\tools\EDIT_G1_STARTUP_READY_POSE.bat
```

| 키 | 기능 |
|---|---|
| `1`~`7`, `↑/↓` | 오른팔 관절 선택 |
| `←/→`, `A/D` | 선택 관절 각도 감소/증가 |
| `,/.` | 증감 단위 축소/확대 (`0.1`, `0.5`, `1`, `2`, `5`도) |
| `Z` | 선택 관절을 0도 쪽으로 이동; 안전 범위에서 자동 제한 |
| `R` | 마지막으로 저장된 자세 복원 |
| `V` | 7관절 값과 정적 검사 결과 출력 |
| `S` | 정적 검사를 통과한 자세를 JSON에 저장 |
| `Q` 또는 `Esc` | 종료 |

MuJoCo의 작은 구는 현재 선택한 관절을 표시한다. 노란색은 저장 가능한 정적
자세, 빨간색은 관절 범위 또는 12 mm 충돌 여유 위반, 저장 직후 초록색은 저장
완료를 뜻한다. 저장 전 설정은
`logs/runtime/startup_ready_pose_previous.json`에 한 단계 백업된다.

편집기의 검사는 한 자세만 검사한다. 시작 자세부터 목표 자세까지의 swept path,
속도, 가속도, jerk는 검사하지 않으므로 `S` 저장 직후 다음 두 단계를 수행한다.

Startup Recovery의 실제 충돌 hard minimum은 전 구간 12 mm다. 20 mm는
초기 접촉 쌍에서 벗어나는 방향을 잠시 유지하기 위한 escape 보조 목표 해제값이며,
별도 자세나 정지 구간이 아니다. 준비자세 recovery는 첫 스텝부터 함께 실행한다.

```powershell
.\tools\TEST_G1_STARTUP_RECOVERY_OFFLINE.bat
.\tools\VIEW_G1_STARTUP_RECOVERY.bat
```

현재 캡처 자세에 대한 500 Hz dry-run은 3.828초에 완료됐고 속도 8 deg/s,
가속도 30 deg/s^2, jerk 300 deg/s^3 제한과 독립 replay를 통과했다. 이 수치는 아직 실제 G1
승인 기준이 아니므로 결과의 `hardware_ready`는 `false`이며 실제
publisher나 command output은 없다.

## Mink → Safety mirror

Windows Mink controller는 하드웨어 safety dry-run 검증을 위해 robot state/target 정보를 UDP `5008`에도 mirror할 수 있다.

```text
Mink
 ├─ UDP 5006 → Unity
 └─ UDP 5008 → Safety dry-run
```

## 실제 LowState → Gate 5 read-only monitor

```powershell
.\tools\START_G1_GATE5_READ_ONLY.bat
```

이 launcher는 WSL의 read-only subscriber와 Windows Gate 5 모니터만 실행한다.

```text
G1 rt/lowstate
→ read_only_lowstate.py (DDS subscriber only)
→ schema/session/sequence가 있는 UDP 5007 telemetry
→ gate5_lowstate_safety_monitor.py
→ measured q = requested HOLD q
→ safety_gate.evaluate_target(...)
→ HOLD_READY 또는 fail-closed FAULT
```

Gate가 허용한 `candidate_q_rad`는 검사 결과 JSON에만 기록하며 다른 프로세스나
로봇으로 전달하지 않는다. `rt/lowcmd`, `ChannelPublisher`, `LowCmd` 경로는 없다.
LowState가 250 ms 이상 끊기면 `LOWSTATE_TIMEOUT`과 함께 후보를 `null`로 만든 뒤
모니터를 종료한다. bridge 세션 변경이나 역행/중복 순번도 명시적 재시작이 필요한
fault로 처리한다.

결과:

```text
logs/runtime/g1_gate5_lowstate_safety.json
logs/runtime/g1_gate5_lowstate_safety.jsonl
```

실제 G1 없이 수신, HOLD 후보, 단절 차단을 검증하려면 다음을 실행한다.

```powershell
.\tools\TEST_G1_GATE5_READ_ONLY.bat
```

이 테스트는 synthetic UDP telemetry만 사용하며 결과를
`logs/test_results/g1_gate5_read_only.log`에 저장한다.

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
| `gate5_lowstate_safety_monitor.py` | 실제 LowState를 Safety Gate에 넣는 무출력 Gate 5 모니터 |
| `receive_initial_state.py` | UDP 5007 초기 pose 수신 |
| `verify_initial_pose_sync.py` | G1 pose → Mink → Unity packet 일치 검사 |
| `safety_gate.py` | fail-closed target safety validation |
| `hardware_state.py` | phase/fault schema |
| `hold_dry_run.py` | measured pose HOLD 검증 |
| `mink_target_dry_run.py` | Mink target safety dry-run |
| `simulate_startup_recovery.py` | measured rest-to-ready Mink QP offline recovery |
| `edit_startup_ready_pose.py` | MuJoCo keyboard editor for the named startup ready pose |
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
