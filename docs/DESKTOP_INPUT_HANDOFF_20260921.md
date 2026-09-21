# 다른 데스크톱에서 이어받기 — 2026-09-21

현재 브랜치는 `codex/g1-laptop-sync-20260917`, 저장소는 `https://github.com/Y1048/Y.git`이다.
이 문서와 `docs/CHAT_HANDOFF.md` 상단이 과거 인계보다 우선한다. `main`은 변경하지 않는다.

## 현재 목표와 결정

- 우리는 Quest/Unity 양팔 IK 14축과 Omni 이동값을 정확히 생성·전달한다. 실제 G1 제어기는 상대 개발자가 담당한다.
- 양팔 관절 순서는 왼팔15~21, 오른팔22~28, 단위rad. 모든 관절 목표의 속도 상한3rad/s, 가속도 상한3rad/s².
- 설정 파일은 `MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py`. PD/gain은 이번에 바꾸지 않았다.
- Omni는 월드mx/my를 현재 절대armYaw로 몸 기준vx/vy로 회전한다. 전진+vx, 왼쪽+vy, 단위m/s. yaw_rate는rad/s.
- 계산·관찰송신 목표60Hz, 화면표시100Hz. 독립 입력의 취득시각은 같지 않으며 표시는 최신값을 반복할 수 있다.
- 통합 진입점은 `tools/START_G1_VR_TELEOP.bat`: 입력 관찰4창 + 기존 읽기전용 카메라. 모터 제어기가 아니다.
- 사용자가 FOV/시점/영상패널 변경을 하지 않기로 했다. 현재 화면 배치를 유지한다.
- 상·하체 동시 입력 구조이며 모드 전환 기능을 추가하지 않는다. 로그 자동삭제·압축도 넣지 않는다.
- 연구 PD 후보는 최종 승인값이 아니다. `recommended_hardware_gains = null`.

## 확인된 결과와 남은 일

최신 실제 Quest 세션 `unity_20260921_152631_628857.jsonl`은 양팔tracking3회,
재engage2회, pinch복귀3회 완료, 최종READY였다. BLOCKED/solver/return fault0,
최대 IK 목표속도1.364523rad/s, 최대가속도3rad/s²(수치오차 범위).

PC localhost 수신15,656개에서 순번누락·역전·전달값불일치0, 약59.999Hz였다.
단, **Omni 원본mx=-0.05,my=0.27이 고정이고 vx/vy/yaw_rate는0이었다. 실제 보행과
양팔의 동시 움직임은 미확인**이다. 사용자가 실제로 걸었는지 답하기 전에 다른 작업으로 넘어갔다.
다음은 실제 Omni 보행 시 원본이 변하는지와 변환 방향을 확인하는 것이다. 양팔 IK를 다시 튜닝할 필요는 없다.

증거는 `docs/validation/input_limits_integration_20260921/`에 있다.
40개 좌표/복사/clocked 검사와2개 생성 입력 loopback 검사 통과. 이는 실제 G1 모터 검증이 아니다.
이전 양팔 전체116개는115통과 후 마지막 기록종료창 테스트를 수정해 단독재실행 통과했다.
전체116개를 수정 후 다시 한 번 실행했다고 주장하지 않는다. 과거 실패 로그도 보존했다.

## Git으로 받기

기존 저장소에서는 먼저 로컬 변경과 다른 worktree를 확인한다.

```powershell
git status --short --branch
git worktree list
git fetch origin
git rev-list --left-right --count HEAD...origin/codex/g1-laptop-sync-20260917
```

해당 브랜치이고 로컬이 clean하며 분기되지 않았을 때만:

```powershell
git pull --ff-only origin codex/g1-laptop-sync-20260917
```

새 폴더로 받을 때:

```powershell
git clone --branch codex/g1-laptop-sync-20260917 https://github.com/Y1048/Y.git G1_Teleop_Source
cd G1_Teleop_Source
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\VERIFY_DESKTOP_SOURCE_CHECKOUT.ps1
```

dirty이면 덮어쓰기/reset/clean/강제pull하지 않는다. 두 PC 작업 시작 전fetch, 종료 후작업범위commit/push,
원격HEAD재확인은 `docs/migration/20260917/TWO_PC_SYNC.md` 규칙을 유지한다.

## Git만으로 옮겨지지 않는 것

- **실제 원본 CSV/JSONL**, `logs/` 아래 실행기록·백업·격리 엔진은 노트북 로컬에만 있을 수 있다.
  Git에는 선택한 검증 보고서·fixture만 있다. 분석 보고서의 절대경로는 증거 위치이며 다른 PC 실행경로가 아니다.
- Windows Python/패키지, Unity Library, Meta Horizon Link, Omni Connect, WSL와 그venv는 별도 설치/복원이 필요하다.
- 확인 환경: Python3.11.9, MuJoCo package/native3.12.0, Mink1.3.0, qpsolvers4.13.0,
  DAQP0.9.1, NumPy2.4.6, Ruckig0.19.4. Omni 의존성은 `hardware/g1_arm_bridge/requirements-omni-gateway.txt`.
- Unity 프로젝트 버전은 `Unity_G1_VR/ProjectSettings/ProjectVersion.txt`의6000.5.4f1,
  Meta XR은 Packages/manifest.json의205.0.0. 기존 SampleScene의 양팔 확장을 사용한다.
- BAT는 `py -3.11`을 사용한다. 다른 Python이나 venv를 설치했더라도 BAT가 그 환경을 쓰는지 확인한다.
- MuJoCo3.12.0 격리 경로를 준비한 뒤 `G1_BIMANUAL_ENGINE_ROOT`로 지정할 수 있다.
  runtime `--validate-only`는 엔진과 메타데이터 검사이며 누락된 다른 패키지가null이어도 성공할 수 있다.
  전체 IK 의존성이 갖춰졌다는 판정에는 실제 오프라인 테스트가 필요하다.

```powershell
# 프로젝트에 해당 격리 엔진을 설치/복원한 경우의 예시
$env:G1_BIMANUAL_ENGINE_ROOT = (Resolve-Path .\logs\diagnostics\mujoco_versions\3.12.0).Path
py -3.11 -B .\MuJoCo_G1_Controller\scripts\g1_bimanual_runtime.py --validate-only
py -3.11 -B .\MuJoCo_G1_Controller\scripts\g1_bimanual_runtime.py --mode test
```

Omni Connect는 Bluetooth 연결 후 `ws://127.0.0.1:32123`을 제공해야 한다.
G1 수신기 파일은 `tools/G1_INPUT_RECEIVE_AUDIT.py`이지만 launcher는 기존
`/home/unitree/g1_input_audit_20260921_7e83c4` 배포 폴더를 가정한다. Git pull로 G1 파일이 설치되지는 않는다.

**카메라 경로에는 아직 노트북 고정 경로가 있다.** `START_G1_CAMERA_TO_UNITY.bat`와
`start_camera_tcp_bridge_wsl.sh`는 WSL Ubuntu, `/mnt/c/Users/user/Desktop/G1_Teleop_Project`,
`/home/user/.venvs/g1-teleop`, PC주소192.168.123.99를 가정한다. 다른 checkout 경로/계정이면
그대로 실행되지 않는다. 데스크톱 환경을 확인하고 카메라 경로를 맞춘 뒤 통합실행한다.
통합 `--host`는 관찰 수신 주소만 바꾸며, 카메라의 이 경로까지 바꾸지 않는다.
`--check-only` 통과도 실제 카메라·G1·전체 의존성 검증을 뜻하지 않는다.

현재 노트북의 localhost 관찰 창은 이 push로 종료되거나 다른 PC로 이전되지 않는다.
다른 목적지로 관찰기를 시작하기 전 기존 자신의 관찰 창을 닫고 포트5020/55070/55071 점유를 확인한다.
과거 전신 제어기·AI복귀·하체정책 실험을 현재 입력 관찰 작업으로 오인해 실행하지 않는다.

## 게시 전 검사

변경된 Python 38개 파일은 AST 구문 검사를 통과했다. 기존 실행 테스트와 실착 결과는 위 검증 자료에 구분해 보존했다. 과거 실패 기록 `motion_tests.txt`의 원문 공백은 보존하며, 이를 제외한 staged diff의 공백 검사를 수행했다. 이번 게시 과정에서는 G1 접속·모터 실행을 하지 않았다.
