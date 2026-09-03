# G1 Right-Arm Hardware Bridge

이 폴더는 Windows의 Mink teleoperation controller와 실제 Unitree G1 사이의 **하드웨어 안전 경계**다.

> **현재 상태:** Gate 6 `rt/arm_sdk` measured-pose HOLD publisher 경계를 분리 구현했고, 사용자 확인을 거친 최대 weight `0.2` HOLD를 실제 G1에서 1회 완료했다. `config/g1_gate6_hold.json`은 다시 `hardware_output_authorized=false`로 잠겨 있으며 live Mink target은 아직 실제 G1에 전송하지 않았다.

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
- Unitree DDS `rt/odommodestate` subscribe
- DDS publisher 없음
- G1 29 joints position/velocity 측정 및 전달
- 기존 Gate 5 호환을 위한 right-arm 7 joints 필드 유지
- position / velocity / estimated torque 확인
- stale LowState fault 처리
- 필요 시 Windows로 UDP 5007 또는 5009 telemetry forward
- base pose는 첫 유효 odometry sample을 원점/identity로 만든 상대값만 전달

예상 사용:

```bash
python3 hardware/g1_arm_bridge/read_only_lowstate.py eth0
```

실제 G1이 연결된 interface 이름으로 `eth0`를 바꾼다.

### 실시간 MuJoCo/Unity 전신 표시

```powershell
.\tools\VIEW_G1_LIVE_MUJOCO.bat
```

이 런처는 `rt/lowstate`의 29개 `q`/`dq`와 `rt/odommodestate`의 상대 base
pose를 UDP 5009로 받아 MuJoCo에 표시한 뒤, 같은 검증 완료 상태를
`g1_unity_state_bridge.py`로 변환해 UDP 5010의
Unity 전신 프리뷰에도 전달한다. Unity의 Mink 피드백 수신기 UDP 5006과 실제
G1 표시 수신기 UDP 5010은 별도 컴포넌트다. 따라서 실제 상태 표시는
`G1ExistingTargetUdpSender`의 workspace/collision 피드백 출처를 바꾸지 않는다.
이 경로에는 DDS publisher, LowCmd 또는 motor command가 없다.
base topic이 끊기면 마지막 base pose를 유지하면서 29관절 표시는 계속한다.
기존 저장 packet에 base 필드가 없으면 고정 base로 재생한다.
라이브 런처는 실제 UDP 5009 source packet을
`logs/runtime/g1_live_state_YYYYMMDD_HHMMSS.jsonl`에 자동 저장한다.

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
캡처한 오른팔 7개 관절값이 현재 Mink 모델까지 그대로 유지되는지 검사한다.
Unity state packet은 오른팔 호환 필드와 함께 29개 관절 이름/위치를 전달한다.

### 저장 상태 오프라인 재생

G1을 사용할 수 없는 동안에도 29관절 표시 경로를 반복 검증할 수 있다.

```powershell
.\tools\VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat
```

`replay_saved_lowstate_mujoco.py`는 저장 JSON을 엄격한 LowState telemetry
문서로 바꿔 로컬 UDP 5009에 30 Hz로 재생하고, 기존
`live_lowstate_mujoco.py`가 이를 그대로 수신한다. 검증된 상태는 UDP 5010에도
전달되므로 Unity가 Play 상태이면 공식 G1 모델에서 같은 자세를 확인할 수 있다.
Unitree SDK와 DDS를 import하지 않고 publisher 및 motor command를 만들지 않는다.
완전한 실제 29관절 저장본이 없을 때만 pose-sync 검증 자세를 명시적인
fallback으로 사용한다.

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
gate5_lowstate_safety_monitor.py
arm_sdk_hold_contract.py
mink_target_dry_run.py
generate_fake_mink_targets.py
test_fake_mink_safety_e2e.py
test_mink_safety_pipeline.py
```

대표 도구:

```powershell
.\tools\START_G1_GATE7_LIVE_DRY_RUN.bat
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

## Regular Mode startup precheck

```powershell
.\tools\CHECK_G1_TELEOP_STARTUP.bat
```

이 검사는 Startup Recovery를 항상 실행하지 않고, 현재 자세가 이미 안전하면
생략하기 위한 **읽기 전용 판정기**다.

```text
MotionSwitcher CheckMode (read-only RPC query)
              +
rt/lowstate 1 second window
  - packet age / session / sequence
  - mode_machine and mode_pr consistency
  - Gate 5 joint limits
  - right-arm pose span and velocity p95
  - measured 29-joint MuJoCo/Mink collision distance for both arms
              ↓
DIRECT_TELEOP_READY / WAIT_AND_RETRY /
REGULAR_MODE_REQUIRED / RECOVERY_REQUIRED / STARTUP_BLOCKED
```

`query_motion_mode.py`는 `CheckMode()`만 호출한다. `SelectMode()`와
`ReleaseMode()`는 호출하지 않으며 로봇 상태를 바꾸지 않는다. 현재 사용자가
Regular Mode라고 확인한 실기에서 반환된 MotionSwitcher 서명은
`form="0", name="ai"`였다. 이는 현재 G1/펌웨어에서 캡처한 운용 서명이며,
`LowState.mode_machine=5`는 Regular/Damping 구분값으로 사용하지 않는다.

현재 판정 기준은 다음과 같다.

```text
observation window                  : 1.0 s
minimum forwarded packets           : 20
maximum LowState age                : 250 ms
maximum right-arm pose span         : 0.5 deg
maximum right-arm velocity p95      : 3.0 deg/s
minimum modeled collision clearance : 12 mm
```

기준은 `config/g1_startup_precheck.json`에 있다. 펌웨어나 G1이 바뀌어
MotionSwitcher 서명이 달라지면 자동으로 새 값을 받아들이지 않고 시작을
차단한다. 새 서명은 로봇 운용 모드를 사람이 확인한 뒤 별도로 검토해야 한다.

`DIRECT_TELEOP_READY`는 측정 자세가 Recovery 생략 조건을 통과했다는 의미다.
실제 publisher 생성이나 command 전송을 허가하지 않으며, 현재 저장소에는 여전히
이 검사는 실제 G1 command publisher를 생성하지 않는다. 결과 파일:

```text
logs/runtime/g1_motion_mode_query.json
logs/runtime/g1_startup_precheck.json
```

## Gate 6 measured-pose Arm SDK HOLD

Gate 6은 Regular Mode의 하체 motion service를 유지하면서 공식
`rt/arm_sdk` 경로로 양팔 제어권을 단계적으로 혼합하기 위한 경계다.
Regular Mode 실기 출력은 G1이 평평한 지면에 두 발로 서서 스스로 균형을
잡는 상태에서만 허용한다. 공중에 매달아 하중을 지지한 상태의 검사는
`rt/lowstate` 읽기 및 메시지 계약 확인 근거일 뿐, 실기 출력 승인 근거가 아니다.

```powershell
.\tools\TEST_G1_GATE6_HOLD_OFFLINE.bat
.\tools\PREPARE_G1_GATE6_HOLD.bat
```

`TEST_G1_GATE6_HOLD_OFFLINE.bat`는 Windows의 순수 command-contract 테스트와
WSL에 설치된 Unitree SDK2의 실제 35-slot HG `LowCmd_`/CRC 호환성을 검사한다.
`ChannelFactory`와 DDS publisher를 만들지 않는다.

`PREPARE_G1_GATE6_HOLD.bat`는 연결된 G1에서 다음 조건만 읽기 전용으로
검사한다.

```text
MotionSwitcher CheckMode == form 0 / name ai
rt/lowstate 수신 및 1초 settle window
mode_pr == 0, mode_machine == 5
양팔 15..28 관절 유한값/물리 관절범위
양팔 초기 최대 속도 <= 5 deg/s
측정 q와 HOLD target이 정확히 동일
```

Arm SDK weight는 양팔 명령 전체를 motion service 명령과 혼합하므로 오른팔만
검사하지 않는다. 왼팔과 오른팔 14축을 모두 현재 실측값으로 시드한다. 반면
허리 12~14번과 하체 관절은 dynamic target set에 포함하지 않고 command mode와
gain을 0으로 유지한다. 첫 실기 후보 weight 상한은 0.2이고, 정상 종료 경로는
3초 ramp-up, 3초 HOLD, 3초 ramp-down 후 weight 0을 반복 송신하도록 구성했다.

실제 출력에는 추가로 다음 네 조건이 모두 필요하다.

```text
1. 60초 이내 DIRECT_TELEOP_READY startup precheck
2. hardware_output_authorized == true
3. 실행 시 정확한 hardware confirmation phrase
4. 실행 시 정확한 grounded-Regular confirmation phrase
```

현재 2번이 의도적으로 `false`이므로 실제 출력 분기는 실행할 수 없다. 강제로
출력 인자를 주어도 `OUTPUT_NOT_AUTHORIZED`, `publisher_present=false`,
`published_frames=0`으로 차단된다.

2026-08-28 연결 실측 준비 결과:

```text
phase                         : HOLD_READY
network interface             : eth3
motion mode                   : form=0, name=ai
settle samples                : 840
maximum dual-arm velocity     : 2.72 deg/s
publisher present             : false
command output enabled        : false
```

이 결과는 매달린 G1에서 얻은 읽기 전용 결과이므로 DDS 수신, mode signature,
관절값 및 HOLD 계약만 검증한다. 지상 자립 Regular Mode의 실제 출력 승인은
새 현장 확인과 새 startup precheck를 거쳐야 한다.

결과:

```text
logs/runtime/g1_gate6_arm_sdk_hold.json
logs/runtime/g1_gate6_arm_sdk_hold.jsonl
logs/test_results/g1_gate6_hold_offline.log
logs/test_results/g1_gate6_hold_prepare.log
```

## Gate 7 locked Mink target and Regular return

```powershell
.\tools\TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat
```

Gate 7은 실제 publisher를 추가하지 않고 다음 live-target 계약을 오프라인으로
검증한다.

```text
active Mink state       -> 오른팔 22..28 후보 추종
intentional pinch       -> 실측 Regular 양팔 15..28로 minimum-jerk 복귀
tracking/network loss   -> 측정된 현재 양팔 자세를 최대 10초 HOLD
workspace/collision     -> 측정된 현재 양팔 자세를 최대 10초 HOLD
fault persists 10 s     -> 같은 검증된 Regular 양팔 복귀
active recovers < 10 s  -> 타이머 취소 후 오른팔 추종 재개
```

`pinch_disengaged`와 `tracking_disengaged`는 Unity에서 이미 구분된다. Mink가
내부 제어 상태를 둘 다 idle로 축약하더라도 UDP 5008의
`input_command_mode`가 원본 이유를 보존한다. active에서 pinch로 넘어가는 edge는
즉시 복귀를 시작하고, ACTIVE 이후 의도치 않은 해제는 10초간 지속될 때만 복귀한다.
처음부터 idle인 세션에는 이 타이머가 작동하지 않는다.

복귀 목표는 `config/g1_regular_arm_pose.json`의 지상 Regular 실측 양팔 자세다.
trajectory는 velocity, acceleration, jerk 제한을 만족하는 minimum-jerk 곡선이며,
모든 250 Hz sample이 현재 MuJoCo/Mink collision pair에서 12 mm 이상인지 먼저
검증한다. 검증기 누락 또는 경로 충돌 시 fail closed로 HOLD한다.

이 단계는 저장된 Regular 관절 자세 후보를 계산할 뿐 실제 G1 내부 Regular
제어기로 권한을 넘기지 않는다. 휴대용 조종기는 비상정지와 운용 모드 전환을 위해
계속 사용한다. 실제 권한 반환은 Arm SDK weight release, 현재 motion service 확인,
지상 자립 실기 승인이 포함된 별도 단계다.

### Gate 7 live dry-run

```powershell
.\tools\START_G1_GATE7_LIVE_DRY_RUN.bat
.\tools\TEST_G1_GATE7_LIVE_DRY_RUN.bat
```

실행기는 현재 Unity/Mink 스트림의 UDP 5008을 250 Hz로 소비하고, Gate 7 결정과
SDK-neutral 35-slot frame 후보를 JSONL에 기록한다. 기본 `mink` 모드는 G1 없이
shadow measured pose를 후보에 맞춰 갱신한다. 실제 G1 read-only 상태로 비교할
때는 전용 UDP 5007 forwarder와 함께 다음 옵션을 사용한다.

```powershell
py -3.11 hardware\g1_arm_bridge\gate7_live_dry_run.py `
  --measured-source lowstate --lowstate-port 5007
```

G1 연결, read-only forwarder, Gate 7 및 Unity/MuJoCo를 순서대로 시작하는 전용
실행기는 다음과 같다.

```powershell
.\tools\START_G1_GATE7_LOWSTATE_DRY_RUN.bat
```

LowState mode는 250 ms stale 또는 측정 자세와 후보의 10도 초과 차이를 거부한다.
양쪽 모드 모두 Unitree SDK import, DDS entity, publisher 및 robot command가 없다.

기본 live dry-run은 승인 후보를 localhost UDP `5012`로 기존 MuJoCo 창에
시뮬레이션 피드백한다. MuJoCo는 연동 해제 뒤 `REGULAR_RETURN`과
`REGULAR_HOLD`만 적용하므로 10초 HOLD와 Regular 자세 복귀를 G1 없이 볼 수 있다.
패킷에는 `simulation_only=true`, `hardware_output_authorized=false`가 강제되며
실제 Unitree SDK/DDS 출력은 계속 존재하지 않는다.

현재 `config/g1_gate7_mink_arm_sdk.json`의
`hardware_output_authorized=false`는 고정이다. 오프라인 검증기는 Unitree SDK를
import하지 않고, socket/DDS/publisher를 만들지 않으며, 실제 G1 command를 보내지
않는다.

### Gate 7 live hardware foundation (locked)

```powershell
.\tools\TEST_G1_GATE7_HARDWARE_FOUNDATION_OFFLINE.bat
```

`gate7_mink_wsl_relay.py`는 Windows `127.0.0.1:5008`에서만 수신하고 strict
Mink schema, session, sequence를 검사한 packet만 WSL UDP `5013`으로 전달한다.
이 relay에는 Unitree SDK와 DDS 코드가 없다.

`gate7_live_arm_sdk.py`는 WSL에서 직접 `rt/lowstate` 29관절을 읽고 Gate 7
상태 머신 뒤에 Ruckig 0.19.4 궤적 제한을 적용하는 잠금 어댑터다. 물리 후보는
40/100 deg/s와 설정 원본의 가속도·jerk를 그대로 사용한다. 물리 모드는 명시적 승인과 두
확인 문구, fresh `DIRECT_TELEOP_READY`, MotionSwitcher `form=0/name=ai`, 예상
motor mode, fresh/settled LowState, precheck 자세 일치를 모두 요구한다.
UDP 5013에서 유효한 strict Mink packet까지 수신한 뒤에만 publisher를 생성한다.

publisher가 생성되면 먼저 현재 양팔 자세를 5초 동안 weight ramp로 획득한다.
그 뒤 오른팔 `22~28`만 Mink target으로 변경하고 왼팔 `15~21`은 획득 자세를
HOLD한다. 허리와 하체의 mode/gain/dq/tau는 계속 0이다. LowState stale, mode
변경, packet/후보 거부, 시간 만료, 신호 종료에서는 weight를 2초 동안 0으로
내리고 zero-weight frame 25개를 반복한다.

실제 실행기 `START_G1_GATE7_LIVE_HARDWARE.bat`도 준비했지만 현재
`config/g1_gate7_live_hardware_output.json`의
`hardware_output_authorized=false`에서 fail closed한다. 제한된 어깨 authority
시험 결과가 승인되기 전에는 잠금을 해제하지 않는다. Ruckig Python 패키지는
노트북 WSL에만 필요하며 G1 내부에는 설치하거나 파일을 변경하지 않는다.

첫 실제 VR 시험은 표준 프로필을 직접 바꾸지 않고 별도
`g1_gate7_first_live_mink_arm_sdk.json`과
`g1_gate7_first_live_hardware_output.json`을 사용한다. weight는 앞선 물리
authority 시험에서 유효성이 확인된 1.0이고, 시간은 20초, Ruckig 관절 제한은
10/25 deg/s, 20/50 deg/s2, 80/200 deg/s3이다. publisher 획득 자세에 대한
14개 팔 관절의 최대 명령 이탈은 3도이며, 검사는 `publisher.Write`보다 먼저
실행된다. 초과 시 `start_pose_excursion_limit` fault 후 기존 2초 weight release와
25개 zero frame 절차를 수행한다. 설정은 모두 잠겨 있다.

```powershell
.\tools\TEST_G1_GATE7_FIRST_LIVE_OFFLINE.bat
.\tools\START_G1_GATE7_FIRST_LIVE_TRIAL.bat
```

첫 명령은 Unitree SDK/DDS 없이 전용 프로필 전체를 검사한다. 두 번째 명령은 물리
실행기지만 현재 잠금에서 publisher 생성 전에 차단된다.

실제 포트와 가상 LowState를 사용하는 전체 무출력 시험은 다음과 같다.

```powershell
.\tools\TEST_G1_GATE7_VIRTUAL_HARDWARE_E2E.bat
```

이 시험은 합성 packet을 UDP `5008 -> 5013`으로 실제 전달하고 Gate 7
SDK-neutral frame까지 생성한다. duplicate/malformed packet, collision 제한,
10초 unintended HOLD, LowState stale, weight acquire/release를 함께 검사하지만
Unitree SDK나 DDS entity를 만들지 않는다.

실제 Quest 캡처를 물리 후보 제한으로 검증하려면 다음을 실행한다.

```powershell
.\tools\TEST_G1_GATE7_RUCKIG_HARDWARE_PROFILE_OFFLINE.bat
```

이 검사는 40/100 deg/s, 가속도·jerk 배율 1.0에서 미분 제한 초과가 0인지 확인한다.

### Recorded VR input regression

`gate7_mink_capture.py`는 localhost UDP 5008 strict packet의 원본 bytes와 도착
간격을 JSONL에 저장하고 UDP 5014의 Gate 7 dry-run으로 전달한다.
`gate7_mink_replay.py`는 동일 관절 target을 새 transport session으로 재생한다.
`gate7_capture_regression.py`는 캡처를 250 Hz virtual LowState로 deterministic하게
실행하고 상태 전이 및 전체 target trace digest를 baseline과 비교한다.

```powershell
.\tools\START_G1_GATE7_VR_RECORDING.bat
.\tools\TEST_G1_GATE7_LATEST_CAPTURE_REGRESSION.bat
```

회귀 post-roll은 13초다. 입력 stale 이후 10초 HOLD와 Regular 복귀가 끝나
`REGULAR_HOLD`에 도달할 시간을 포함한다. 결과 변화는 hardware 시험 전에
검토해야 하며 자동 승인으로 사용하지 않는다.

## 실제 command 단계 전 필수 순서

```text
1. WSL/Unitree SDK2 정상화
2. 실제 G1 Ethernet/DDS 연결
3. rt/lowstate read-only 검증
4. Regular Mode startup precheck
5. joint index / sign / range 검증
6. measured pose → Mink/Unity 초기 sync
7. 실제 LowState 기반 Safety Gate dry-run
8. q_target = q_measured HOLD dry-run
9. Gate 6 publisher 계약/SDK 메시지 검토
10. 출력 잠금 상태에서 실측 HOLD_READY 확인
11. 지상 자립 Regular Mode와 현장 stop operator를 확인한 뒤 제한된
    0.2-weight HOLD 실기 승인
12. 그 이후에만 Mink target 연결
```

이 순서를 건너뛰지 않는다.

## 제한된 오른팔 7DoF interactive publish 실험

```powershell
.\tools\TEST_G1_RIGHT_ARM_JOG_OFFLINE.bat
.\tools\START_G1_RIGHT_ARM_JOG_MUJOCO.bat
```

이 실험은 live VR target 이전에 `rt/arm_sdk` publish와 실제 LowState 반영을
오른팔 관절별로 확인한다. 실행 중 숫자키 `1~7`로 하드웨어 인덱스 `22~28` 중
한 관절을 활성화하며, 목표는 1도 단위, 시작 자세 기준 최대 ±20도로 제한한다.
어깨·팔꿈치는 2.5 deg/s, 손목은 5 deg/s이며 다음 목표가 실측보다 2도 넘게
앞서면 추가 step 입력을 거부한다. 다른 관절을 고르면 현재 관절을 precheck
자세로 먼저 복귀시킨다. Jog 전용 Arm SDK weight 상한은 0.25다. Arm SDK
전역 weight 때문에 양팔 14축 frame을 보내지만 나머지 13축 목표는 매 주기
실측값으로 시드하며, 허리와 하체의 mode, gain, dq, tau는 0이다.

첫 `1~7` 선택 전에는 Arm SDK weight가 0이며 30초 active timer도 시작하지 않는다.
선택 순간 현재 양팔 자세가 collision permit의 precheck 자세와 1도 이내인지 다시
검사하고 통과한 경우에만 weight ramp를 시작한다. 선택 없이 15초가 지나면 종료한다.

publisher 생성 전 필수 조건은 fresh `DIRECT_TELEOP_READY`, MotionSwitcher
`form=0/name=ai`, `mode_pr=0`, `mode_machine=5`, 정지한 양팔 및 일곱 관절의
방향별 MuJoCo 충돌 검사 통과다. 검사는 1도씩 바깥으로 진행하며 처음 실패한
각도 바로 전까지를 해당 방향의 허용 범위로 저장한다. 실제 자세는 별도 read-only
LowState 경로 UDP 5009로 MuJoCo에 표시한다. 경로 한쪽이라도 12 mm 충돌
여유를 만족하지 못하면 그 방향의 범위를 더 확장하지 않는다. 경로검사 후
다시 읽은 실제 양팔 자세가 precheck 자세에서 1도 넘게 달라져도 publisher를
생성하지 않고 재검사를 요구한다.

### Weight 1.0 분리 시험

`START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat`은 일반 Jog와 설정 및 permit을
분리한 진단용 시험이다. `trial_mode=full_authority_shoulder_pitch_trial`일 때만
코드가 weight `1.0`을 허용하며 다음 조건을 모두 강제한다.

- 허용 관절은 `right_shoulder_pitch` 하나뿐이다.
- 시작 LowState에서 읽은 양팔 14축 목표를 authority transfer 동안 고정한다.
- 5초 ramp 중에는 방향키 입력을 받지 않는다.
- weight `1.0` 및 14축 최대 추종 오차 `1.5도 이하`에서만 Jog를 arm한다.
- 이동 범위 `+/-1도`, 속도 `1 deg/s`, active 시간 `15초`를 넘길 수 없다.
- 정상 종료와 fault 모두 weight를 0으로 내리고 zero frame을 반복 전송한다.

이 시험은 VR/Gate 7의 기본 경로가 아니며, `0.25`에서 관찰된 작은 실측 응답이
AI/Regular command blending 때문인지 확인하기 위한 제한된 하드웨어 진단이다.

## Command publisher 정책

실제 publisher 코드는 `gate6_arm_sdk_hold.py`, 제한된 Jog 및 잠긴
`gate7_live_arm_sdk.py`의 명시적 hardware-output 분기에만 있다. 기본 실행에서는
생성하지 않는다. Gate 7 live config 잠금 때문에 새 live 분기는 활성화할 수 없다.

publisher 정책:

- `read_only_lowstate.py`에 publisher를 추가하지 않는다.
- command publisher는 read-only forwarder와 분리된 프로세스로 유지한다.
- 양팔 HOLD 계약이 `allowed=True`인 경우만 35-slot SDK frame을 만든다.
- stale state/fault 시 fail closed한다.
- 정상 경로는 Arm SDK weight acquire/release lifecycle을 명시적으로 관리한다.
- `rt/lowcmd`를 사용하지 않고 `rt/arm_sdk`만 사용한다.
- 허리 12~14번과 하체 관절은 dynamic target update에서 제외한다.

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| `read_only_lowstate.py` | G1 DDS LowState read-only |
| `live_lowstate_mujoco.py` | UDP 5009 실제 29관절 MuJoCo 표시 및 선택적 Unity 전달 |
| `replay_saved_lowstate_mujoco.py` | 저장 29관절 상태의 G1-free 오프라인 재생 |
| `g1_unity_state_bridge.py` | 검증된 LowState를 UDP 5010 Unity 표시 패킷으로 변환 |
| `query_motion_mode.py` | MotionSwitcher `CheckMode()` 전용 무변경 조회 |
| `check_startup_readiness.py` | Regular 자세의 Recovery 생략 조건 판정 |
| `gate5_lowstate_safety_monitor.py` | 실제 LowState를 Safety Gate에 넣는 무출력 Gate 5 모니터 |
| `arm_sdk_hold_contract.py` | 양팔 measured-pose HOLD, 관절범위, 35-slot frame, weight schedule 계약 |
| `gate6_arm_sdk_hold.py` | 기본 읽기 전용 Gate 6 준비 검사와 잠긴 `rt/arm_sdk` publisher 경계 |
| `arm_sdk_teleop_contract.py` | strict Mink input, watchdog, right-arm target, 10초 HOLD 및 dual-arm 복귀 계약 |
| `gate7_mink_arm_sdk_offline.py` | Gate 7 trajectory/collision/35-slot frame 무출력 통합 검증 |
| `gate7_live_dry_run.py` | UDP 5008 실시간 Gate 7 후보와 로그, 선택적 LowState 측정 비교 |
| `gate7_mink_wsl_relay.py` | localhost UDP 5008 strict 검증 후 WSL UDP 5013 전달; DDS 없음 |
| `gate7_live_arm_sdk.py` | 잠긴 Gate 7 실측 LowState + live `rt/arm_sdk` 어댑터 |
| `gate7_hardware_virtual_e2e.py` | UDP 5008→5013과 가상 LowState를 이용한 무출력 전체 경로 검증 |
| `gate7_mink_capture.py` | strict UDP 5008 원본/시간 기록 및 UDP 5014 전달 |
| `gate7_mink_replay.py` | 기록된 target을 fresh transport session으로 UDP 재생 |
| `gate7_capture_regression.py` | 캡처 기반 deterministic Gate 7 trace와 baseline 비교 |
| `gate7_fault_injection_matrix.py` | packet/추적/workspace/collision/LowState fault 무출력 주입 검사 |
| `gate7_capture_quality.py` | 실제 Quest 캡처의 raw IK 및 Gate 7 candidate 품질 분석 |
| `gate7_capture_mujoco_replay.py` | 캡처의 engage/tracking-loss 구간 MuJoCo 반복 재생 |
| `ruckig_gate7_controller.py` | Gate 7 상태/watchdog/collision 결정 뒤 모든 상태를 Ruckig 궤적으로 제한 |
| `ruckig_joint_motion_limiter.py` | Ruckig 기반 속도·가속도·jerk 무출력 실험 제한기 |
| `verify_arm_sdk_message_offline.py` | 설치된 Unitree SDK2 `LowCmd_`/CRC 무통신 호환성 검사 |
| `receive_initial_state.py` | UDP 5007 초기 pose 수신 |
| `verify_initial_pose_sync.py` | G1 pose → Mink → Unity packet 일치 검사 |
| `safety_gate.py` | fail-closed target safety validation |
| `hardware_state.py` | phase/fault schema |
| `arm_sdk_hold_contract.py` | 양팔 measured pose HOLD 계약; 구형 단일 팔 HOLD 데모 대체 |
| `mink_target_dry_run.py` | Mink target safety dry-run |
| `simulate_startup_recovery.py` | measured rest-to-ready Mink QP offline recovery |
| `edit_startup_ready_pose.py` | MuJoCo keyboard editor for the named startup ready pose |
| `HARDWARE_BRINGUP_CHECKLIST.md` | 실제 하드웨어 단계별 체크리스트 |

오프라인 Ruckig 비교 경로는 물리 Gate 7과 분리되어 있다. 각 관절은 다른 관절의
도착시간에 묶이지 않고 독립적으로 제한 궤적을 생성한다. 현재 비교값은
50/125 deg/s, 물리 설정 대비 가속도 3배, jerk 6배이며 실제 G1 설정 40/100 deg/s와
하드웨어 출력 잠금은 변경하지 않는다.

## 금지 사항

실제 G1 연결 전에는 다음을 임의로 하지 않는다.

```text
- read-only 파일에 publisher 추가
- Safety Gate 우회
- 초기 measured pose sync 없이 target 전송
- 큰 joint step으로 첫 command 전송
- simulation에서 통과했다는 이유만으로 real command 활성화
```
