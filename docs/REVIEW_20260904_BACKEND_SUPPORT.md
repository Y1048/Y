# Backend support/helper full-text review — 2026-09-04

Branch: `main`

This is a **review-only** batch. Production behavior was not modified while recording this review.

## Files reviewed

```text
backend/g1_teleop/inspection_contact.py
backend/g1_teleop/inspection_demo.py
backend/tests/test_inspection_contact.py
backend/tests/test_inspection_demo.py
backend/tests/test_gate7_mujoco_feedback_receiver.py
backend/tests/test_batch_failure_guidance.py
backend/tests/test_code_index.py
backend/tests/test_feasible_target_return.py
backend/tools/inspect_feasible_target_return.py
backend/tools/build_code_index.py
backend/tools/reconcile_review_ledger.py
```

## Conclusions

### Inspection state/demo modules are observational, not an authority path

`inspection_contact.py` tracks policy state and enriches runtime status; it does not alter IK targets, collision constraints, joint limits or motor commands. Its tests explicitly exercise disabled, approach, contact-confirm, surface-follow and retract transitions.

`inspection_demo.py` tracks target proximity/hold completion and appends a fixed-schema CSV result. It does not alter the control target. The current tests cover deterministic approach/hold/completion, hold reset, completion latching and CSV creation.

There are input-hardening opportunities for non-finite `distance_m` / `now_s`, but because this module is observational and the reviewed caller boundary does not use its result to authorize robot output, no new safety R-number is assigned in this batch.

### Gate 7 simulation feedback receiver test

The MuJoCo feedback receiver test verifies out-of-order rejection within one stream, allows an explicit new stream, and verifies that applying feedback changes only dual-arm qpos indices 15..28. This supports the previously reviewed simulation-only feedback boundary; no new finding was added.

### Failure-guidance and code-index tests are administrative only

`test_batch_failure_guidance.py` verifies nearby operator `[ACTION]` text after batch failure markers; it does not validate exit-code correctness or runtime side effects. It therefore must not be treated as evidence that launchers fail correctly. Existing launcher/exit-code findings such as R20/R23/R54/R56 remain unaffected.

`build_code_index.py`, `test_code_index.py` and `reconcile_review_ledger.py` are offline inventory/review-administration tools. They do not import project runtime modules or create network/SDK entities. The review ledger remains conservative by preserving explicit semantic decisions and defaulting new files to `static_only`.

### Existing R20 extends to `inspect_feasible_target_return.py`

`inspect_feasible_target_return.py` computes `OFFLINE_CRITERIA_MET` versus `REVIEW_REQUIRED`, writes the result and prints the verdict, but `main()` does not return/raise a non-zero process status when the verdict is `REVIEW_REQUIRED`. Therefore an automation that relies only on process exit status can still treat a review-required diagnostic as success.

This is the same defect class already recorded as **R20** (diagnostic/quality tools emitting failure-like status while exiting zero). It is recorded as an additional R20 surface, not a new finding number.

The corresponding `test_feasible_target_return.py` verifies verdict content but does not assert process exit semantics.

## Review result

```text
new R-number findings             : 0
existing finding extended         : R20 -> inspect_feasible_target_return.py
production source changes         : NONE
runtime tests executed this batch : NONE
physical/WSL/Unity/G1 runtime     : NOT RUN
```

The listed files may be promoted to `full_text_review`. Existing R20 remains open until process exit semantics are remediated separately.
