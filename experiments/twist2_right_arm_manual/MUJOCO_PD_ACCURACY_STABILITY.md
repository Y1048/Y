# MuJoCo PD accuracy and endpoint stability

Offline only. This does not change the VR launcher, LowCmd writer, IK costs,
source XML/meshes, physical gains, or the mandatory all29 joint-limit guard.

## Fixed protocol

The existing round trip remains joint22 ready -> +8deg -> -8deg -> ready,
three cycles; gains are grouped on22..25. Other joints are not independently
identified. Reference50Hz, writer500Hz, and original guarded dynamics remain.

Twelve candidate pairs: Kp100 with Kd1.1/1.2/1.3/1.4/1.5/1.6/1.8/2;
96/1.3,96/1.6,80/1,56/3. All pairs receive the same35 known conditions.
The prior eight holdouts are now explicitly calibration data, NOT independent
validation evidence. Ten NEW conditions are fixed in the manifest before
execution. No threshold, scenario or shortlist is tuned using their outcomes.

## Accept before optimizing

Every existing guard and completion requirement must pass. Additionally,
all nine endpoint holds must provide their final50 samples (100ms at500Hz):

- joint22 position error at every tail sample <=0.02rad;
- joint22 absolute measured tail speed <=0.1rad/s;
- each right-arm joint's tail peak-to-peak position <=0.005rad;
- each right-arm joint's tail RMS speed <=0.05rad/s.

These are transparent performance-screen thresholds, NOT physical robot safety
certification. They do not relax any prior limit. A constant but inaccurate
hold can fail the error condition while passing the vibration condition.
A rejected/shortened trial has no selectable optimization score.

Among all-condition passes, minimize WORST original-reference RMSE. Within
2% of that minimum, prefer lower worst right7 tail RMS speed, then lower tail
position variation. This explicitly trades at most2% calibration RMSE for
less residual motion; it does not assert that both objectives have one common
mathematical optimum. Report the Pareto front and the minimum-RMSE candidate
alongside the selected compromise.

Freeze the first4 candidates in this order plus controls100/2,80/1,56/3 before
running the10 fresh conditions. Preserve calibration preference order after
reporting separate validation pass/fail; never re-rank by validation error.
If none passes, promote no candidate and do not loosen the tests.

## Reproduce

Use the separate MuJoCo3.3.7 environment documented in MUJOCO_PD_SWEEP.md.
From repository root (new output directories only):

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_accuracy_stability.py --workers 6 --output logs/test_results/mujoco_pd/accuracy_stability_new
```

`--smoke` runs an explicit four-case subset; it is not the full experiment.
`--audit-only --output <existing-results>` reloads evidence without simulation.

Results include original compact q22 traces, full q/dq/reference/command arrays
for all29 joints at500Hz, case quality metrics, frozen plans/selection,
summary.json, audit.json, and all_cases.csv. The auditor reloads all29 traces,
compares q22 to the original engine trace, verifies sampled inner-limit margins,
and checks the physics-rate guard extrema/pre/post/final-state coverage.
It does NOT reconstruct every physics-rate state or prove continuous safety.

## Scope limits

Fixed pelvis, small single-joint excitation and hypothetical actuator/model
uncertainty are not evidence of free-base balance, payload changes, large VR
motions, noise robustness or physical motor performance. No gains are deployed.
Kp100 is still the existing search ceiling; local/global optimality is unproved.
Record actual run/test counts and all exclusions in the repository handoff.
