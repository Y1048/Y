# 다른 PC에서 입력·카메라 실행


## 2026-09-21 기본 실행의 자동 의존성 복구

최신 브랜치를 pull한 뒤 `tools\START_G1_VR_TELEOP.bat`을 실행하면, 네트워크/SSH/작업 프로세스를 시작하기 **전에** 해당 프로젝트 `.venv-teleop`을 검사한다.
- Python 3.11 x64 및 프로젝트 venv 경로 확인
- `requirements-teleop.txt`의 모든 고정 버전, 실제 import, `pip check` 확인
- 빈 venv/누락/버전 불일치라면 프로젝트 venv에 전체 requirements 설치 후 재검증
- 설치 실패/인터넷 미연결이면 실행 차단. 다운로드가 가능한 상태에서 동일 BAT를 다시 실행
- 이미 정상이라면 설치하지 않음. `--check-only`는 설치 없이 검사만 수행

가상환경이 없을 때 생성하려면 Windows Python Launcher의 `py -3.11`이 필요하다. 패키지 다운로드 연결도 필요하다. Unity/Meta Link/Omni Connect 설치나 G1 수신 성공을 이 검사가 보장하지는 않는다. `.venv-teleop`은 Git으로 복사하지 않고 각 PC에서 구성한다. 아래 별도 SETUP 안내는 수동 설치 및 기존 WSL 카메라 경로 준비용으로 유지한다.

## 현재 기본 카메라 경로

```text
G1 내부 VideoClient (eth0)
 → JPEG + G1CM 프레임 헤더
 → SSH stdout 스트림 (G1 TCP 22)
 → PC g1_camera_ssh.py
 → PC 내부 TCP 127.0.0.1:5011
 → Unity
```

기본값은 SSH다. VideoClient는 G1 내부에서 실행하며, PC와 G1 사이에는 JPEG만 SSH로 전달한다.
Unity의 TCP5011 수신 포맷은 그대로다. TCP5011은 외부 네트워크가 아닌 PC 로컬 전용이다.
G1 시스템 Python3와 기존 unitree_sdk2py를 사용하며 SSH stdin 실행으로 새 파일은 남기지 않는다.
카메라 코드는 모터 명령이나 입력 수신 포트를 사용하지 않는다.
통합 배치는 G1_INPUT_RECEIVE_AUDIT.py 수신기를 실행/재사용하지 않는다.

설치/check-only에는 WSL 의존성 검사가 남아 있지만 기본 영상 전송은 WSL을 거치지 않는다.
--transport wsl은 이전 경로 진단용이며, 현재 노트북의 새 CycloneDDS 초기화 crash는 미해결이다.
기본 SSH 경로로 실제 G1 JPEG 수신은 확인했다. Unity 최종 화면 표시는 별도 확인이 필요하다.


이 문서는 이전 인계의 **노트북 고정 카메라 경로/venv 안내를 대체**한다.
대상은 Windows 11 22H2 이상 x64 + 최신 WSL2 Linux 환경이다.
모든 OS에서 무설치 실행하는 패키지는 아니다. PC마다 최초 설치는 필요하다.

## 실행 순서

저장소를 원하는 드라이브/폴더에 받은 뒤 프로젝트 루트에서 실행한다.

```powershell
.\tools\SETUP_G1_VR_TELEOP.bat
```

이 작업은 프로젝트 안 `.venv-teleop`에 고정 버전 IK/Omni 패키지를 설치한다.
카메라 소스는 Windows Git으로 지정 리비전만 내려받아 WSL에 전달한다. WSL의 GitHub 연결이 느린 환경도 고려했다.
WSL에는 사용자 전용 `~/.local/share/g1-teleop-camera` 아래 Python 3.11,
CycloneDDS, Unitree Python SDK를 설치한다. Python 시스템 환경을 변경하지 않는다.
이미 설치돼 있으면 재사용한다. SDK와 CycloneDDS 소스 리비전은 고정하며,
기존 소스가 변경돼 있으면 덮어쓰지 않고 중단한다.
SDK는 공식 [Unitree 설치 방식](https://github.com/unitreerobotics/unitree_sdk2_python#installation)을 따른다.
WSL Python은 [uv](https://docs.astral.sh/uv/getting-started/installation/)로 준비한다.

설치 후 Unity Hub에서 **이 checkout의 `Unity_G1_VR`**을 열고 Play를 켠다.
Meta Horizon Link의 Quest 연결과 Omni Connect의 Bluetooth 연결을 완료한다.

```powershell
# 설치/모델 검사만. 모터·카메라·SSH 실행 없음
.\tools\SETUP_G1_VR_TELEOP.bat --check-only

# 카메라만 실행해서 먼저 확인
.\tools\START_G1_CAMERA_TO_UNITY.bat

# 양팔 IK + Omni 관찰 + 카메라 통합 실행
.\tools\START_G1_VR_TELEOP.bat
```

카메라 창을 이미 열었다면 통합 launcher는 같은 카메라를 추가 실행하지 않는다.
G1이 없는 PC에서 IK/Omni 의존성만 준비할 때는 setup에 `--pc-only`를 붙인다.
관찰기가 전송하는 것은 입력 관찰 패킷이며 이 배치파일은 모터 제어기를 실행하지 않는다.

## PC마다 필요한 최초 준비

- Windows Python 3.11 x64 + Python Launcher (`py -3.11`). 없으면 Python 공식 설치 프로그램으로 설치한다.
- WSL2 Linux 배포판. 없으면 관리자 터미널의 `wsl --install`로 설치하고 사용자 생성을 끝낸다.
- WSL에 `git`, C compiler, `curl`이 필요하다. Ubuntu에서 빠져 있으면
  `sudo apt-get update` 후 `sudo apt-get install git build-essential curl`을 실행한다.
- Unity 버전은 `Unity_G1_VR/ProjectSettings/ProjectVersion.txt` 기준으로 Unity Hub에서 설치한다.
- Meta Horizon Link·Omni Connect 설치와 장치 연결은 별도다. 계정 로그인과 Bluetooth pairing은 복제되지 않는다.
- G1 유선 LAN은 로봇과 같은 서브넷의 **중복되지 않는 PC IP**가 필요하다.
  이제 PC IP를 `192.168.123.99`로 강제하지 않는다. 로봇까지 직접 연결된 WSL route에서 NIC를 찾는다.

## 이전 WSL 경로 설정 (기본 SSH 영상에는 해당 없음)

이전 --transport wsl 카메라 전송은 WSL → Windows Unity **127.0.0.1:5011**이다.
Windows 11의 WSL mirrored networking을 사용한다.
[Microsoft 문서](https://learn.microsoft.com/en-us/windows/wsl/networking#mirrored-mode-networking)의
방법대로 setup은 사용자 홈 `.wslconfig`의 기존 항목을 보존하고 원본 백업을 만든 뒤 아래 값만 병합한다. 중복/모호한 항목은 덮어쓰지 않는다.

```ini
[wsl2]
networkingMode=mirrored
```

**실행 중인 WSL 작업을 먼저 종료한 뒤** `wsl --shutdown`으로 적용하고 다시 실행한다.
설치기는 기존 작업을 끊거나 WSL을 자동 재시작하지 않는다. NIC 주소와 방화벽은 변경하지 않는다.
`wsl -- wslinfo --networking-mode`로 `mirrored`를 확인한다.
카메라 실행은 NAT이면 SDK 초기화 전에 중단하고 이 문서를 안내한다.

WSL 기본 배포판을 사용하므로 이름을 Ubuntu로 고정할 필요가 없다.
다른 배포판을 선택할 때만 PowerShell에서 다음처럼 지정하고 setup/launch를 동일하게 실행한다.

```powershell
$env:G1_WSL_DISTRO = 'Ubuntu-24.04'
```

폐쇄망 `192.168.10.165`를 사용할 경우:

```powershell
.\tools\START_G1_VR_TELEOP.bat --host 192.168.10.165
```

랜선 자체가 필수는 아니지만 PC에서 해당 G1까지 통신이 가능해야 한다. SSH 성공과 UDP ACK/카메라 DDS 성공은 별도로 확인한다.

기본값은 자동 선택이다. `192.168.123.164:22`를 최대 1.5초 확인하고 실패하면 `192.168.10.165:22`를 최대 1.5초 확인한다. 두 주소 모두 접근 불가이면 창을 생성하기 전에 중단한다. 선택 주소는 `[G1 NETWORK]`에 표시하며 모든 입력 worker와 카메라에 동일하게 전달한다. TCP 22 확인은 로그인/UDP/카메라 검증이 아니다. 통합 launcher의 `--check-only`도 기본 auto에서는 이 TCP 확인을 수행한다. **setup의 `--check-only`는 G1에 접속하지 않는다.**

G1 주소가 바뀌면 통합 실행에 `--host 새주소`, 카메라 단독 실행에는
`--robot-host 새주소`를 붙인다. PC 계정명·드라이브·프로젝트 경로는 자동 변환한다.

## 검사 결과를 해석하는 방법

- setup PASS: Python 패키지, 전체 IK import 및 모델 생성, 카메라 SDK import 성공.
- SDK import는 DDS 초기화나 카메라 수신 시험이 아니다.
- `Waiting for Unity`면 현재 checkout의 Unity Play와 TCP 5011 수신을 확인한다.
- 카메라 이미지 실패는 G1 연결/카메라 서비스/DDS 네트워크를 별도 확인한다.
- 실제 데스크톱의 영상·Quest 표시·Omni 입력은 해당 PC에서 확인해야 한다.
- `.venv-teleop`와 원본 로그는 Git에 넣지 않는다. 새 PC에서는 setup을 다시 실행한다.

기존 관찰 수신기 파일은 보존하지만 통합 실행에서는 사용하지 않는다.
상위 제어기 입력 통합은 별도 작업이며 PC setup은 수신기를 배포하지 않는다.

## 2026-09-21 검증

Windows 새 `.venv-teleop` 설치, 전체 IK import/모델 구성, pip check 성공.
WSL 별도 Python 3.11 환경에서 CycloneDDS 빌드/설치와 카메라 SDK import 성공.
전체 setup 재실행 및 `--check-only` 성공. G1 SDK 초기화/영상/모터 실행 없음.
이식성·자동 주소 선택·launcher·입력 console/tap 44개, JPEG packet 4개 통과.
생성 입력 통합 테스트는 새 환경의 테스트 전용 `websockets` 미설치로 실행 전 실패했다. 이후 UDP 55071 기존 점유를 확인하여 해당 통합 테스트는 재실행하지 않았다. 기존 프로세스는 종료하지 않았다.
새 데스크톱의 실제 카메라 수신은 아직 미검증이다.
