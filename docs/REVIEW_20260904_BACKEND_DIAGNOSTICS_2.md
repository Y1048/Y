# Backend Mink benchmark and replay full-text review - 2026-09-04

Branch: `main`

This is a **review-only** batch. No production controller, benchmark behavior,
test expectation, hardware configuration or authorization was changed.

## 검토

The following remaining `static_only` files were read in full:

```text
backend/tests/test_mink_candidate_benchmark.py
backend/tests/test_mink_tracking_lag.py
backend/tests/test_recorded_pose_speed_comparison.py
backend/tests/test_recorded_reach_bound.py
backend/tools/benchmark_mink_candidate.py
backend/tools/benchmark_mink_rendered_replay.py
backend/tools/compare_recorded_pose_speeds.py
backend/tools/diagnose_mink_tracking_lag.py
backend/tools/diagnose_recorded_reach.py
backend/tools/offline_render_worker.py
```

All reviewed tools are offline planner, replay, reach-bound or render
diagnostics. They create no Unitree SDK/DDS publisher and send no robot command.
Their reports are kinematic and timing evidence, not physical authorization.

### Existing R20 remains confirmed

`benchmark_mink_candidate.py` reports `DEADLINE_MISSES` but returns process
success whenever trajectory parity holds. `benchmark_mink_rendered_replay.py`
also returns success for `DEADLINE_MISSES` and `DISPLAY_AGE_MISSES`, and only
returns nonzero for parity/render failure. `compare_recorded_pose_speeds.py`
can report `REVIEW_REQUIRED` without returning a nonzero status.

These are already recorded R20 surfaces. The reviewed tests correctly exercise
status classification and numerical behavior, but do not change the CLI exit
contract.

### Existing R24 remains confirmed

`diagnose_mink_tracking_lag.py` still describes the candidate as using
unchanged `40/100 deg/s` limits. Its actual planner receives
`virtual_center_velocity_limits()`, which currently supplies `0.08 rad/s` for
all seven right-arm joints. The reported provenance is therefore stale. This is
the existing R24 defect and does not require a new finding number.

### Existing R27 remains the transform-validation boundary

Recorded target rotations are validated as finite proper rotation matrices in
`compare_recorded_pose_speeds.py` before `_matrix_to_se3()` is called. This
caller is stricter than the generic transform API. Generic callers that do not
perform the same SO(3) validation remain covered by R27; this batch neither
widens nor closes it.

### Other conclusions

- Candidate cache keys bind exact configuration, mocap state, timestep and
  collision-limit settings; cached arrays are copied before return.
- The broadphase only skips pairs when conservative bounding radii prove them
  outside the narrow-phase distance, and unsupported/invalid bounds fall back
  to narrow phase.
- Decoupled rendering uses one bounded coherent latest-state slot and reports
  skipped, stale and trailing states separately. It is explicitly not an input
  transport or physical timing test.
- The reach diagnostic proves only an outside-sphere impossibility bound. It
  explicitly does not claim that targets inside the sphere are feasible or
  collision-free.
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
py -3.11 -m unittest \
  backend.tests.test_mink_candidate_benchmark \
  backend.tests.test_mink_tracking_lag \
  backend.tests.test_recorded_pose_speed_comparison \
  backend.tests.test_recorded_reach_bound
```

Result:

```text
30 tests run
30 passed
```

No WSL, DDS, Unity, Quest or G1 runtime was started. No network, publisher or
robot command was created.

## 남은 항목

1. Keep R20 and R24 remediation separate from this review batch.
2. Continue the remaining backend diagnostic/test helper queue before moving to
   `tools/*.bat` and launcher layers.
3. Preserve R27 until the generic SO(3) validation boundary is remediated and
   tested.
4. Keep all connected-G1 verification deferred and explicitly authorized.

Review result:

```text
new R-number findings       : 0
existing findings confirmed: R20, R24, R27 boundary
physical validation        : NOT AUTHORIZED / NOT RUN
```
