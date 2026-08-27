# Project Tools

`tools/`에는 현재 G1 teleoperation에 필요한 실행, 검증, 네트워크 복구용 BAT만 둔다.

## Live teleoperation

기본 실행은 프로젝트 루트의 다음 파일을 사용한다.

```powershell
.\START_VR_HAND_TO_MUJOCO.bat
```

## Quest and Unity

```powershell
.\tools\BUILD_AND_INSTALL_VR_APK.bat
.\tools\REPLAY_LIVE_WORKSPACE.bat
```

## Frame and IK validation

```powershell
.\tools\TEST_MINK_WRIST_FRAME.bat
.\tools\TEST_G1_MINK_FK_PARITY.bat
```

## Hardware read-only and synchronization

```powershell
.\tools\START_G1_READ_ONLY.bat
.\tools\START_MINK_G1_HARDWARE_SYNC.bat
.\tools\START_G1_GATE5_READ_ONLY.bat
.\tools\EDIT_G1_STARTUP_READY_POSE.bat
.\tools\TEST_G1_STARTUP_RECOVERY_OFFLINE.bat
.\tools\VIEW_G1_STARTUP_RECOVERY.bat
```

`START_G1_READ_ONLY.bat`는 WSL에서 `192.168.123.99`가 설정된 interface를
자동 탐색하고 `rt/lowstate`만 구독한다. DDS publisher와 motor command는 없다.

`EDIT_G1_STARTUP_READY_POSE.bat`는 실제 G1과 연결하지 않고 MuJoCo에서 오른팔
7관절 준비자세를 편집한다. `1~7`로 관절 선택, `←/→` 또는 `A/D`로 각도 변경,
`,/.`로 증감 단위 변경, `S`로 저장한다. 저장 시 Safety Gate 관절 범위와
Mink의 12 mm 정적 충돌 여유를 검사하지만, 저장 후에는 반드시
`TEST_G1_STARTUP_RECOVERY_OFFLINE.bat`으로 실제 캡처 자세부터 새 준비자세까지의
전체 경로를 다시 검증해야 한다.

## Hardware safety validation

```powershell
.\tools\START_MINK_G1_SAFETY_DRY_RUN.bat
.\tools\TEST_G1_GATE5_READ_ONLY.bat
.\tools\TEST_G1_HARDWARE_SAFETY_GATE.bat
.\tools\TEST_G1_HOLD_DRY_RUN.bat
.\tools\TEST_MINK_SAFETY_PIPELINE.bat
.\tools\TEST_FAKE_MINK_SAFETY_E2E.bat
.\tools\TEST_G1_HARDWARE_STATE.bat
```

실제 G1 command publisher는 아직 없다. 하드웨어 검증 순서는
`hardware/g1_arm_bridge/HARDWARE_BRINGUP_CHECKLIST.md`를 따른다.

`START_G1_GATE5_READ_ONLY.bat`는 실제 `rt/lowstate` 측정 자세를 UDP 5007로
받아 같은 자세를 HOLD 요청으로 Safety Gate에 넣는다. 허용된 후보는 로그에만
기록하며 어디에도 전송하지 않는다. 상태와 이벤트는 각각
`logs/runtime/g1_gate5_lowstate_safety.json` 및 `.jsonl`에 저장된다.

`TEST_G1_GATE5_READ_ONLY.bat`는 G1 없이 이 경로와 250 ms stale 차단을
검증하고 `logs/test_results/g1_gate5_read_only.log`를 남긴다.

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
