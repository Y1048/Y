# Backend Mink diagnostic full-text review - 2026-09-04

Branch: `main`

This is a **review-only** batch. No production controller, diagnostic behavior,
test expectation, hardware configuration or authorization was changed.

## 검토

The following remaining `static_only` files were read in full:

```text
backend/tests/test_mink_collision_diagnostics.py
backend/tests/test_mink_collision_feasibility.py
backend/tests/test_mink_distance_invariance.py
backend/tests/test_mink_feasible_target.py
backend/tests/test_mink_step_acceptance_comparison.py
backend/tools/compare_mink_step_acceptance.py
backend/tools/diagnose_mink_collision_feasibility.py
backend/tools/diagnose_mink_distance_invariance.py
backend/tools/verify_feasible_target.py
```

The tools are offline MuJoCo/Mink diagnostics. They create no Unitree SDK/DDS
publisher and do not authorize robot output. Their path checks are explicitly
sampled kinematic checks, not continuous collision, dynamics or physical safety
proofs.

### Existing R20 remains confirmed

`verify_feasible_target.py` can write and print `REVIEW_REQUIRED` while returning
process success. `diagnose_mink_distance_invariance.py` can similarly emit
`BLOCK_DEPLOYMENT` without a nonzero process status. Both surfaces were already
listed under R20. The corresponding reviewed tests exercise numerical/report
content but do not close process-exit semantics.

### Existing R24 extends to stale test expectations

`compare_mink_step_acceptance.py` still states that its report used `40/100
deg/s` caps even though `BuildPlanner()` obtains the current limits from
`virtual_center_velocity_limits()`, which currently returns `0.08 rad/s` for
all seven right-arm joints.

`test_mink_collision_feasibility.py` also hard-codes `1 / 40` seconds as the
expected minimum duration for a one-degree elbow path. With the current
`0.08 rad/s` cap, the computed value is about `0.218166 s`, not `0.025 s`.
This is the same current-limit/report provenance defect already recorded as
R24, not a new R-number.

### Existing R27 remains the transform-validation boundary

The endpoint-audit paths reconstruct SE(3) goals from saved matrices through
`_matrix_to_se3()` without independently validating SO(3). This is covered by
the existing generic matrix-validation finding R27. The reviewed files do not
justify a duplicate finding.

### Other conclusions

- Exact mesh-contact handling keeps true contacts distinct from isolated
  MuJoCo zero-distance artifacts in the reviewed tests.
- Sampled direct/waypoint paths reject invalid intermediate configurations and
  preserve frozen coordinates, while clearly documenting that sampling is not
  a continuous or dynamic proof.
- Step-acceptance comparison restores the shared orientation-limit policy and
  task cost after lookahead, including its exception path.
- No new independent P1/P2/P3 finding was identified in this batch.

## 코드 수정

```text
Production/controller changes : NONE
Diagnostic behavior changes   : NONE
Test expectation changes      : NONE
Review artifacts only         : YES
```

The pre-existing local Unity code-coverage settings modification was not
touched.

## 테스트

Executed locally with Python 3.11:

```text
py -3.11 -m unittest backend.tests.test_mink_collision_feasibility
```

Result:

```text
8 tests run
6 passed
2 failed
```

Both failures are the R24 stale `1 / 40` expectations. The numerical result in
both cases was `0.2181661564992915 s`, consistent with a one-degree move at the
current `0.08 rad/s` limit.

No WSL, DDS, Unity, Quest or G1 runtime was started. No network or publisher was
created.

## 남은 항목

1. Keep R20 and R24 remediation separate from this review batch.
2. Continue remaining backend diagnostic/test helpers, starting with candidate
   benchmark, tracking-lag, recorded-speed and virtual-center regression tools.
3. Review `tools/*.bat` and launcher layers after the backend helper queue.
4. Preserve R27 until generic SO(3) validation is remediated and tested.

Review result:

```text
new R-number findings       : 0
existing findings confirmed: R20, R27
existing finding extended  : R24 test expectations
physical validation        : NOT AUTHORIZED / NOT RUN
```
