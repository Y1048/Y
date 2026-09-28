# 새 PC에서 G1 Teleop 준비

이 문서는 빈 Windows PC에서 현재 **Quest 양손 + bimanual Mink/MuJoCo + Omni observation + G1 LowState/camera** 환경을 준비하는 순서다.

현재 통합 진입점:

```powershell
.\tools\START_G1_VR_TELEOP.bat
```

> 이 기본 BAT는 G1 모터 명령을 실행하지 않는다. 실제 물리 출력은 별도 hardware gate다.

## 1. 권장 환경

- Windows 10/11 x64
- Git for Windows
- Python 3.11 x64
- Unity Hub
- Unity Editor `6000.5.4f1`
- Meta Horizon Link
- Quest 2/3/3S
- Virtuix Omni Connect
- Windows OpenSSH Client
- G1 Ethernet 또는 폐쇄망

프로젝트는 `C:\G1_Teleop_Project`처럼 짧은 경로를 권장한다.

## 2. 저장소

```powershell
git clone <repo-url> C:\G1_Teleop_Project
cd C:\G1_Teleop_Project
```

`main`이 현재 source of truth다.

## 3. Python 환경

프로젝트 venv는 Git에 포함되지 않는다.

```powershell
.\tools\SETUP_G1_VR_TELEOP.bat
```

설치 없이 검사만:

```powershell
.\tools\SETUP_G1_VR_TELEOP.bat --check-only
```

현재 bimanual environment는 Python 3.11과 프로젝트 requirements를 사용한다.

## 4. Unity / Quest

1. Unity `6000.5.4f1` 설치
2. Meta Horizon Link 설치
3. Meta를 active OpenXR runtime으로 설정
4. Quest Hand Tracking 활성화
5. USB Link/Air Link 연결

Unity 프로젝트:

```text
Unity_G1_VR
```

첫 실행 또는 `Library/` 삭제 후에는 Unity가 package/import cache를 다시 생성하므로 시간이 걸릴 수 있다.

## 5. Omni

Omni Connect가 로컬 WebSocket을 제공해야 한다.

```text
ws://127.0.0.1:32123
```

기본 launcher에서 Omni worker는 `--dry-run` observation 모드다.

## 6. G1 네트워크

기본 launcher는 G1 host를 자동 선택할 수 있으며 TCP 22 SSH 연결을 사용한다.

대표 후보 주소는 현재 환경 설정에 따라 wired/closed-network 순으로 검사된다. 실제 주소는 `g1_portable_environment.py`의 선택 결과를 따른다.

OpenSSH 확인:

```powershell
ssh -V
```

## 7. 기본 실행

```powershell
.\tools\START_G1_VR_TELEOP.bat
```

launcher가 수행하는 것:

- Python dependency 확인
- G1 host 확인
- observation worker 시작/재사용
- bimanual arm worker 시작
- Omni dry-run 시작
- camera 시작/재사용
- Unity Editor 시작/재사용

수행하지 않는 것:

- Unity Play 자동 시작
- G1 motor publisher 승인
- physical arm command 자동 실행

## 8. 현재 bimanual 계약

```text
Unity -> Python : UDP 127.0.0.1:5020
schema          : g1.bimanual.unity.sim.v4
input frame     : unity_display_world_v1
compute         : 60 Hz
arms            : 14 DoF total
```

## 9. 현재 control profile

```text
proximal velocity 90 deg/s
wrist velocity    180 deg/s
acceleration      90 deg/s²
tracking rate     1.0 /s
```

## 10. 카메라

기본 camera path:

```text
G1 VideoClient (eth0)
 -> SSH
 -> Windows g1_camera_ssh.py
 -> TCP 127.0.0.1:5011
 -> Unity PiP
```

PiP는 G1 `RobotRoot` 기준이다.

## 11. check-only

```powershell
.\tools\START_G1_VR_TELEOP.bat --check-only
```

주의: `--host auto`에서는 G1 후보 주소의 TCP 22 reachability도 검사하므로 G1 네트워크가 완전히 끊겨 있으면 실패할 수 있다.

## 12. 검증

설치 후 root `README.md`의 bimanual 80-test 묶음과 `CODE_INDEX --check`를 실행한다.

## 13. 물리 출력

실제 G1 arm command를 테스트할 때는 이 setup 문서가 아니라 `hardware/g1_arm_bridge/HARDWARE_BRINGUP_CHECKLIST.md`를 따른다.
