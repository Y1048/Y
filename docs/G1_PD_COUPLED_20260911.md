# G1 coupled model/actuator PD matrix — 2026-09-11

Base `884882d8175676caac7e852547de90b48aa1c700`. Tested code `47b85fe66ee43a3a841b3d9657568ec8d00f5ac1`. Offline only.

## Answer and actual coverage

Not all possible gains or operating conditions have been tested. Prior studies
covered discrete gains and a single fixed-pelvis small-motion reference. This
study fills an important gap: model changes and actuator delay occur TOGETHER,
not in separate scenario families. Every declared12pairs x81conditions cell
was actually attempted without pruning: **972 executions**.

First stage:780 full-factorial/nominal calibration cases, then
128 cases for frozen finalists/controls.
Second stage:64 additional cases fill ALL unselected gain x
validation cells, including any previously unsuccessful gain. There are no
missing cells in this declared matrix. Each cell starts from a fresh state.
A guard-refused attempt is not claimed to finish all three cycles.

Completed:969; core guard eligible:969;
endpoint-quality eligible:969.
Core rejection counts:{"ready_pose_not_settled_in_final_warmup_second": 3}.
Additional quality counts:{}.
Limit guard events:{}.

The lowest worst-error pair that passed all81 conditions among these12 tested pairs is **100/1.4**. This is not a continuous-gain, universal or physical optimum.
The original frozen shortlist ordering is preserved in base_summary.json.
The full81 ranking below is descriptive after every declared condition has
been observed. These81 conditions are no longer independent validation data
for future retuning on this same data set.

## Unchanged controller and joint-limit contract

Same joint22 +/-8-degree round trip, three cycles; gains applied together to22..25.
Same fixed pelvis,50Hz reference,500Hz writer, zero dq_cmd/tau_ff, same original
XML/mesh/actuator limits and all29 pre/post/final-state monitor.
No IK damp/cost, real gains, VR input/UDP/LowCmd logic or Robot/All block changed.
The private simulation model's passive damping is an uncertainty factor, not
an edit to live IK damping or actual hardware Kd.

Soft reserve0.05rad and reaction/braking assumptions were not relaxed. No measured
qpos projection or clipped substitute trajectory is accepted for a better score.
Observed minimum soft clearance:0.211798601708536rad;
model hard-range clearance:0.261798601708536rad.
XML hard range is NOT an identified real hard-stop position; simulation refusal
is NOT a physically verified braking maneuver or absolute safety guarantee.

## Frozen conditions

Calibration:nominal plus all64 Cartesian products of:
right-arm mass/inertia scale0.75/1.25; passive damping scale0.5/1.5;
frictionloss scale0/0.5; torque delay0/2ms; first-order torque lag0/6ms;
physics timestep1/0.5ms. Each of12 pairs sees all65.
New validation:16 different combined configurations fixed with seed2026091104
before execution. Values are explicit in base_manifest.json. The RNG chooses
parameter tuples, not measurement noise. These are hypothetical sensitivities,
not probabilities or system identification of actual G1 uncertainty.

Mass/inertia changes are propagated with mj_setConst, per MuJoCo's official
Simulation documentation. No hidden compensation or position-reset step is added.
Lower physics timestep also raises the ideal PD evaluation rate, so this is
not an integrator-only convergence test of a fixed motor loop.

## Complete all81-condition comparison

RMSE is against the ORIGINAL q22 reference. End-of-hold metrics use the final
100ms of each of nine holds and the worst of seven right-arm joints.
A rejected candidate has no comparable full worst-error optimization score.

| Kp/Kd | Quality pass | Worst RMSE rad | Worst right7 tail RMS rad/s | Worst tail p2p rad |
| --- | --- | --- | --- | --- |
|100/1.4|81/81|0.00795380216629|0.00862886521721|0.000663520925392|
|100/1.5|81/81|0.00803073778283|0.00762505167848|0.000570009350133|
|100/1.75|81/81|0.00823495903793|0.00567050626534|0.000389840577255|
|96/1.5|81/81|0.00830990500992|0.00730144101759|0.000462486697946|
|100/2|81/81|0.00845451406071|0.00430732027082|0.000265893158425|
|96/2|81/81|0.00875878126611|0.00463110333573|0.00026750056764|
|100/2.5|81/81|0.00893175631909|0.00303320209722|0.000184097434369|
|88/2|81/81|0.00944690727196|0.00613054189676|0.000469210349562|
|100/3|81/81|0.00944995389047|0.00225048675436|0.000164133544249|
|80/1|80/81|excluded|excluded|excluded|
|100/1.275|80/81|excluded|excluded|excluded|
|100/1.3|80/81|excluded|excluded|excluded|

All refusal records and exact scenario values are in failures.json.
Different condition sets are not interchangeable: do not claim an improvement
percentage by comparing this table's error with an earlier study's worst RMSE.
All candidate comparisons WITHIN this table use the same81 conditions.

## Verification and retained evidence

Local Windows Python3.11.9,MuJoCo3.3.7,NumPy2.4.6. The183-test allowlist passed182,
with one original C++ compiler-dependent parity skip, then10 disjoint matrix
tests passed.192 unique passes,1 skip,0 failures. Repeated tests are not counted twice.
Hosted run34609334553,job103295578442 on `47b85fe66ee43a3a841b3d9657568ec8d00f5ac1`:
**193/193 passed,no skips**, including C++ reference compilation/parity.
CI ran the regression allowlist and smoke/parity dynamics, NOT all972 executions.
The full study ran in the isolated Windows worktree; the live dirty tree was not reset.

Exact nominal, motor-only and model-only parity with inherited engines was tested.
Audit reloaded all972 compact/full29 trace pairs, 8854377 rows
of29 states at500Hz and 28188 joint extrema/witness records.
It checked source/model/mesh hashes, mutation evidence, clocks, original-reference
RMSE/torque/overshoot/settling, endpoint stability, sampled all29 margins,
frozen first-stage selection, every missing-cell plan and final whole-matrix rank.
Physics-rate pre/post/final checks remain active; full continuous-time state
and all physics-rate trajectories are not independently reconstructed.

Raw base/matrix traces and test logs copied and hash-compared to:
`C:\Users\user\Documents\G1_PD_Coupled_20260911`. Verified raw result files:2930.
Compact evidence:`docs/validation/g1_pd_coupled_20260911/`.
all_cases.csv SHA256:`f1f34a164f311ed6c0978c25a80f4f7b8e4a85d77643edb4f9a9d106eb701ff2`.
Usage:`experiments/twist2_right_arm_manual/MUJOCO_PD_COUPLED_STRESS.md`.

## Still outside coverage

Values between sampled gains; Kp>100; other joints' independent gains; other
initial poses or larger/faster trajectories; sensing noise, backlash, heating,
real payload geometry; standing/free-base TWIST2 balance; true robot delay,
braking and hardware owner integration. Passing this finite model study does
not certify any of those cases. No G1, DDS, SDK, motor output, ARM build/deployment
or automatic gain adoption occurred. Keep physical launch blocks and known-working
VR baseline. Next work remains a separately declared offline operating-condition
study or reviewed model calibration, not another claim of all possible cases.
