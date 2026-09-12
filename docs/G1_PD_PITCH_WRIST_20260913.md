# Recorded-pipeline pitch and wrist PD investigation — 2026-09-13

Base: `43fd4ea11a2d057853688a943a16a6d0505e21fb`.
Initial implementation: `1db575fb88e6ef4aa4c9266d38afead548fa6602`.
Tested provenance correction: `b9c14d2e9f1033eb2f8d40c2ea164bc3db1eb010`.

**No final PD vector is selected.** All four finalists pass the twelve known
recorded conditions, but each fails one of the sixteen expanded conditions.
An experiment/audit exit0 is not a successful trajectory or hardware approval.

## Fixed control contract

Baseline proximal22..25 Kp=[100,300,64,100], Kd=[1.4,3,1.2,1.4]; wrist27=20/1.
Only shoulder pitch22 and wrist pitch27 are varied. Roll23 stays300/3, yaw24
64/1.2 and elbow25 100/1.4. Other joints, original model files and IK remain.
The causal20ms previous-to-current command interpolation is fixed. Every score
uses original seven-joint recorded goals, not the interpolated command.
No lookahead, time stretching, reference bias, gravity compensation, integral
or desired-velocity feedforward. This is PD-plus-prefilter research, not
bare-PD optimization or approval of the unchanged live VR pipeline.

The new process-local adapter permits pitch22 Kp up to160 and wrist27 up to40.
It restores old functions/caps on every exit. The original real Kp100 input
validator is unchanged. Pitch120 and roll300 are NOT approved real-gain values.

## Executed search and conditional phases

|Stage|Grid/plan|Actual integrations|Completed/eligible|
|---|---|---:|---:|
|Pitch22|Kp80/100/120/140/160 x Kd1/1.4/2 x3known cells|45|41/41|
|Wrist27|At best all-pass pitch: Kp15/20/30/40 x Kd0.6/1/1.4 x3cells|36|32/32|
|Validation|4frozen finalists x2clocks x8models|64|60/60|
|Synthetic regression|14known checks per fully passing finalist|0|No qualified entrants|
|**Total**|**26distinct full gain specifications**|**145**|**133/133**|

Every cell in each entered stage was attempted. Regression was conditional on
passing all16recorded cells; no finalist qualified, so its recorded plan is empty.
Do not inherit earlier synthetic passes or describe these new vectors as regressed.
Fixtures, import checks, storage probes and audits are not formal integrations.
Total simulated duration4784.481999999368s is not wall-clock runtime.

## Accuracy on the SAME twelve previously known conditions

All values below are original-goal RMSE maxima across conditions and right7joints.
This twelve-cell comparison is descriptive, not the full sixteen-cell score.

|Pitch22|Wrist27|Known passes|Worst all7 RMSE rad|Wrist27 worst RMSE rad|Expanded passes|
|---|---|---:|---:|---:|---:|
|100/1.4|20/1|12/12|0.014014588331269116|0.013735342449834119|15/16|
|120/1|20/1|12/12|0.013758132191587157|0.013758132191587157|15/16|
|**120/1**|**30/1**|**12/12**|**0.0118017425371684**|**0.009424094299826978**|**15/16**|
|120/1|30/1.4|12/12|0.011802825299733366|0.010079523762354815|15/16|

The120/1+30/1combination reduces the matched worst all7error by15.7895883% and
wrist27error by31.3879917%. It is not selected because it fails expanded validation.
The three-cell screen ranked wrist30/1.4 slightly ahead of30/1; the twelve-cell
ordering differs. Do not rewrite the screen order after seeing validation.
Wrist27 peak torque over these same12cells rises from0.5752612 to0.7010855Nm
for30/1. Smaller error does not imply less actuator demand or hardware safety.

## New mixture exposes coupled yaw/elbow speed failures

Both extra mixtures were fixed before formal execution and used with both clocks:

|Mixture|Mass/inertia|Damping|Friction|Torque delay|Torque lag|Physics step|
|---|---:|---:|---:|---:|---:|---:|
|mix_a|1.10x|0.70x|0.20x|6ms|6ms|1ms|
|mix_b|0.85x|1.50x|0.10x|1ms|10ms|0.5ms|

All four finalists fail ONLY send-clock mix_a. The unchanged upper-speed gate
is1.5rad/s. Integrated signed speeds at rejection, including3swarmup in time:

|Pitch22|Wrist27|Joint|Speed rad/s|Time s|
|---|---|---:|---:|---:|
|100/1.4|20/1|24yaw|-1.5158214487|8.429|
|120/1|20/1|25elbow|-1.5183046717|4.118|
|120/1|30/1|24yaw|-1.5035593181|8.428|
|120/1|30/1.4|24yaw|-1.5211562714|8.428|

The old baseline also fails. These hypothetical torque-path/model mixtures are
not measured G1 uncertainty, and an offline speed refusal alone does not prove
physical instability/divergence. Failed partial RMSE values cannot be selected.
The result shows improved pitch/wrist accuracy but unresolved coupled delay
sensitivity in yaw/elbow. No changes to those axes were made after seeing failures.

## Protection and scope

Of145attempts,7stop on exhausted stopping-envelope slack and5on post-step speed.
Four stopping events belong to pitch screening; wrist screening has3stopping
and1speed failure; validation has4speed failures. All failed records are retained.
Global soft/model-hard minima:0.21179860120574887/0.2617986012057489rad.
Global stopping slack:-0.019975967903626435rad belongs to REJECTED trajectories;
it is not a safe positive margin. No positional soft/model-hard contact was observed.
All29pre/post/final checks, extra0.05radreserve,20msreaction, assumed1rad/s^2braking,
original torque/velocity limits and final-hold0.02rad/0.1rad/s bounds are unchanged.
No qpos projection or accepted reference clipping. XML hard ranges are not measured
mechanical stops, and finite fixed-pelvis screening is not a real braking guarantee.

## Input, computation and verification

Reused one known1618-target outgoing episode,1373ACKrecords,27.453ssend and26.950s
sample clocks. It is not a new VR session, confirmed motor acceptance or measured
robot response. Ready posture,3swarmup and5sfinal hold are simulation additions.
The hold cannot dilute recording-segment RMSE.
Exact original lines950..3940 were exported to the PRIVATE repository; all target
arrays,clocks,events,sequences andACKcount match the source. No numeric rewriting.
OriginalSHA:2710d76445c3e004f811567b38f289e8451a47fb2960d43576b021a9e87f7871.
ExportSHA:4d5b4c3477c45cd25160dfd80dc08b3c318f7e37c4cb4df62277b1482464453f.
The full original PC log was not uploaded. Source provenance is beside the export.

The Windows formal start refused insufficient disk BEFORE output or integration.
No old logs were deleted and the2GBworker reserve stayed. Later free space recovered
without any cleanup in this workflow. Actual145cases ran in the isolated ChatGPT
Linux container:Python3.13.5,MuJoCo3.3.7,NumPy2.4.6,4workers,network disabled.
An initial portable import omitted the canonical joint tuple; b9c14d2 supplied
that existing module and its source hash. No numerical/dynamics change was made.
Running scriptSHA:f0a088befec023ba5c10f4f16ddd3771b0e1dbc16ceeabf9fe8387be05e9649d.

Dedicated28tests passed on Windows and again on isolated Linux after the packaging
fix. Hosted Linux run34704567847/job103582176999 onb9c14d2 passed **505/505tests,
zero skips/failures**, including C++ reference parity. Decoded log inspected,
842.073s,Python3.11.16,MuJoCo3.3.7,NumPy2.4.6,Ubuntu24.04.5. CItests are not145runs.
Automatic and separate audit-only both passed:145full-state traces,2,392,319all29
500Hzrows and4,205joint minima. Audits check original targets, applied gains,
PD/writer/filter equations, quality, source/model hashes, guard evidence and
selection. They do not independently reintegrate between sampled rows.
All260preexisting protected source/model/tool files and dirty live Git status
are unchanged. NoG1SSH,DDS/SDK,publisher,actuation,ARMdeployment,VR/IK/live gain
edit,model limit change orRobot/Allunblocking.

## Records and next permitted work

Code/manual:experiments/twist2_right_arm_manual/mujoco_pd_recorded_pitch_wrist.py
andMUJOCO_PD_PITCH_WRIST.md. GitHub compact result,CI,preservation receipts:
docs/validation/g1_pd_pitch_wrist_20260913/.
Full comparisonCSV,plans,metrics,failures,hashes and detailed report are attached
in G1_PD_PitchWrist_evidence_20260913.zip (204141bytes,29files), not all inGitHub.
All145rawNPZ/JSON and frozen sources are attached in
G1_PD_PitchWrist_20260913_full.zip (1898970936bytes,364files,CRCchecked),
SHA256:7de22496e7c970f3488d62bd467f67cc5329b6407fe24be40faa6160b890f3f3.
These archives are in this conversation sandbox, NOT copied to the PC Documents
folder or fully uploaded toGitHub. Compact archiveSHA is in result_receipt.json.
ComparisonCSV SHA:87f00b26602d6fc217554a2df8e085b8688f7e129f9bd3b461e0fb3d0e1eecc6.

Keep this non-selection and original failed unfiltered study intact. The next
separate contract should investigate yaw/elbow torque-delay interaction without
relaxing guards, then revalidate any new vector on declared prior conditions.
More recorded sessions,actual motor timing/noise/backlash/payload/thermal behavior
and free-base balance remain unverified. No globally or physically optimal PD
is claimed, and no new vector is approved for real deployment.
