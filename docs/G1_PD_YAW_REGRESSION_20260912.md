# G1 yaw-candidate individual-axis regression — 2026-09-12

Base `649a052124b195b7c039124144759af0fb234757`; tested implementation `25095da9d3995dd37e569a3b03cb722fee061bae`.

## Scope and recovered work

This continuation first recovered the completed 288-case simultaneous matrix and 462-case yaw refinement. Those 750 attempts were NOT repeated or counted as new. Their raw evidence and earlier 331-test CI result are now recorded in `G1_PD_MULTIAXIS_20260912.md` and `docs/validation/g1_pd_multiaxis_20260912/`.

The former research vector [100,300,100,100]/[1.4,4,1.4,1.4] did not pass the simultaneous matrix: 104/144. Joint 24 exceeded the measured-speed criterion in the declared delayed-motor boundary model. The separate yaw search produced 72/1 and 64/1 candidates, each passing 144+24 simultaneous conditions. Independent-axis passes of the old gain vector were not transferred to these different gains.

## New verification

Actually executed 432 NEW integrations: two frozen vectors x 216 known individual-axis conditions. Completed 432; all-criteria eligible 432. Phase counts: {"prior_final": 48, "prior_fresh": 96, "prior_operating": 288}. No pruning, omitted cells or retuning.

All 216 profiles per candidate are reused regression data: 144 original operating, 48 formerly fresh and 24 formerly final. Each axis 22..25 has 54 excitation cases. Names fresh/final are historical labels, not new holdout claims. The source operating preference order was frozen before these runs; a failed candidate cannot be promoted for a smaller partial error.

The original single-axis profile is represented with exactly one nonzero scale in the unchanged multiaxis core. Full-array parity with the old individual engine is tested. Unlike earlier partial endpoint screening, all four proximal endpoints, including stationary axes, are checked on all new 216 cases. Limits, state guards, reference, pure PD, zero desired velocity/feedforward, torque-path model and quality thresholds are unchanged.

|Yaw Kp/Kd|Simultaneous operating|Additional simultaneous|Individual regression|Worst individual all-four RMSE rad|Descriptive worst over 384 rad|
|---|---:|---:|---:|---:|---:|
|64/1|144/144|24/24|216/216|0.0119380156145878|0.0119380156145878|
|72/1|144/144|24/24|216/216|0.0119457525753513|0.0119457525753513|

Retained simulation candidate: `{"kd": [1.4, 4.0, 1.0, 1.4], "kp": [100.0, 300.0, 72.0, 100.0]}`. Same research-only Kp 300 on joint 23; it is outside the unchanged live Kp 100 validator and is NOT a real motor rating or permission to apply the vector. A successful finite regression is neither a global optimum nor arbitrary-VR/free-base validation.

The descriptive combined score is the maximum original-reference RMSE across source simultaneous and new individual conditions for the SAME gain vector. It is not an independent held-out score or an improvement percentage versus a different study. The selection itself preserves source simultaneous order, rather than reranking from the new regression.

Post-hoc descriptive combined minimum: `{"kd": [1.4, 4.0, 1.0, 1.4], "kp": [100.0, 300.0, 64.0, 100.0]}` with worst RMSE 0.0119380156145878 rad. This is 0.064767% below the frozen source-order survivor. The difference is small; the source-order selection remains separately recorded, and it is NOT claimed to be the combined-error minimum. Both vectors remain simulation-only comparison candidates.

## Accuracy, guard evidence and preservation

For the frozen 72/1 source-order candidate, the worst observed values in the new 216 regressions were:

| Metric | Maximum |
|---|---:|
| All-four endpoint error (rad) | 0.0178485247531 |
| All-four endpoint speed (rad/s) | 0.00407006469109 |
| Right-arm end-hold RMS speed (rad/s) | 0.00327282929425 |
| Right-arm end-hold position variation (rad) | 0.000319501986046 |
| Torque-limiting ratio | 0 |
| Hard-clipping ratio | 0 |

All new-run minimum soft/model-hard/stopping margins: 0.211798601205472/0.261798601205472/0.160598601205472 rad. Guard events: none; base rejections: none; exclusions: none.

The 0.05 rad extra internal reserve and all 29-joint pre/post/final-step check remain. Observed clearance refers to software/model ranges, not measured mechanical stops. No physical braking or absolute no-contact/stability guarantee is inferred from an offline refusal.

All 320 preexisting protected runtime/model files match their initial hashes. The original dirty VR worktree status is byte-identical to the saved status. No reset/clean/overwrite, real gain change, model edit, IK damp/cost edit, G1 SSH, SDK/DDS creation, publisher/subscriber, actuation, deployment, or Robot/All unblock occurred.

## Verification actually performed

The source 462 records were fully reaudited; the new 432 full-state traces were read back with 5,786,288 rows at 500 Hz and 12,528 joint extrema. The audit recomputed applied vector PD torque, all-four quality, original held targets, model mutation, plan completeness, guards and frozen selection. Standalone audit-only CLI also exited 0 without any new dynamics. Physics-rate continuous trajectories are not independently reconstructed.

Windows suite: 358 discovered, 357 passed, one original C++ compiler-dependent skip, zero failures/errors. Hosted run 34689112317, job 103541156241 on 25095da: 358/358 passed, zero skips; decoded logs inspected. CI executes regressions/component dynamics, not the full 432-case matrix. The full study ran in the isolated Windows environment.

New tests: 27/27, including profile/plan isolation, old-engine full-state parity, all-four inactive-axis bias rejection, PD equations, no fabricated winner, failure order, wrong/missing evidence and source/summary tampering. The real two-case bundle fixture mocks source receipt only and is not counted as formal source revalidation or a full new study.

## Records and reproduction

Raw full-state data: `C:\Users\user\Documents\G1_PD_YawRegression_20260912`. Original yaw data: `C:\Users\user\Documents\G1_PD_MultiaxisYaw_20260912`. Compact evidence: `docs/validation/g1_pd_yaw_regression_20260912/`. Raw inventory lists exact byte hashes; full NPZ files remain on the PC. Repository text files may be normalized by Git line-ending handling; raw-byte hashes refer to retained original artifacts.

New all_cases.csv raw SHA256: `b2aec1409312e6d1e5da4f4239ea1c711785748fa75dcbe22fba2b1f57d111ac`. Usage: `experiments/twist2_right_arm_manual/MUJOCO_PD_YAW_REGRESSION.md`. Run `mujoco_pd_yaw_regression.py --source-yaw <source> --output <new-folder> --workers 4`; reread with the same paths and `--audit-only`.

Next permitted work remains offline. Evaluate independently timed or recorded multi-axis VR references, hand/wrist excitation, payload/noise/thermal realism and actual actuator constraints before considering hardware. Do not treat an earlier final-review JSON for different gains as certification of this vector.
