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
- 최종 운영 구조는 Quest APK가 손/HMD tracking을 직접 수집해 PC Portable로 전송하여 운영 PC의 Unity Editor 의존성을 제거하는 것이다
- Meta Quest / Link 환경과 필요한 드라이버
- Omni Connect
- working OpenSSH client (`ssh.exe`, `ssh-keygen.exe`): Windows OpenSSH 또는 Git for Windows OpenSSH
- G1 Ethernet 또는 closed network
- G1 onboard `/home/unitree/groot_onboard_runtime`에 heading controller와 executable `build/groot_balance_actuator`
- APK 설치 시 Meta Quest Developer Hub의 `adb.exe`

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

## 3. Ethernet

G1 유선 주소는 `192.168.123.164`, PC 쪽 G1 전용 주소는 `192.168.123.99/24`다. 새 PC에서 처음 연결하거나 해당 NIC가 아직 설정되지 않았으면 한 번 실행한다.

```bat
tools\CONFIGURE_G1_ETHERNET.bat
```

어댑터 선택은 더 이상 ASIX 모델명에 의존하지 않는다. 물리 Ethernet(`HardwareInterface=True`, non-virtual, `802.3`)만 후보로 사용하며 Wi-Fi/VPN/가상/Bluetooth는 제외한다. 이미 `192.168.123.99/24`가 설정된 물리 Ethernet이 있으면 그 NIC를 우선 재사용하고, 아니면 링크가 올라온 물리 Ethernet이 정확히 하나일 때만 자동 선택한다. 여러 유선 NIC가 동시에 링크된 경우에는 추측하지 않고 fail-closed하며 아래처럼 명시한다.

```bat
tools\CONFIGURE_G1_ETHERNET.bat --interface-index <ifIndex>
```

설정 후 기본 teleop launcher는 `192.168.123.164:22` 유선을 먼저 확인하고, 안 되면 폐쇄망 `192.168.10.165:22`로 fallback한다. 따라서 같은 PC에서는 이후 랜선만 바뀌어도 별도 재설정 없이 유선을 자동 우선 사용한다.

DHCP 복구:

```bat
tools\RESTORE_G1_ETHERNET_DHCP.bat
```

자동 restore는 `192.168.123.99/24`가 설정된 물리 Ethernet을 찾아 링크가 내려가 있어도 복구한다. 찾지 못하거나 여러 후보가 있으면 자동 변경하지 않고 `--interface-index`를 요구한다.

UAC elevation과 Windows NetTCPIP/DNS 변경은 OS 기능이므로 PowerShell helper를 사용하지만, Python/venv dependency는 없다. IP/DNS 변경 전 snapshot을 만들고 검증 실패 시 기존 IPv4/DNS 상태로 rollback한다.

## 4. Camera

```text
Insta360 Link 2 Pro UVC MJPEG
 -> SSH
 -> bundled Python g1_camera_ssh.py
 -> TCP 127.0.0.1:5011
 -> Unity HMD-follow PiP
```

현재 target은 1920×1080 MJPEG / 30 fps / 16:9이며 G1에서 재인코딩하지 않는다.

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
