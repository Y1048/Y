# 다른 PC에서 G1 Teleop 실행

## 요구 환경

- Windows 11
- Python 3.11 x64
- 프로젝트에 기록된 Unity version
- Meta Quest / Link
- Omni Connect
- G1 Ethernet 또는 closed network

WSL2는 현재 기본 camera/observation 경로에 필요하지 않다.

## 1. 저장소 준비

```bat
tools\SETUP_G1_VR_TELEOP.bat
```

`.venv-teleop`을 만들고 `tools/requirements-teleop.txt`의 exact pin을 설치/검사한다. global Python은 수정하지 않는다.

검사만:

```bat
tools\SETUP_G1_VR_TELEOP.bat --check-only
```

## 2. Ethernet

필요 시:

```bat
tools\CONFIGURE_G1_ETHERNET.bat
```

DHCP 복구:

```bat
tools\RESTORE_G1_ETHERNET_DHCP.bat
```

wired G1 주소는 기본적으로 `192.168.123.164`, closed-network fallback은 `192.168.10.165`를 탐색한다.

## 3. 실행

```bat
tools\START_G1_VR_TELEOP.bat
```

launcher는 기존 정상 worker를 재사용하며 사용자 프로세스를 임의 종료하지 않는다.

check-only:

```bat
tools\START_G1_VR_TELEOP.bat --check-only
```

## 4. Camera

```text
G1 VideoClient
 -> SSH
 -> Windows g1_camera_ssh.py
 -> TCP 127.0.0.1:5011
 -> Unity PiP
```

현재 target은 1920×1080 / 15 fps / 16:9이다. 처음 G1 주소에 연결할 때 SSH key enrollment가 필요할 수 있다.

## 5. Omni

Omni Connect가 `ws://127.0.0.1:32123`에서 데이터를 제공해야 한다. 통합 launcher의 Omni worker는 `--dry-run`이다.

## 6. Unity

`START_G1_VR_TELEOP.bat`은 Unity Editor를 열거나 기존 editor를 재사용하지만 Play mode를 강제로 켜지 않는다.

## 7. 검증

```bat
.venv-teleop\Scripts\python.exe -B -m unittest discover -s backend\tests -p "test_*.py"
.venv-teleop\Scripts\python.exe -B -m unittest discover -s hardware\g1_arm_bridge -p "test_*.py"
```

## 8. 문제 분리

- 5020 bind 실패: 기존 bilateral backend 확인
- camera 실패: G1 SSH / VideoClient / TCP 5011 확인
- Omni 실패: Omni Connect 32123 확인
- dependency 실패: 통합 launcher를 다시 실행해 pinned environment repair
- G1 host 탐색 실패: Ethernet/closed network TCP 22 확인
