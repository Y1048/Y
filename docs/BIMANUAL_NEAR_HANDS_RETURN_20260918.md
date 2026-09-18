# 양팔 near-hands 복귀 회복 v2 — 2026-09-18

기준 브랜치: `codex/g1-laptop-sync-20260917`.
세션 리포트 도구가 최신 실제 operator simulation 로그에서 복귀 실패를 발견했다.
이 변경은 fixed-base 양팔 시뮬레이션의 복귀 경로만 다루며 실제 G1/DDS/모터 출력은 없다.

## 발견된 실제 simulation 실패

원본 로그:
`unity_20260918_155812_5222579.jsonl`
SHA-256: `8fa12e145b96c07c9f4f1732b365c9d655252e23fffc00fe2733ee74c1d79d5d`.

세션은 sequence 697에서 `tracking_lost`로 RETURNING에 들어갔고,
기존 direct safe-waypoint 경로가 반복해서 swept-clearance에 걸렸다.
최종 상태는 `blocked`, reason은
`return_path_blocked:return_swept_clearance`였으며 BLOCKED state가 860행 기록됐다.

실패 직전 q/velocity/acceleration과 17-step checked brake tail을
`backend/tests/fixtures/bimanual_return_near_hands_20260918.json`으로 보존했다.
기존 v1 알고리즘은 이 fixture에서도 동일 유형의 반복 거부 후 BLOCKED를 재현했다.

## 원인과 trigger

기존 v1은 양팔을 동시에 mirrored safe waypoint로 보냈다.
실패 fixture의 전체 최소 clearance는 시작 시 약 5.788mm였고,
좌·우 팔 사이 inter-arm clearance는 약 8.131mm였다.

기존 정상 return 시작의 inter-arm clearance는 검색 상한 200mm 이상이었고,
Quest 성공 fixture 두 return도 global clearance가 약 25.6/27.1mm였다.
따라서 v2는 **inter-arm clearance가 12mm 미만인 경우에만** near-hands recovery를 사용한다.
팔-몸통 등 다른 pair가 가까운 것만으로 recovery가 켜지지 않도록 trigger를 inter-arm pair로 제한했다.

global start clearance가 5mm 미만이거나 nonfinite이면 기존처럼 fail-closed한다.
inter-arm clearance도 nonfinite이면 복귀를 시작하지 않는다.

## v2 복귀 순서

near-hands 조건에서는 다음 순서를 사용한다.

`checked stop → separate_left/right → 기존 safe waypoint → home → 0.5초 settle → READY`

먼저 기존에 이미 검증된 brake tail을 소비해 0속도까지 정지한다.
그 뒤 좌/우 한 팔 separation 후보를 비교하고 안전 후보를 선택한다.

후보 선택 probe는 출력 명령이 아니다. 60Hz Ruckig pose에서 thresholded clearance를 보고
어느 팔을 먼저 시도할지만 결정한다. 실제로 publish되는 모든 separation step은 기존과 동일하게
`checked_stop_plan()`의 0.25도 sampled swept-clearance, joint range, 속도/가속도 검사를 통과해야 한다.
선택한 separation이 실제 checked path에서 거부되면 checked stop 후 반대쪽 후보를 시도하며,
둘 다 사용할 수 없으면 BLOCKED로 fail-closed한다.

route probe를 full exact/0.25도 sampling으로 수행했을 때 한 tick이 약 243ms까지 늘어났다.
선택용 probe를 60Hz pose + conservative threshold broadphase로 줄인 뒤 fixture의 선택은 동일했고,
transition tick은 약 20ms 수준으로 감소했다. 이는 hard real-time 보증은 아니다.

`return_policy`는 새 로그에서 구분 가능하도록 `bimanual_staged_return_v2`로 올렸다.
기존 v1 기록 fixture는 역사적 증거이므로 그대로 v1을 검증한다.

## 원본 fixture 결과

- 총 510 tick, simulation time 8.5초.
- stage: `near_hands_stop → separate_left → safe_waypoint → home → complete`.
- global 시작 clearance: 약 5.788mm.
- inter-arm 시작 clearance: 약 8.131mm.
- 최소 sampled clearance: 약 5.696mm.
- 최대 출력 속도: 약 44.464deg/s.
- 최대 출력 가속도: 수치 오차 범위에서 60deg/s².
- replan 0회, 최종 home 오차는 수치 roundoff 수준, 최종 READY.

좌우 대칭 변환 fixture에서도 자동으로 `separate_right`를 선택했고,
510 tick / 8.5초에 READY, 최소 clearance 약 5.751mm를 유지했다.
따라서 고정 left-first workaround가 아니라 현재 상태에 따라 좌우 대칭적으로 route를 선택한다.

## 기존 정상 경로 보존

기존 recorded return 시작 2개는 near-hands recovery를 사용하지 않는다.

- tracking_lost: 356 tick / 5.933초, 최소 clearance 약 40.373mm.
- pinch: 321 tick / 5.350초, 최소 clearance 약 39.140mm.

기존 safe waypoint/home Ruckig parity, fault 시 checked braking, timeout, invalid waypoint,
Quest pinch/reengage 기록 재생도 계속 회귀검사한다.

## 최종 독립 검증과 실행 폴더 반영

12mm 조건이 global clearance가 아니라 inter-arm clearance에만 적용되는지도 별도 고정했다.
seeded 자세에서 global clearance는 약 6.768927mm였지만 inter-arm clearance는
약 85.630996mm였고 near-hands recovery가 발동하지 않았다.

`43e108d` 기반 detached worktree에서 isolated MuJoCo 3.12.0으로 전체 bimanual suite
**89/89 PASS, 102.616초**를 확인했다. 실행 폴더에 대상 파일만 반영한 뒤 validated runtime
전체 suite도 **89/89 PASS, 111.748초**였다.

실행 폴더 백업은 `logs/backups/bimanual_near_hands_return_20260918_210946/`이다.
runtime/report/return Python 및 관련 테스트·fixture 7개만 동기화했고, 주변 scripts/tests/
Unity G1Teleop/Editor/tools 보호 파일 385개는 SHA-256 변경 0개였다.

실제 BAT smoke는 production 5020 대신 `127.0.0.1:57287`에서 headless 0.35초로 실행했고
exit 0과 normal exit를 확인했다. 사용자의 기존 Python/Unity 프로세스는 종료하거나
재시작하지 않았으므로 파일 변경은 다음 새 simulation process부터 로드된다.

추가로 separation 실제 sampled path가 probe 이후 `swept_clearance`로 거부되는 경계를
회귀검사했다. 원본 fixture의 zero-speed probe는 left 약 5.787594mm, right 약
4.573178mm이므로 left가 실제 path에서 거부되면 right도 5mm hard clearance를 만족하지
못해 BLOCKED가 맞다. 반대 후보가 probe 기준 안전하다고 가정한 state-machine 검사에서는
checked stop 후 `separate_right`로 전환되는 것도 고정했다. unsafe right 후보는 publish하지 않는다.
이 후속 테스트를 포함한 source/runtime 전체 suite는 각각 91/91 PASS였다.
실행 폴더에는 테스트 파일 하나만 추가 동기화했고 백업은
`logs/backups/bimanual_near_hands_retry_20260918_214512/`, 보호 파일 391개 변경은 0개였다.

## 범위

5mm hard clearance, 0.25도 swept sampling, joint/velocity/acceleration limit,
기존 checked stopping-tail, 공동 14축 QP와 tracking motion policy는 완화하거나 변경하지 않았다.
near-hands route probe는 후보 선택 heuristic일 뿐 safety certificate가 아니다.
실제 출력은 기존 sampled geometry guard를 통과해야 한다.

이 결과는 fixed-base simulation의 sampled geometry 검증이다.
실제 G1의 연속시간 충돌 회피, 구조 오차, 탄성, 지연이나 물리 제동을 증명하지 않는다.

검증 자료는 `docs/validation/bimanual_near_hands_return_20260918/`에 보존한다.
