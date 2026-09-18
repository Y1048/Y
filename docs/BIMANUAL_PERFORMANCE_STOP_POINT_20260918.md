# 양팔 성능 미세최적화 중단 기준 — 2026-09-18

기준 커밋: `1e28597` (`Optimize stopping-tail collision broadphase`).
현재 production 후보는 conservative bounding-sphere broadphase까지이며,
5mm hard clearance, 0.25도 sweep substep, exact `mj_geomDistance`,
zero-distance robust 경로를 유지한다.

이번 후속 작업은 sphere 이후에 더 줄일 수 있는 저위험 계산 비용을 조사했다.
결론은 **추가 미세최적화를 production 코드에 넣지 않는다**이다.
효과가 없거나 호스트 변동보다 작았고, 안전 의미를 바꿀 이유가 없었다.

## 1. squared sphere mask

`np.linalg.norm(delta)`의 sqrt를 없애고 squared center distance를 비교하는 후보를 검증했다.
기록 fixture 약 1,284,953 pair mask와 random 약 1,317,000 pair mask에서
기존 norm 판정과 불일치는 0건이었다.
mask 단독 microbenchmark는 약 10.33us → 5.32us로 빨랐다.

하지만 독립 clean worktree에서 A-B-B-A 전체 Quest replay를 다시 측정하면
전체 평균 21.203s → 21.309s, p95 14.606ms → 14.687ms로 개선이 재현되지 않았다.
p50만 약 1.5% 빨랐고 나머지는 동급/소폭 악화였다.
따라서 numpy mask 자체 절감은 전체 stopping-tail 비용에서 너무 작다고 판정했다.

## 2. sphere + AABB 2단계 broadphase

sphere survivor에만 기존 rotated world-AABB를 추가 적용하는 후보를 검사했다.
두 단계 모두 보수적 하한이라 안전 판정은 유지되지만, AABB 계산 비용이 더 컸다.
동일 fixture에서 sphere-only 대비 전체 replay 평균이 약 2.62% 느려졌다.
따라서 적용하지 않는다.

## 3. `mj_geomDistance` distmax 축소

threshold 경로에서 20cm 대신 5mm를 `distmax`로 주는 후보를 검사했다.
random 500자세, 219,500 pair에서 cutoff 내부 실제 거리값 불일치는 0건이었다.
그러나 실제 Quest replay에서는 전체 시간이 일관되게 개선되지 않았고 일부 실행은 더 느렸다.
MuJoCo의 이 mesh 조합에서는 작은 distmax가 더 싼 경로라는 보장이 없었다.
따라서 적용하지 않는다.

## 4. unsafe pair 조기 반환

stopping-tail threshold 검사에서 5mm 미만 pair를 찾는 즉시 나머지 pair를 건너뛰는 후보도 측정했다.
Quest 성공 fixture의 threshold call은 162,722회였고 broadphase survivor는 총 1,282,088 pair였다.
조기 반환으로 실제 생략 가능한 pair는 171개뿐이었다.
즉 exact pair 호출 절감은 약 **0.0133%**였다.
unsafe sample 자체가 47회뿐이어서 전체 성능 개선 수단으로는 의미가 없다.

## 현재 결론

sphere broadphase 이후 threshold call당 exact candidate는 평균 약 7.88개다.
여기서 더 줄이려면 단순 numpy 식 변경이 아니라 stopping-tail collision 평가 구조 자체를 바꿔야 한다.

다음 성능 작업은 아래 조건을 만족할 때만 검토한다.

- sampled stopping trajectory의 모든 기존 시각점을 유지한다.
- 5mm hard clearance와 0.25도 substep을 완화하지 않는다.
- survivor pair의 exact MuJoCo geometry 판정을 대체하거나 근사하지 않는다.
- 0거리 mesh/contact robust 경로를 유지한다.
- Quest fixture의 q 경로가 0rad 차이로 유지된다.
- clean worktree에서 반복 A/B로 유의미한 개선이 재현된다.

따라서 후보는 batch/parallel evaluation처럼 구조적인 방식뿐이며,
그 역시 별도 `MjData` 소유권, deterministic 결과, 예외/zero-distance 경로를 증명하기 전에는 적용하지 않는다.
현재 `1e28597`의 구현을 성능/안전 균형 기준점으로 유지한다.

이번 조사 중 사용한 실험용 worktree/스크립트는 production source에 포함하지 않는다.
동시에 진행 중인 session-report 미커밋 작업도 수정하거나 커밋하지 않았다.
