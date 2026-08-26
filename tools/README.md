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
.\tools\CALIBRATE_WRIST_FRAME.bat
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
.\tools\TEST_G1_STARTUP_RECOVERY_OFFLINE.bat
```

`START_G1_READ_ONLY.bat`는 WSL에서 `192.168.123.99`가 설정된 interface를
자동 탐색하고 `rt/lowstate`만 구독한다. DDS publisher와 motor command는 없다.

## Hardware safety validation

```powershell
.\tools\START_MINK_G1_SAFETY_DRY_RUN.bat
.\tools\TEST_G1_HARDWARE_SAFETY_GATE.bat
.\tools\TEST_G1_HOLD_DRY_RUN.bat
.\tools\TEST_MINK_SAFETY_PIPELINE.bat
.\tools\TEST_FAKE_MINK_SAFETY_E2E.bat
.\tools\TEST_G1_HARDWARE_STATE.bat
```

실제 G1 command publisher는 아직 없다. 하드웨어 검증 순서는
`hardware/g1_arm_bridge/HARDWARE_BRINGUP_CHECKLIST.md`를 따른다.

## Network setup and recovery

```powershell
.\tools\DETECT_G1_NETWORK.bat
.\tools\CONFIGURE_G1_ETHERNET.bat
.\tools\ALLOW_G1_DDS_WSL.bat
.\tools\ALLOW_G1_LOWSTATE_TO_WINDOWS.bat
.\tools\RESTORE_G1_ETHERNET_DHCP.bat
```

관리자 권한 PowerShell 구현 파일은 BAT가 내부적으로 호출하므로 삭제하지 않는다.

## Camera foundation

```powershell
.\tools\VERIFY_HEAD_CAMERA_FOUNDATION.bat
```

현재 controller와 연결되지 않은 과거 role-split, A/B 비교, 단일 카메라 preview,
torso posture BAT와 전용 Python 코드는 제거했다. 현재 실행·검증 경로만 유지한다.
