# 양팔 세션 자동 리포트 — 2026-09-18

기준 브랜치: `codex/g1-laptop-sync-20260917`, 출발 커밋 `31a68d4`.
Quest 동작이 안정된 뒤 반복 로그를 매번 수작업으로 분석하지 않도록
읽기 전용 세션 리포트 도구를 추가했다. 실제 G1/DDS/SSH/모터 출력은 없다.

## 실행

가장 최근의 실제 operator input이 있는 세션을 빠르게 분석한다.

```powershell
.\tools\REPORT_LATEST_BIMANUAL_SESSION.bat
```

현재 시뮬레이터로 입력을 끝까지 재생해 q 경로와 clearance까지 확인하려면:

```powershell
.\tools\REPORT_LATEST_BIMANUAL_SESSION.bat --replay --strict
```

보고서는 실행 폴더의 `logs/test_results/bimanual/reports/` 아래 JSON과 Markdown으로 저장된다.
`--latest`는 더 최근에 생성된 headless smoke 로그에 accepted input이 없으면 건너뛰고
실제 operator packet이 들어온 최신 세션을 우선 선택한다.

## 정적 분석 항목

JSONL을 스트리밍으로 읽어 대용량 로그도 전체를 메모리에 올리지 않는다.
다음 항목을 자동으로 계산한다.

- READY/TRACKING/RETURNING/BLOCKED 상태 전이와 reason.
- tracking 시작 횟수와 재engage 횟수.
- 각 복귀의 reason, wall time, 내부 simulation time, waypoint/home/complete stage와 replan 수.
- input engage/return/tracked flag 변화와 reject reason.
- control tick, tracking tick, loop period의 p50/p95/p99/max.
- 기록 q를 고정 dt=1/60초로 차분한 최대 속도/가속도와 기존 관절 한계 초과 여부.
- run 행의 다섯 Python SHA-256과 현재 소스의 일치 여부.

기록 q 차분 속도/가속도는 실제 모터 측정값이 아니다.
`tracking_tick_p95_exceeds_nominal_60hz_period`와 source hash 차이는 warning이다.
과거 정상 세션을 새 코드로 읽을 때 source hash warning은 정상적으로 발생할 수 있다.

BLOCKED, nonfinite/malformed joint output, 속도/가속도 한계 초과는 failure다.
`--strict`는 warning만으로 실패하지 않고 failure 또는 replay 안전/경로 불일치에서 nonzero로 종료한다.

## `--replay`

report 모드는 기존 `g1_bimanual_runtime.py`의 validated MuJoCo 3.12 bootstrap을 사용한다.
`--replay`에서는 기록된 raw input을 현재 decoder/UnityCycle/BimanualSimulation으로 다시 넣는다.

검사 항목:

- 기록의 input accepted/rejected 결과와 현재 decoder/cycle 결과 일치.
- state와 reason 일치.
- 기록 q와 현재 q의 최대 차이 5e-6rad 이하.
- active output의 sampled clearance 5mm 이상.
- 출력 가속도 60도/s² 이하.
- 최종 복귀 stage/replan과 상태.

Quest 성공 fixture에 대한 `--replay --strict`는 PASS했다.
2,927 state tick, 2,016 input을 재생했고 q 최대 차이 0rad,
최소 sampled clearance 5.032381mm, 최대 출력 가속도는 수치 오차 범위의 60도/s²였다.
두 pinch 복귀와 사이의 재engage도 그대로 재현됐다.

이 replay는 fixed-base sampled geometry 검증이며 물리 G1 제동/연속시간 충돌 증명이 아니다.

## 상태 전이 집계와 검증

상태 전이는 `(state, reason)` 조합이 아니라 **state 자체가 실제로 바뀔 때만** 집계한다.
따라서 TRACKING 중 reason만 바뀌어도 재engage로 세지 않고, RETURNING 중 reason만
바뀌어도 새 return을 시작한 것으로 세지 않는다.

세션-report/runtime 타깃 테스트는 21/21 PASS였고, 당시 전체 bimanual suite는 86/86 PASS였다.
Quest 성공 fixture의 static `--strict`와 replay `--strict`는 exit 0, malformed synthetic session의
validated-runtime strict 실행은 exit 1을 확인했다.

## 최신 operator 세션에서 발견한 복귀 실패

리포트 도구는 더 최신인 headless smoke들을 건너뛰고
`unity_20260918_155812_5222579.jsonl`을 실제 operator 세션으로 선택했다.
이 세션은 sequence 697의 tracking loss 뒤
`return_path_blocked:return_swept_clearance`로 BLOCKED가 되었고 strict report는 exit 1이었다.
이 실패는 [near-hands return v2](BIMANUAL_NEAR_HANDS_RETURN_20260918.md)의 회귀 fixture로 보존했다.

과거 v1 전체 세션을 v2에 그대로 대입해 state 일치를 강제하는 대신, 실패 시점의
q/velocity/acceleration과 기존 checked brake tail을 작은 fixture로 고정해 v2 return을 검증한다.
현재 실행 폴더에는 session-report 후속 수정과 near-hands v2를 함께 반영했다.
새로 시작하는 simulation 로그는 `return_policy=bimanual_staged_return_v2`를 기록해야 한다.
