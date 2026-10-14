# 새 PC·다른 G1/Quest/Insta360 준비

현재 사용 경로는 **Windows Unity Editor + Quest Link**다. APK/ADB 설정은 이 경로에 필요하지 않다. Windows EXE만으로 동일한 손 추적이 검증된 상태는 아니다.

## 가져갈 것

- 처음 쓰는 PC: `git clone https://github.com/Y1048/Y.git G1_Teleop_Project`
- 이미 clone한 PC: 사용자 변경을 보존하고 `git pull --ff-only origin main`
- Python, IK 패키지, H264 디코더는 저장소의 `runtime/python`에 포함된다. BAT만 복사하지 않는다.
- G1 내부 프로그램·정책·라이브러리는 PC clone에 포함되지 않는다. 사용자 계획대로 G1 파일 복제는 별도 USB 단계다.

## 별도 준비

| 항목 | 필요한 준비 | 자동화 범위/주의 |
|---|---|---|
| Windows | Windows 11 x64, OpenSSH client 또는 Git for Windows의 SSH | Linux/macOS/Windows ARM용 runtime이 아님 |
| Unity | `Unity_G1_VR/ProjectSettings/ProjectVersion.txt`와 같은 Editor, 현재 6000.5.4f1, 라이선스 활성화 | 표준 설치 경로 자동 탐색. 다른 경로는 `UNITY_EXE` 지정 |
| Unity 패키지 | 출발 전에 프로젝트 최초 임포트·컴파일 완료 | 새 PC 최초에는 인터넷과 패키지 다운로드가 필요할 수 있음 |
| Quest | Meta Horizon Link 설치, 새 Quest 페어링·Link 연결·손 추적 확인 | 시리얼 번호 고정 없음. 새 장비 연결/권한은 직접 준비 |
| Omni | Omni Connect 설치·실행, 실제 Omni Bluetooth 연결 | `127.0.0.1:32123` 연결과 실제 새 샘플 수신 확인. 포트 열림만으로 센서 정상 판정 불가 |
| Insta360 | G1 USB 연결, 장치 권한, `v4l2-ctl`, H264 경로의 `fuser` | 시리얼 고정 없이 Insta360 video-index0 한 대 선택. 여러 대면 중단 |
| 카메라 포맷 | 해당 제품이 H264 1920×1080 30fps를 제공해야 함 | 모델명이 같아도 장치 열거로 확인. 미지원이면 명시적 `--camera-codec mjpeg`; 네트워크 부하 재확인 |
| G1 네트워크 | 유선 또는 폐쇄망에서 SSH 접근 | auto는 `192.168.123.164`, `192.168.10.165`만 탐색. 다른 주소는 `--host 주소` |
| SSH 인증 | 새 PC의 키 등록, 새 G1의 호스트 신뢰 확인 | 개인 키를 여러 PC에 복제하지 않음. 일반 실행/카메라 실행에서 최초 비밀번호 등록 가능. 변경된 호스트 키는 먼저 장비 신원 확인 |
| G1 내부 | `unitree` 사용자, `/home/unitree/groot_onboard_runtime`, 제어기·heading·카메라 보조 파일, SDK/정책 의존성, 현재 `eth0` 구성 | 경로/사용자/interface는 현재 통합 계약이다. 임의 G1에 파일이 없으면 clone만으로 준비되지 않음 |

현재 SSH 카메라 경로에는 **WSL, PC FFmpeg 별도 설치, SteamVR을 추가하지 않는다.** 전용 Ethernet 주소 복구는 조건이 맞을 때 UAC를 요청하며, 불명확한 NIC는 임의로 변경하지 않는다. 방화벽 전체 해제 대신 해당 프로그램/필요 통신을 확인한다.

## 모터를 시작하지 않는 확인 순서

프로젝트 루트에서:

```powershell
.\runtime\python\python.exe -I -B tools\G1_PORTABLE.py check-runtime --pc-only
.\runtime\python\python.exe -I -B tools\G1_PORTABLE.py resolve-unity
.\START_G1_VR_TELEOP.bat --check-connections
```

다른 G1 IP라면 마지막 명령에 `--host 주소`를 붙인다. 연결 점검은 인증 등록·IP 변경·SDK 초기화·카메라 캡처·모터 출력을 하지 않는다. 초기 인증이 안 된 PC는 SSH 항목이 실패하는 것이 정상이다.

카메라만 확인할 때:

```powershell
.\TEST_G1_CAMERA.bat
```

종료는 페이지의 **카메라 종료** 버튼. 탭만 닫으면 수신은 계속된다. 통합 실행 전에 종료한다.

`--check-only`는 실행 계획 검사이며 Link 손 추적, Omni 실제 입력, UDP 수신, 로봇 동작 검증을 대신하지 않는다. 전체 실행은 `START_G1_VR_TELEOP.bat`; 새 제어기 시작 시 ACTUATE 확인이 있으므로 준비 검사 목적으로 일반 실행하지 않는다.

## 2026-10-14 확인과 남은 것

- 현재 노트북: bundled Python·IK 모델 구성·Unity 경로 확인 통과. Link/Omni Connect 설치 확인. 점검 순간 Omni 32123은 응답 없음.
- 현재 G1: SSH, 파일·장치 권한, H264 1080p30 열거, fuser 확인 통과. 카메라 단독 영상은 사용자 확인 완료.
- 아직 별도 확인: 새 PC 최초 임포트/Quest 손/Omni 입력/UDP 전달, 다른 시리얼 장비 실기, 통합 동시 부하, PTZ, 실제 로봇 제어.
- 팔 최종 LowCmd 기록은 별도 후보만 빌드돼 있고 통합 실행에서는 아직 비활성. 새 측정 전에 이 점을 해결해야 한다.

상세 실행 옵션: [Portable 안내](docs/PORTABLE_TELEOP_SETUP.md). 계측 상태: [최종 LowCmd 점검](docs/GROOT_ARM_COMMAND_OBSERVER_20261007.md).
