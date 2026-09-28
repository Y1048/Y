# Project Tools

`tools/`에는 현재 통합 launcher, setup, observation, read-only hardware, legacy/specialized 검증 도구가 함께 있다.

## 현재 기본 실행

```powershell
.\tools\START_G1_VR_TELEOP.bat
```

현재 기본 목적:

```text
bilateral IK
Omni observation
G1 LowState observation
front camera
Unity open/reuse
NO MOTOR OUTPUT
```

launcher는 동일 옵션의 기존 worker를 보존하고, 충돌하는 옵션의 process를 자동 종료하지 않는다.

주요 옵션:

```powershell
.\tools\START_G1_VR_TELEOP.bat --check-only
.\tools\START_G1_VR_TELEOP.bat --no-unity
.\tools\START_G1_VR_TELEOP.bat --show-consoles
```

## 현재 worker

`G1_VR_TELEOP_LAUNCH.py`의 integrated worker:

- `lowstate`: read-only G1 state observation
- `send`: input observation sender, 60 Hz
- `omni`: Omni gateway dry-run, 60 Hz
- `arm`: bimanual Mink/MuJoCo worker, 60 Hz
- `camera`: G1 VideoClient SSH bridge -> Unity TCP 5011

관찰 display는 100 Hz다.

## Bimanual simulation

현재 arm worker:

```text
MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py
  --mode unity
  --headless
  --compute-hz 60
```

Unity 양손 입력은 UDP `5020`, observation copy는 localhost UDP `55071`을 사용한다.

## 설치 / dependency

```powershell
.\tools\SETUP_G1_VR_TELEOP.bat
.\tools\SETUP_G1_VR_TELEOP.bat --check-only
```

프로젝트 `.venv-teleop`은 Python 3.11 기준이며 Git에 포함하지 않는다. 상세는 [../docs/PORTABLE_TELEOP_SETUP.md](../docs/PORTABLE_TELEOP_SETUP.md).

## Unity

기본 launcher는 `Unity_G1_VR`을 `6000.5.4f1`로 연다. 이미 같은 프로젝트가 열려 있으면 재사용한다. Play는 자동으로 켜지 않는다.

PiP camera는 G1 `RobotRoot` 기준이다.

## Read-only / display tools

대표 도구:

```text
START_G1_READ_ONLY.bat
VIEW_G1_LIVE_MUJOCO.bat
VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat
START_G1_CAMERA_TO_UNITY.bat
CHECK_G1_TELEOP_STARTUP.bat
```

이 도구 이름에 `G1` 또는 `hardware`가 있어도 read-only path는 motor command를 의미하지 않는다.

## Physical hardware tools

`START_G1_GATE*`, Arm SDK, bounded joint trial 도구는 기본 bimanual launcher와 별도다.

실제 motor authority가 있는 도구는 반드시 `hardware/g1_arm_bridge/README.md`와 `HARDWARE_BRINGUP_CHECKLIST.md`, 관련 authorization config를 먼저 확인한다.

과거 bounded physical trial 중 **right-arm only**인 도구는 현재 deprecated다. 앞으로의 실제 arm control도 양팔 14축만 지원하며, right-arm-only launcher는 실행 경로로 사용하지 않는다.

## Deprecated single-arm tools — 직접 실행 금지

다음 계열은 현재 default가 아니다.

```text
START_VR_HAND_TO_MUJOCO.bat
START_VR_HAND_TO_MUJOCO_VANILLA_MINK.bat
START_VR_STANDARD_MINK.bat
5005/5006 single-arm tools
```

기존 regression/reference 또는 특수 hardware path 때문에 남아 있다.

## 테스트

현재 bimanual 핵심 회귀는 root README의 80-test 묶음을 사용한다.

코드 색인:

```powershell
.venv-teleop\Scripts\python.exe backend\tools\build_code_index.py
.venv-teleop\Scripts\python.exe backend\tools\build_code_index.py --check
```

## 로그

`logs/`는 runtime에서 다시 생성되는 로컬 산출물이다. Git source of truth가 아니다.

오래된 validation/review 로그는 정리됐으며 필요한 과거 상태는 Git history에서 확인한다.

## 도구를 고를 때

1. 평소 개발/관찰: `START_G1_VR_TELEOP.bat`
2. 설치/의존성: `SETUP_G1_VR_TELEOP.bat`
3. 저장/실측 표시: `VIEW_G1_*`
4. 물리 output: hardware README/checklist 확인 후 별도 Gate launcher
5. deprecated single-arm: 직접 실행하지 않음. 내부 helper/reference 의존성 제거 전까지만 소스 보존
