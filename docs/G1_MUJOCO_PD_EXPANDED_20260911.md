# G1 expanded offline PD screening — 2026-09-11

Base: `b61def51ae57cac7a31daf9d169abece6a5cd615`. Simulation only. No hardware gains applied or recommended.

## Measured result

56/3 was the best of the historical nine-pair grid, not an established optimum.
This study attempted **718 simulations**:448 expanded/model runs and270
motor/friction runs. **678 completed and were eligible;40 were excluded**.
Do not call excluded attempts completed three-cycle experiments.
There were192 coarse gain pairs,56 additional fine pairs and200 selected
model/timestep cases. The motor study used15 pairs in18 named conditions.
Repeated nominal runs are not additional distinct gain pairs.

| Kp | Kd | Nominal joint22 reference RMSE (rad) | Motor/friction eligible |
| --- | --- | --- | --- |
| 40 | 5 | 0.025205712095 | 17/18 |
| 56 | 3 | 0.0146498091822 | 18/18 |
| 80 | 1 | 0.00806885259964 | 18/18 |
| 100 | 0.1 | 0.00592090905397 | 9/18 |
| 100 | 0.5 | 0.00620669186415 | 15/18 |
| 100 | 1 | 0.00659562531046 | 18/18 |
| 100 | 2 | 0.00755652846809 | 18/18 |
| 100 | 3 | 0.00870164527891 | 18/18 |

The nominal lowest-RMSE pair was100/0.1, but it passed only9/18 motor/friction
conditions. Among the15 motor-study pairs,100/1 passed18/18 and minimized
worst-case RMSE among fully eligible pairs: `0.006616652673669812` rad.
100/2 and80/1 also passed18/18. These are simulation-screening candidates,
not physical G1 recommendations. Kp100 is the existing allowed search ceiling;
a boundary winner does not establish local or global optimality.

## Protocol

The original simulation engine, C++ reference and writer math were unchanged.
A fixed-pelvis model tracks joint22 ready -> +8 degrees -> -8 degrees -> ready,
three cycles, with grouped Kp/Kd on joints22..25. Other joint references remain
unchanged. Every candidate starts from reset and an independent3-second warmup.
Completed trials record7633 samples at500Hz. Target velocity/feedforward torque
remain zero. This does not independently identify all arm joints.

Coarse Kp:16,24,32,40,48,56,64,72,80,88,96,100.
Coarse Kd:0.1,0.25,0.5,0.75,1,1.25,1.5,2,2.5,3,4,5,7,10,15,20.
The committed script and saved plans define deterministic fine-grid selection.

Model perturbations use right-arm mass/inertia factors0.75/1.25, passive damping
factors0.5/2, added frictionloss0.1/0.25Nm, combined cases and0.5ms timestep.
These are hypothetical sensitivity assumptions, not measured uncertainty bounds
or an added end-effector payload. The second study reduces friction to0/0.25/0.5
and inserts1–8ms pure torque delay or2–10ms first-order torque lag, including
combined cases. Delay is applied to simulated torque, not a reconstruction of
measured UDP commands or measured motor electronics. Changing timestep also
changes ideal PD evaluation frequency: not pure integrator convergence.

## damp and cost: inspected local active path

The current PC launcher selects `--ik-solver vanilla --upstream-mink-collision`.
Its uncommitted local code was inspected without execution or modification;
it is not identical to the committed baseline. The selected route is
StandardMinkPlanner -> UpstreamMinkTracking. StandardMinkPlanner uses base
position cost8, orientation cost2, posture cost0.04, proximal joint-motion
DampingTask cost0.25, wrist cost0.015 and LM damping1e-5.
UpstreamMinkTracking calls build_ik with damping1e-6, not base QP_DAMPING1e-8.
Hierarchical cost values0.03/0.50/proximal maximum100 belong to another objective
path; they must not be mistaken for active vanilla weights or motor Kd.

These718 PD runs bypass Mink completely. They cannot optimize IK damp/cost.
No IK settings were changed. Keep IK fixed during motor PD comparison, then
use a separate identical recorded-input A/B replay for IK weights. Evaluate
Cartesian position/orientation error, command velocity/acceleration, tracking
lag, constraints and collision rejections rather than changing every parameter
at once. XML passive damping is also distinct from motor Kd and IK cost.

## Actual validation and limitations

Windows, Python3.11.9, MuJoCo3.3.7, NumPy2.4.6, isolated environment.
Tests: **60 passed,1 skipped,0 failures,
0 errors**, 61 discovered. Original C++ compilation
parity was skipped because this Windows host has no compiler; historical Linux
parity is not presented as a new pass.

All718 saved traces were reloaded and hash/finite-array/time/gain/cycle/metric/
eligibility checked. All15 common nominal joint22 response arrays matched
exactly between studies. Source/model/mesh exact checkout bytes were checked
against the original raw manifests. NPZ retains joint22 at500Hz; right-arm
other-joint metrics are scalar JSON observations. Physics-rate contact counters
and other-joint aggregates are not independently reconstructed from those
joint22-only traces. No continuous-time or physical safety proof is claimed.

New tests cover grid bounds, failed-run retention, callback restoration, exact
zero-delay parity, FIFO delay, first-order lag, reset, socket refusal and
artifact tampering. The pre-existing test change only accepts native Windows
path separators in the manifest key; production engine semantics are unchanged.
Workers reject Python socket audit events after local OS metadata is cached.
Initial setup failure and the prior Windows assertion failure remain history.

No G1 connection, DDS/SDK, motor output, robot build, GUI/BAT run, deployment,
free-base balance or physical handoff was performed. The user working source
was not reset, cleaned or overwritten. Robot/All physical blocks remain intact.

## Reproduce and evidence

Use the separate MuJoCo3.3.7 environment in MUJOCO_PD_SWEEP.md. Repository root:

```powershell
python -B experiments/twist2_right_arm_manual/mujoco_pd_expand.py --workers 6 --output results/expanded
python -B experiments/twist2_right_arm_manual/mujoco_pd_motor_stress.py --workers 6 --output results/motor
python -B experiments/twist2_right_arm_manual/mujoco_pd_expand_audit.py results/expanded results/motor --output results/audit
```

Every output directory must be new. Optional audit `--source-root` requires the
original checkout bytes; a differently newline-normalized checkout is not
silently treated as byte-identical.

Compact evidence: `docs/validation/g1_pd_expanded_20260911/` contains all718
case rows, study summaries, complete hash inventory/audit and test counts.
CSV SHA-256: `aa7bd03f4c85c27939df9aa0d4e1a4d699599e01881a8218512e5c03f4d364a1`.
All original traces/cases/manifests are retained on the user PC at `C:\Users\user\Documents\G1_PD_Expanded_20260911`.
Temporary runs, including earlier failed setup evidence, were not erased.

Next permitted work remains offline. No automatic gain deployment or physical
trial approval follows from these tests. Noise, backlash, temperature, measured
motors, live VR timing and standing balance remain unvalidated.
