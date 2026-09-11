# G1 PD screening: all-joint inner-limit envelope

Base: `78f50f5d5232bbb67418e0557ae8992e686ceb69`.
User requirement: do not let the joint trajectory reach soft or hard limits.
Scope: offline simulation and candidate acceptance, NOT deployed VR/G1 control.

## Policy implemented

The soft interval is the intersection of the existing C++ soft interval and the
XML joint-limit activation interval (`range` adjusted by `jnt_margin`). Every
reference and command must remain STRICTLY inside an additional **0.05 rad**
reserve on both sides. Equality at a boundary is rejected. All29 model joints
must have enabled limits, finite ordered intervals, and a nonempty inner range.
The underlying XML limits, solver parameters, model damping and real robot
limits are not relaxed. `hard_lower/upper` refer to XML ranges, not measured
physical G1 hard stops.

Before integrating, analytic extrema certify the inherited monotone-segment
+8/-8-degree reference, including both signs. The regular writer's result is
checked AFTER its torque-based target limiter so that limiter cannot bypass
the envelope. A kinematic command governor computes the allowed incremental
motion; needing ANY target alteration refuses the PD trial instead of silently
ranking a clipped/slowed replacement trajectory. Unmodified valid-region
PD arithmetic and the original reference remain unchanged.

Measured q/dq of ALL29 joints are checked before AND after each mj_step, during
warmup, at trial start and at the final integrated step. The final-step gap in
the old pre-step-only check is closed. An active MuJoCo joint-limit constraint
also refuses the trial. Invalid state, nonfinite time and exhausted margins
cannot produce an accepted result. No measured qpos/qvel is projected, and a
failed monitor stays latched until a separate new candidate instance is made.

## Stopping-envelope assumptions, not physical guarantees

For each boundary, v is speed toward that boundary (negative values become0).
The required distance BEFORE entering the reserved corridor is:

    v*T + 0.5*a_out*T² + (v + a_out*T)²/(2*a_brake)

Defaults: T=0.02s, a_out=2rad/s², a_brake=1rad/s², in addition to 0.05rad reserve.
These are explicit conservative screening assumptions, not measurements of
G1 braking authority or worst-case actual latency. Model errors, loss of
support, external forces, asynchronous owners and unbounded delays are not
covered. A stopped SIMULATION is not a physically stopped real robot.
There is no claim of an absolute real-world invariant, servo certification,
zero continuum-time penetration, or a validated recovery/hold maneuver.
No governor or safety-state transition is deployed into the real VR writer.

MuJoCo itself describes compliant limit constraints and configurable activation
margins; this screen does not rely on the solver acting like an infinitely hard
wall. Primary references checked during this work:
- https://mujoco.readthedocs.io/en/3.3.7/XMLreference.html#body-joint
- https://mujoco.readthedocs.io/en/3.3.3/modeling.html#impedance

## Verification design

New tests cover every lower/upper boundary of all29 joints, strict equality,
directional stopping budget, invalid arrays, latched refusal, exact extrema,
random command-governor steps, command alteration exclusion, inactive model
limits, and limit activation margins. Deliberate state-injection tests ensure
that an ankle violation and a violation on the VERY LAST physics step cannot
be labeled complete. Those injected failures are tests, not successful robot
motions. Replay-evidence tests reject missing joints, missing final coverage,
false eligibility and modified minimum-clearance witnesses.

The fixed historical CSV defines 718 specific tests; no new adaptive grid is
substituted and old eligibility is NOT reused as new evidence. All selected
cases are actually rerun with the default guard. Per-case compressed joint22
traces and all29 monitor minima/witnesses/events are preserved, including
failures. The companion audit independently reloads joint22 traces and checks
hashes, clocks, metrics and cycle coverage. It validates all29 minimum-margin
witnesses and coverage counters, but cannot reconstruct the entire all29
trajectory from the compact joint22-only trace; that limitation is explicit.

## Preservation

No changes to `START_TWIST2_MINK_CYCLE_CANDIDATE.ps1`, the G1 controller,
UDP/Mink targets, actual PD gains, source XML/meshes or C++ trajectory. Normal
VR and gain-search cost weights are not changed. The original dirty PC worktree
was not reset, cleaned or overwritten; work occurs in a detached worktree.
Robot/All launch blocks, charging restriction and no-DDS constraint remain.

The earlier 718-run study was already committed as78f50f5; this is a new screen,
not a retroactive assertion that the old joint22-only logs proved all29 margins.

## Reproduction

Use the isolated MuJoCo3.3.7 environment from MUJOCO_PD_SWEEP.md:

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_limit_replay.py --workers 6 --output logs/test_results/mujoco_pd/limit_replay_new
```

All output directories must be new. `--cases N` is an explicit prefix subset
for smoke tests and must not be described as a full718 replay. Default is718.

## Actual local result

Windows Python3.11.9, MuJoCo3.3.7, NumPy2.4.6. **718/718 conditions rerun**; 678 completed/eligible, 40 excluded.

Rejection reasons: {"joint_stopping_envelope_exhausted": 6, "measured_velocity_limit": 6, "ready_pose_not_settled_in_final_warmup_second": 28}.

Six stopping-envelope refusals occurred before joint-limit contact; they were already ineligible in the historical screen for later failures. No previously eligible case became eligible by weakening a constraint.

Across accepted candidates, the minimum soft clearance was **0.211798601708536 rad (12.135166 deg)**, minimum XML-range clearance **0.261798601708536 rad**, and minimum stopping-distance slack **0.16059860169536 rad**.

Across ALL attempted trajectories up to refusal/completion, the smallest observed soft and XML-hard margins were 0.211798601708536 and 0.261798601708536 rad. No observed soft/hard touch or active model limit constraint occurred in this replay. These sampled observations are not an absolute physical guarantee.

Local regression result: **89 passed,1 skipped,0 failures/errors** of90. The skipped legacy C++ trajectory comparison requires a compiler absent on this Windows host. New hosted CI includes that test, but its outcome is not claimed in this commit.

Independent audit reloaded all718 compressed q22 traces, recomputed7458 metric values, validated all20,822 joint minimum-clearance witnesses and coverage counters, and checked the exact source/model/mesh bytes in the run manifest. The data itself remains q22 traces plus all29 extrema, NOT full all29 trajectory storage.

Compact evidence: `docs/validation/g1_pd_limits_20260911/`. Raw cases/traces/manifest and test output: `C:\Users\user\Documents\G1_PD_JointLimits_20260911`.

The new test workflow is additive. The original robot/VR files and launch blocks are unchanged. Next work remains offline; actual braking, full-body balance, real hard-stop locations, and live guard integration are NOT validated.


## 2026-09-11 — hosted all-joint verification completed

Tested code `8dbe3bc4304882b9bae3775c2bcc359a56193dd0`. Inspected Actions run **34584881165**,
job **103216672502** (`all-joint-limits`): **success**. The full decoded job
log reports **90/90 tests passed, no skips**, including the original C++
reference compilation/parity check skipped on the Windows host. Hosted
Ubuntu24.04.5, Python3.11.16, MuJoCo3.3.7, NumPy2.4.6. The tests ran in79.105s.

The earlier hosted-pending entry is historical. This append and hosted_ci.json
record the observed outcome; they do not change code, model parameters,
thresholds, the718-case result, VR/G1 configuration or deployment state.
The full718 replay was on the isolated Windows host, not rerun by this90-test
workflow. No physical guarantee, robot connection, DDS or motor output.

Evidence: `docs/validation/g1_pd_limits_20260911/hosted_ci.json`.
Next permitted work remains offline; actual braking/latency and hardware
owner integration must be validated before a physical guard is deployed.
