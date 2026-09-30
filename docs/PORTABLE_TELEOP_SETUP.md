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
- Unity 6000.5.4f1
- Meta Quest / Link 환경과 필요한 드라이버
- Omni Connect
- Windows OpenSSH client (`ssh.exe`, `ssh-keygen.exe`)
- G1 Ethernet 또는 closed network
- G1 onboard `/home/unitree/groot_onboard_runtime`에 heading controller와 executable `build/groot_balance_actuator`
- APK 설치 시 Meta Quest Developer Hub의 `adb.exe`

## 1. 폴더 복사 후 runtime 검사

```bat
runtime\python\python.exe -I -B tools\G1_PORTABLE.py check-runtime --pc-only
```

별도 setup BAT는 유지하지 않는다. 위 명령은 bundled runtime 자체만 사용해 PC-side Python 환경을 검사한다.

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
tools\START_G1_VR_TELEOP.bat
```

검사만:

```bat
tools\START_G1_VR_TELEOP.bat --check-only
```

BAT는 환경 로직을 갖지 않고 Embedded Python dispatcher만 호출한다. 일반 실행은 GROOT supervisor를 새로 시작해야 할 때 `ACTUATE` 확인을 요구하고, 확인 후 heading controller와 300초 balance actuator를 SSH로 함께 실행한다. motor output 없이 PC/Unity/observation만 실행하려면 `tools\START_G1_VR_TELEOP.bat --no-groot-actuation`을 사용한다. `--check-only`은 GROOT remote login이나 actuation을 수행하지 않는다.

## 3. Ethernet

필요 시:

```bat
tools\CONFIGURE_G1_ETHERNET.bat
```

DHCP 복구:

```bat
tools\RESTORE_G1_ETHERNET_DHCP.bat
```

UAC elevation과 Windows NetTCPIP/DNS 변경은 OS 기능이므로 PowerShell helper를 사용하지만, Python/venv dependency는 없다.

## 4. Camera

```text
G1 VideoClient
 -> SSH
 -> bundled Python g1_camera_ssh.py
 -> TCP 127.0.0.1:5011
 -> Unity PiP
```

현재 target은 1920×1080 / 15 fps / 16:9이다.

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
