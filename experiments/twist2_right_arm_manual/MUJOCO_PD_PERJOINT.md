# Offline per-joint PD search

This is research-only. Do not pass these gains to START_TWIST2_MINK_CYCLE_CANDIDATE.
No SDK/DDS or robot connection is created. The working VR/UDP/LowCmd pipeline is unchanged.

## Why this differs from the earlier common-gain search

The prior operating study found static shoulder-roll error with Kp<=100.
This study changes only joint23's SIMULATION search ceiling to300; other proximal
Kp ceilings stay100 and all Kd bounds remain0.1..20. Live/C++ gain validators are
unchanged and still reject Kp>100. Joint, torque, velocity, command and stopping
limits are NOT raised. The research cap300 is not a verified motor capability.
No integral, gravity compensation, desired-velocity feedforward, or target bias
is added. Selected gains are vectors for joints22,23,24,25, not one common pair.

## Procedure

1. Evaluate40 joint23 Kp/Kd pairs on six roll cases each. Remaining axes start100/1.4.
2. Fix the roll winner and coordinate-search joints22,24,25 in that order using
   six candidate pairs on six cases each; retain current vector if needed.
3. Before full verification, freeze the coordinate vector, roll-only vector,
   higher-Kd comparison and original100/1.4 baseline. Duplicate vectors are run once.
4. Run EVERY selected vector across the inherited144 operating cases, including
   each proximal axis, changed amplitudes/speeds/start pose,12cycles and30s holds.
5. Freeze up to3 fully passing vectors before12 new model settings x4axes,
   including different amplitudes, speeds and five-second final holds.
6. Reload all full29 states and torque traces, recompute metrics, verify original
   references and limit witnesses, actual gain arrays, adaptive choices and hashes.

The objective is worst ORIGINAL-reference active-axis RMSE after all unchanged
performance/limit criteria pass. Coordinate search does NOT prove a global8D
optimum. The final study is finite-horizon and fixed-pelvis, without calibrated
sensor noise/backlash/temperature/free-base balance or real actuator capability.
Friction/mass/delay parameters are hypothetical. Integration step also changes
ideal PD evaluation rate; it is not an integrator-only convergence claim.

## Run

Use a separate Python environment with mujoco_pd_requirements.txt installed.
From repository root (output must not already exist):

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_perjoint_study.py --workers 8 --output C:\path\perjoint_results
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_perjoint_study.py --output C:\path\perjoint_results --audit-only
```

The original RUN_MUJOCO_PD_SWEEP.bat and its100Kp validation stay unchanged.
A successful study exit means execution/audit finished, not that a feasible
candidate necessarily exists; inspect selected_simulation_vector. None means
no candidate passed both operating verification and the new validation.

Raw results: manifest, phase plans, frozen selection, all-case JSON, full29 NPZ,
summary, all_cases.csv, all_joint_margins.csv, audit. Final audit checks source
bytes during the actual run; audit-only can verify retained data on another host.
The temporary Python gain adapter is supported only in isolated single-threaded
worker processes, never concurrently in threads or live control programs.
