# Yaw candidate regression after simultaneous-axis refinement

This entry point validates the two frozen simultaneous-motion finalists against
216 previously used individual-axis conditions each. It does not search new gains,
change hardware settings, initialize DDS, or execute recorded source code.
The earlier profiles are known regression data, not independent new holdouts.

## Run from the repository root

Use the existing isolated `.venv-mujoco-pd` environment described in
`MUJOCO_PD_FINAL.md`. Do not install into or modify the working VR environment.

```powershell
$out = "$env:USERPROFILE\Documents\G1_PD_YawRegression_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_yaw_regression.py --source-yaw "$env:USERPROFILE\Documents\G1_PD_MultiaxisYaw_20260912" --output $out --workers 4
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_yaw_regression.py --source-yaw "$env:USERPROFILE\Documents\G1_PD_MultiaxisYaw_20260912" --output $out --audit-only
```

The source yaw study and its full-state evidence must be present and fully audited.
The script refuses overlapping source/output paths, existing output, changed source
or model bytes, missing cases and unsupported hardware claims. Workers must be 1..8.
Linux uses the same Python script and arguments with Linux filesystem paths.

## Protocol

The source finalists must each pass 144 simultaneous operating and 24 additional
conditions. Preserve their frozen operating-error preference order. Validate each
on 144 original operating, 48 previous validation and 24 previous final profiles.
Each proximal axis has 54 individual excitation cases; 2 vectors x 216 = 432 new
integrations. Do not inherit old different-gain passes. All four proximal joints,
including stationary joints, must satisfy the unchanged endpoint tolerances.

The unchanged multiaxis core uses a single nonzero motion scale to reproduce
individual-axis dynamics. The reference, pure-PD law, torque path, guards, reserve,
model ranges, timing and other gains remain unchanged. Tests compare full state
arrays with the previous individual-axis engine. Every scheduled case is run;
failed attempts stay recorded and cannot contribute a selectable complete score.

Outputs contain the frozen plan/inputs, source receipt, all 29-joint time series,
case JSON, summary, all-case CSV, joint margins and audit. `--audit-only` recomputes
saved evidence without new dynamics. An audit success means the records agree,
not that all candidates passed. `selected_simulation_vector` may be null.
Source audit may regenerate identical CSV/audit derivatives, never raw trajectories.

## Interpretation

Research-only Kp 300 on joint 23 still exceeds the unchanged live Kp 100 bound.
Do not copy these values to `START_TWIST2_MINK_CYCLE_CANDIDATE` or relax its checks.
No robot, SDK/DDS, real motor output, IK cost/damping or deployment is involved.
A vector passing all 216 regressions and 168 source simultaneous cases has finite
384-condition evidence only. It is not a global optimum, arbitrary VR validation,
free-base balance result, motor certification or physical no-limit-contact proof.
The previous final-review candidate is historical; it is not evidence for new gains.
