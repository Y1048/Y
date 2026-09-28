# G1 Teleop Current Handoff

이 문서는 현재 `main`의 상태만 요약한다. 과거 단계별 review/validation 기록은 Git history에서 확인한다.

## 현재 기본 실행

```powershell
.\tools\START_G1_VR_TELEOP.bat
```

현재 통합 런처의 목적:

```text
bilateral IK + Omni observation + LowState observation + front camera
NO MOTOR OUTPUT
```

동일 worker가 이미 정상 옵션으로 실행 중이면 재사용한다. Unity 프로젝트가 닫혀 있으면 `Unity_G1_VR`을 `6000.5.4f1`로 연다. Play는 사용자가 직접 켠다.

## 현재 상체 구조

- Quest left/right wrist
- Unity `G1BimanualSimulationSender`
- UDP `127.0.0.1:5020`
- schema `g1.bimanual.unity.sim.v4`
- frame `unity_display_world_v1`
- Python `g1_bimanual_runtime.py`
- Mink/MuJoCo 양팔 14축 QP
- compute 60 Hz
- observation display 100 Hz

현재 제어 수치:

```text
proximal velocity = 90 deg/s
wrist velocity    = 180 deg/s
acceleration      = 90 deg/s²
IK tracking rate  = 1.0 /s
```

production bimanual path에서 pseudo-inverse correction/rate heuristic은 제거됐다.

## 최근 속도 개선

`IK_TRACKING_RATE_S=1.0` fixed profile을 실제 G1 세션에서 사용했고 이전보다 체감 추종 속도가 크게 좋아졌다.

추가 offline 실험:

- rate 1.03~1.09: tracking error 이득이 작고 1.10부터 rotation-quality gate가 깨짐
- acceleration 95~105 deg/s²: 실제 replay 이득이 거의 없음
- adaptive position gain: 소폭 개선은 있었지만 복잡성 대비 가치가 작음

결론:

```text
현재 fixed 1.0 / 90 / 180 / 90 profile 유지
추가 gain heuristic 미적용
```

## 남은 큰 position residual

최근 session 분석에서 큰 wrist error는 단순 속도 문제만이 아니었다.

확인 과정:

1. 목표가 거의 정지한 구간에서도 큰 error가 오래 남음
2. orientation cost를 줄이거나 0으로 해도 일부 구간은 거의 동일
3. posture/damping/shoulder-comfort를 줄여도 동일
4. joint hard limit에 붙지 않은 구간에서도 발생
5. 다중 초기값 nonlinear IK에서도 일부 target은 큰 최소오차가 남음
6. G1 shoulder 기준으로 world target이 실제 팔 길이보다 먼 구간이 많음

현재 문제 정의: **Quest absolute world wrist workspace와 G1 arm reachable workspace의 체격/기구 차이.**

생산 코드에는 아직 adaptive position gain, permanent reach clamp, global movement scaling, engage-relative mapping 복원을 넣지 않았다.

향후 필요하면 **world-frame/Omni 계약을 유지하는 별도 retargeting layer**로 설계한다.

## PiP

PiP bug는 수정됐다.

이전: `CenterEyeAnchor` parent -> 사람 머리를 따라감.

현재: `G1 RobotRoot` parent -> G1/Omni 기준 유지.

관련 commit lineage:
- `37510e9` Anchor G1 camera PiP to robot root
- `2b99f68` Simplify bimanual IK tracking rate

## Omni / world frame

현재 upper-body contract:

```text
Quest aligned world wrist
 -> Unity/G1 axis mapping
 -> absolute world wrist target
 -> rotating G1/MuJoCo base
```

engage-relative v1 packet과 현재 world v4 packet을 섞지 않는다. 상세는 `docs/OMNI_WORLD_UPPER_BODY_20260922.md`.

## 기본 launcher와 motor authority

`START_G1_VR_TELEOP.bat`은 G1 motor command를 하지 않는다.

물리 출력은 별도 `hardware/g1_arm_bridge/` 경로다. 현재 운용 원칙은 **항상 양팔 14축**이며, 소스에 남아 있는 right-arm-only Gate/trial은 deprecated라 사용하지 않는다. 현재 live bilateral motor tracking은 아직 미완성 상태다.

## 검증

최근 문서/정리 이후 bimanual regression:

```text
116/116 PASS
fixture historical exact replay max q difference = 0
G1.zip actual-session exact replay = PASS
input rows = 7,837 / accepted = 7,836
state/q rows = 46,570
state mismatch = 0
reason mismatch = 0
tick_action mismatch = 0
max q difference = 2.000621890374532e-13 rad
official --mode report --replay --strict exit = 0
```

`G1.zip` 원본은 현재 PC의 `C:\Users\user\Desktop\G1.zip`에 있으며 저장소에는 커밋하지 않는다. session snapshot의 `g1_bimanual_limits.py`와 `g1_bimanual_unity_sim.py`는 raw hash만 newline 차이로 달랐고 normalized content hash는 current source와 동일했다.

### Replay 보존 규칙

다음은 이름이 legacy처럼 보여도 현재 실행/replay/회귀에 필요하므로 임의 삭제하지 않는다.

- `MuJoCo_G1_Controller/scripts/g1_bimanual_*.py` current core
- `run_mink_g1_right_arm_prototype.py`, `g1_right_arm_common.py`, `g1_mink_collision_policy.py` 및 G1 MuJoCo model tree의 전이 의존성
- `backend/tests/test_bimanual_*.py`, `backend/tests/bimanual_replay_profiles.py`, `backend/tests/fixtures/bimanual_*`
- `experiments/twist2_right_arm_manual/`: current bimanual regression의 upstream Mink 비교 reference와 CI가 직접 참조
- `experiments/independent_locomotion/`: replay dependency는 아니지만 현재 `tools/START_MJLAB_*` launcher가 남아 있어 보존

## 저장소 정리

과거 validation/migration/review 산출물을 제거했고 실행과 회귀에 필요한 source/tests/experiments는 보존했다. 2026-09-28 2차 정리에서는 현재 bilateral 실행과 `G1.zip` replay 양쪽에 불필요한 `g1_velocity_mink_right_arm_20260914`, `startup_recovery_multistrategy`, `startup_recovery_posture_sweep`만 제거했다.

현재 핵심 문서:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CODE_GUIDE.md`
- `docs/PROTOCOL.md`
- `docs/OMNI_WORLD_UPPER_BODY_20260922.md`
- `docs/PORTABLE_TELEOP_SETUP.md`
- `MuJoCo_G1_Controller/README.md`
- `Unity_G1_VR/README.md`

## 다음 개발 순서

1. 현재 fixed speed profile을 유지한다.
2. PiP RobotRoot behavior를 실제 Play에서 재확인한다.
3. controller/replay dependency를 바꾸면 `116/116` 회귀와 `G1.zip` actual-session strict replay를 함께 다시 실행한다.
4. 큰 wrist target residual이 계속 문제면 retargeting을 별도 mapping layer로 설계한다.
5. physical live tracking은 right-arm-only contract를 재사용하지 말고 bilateral 14-joint contract로 교체한 뒤 별도 승인한다.
6. 추가 정리는 파일명이나 legacy 명칭이 아니라 import/test/launcher/CI 의존성 감사 후에만 진행한다.

기존 dirty/untracked 작업은 임의 reset/clean하지 않는다.
