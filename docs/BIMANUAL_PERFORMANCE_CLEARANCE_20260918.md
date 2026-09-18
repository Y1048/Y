# 양팔 충돌 여유와 제어 tick 성능 분석 — 2026-09-18

기준 브랜치: `codex/g1-laptop-sync-20260917`, 출발 커밋 `a65495f`.
실제 Quest에서 정상 동작을 확인한 세션과 그 회귀 fixture를 사용했다.
이번 변경은 시뮬레이션 collision 검사 계산만 최적화한다.
실제 G1/DDS 출력은 수행하지 않았다.

## 확인한 병목

성공 fixture 2,927 state tick을 함수별로 프로파일링했다.
tracking tick에서 QP solve 자체는 병목이 아니었다.

- `qpsolvers.solve_problem`: 2,081회 합계 약 91ms, 평균 약 0.044ms.
- `mink.build_ik`: 합계 약 395ms.
- `checked_stop_plan`: 2,717회 합계 약 16.7초, p95 약 15.23ms.
- 그 안의 `clearance`: 162,727회, 합계 약 14.16초.

따라서 대부분의 비용은 매 명령에 대해 미리 검사하는 정지 tail의 sampled collision 검사였다.
정지-tail 샘플 수나 0.25도 substep, 5mm hard clearance를 줄이지 않았다.

## 적용한 최적화

`BimanualSimulation.clearance()`는 qpos를 바꾼 뒤 collision geometry와 contact만 필요하다.
기존에는 전체 `mujoco.mj_forward()`를 호출해 velocity/actuation/acceleration 단계까지 계산했다.
이를 position-dependent 단계인 `mujoco.mj_fwdPosition()`으로 바꿨다.

안전 판정 의미가 같은지 먼저 오프라인으로 확인했다.
임의 joint-range 내부 자세 500개에서 기존 full-forward와 position-only 결과를 비교했다.

- nearest distance 최대 차이: 0m.
- nearest geom pair 불일치: 0회.
- contact count 불일치: 0회.
- finite/nonfinite 판정 불일치: 0회.

실제 Quest 성공 fixture에서도 현재 코드의 출력 관절 경로는 기존 로그와 최대 차이 0rad였고,
최소 sampled clearance 5.032381mm와 두 pinch 복귀/re-engage 상태 전이가 그대로 유지됐다.

## A/B 성능

같은 2,927 state fixture를 이전 `mj_forward`와 새 `mj_fwdPosition`으로 직접 재생했다.
한 쌍의 동일 조건 측정은 다음과 같다.

| 항목 | 이전 | 최적화 후 |
| --- | ---: | ---: |
| 전체 재생 | 21.732초 | 19.789초 |
| tick p50 | 6.514ms | 5.924ms |
| tick p95 | 16.416ms | 14.627ms |
| tick p99 | 19.612ms | 18.535ms |
| 최대 tick | 26.035ms | 24.385ms |

다른 실행에서도 이전 21.569초/p95 16.447ms 대비 최적화 19.649초/p95 14.444ms였다.
호스트 스케줄링 영향을 받으므로 최대값이나 한 번의 p95를 hard real-time 보증으로 해석하지 않는다.
두 A/B 모두 관절 경로 차이 0rad, 최소 clearance 동일, replan 0회였다.

## 5mm 충돌 경계 분석

성공 세션의 tracking state 2,081개를 별도로 검사했다.
최소 sampled clearance는 5.032381mm이며 sequence 1575에서 나왔다.
가장 가까운 쌍은 왼손목 yaw collision geom과 오른손 rubber-hand collision geom이다.
그 순간 두 wrist-yaw body 중심 거리는 약 79.61mm였다.

경계 근처 분포:

- 5.1mm 미만: 5틱(0.24%).
- 6mm 미만: 267틱(12.83%).
- 7mm 미만: 589틱(28.30%).
- 10mm 미만: 672틱(32.29%).

즉 5mm 근접은 한 번의 이상치만은 아니다. 양팔 동작 중 hard clearance 제약이 실제로 자주 활성화된다.
사용자가 현재 Quest 동작감을 정상으로 확인했으므로 이 작업에서는 5mm를 7~10mm로 올리거나
soft repulsion을 추가하지 않았다. 그렇게 하면 상당한 tracking 구간의 자세와 사용감이 바뀔 수 있다.

이 5mm는 고정 기구학 장면의 sampled geometry 간격이다.
실제 로봇의 링크 오차, 탄성, 제어 지연이나 연속시간 충돌 안전 여유를 보증하지 않는다.

## 전체 검증과 설치

새 동등성 검사를 `test_bimanual_sim.py`에 추가했다.
임의 자세에서 full-forward와 position-only contact/nearest distance가 같은지 지속적으로 확인한다.

- 소스 bimanual suite: **74/74 PASS**, 89.330초.
- 노트북 실행 폴더 suite: **74/74 PASS**, 96.558초.
- Quest 성공 fixture: 관절 경로 최대 차이 0rad, 최소 clearance 5.032381mm.
- 기존 recorded staged fixture: 관절 경로 최대 차이 0rad.

같은 노트북의 실행 폴더에는 다음 두 파일만 기존 HEAD와 일치함을 확인한 뒤 백업하고 반영했다.

- `MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py`
- `backend/tests/test_bimanual_sim.py`

백업: `logs/backups/bimanual_perf_20260918_154241/` (실행 폴더 기준).
Unity/C# 파일, IK motion policy, Ruckig 복귀, 속도/가속도/clearance 값은 이번 설치에서 변경하지 않았다.

사용자가 이미 실행 중인 Python 프로세스는 종료하거나 재시작하지 않았다.
파일 반영은 다음 Python 시작부터 적용된다. 현재 세션을 유지하고 있다면 그 세션은 이전 로드된 코드로 계속 동작한다.

검증 자료:
- `validation/bimanual_performance_clearance_20260918/verification.json`
- `validation/bimanual_performance_clearance_20260918/profile_report.json`
- `validation/bimanual_performance_clearance_20260918/baseline_old.txt`
- `validation/bimanual_performance_clearance_20260918/optimized.txt`
