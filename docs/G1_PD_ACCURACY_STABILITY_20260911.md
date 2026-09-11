# G1 PD accuracy and endpoint stability — 2026-09-11

## Scope and measured outcome

Base `41b25f87a7bbf959c658d1c023f74ebe260d3f23`; implementation tested `f4078fdd3309019a888d47c05197cc05fe118029`. Offline only.
First survivor in the frozen calibration preference is **100/1.3**. It passes35/35 known and10/10 new conditions. Worst calibration RMSE=0.00932800765182386rad, worst new-condition RMSE=0.00922649250092812rad. This is a finite-grid, finite-horizon simulation candidate, not deployed hardware gains or a proven optimum.

**490 actual runs**:420 calibration (12pairs x35 known conditions)
and70 fresh-condition validation (7 frozen pairs x10).
Completed=487; existing guard eligible=487;
new endpoint-quality eligible=482.
Do not confuse added performance rejection with a physical limit violation.
Base refusals: `{"ready_pose_not_settled_in_final_warmup_second": 3}`.
Quality refusals among base-eligible cases: `{"max_q22_tail_error_rad": 5}`.
Guard events: `{}`.

## Optimization rule, fixed before this experiment

The prior27 calibration and8 holdout conditions are now35 KNOWN conditions.
They were reused to narrow gains and are NOT fresh independent validation.
Kp100 with Kd1.1/1.2/1.3/1.4/1.5/1.6/1.8/2,96/1.3,96/1.6,80/1,56/3.
No increase of the existing Kp100 ceiling. Source gains remain unchanged.

All original guards/completion criteria apply. Additionally all9 endpoint holds
must have50 final samples (100ms at500Hz):q22 error<=0.02rad and speed<=0.1rad/s;
every right-arm joint tail p2p<=0.005rad and RMS speed<=0.05rad/s.
These are explicit performance tolerances, not calibrated physical safety bounds.
They are fixed in source and run manifest, and were not changed after results.
Historical baseline logs were inspected before this run to understand metrics;
that inspection is not new simulation evidence or a claim of blind thresholds.

Among candidates passing EVERY known condition, minimize worst ORIGINAL-reference
RMSE. Within2% of that minimum, prefer smaller worst right7 tail RMS speed,
then smaller position variation. Thus the chosen preference can trade up to2%
calibration error for less endpoint motion. The least-error candidate and most
stable candidate need not coincide. Minimum-RMSE calibration pair:[100.0, 1.1].
Calibration preference:[[100.0, 1.2], [100.0, 1.1], [100.0, 1.3], [100.0, 1.4], [100.0, 1.5], [100.0, 1.6], [96.0, 1.3], [100.0, 1.8], [96.0, 1.6], [100.0, 2.0], [80.0, 1.0]].
Calibration Pareto set (RMSE,tail RMS speed,peak q22 torque):[[100.0, 1.1], [100.0, 1.2], [100.0, 1.3], [100.0, 1.4], [100.0, 1.5], [100.0, 1.6], [96.0, 1.3], [100.0, 1.8], [96.0, 1.6], [100.0, 2.0], [80.0, 1.0]].

Freeze first4 preferred candidates plus100/2,80/1,56/3 before the new10 conditions.
Selection contains exact calibration-case hashes. Never retune on validation;
keep calibration order among validation survivors. Final frozen-order survivors:
`[[100.0, 1.3], [100.0, 1.4], [100.0, 2.0]]`. An unselected candidate is NOT a validation failure or success.

## All candidate results

The known/new pass columns show BASE passes/QUALITY passes/number of conditions.
'Not selectable' means at least one required condition failed, not a numeric
penalty fabricated for missing/early-stopped data.

| Kp/Kd | Known base/quality passes | Worst known RMSE rad | Worst right7 tail RMS speed rad/s | New base/quality passes | Worst new RMSE rad |
| --- | --- | --- | --- | --- | --- |
|100/1.1|35/35/35|0.00914270018066|0.00805209568973|9/9/10|not selectable|
|100/1.2|35/35/35|0.00923438478558|0.00749421665643|9/9/10|not selectable|
|100/1.3|35/35/35|0.00932800765182|0.00694300535277|10/10/10|0.00922649250093|
|100/1.4|35/35/35|0.0094234839966|0.00641718955049|10/10/10|0.00931612682312|
|100/1.5|35/35/35|0.00952075164624|0.00590225774651|not selected|not tested|
|100/1.6|35/35/35|0.00961971576669|0.00540070546591|not selected|not tested|
|96/1.3|35/35/35|0.00967694942534|0.00649487688888|not selected|not tested|
|100/1.8|35/35/35|0.00982250937133|0.00445734533316|not selected|not tested|
|96/1.6|35/35/35|0.00998175152275|0.00503146256799|not selected|not tested|
|100/2|35/35/35|0.0100312489178|0.00362013865988|10/10/10|0.00988908000098|
|80/1|35/35/35|0.0110905901413|0.0100978677979|9/9/10|not selectable|
|56/3|35/32/35|not selectable|not selectable|10/8/10|not selectable|

## Surviving candidates: combined45-condition descriptive metrics

These combined metrics describe the results; they do not re-rank using held-out
outcomes. Units are rad,rad/s,Nm. Peak-to-peak variation includes slow drift as
well as oscillation; it is not an identified frequency-response stability margin.

```json
{
  "100/1.3": {
    "nominal_rmse_rad": 0.006859272623171351,
    "all45_worst_rmse_rad": 0.009328007651823863,
    "all45_worst_peak_error_rad": 0.01682094811634971,
    "all45_worst_right7_tail_rms_speed_rad_s": 0.00817281995412744,
    "all45_worst_right7_tail_p2p_rad": 0.0007362076626669101,
    "all45_max_joint22_torque_nm": 1.4050329184419754,
    "all45_min_right7_soft_margin_rad": 1.0735864057259215
  },
  "100/1.4": {
    "nominal_rmse_rad": 0.006952196673044818,
    "all45_worst_rmse_rad": 0.009423483996599449,
    "all45_worst_peak_error_rad": 0.017081530011169313,
    "all45_worst_right7_tail_rms_speed_rad_s": 0.007598983514253289,
    "all45_worst_right7_tail_p2p_rad": 0.0006928682583419721,
    "all45_max_joint22_torque_nm": 1.405575386247989,
    "all45_min_right7_soft_margin_rad": 1.0735879713721572
  },
  "100/2": {
    "nominal_rmse_rad": 0.007556528468090668,
    "all45_worst_rmse_rad": 0.010031248917777055,
    "all45_worst_peak_error_rad": 0.018695291846087203,
    "all45_worst_right7_tail_rms_speed_rad_s": 0.00448629124200852,
    "all45_worst_right7_tail_p2p_rad": 0.0004207291219702203,
    "all45_max_joint22_torque_nm": 1.4075034678360183,
    "all45_min_right7_soft_margin_rad": 1.0735975372035547
  }
}
```

## Limits and evidence

Original single joint22 +/-8degree three-cycle trajectory, grouped gains22..25,
50Hz reference,500Hz writer, fixed pelvis and all29 guard remain unchanged.
No qpos projection, trajectory clipping or raised model/real limit to obtain a pass.
Minimum observed all29 soft margin=0.211798601708536rad;
XML-hard margin=0.261798601708536rad.
These are sampled model observations, not physical hard-stop or absolute safety proof.

All29 q/dq/reference/command arrays were retained at500Hz for every case,
including base/quality failures. Physics-rate pre/post/final guard checks and
all29 extrema/witnesses were also retained. Audit reloaded 490 compact
and full-state trace pairs, 4452271 all29 sample rows,
and 14210 joint-extrema records. It recomputed endpoint
metrics, q22 RMSE/overshoot/settling/torque, sampled limits, final selection and
rankings; compact/full q22 arrays matched. Source/model/mesh raw hashes matched.
Full physics-rate trajectories and continuous-time safety are not reconstructed.

Local Windows:Python3.11.9,MuJoCo3.3.7,NumPy2.4.6.
135 tests discovered:134 passed,one C++ compilation parity skipped,no failures/errors.
Hosted run34593608750,job103244239811 on `f4078fdd3309019a888d47c05197cc05fe118029`:135 passed,zero skipped;
full decoded log inspected, including C++ parity. CI includes the four-case
smoke and tests, not this full 490-run experiment.

Retained raw files, full-state arrays and tests: `C:\Users\user\Documents\G1_PD_AccuracyStability_20260911`.
Copy hashes were compared. Compact evidence lives at
`docs/validation/g1_pd_accuracy_stability_20260911/`.
all_cases.csv SHA256:`9353be6aa9610620ddcb8a81d326b33de50c12f9c31626f1c4960457a7c3e88e`.
Actual raw Windows checkout hashes retain their original line endings.

## Reproduce and continue

See `experiments/twist2_right_arm_manual/MUJOCO_PD_ACCURACY_STABILITY.md`.
Use the separate MuJoCo3.3.7 environment. No live launcher is invoked.

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_accuracy_stability.py --workers 6 --output logs/test_results/mujoco_pd/accuracy_stability_new
```

Original VR/UDP/LowCmd/IK source, physical gains, model limits and dirty user PC
worktree were not overwritten. No real G1,DDS,SDK,motor output,GUI/BAT,ARM build
or deployment. Robot/All charging blocks remain. This finite-horizon protocol
does not identify noise/backlash/thermal effects, actual latency or braking,
free-base balance, large-motion VR accuracy or independent gains for other joints.
Next work is a separately specified offline operating/excitation study or reviewed
model calibration, not automatic hardware adoption or post-hoc rescue of failures.
