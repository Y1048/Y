# Backend virtual-center and camera helper full-text review - 2026-09-04

Branch: `main`

This is a **review-only** batch. No controller, generated model, camera profile,
test expectation, hardware configuration or authorization was changed.

## 검토

The following remaining backend `static_only` files were read in full:

```text
backend/tests/test_mink_reachability_limit.py
backend/tests/test_mink_task_cost_contract.py
backend/tests/test_mink_virtual_center_trajectory.py
backend/tests/test_mujoco_control_math.py
backend/tests/test_mujoco_inspection_scene_visibility.py
backend/tests/test_startup_ready_pose_editor.py
backend/tests/test_virtual_center_kinematics_regression.py
backend/tests/test_virtual_center_orientation_policy.py
backend/tests/test_wrist_target_mapping_audit.py
backend/tools/audit_wrist_target_mapping.py
backend/tools/verify_camera_simulation.py
backend/tools/verify_unity_state_packets.ps1
backend/tools/verify_virtual_center_kinematics.py
```

The Python tools are offline MuJoCo/Mink, camera transport or recorded mapping
diagnostics. The PowerShell helper invokes pure methods from an already-built
Unity assembly. None is a physical G1 authorization or validation path.

### Existing R24 extends to remaining stale tests

`test_virtual_center_orientation_policy.py` still requires exactly `40/100
deg/s`, although the current controller constants are both
`math.degrees(0.08)`, approximately `4.58366 deg/s`.

`test_virtual_center_kinematics_regression.py` also checks only that measured
velocities remain below the obsolete `40/100 deg/s` values. The test can pass
without enforcing the current `0.08 rad/s` contract. Both are additional R24
surfaces, not new findings.

### Existing R53 extends to camera/model diagnostics

`verify_camera_simulation.py` calls
`g1.make_demo_xml("camera_validation", show_inspection_scene=True)` against the
repository's shared generated model path and does not restore the prior model
after the diagnostic. An interrupted
`test_mujoco_inspection_scene_visibility.py` run can leave the same shared file
in its temporary visible-scene state before its `finally` cleanup is reached.

This is the same shared mutable generated-model/provenance class recorded as
R53 for recovery experiments. The additional surfaces can affect a later local
MuJoCo run, but they do not create or modify files on the physical G1.

### Existing R27 boundary remains unchanged

The target-mapping audit validates recorded rotations before conversion, and
the tested quaternion conversion normalizes through the active controller
path. These callers do not close the generic SO(3) input-validation issue in
R27, and no duplicate finding is needed.

### Other conclusions

- The Mink task-cost regression correctly demonstrates that `cost` weights
  both Jacobian rows and feedback error, while `gain` scales feedback error.
- Reachability helpers keep a necessary chain-length bound distinct from a
  feasibility or collision permit.
- The Unity packet verifier is source/compiled-assembly validation only; it
  explicitly creates no socket and does not exercise Unity Play, Quest or DDS.
- Startup ready-pose editor tests use temporary paths and preserve unrelated
  JSON fields while validating configured joint ranges.
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

Executed locally with Python 3.11, selecting tests that do not regenerate the
shared repository MuJoCo XML:

```text
py -3.11 -m unittest \
  backend.tests.test_mink_reachability_limit \
  backend.tests.test_mink_task_cost_contract \
  backend.tests.test_mujoco_control_math \
  backend.tests.test_wrist_target_mapping_audit \
  backend.tests.test_virtual_center_orientation_policy.VirtualCenterOrientationPolicyTest.test_live_joint_speed_keeps_proximal_slow_and_wrist_fast
```

Result:

```text
15 tests run
14 passed
1 failed
```

The single failure is the R24 expectation: current proximal speed is
`4.583662361046586 deg/s`, not `40.0 deg/s`.

Tests and tools that call `make_demo_xml()` were not executed in this review
batch because they rewrite the shared generated XML that R53 identifies. No
WSL, DDS, Unity, Quest or G1 runtime was started.

## 남은 항목

1. The backend diagnostic/test helper queue is now fully read at the current
   scope; continue with `tools/*.bat` and launcher layers.
2. Keep R24 and R53 remediation separate from review bookkeeping.
3. Preserve R27 until generic SO(3) validation is remediated and tested.
4. Do not execute connected-G1, WSL/DDS or publisher paths without exact user
   authorization.

Review result:

```text
new R-number findings       : 0
existing finding extended  : R24, R53
existing boundary retained : R27
physical validation        : NOT AUTHORIZED / NOT RUN
```
