# G1 per-joint PD results — 2026-09-12

Base `2ae59402367def9d28e823c59e81bc09a5a8040e`. Dynamics executed on `4eed0c5b763f03b121a1929eacd53c3ae750c97b`.
Reporting/audit correction `768a2355ea5b716137858851eb2f721ce023e783`. Simulation only; no deployment.

## Selected candidate

Joints 22..25: **Kp=[100.0, 300.0, 100.0, 100.0]; Kd=[1.4, 4.0, 1.4, 1.4]**.
This vector passed **144/144 existing operating cases +48/48 new cases**.
Each proximal axis was excited separately; remaining joint gains were unchanged.

**Joint 23 Kp 300 exceeds the UNCHANGED live/C++ ceiling 100.** This is a separate
research-only simulator bound, not an actuator rating or hardware approval.
Do not copy the values into START_TWIST2_MINK_CYCLE_CANDIDATE or relax live
validators. Joint/torque/velocity limits and all 29  guards were NOT increased.
No integral, gravity compensation, velocity feedforward or reference offset.

## Actual runs and procedure

Formal runs: 1,020; completed: 978; all-criteria eligible: 886.
Phase counts: {"axis22": 36, "axis24": 36, "axis25": 36, "fresh": 96, "operating": 576, "roll": 240}.
There were 57 distinct vectors, not 1,020 unique gains. Twelve exploratory pilot runs and
unit-test dynamics are separate and not included in the formal count.

Roll search: 40 pairs x 6 conditions; then coordinate search on joints 22, 24 and 25, with 6 pairs x 6 conditions each.
Four candidate vectors were frozen before 576 full operating verification runs.
The two passing vectors were frozen before 48 new cases each. No fresh outcome
was used to retune a gain or threshold. Each planned cell was attempted; an
unsafe early refusal did not complete its intended trajectory.

Operating coverage: four separately excited proximal axes, 4/8/12 degrees amplitude,
10/20/30 deg/s limits, elbow starts shifted 10 degrees, 12 cycles and 30-second final holds.
Fresh 48 cases: twelve prespecified combined model/actuator conditions times 4 axes,
6/10/12-degree profiles, 15/25/30 deg/s caps, shifted starts and 5-second holds. Model mass,
friction, damping and torque-delay/lag are hypothetical, not measured G1 ranges.
This is a finite, fixed-pelvis study. Coordinate search is not global 8-dimensional optimization;
Kp23 = 300 and other Kp=100 remain at search boundaries. Unsampled gains, continuous
uncertainties, simultaneous joint motions and real motor conditions are not proven.

## Same-condition comparisons

|Kp22..25|Kd22..25|Operating pass|Fresh pass|Worst operating RMSE rad|
|---|---|---:|---:|---:|
|100,300,100,100|1.4,4,1.4,1.4|144/144|48/48|0.0119627613072|
|100,300,100,100|3,5,3,3|144/144|48/48|0.0130681964435|
|100,300,100,100|1,4,1.4,1|140/144|not selected|excluded|
|100,100,100,100|1.4,1.4,1.4,1.4|108/144|not selected|excluded|

The lower-D coordinate vector has lower partial errors but fails 4 conditions,
so it is not an eligible optimum. The original common 100/1.4 vector fails 36 roll cases.
All selected-axis combined results use 36 existing + 12 fresh cases each:

|Joint|Kp|Kd|Operating + fresh passes|Worst active RMSE rad|Worst endpoint error rad|
|---|---:|---:|---:|---:|---:|
|22|100|1.4|48/48|0.0115029760078|0.0178481020382|
|23|300|4|48/48|0.0115672853895|0.0152375907852|
|24|100|1.4|48/48|0.00809790768242|0.00749447468412|
|25|100|1.4|48/48|0.0119627613072|0.0141853332211|

Overall selected worst active RMSE:0.011962761307211 rad
(0.685415734 degrees).
Worst end-tail RMS speed across 7 right-arm joints: 0.00270634449969118 rad/s;
peak-to-peak: 0.000264837897505499 rad.
All 192 selected cases have zero recorded torque-limiting/clipping ratios.
End-tail metrics are finite-horizon conditions, not a formal stability margin.

Matched nominal roll: RMSE 0.0230798161033409 -> 0.0084943385038965 rad
(**63.195814%** reduction). End-tail position error
0.0295955213955502 -> 0.00999710963266143 rad.
Peak active torque increased 3.04551853307257
-> 3.4126274894744 Nm. Better tracking did not mean no extra demand.
After a 30-second nominal hold, error fell from 0.0223132110565802 to 0.00768426027915214 rad.
These are the SAME nominal profiles, not mismatched worst-case percentages.

## Failures and guards

Base refusals: {"post_step_measured_velocity_limit": 42}.
Exclusion labels: {"active_tail_error_rad": 92, "post_hold_last_second_not_settled": 6, "post_step_measured_velocity_limit": 42}.
42 velocity refusals; 92 completed endpoint-error failures, 6 of which also fail
extended hold. Labels overlap and must not be added as separate trials.
All 29 joint-limit guard events: {}.
Minimum observed soft/model-hard clearance:
0.211798601205472 / 0.261798601205472 rad.
Original 0.05 rad inner reserves, stopping assumptions and pre/post/final checks
are unchanged. No projection or substitute clipped reference is accepted.
XML ranges are not measured hard-stop positions and simulation refusal is not
a verified real emergency brake. No absolute physical no-contact promise.

## Verification and recorded processing correction

The full audit reloaded 1,020 full-state traces with 29 joints, 11,159,730 rows sampled at 500 Hz,
and 29,580 joint minimum/witness records. It recomputed
PD torque equations, original references, endpoint criteria, actual vector
arrays, model mutation, all 29 sampled limits, plans and adaptive decisions.
Full physics-rate continuous trajectories are not independently reconstructed.

The initial audit refused equality because parallel completion ordered failure
lists differently. The correction sorts cases by id before summary creation.
Original summary and all 48 manifest source/model/mesh inputs were archived.
Canonical comparison proved counts, every metric, eligibility/rank and selected
vector unchanged. Raw case JSON/NPZ and frozen selection were not edited and no
new dynamics were run for the correction. processing_fix.json separates original
dynamics provenance and the fixed processing source; the full audit then passed.

All 144 new common-baseline trajectories exactly match the earlier operating
study across every saved 29-joint array and guard/metric result. This checks
that the adapter preserves original behavior for original gains.

Final Windows suite: 257 discovered, 256 passed, 1 original C++ compiler-dependent skip, 0 failures/errors.
Final Linux run 34626120122, job 103351536341 on `768a2355ea5b716137858851eb2f721ce023e783`:
**257/257 passed, 0 skipped**, including C++ parity; decoded log inspected.
Before the reporting fix, 256/256 hosted tests also passed on `4eed0c5b763f03b121a1929eacd53c3ae750c97b`.
The final 28 per-joint tests include reverse-completion order, scope restoration,
vector/torque consistency, unchanged Kp 100 live bound, reference/guard tampering
and real dynamics. CI runs tests/component dynamics, not all 1,020 formal cases.
Full study: isolated Windows, Python 3.11.9, MuJoCo 3.3.7, NumPy 2.4.6.

## Records and unchanged live path

Raw records written directly to `C:\Users\user\Documents\G1_PD_PerJoint_20260912`. No redundant multi-GB copy.
Repository evidence: `docs/validation/g1_pd_perjoint_20260912/`.
all_cases.csv SHA256:`f55d142833620704e931e6305ccec77fb00ba488e44a827f881474449d45e8b5`.
Includes original/corrected summaries, processing history, frozen selections,
all-case CSV, joint margins, raw inventory, matched baseline and tests.
Usage:`experiments/twist2_right_arm_manual/MUJOCO_PD_PERJOINT.md`.

Original dirty worktree, working VR/Mink/UDP/LowCmd/IK, source XML/meshes,
actual gains and Robot/All charging blocks remain unchanged. No G1 SSH or DDS/SDK,
publishers/subscribers, physical actuation, GUI/BAT or ARM deployment.
Not wrist tuning, simultaneous arbitrary VR motion, free-base balance, heating,
sensor noise/backlash or actuator certification. Next permitted work is offline
model calibration/sensitivity or broader declared validation, not deployment
of gains outside unchanged hardware validators.
