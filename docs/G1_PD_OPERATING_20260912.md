# G1 wider PD operating-envelope verification —2026-09-12

Base `4b9dde3d0c11e54672e71243ed0092ebae70b017`. Tested implementation `df0620d800bf37b57dc414b2a85f7848fd7035c7`. Offline only.

## Main result

**NONE of the12 tested common group-gain pairs passes every operating cell. No common PD optimum or hardware gain is promoted.**

**1728 actual attempts**, with no pruned or missing cells. Completed:1636;
quality eligible:1226; rejected:502.
Main1440 plus long-profile288; every pair sees the same144 operating cells.
New per-axis endpoint checks expose limitations the former joint22-only
objective did not evaluate. Earlier single-axis results are preserved as
historical, scoped evidence, NOT relabeled as a four-axis success.

Base/integration refusal counts:`{"ready_pose_not_settled_in_final_warmup_second": 92}`.
All exclusion labels:`{"active_tail_error_rad": 410, "post_hold_last_second_not_settled": 64, "ready_pose_not_settled_in_final_warmup_second": 92}`.
Labels may overlap within a rejected case; do not sum them as distinct trials.
Guard events:`{}`.
Actual simulated time accumulated across attempts:39203.588s
(10.8899simulated hours), not physical operating hours.

## Declared coverage

Main:12bounded group-gain pairs x4independently excited axes22..25 x5profiles x6
coupled model/motor settings. Profiles cover amplitudes4/8/12deg; speed caps10/20/30deg/s;
acceleration caps<=60deg/s^2; and elbow baseline+10deg. These are explicit new
OFFLINE reference profiles, not changes to the C++/VR trial.
Long:12pairs x4axes x3profiles x2coupled settings. Twelve round trips+5s hold,
three round trips+30s hold, and six trips from elbow-10deg+5s hold. Long time
is not a motor heating or indefinite stability model.

All declared cells were executed, even after a given gain failed elsewhere.
The failed-setting list and every exact profile/scenario are retained. This is
a complete finite verification matrix, not all possible gains or operating states,
and not independent real-robot model calibration.

## Identical group gains, different excited axes

The gain pair is applied together to22..25 while ONE named axis is excited per
run. This is NOT an independently optimized gain set for all four joints.
The other joint gains stay unchanged. Passes require all guard AND performance
conditions; an early refusal is not a completed three-cycle trajectory.

| Group Kp/Kd | Joint22 passes | Joint23 passes | Joint24 passes | Joint25 passes | All144 pass |
| --- | --- | --- | --- | --- | --- |
|80/1|27/36|0/36|28/36|28/36|False|
|88/2|36/36|0/36|36/36|36/36|False|
|96/1.5|36/36|0/36|36/36|36/36|False|
|96/2|36/36|0/36|36/36|36/36|False|
|100/1.275|28/36|0/36|28/36|28/36|False|
|100/1.3|29/36|0/36|29/36|29/36|False|
|100/1.4|36/36|0/36|36/36|36/36|False|
|100/1.5|36/36|0/36|36/36|36/36|False|
|100/1.75|36/36|0/36|36/36|36/36|False|
|100/2|36/36|0/36|36/36|36/36|False|
|100/2.5|36/36|0/36|36/36|36/36|False|
|100/3|36/36|0/36|36/36|36/36|False|

Per-axis coverage/exclusion details are in axis_coverage.json. A rejected pair
has no selectable full-matrix RMSE. Partial errors in summary.json are descriptive
only; choosing the smallest partial score would hide missing/failed conditions.

## What the nominal roll diagnostic means

nominal_roll_diagnostics.json contains saved endpoint error, residual motion and
requested/actual torque at100/1.4, including a30s final hold. A separate static
mj_forward query evaluates model gravity at the observed pose with zero velocity;
it neither integrates nor modifies any recorded trajectory or control setting.
No diagnosis of actual G1 friction or motor loads is claimed.

The controller remains tau=Kp*(q_cmd-q)-Kd*dq, with zero target velocity and
zero feedforward. A quiet but biased endpoint is a tracking failure, not proof
of oscillatory instability. Such bias is consistent with load being supported
through position error in this model; it is NOT proof that changing IK cost or
Kd alone will remove it. Do not confuse pure-PD model behavior with identified
hardware behavior or automatically add compensation to the live robot.

## Guards and numerical comparison

All29 original inner-limit, stopping and reference/command checks remain.
The new engine additionally rejects post-step upper/leg velocity violations,
including the final step. Source XML/mesh/actuator limits are unchanged. Only
fresh private model mass/inertia/damping/friction instances are varied.
Model changes use mj_setConst as documented for MuJoCo3.3.7.
No qpos projection or clipped substitute reference is accepted to improve error.

The existing endpoint tolerances remain0.02rad error and0.1rad/s speed for
joint22, and the SAME tolerances now also cover the actually excited axis.
All right7 tail peak-to-peak<=0.005rad and RMS speed<=0.05rad/s. Every hold's
last100ms is checked, plus the ENTIRE last1s of extended post-hold. No threshold
was relaxed after seeing failures. Gravity compensation was not added.

Observed all29 minimum soft margin:0.211798601205472rad;
model hard-range margin:0.261798601205472rad.
These are sampled/model results, not measured real hard stops or absolute
physical no-contact guarantees. True pre/post/final physics states were monitored;
full continuous-time trajectories are not mathematically reconstructed.
The1ms/0.5ms cases also change ideal motor PD update rate, not just integration.

## Actual verification

36 new tests initially passed. Full local Windows allowlist229 discovered:
228passed,1legacy C++ compiler-dependent skip,0failures/errors.
An earlier local suite wrapper failed in Windows process spawning because the
untracked wrapper lacked a main-entry import guard. The failed wrapper, log and
counts are retained. The corrected wrapper reran the FULL unchanged suite; no
frozen simulation or repository test code was modified. See local_runner_failure.json.
Inspected hosted run34616834178, job103320746401 on `df0620d800bf37b57dc414b2a85f7848fd7035c7`:
229/229passed,zero skipped, including C++ parity. CI ran tests and smoke/parity
trials, not this full1728-cell study. The full matrix ran in an isolated Windows
worktree with Python3.11.9,MuJoCo3.3.7,NumPy2.4.6 and8workers.
Default generalized reference matches the original at10000reference times.
Actual all29 q/dq/ref/cmd arrays match the inherited engine exactly on nominal
and a perturbed coupled comparison. No equivalence is claimed for newly changed
operating references. Boundaries, final-state violations, missing holds and
score/reference/model/trace tampering are covered by regression tests.

The final audit reloaded all1728 retained full-state traces,
19602672 rows containing29joint states at500Hz, and
50112 minimum-clearance/witness records. It recomputed
held50Hz references, dynamic scores, endpoint quality, all29 sampled limits,
model mutations, complete matrix membership and final rankings from evidence.
Source/model/mesh identities matched. Full physics-rate trajectories are not
independently reconstructed; hardware stability is not validated.

## Records, preserved working path and next scope

Compact evidence:docs/validation/g1_pd_operating_20260912/.
all_cases.csv SHA256:`be3be27dd01bbe069f022be9679491692829b66d62824ca0f329d2a1a950258a`.
Raw traces and records copied/hash-compared to`C:\Users\user\Documents\G1_PD_Operating_20260912`.
Retained raw bytes:15466746376; files verified:3463.
Usage:experiments/twist2_right_arm_manual/MUJOCO_PD_OPERATING.md.

Original dirty user tree, VR/Mink/UDP/LowCmd code, actual gains, IK damp/cost,
XML/mesh limits and Robot/All charging blocks remain unchanged. No G1 SSH,
DDS/SDK/publisher/subscriber, motor output, GUI/BAT or ARM deployment.
The next issue is scoped per-joint tracking and model/load diagnosis, not another
unqualified declaration of a universal100/x optimum. No independent four-axis
gain identification, sensor-noise/backlash/heating, arbitrary VR path, payload
shape, free-base balance or physical braking proof is supplied by this study.
