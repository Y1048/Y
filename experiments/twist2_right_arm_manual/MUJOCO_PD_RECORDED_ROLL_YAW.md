# Recorded-input yaw and shoulder-roll PD refinement

This is OFFLINE simulation research, not a hardware configuration or deployment.
Run from the repository root with the existing isolated MuJoCo Python environment.

## Fixed control and objective

Use the existing causal 20 ms previous-to-current command interpolation. Original
recorded 7-joint goals remain the scoring reference. Do not rescale, time-stretch,
clip the score reference, or infer robot acceptance from send_attempt records.
The current recording and hypothetical model scenarios are already observed data,
not a new independent holdout. Frozen-pelvis dynamics cannot validate balance.

Minimize worst original-goal all-seven-joint RMSE subject to every existing
settling, speed, torque, contact and all-29-joint guard criterion. No incomplete
trial gets an eligible error score. All declared cells of each phase are attempted.

## Search stages

1. Yaw: Kp 40,48,56,64,72,80 and Kd 0.6,0.8,1,1.2,1.4,1.6; 36 vectors,
   each tested on nominal/send, delay_boundary/send and delay_boundary/sample.
2. Hold the first all-pass yaw candidate fixed. Roll: Kp 250,275,300,325,350
   and Kd 3,4,5,6; 20 vectors, each on the same three conditions.
3. Freeze the deduplicated best two roll vectors and best two yaw vectors.
   Replay every vector under both clocks and all six existing model scenarios.
4. Every fully passing replay vector is rechecked on 14 declared synthetic cases:
   three synchronous/independent profiles plus four isolated axes, each under
   nominal and known delay-boundary dynamics. This is a subset of old coverage,
   not inheritance of hundreds of previous tests for newly changed vectors.

The selected vector is the lowest recorded-input minimax error among candidates
passing both phase 3 and phase 4. Synthetic and recorded RMSE are not mixed into
one score. A phase with no feasible candidate records none rather than inventing one.
The method is bounded coordinate search, not global eight-dimensional optimization.

## Simulation-only roll bound

Only this runner's process-local context temporarily permits joint23 Kp up to350.
The original simulator's300 bound is restored even on an exception. The original
live Kp100 parser, model ranges, torque/velocity limits, 0.05rad reserve and all
other controller files remain unchanged. Values above100 are NOT hardware-approved.
No G1 connection, DDS, SDK, publisher, live recording or deployment is performed.

## Run and audit

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B .\experiments\twist2_right_arm_manual\mujoco_pd_recorded_roll_yaw.py --recording C:\path\to\recording.jsonl --output C:\path\to\new-results --workers 6
.\.venv-mujoco-pd\Scripts\python.exe -B .\experiments\twist2_right_arm_manual\mujoco_pd_recorded_roll_yaw.py --output C:\path\to\new-results --audit-only
```

The recording must contain exactly one complete qualified episode beginning at
the unchanged ready pose. Existing output is refused, as are invalid worker counts.
At least4GB free space is required. The runner archives computation sources, model
assets, raw input, normalized target arrays, stage plans, every full29 trace and
failed-case evidence. `--smoke` checks routing only and never selects a candidate.

`summary.json` stores stage-specific rankings and the selected filtered-pipeline
candidate. `audit.json`, `all_cases.csv`, and `all_joint_margins.csv` are produced
by re-reading sources, plans, applied gains, original goals, torque/limiter/filter
equations, endpoint metrics, guard extrema and every stored trace. Exit0 means
processing and auditing finished, not that every simulated trial passed.
