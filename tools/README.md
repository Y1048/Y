# Project Tools

`tools/`에는 현재 G1 teleoperation에 필요한 실행, 검증, 네트워크 복구용 BAT만 둔다.

코드 설명은 [CODE_GUIDE](../docs/CODE_GUIDE.md), 2026-09-03 삭제 범위와
보존 이유는 [정리 기록](../docs/CLEANUP_20260903.md)을 먼저 확인한다.
`TEST_*`는 자동 회귀검사용이며, `START_*` 물리 실행과 같은 의미가 아니다.

파일 검색은 [코드 색인](../docs/CODE_INDEX.md)을 사용한다. 코드/설정 파일을
추가하거나 변경한 뒤에는 `py -3.11 backend/tools/build_code_index.py`로 갱신한다.
`--check`는 저장된 색인이 현재 파일과 일치하는지만 검사하며 실행 승인이나
전체 코드 검토를 대신하지 않는다.

## Live teleoperation

기본 실행은 프로젝트 루트의 다음 파일을 사용한다.

```powershell
.\START_VR_HAND_TO_MUJOCO.bat
.\tools\START_G1_GATE7_LIVE_DRY_RUN.bat
```

## Quest and Unity

### Unity display source (explicit per Play session)

- `START_VR_HAND_TO_MUJOCO.bat` and Quest recording/dry-run launchers select
  `simulation`: only UDP 5006 Mink state drives the displayed robot.
- `START_G1_GATE7_LIVE_HARDWARE.bat` (including trial wrappers) selects `hardware`
  and invokes the root launcher with `--hardware-display`. UDP 5010 measured
  29-joint state is the only robot display source; UDP 5006 remains IK/green-goal
  diagnostic data, never a substitute for measured joints.
- `VIEW_G1_LIVE_MUJOCO.bat` also selects `hardware` without granting motor output.
- `VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat` selects `recorded`, labelled NOT LIVE.
- Stop Unity Play before switching launchers/modes, then press Play again.
  `tools/SET_UNITY_DISPLAY_MODE.ps1` writes only local
  `logs/runtime/unity_display_mode.json`. It changes no hardware authorization.
  A running Play session latches its mode; a detected config change blocks
  display updates until Play restarts. Missing/invalid config also blocks display.
- On stale/missing measured state, the last displayed pose stays frozen and a
  headset status says `G1 STATE LOST / WAITING`. There is no simulation fallback.
  Before the first measured packet, the prefab/default pose is NOT a measurement.
  This is display behavior, not a motor emergency-stop implementation.
- The label is local provenance metadata, not cryptographic source authentication.
  Do not run saved-state replay and live hardware mirroring simultaneously.

```powershell
.\tools\BUILD_AND_INSTALL_VR_APK.bat
```

## Frame and IK validation

```powershell
.\tools\TEST_MINK_WRIST_FRAME.bat
.\tools\TEST_G1_MINK_FK_PARITY.bat
.\tools\TEST_MINK_COLLISION_TANGENT_OFFLINE.bat
```

`TEST_MINK_COLLISION_TANGENT_OFFLINE.bat`는 2026-09-04 Quest 시험에서
측정한 5 mm 충돌 경계 자세를 네트워크 없이 재현한다. 기존 단조 merit 정책이
즉시 정지하는 것과 로컬 waypoint 정책이 5 mm를 유지하며 바깥쪽으로 우회한 뒤
원래 목표 오차를 다시 줄이는 것을 비교한다.
Unitree SDK, DDS publisher와 로봇 명령은 사용하지 않는다.

## Hardware read-only and synchronization

```powershell
.\tools\START_G1_READ_ONLY.bat
.\tools\VIEW_G1_LIVE_MUJOCO.bat
.\tools\VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat
.\tools\CHECK_G1_TELEOP_STARTUP.bat
.\tools\START_MINK_G1_HARDWARE_SYNC.bat
.\tools\START_G1_GATE5_READ_ONLY.bat
.\tools\PREPARE_G1_GATE6_HOLD.bat
.\tools\EDIT_G1_STARTUP_READY_POSE.bat
.\tools\TEST_G1_STARTUP_RECOVERY_OFFLINE.bat
.\tools\VIEW_G1_STARTUP_RECOVERY.bat
```

`START_G1_READ_ONLY.bat`는 WSL에서 `192.168.123.99`가 설정된 interface를
자동 탐색하고 `rt/lowstate`와 `rt/odommodestate`를 구독한다. DDS publisher와
motor command는 없다.

`VIEW_G1_LIVE_MUJOCO.bat`는 읽기 전용 `rt/lowstate`에서 다리, 허리, 양팔을
포함한 29개 관절을, `rt/odommodestate`에서 base 위치/방향을 함께 받아 UDP
5009로 전달한다. 첫 유효 base sample을 원점과 identity로 정규화한 뒤 MuJoCo
G1 전신과 base에 계속 반영한다. MuJoCo가 해당 프레임에 실제 표시한 보간 자세는
UDP 5010으로 Unity의 별도
하드웨어 프리뷰 수신기에 전달된다. Unity를 Play 상태로 두면 공식 G1 모델이
명시적인 hardware 표시 모드에서 실측 관절값만 표시하며, 이 경로는 Mink 안전 피드백용 UDP 5006을
변경하지 않는다. 첫 패킷은
즉시 적용하고 이후 30 Hz 표본 사이만 짧게 보간한다. 250 ms 이상 패킷이
끊기면 마지막 자세에서 멈추며 로봇으로 보내는 명령은 없다.
base topic이 없거나 250 ms 이상 stale이면 관절 미러는 계속 동작하고 마지막
base pose만 유지한다. 저장 상태처럼 base 필드가 없는 기존 packet은 고정 base로
재생된다.
각 라이브 실행은 UDP 5009에 보낸 정확한 source packet을
`logs/runtime/g1_live_state_YYYYMMDD_HHMMSS.jsonl`에 기록하고 forwarder 창에
저장 경로를 표시한다. 이동 테스트 후 위치/yaw 방향과 packet 연속성을 재검토할
때 이 파일을 사용한다.
MuJoCo Viewer는 별도로
`logs/runtime/g1_visual_mirror_YYYYMMDD_HHMMSS.jsonl`을 자동 저장한다. 여기에는
G1 원본 이동량, MuJoCo 실제 표시 이동량, Unity에 전달한 동일 이동량과 순간
보간 오차가 들어간다. Unity Console의 `G1 BASE MIRROR` 행은 Unity G1 root가
그 5010 자세를 실제로 적용한 오차까지 1초마다 표시한다.
첫 실행에서 UDP가 차단되면 `ALLOW_G1_LOWSTATE_TO_WINDOWS.bat`를 관리자 승인으로
한 번 실행해 읽기 전용 telemetry 포트 5007과 5009를 허용한다.

`VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat`는 G1, Ethernet, WSL, DDS 및 VR 없이
저장된 29관절 JSON을 같은 UDP 5009 계약으로 재생하고, Unity가 Play 상태이면
같은 검증 자세를 UDP 5010으로 표시한다. 완전한
`g1_hardware_lowstate.json`이 있으면 이를 우선 사용하고, 현재처럼 구형 실제
스냅샷에 29관절 필드가 없으면 `g1_hardware_pose_sync_validation.json`의 검증용
전신 자세를 사용하면서 화면에 경고를 표시한다. 다음 실제 연결에서
`START_G1_READ_ONLY.bat`를 실행하면 새 실제 29관절 캡처로 자동 전환된다.

`CHECK_G1_TELEOP_STARTUP.bat`는 현재 G1이 검증된 Regular 상태라면 Startup
Recovery를 생략할 수 있는지 자동 판정한다. 먼저 MotionSwitcher의 읽기 전용
`CheckMode()`만 호출하고, 이어서 1초간 `rt/lowstate`를 관찰해 패킷 신선도,
기종/관절구조, Gate 5 관절 제한, 오른팔 정지 상태, 실제 29관절 자세를 반영한
양팔 Mink 충돌 여유를 검사한다. `DIRECT_TELEOP_READY`는 Recovery 생략 후보라는
뜻일 뿐이며 실제 명령 승인은 아니다. 결과는
`logs/runtime/g1_startup_precheck.json`에 저장된다.

`EDIT_G1_STARTUP_READY_POSE.bat`는 실제 G1과 연결하지 않고 MuJoCo에서 오른팔
7관절 준비자세를 편집한다. `1~7`로 관절 선택, `←/→` 또는 `A/D`로 각도 변경,
`,/.`로 증감 단위 변경, `S`로 저장한다. 저장 시 Safety Gate 관절 범위와
Mink의 12 mm 정적 충돌 여유를 검사하지만, 저장 후에는 반드시
`TEST_G1_STARTUP_RECOVERY_OFFLINE.bat`으로 실제 캡처 자세부터 새 준비자세까지의
전체 경로를 다시 검증해야 한다.

## Hardware safety validation

```powershell
.\tools\START_G1_GATE7_LIVE_DRY_RUN.bat
.\tools\TEST_G1_GATE5_READ_ONLY.bat
.\tools\TEST_G1_GATE6_HOLD_OFFLINE.bat
.\tools\TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat
.\tools\TEST_G1_GATE7_LIVE_DRY_RUN.bat
.\tools\TEST_G1_HARDWARE_SAFETY_GATE.bat
.\tools\TEST_MINK_SAFETY_PIPELINE.bat
.\tools\TEST_FAKE_MINK_SAFETY_E2E.bat
.\tools\TEST_G1_HARDWARE_STATE.bat
```

Gate 6 command publisher 경계는 구현되어 있으며, 사용자 확인을 거친 첫
`0.2`-weight measured-pose HOLD를 1회 완료했다. 영구 config는 다시 잠겨 있고
live Mink target 출력은 아직 수행하지 않았다. 하드웨어 검증 순서는
`hardware/g1_arm_bridge/HARDWARE_BRINGUP_CHECKLIST.md`를 따른다.

`START_G1_GATE5_READ_ONLY.bat`는 실제 `rt/lowstate` 측정 자세를 UDP 5007로
받아 같은 자세를 HOLD 요청으로 Safety Gate에 넣는다. 허용된 후보는 로그에만
기록하며 어디에도 전송하지 않는다. 상태와 이벤트는 각각
`logs/runtime/g1_gate5_lowstate_safety.json` 및 `.jsonl`에 저장된다.

`TEST_G1_GATE5_READ_ONLY.bat`는 G1 없이 이 경로와 250 ms stale 차단을
검증하고 `logs/test_results/g1_gate5_read_only.log`를 남긴다.

`TEST_G1_GATE6_HOLD_OFFLINE.bat`는 G1 없이 양팔 14축 HOLD 계약, Arm SDK
weight acquire/release, 허리·하체 명령 제외, hardware-output 잠금, 설치된
Unitree SDK2의 35-slot `LowCmd_`와 CRC를 검사한다.

`TEST_G1_GATE6_INTERRUPT_RELEASE_OFFLINE.bat`는 G1과 SDK 없이 최대 weight
`0.2`에서 Ctrl+C가 요청됐다고 가정하여 2초 동안 weight를 0으로 낮추고
25개의 zero-weight frame을 보내는 계약을 검증한다. 양팔 목표가 측정 시작
자세에서 변하지 않고 하체·허리 명령이 비활성인지도 검사한다.
`START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat`는 같은 계약의 향후 지상 물리
시험 전용 실행기지만 별도 config가 `hardware_output_authorized=false`라 현재
실행은 차단된다. 명시적 물리 시험 승인 전에는 이 잠금을 해제하지 않는다.

`TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat`는 G1 없이 UDP 5008 strict packet,
순번/watchdog, 오른팔 active target, 의도적 pinch 즉시 복귀와 의도치 않은 해제
10초 후 Regular 양팔 minimum-jerk 복귀, 전체 경로 collision 여유와 35-slot
arm-only 후보 frame을 검사한다. Unitree SDK, DDS entity, publisher 또는 robot
command를 만들지 않는다.

`START_G1_GATE7_LIVE_DRY_RUN.bat`는 Unity와 현재 virtual-center Mink 제어기를
그대로 실행하면서 별도 창에서 UDP 5008 strict stream을 250 Hz Gate 7 상태
머신에 넣는다. 기본 `mink` 측정 모드는 승인된 후보를 이상적으로 추종시켜 G1
없이 긴 VR 동작을 검사한다. 이벤트와 종료 요약은
`logs/test_results/g1_gate7_live_dry_run_*`에 저장한다. 기존
과거 호환 wrapper는 제거했으며 Gate 7 검증은 위 런처를 직접 사용한다.

Gate 7이 승인한 후보는 localhost UDP `5012`로 기존 MuJoCo 창에도 전달된다.
평소 `TRACK_MINK_RIGHT` 상태는 기존 Mink IK가 계속 담당하고, 연동 해제 후
`REGULAR_RETURN`과 `REGULAR_HOLD`만 시뮬레이션 표시 자세에 적용된다. 따라서
실제 G1 없이도 10초 HOLD와 Regular 자세 복귀를 한 창에서 확인할 수 있다.
이 패킷은 실제 SDK/DDS 명령 경로와 연결되지 않는다.

`TEST_G1_GATE7_LIVE_DRY_RUN.bat`는 core 상태 머신과 실제 localhost UDP E2E를
자동 검증하고 저장 로그 경로를 출력한다. `gate7_live_dry_run.py`의 선택적
`--measured-source lowstate --lowstate-port 5007` 모드는 실제 G1 read-only
측정값을 사용할 수 있지만, LowState가 250 ms보다 오래되거나 후보 오차가 10도를
넘으면 frame을 제거한다.

실제 G1을 연결한 읽기 전용 Gate 7 비교는 다음 전용 실행기를 사용한다.

```powershell
.\tools\START_G1_GATE7_LOWSTATE_DRY_RUN.bat
```

이 실행기는 WSL에서 `rt/lowstate`만 구독하여 29개 관절값을 UDP `5007`로
100 Hz 전달하고, Gate 7을 `measured-source=lowstate`,
`trajectory-generator=ruckig`, `simulate-command-following`으로 실행한 뒤 기존
Unity/Mink/MuJoCo 경로를 연다. LowState는 초기 자세, 통신 freshness와 motor mode
검증에 사용하고, 무출력으로 G1이 정지해 있는 동안에는 명령을 수행했다고 가정한
shadow 자세로 후보 추종을 계산한다. 실제 후보와 동일한 40/100 deg/s Ruckig 제한을
사용한다. LowState가 250 ms 이상 오래되면 후보 frame을 제거한다. DDS publisher와
실제 G1 command 경로는 만들지 않는다.

실제 어깨 authority 시험을 기다리는 동안 Gate 7 물리 경로의 기반은 다음으로
오프라인 검사한다.

```powershell
.\tools\TEST_G1_GATE7_HARDWARE_FOUNDATION_OFFLINE.bat
```

이 검사는 Windows localhost UDP `5008` packet을 검증해 WSL UDP `5013`으로
전달하는 relay, 물리 어댑터 설정, authority acquire/release 수학과 publisher
생성 순서를 검사한다. Unitree SDK/DDS publisher를 만들지 않고 결과를
`logs/test_results/g1_gate7_hardware_foundation_*.log`에 저장한다.

실제 두 UDP 포트와 가상 LowState를 포함한 전체 무출력 E2E는 다음으로 실행한다.

```powershell
.\tools\TEST_G1_GATE7_VIRTUAL_HARDWARE_E2E.bat
```

합성 Mink packet이 실제 localhost UDP `5008` relay를 지나 UDP `5013`으로
전달된다. 정상 추종, 중복 sequence와 malformed JSON 거부, collision
`SAFETY_HOLD`, 10초 뒤 Regular 복귀, LowState stale frame 제거, 5초 authority
획득과 2초 release 및 zero frame 25회 계약을 가상으로 검사한다. 실제 후보와
동일한 Ruckig 0.19.4 및 40/100 deg/s, 가속도·jerk 배율 1.0도 사용한다.

가장 최근 Quest 캡처를 실제 후보 제한으로 다시 계산하는 검사는 다음과 같다.

```powershell
.\tools\TEST_G1_GATE7_RUCKIG_HARDWARE_PROFILE_OFFLINE.bat
```

속도·가속도·jerk 초과가 하나라도 있으면 실패한다. Unitree SDK, DDS publisher와
robot command는 사용하지 않고 JSON/HTML 결과를 `logs/quality/`에 저장한다.

향후 실제 경로의 런처는 `START_G1_GATE7_LIVE_HARDWARE.bat`으로 미리 분리했다.
현재 `config/g1_gate7_live_hardware_output.json`의
`hardware_output_authorized=false`에서 첫 단계가 차단된다. 제한된 어깨 시험이
승인되기 전에는 이 값을 변경하지 않는다. 나중에 실행할 때 필요한 Ruckig는 G1이
아니라 노트북 WSL에 설치하며, 런처가 정확히 0.19.4인지 먼저 검사한다.

첫 실제 VR 명령은 표준 프로필과 분리한 다음 두 파일로 준비한다.

```powershell
.\tools\TEST_G1_GATE7_FIRST_LIVE_OFFLINE.bat
.\tools\START_G1_GATE7_FIRST_LIVE_TRIAL.bat
```

첫 파일은 G1 없이 전용 프로필, 시작 자세 대비 3도 제한, publisher 이전 검사 순서와
가상 UDP E2E를 검증한다. 두 번째 파일은 `--first-live` 프로필로 공통 실기 실행기를
호출하지만, 현재 `g1_gate7_first_live_hardware_output.json`의 잠금에서 즉시
중단된다. 전용 프로필은 weight 1.0, 20초, 관절 속도 10/25 deg/s, 가속도
20/50 deg/s2, jerk 80/200 deg/s3이다. 명령 관절 중 하나라도 publisher 획득
자세에서 3도를 넘으려 하면 해당 frame은 송신 전에 거부되고 release 절차로 간다.

## VR Mink 입력 기록과 회귀 재생

```powershell
.\tools\TEST_G1_GATE7_CAPTURE_REPLAY_OFFLINE.bat
.\tools\START_G1_GATE7_VR_RECORDING.bat
.\tools\TEST_G1_GATE7_LATEST_CAPTURE_REGRESSION.bat
```

첫 파일은 G1과 VR 없이 실제 localhost socket으로 기록·전달·재생과 deterministic
Gate 7 trace를 검증한다. 두 번째 파일은 recorder가 UDP `5008`을 받고 strict
packet만 JSONL에 저장하면서 Gate 7 dry-run의 UDP `5014`로 전달한다. 대표 동작을
마친 뒤 recorder 창에서 `Ctrl+C`를 먼저 눌러
`logs/captures/g1_mink_capture_*.jsonl` 경로를 확인한다.

세 번째 파일은 가장 최근 캡처를 250 Hz Gate 7에 deterministic하게 재생한다.
처음 실행하면 같은 이름의 `.baseline.json`을 만들고, 이후 실행은 capture payload,
Gate 7 config, 상태별 tick 수, candidate/denied frame 수와 전체 관절 target trace
SHA-256을 비교한다. 마지막 packet 이후 13초를 추가 재생하므로 stale 판정,
10초 HOLD, minimum-jerk 복귀와 최종 `REGULAR_HOLD`까지 포함된다.

캡처는 원본 UDP bytes를 Base64로 보존한다. 실제 UDP 재생 시에는 관절값과 상태를
유지하고 session/sequence/timestamp만 새 실행에 맞게 바꿔 이전 session 순번과
충돌하지 않게 한다. 이 전체 경로에는 Unitree SDK나 DDS publisher가 없다.

실제 연결 전에 fail-closed 동작을 한 번에 재검사하려면 다음을 실행한다.

```powershell
.\tools\TEST_G1_GATE7_FAULT_MATRIX_OFFLINE.bat
.\tools\TEST_G1_GATE7_LATEST_CAPTURE_FAULT_MATRIX.bat
```

이 검사는 G1과 VR 없이 짧은 packet gap, timeout을 넘긴 packet 유실, 추적 상실,
workspace 이탈, collision 제한, duplicate/reordered sequence, stale LowState를
주입한다. 짧은 유실은 추종을 유지하고, fault는 현재 target을 고정하며, 정상 입력이
돌아오면 추종을 재개하고, 10초 동안 복구되지 않으면 minimum-jerk Regular 복귀를
완료해야 통과한다. SDK, DDS entity, publisher 및 로봇 명령은 생성하지 않는다.
첫 파일은 내장 합성 입력을 사용한다. 두 번째 파일은 가장 최근 실제 VR 캡처에서
active packet을 가져와 같은 fault matrix를 적용하므로, VR 기록 후 한 번 실행한다.

실제 Quest 캡처의 품질 리포트와 MuJoCo 재생은 다음으로 실행한다.

```powershell
.\tools\ANALYZE_G1_GATE7_LATEST_CAPTURE.bat
.\tools\VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat
.\tools\VIEW_G1_GATE7_LIMITED_CAPTURE_MUJOCO.bat
```

분석기는 raw Mink IK의 관절 범위, 속도, 위치/회전 오차, 충돌거리와 active 구간을
계산하고, 동일 입력을 250 Hz Gate 7 ideal-following candidate에 넣어 속도·가속도·
jerk를 설정값과 비교한다. JSON과 HTML은 `logs/quality/`에 저장된다. 뷰어는 긴
idle 구간을 생략하고 첫 engage부터 마지막 tracking-loss까지 앞뒤 1초를 포함한
구간만 MuJoCo에서 반복 재생한다. 두 경로 모두 G1, Unitree SDK, DDS 및 publisher를
사용하지 않는다.

세 번째 뷰어는 활성 Gate 7을 바꾸지 않는 Ruckig 0.19.4 실험 경로다. 모든 명령
상태를 250 Hz 온라인 궤적으로 만들며 관절별 도착 시각은 독립적이다. 현재 오프라인
비교 프로파일은 50/125 deg/s, 기존 대비 가속도 3배, jerk 6배다. 원본 뷰어와 제한
뷰어를 차례로 실행해 반응성과 부드러움을 비교한다. 이 수치는 실제 G1 설정에
적용되지 않았고 실험 제한기는 물리 명령 경로와 연결되어 있지 않다. `ruckig`가
없으면 BAT가 `py -3.11 -m pip install ruckig==0.19.4`를 안내한다.

`PREPARE_G1_GATE6_HOLD.bat`는 연결된 G1의 현재 Regular Mode와
`rt/lowstate`를 읽어 양팔 measured-pose HOLD 후보를 만들 수 있는지만
검사한다. `ChannelPublisher`를 만들지 않고 실제 명령을 보내지 않는다. 현재
실제 출력은 `config/g1_gate6_hold.json`의
`hardware_output_authorized=false`로 차단되어 있다.

## Bounded physical right-arm interactive publish test

```powershell
.\tools\TEST_G1_RIGHT_ARM_JOG_OFFLINE.bat
.\tools\START_G1_RIGHT_ARM_JOG_MUJOCO.bat
```

첫 파일은 G1 없이 설정, 35-slot frame, 오른팔 인덱스 `22~28`, 최대 ±20도 범위,
어깨·팔꿈치 2.5 deg/s 및 손목 5 deg/s 속도 제한과 하체/허리 비활성 불변식을
검사한다. 두 번째 파일은 실제
G1이 평평한 지면에서 Regular Mode일 때만 사용한다. 실행기는 MotionSwitcher
`CheckMode`, fresh startup precheck를 수행한 뒤 실제 29관절 자세에서 일곱 관절의
양방향 경로를 1도씩 MuJoCo로 검사한다. 각 관절에는 최대 ±20도 안에서 첫 충돌
실패 직전까지의 비대칭 허용 범위가 발급된다. 이후 LowState를
`VIEW_G1_LIVE_MUJOCO.bat`으로 표시하고 두 확인 문구가 정확히 입력된 경우에만
`rt/arm_sdk` publisher를 생성한다. publisher 직전 자세가 경로검사 자세에서
양팔 기준 1도 넘게 달라지면 stale-path 사용을 막고 종료한다.

조작은 현재 터미널에서 `1~7`로 관절을 실시간 선택하고 `Up`/`Down`으로 한 번에
1도씩 목표를 바꾼다. 다른 관절을 선택하면 기존 관절이 precheck 시작 자세로
복귀한 뒤 새 관절로 전환된다. 다음 step 목표가 실측 관절보다 2도 넘게 앞서면
`INPUT BLOCKED`로 해당 키 입력만 무시한다. 실제 목표는 관절별 속도와 발급된
방향별 범위로 제한되며, 이번 단계의 Jog 전용 Arm SDK weight 상한은 0.25다.
첫 관절을 선택하기 전에는 weight를 0으로 유지한다. `1~7` 선택과 현재 자세
재검증이 성공한 시점부터 ramp와 30초 조작 시간이 시작되며, 15초 동안 선택하지
않으면 권한을 획득하지 않고 종료한다.
`Q` 또는 30초 만료 시
weight를 1초 동안 0으로 내리고 zero-weight frame 25개를 보낸 뒤 종료한다. 실제
테스트 중에는 조종기를 들고 `L2+B` 비상정지를 즉시 사용할 수 있어야 한다.
소프트웨어는 지면 접촉과 실제 균형 상태를 판별하지 않는다. 물리 출력 전에는
G1이 평평한 지면에서 두 발로 자립하여 Regular Mode 균형 제어 중인지 사람이
별도로 확인해야 하며, 매달린 상태의 준비 결과로 출력 단계를 승인하지 않는다.

### Full-authority shoulder-pitch tracking trial

`0.25` weight에서 명령 대비 실측 움직임이 작았던 원인을 분리 확인할 때만 다음
전용 경로를 사용한다. 기존 7관절 Jog를 대체하지 않는다.

```powershell
.\tools\TEST_G1_SHOULDER_PITCH_FULL_AUTHORITY_OFFLINE.bat
.\tools\START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat
```

물리 런처에서 `1`을 누르면 현재 LowState의 양팔 14관절 자세를 고정 목표로
저장하고 Arm SDK weight를 5초 동안 `0 -> 1`로 올린다. 이 구간에는 방향키가
차단된다. weight가 1이고 14관절 최대 오차가 1.5도 이하일 때만 `[ARMED]`가
출력되며, 이후 오른쪽 shoulder pitch만 시작 자세 기준 `+/-1도`, `1 deg/s`로
조작할 수 있다. ARMING이 10초 안에 안정되지 않거나 LowState/mode/충돌 permit
조건이 깨지면 종료하고 zero-weight frame을 반복 전송한다. 실제 로봇 시험은
지상 Regular Mode, 주변 비움, 조종기 `L2+B` 준비 상태에서만 수행한다.

## Network setup and recovery

```powershell
.\tools\DETECT_G1_NETWORK.bat
.\tools\CONFIGURE_G1_ETHERNET.bat
.\tools\ALLOW_G1_DDS_WSL.bat
.\tools\ALLOW_G1_LOWSTATE_TO_WINDOWS.bat
.\tools\RESTORE_G1_ETHERNET_DHCP.bat
```

관리자 권한 PowerShell 구현 파일은 BAT가 내부적으로 호출하므로 삭제하지 않는다.

## Failure guidance

배치파일은 실패 시 `[FAIL]`, `[ERROR]`, `[BLOCKED]`, `[FAULT]`만 출력하고
끝내지 않는다. 바로 다음 줄의 `[ACTION]`에 사용자가 확인하거나 실행할 조치를
표시한다. 테스트 결과를 파일로 저장하는 배치파일은 동일한 `[ACTION]` 문구도
결과 로그에 함께 기록한다.

이 규칙은 `backend/tests/test_batch_failure_guidance.py`가 루트와 `tools/`의
모든 배치파일을 검사해 누락을 막는다.

## Camera foundation

```powershell
.\tools\VERIFY_HEAD_CAMERA_FOUNDATION.bat
```

현재 controller와 연결되지 않은 과거 role-split, A/B 비교, 단일 카메라 preview,
torso posture BAT와 전용 Python 코드는 제거했다. 현재 실행·검증 경로만 유지한다.

실제 G1 카메라만 따로 확인할 때는 다음 읽기 전용 런처를 사용한다.

```powershell
.\tools\START_G1_CAMERA_TO_UNITY.bat
```

평소에는 루트의 `START_VR_HAND_TO_MUJOCO.bat`이 G1 Ethernet을 확인하고 이
브리지를 자동으로 시작한다. WSL의 공식 SDK2 `VideoClient.GetImageSample()`이
카메라 프레임을 읽어 Unity TCP 5011로 전달한다.

G1 전원이 없을 때 동일한 Unity PiP 경로를 검증하려면 다음을 사용한다.

```powershell
.\tools\TEST_CAMERA_REPLAY_TO_UNITY.bat
```

Python 3.11에서 생성한 움직이는 합성 JPEG를 실제 카메라와 동일한 `G1CM`
패킷으로 loopback TCP 5011에 보낸다. 영상에는 `OFFLINE REPLAY`가 항상 표시되며
Unitree SDK, DDS와 로봇 명령을 사용하지 않는다. 종료하면 결과가
`logs/camera/camera_offline_replay_*.json`에 저장되고 정확한 경로가 출력된다.
반환한 JPEG를 로컬 TCP `127.0.0.1:5011`로 전달하며, Unity Play 상태의
`G1HeadCameraPiP`가 이를 표시한다. 이 경로는 영상 수신 전용이고 DDS publisher,
IK target 또는 로봇 명령을 만들지 않는다.
