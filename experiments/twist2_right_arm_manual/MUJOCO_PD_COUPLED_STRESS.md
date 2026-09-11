# Coupled model and actuator PD screening

This is an offline MuJoCo study. It never launches VR, a robot executable,
Unitree SDK, DDS or a transport. No candidate is automatically deployed.

## Scope

The previous study varied model and motor-path uncertainty in separate runs.
This one combines them in the same private fixed-pelvis model. The original
joint22 +/-8-degree three-cycle reference, group gains22..25, 50Hz reference,
500Hz writer, core dynamics and all29 limit/endpoint acceptance rules stay unchanged.

Twelve pairs are frozen:80/1,88/2,96/1.5,96/2,100/1.275,100/1.3,100/1.4,
100/1.5,100/1.75,100/2,100/2.5,100/3. Kp100 is still the existing ceiling.
Each sees all64 factorial combinations plus nominal, without pruning:

| Factor | Calibration levels |
| --- | --- |
| Right-arm mass and inertia scale together |0.75,1.25|
| Right-arm passive damping scale |0.5,1.5|
| Right-arm frictionloss scale |0,0.5|
| Added right-arm torque delay |0,2ms|
| First-order right-arm torque lag |0,6ms|
| Physics timestep |1ms,0.5ms|

780 calibration attempts are prescribed. The strict worst original-reference
RMSE orders pairs ONLY after every calibration trial passes both core guards
and endpoint performance. Freeze top6 plus controls100/1.275,100/2,80/1;
then check16 separately prespecified combined conditions(seed2026091104).
Failed controls are retained for comparison, not promoted. If none survive,
report that outcome without changing a guard or rescoring an incomplete trial.
No post-validation retuning is part of this protocol.

These factors are hypothetical sensitivities, NOT calibrated G1 uncertainty.
The torque delay is not a measured network delay; mass scaling is not an
identified payload. XML and model ranges are untouched. mj_setConst propagates
runtime mass/inertia changes as documented by MuJoCo's Simulation reference.
No new gravity compensation, velocity feedforward or desired trajectory is added.

## Reproduce from repository root

Use the existing isolated environment from MUJOCO_PD_SWEEP.md, MuJoCo3.3.7.
Choose a NEW output directory for every run; existing results are never overwritten.

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_coupled_stress.py --workers 6 --output logs/test_results/mujoco_pd/coupled_new
```

Append `--smoke` for four cases(two pairs, one condition per phase), NOT the
whole study. `--audit-only` with the existing output path reloads recorded
compact/full-state traces, recomputes metrics, checks all29 sampled limits and
physics-rate witnesses, coupled model mutation evidence, frozen plans/selection.
The full run also checks original source/model/mesh hashes. No GUI or BAT is invoked.

Files:manifest.json, calibration_plan.json, selection.json, validation_plan.json,
cases/*.json, traces/*.npz, full_state/*.npz, summary.json, audit.json and all_cases.csv.
All29 q/dq/reference/command sampled arrays are retained, including failures.
Reported all29 minima are observed model states, not continuous-time guarantees.

## Not covered

Continuous gain/parameter spaces, other joints' independent gains, other poses,
large/faster trajectories, sensing noise/backlash/thermal effects, actual braking,
free-base balance and physical hardware remain outside this fixed protocol.
No finite test count means all possible cases. Preserve the user's live tree,
real gains, IK damp/cost and charging-time Robot/All blocks.

## Complete the full matrix (all gains, no finalist-only gap)

After the first command has completed, run this separate completion command.
It preserves the first study and executes the missing validation cells even
for previously excluded/non-finalist gains. The full experiment therefore has
12pairs x81conditions =972 actual attempts; early refusal inside an attempt
is retained as a failure, not claimed as three completed cycles.

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_coupled_matrix.py --base-run logs/test_results/mujoco_pd/coupled_new --output logs/test_results/mujoco_pd/coupled_matrix_new --workers 6
```

The separate all81 ranking is a descriptive comparison after every prescribed
cell has been observed. It is not a new independent validation for tuning on
those same81 conditions. All possible continuous conditions are still NOT covered.
Use both retained result directories for future audit/reproduction; their hashes
are cross-checked. No previously failed gain or criterion is changed to pass.
