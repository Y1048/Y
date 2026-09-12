# Independent joint timing PD verification — 2026-09-12

Base `402e1ed9e20fcac98caca2c696158409f1fc83fa`.
Dynamics implementation `bbc4b55b8269edbe51e980336c7199f881eadf3c`.
Processing correction `615b96aa8ec69125b426ed79a1723d45d4964bee`.
This result is simulation research, not a deployable G1 configuration.

## Purpose and actual executions

Two prior candidates were frozen: Kp22..25=[100,300,64,100] and [100,300,72,100],
both with Kd=[1.4,4,1,1.4]. Other joints retain original gains. No retuning.
All eight profiles and six scenarios were defined before running:
**96 actual integrations, 96 completed, 96 passed; no missing or pruned cells**.
Twelve are synchronous control comparisons; 84 use independent timing. Each
candidate sees exactly the same 48 conditions. Test runs are counted separately.

Profiles include forward/reverse start staggering, different per-axis amplitudes,
speeds and repetition counts, mixed signs, paired starts, six-cycle 30-second
common rest, and an elbow-shifted baseline. Actual starts differ by up to 1.12s;
amplitudes are 4..11deg, speed caps 10..27deg/s and cycles 3..6 per axis.
The six model conditions are nominal, half timestep, heavy, the previous coupled
delay boundary, light-delayed and mixed-delayed. Mass/inertia, damping, friction
and torque delay/lag are assumptions, not measured physical uncertainties.
Targets start at rest rather than jumping onto a phase-shifted waveform. Each
axis finishes its cycles and waits at baseline for the shared final rest.
This is NOT recorded VR or free-base balance validation.

## Result and tradeoff

| Yaw Kp/Kd | New passes | Worst all4 RMSE rad | Max own-hold error rad | Common-rest error rad |
|---|---:|---:|---:|---:|
| 64/1 | 48/48 | 0.0114164565416429 | 0.015561046976073 | 0.0104741927664771 |
| 72/1 | 48/48 | 0.0110175568224662 | 0.0155658845685444 | 0.0103992152130213 |

The new 48-condition minimax choice is **yaw72/1**, other gains unchanged.
Its new-condition worst RMSE is **3.494076%** below 64/1.
For 64/1 the maximum occurs at joint24 in shifted_start/mixed_delayed; for 72/1
the limiting error in that same condition moves to joint25. These observations
are not proof that higher stiffness universally improves stability.

Prior 384-attempt descriptive maxima remain 64/1=0.0119380156145878 rad and 72/1=0.0119457525753513 rad.
Both new maxima are smaller than the corresponding previous maxima; therefore
64/1 still has the very slightly smaller historical-plus-new maximum. We do NOT
claim 72/1 minimizes every combined dataset. Each candidate passed its previous
own 384 attempts and these 48 attempts, but this is not 432 independent unseen
conditions. Earlier endpoint mappings are not retroactively changed. Both
candidates remain valid comparison points, not continuous/global optima.

Kp23=300 is research-only, above the unchanged live-code Kp100 input limit.
Neither vector is approved for physical output or automatically deployed.

## Acceptance mapping and untouched dynamics

The original pure PD, zero velocity target/feedforward, writer limiting, 500Hz
command/50Hz reference, all29 state guards, post-step speed checks, contact rules,
source model/meshes, torque constraints and 0.05rad inner reserve are unchanged.
The new core is separate. Its synchronous-input full29 array test matches the
old core exactly. No qpos projection, target bias, gravity compensation,
integral term, IK damp/cost adjustment or limit widening was introduced.

Rest windows follow EACH axis's own segment clock. Every last100ms endpoint
requires that axis error<=0.02rad, speed<=0.1rad/s, p2p<=0.005rad, RMS<=0.05rad/s.
Other intentionally moving axes are not mislabeled as residual oscillation.
At shared final rest, the WHOLE last1s checks all4 position/speed; last100ms
checks right7 p2p/RMS with the original numeric thresholds. The reader rebuilds
held targets and each axis's cycle/phase metadata separately.

For yaw72/1, maxima in the 48 new runs were:

```json
{
  "max_axis_hold_error_rad": 0.015565884568544353,
  "max_axis_hold_speed_rad_s": 0.03175568243911184,
  "torque_limited_ratio": 0.0,
  "hard_clipped_ratio": 0.0,
  "common_error_rad": 0.01039921521302134,
  "common_speed_rad_s": 1.3389024266109343e-05,
  "common_right7_p2p_rad": 1.0351344639225601e-06,
  "common_right7_rms_speed_rad_s": 1.0564100901517321e-05
}
```

Torque-target limiting and hard-clipping ratios were zero for all96cases.
No guard events. Observed minimum soft/model-hard/stopping slack:
**0.211798601205472 / 0.261798601205472 / 0.160598601205472 rad**.
Software/XML bounds are not measured mechanical stops. Finite evidence and
physics-step minima do not prove real braking or continuous-time safety.

## Processing failure and correction

The first96-case program exited1 after integration: strict summary readback
compared total simulated time 3067.4730000001064s with 3067.473000000107s.
The ONLY difference was floating-point summation order. No score, ranking,
gain, eligibility, condition or trajectory differed. That failure is preserved.

Future totals use math.fsum. The audit allows 1e-9s absolute tolerance ONLY for
total elapsed time, not accuracy/stability or other fields. Only the exact
pre-fix runner hash is recognized; all other physics/model/source bytes remain
strict. Old manifests, caseJSON, NPZ and summary are byte-identical. Archived
Python is never executed. A subsequent audit-only CLI exited0 with no dynamics.
The processing receipt records original and current runner hashes.

## Verification actually performed

Dedicated tests: **40/40 passed**, including five aggregation/source regressions.
Two initial TEST assumptions failed (nonoverlapping hold/cross fixture and wrong
text spelling of the existing cap). Only test expectations changed. Formal
conditions, numeric thresholds and dynamics were not altered to rescue failures.
A local documentation-packaging input also had quoting errors before file creation;
that input was discarded and rebuilt as syntax-checked code plus plain templates.
No simulation evidence or repository source was changed by that input error.

Final Windows allowlist: **398 discovered, 397 passed, one existing C++ compiler
skip, zero failures/errors**. Earlier393-suite results are historical.
Inspected hosted run **34692035188**, job **103548879462**, on615b96a:
**398/398 passed, zero skips**, including C++ parity. Hosted work is regression
and component dynamics, not the full96 formal study. Formal integrations used
isolated Windows Python3.11.9, MuJoCo3.3.7 and NumPy2.4.6.

Re-read all96 full29 traces: **1,533,780 rows at500Hz**, **2,784 joint minima**.
Checked original independent reference timing, vector PD torque, applied gains,
model mutations, rest windows, complete plan, source/trace hashes, guard witnesses
and scores/ranking. Continuous physics-rate trajectories are not reconstructed.

## Records and preservation

Raw: `C:\Users\user\Documents\G1_PD_IndependentTiming_20260912`. 253 files, 1,225,023,446 bytes.
Compact tables/plans/manifests/audits: `docs/validation/g1_pd_independent_20260912/`.
Raw NPZ streams remain on PC, not claimed to be uploaded to GitHub.
Raw comparison CSV SHA256: `1b7c0a5f999f28402c0dc767ac75de559b0cbb2cd78cda1543aa3dd3d8082c96`.
Usage: `experiments/twist2_right_arm_manual/MUJOCO_PD_INDEPENDENT_TIMING.md`.
Run `mujoco_pd_independent_study.py --output <new-folder> --workers 4` and
recheck with the same output plus `--audit-only`.

All 359 protected runtime/model/experiment snapshot files match their
initial hashes. Original dirty live-tree Git status is unchanged. No G1 SSH,
DDS/SDK, publisher/subscriber, motor output, ARM deployment, Robot/All unblocking,
VR-environment modification, IK or real-gain edit occurred. Older final-review
bundles still describe their recorded gains; they are not overwritten to certify
this result. Recorded VR/hand/wrist paths, actual actuator limits, load/noise/
thermal/backlash, full-body balance, braking and ownership remain unverified.
