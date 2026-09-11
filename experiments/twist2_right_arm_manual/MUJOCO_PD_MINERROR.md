# Strict minimum-error PD search (offline only)

Run `mujoco_pd_minerror.py` in the isolated MuJoCo 3.3.7 environment.
This is an additive experiment: unchanged PD engine, reference, XML and inner
limit monitor; no live launcher, SDK, DDS or gain deployment.

## Objective and frozen plan

User priority: minimum tracking error subject to stable, limit-safe simulated
behavior. Existing quality thresholds remain unchanged. Unlike the earlier
2% accuracy plateau, this study strictly orders candidates by worst ORIGINAL
joint22-reference RMSE after every known condition passes; tail motion only
breaks exact RMSE ties. This is not a guarantee of physical stability.

482 unique pairs: Kp16..100 by4 x Kd0.1/0.25/0.5/0.75/1/1.2/1.3/1.5/2/3/5/7/10/15/20;
Kp96/98/99/99.5/100 x Kd1.200..1.350 by0.005; mandatory reference/control pairs.
The original Kp100 ceiling is NOT changed. Group gains22..25 and the inherited
joint22 +/-8degree three-cycle motion are unchanged.

45 previously used conditions are now KNOWN calibration, not new independent
evidence. Every new run starts from the original identical initial state.
16 new conditions (12 reproducibly generated motor/friction combinations and
4 model conditions) are frozen before any dynamics is run. Motor delay+lag is
7..11ms in these hypothetical torque-path checks; not measured G1 latency.
The 20260911 seed freezes the parameter list, not a stochastic motor model.

## Exact lower-bound pruning

1. Rerun100/1.3,100/1.4,100/2 over all45 to establish real feasible bounds.
2. For each grid cell, run prescribed conditions in the same order. A failed
   required condition excludes that cell. A partial maximum RMSE is a lower
   bound on the full maximum; if it strictly exceeds an already fully tested
   feasible score (plus1e-12), remaining conditions cannot make it the winner.
3. Store every early-pruning witness and the fully evaluated incumbent used.
   This is not an assertion that the pruned cell is unstable or fully tested.
4. Force full comparisons for100/1.25,1.275,1.325,1.35,1.5 as well as seed controls,
   unless an unchanged stability/guard requirement fails.
5. Freeze the best8 fully evaluated feasible cells plus seed controls, then
   evaluate the16 new conditions. Preserve calibration ordering among survivors;
   never retune on those validation outcomes or silently change quality limits.

All482 cells receive a sufficient calibration decision (full evaluation,
constraint failure, or bound proof). The number of actual simulations is
reported separately; do not claim482x45 runs if pruning skipped them.
The numerical certificate is for THIS discrete grid and known scenario set.
It is not a continuous-gain/global physical optimum, and validation is only
performed for the frozen shortlist, not every grid cell.

## Commands

From repository root, with `.venv-mujoco-pd` created per MUJOCO_PD_SWEEP.md:

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_minerror.py --workers 8 --output logs/test_results/mujoco_pd/minerror_new
```

Small plumbing/algorithm check (3pairs x1known and1new condition; not full study):

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_minerror.py --smoke --workers 3 --output logs/test_results/mujoco_pd/minerror_smoke_new
```

Recheck stored results without simulation:

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_minerror.py --audit-only --output logs/test_results/mujoco_pd/minerror_new
```

New output folders only; no overwrite/resume into partly completed folders.
An infrastructure error aborts rather than fabricating a failure or optimum.
Normal runs call the auditor with actual checkout bytes for source/mesh hashes.
`--audit-only` is portable and checks artifacts without requiring identical
source line-ending bytes. It regenerates pruning witnesses, scores, frozen
selection, full29 500Hz states, sampled margins and endpoint performance.
Physical-rate limit extrema are retained; complete continuous trajectories
between samples are not mathematically certified. Failed simulations are NOT
physical stopping/hold maneuvers.

## Preserved limitations

Fixed pelvis, small joint22 excitation, grouped proximal gains, hypothetical
friction/motor/model variation, no identified real sensor noise, backlash,
temperature, larger motions, IK cost optimization or free-base balance. Do not
change working VR setup or deploy a gain automatically. Robot/All stay blocked
while charging. Append actual counts, failures, evidence, commit and next
permitted offline work to docs/G1_REGULAR_HANDOFF_20260910.md.
