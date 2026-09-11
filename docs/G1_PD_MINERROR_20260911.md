# G1 strict minimum-error PD results — 2026-09-11

Base `1d7b1f76111034a468774e5748eae8d30da5b42d`; tested implementation `1d768b7cefe44adc4027346aa17f9af1a10e385a`. Offline only.

The first strict-calibration-order validation survivor is **100/1.275**. Known45 worst RMSE=0.00930442651158736rad; fresh16 worst RMSE=0.00952406318834176rad. This is a bounded finite-grid, finite-horizon simulation candidate, NOT a physical optimum or deployment.

Known45-condition finite-grid winner: **[100.0, 1.275]**.
Fresh validation survivors in unchanged calibration order:
`[[100.0, 1.275], [100.0, 1.28], [100.0, 1.285], [100.0, 1.29], [100.0, 1.295], [100, 1.3], [100.0, 1.325], [100.0, 1.35], [100.0, 1.4], [100, 2.0]]`. These are different claims: only frozen finalists,
not the whole grid, were tested on the16 new conditions. This does not prove
a continuous-gain or physical optimum.

## Actual simulations and decisions

482 distinct grid cells; **1161 actual simulations**:
1001 known-condition runs and 160 fresh-condition runs.
Completed=1100; original guard eligible=1100;
endpoint-quality eligible=938.
Grid decisions: `{"bound_pruned": 248, "constraint_rejected": 223, "fully_evaluated": 11}`.
Base refusals: `{"joint_stopping_envelope_exhausted": 10, "measured_velocity_limit": 3, "ready_pose_not_settled_in_final_warmup_second": 48}`.
Additional quality refusals: `{"max_q22_tail_error_rad": 162, "max_right7_tail_p2p_rad": 2, "max_right7_tail_rms_speed_rad_s": 3}`.
Guard events: `{"joint_stopping_envelope_exhausted": 10}`.
Do not claim482x45 runs, count pruned conditions as executed, or label
bound-pruned cells unstable. A partial maximum is a lower bound on full maximum
error; a fully evaluated feasible incumbent supplies the upper bound. All482
such decisions and witnesses were independently checked from saved evidence.
This numerically verifies the minimax winner on this finite calibration grid.

## Protocol

No2% error plateau: strictly minimize worst original joint22-reference RMSE
AFTER every unchanged stability/limit requirement passes. Endpoint motion
breaks exact RMSE ties only. The previous workflow is not modified.
The482 pairs span Kp16..100 and Kd0.1..20 plus a finer Kp96/98/99/99.5/100,
Kd1.200..1.350 by0.005 region. Kp100 ceiling remains.
45 earlier conditions are reused KNOWN calibration, not fresh evidence.
16 new scenarios were frozen before any dynamics:12 hypothetical motor/friction
combinations from seed20260911 and4 model variations. The RNG selects the
parameter list, not stochastic measurement noise or calibrated real uncertainty.
Seed controls100/1.3,100/1.4,100/2 were resimulated over all45. Nearby forced
comparisons and early-refusal witnesses are retained. Up to8 fully tested top
pairs plus seed controls were frozen before validation. No retuning on its
outcome and no relaxation of the quality thresholds.

## Frozen finalists

| Kp/Kd | Known quality passes | Worst known RMSE rad | New quality passes | Worst new RMSE rad |
| --- | --- | --- | --- | --- |
|100/1.275|45/45|0.00930442651159|16/16|0.00952406318834|
|100/1.28|45/45|0.00930913265341|16/16|0.00952833722011|
|100/1.285|45/45|0.00931384426079|16/16|0.00953261474501|
|100/1.29|45/45|0.00931856129154|16/16|0.00953689653069|
|100/1.295|45/45|0.00932328267968|16/16|0.00954118281551|
|100/1.3|45/45|0.00932800765182|16/16|0.00954547152808|
|100/1.325|45/45|0.00935170298676|16/16|0.00956698357447|
|100/1.35|45/45|0.00937551384893|16/16|0.00958860188249|
|100/1.4|45/45|0.0094234839966|16/16|0.00963215321158|
|100/2|45/45|0.0100312489178|16/16|0.010186323859|

Combined61-condition descriptive metrics, not post-hoc reranking:

```json
{
  "100/1.275": {
    "known_worst_rmse_rad": 0.00930442651158736,
    "fresh_worst_rmse_rad": 0.009524063188341758,
    "all61_worst_rmse_rad": 0.009524063188341758,
    "nominal_rmse_rad": 0.00683642690663944,
    "all61_worst_tail_rms_rad_s": 0.00830795701224163,
    "all61_worst_tail_p2p_rad": 0.0007455675555081975,
    "all61_peak_error_rad": 0.01675623240029296,
    "all61_peak_q22_torque_nm": 1.4664552228709695
  },
  "100/1.28": {
    "known_worst_rmse_rad": 0.009309132653405485,
    "fresh_worst_rmse_rad": 0.00952833722011405,
    "all61_worst_rmse_rad": 0.00952833722011405,
    "nominal_rmse_rad": 0.006840983206432442,
    "all61_worst_tail_rms_rad_s": 0.008281328042073611,
    "all61_worst_tail_p2p_rad": 0.0007437275615794214,
    "all61_peak_error_rad": 0.016769160384121462,
    "all61_peak_q22_torque_nm": 1.4664964811620393
  },
  "100/1.285": {
    "known_worst_rmse_rad": 0.009313844260789177,
    "fresh_worst_rmse_rad": 0.00953261474500992,
    "all61_worst_rmse_rad": 0.00953261474500992,
    "nominal_rmse_rad": 0.00684554596418576,
    "all61_worst_tail_rms_rad_s": 0.008254464225169386,
    "all61_worst_tail_p2p_rad": 0.0007418523982859471,
    "all61_peak_error_rad": 0.01678209595716834,
    "all61_peak_q22_torque_nm": 1.4665371123799729
  },
  "100/1.29": {
    "known_worst_rmse_rad": 0.009318561291542867,
    "fresh_worst_rmse_rad": 0.009536896530692123,
    "all61_worst_rmse_rad": 0.009536896530692123,
    "nominal_rmse_rad": 0.006850115113921835,
    "all61_worst_tail_rms_rad_s": 0.008227474308032124,
    "all61_worst_tail_p2p_rad": 0.0007400051069355595,
    "all61_peak_error_rad": 0.016795039096952666,
    "all61_peak_q22_torque_nm": 1.4665772657123037
  },
  "100/1.295": {
    "known_worst_rmse_rad": 0.009323282679682786,
    "fresh_worst_rmse_rad": 0.009541182815512646,
    "all61_worst_rmse_rad": 0.009541182815512646,
    "nominal_rmse_rad": 0.006854690691170178,
    "all61_worst_tail_rms_rad_s": 0.008200227727570533,
    "all61_worst_tail_p2p_rad": 0.0007381200301068702,
    "all61_peak_error_rad": 0.016807989845440657,
    "all61_peak_q22_torque_nm": 1.4666169481215925
  },
  "100/1.3": {
    "known_worst_rmse_rad": 0.009328007651823863,
    "fresh_worst_rmse_rad": 0.009545471528076856,
    "all61_worst_rmse_rad": 0.009545471528076856,
    "nominal_rmse_rad": 0.006859272623171351,
    "all61_worst_tail_rms_rad_s": 0.00817281995412744,
    "all61_worst_tail_p2p_rad": 0.0007362076626669101,
    "all61_peak_error_rad": 0.01682094811634971,
    "all61_peak_q22_torque_nm": 1.4666561589382272
  },
  "100/1.325": {
    "known_worst_rmse_rad": 0.00935170298676036,
    "fresh_worst_rmse_rad": 0.0095669835744733,
    "all61_worst_rmse_rad": 0.0095669835744733,
    "nominal_rmse_rad": 0.006882274278645048,
    "all61_worst_tail_rms_rad_s": 0.008033268772876925,
    "all61_worst_tail_p2p_rad": 0.0007261842592991008,
    "all61_peak_error_rad": 0.016885848397618988,
    "all61_peak_q22_torque_nm": 1.466846348487454
  },
  "100/1.35": {
    "known_worst_rmse_rad": 0.00937551384892793,
    "fresh_worst_rmse_rad": 0.009588601882492661,
    "all61_worst_rmse_rad": 0.009588601882492661,
    "nominal_rmse_rad": 0.006905433513006704,
    "all61_worst_tail_rms_rad_s": 0.007890529389418506,
    "all61_worst_tail_p2p_rad": 0.0007155265164945357,
    "all61_peak_error_rad": 0.016950920527575616,
    "all61_peak_q22_torque_nm": 1.4670228196513801
  },
  "100/1.4": {
    "known_worst_rmse_rad": 0.009423483996599449,
    "fresh_worst_rmse_rad": 0.009632153211579246,
    "all61_worst_rmse_rad": 0.009632153211579246,
    "nominal_rmse_rad": 0.006952196673044818,
    "all61_worst_tail_rms_rad_s": 0.007598983514253289,
    "all61_worst_tail_p2p_rad": 0.0006928682583419721,
    "all61_peak_error_rad": 0.017081530011169313,
    "all61_peak_q22_torque_nm": 1.4673416027172763
  },
  "100/2": {
    "known_worst_rmse_rad": 0.010031248917777055,
    "fresh_worst_rmse_rad": 0.01018632385904016,
    "all61_worst_rmse_rad": 0.01018632385904016,
    "nominal_rmse_rad": 0.007556528468090668,
    "all61_worst_tail_rms_rad_s": 0.00448629124200852,
    "all61_worst_tail_p2p_rad": 0.0004207291219702203,
    "all61_peak_error_rad": 0.018695291846087203,
    "all61_peak_q22_torque_nm": 1.469100729588381
  }
}
```

## Limits and verification

Original fixed pelvis, joint22 +/-8degree three-cycle motion, group gains22..25,
50Hz references,500Hz writer and all29 pre/post/final guards are unchanged.
No limit relaxation, measured-state projection, or substituted/clipped trajectory.
Minimum observed soft margin=0.211798601708536rad;
model-hard margin=0.261798601708536rad.
The XML range is not a measured physical hard stop. Simulated refusal is not a
validated real braking/hold maneuver or a continuous-time safety guarantee.

Audit reloaded all1161 compact/full trace pairs,
10120147 all29 sample rows at500Hz, and
33669 physics-rate extrema/witness records.
It recomputed scores, quality, limits, pruning proofs and frozen selection.
135 old/new seed trajectories matched EXACTLY across all29 q/dq/ref/cmd and
clock/cycle/segment arrays. Source/mesh bytes and retained-copy hashes checked.
Full physics-rate trajectories and unobserved between-step states are not
independently reconstructed.

Local Windows Python3.11.9/MuJoCo3.3.7/NumPy2.4.6,8 workers:
159 discovered,158 passed,1 C++ compiler-dependent skip,0 failures/errors.
Hosted run34602915247 job103274322288 on `1d768b7cefe44adc4027346aa17f9af1a10e385a`:
159/159 passed,0 skipped including C++ parity; decoded logs inspected.
CI tests include the6-case smoke, NOT this entire optimization.
Initial prototype smoke exposed tuple/list serialization comparison; it was
fixed and regression-tested before full execution, without changing dynamics.
That failed smoke is retained separately and excluded from experiment counts.

## Files and remaining scope

Compact evidence:`docs/validation/g1_pd_minerror_20260911/`.
all_cases SHA256:`03b5e6b26371194107cd92d9444af30d886ea6ccebd0a639d6e537f1daa48b7e`.
Raw cases/full29 traces/decisions copied and hash-verified at`C:\Users\user\Documents\G1_PD_MinError_20260911`.
Usage:`experiments/twist2_right_arm_manual/MUJOCO_PD_MINERROR.md`.

Working VR/UDP/LowCmd/IK code, original dirty PC tree, XML/meshes, physical gains
and charging-time Robot/All blocks are unchanged. No G1,DDS,SDK,motor output,
GUI/BAT,ARM or deployment. No validated real delay/noise/backlash/temperature,
free-base balance, larger motions or independent gains for other joints.
Sub-percent simulated improvement is not established hardware improvement.
Continue separately specified offline testing or reviewed model calibration;
never automatically apply a candidate or relax a failed criterion.
