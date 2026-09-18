# Quest 실제 pinch/re-engage 확인 — 2026-09-18

기준 브랜치: `codex/g1-laptop-sync-20260917`, 출발 커밋 `45146f4`.
사용자가 최신 Quest 세션을 실행한 뒤 "잘된다"고 확인했다.
이 문서는 주관적 사용감 확인과 같은 세션의 기계 로그를 구분해 함께 보존한다.
실제 G1/DDS 물리 제어는 수행하지 않았다.

## 실제 세션 로그

원본: 노트북 실행 폴더의
`logs/test_results/bimanual/unity_20260918_144806_4738178.jsonl`.

원본 SHA-256:
`cd9f1af99c2c1000035d5c277fbe0cde55e487db92c4c91c36588b3f0ab204d3`.
크기 9,289,214 bytes.

run 행은 `bimanual_motion_v1`, `bimanual_boundary_v1`,
`bimanual_staged_return_v1`, MuJoCo 3.12.0을 기록한다.
기록된 다섯 Python source SHA-256은 현재 소스와 모두 일치했다.

## 로그에서 확인한 상태 전이

`READY → TRACKING → RETURNING(pinch) → READY → TRACKING → RETURNING(pinch) → READY`

첫 tracking 시작 입력 sequence는 457, 첫 pinch 요청은 1786이었다.
첫 복귀는 로그 시각 기준 약 5.781초에 완료됐고 재계획은 없었다.
그 뒤 sequence 2119에서 다시 engage되어 두 번째 TRACKING이 확인됐다.
두 번째 pinch 요청은 sequence 2215였고, 두 번째 복귀는 약 5.437초에 완료됐다.

두 복귀 모두 `safe_waypoint → home → complete` 순서를 거쳤다.
첫 복귀의 Ruckig 내부 simulation time은 5.383초,
두 번째는 5.217초이며 둘 다 마지막 0.5초 정착을 포함한다.
로그에 BLOCKED나 reject packet은 없었다.

전체 세션의 상태 행은 4,400개, input 행은 2,571개였다.
기록 qpos 차분 기준 최대 관절속도는 약 74.53도/s,
최대 가속도는 수치 오차 범위에서 60도/s²였다.
IK 보호 감속 이유는 `checked_braking:swept_clearance` 47틱이었다.

제어 tick은 p50 약 4.90ms, p95 약 20.29ms, 최대 약 33.94ms였다.
따라서 사용자가 체감상 정상이라고 확인한 것과 별개로,
모든 host loop가 지속적으로 16.67ms 안에 끝난다고 주장하지 않는다.

## 실제 기록 회귀 fixture

sequence 450부터 2465까지를 압축 fixture로 보존했다.

`backend/tests/fixtures/bimanual_quest_reengage_20260918.json.gz`는
run 1행, input 2,016행, state 2,927행으로 총 4,944행이다.
압축 SHA-256은
`1f05d7f921768955e64515d3486f7f2c975db9653a4ebaa1945e5915f5b26814`이다.

`test_bimanual_quest_reengage.py`는 원 packet과 tick 시각으로 현재
`UnityCycle`/`BimanualSimulation`을 재생한다. 결과는 기록과 최대 관절값 차이 0rad,
최소 sampled clearance 5.032381mm, 최대 출력 차분 가속도 60.000000000063도/s²였다.
두 pinch 복귀와 그 사이의 재engage 상태 전이가 그대로 재현됐다.

새 fixture 테스트를 포함한 전체 bimanual suite는 **73/73 PASS, 115.560초**였다.
이 수치는 한 번의 완료 실행이며 실시간 성능 benchmark가 아니다.

## 사용자 확인과 자동 검증의 범위

사용자 확인은 실제 Quest 착용 상태에서 현재 조작 흐름이 정상이라는 주관적 검증이다.
자동 fixture는 해당 세션의 UDP 입력/시뮬레이션 상태가 현재 코드에서 재현되는지를 검증한다.
둘을 합쳐도 실제 G1 물리 제동, 연속시간 충돌 무발생 또는 모든 자세에서의 사용감을 보증하지 않는다.

직전 `45146f4`의 `CanClearMustLeave()` 변경은 기존 inline 조건을 함수로 분리한
semantics-preserving 리팩터링이다. 사용자가 성공을 확인한 실행 폴더에는 아직
그 C# 파일을 hot-copy하지 않았다. Unity Editor가 열려 있었기 때문이다.
기능적으로는 성공 세션이 기존 inline leave-zone 로직 자체를 실제로 통과했다.

검증 기록: `docs/validation/bimanual_quest_confirmed_20260918/`.
