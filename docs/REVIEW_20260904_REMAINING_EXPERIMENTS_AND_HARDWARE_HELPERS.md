# Remaining experiments and hardware-helper full-text review - 2026-09-04

Branch: `main`

This is a **review-only** batch. No controller, experiment, authorization,
network setting or physical-output behavior was changed.

## 검토

The final 34 queued `static_only` files were read in full:

```text
experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat
experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat
experiments/startup_recovery_posture_sweep/run_sweep.py
experiments/startup_recovery_posture_sweep/single_pose_runner.py
experiments/startup_recovery_posture_sweep/test_sweep.py
experiments/twist2_right_arm_manual/TEST_OFFLINE.bat
experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp
hardware/g1_arm_bridge/g1_base_state.py
hardware/g1_arm_bridge/generate_fake_mink_targets.py
hardware/g1_arm_bridge/lowstate_health_guard.py
hardware/g1_arm_bridge/mink_target_dry_run.py
hardware/g1_arm_bridge/probe_joint_motion.py
hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py
hardware/g1_arm_bridge/test_arm_sdk_teleop_contract.py
hardware/g1_arm_bridge/test_experimental_stateful_gate7_controller.py
hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py
hardware/g1_arm_bridge/test_g1_base_state.py
hardware/g1_arm_bridge/test_g1_right_arm_jog.py
hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py
hardware/g1_arm_bridge/test_gate7_first_live_profile.py
hardware/g1_arm_bridge/test_gate7_live_dry_run.py
hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py
hardware/g1_arm_bridge/test_gate7_visible_motion_profile.py
hardware/g1_arm_bridge/test_hardware_state.py
hardware/g1_arm_bridge/test_lowstate_health_guard.py
hardware/g1_arm_bridge/test_mink_safety_pipeline.py
hardware/g1_arm_bridge/test_physical_precheck_provenance_entries.py
hardware/g1_arm_bridge/test_right_arm_jog_contract.py
hardware/g1_arm_bridge/test_safety_gate.py
hardware/g1_arm_bridge/test_validate_right_arm_jog_collision_path.py
hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py
hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py
hardware/g1_arm_bridge/verify_initial_pose_sync.py
tools/DETECT_G1_NETWORK_ADMIN.ps1
```

Ledger reconciliation also exposed five split-runtime files added after the
previous coverage snapshot. They were read in full in the same batch:

```text
MuJoCo_G1_Controller/scripts/g1_gate7_feedback.py
MuJoCo_G1_Controller/scripts/g1_mink_collision_policy.py
MuJoCo_G1_Controller/scripts/g1_mink_diagnostics.py
MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py
backend/tests/test_mink_runtime_refactor_compatibility.py
```

The split modules preserve the public aliases exported by
`run_mink_g1_right_arm_virtual_center_live.py`, the local 5/10 mm and guarded
20/40 mm collision profiles, the 0.5 mm local QP reserve, Gate 7 simulation
feedback filtering and the existing diagnostics schema. The compatibility test
checks these contracts directly. No behavior change or new finding was found in
this refactor review.

### Existing R20 and R54 remain confirmed

`mink_target_dry_run.py` can report process success after receiving only a
single synchronization packet without accepting a command. Its companion
source-contract test checks that an `accepted=` field is printed but does not
require a positive accepted count. The stronger fake-pipeline test requires an
`[ALLOW]` event, but it does not remove the weaker dry-run success boundary.

The posture sweep also returns success when its infrastructure completed even
if no sampled pose recovered. This is the existing R54 experiment surface of
R20, not a new independent finding.

### Existing R43-R45 and R49 remain confirmed

`twist2_right_arm_trial.cpp` is a command-capable experimental whole-body
`rt/lowcmd` owner. It initializes a LowState subscriber, a LowCmd publisher and
MotionSwitcher only after the operator confirmation phrase. The offline BAT
does not run this binary; it invokes `verify_offline.py` only.

Full-source review reconfirmed the previously recorded boundaries:

- R43: right-arm keyboard targets have joint/rate/ideal-torque limits but no
  Cartesian workspace, collision swept path, acceleration or jerk envelope.
- R44: command build, CRC, publisher write and statistics updates are outside
  the writer's local exception-to-damping block.
- R45: planned completion ends after damping output without proving a stable
  AI-standing/control-owner handback.
- R49: `validate_state()` checks the supplied state but calculates freshness
  from a second snapshot, so fields and receipt time are not one immutable
  sample.

No TWIST2 executable, compiler, WSL command, DDS entity or publisher was
started in this review.

### Existing R50 remains partially open

`lowstate_health_guard.py` and its tests cover finite IMU/motor fields,
roll/pitch, temperature, motor fault state and estimated torque. This confirms
the current supported-path mitigation. Remote/deadman and CRC/integrity remain
open pending verified read-only Unitree SDK field evidence; this review did not
invent those checks or claim physical acceptance.

### Existing R53 remains confirmed

`run_sweep.py`, `single_pose_runner.py` and `verify_initial_pose_sync.py` use
the shared generated MuJoCo XML preparation path. The sweep's resume mode can
also retain prior non-error results without rebinding them to current source,
model and configuration hashes. These are existing R53 model/evidence
provenance surfaces.

### Existing R56 remains confirmed

`DETECT_G1_NETWORK_ADMIN.ps1` invokes `pktmon` native commands without checking
each child exit code and artifact before writing its completion marker. This is
the existing R56 transactional network-capture finding.

### Additional review notes

- `probe_joint_motion.py` is read-only with respect to the robot but creates a
  LowState DDS subscriber and writes a local result artifact. It was inspected,
  not executed.
- `generate_fake_mink_targets.py` emits synthetic UDP state packets and imports
  no Unitree SDK. Supported physical ingress provenance is expected to reject
  this synthetic source.
- `validate_right_arm_jog_collision_path.py` returns a nonzero process code for
  a failed permit and writes a local atomic result. Its permit remains subject
  to the separately documented R40/R42 provenance and final-segment boundaries.
- `verify_arm_sdk_message_offline.py` imports message/CRC definitions only and
  creates no ChannelFactory or DDS entity. Its PASS is an SDK-message contract,
  not physical validation.
- `test_g1_right_arm_jog.py` contains two harmless unreachable expression lines
  after `unittest.main(...)`. They are cleanup debt only and do not justify a
  new finding number.

No new independent P1/P2/P3 finding was identified in this batch.

## 코드 수정

```text
Production source changes  : NONE
Authorization changes      : NONE
Controller changes         : NONE
Review artifacts only      : YES
```

## 테스트

Executed locally:

```text
py -3.11 -m compileall -q experiments/startup_recovery_posture_sweep hardware/g1_arm_bridge
py -3.11 -m pytest -q <18 reviewed unit/contract test files>
py -3.11 hardware/g1_arm_bridge/test_mink_safety_pipeline.py
py -3.11 hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py
py -3.11 backend/tools/reconcile_review_ledger.py
py -3.11 backend/tools/build_code_index.py
py -3.11 -m pytest -q backend/tests/test_code_index.py
```

Result:

```text
Python compile/import surface     : PASS
unit/contract tests               : PASS (108 tests, 18 subtests)
synthetic UDP safety pipeline     : PASS (239 accepted; stale-stop observed)
fake Mink UDP end-to-end          : PASS (239 accepted; stale-stop observed)
canonical review ledger           : 308/308 full_text_review, 0 static_only
static check failures             : 0
code-index administration tests   : PASS (3 tests)
```

The two process tests explicitly reported `Unitree SDK: NONE`, `DDS: NONE` and
`Robot cmd: NONE`. No G1, WSL, Unity, Quest, camera or administrator network
action was used. Command-capable helpers, `probe_joint_motion.py`, the TWIST2
binary, shared-XML writers and the administrator network script were not run.

## 남은 항목

1. Remediate R20/R24/R27/R32 separately from review bookkeeping.
2. Keep R43-R45/R49 experimental TWIST2 physical use blocked until their
   existing safety and ownership findings are addressed.
3. Keep R50 remote/deadman/CRC open until the actual read-only SDK fields are
   verified without creating a publisher.
4. Keep R53/R54 and the deferred Startup Recovery strategy-atlas experiment
   separate from the active recovery path.
5. Preserve all hardware authorization locks and require exact approval for any
   physical action.

Review result:

```text
full-text files completed   : 39
new R-number findings       : 0
existing findings confirmed: R20, R43-R45, R49, R50, R53, R54, R56
physical validation         : NOT AUTHORIZED / NOT RUN
```
