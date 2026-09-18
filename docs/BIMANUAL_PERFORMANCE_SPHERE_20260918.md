# 양팔 clearance bounding-sphere broadphase — 2026-09-18

기준 브랜치: `codex/g1-laptop-sync-20260917`, 출발 커밋 `31a68d4`.
직전 `mj_kinematics` 최적화 이후에도 checked stopping-tail의 반복 clearance가 주 병목으로 남았다.
이번 변경은 broadphase 계산만 바꾸며 실제 exact geometry 거리 계산과 안전 한계는 유지한다.
실제 G1/DDS 출력은 수행하지 않았다.

## 병목 재확인

Quest 성공 fixture의 실제 로그에서 control tick 시간과 이미 검증된 stopping-tail 길이의
상관계수는 약 0.85였다. tail 40 step 이상 구간은 짧은 tail보다 눈에 띄게 느렸다.
따라서 QP나 동작 정책이 아니라, tail의 많은 sampled collision 검사가 다음 최적화 대상이다.

기존 tail을 통째로 재사용할 수 있는 경우도 측정했다.
2,717회의 `checked_stop_plan()` 중 직전 tail의 첫 velocity/candidate와 완전히 같은 경우는
64회, 약 2.4%뿐이었다. 효과가 작고 상태 의존성이 커 이 경로는 적용하지 않았다.

## 적용한 broadphase

각 MuJoCo geom의 local `geom_aabb`를 감싸는 bounding sphere를 초기화 시 미리 계산한다.
매 sampled pose에서는 sphere 중심만 world frame으로 변환하고, 두 sphere 사이의 하한이
5mm보다 큰 pair만 exact `mj_geomDistance` 호출 전 제외한다.

local AABB를 완전히 감싸는 sphere이므로 sphere들이 threshold보다 멀면 실제 geom도 반드시 더 멀다.
threshold 안에 남은 pair는 기존과 동일하게 `mj_geomDistance`를 계산하고,
정확히 0m인 경우에는 이전 `mj_fwdPosition` + robust contact/zero-mesh probe 경로를 사용한다.

5mm hard clearance, 0.25도 sweep substep, stopping-tail 길이,
속도/가속도 제한, 공동 14축 QP, ArmMotionPolicy, 단계형 Ruckig 복귀는 변경하지 않았다.

## 보수성 검증

Quest 성공 기록 2,927자세의 모든 pair에서 sphere가 제외한 약 1,258,802개 pair를
raw `mj_geomDistance`로 다시 검사했다. 5mm 이하 pair를 잘못 제외한 사례는 0건이었다.

추가 random joint-range 자세 1,200개에서도 약 510,643개 제외 pair를 exact distance로
재확인했으며 잘못 제외한 사례는 0건이었다.
production 회귀에는 random 300자세에서 같은 보수성 조건을 직접 검사하는 테스트를 추가했다.
기존 exact clearance와 threshold broadphase의 안전/비안전 판정 회귀도 유지한다.

Quest fixture 전체 재생 결과는 변경 전과 동일하다.

- 기록 관절값과 최대 차이 0rad.
- 최소 sampled clearance 5.032381mm.
- pinch 복귀 2회와 중간 재engage 상태 전이 유지.
- 출력 차분 최대 가속도 60도/s² 제한 유지.

## A/B 성능

시스템 부하가 앞선 측정보다 높은 상태였으므로 절대 시간보다는 같은 A-B-B-A 실행 내 상대값만 사용한다.
동일한 2,927 state Quest fixture에서 `31a68d4`의 world-AABB broadphase와 새 sphere broadphase를 비교했다.

| 항목 | 기존 평균 | sphere 평균 | 감소 |
| --- | ---: | ---: | ---: |
| 전체 재생 | 28.034초 | 24.009초 | 14.36% |
| tick p50 | 7.649ms | 7.098ms | 7.20% |
| tick p95 | 20.902ms | 17.300ms | 17.23% |

두 sphere 실행의 p95는 17.079ms와 17.521ms였고,
두 기존 실행은 23.021ms와 18.784ms였다.
모든 A/B에서 관절 경로 차이 0rad, 최소 clearance 5.032381mm, 최종 READY가 동일했다.
p99/max는 호스트 outlier 영향이 커 비교 결론의 근거로 사용하지 않는다.
이 결과 역시 hard real-time 60Hz 보증이 아니다.

## 독립 검증과 병렬 작업 분리

검증 중 같은 source worktree에 별도 session-report 작업의 미커밋 파일이 나타났다.
해당 파일은 수정·삭제·커밋하지 않았다. sphere 변경과 겹치는 두 파일의 diff를 확인한 결과
`g1_bimanual_sim.py`와 `test_bimanual_sim.py`에는 sphere 변경만 있었다.

재현 가능한 검증을 위해 `31a68d4`에서 detached clean worktree를 만들고
sphere 두 파일만 복사해 전체 suite를 실행했다. 결과는 **77/77 PASS, 106.791초**다.
이는 병렬 작업의 추가 테스트를 포함하지 않는 이번 커밋 자체의 기준 결과다.

실행 폴더에는 두 대상 파일만 기존 `31a68d4`와 내용이 일치함을 확인한 뒤 백업·반영했다.
백업: `logs/backups/bimanual_sphere_broadphase_20260918_172922/`.
주변 scripts/tests/Unity G1Teleop 보호 파일 279개는 바이트 변경 0개였다.

실행 폴더의 이번 변경 관련 `test_bimanual_sim` + Quest replay는 **16/16 PASS, 35.462초**다.
현재 실행 폴더 전체 suite도 82/82 PASS였지만, 그중 5개는 병렬 session-report 작업의
아직 미커밋 테스트이므로 이번 Git 커밋의 재현 결과로 세지 않는다.
실제 BAT는 별도 loopback 포트 57284에서 headless 0.35초 기동·종료했다.

사용자의 기존 Python 프로세스는 종료하지 않았다.
새 broadphase는 다음 Python simulation 시작부터 로드된다.
Unity/C#과 실제 G1/DDS는 변경하거나 실행하지 않았다.

검증 자료:
- `validation/bimanual_performance_sphere_20260918/verification.json`
- `validation/bimanual_performance_sphere_20260918/clean_suite.txt`
- `validation/bimanual_performance_sphere_20260918/runtime_targeted.txt`
- `validation/bimanual_performance_sphere_20260918/sphere_bound_validation.txt`
- `validation/bimanual_performance_sphere_20260918/ab_benchmark.txt`
- `validation/bimanual_performance_sphere_20260918/bat_smoke.txt`
