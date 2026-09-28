# 다른 PC에서 G1 Teleop 실행

현재 portable setup은 `tools/START_G1_VR_TELEOP.bat`과 프로젝트 `.venv-teleop`을 기준으로 한다.

## 기본 구성

```text
Windows x64
Python 3.11
Unity 6000.5.4f1
Meta Horizon Link
Omni Connect
Windows OpenSSH
```

WSL2는 현재 기본 SSH camera/observation 경로의 필수 조건이 아니다. WSL 전용 legacy/hardware 도구를 명시적으로 사용할 때만 필요하다.

## Python dependency

```powershell
.\tools\SETUP_G1_VR_TELEOP.bat
```

setup은 프로젝트 `.venv-teleop`을 준비하고 pinned/import 상태를 검사한다. 기존 정상 venv는 재사용한다.

검사만:

```powershell
.\tools\SETUP_G1_VR_TELEOP.bat --check-only
```

## 현재 기본 실행

```powershell
.\tools\START_G1_VR_TELEOP.bat
```

이 launcher는:

- 동일 checkout의 Unity 프로젝트를 연다/재사용한다.
- bimanual IK worker를 60 Hz로 실행한다.
- Omni를 observation-only dry-run으로 읽는다.
- LowState/input observation worker를 시작한다.
- camera worker를 시작/재사용한다.
- motor output은 실행하지 않는다.

Unity Play는 사용자가 직접 켠다.

## 현재 bimanual endpoint

```text
UDP 127.0.0.1:5020
g1.bimanual.unity.sim.v4
unity_display_world_v1
```

legacy `5005/5006` 설명은 현재 기본 경로에 적용하지 않는다.

## 카메라

```text
G1 eth0 VideoClient
 -> SSH stdout
 -> PC
 -> TCP 127.0.0.1:5011
 -> Unity
```

PiP parent는 G1 `RobotRoot`다.

## Omni

```text
Omni Connect -> ws://127.0.0.1:32123
```

기본 launcher의 gateway는 motor command가 없는 dry-run observation이다.

## PC 간 이동 시 복사하지 않는 것

- `.venv-teleop`
- Unity `Library/`, `Temp/`, `Logs/`
- runtime `logs/`
- Python `__pycache__`

이 항목은 새 PC에서 재생성한다.

## Git에서 가져오는 것

- source
- Unity `Assets/`, `Packages/`, `ProjectSettings/`
- current docs
- backend tests
- hardware/tooling source

## 첫 실행 점검

1. `git status`로 checkout 확인
2. setup BAT 실행
3. Quest/Meta OpenXR 확인
4. Omni Connect 확인
5. G1 Ethernet/SSH 확인
6. `START_G1_VR_TELEOP.bat --check-only`
7. 통합 launcher 실행
8. Unity compile 완료 후 Play

## 문제 분리

- Python import 실패: `.venv-teleop` / requirements
- Unity open 실패: `6000.5.4f1` 경로/Hub
- 5020 bind 실패: 오래된 bimanual worker
- camera 실패: SSH/G1 VideoClient/TCP 5011
- Omni 실패: Omni Connect 32123
- check-only G1 unavailable: Ethernet/closed-network TCP 22

## 실제 motor control

portable observation setup 완료는 physical G1 command 승인이 아니다. 실제 출력은 hardware checklist의 별도 gate를 따른다.
