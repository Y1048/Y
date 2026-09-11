# Offline PD operating-envelope study

This study is separate from VR/Mink/UDP/LowCmd and never deploys a gain.
The original trial and guarded engine remain unchanged. This new engine is
checked against the original on the identical joint22 default trajectory.

## Declared coverage

The full matrix is1728 attempts with12 unchanged bounded group-gain pairs.
Main1440:12pairs x4excited axes(22,23,24,25) x5profiles x6coupled scenarios.
Profiles:8deg standard,4deg/10deg/s,12deg/20deg/s,8deg/30deg/s,
and standard motion with the elbow baseline shifted+10deg.
Acceleration stays at60deg/s^2 or below; the original20deg/s trajectory remains
unchanged outside this experiment. Group gains affect22..25; only one joint
is excited per run. This does NOT identify independent gains for every joint.
Long288:12pairs x4axes x3profiles x2scenarios. The profiles are12round trips
plus5s hold,3round trips plus30s hold,and6round trips from elbow-10deg plus5s hold.
All scenarios are explicit in source/plan.json; no unobserved cell counts as
executed. No pruning and no use of outcomes to edit thresholds or rescue failures.

Same position/torque limiter, zero target velocity/feedforward and all29
pre/post/final inner-limit checks. The operating engine additionally refuses
post-step velocity violations, including the final step. All29 q/dq/ref/cmd,
requested and actual torque are retained at500Hz. Contact observations and
limit witnesses are checked at the physics rate. Default1ms versus0.5ms
also changes ideal motor PD rate; this is not a fixed-motor-rate convergence test.

## Acceptance and ranking

Preserve existing performance limits on joint22 and ALSO apply the same
0.02rad endpoint error and0.1rad/s endpoint speed to the actually excited axis.
All right7 tail variation<=0.005rad and RMS speed<=0.05rad/s. All3xcycles
hold tails must be present. A long final hold also checks its ENTIRE last1s.
These are declared performance tolerances, not calibrated hardware margins.
Any physics-step contact, guard intervention, incomplete trial or excess torque
limiting excludes the candidate. No qpos projection or trajectory clipping to pass.
The strict objective is worst original-reference error of the excited joint,
but only after ALL cells pass. If no group-gain pair passes, report no winner;
do not silently rank partial/failing results as optimal or loosen the tolerances.

## Run and verify

Use the separate MuJoCo3.3.7 environment, not the live VR environment.

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_operating_study.py --workers 8 --output logs/test_results/mujoco_pd/operating_new
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_operating_study.py --audit-only --output logs/test_results/mujoco_pd/operating_new
```

Use--smoke for TWO specific default-reference cases, not the full1728 matrix.
Existing output directories are refused. Exit0 means the declared experiment
and artifact audit completed, NOT that every gain passed. Check summary.json.
The auditor regenerates the declared plan, analytic held references, scores,
quality decisions and rankings from retained traces and checks model mutation,
source/asset hashes and all29 minimum-clearance witnesses.

## Scope limitations

Fixed pelvis; not free-base standing/TWIST2 balance. Model mass/friction/lag/delay
are hypothetical, not measured G1 identification. Long repetitions are not a
heating model. No sensor noise, backlash, arbitrary Cartesian VR paths, collision
avoidance planner, actual actuator stop, hardware or continuous-time safety proof.
No live launcher, G1 SSH/DDS/SDK/motor output or ARM deployment is permitted here.
