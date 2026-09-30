# G1 Teleop Current Handoff

최종 갱신: 2026-09-30

## 현재 실행

```bat
tools\START_G1_VR_TELEOP.bat
```

BAT는 bundled `runtime/python/python.exe`로 `tools/G1_PORTABLE.py teleop`을 호출하는 3줄짜리 shim이다.

## Portable Python

- CPython Embedded 3.11.9 x64 bundled
- exact 16 package pins bundled
- no system Python
- no `py -3.11`
- no `.venv-teleop`
- no runtime pip repair
- `RUNTIME_MANIFEST.json`으로 base/core/package contract 검증

다른 Windows PC로 옮길 때 프로젝트 폴더 전체를 복사하면 Python 환경도 같이 이동해야 한다.

## Bilateral IK

- 14 arm joints
- one MuJoCo configuration
- left/right tasks solved in the same QP
- proximal 90 deg/s
- wrist 180 deg/s
- acceleration 90 deg/s²
- compute 60 Hz

## Camera

```text
1920x1080 JPEG
15 fps target
16:9 PiP
PiP parent = G1 RobotRoot
SSH transport only
```

## Regression gates

- backend current regression
- hardware Omni/Ruckig regression
- `G1.zip --replay --strict` exact replay
- portable relocation check from a different directory
- 남은 사용자용 BAT 4개 전수 embedded-shim 감사
- operator runtime source의 machine-local Python 경로 금지

2026-09-29 전체 archive validator 추가 후 재검증: backend 219/219 PASS, hardware 38/38 PASS,
code index PASS, no-system-Python startup check PASS. Backend 회귀는 `.git` 없는 export에서도 실행 가능하다. `G1.zip`은 bimanual exact replay뿐 아니라 Quest/Unity, Omni, LowState, PC→G1 observation, G1→GROOT까지 전체 offline strict validation PASS했다.
상세 근거: `docs/G1_ARCHIVE_FULL_OFFLINE_VALIDATION_20260929.md`.

2026-09-30 R1a 재검증: backend 223/223 PASS, hardware 38/38 PASS, `G1.zip archive-validate --strict` PASS, bimanual exact replay state/reason/accepted mismatch 0, max q difference `2.00062189037453e-13 rad`. 변경 C# 3개는 Roslyn syntax error 0. Unity batch validator는 코드 오류가 아니라 기존 Package Manager IPC startup failure로 실행 전 종료되었고, 오래된 `.csproj` 직접 build는 이미 삭제된 과거 C# 파일 4개를 참조해 유효한 semantic compile gate가 아니다.

2026-09-30 R1c 재검증: backend 226/226 PASS, hardware 38/38 PASS, `G1.zip archive-validate --strict` exact PASS, accepted/state/reason mismatch 0, max q difference `2.00062189037453e-13 rad`. `g1_bimanual_safety.py`가 hard geometry clearance, Mink collision bound, acceleration/joint-limit/yaw braking bounds와 checked stop-tail을 소유한다. `g1_bimanual_sim.py`에는 기존 테스트/진단 호환용 `limits`, `clearance()`, `checked_stop_plan()` proxy/alias만 남긴다.

## External dependencies

Unity 6000.5.4f1, OpenSSH, Quest tooling/driver, Omni Connect, G1 network는 외부 dependency다. Python package dependency만 project-local로 완전히 고정한다.

## Upper-body simplification discussion

상체 제어 구조를 수정하거나 gain/limit를 재튜닝하기 전에 `docs/G1_UPPER_BODY_CONTROL_SIMPLIFICATION_AUDIT_20260929.md`를 먼저 읽는다. 2026-09-30 R1a에서 dead Python members를 제거하고, current `unity_display_world_v1` target mapping을 `g1_bimanual_target.py`, historical relative input을 `g1_bimanual_legacy_input.py`, 현재 tuning을 `g1_bimanual_profile.py`로 분리했다. R1b에서는 dormant right-arm sender/preview 분기를 제거했고, R1c에서는 hard safety 계산을 `BimanualSafetyEnvelope`로 이동했다. 이후 heuristic ablation을 완료했다. torso target projection은 연속 입력에서 약 296 mm hidden target jump를 만들면서 hard safety와 역할이 중복되어 제거했다. elbow assist, wrist priority, shoulder comfort, dynamic orientation priority는 제거 시 posture/clearance/braking 또는 joint allocation이 악화되어 유지한다. shoulder-yaw envelope는 ordinary trajectory 영향은 없었지만 independent fallback이라 SafetyEnvelope 안에 유지한다. 실제 replay profile에서는 QP solver 자체보다 checked stop-tail/geometry 검증이 지배적인 계산비용이다. 다음 단계는 gain 재튜닝이 아니라 safety hot path를 하나씩 offline ablation하는 것이다. checked stop-tail은 마지막 안전 gate로 유지한 상태에서 앞단의 겹치는 constraint가 실제로 무엇을 추가하는지 측정한다.

## 작업 원칙

1. BAT는 shim 외 로직 금지.
2. 새 Python dependency가 필요하면 bundled runtime과 manifest를 같이 갱신.
3. 기존 dirty/untracked를 reset/clean하지 않는다.
4. 변경 후 embedded runtime에서 회귀 실행.
5. relocation test 없이 portable 완료로 판정하지 않는다.
