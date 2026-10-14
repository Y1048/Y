# 다른 PC에서 G1 Teleop 실행

## 핵심

이 프로젝트는 Python 실행 환경을 폴더 안에 포함한다.

```text
runtime/python/python.exe
runtime/python/Lib/site-packages/
runtime/python/RUNTIME_MANIFEST.json
```

따라서 다른 Windows PC로 옮길 때 **시스템 Python 설치, venv 생성, pip install은 필요하지 않다.** 프로젝트 폴더 전체를 복사하면 Python 쪽 환경도 같이 이동한다.

## 여전히 외부에 필요한 것

- Windows 11 x64
- 현재 Quest Link 양손 실기에는 프로젝트 `ProjectVersion.txt`의 Unity Editor가 필요하다. launcher가 자동 탐색하며 사용자가 Editor를 직접 조작할 필요는 없다
- prebuilt Windows player `Builds/Windows/G1Teleop.exe` 및 동반 파일은 standalone 진단용으로 유지한다
- 현재 운영은 Unity Editor + Link다. Quest APK/ADB는 추후 Editor 의존성을 제거하려는 별도 경로이며 이번 새 PC 준비의 필수 조건이 아니다
- Meta Quest / Link 환경과 필요한 드라이버
- Omni Connect
- working OpenSSH client (`ssh.exe`, `ssh-keygen.exe`): Windows OpenSSH 또는 Git for Windows OpenSSH
- G1 Ethernet 또는 closed network
- G1 onboard `/home/unitree/groot_onboard_runtime`에 heading controller와 executable `build/groot_balance_actuator`
- APK를 별도로 설치할 때만 ADB 준비가 필요하다

## 1. 폴더 복사 후 runtime 검사

```bat
runtime\python\python.exe -I -B tools\G1_PORTABLE.py check-runtime --pc-only
```

별도 setup BAT는 유지하지 않는다. 위 명령은 bundled runtime 자체만 사용해 PC-side Python 환경을 검사한다.
SSH 실행기는 `tools/g1_ssh_login.py`가 health check한다. `SSH_EXE`가 있으면 그 경로를 엄격히 사용하고, 자동 탐색에서는 Windows OpenSSH가 실행 불능이면 Git for Windows OpenSSH로 fallback한다.

검사 항목:

- CPython Embedded 3.11.9 x64
- runtime manifest/core hash
- exact package versions
- MuJoCo 3.12 model construction
- DAQP/QP backend
- 로컬 SSH camera prerequisite

실패하면 PC에서 pip install로 고치지 말고 **정상 프로젝트의 `runtime/python` 폴더를 통째로 복원**한다.

## 2. 실행

```bat
START_G1_VR_TELEOP.bat
```

검사만:

```bat
START_G1_VR_TELEOP.bat --check-only
```

BAT는 환경 로직을 갖지 않고 Embedded Python dispatcher만 호출한다. 기본 실행은 **Unity Editor를 자동 실행하고 launcher 요청을 받은 Editor가 자동으로 Play mode에 진입**하므로 사용자가 Play를 누를 필요가 없다. GROOT supervisor를 새로 시작해야 할 때만 `ACTUATE` 확인을 요구한다. motor output 없이 Editor/observation만 실행하려면 `START_G1_VR_TELEOP.bat --no-groot-actuation`을 사용한다. `--standalone`은 손 tracking이 필요 없는 Windows player 진단용이다. `--check-only`은 Editor/worker/GROOT를 시작하지 않는다.

Windows build는 `G1VRBuild.BuildWindows()`가 `resources.assets`의 로컬 Meta DevAgent access token/server address를 post-build 단계에서 제거하고, 유일 occurrence를 검증하지 못하면 fail closed한다. `DevAgentSettings.asset`의 로컬 값 자체는 build 과정에서 수정하지 않는다.

### 읽기 전용 연결 점검

```powershell
.\START_G1_VR_TELEOP.bat --check-connections
# 다른 주소라면:
.\START_G1_VR_TELEOP.bat --check-connections --host 10.50.1.8
```

이 옵션은 TCP/SSH로 실제 접속해 필수 파일과 장치 상태를 읽지만, IP 설정/UAC, 로그인 키 등록, Unity/작업 프로세스, 카메라 캡처, SDK/DDS 초기화, 제어기를 실행하지 않는다. 점검용 별도 수신기도 만들지 않는다. 일반 실행 전 새 환경에서 사용한다.

- auto는 192.168.123.164와 192.168.10.165 두 주소만 확인하며 유선을 우선한다. 임의 IP 탐색은 아니다. 연결에 사용된 PC IP도 출력한다.
- 기존 SSH 신뢰 정보와 unitree 키 로그인을 사용한다. 새 PC의 키 미등록, 새 G1의 미신뢰 호스트, 같은 IP의 다른 G1로 인한 호스트 키 변경, timeout을 구분한다. 인증 정보는 자동 변경하지 않는다.
- G1의 eth0, unitree_sdk2py 패키지 존재, GROOT 실행 파일/heading 소스/카메라 보조 파일 존재를 검사한다. 실행 파일 내부 동작·정책·라이브러리 호환성 검증은 아니다.
- Insta360 video-index0 장치가 한 대인지, 읽기/쓰기 권한과 v4l2-ctl이 있는지 확인한다. 여러 대면 의도한 장치를 명확히 선택하도록 실패로 표시한다. 선택한 codec의 1920×1080 30fps 열거도 읽기 전용으로 확인하며, 기본 H264에는 fuser 존재도 요구한다. `--check-connections --camera-codec mjpeg`는 기존 MJPEG 지원을 검사한다. 포맷 설정/캡처는 하지 않는다.
- **PASS는 준비 조건 검사 통과**다. UDP 수신 ACK, 실제 JPEG 영상·PTZ, Quest 손 인식, 모터 동작은 검증하지 않는다.
- 결과는 logs/test_results/connection_checks/connection_날짜_시각.json에 보존한다. 불완전하면 종료 코드 1이다.

기존 --check-only는 실행 계획 검사다. --check-connections와 동시에 사용할 수 없다. 필수 파일 복제가 필요한 경우의 G1 내부 파일 복제 작업은 별도 단계로 남긴다.

### 새 PC의 Unity 최초 임포트

최초 실행에서는 패키지 다운로드·프로젝트 임포트·스크립트 컴파일을 기다린다. 프로젝트 파일만 복사해도 Unity 설치/라이선스, Meta Link 연결과 최초 패키지 준비까지 자동 완료되는 것은 아니다. 현장에 가져가기 전에 새 PC에서 한 번 열어 준비한다.

자동 Play 요청은 2분 대기 만료 대신 현재 Unity 프로세스 시작 시각을 기준으로 검사한다. 같은 실행 세션에서 임포트가 오래 걸려도 요청은 유지한다. 이전 실행보다 오래된 요청은 거부하고 정상 Editor 종료 시 대기 요청을 제거한다. 시작 직전 120초는 launcher가 먼저 요청을 쓰는 순서를 위한 유예이며, 임포트 제한 시간이 아니다.

준비되면 `Assets/Scenes/SampleScene.unity`를 명시적으로 연 뒤 Play한다. 다른 씬에 미저장 변경이 있으면 Unity의 저장/취소 대화상자가 나타날 수 있다. 취소하면 Play하지 않으며 다시 BAT를 실행해 요청한다. 이미 Play 중이면 현재 씬을 바꾸지 않는다. 씬 누락이나 스크립트 컴파일 실패는 Console에서 원인을 확인한다.

정상 준비 로그: `[G1 AUTO PLAY] Import complete, SampleScene ready; starting Play mode.` 이 메시지는 Editor 준비 완료이며 IK 연결·카메라·실제 G1 준비 완료를 의미하지 않는다.

## 3. Ethernet

G1 유선 주소는 `192.168.123.164`, PC 쪽 G1 전용 주소는 `192.168.123.99/24`다.

기본 `START_G1_VR_TELEOP.bat` 실행은 worker나 motor owner를 시작하기 전에 Windows의 물리 Ethernet 상태를 읽기 전용으로 검사한다. 이미 `192.168.123.99/24`가 설정된 G1 NIC가 정상 링크 상태면 그대로 사용한다. 주소가 다른 경우에는 **물리 non-virtual 802.3 Ethernet 중 링크가 올라와 있고 기본 인터넷 route가 없는 후보가 정확히 하나일 때만** 해당 NIC의 ifIndex를 선택해 UAC 관리자 설정을 요청한다. Wi-Fi/VPN/가상/Bluetooth와 기본 인터넷 route가 있는 Ethernet은 자동 변경 대상이 아니다.

자동 복구는 `CONFIGURE_G1_ETHERNET_ADMIN.ps1 -InterfaceIndex <ifIndex> -VerifyRobotSsh`를 사용한다. `192.168.123.99/24` 설정 후 `192.168.123.164:22`가 실제 응답해야 teleop 단계로 진행한다. 응답하지 않거나 설정/검증이 실패하면 기존 IPv4/DNS snapshot으로 rollback하고 **어떤 teleop worker도 시작하지 않는다**. UAC를 취소해도 동일하게 fail-closed한다. `--check-only`와 명시적 `--host` 실행은 자동 네트워크 변경을 하지 않는다.

수동 설정이 필요하면:

```bat
tools\CONFIGURE_G1_ETHERNET.bat
```

어댑터 selector는 특정 ASIX 모델명에 의존하지 않는다. 이미 `192.168.123.99/24`가 설정된 물리 Ethernet을 우선하고, 아니면 링크가 올라온 물리 Ethernet이 정확히 하나일 때만 선택한다. 여러 유선 NIC가 동시에 후보가 되어 안전하게 추론할 수 없으면 자동 변경하지 않고 아래처럼 명시한다.

```bat
tools\CONFIGURE_G1_ETHERNET.bat --interface-index <ifIndex>
```

설정 후 teleop host 선택은 `192.168.123.164:22` 유선을 먼저 확인하고, 안 되면 폐쇄망 `192.168.10.165:22`로 fallback한다. 따라서 새 PC에서도 G1 직결 Ethernet을 안전하게 식별할 수 있는 상태라면 BAT 실행만으로 주소 복구와 유선 선택까지 이어진다.

DHCP 복구:

```bat
tools\RESTORE_G1_ETHERNET_DHCP.bat
```

자동 restore는 `192.168.123.99/24`가 설정된 물리 Ethernet을 링크가 내려가 있어도 찾는다. 찾지 못하거나 여러 후보가 있으면 자동 변경하지 않고 `--interface-index`를 요구한다.

UAC elevation과 Windows NetTCPIP/DNS 변경은 OS 기능이므로 PowerShell helper를 사용하지만 Python/venv dependency는 없다. IP/DNS 변경 전 snapshot을 만들고 검증 실패 시 기존 IPv4/DNS 상태로 rollback한다.

## 4. Camera

영상만 보고 싶으면 루트의 `TEST_G1_CAMERA.bat`를 실행한다. 브라우저에 카메라만 표시하며 Unity/IK/Omni/PTZ/LowState/모터 제어는 시작하지 않는다. HTTP와 영상 수신 포트는 localhost에서 자동 배정하므로 Unity 5011과 겹치지 않는다. 종료는 페이지의 **카메라 종료** 버튼 또는 실행 창의 Ctrl+C. 브라우저 탭만 닫으면 수신은 계속되므로 종료 버튼을 사용한다. 이미 카메라를 쓰는 통합 세션은 먼저 정상 종료해야 한다.

```text
Insta360 Link 2 Pro UVC H.264
 -> SSH
 -> bundled Python/PyAV: PC H.264 decode + JPEG conversion
 -> TCP 127.0.0.1:5011 (existing G1CM/JPEG protocol)
 -> Unity HMD-follow PiP
```

현재 기본 target은 **1920×1080 H.264 / 30 fps / 16:9**이다. 카메라 압축 출력을 G1에서 그대로 전달하고 PC에서만 디코딩한다. Unity에는 기존 JPEG 형식으로 전달하여 Unity 코드/씬은 바꾸지 않는다. PC의 JPEG 변환은 추가 손실 압축이며 시각적 화질 확인은 별도다. PyAV 17.0.1과 FFmpeg DLL은 `runtime/python`에 포함돼 별도 pip/FFmpeg 설치가 필요 없다.

기존 방식은 `START_G1_VR_TELEOP.bat --camera-codec mjpeg`로 선택한다. 기존 카메라 프로세스가 다른 codec으로 실행 중이면 먼저 그 실행기를 종료해야 한다. 자동 fallback으로 100Mbps 링크에 무거운 MJPEG를 몰래 다시 켜지 않는다.

모터/Unity를 실행하지 않는 20초 카메라 수신·디코딩 검사:

```bat
runtime\python\python.exe -I -B tools\G1_CAMERA_LAUNCH.py --robot-host auto --probe-seconds 20
```

H.264 모드는 시작 전 장치 점유 여부와 포맷을 확인하며 정상 종료/예외 시 이전 포맷과 FPS를 복원한다. PTZ 및 모터 명령은 생성하지 않는다. 로그 `camera_h264/*_frames.jsonl`의 remote timestamp는 압축 chunk를 읽은 시각이며 센서 촬영시각/절대 영상지연이 아니다. 수신과 로컬 송신을 분리하고 디코딩된 최신 영상 한 장만 유지한다.

## 5. 테스트

```bat
runtime\python\python.exe -B -m unittest discover -s backend\tests -p "test_*.py"
runtime\python\python.exe -B -m unittest discover -s hardware\g1_arm_bridge -p "test_*.py"
```

## 6. 실제 archive 오프라인 gate

기준 `G1.zip`이 있으면 live 장비 없이 전체 기록 경로를 재검증한다.

```bat
runtime\python\python.exe -I -B tools\G1_PORTABLE.py archive-validate "C:\Users\user\Desktop\G1.zip" --strict
```

이 검증은 네트워크 연결이나 robot command를 만들지 않는다. bimanual, Quest/Unity trace, Omni, LowState, PC→G1 observation, G1→GROOT telemetry를 archive 내부 기록으로 교차 검증한다.

## 7. 이동성 gate

portable runtime은 원래 checkout 경로가 아닌 별도 폴더로 복사한 뒤에도 `START_G1_VR_TELEOP.bat --check-only`가 통과해야 한다.

하드코딩된 사용자 경로, `.venv-teleop`, system `py`, pip repair에 의존하면 portable gate 실패로 본다.
