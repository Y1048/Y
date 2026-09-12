# Simultaneous-axis PD verification (offline only)

This is an additive validation of the two accepted per-joint research candidates,
not another hardware gain deployment or an assertion of a global optimum.
It leaves the original VR/UDP/LowCmd path, source model, limits and prior studies
unchanged. Joint 23 Kp 300 is outside the unchanged live Kp 100 limit.

## Declared comparison

Both vectors keep Kp22..25 = [100,300,100,100]. The Kd vectors are
[1.4,4,1.4,1.4] and [3,5,3,3]. They are frozen before the new runs.
All four proximal axes follow the same smooth time law with independent signs:
all 16 combinations of (-1,+1)^4. They move simultaneously, including opposite
axis directions. This is NOT recorded arbitrary VR input or phase-shifted motion.

Main: 2 vectors x16 sign patterns x2 profiles x4 model/motor settings =256 runs.
Profiles are 4 degrees at10 deg/s (30 deg/s^2), and8 degrees at20 deg/s
(60 deg/s^2), three round trips each. Settings: nominal, half timestep,
heavy/lagged, and the previous combined delay boundary. Exact factors are in code.
Long: 2 vectors x4 signed patterns x2 profiles x2 settings =32 more runs.
Profiles are12 degrees plus5-second hold, or12 repeats plus30-second hold
with elbow baseline shifted -5 degrees. Total288 attempts, no cell pruning.

Pure PD, zero desired velocity, zero feedforward, and inherited writer/torque
limits are unchanged. All29 joints have preflight, command, pre/post-step and
final-state limit/stopping checks. Each endpoint checks all4 proximal axes,
including stationary axes in component tests, plus right7 residual motion.
Each vector must pass EVERY planned condition before receiving a selectable
worst-axis/worst-condition original-reference RMSE. A low partial score cannot
rescue a failed candidate. No data-dependent gain or tolerance adjustment.

## Run in the separate environment

From the repository root after installing mujoco_pd_requirements.txt into the
existing separate .venv-mujoco-pd (never the working VR environment):

```powershell
$out = "$env:USERPROFILE\Documents\G1_PD_Multiaxis_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
.\.venv-mujoco-pd\Scripts\python.exe -B .\experiments\twist2_right_arm_manual\mujoco_pd_multiaxis_study.py --output $out --workers 6
.\.venv-mujoco-pd\Scripts\python.exe -B .\experiments\twist2_right_arm_manual\mujoco_pd_multiaxis_study.py --output $out --audit-only
```

Linux uses the same script with python3. --smoke runs exactly two component
cases, never a full validation or selected final candidate. Existing outputs
are refused. Workers1..8 use the existing socket-denial initialization.

Keep summary.json, audit.json, plan.json, manifest.json, all_cases.csv,
all_joint_margins.csv, cases/, full_state/ and frozen_source/. Every run retains
29-joint q/dq/reference/command/requested/actual torque arrays at500Hz, failures
included. Model and source input bytes are archived without executing archives.
Verification recomputes the per-axis scores, vector reference, PD equation,
limits and plan completeness. It requires the current computational source to
match the manifest. Full physics-rate guard observations are extrema/witnesses,
not independently reconstructed continuous trajectories.

## Interpretation boundary

Fixed pelvis, synchronized small motions, hypothetical model/torque-path
uncertainty. No free-base TWIST2 balance, actual VR stream, wrist tuning,
noise/backlash/heating, calibrated actuator bandwidth or physical braking.
A model limit is not a measured mechanical stop. A simulation refusal is not
an implemented physical emergency stop. No DDS, SDK, robot command or launch
unblocking is part of this entry point. All exports remain simulation-only.


## Focused yaw refinement after the matrix failure

`mujoco_pd_multiaxis_yaw.py` changes ONLY joint24 gains after all80 failed
original matrix runs exceeded the integrated yaw speed bound. These are now
known calibration failures, not independent validation. No other gain changes.

42pairs: Kp24=32,48,64,72,80,88,100; Kd24=0.4,0.7,1,1.4,2,3.
Each sees the same3screening conditions (126actual attempts). Freeze the two
lowest worst-error all-pass vectors before applying all144operating conditions
to each. Freeze operating survivors before24new prescribed simultaneous cases.
Final outcomes can reject but cannot retune or reorder the operating selection.
An empty selection is a valid result; no failed low-error candidate is promoted.

```powershell
$out = "$env:USERPROFILE\Documents\G1_PD_MultiaxisYaw_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
.\.venv-mujoco-pd\Scripts\python.exe -B .\experiments\twist2_right_arm_manual\mujoco_pd_multiaxis_yaw.py --output $out --workers 6
.\.venv-mujoco-pd\Scripts\python.exe -B .\experiments\twist2_right_arm_manual\mujoco_pd_multiaxis_yaw.py --output $out --audit-only
```

The initial matrix remains a separate immutable result. This search has its own
manifest, phase plans, frozen selections, full29traces and source/model archive.
Kp23=300 remains research-only; hardware limits and live settings stay unchanged.
