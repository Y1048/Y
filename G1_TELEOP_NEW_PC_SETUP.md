# 새 PC에서 G1 Teleop을 처음 실행하는 전체 체크리스트

이 문서는 빈 Windows PC에서 이 저장소의 **Quest 양손 추적 + Mink IK + Omni 입력 +
G1 LowState/카메라 표시** 환경을 준비하는 순서다. 현재 통합 진입점은
`tools\START_G1_VR_TELEOP.bat`이다.

> 현재 통합 BAT는 입력 생성·관찰과 카메라 표시용이다. G1 모터 명령, LowCmd
> publisher, 하체 정책 또는 실제 상위 제어기를 실행하지 않는다. 실제 로봇 구동은
> 별도의 단일 전신 제어기와 별도 검증이 필요하다.

## 1. 필요한 장비

- Windows 10/11 64-bit PC
- Meta Quest 2, Quest 3 또는 Quest 3S와 충전된 배터리
- Quest Link용 고품질 USB 3 케이블 또는 안정적인 Air Link 네트워크
- Virtuix Omni One과 Windows PC의 Bluetooth
- G1 연결용 Ethernet 또는 `192.168.10.165`에 접근 가능한 폐쇄망
- 인터넷 연결: 최초 Git clone, Unity package 복원, Python package 설치에 필요

프로젝트 경로가 너무 깊으면 Windows 경로 길이 문제가 생길 수 있다. 새 PC에서는
`C:\G1_Teleop_Project`처럼 짧은 경로를 권장한다.

## 2. 설치해야 하는 프로그램

### 반드시 설치

| 프로그램 | 프로젝트 기준 | 용도 / 설치 후 확인 |
| --- | --- | --- |
| Git for Windows | 현재 유지보수 버전 | 저장소 clone/pull. `git --version` |
| Python x64 | **3.11** (`3.11.9` 검증) | BAT가 `py -3.11`을 사용. 최신 3.14만 설치하면 안 됨 |
| Unity Hub | 현재 유지보수 버전 | 고정 Unity Editor 설치·라이선스 |
| Unity Editor | **6000.5.4f1** | 프로젝트 고정 버전. 통합 BAT가 이 버전을 탐색 |
| Meta Horizon Link | 현재 버전 | Quest PCVR, 손 추적, Oculus/OpenXR runtime |
| Steam + SteamVR | 현재 버전 | Omni Connect 설치 선행조건 |
| Virtuix Omni Connect | `1.2.93`에서 수신 검증 | Omni Bluetooth 연결과 localhost WebSocket `32123` |
| Windows OpenSSH Client | Windows 선택적 기능 | G1 LowState/카메라 SSH. `ssh -V` |

공식 설치 링크:

- [Git for Windows](https://git-scm.com/install/windows)
- [Python 3.11.9 Windows x64](https://www.python.org/downloads/release/python-3119/)
- [Unity Hub 설치](https://docs.unity.com/en-us/hub/install-hub-win-mac)
- [Unity 6000.5.4f1](https://unity.com/releases/editor/whats-new/6000.5.4f1)
- [Meta Quest 및 Meta Horizon Link 설치](https://www.meta.com/quest/setup/)
- [SteamVR](https://store.steampowered.com/app/250820/SteamVR/)
- [Omni Connect](https://virtuix.com/pc)
- [Omni One PCVR 설치 순서](https://support.virtuix.com/hc/en-us/articles/32828540669837-PCVR-Software-Preparation)
- [Windows OpenSSH 설치](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)

### SteamVR의 정확한 역할

Virtuix 공식 설치 순서는 SteamVR을 먼저 설치하도록 요구하고 Omni Connect 설치기도
SteamVR 미설치 시 종료된다. 그러나 Omni Connect 1.1.51 이후 앱 자체는 SteamVR을
실행하지 않아도 동작할 수 있다. 이 프로젝트는 Omni Connect의 로컬 WebSocket만 읽는다.

Quest/Unity 실행 중에는 **Meta Horizon Link를 활성 OpenXR runtime으로 유지**한다.
SteamVR을 활성 OpenXR runtime으로 바꾸면 현재 Oculus XR Plugin이 초기화에 실패할 수
있다. 즉 SteamVR은 설치해 두되 평소 이 프로젝트를 실행할 때 열 필요는 없다.

### 현재 기본 경로에서는 불필요

- **WSL2:** 현재 기본 카메라는 Windows OpenSSH 경로다. `--transport wsl`이라는 과거
  진단 경로를 일부러 사용할 때만 필요하다.
- **Meta Quest Developer Hub / ADB / Android Build Support:** Quest에 APK를 직접
  빌드·설치할 때만 필요하다. 현재 Unity Editor + Quest Link Play에는 필요 없다.
- **Visual Studio:** C#을 IDE에서 편집할 때 선택 사항이다. Unity 프로젝트를 열고
  Play하는 것만으로는 필수가 아니다.
- **Omni Unity SDK:** 현재 Omni 입력은 별도 Python gateway가 Omni Connect
  WebSocket을 읽으므로 필요 없다.

## 3. Unity와 Quest 최초 설정

1. Unity Hub에 로그인하고 Editor `6000.5.4f1`을 설치한다.
2. Meta Horizon Link에 로그인하고 Quest를 USB Link 또는 Air Link로 연결한다.
3. Meta Horizon Link의 `Settings > General > OpenXR Runtime`에서
   **Set Meta Horizon Link as active**를 누른다.
4. Meta Horizon Link의 Developer runtime 기능을 켠다.
5. Quest 설정에서 Hand Tracking을 켜고 Quest Link를 시작한다.
6. 아래 명령으로 Windows의 실제 활성 runtime을 확인한다.

```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Khronos\OpenXR\1' |
  Select-Object ActiveRuntime
```

정상 예시는 경로 끝이 `oculus_openxr_64.json`이다. SteamVR JSON이 나오면 Meta
Horizon Link에서 Meta runtime을 다시 활성화한다.

이 저장소는 Unity package를 `Packages/manifest.json`에서 복원한다. 핵심 고정값은
Meta XR SDK `205.0.0`, Oculus XR Plugin `4.5.4`다. 새 PC에서 처음 프로젝트를 열 때
package import와 Library 생성에 시간이 걸릴 수 있으므로 완료되기 전에 Play하지 않는다.

## 4. Omni One 최초 설정

1. Steam과 SteamVR을 설치한다.
2. Omni Connect를 설치하고 Omni 계정으로 로그인한다.
3. PC Bluetooth를 켜고 Omni One을 Omni Connect에 연결한다.
4. Omni 위에 올라가 연결 상태와 tracking을 확인한다.
5. 다음 명령으로 WebSocket listener를 확인한다.

```powershell
Get-NetTCPConnection -State Listen -LocalPort 32123
```

장치 연결 전에는 `32123`이 열리지 않을 수 있다. 프로젝트 gateway는
`ws://127.0.0.1:32123`에서 `movementXY`와 `armYaw`를 읽는다. SteamVR은 이 로컬
데이터 수신 중 실행 상태일 필요가 없다.

## 5. 저장소 받기

PowerShell에서:

```powershell
cd C:\
git clone --branch main https://github.com/Y1048/Y.git G1_Teleop_Project
cd C:\G1_Teleop_Project
git status --short --branch
```

현재 `Y1048/Y`는 공개 저장소이므로 새 PC에서 clone/fetch/pull할 때 GitHub 계정이나
로그인이 필요 없다. 변경을 GitHub에 push할 때만 쓰기 권한이 있는 계정 인증이 필요하다.
기존 작업 폴더가 dirty이면 `reset --hard`, `clean`, 강제 pull을 하지 않는다.
다른 PC에서 이어받을 때는 다음 순서로 확인한다.

```powershell
git fetch origin
git rev-list --left-right --count HEAD...origin/main
git pull --ff-only origin main
```

`0 0`이면 로컬과 원격이 같다. 로컬 변경이 있거나 양쪽 숫자가 모두 0이 아니면 먼저
변경 내용을 보존·대조한다.

## 6. Python 환경 설치

먼저 설치 상태를 확인한다.

```powershell
py -3.11 --version
py -3.11 -c "import struct; print(struct.calcsize('P') * 8)"
git --version
ssh -V
```

Python 결과는 3.11.x와 `64`여야 한다. 그다음 프로젝트 루트에서:

```powershell
.\tools\SETUP_G1_VR_TELEOP.bat
.\tools\SETUP_G1_VR_TELEOP.bat --check-only
```

첫 명령은 `.venv-teleop`을 만들고 `tools/requirements-teleop.txt`의 정확한 버전을
설치한다. 주요 항목은 MuJoCo 3.12.0, Mink 1.3.0, DAQP, Ruckig,
websocket-client다. 전역 Python 환경을 사용하지 않는다.

`DEPENDENCIES READY`는 Python/IK import와 로컬 구성 검사 성공을 뜻한다. Quest 입력,
Omni Bluetooth, G1 카메라 또는 실제 로봇 수신 성공을 뜻하지 않는다.

## 7. G1 네트워크와 SSH

통합 launcher는 다음 순서로 G1 SSH 포트를 찾는다.

1. 유선 G1 주소 `192.168.123.164:22`
2. 폐쇄망 G1 주소 `192.168.10.165:22`

launcher가 PC의 Ethernet IP를 자동 변경하지는 않는다. 유선 연결은 PC NIC를 G1과
같은 `192.168.123.0/24` 대역의 중복되지 않는 주소로 설정한 뒤 확인한다.

```powershell
Test-NetConnection 192.168.123.164 -Port 22
Test-NetConnection 192.168.10.165 -Port 22
```

둘 중 실제 연결 방식 하나만 성공하면 된다. 처음 실행할 때 해당 PC 전용 SSH 키를
만들고 G1에 공개키를 등록하기 위해 비밀번호 입력을 한 번 요구할 수 있다. 비밀번호를
BAT, 문서 또는 Git에 저장하지 않는다. 호스트 키가 달라졌다는 경고가 나오면
`known_hosts`를 무조건 삭제하지 말고 실제 G1 주소와 장비를 먼저 확인한다.

기본 SSH 카메라는 G1의 기존 시스템 Python과 `unitree_sdk2py`를 사용한다. PC에서
로봇에 패키지를 복사하지 않는다. G1 쪽 해당 환경이 없으면 카메라만 별도로 준비해야 한다.

## 8. 최초 통합 실행 순서

1. Meta Horizon Link 실행 → Quest Link 연결 → Hand Tracking 확인
2. Omni Connect 실행 → 로그인 → Omni Bluetooth 연결
3. G1 전원 및 사용할 네트워크 연결
4. 프로젝트 루트에서 통합 BAT 실행

```powershell
.\tools\START_G1_VR_TELEOP.bat
```

고정 주소가 필요할 때만:

```powershell
.\tools\START_G1_VR_TELEOP.bat --host 192.168.10.165
```

BAT는 Python 의존성을 검사·복구하고, 누락된 관찰 worker와 카메라를 시작하고,
이 checkout의 `Unity_G1_VR`을 Unity `6000.5.4f1`로 연다. 동일 프로젝트가 이미 열려
있으면 재사용한다. **Unity Play는 자동으로 누르지 않는다.** Unity import/compile이
끝나고 Console에 오류가 없는 것을 확인한 뒤 Play를 누른다.

Play 후 Quest에서:

1. 양손 cyan 손목 marker가 실제 손을 따라오는지 확인
2. 양손을 각각 engage한 뒤 로봇 목표가 따라오는지 확인
3. pinch → 안전 복귀 → 재-engage를 확인
4. Omni에서 전진·후진·좌·우·좌회전·우회전 입력을 확인
5. 카메라 PiP가 표시되는지 확인

현재 BAT는 `G1_INPUT_RECEIVE_AUDIT.py receive`를 실행하거나 재사용하지 않는다.
상위 제어기와 포트가 충돌할 수 있으므로 이 수신기를 임의로 추가 실행하지 않는다.

## 9. 실행 전 읽기 전용 점검

G1에 연결된 상태에서 실행 계획만 확인하고 실제 worker/Unity를 시작하지 않으려면:

```powershell
.\tools\START_G1_VR_TELEOP.bat --check-only
```

G1이 없는 PC에서 Python/IK 환경만 검사하려면:

```powershell
.\tools\SETUP_G1_VR_TELEOP.bat --pc-only
.\tools\SETUP_G1_VR_TELEOP.bat --check-only --pc-only
```

통합 실행 중 새 worker 출력은 기본적으로
`logs/test_results/teleop_background/<session>/`에 저장된다. GitHub clone에는 다른
PC에서 만든 원본 로그, `.venv-teleop`, Unity `Library`와 계정/장치 pairing이 포함되지 않는다.

## 10. 자주 발생하는 문제

| 증상 | 확인할 항목 |
| --- | --- |
| `py -3.11`을 찾지 못함 | Python 3.11 x64 설치 시 Python Launcher 포함 여부 확인 |
| `websocket-client` 등 module 누락 | 인터넷 연결 후 통합 BAT 재실행. 빈 venv를 자동 검출·복구함 |
| Unity 6000.5.4f1을 찾지 못함 | Hub에서 정확한 버전 설치. 특수 경로라면 `UNITY_EXE` 환경변수 지정 |
| `Unable to start Oculus XR Plugin` | Meta Horizon Link를 활성 OpenXR runtime으로 다시 설정. SteamVR runtime 해제 |
| Quest 화면/손 입력 없음 | Quest Link가 실제 시작됐는지, Hand Tracking 및 Meta runtime 확인 |
| Omni 값 없음 | Omni Connect 로그인·Bluetooth 연결과 TCP `32123` listener 확인 |
| `Duplicate ... processes found` | 자신이 이전에 연 manager를 Enter로 정상 종료. 무관한 프로세스는 종료하지 않음 |
| `G1 unavailable` | Ethernet/폐쇄망, G1 전원, 해당 주소의 TCP 22 확인 |
| 카메라가 안 보임 | G1 SSH, G1 VideoClient 환경, Unity Play와 로컬 TCP `5011` 확인 |
| Unity가 열렸지만 동작하지 않음 | package import/compile 완료 및 Console 오류 확인 후 Play |

## 11. 새 PC 준비 완료 기준

- [ ] `git`, `py -3.11`, `ssh` 명령이 동작한다.
- [ ] Unity `6000.5.4f1`이 설치돼 있다.
- [ ] Meta Horizon Link가 활성 OpenXR runtime이다.
- [ ] Quest Link와 양손 Hand Tracking이 동작한다.
- [ ] SteamVR 설치 후 Omni Connect 설치를 완료했다.
- [ ] Omni Connect가 Omni One과 연결되고 TCP `32123`을 연다.
- [ ] `SETUP_G1_VR_TELEOP.bat --check-only`가 통과한다.
- [ ] 사용할 G1 주소의 TCP 22에 접근할 수 있다.
- [ ] `START_G1_VR_TELEOP.bat`이 Unity 프로젝트와 관찰 경로를 시작한다.
- [ ] Unity Play에서 양손 marker, engage/pinch/re-engage, Omni 입력, 카메라를 확인했다.
- [ ] 위 결과를 실제 G1 모터 제어 검증으로 오해하지 않는다.
