# 양팔 clearance 2차 성능 최적화 — 2026-09-18

기준 브랜치: `codex/g1-laptop-sync-20260917`, 출발 커밋 `dc1a29a`.
직전 단계의 `mj_fwdPosition()` 최적화와 Quest 성공 세션을 그대로 기준으로 삼았다.
이번 작업은 sampled collision 계산 비용만 더 줄이며, 동작 목표와 안전 한계를 바꾸지 않는다.
실제 G1/DDS 출력은 수행하지 않았다.

## 왜 추가 최적화했는가

성공한 Quest fixture 2,927 state tick을 프로파일링하면 여전히 가장 큰 비용은
`checked_stop_plan()` 안에서 반복하는 future stopping-tail clearance 검사였다.
QP solve 자체는 병목이 아니며, 충돌 샘플 수와 0.25도 sweep substep은 유지해야 한다.

직전 `dc1a29a`는 `mj_forward()`를 `mj_fwdPosition()`으로 바꿨다.
이번에는 일반적인 non-contact 거리 계산이 geometry transform만 필요하다는 점을 이용해
정상 경로를 `mujoco.mj_kinematics()`로 더 줄였다.

단, MuJoCo가 정확히 0m를 반환하면 contact 배열이 필요한 기존 zero-mesh/contact 판정을
그대로 사용해야 한다. 이때만 한 번 `mj_fwdPosition()`으로 승격한 뒤
기존 `base._robust_geom_distance()`의 exact-contact / zero-distance probe를 실행한다.

## 동등성 검증

기록된 Quest 자세 300개에서 439개 collision pair 전체를 비교했다.
`mj_fwdPosition()`과 `mj_kinematics()`의 `geom_xpos`, `geom_xmat`,
모든 raw `mj_geomDistance` 값은 최대 차이 0이었다.
위치 단계 단독 벤치마크에서 300자세 median은 약 5.083ms 대 1.246ms였다.

추가로 joint range 내부 random 자세 500개를 full `mj_forward()` 기준과 비교했다.
최종 nearest clearance는 모두 정확히 같았다.
0거리 입력은 `mj_fwdPosition()`과 기존 robust 경로로 승격되는지,
일반 nonzero 입력은 승격하지 않는지도 별도 회귀 테스트로 확인한다.

실제 Quest 성공 fixture 전체 재생에서도 다음이 유지됐다.

- 2,927 state tick의 기록 관절값과 현재 계산값 최대 차이 0rad.
- 최소 sampled clearance 5.032381mm.
- 두 pinch 복귀와 중간 재engage 상태 전이 유지.
- 최종 상태 READY, 복귀 replan 없음.

5mm hard clearance, 0.25도 sweep substep, 속도/가속도 한계,
공동 14축 QP, ArmMotionPolicy, 단계형 Ruckig 복귀는 변경하지 않았다.

## A/B 성능

같은 Quest fixture를 `dc1a29a`의 `mj_fwdPosition()` clearance와
새 `mj_kinematics()` clearance로 A-B-B-A 순서로 직접 재생했다.
각 실행은 동일한 2,927 state tick을 처리했고 관절 경로 차이는 0rad였다.

| 항목 | 기존 평균 | 새 평균 | 감소 |
| --- | ---: | ---: | ---: |
| 전체 재생 | 20.209초 | 17.041초 | 15.67% |
| tick p50 | 6.066ms | 5.053ms | 16.71% |
| tick p95 | 15.055ms | 12.274ms | 18.47% |
| tick p99 | 18.339ms | 15.066ms | 17.85% |
| 실행별 최대 tick 평균 | 23.133ms | 19.759ms | 14.58% |

개별 p95는 기존 14.772/15.338ms, 새 경로 12.184/12.365ms였다.
호스트 스케줄링의 영향을 받으므로 이 수치를 hard real-time 보증으로 해석하지 않는다.
다만 동일 fixture/동일 프로세스 조건의 반복 비교에서 방향은 일관됐다.

## 5mm 경계는 유지

직전 분석에서 성공 세션 tracking tick의 최소 clearance는 5.032381mm였고,
6mm 미만 구간도 약 12.8%였다. 사용자가 현재 Quest 사용감을 정상이라고 확인했으므로
5mm를 임의로 7~10mm로 올리거나 soft repulsion을 추가하지 않았다.
이번 개선은 계산량만 줄였고 출력 경로를 바꾸지 않았다.

## 전체 회귀와 실행 폴더 반영

소스 작업본 bimanual suite는 **76/76 PASS, 97.577초**였다.
같은 노트북 실행 폴더는 **76/76 PASS, 96.673초**였다.
기존 Quest success fixture, recorded staged fixture, 복귀/재engage 및 예외 회귀가 모두 포함된다.

실행 폴더는 기존 `dc1a29a`와 줄바꿈을 제외한 내용이 일치하는 것을 먼저 확인했다.
그 뒤 다음 두 파일만 백업 후 선택 반영했다.

- `MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py`
- `backend/tests/test_bimanual_sim.py`

백업: `logs/backups/bimanual_kinematic_clearance_20260918_155946/`.
주변 scripts/tests/Unity G1Teleop의 보호 파일 277개는 바이트 변경 0개였다.

실제 `START_BIMANUAL_UNITY_SIM.bat`도 별도 loopback 포트 64842에서
headless 0.35초 기동 후 정상 종료했다. G1 출력은 없었다.
사용자가 이미 실행 중인 Python 프로세스는 종료하지 않았으므로,
새 clearance 구현은 다음 Python 프로세스 시작부터 적용된다.

검증 자료:
- `validation/bimanual_performance_kinematics_20260918/verification.json`
- `validation/bimanual_performance_kinematics_20260918/ab_benchmark.txt`
- `validation/bimanual_performance_kinematics_20260918/kinematics_equivalence.txt`
- `validation/bimanual_performance_kinematics_20260918/source_suite.txt`
- `validation/bimanual_performance_kinematics_20260918/runtime_suite.txt`
- `validation/bimanual_performance_kinematics_20260918/bat_smoke.txt`
