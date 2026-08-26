# Project Tools

`tools/`에는 G1 teleoperation의 실행, offline regression, collision 진단, Unity/Quest build, hardware dry-run용 Windows BAT 파일이 모여 있다.

파일 수가 많으므로 목적별로 구분해서 사용한다.

## 1. 현재 IK Live 실험

### Virtual Wrist Center

```powershell
.\START_VR_HAND_TO_MUJOCO.bat --smooth
```

현재 최신 실험 controller:

```text
MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py
```

내부 translation은 `right_wrist_roll_link`, orientation과 외부 Unity frame은 `right_wrist_yaw_link`를 사용한다.

### 이전 Role-Split 실험

```powershell
.\tools\TEST_MINK_G1_ROLE_SPLIT.bat
```

virtual-center 이전 role-split/hysteresis behavior 비교용이다.

## 2. IK Offline Regression

VR/Unity/Quest 없이 Python + MuJoCo + Mink만으로 검증한다.

### 기본 role-split regression

```powershell
.\tools\TEST_MINK_ROLE_SPLIT_REGRESSION.bat
```

Synthetic roll/pitch/yaw target에 대해:

```text
position error
orientation error
shoulder/elbow motion
wrist motion
joint velocity
wrist-limit margin
collision clearance
```

를 측정한다.

### Virtual-center A/B

```powershell
.\tools\TEST_MINK_VIRTUAL_WRIST_CENTER_COMPARE.bat
```

```text
A = current yaw-link pose formulation
B = virtual wrist center position + yaw-link orientation
```

을 동일 target에서 비교한다.

### Broad sweep

```powershell
.\tools\TEST_MINK_VIRTUAL_WRIST_CENTER_SWEEP.bat
```

여러 start posture, single-axis/mixed rotation, small translation에 대해 A/B를 대량 비교한다.

이 sweep은 controller 방향을 비교하기 위한 diagnostic이며 개별 tracking/collision aggregate를 실제 하드웨어 안전 인증값으로 사용하지 않는다.

## 3. Collision 진단

### Baseline collision

```powershell
.\tools\TEST_MINK_BASELINE_COLLISIONS.bat
```

여러 nominal start posture에서 시작부터 가까운 collision pair가 있는지 확인한다.

### Current controller collision ON/OFF

```powershell
.\tools\TEST_MINK_COLLISION_INFLUENCE.bat
```

동일 wrist rotation을 CollisionAvoidanceLimit ON/OFF로 돌려 proximal motion의 원인이 kinematic coupling인지 collision avoidance인지 분리한다.

### Virtual-center collision ON/OFF

```powershell
.\tools\TEST_MINK_VIRTUAL_CENTER_COLLISION_INFLUENCE.bat
```

virtual-center formulation에서 같은 검증을 한다.

### Pure-yaw geometry trace

```powershell
.\tools\TEST_MINK_VIRTUAL_CENTER_YAW_COLLISION_GEOMETRY.bat
```

collision avoidance를 끄고 pure yaw trajectory를 추적하면서 실제 MuJoCo geom distance를 측정한다.

확인된 대표 결과:

```text
right hip ↔ right rubber hand
yaw 40° : +24.95 mm
yaw 50° :  +0.40 mm
yaw 60° : -20.21 mm
yaw 70° : -31.42 mm
```

따라서 큰 positive yaw에서 collision avoidance가 팔을 움직이는 것은 실제 hand-hip penetration을 피하기 위한 정상 동작이다.

## 4. Frame / FK 검증

```powershell
.\tools\TEST_MINK_WRIST_FRAME.bat
.\tools\TEST_G1_MINK_FK_PARITY.bat
```

`TEST_G1_MINK_FK_PARITY.bat`는 동일 7 joint 값에서 Unity G1 rig와 MuJoCo G1의 `right_wrist_yaw_link` FK가 일치하는지 확인한다.

Frame 문제를 추적할 때 IK gain을 바꾸기 전에 이 계열을 먼저 확인한다.

## 5. Fake input / End-to-End

```powershell
.\tools\TEST_FAKE_VR_TO_MUJOCO.bat
.\tools\DIAGNOSE_FAKE_TELEOP.bat
```

Quest 없이 synthetic hand/UDP input으로 controller path를 확인한다.

## 6. Hardware Safety

실제 G1 command publisher는 아직 없다. 아래 도구는 read-only/sync/safety/dry-run 용도다.

```powershell
.\tools\START_G1_READ_ONLY.bat
.\tools\ALLOW_G1_LOWSTATE_TO_WINDOWS.bat
.\tools\START_MINK_G1_HARDWARE_SYNC.bat
.\tools\START_MINK_G1_SAFETY_DRY_RUN.bat
.\tools\TEST_G1_HARDWARE_SAFETY_GATE.bat
.\tools\TEST_G1_HARDWARE_STATE.bat
.\tools\TEST_FAKE_MINK_SAFETY_E2E.bat
.\tools\TEST_G1_STARTUP_RECOVERY_OFFLINE.bat
```

`START_G1_READ_ONLY.bat`는 WSL에서 `192.168.123.99`가 설정된 interface를 자동 탐색하고 `rt/lowstate`만 구독한다. DDS publisher와 motor command output은 없다.

`TEST_G1_STARTUP_RECOVERY_OFFLINE.bat`는 캡처된 실제 rest pose에서
Mink QP의 body-escape 및 ready-pose 수렴을 MuJoCo 안에서만 검증한다.
네트워크 소켓, Unitree SDK, DDS publisher, motor command를 사용하지 않는다.

실기 순서는 `hardware/g1_arm_bridge/HARDWARE_BRINGUP_CHECKLIST.md`를 따른다.

## 7. Quest / Unity

Quest APK build/install, frame calibration 등 Unity 관련 BAT도 이 폴더에 있다.

예:

```powershell
.\tools\BUILD_AND_INSTALL_VR_APK.bat
.\tools\CALIBRATE_WRIST_FRAME.bat
```

Unity project 자체 설명은 `Unity_G1_VR/README.md`를 참고한다.

## 8. Camera / 기타 검증

머리 카메라 simulation/capture와 posture 관련 보조 BAT도 존재한다.

예:

```powershell
.\tools\START_HEAD_CAMERA_SIMULATION.bat
.\tools\CAPTURE_HEAD_CAMERA_PREVIEW.bat
.\tools\CAPTURE_TORSO_JOINT_POSTURE.bat
```

현재 오른팔 teleoperation IK를 수정할 때는 위의 IK/Collision/Frame regression 도구를 우선 사용한다.

## 권장 개발 순서

IK를 수정할 때 매번 VR로 바로 확인하지 않는다.

```text
1. 코드 수정
2. Offline regression
3. A/B 또는 collision diagnostic
4. FK/frame test
5. 수치가 개선된 경우에만 Unity/Quest live test
6. hardware 관련 변경은 별도 safety dry-run
```

이 순서가 현재 프로젝트의 기본 검증 방식이다.
