# Recorded seven-joint target PD validation — 2026-09-12

Base: `f5672cdd28ddc93cc0e89a98f1af6169b7763f09`.
Implementation: `5398312463bcd29864b20bb7859d406e1c020a91`.
This is an offline input/pipeline experiment, NOT a deployable G1 gain setting.

## 1. What was actually tested

The prior synthetic experiments did not exercise a recorded seven-joint target
stream. This step reads one explicit PC-side cycle log:
`cycle_packets_20260910_150530_0603774.jsonl`.
Raw SHA256: `2710d76445c3e004f811567b38f289e8451a47fb2960d43576b021a9e87f7871`.
The file contains 17,338 send_attempt and 14,781 ACK records (11,640,237 bytes).

One complete idle -> active -> pinch -> return -> idle target episode was found:
lines 950..3940, **1,618 targets**, PC-send duration **27.453 s**, source-sample
clock duration **26.950 s**. The episode has 1,373 ACK records inside, but neither
ACK state labels nor send_attempts establish actual LowCmd application or motor
response. No measured robot trajectory or starting state is available here.
A bulk multi-log analysis was not completed; this report does not claim coverage
of every PC log or operator session. No new live recording was started.

| Joint | Recorded target excursion, degrees |
|---|---:|
| 22 shoulder pitch | 26.930964 |
| 23 shoulder roll | 18.334684 |
| 24 shoulder yaw | 5.750205 |
| 25 elbow | 44.324986 |
| 26 wrist roll | 12.662875 |
| 27 wrist pitch | 26.350645 |
| 28 wrist yaw | 3.791243 |

All seven recorded goals are preserved, without range scaling, smoothing the
score reference, time stretching, or rerunning IK. Two clock interpretations
are tested: original source sample times and PC-send monotonic timestamps.
Neither is a measured motor arrival clock. Three duplicate send timestamps
retain packet ordering and use the latest recorded goal when sampled. This is
zero-order-held target replay, NOT the runtime protocol or acceptance state machine.

The model starts at the unchanged ready posture, then uses 3 s warmup. A 5 s
final hold is explicitly appended. Both are simulation additions. Tracking RMSE
uses only the recorded segment; the appended hold cannot dilute the score.

## 2. Two separate pipelines, no fully passing vector

Frozen candidates, for joints 22..25:

- Kp `[100, 300, 64, 100]`, Kd `[1.4, 4, 1, 1.4]`.
- Kp `[100, 300, 72, 100]`, Kd `[1.4, 4, 1, 1.4]`.

Other gains, including the wrists, are unchanged. No gain retuning was performed.
Each pipeline executes the same two candidates x two clocks x six nominal/model-
uncertainty conditions = **24 integrations**. One original episode is reused;
this is not 24 distinct recordings. All declared cells are attempted, no pruning.

| Pipeline | Attempted | Trajectories completed | All criteria passed | Refused |
|---|---:|---:|---:|---:|
| Direct recorded target / original command construction | 24 | 0 | 0 | 24 |
| Separate causal 20 ms nominal-command interpolation | 24 | 22 | 22 | 2 |
| **Total actual new integrations** | **48** | **22** | **22** | **26** |

| Yaw Kp/Kd | Direct replay passes | Causal-command passes | Fully passing candidate |
|---|---:|---:|---|
| 64/1 | 0/12 | 11/12 | No |
| 72/1 | 0/12 | 11/12 | No |

A processing exit 0 means the experiment and evidence audit completed. It does
NOT mean all simulated trajectories succeeded. No candidate is selected in
this stage. Small partial-run RMSE values are diagnostic only, not eligible
scores. Previous synthetic passes remain historical evidence for their actual
conditions; they are not erased or extended to this recorded input.

## 3. Direct replay diagnosis: command slope, not measured limit contact

All 24 direct cases stop on `joint_limit_command_intervention`, **joint 27**,
after 0.58 s of PC-send-clock input or 0.60 s of source-clock input. This is the
unchanged stopping-envelope command governor refusing a proposed command step.

Nominal PC-send case (yaw64):

| Observation at refusal | Value |
|---|---:|
| Proposed command change / 2 ms | 2.260210549 rad/s |
| Maximum permitted command slope there | 1.669672307 rad/s |
| Actual simulated wrist speed | 0.071067536 rad/s |
| Actual wrist position | 0.018331422 rad |
| Actual wrist soft-limit clearance | 1.546098136 rad |

The proposed target is far from the positional boundary, and actual joint speed
is much smaller than the implied command slope. A 50 Hz target step consumed by
the today-profile writer can produce a steep 2 ms command change. The governor's
reaction time 20 ms, assumed braking 1 rad/s^2 and outward acceleration 2 rad/s^2
are conservative software assumptions, NOT identified G1 braking parameters.
Do not call this an observed physical hard/soft contact or proven PD instability.
The readback diagnosis for every direct case is retained separately.

## 4. Causal-command comparison: 22 pass, two delayed yaw failures

After diagnosing the direct failure, a separate exploratory implementation
linearly connects each previous known 50 Hz goal to the current known goal over
the next 20 ms. It uses no future sample. All original goals remain in `ref`;
`writer_reference` separately records the interpolated command input. Scores
continue to use original `ref`. The filter adds command lag and changes the
pipeline; it cannot certify bare PD gains or the unchanged live controller.

This stage reused the SAME original bytes and declared model/clock matrix.
It is exploratory reuse of observed data, not an independent new holdout. Guards,
torque limits, measured-speed threshold, state integration and acceptance values
were not weakened to rescue the direct cases. The direct results stay untouched.

Both candidates pass all six source-clock cases and five of six PC-send-clock
cases. Both remaining failures are the PC-send `delay_boundary` condition:
right-arm mass/inertia 1.35x, passive damping 0.85x, friction 0.15x, torque-path
pure delay 4 ms, first-order lag 8 ms, physics timestep 0.5 ms.
These are hypothetical uncertainties, not measured G1 motor characteristics.

| Yaw candidate | Fastest failing axis | Integrated speed | Simulated time incl. 3 s warmup |
|---|---:|---:|---:|
| 64/1 | 24 | 1.505838153 rad/s | 9.1165 s |
| 72/1 | 24 | 1.515688782 rad/s | 8.7590 s |

The unchanged conservative upper-joint measured-speed threshold is 1.5 rad/s.
This is stricter than the actual live-today velocity allowance; crossing this
offline bound does not by itself prove physical instability or divergence.
Neither filtered vector passes all 12 cells, so neither has a selectable score.
No final PD value or deployable command filter is produced.

The22completed filtered cases had maximum final all-seven error0.010229506683rad
and final speed0.000000265112rad/s; recorded torque-limiting/clipping ratios were
zero. This is a description of the completed cohort ONLY, not a replacement for
the two failures or evidence of an all-condition winner.

## 5. Safety, timing and scoring contract

The new replay follows the captured `today` writer speed profile (proximal
pi/2 rad/s, wrists pi rad/s) while retaining existing torque/position equations.
Yesterday-profile parity and the existing C++ today constants are tested. Old
simulation and live files are unchanged. All 29 state guards, 0.05 rad extra
inner reserve, pre/post/final-step checking, contact and warning checks remain.
No qpos projection, compensating target offset, gravity compensation, integral
term, desired-velocity feedforward or relaxed original limits were introduced.

All seven final position errors must be <=0.02 rad and speeds <=0.1 rad/s over
the whole last 1 s of the explicitly appended hold. Last 100 ms position variation
must be <=0.005 rad and speed RMS <=0.05 rad/s for all seven right-arm joints.
Moving human targets are not falsely called residual oscillation. Arbitrary
unlabelled pauses during the original recording are not claimed as certified
endpoint windows. Original-goal RMSE and final-hold errors are separately stored.

| Observed minimum over all 29 joints | Direct | Causal-command |
|---|---:|---:|
| Soft-limit clearance (rad) | 0.211798903883 | 0.211798601206 |
| Model hard-limit clearance (rad) | 0.261798903883 | 0.261798601206 |
| Measured stopping-envelope slack (rad) | 0.160598895957 | 0.160598601206 |

Direct replay has 24 command-refusal events, not state-limit contacts. The causal
comparison has zero joint-envelope events, but two measured-speed rejections.
Reported model ranges are not measured mechanical stops; no absolute hardware
braking, no-contact, continuous-time or full-body stability guarantee follows.
Research roll Kp300 still exceeds the unchanged live-code Kp100 input bound.

## 6. Verification and retained evidence

Dedicated tests passed: **42/42 direct + 13/13 causal-command**. The first direct
test run had two errors: a local/global wrist-column index in a fixture and a
NumPy real scalar rejected by the replay time API. The fixture index was corrected;
finite Real times are accepted while booleans and nonfinite values remain rejected.
Strict JSON input numeric checks and formal conditions/thresholds were unchanged.
A later documentation REPL block termination error did not change dynamics or data.

Full Windows regression: **453 discovered, 452 passed, one preexisting C++
compiler-dependent skip, zero failures/errors**. Test fixtures are generated
examples, not actual operator input, and are never counted as formal integrations.
Hosted Linux run **34696117419**, job **103559778760**, on implementation
**5398312** passed **453/453 tests with zero skips**, including C++ reference
parity. Decoded logs were inspected (635.614 s). Hosted tests use Python3.11.16,
MuJoCo3.3.7 and NumPy2.4.6 on Ubuntu24.04.5. Formal48replay experiments ran in
the isolated Windows environment; CI fixtures do not count as formal recordings.

Both automatic full audits and separate audit-only CLI executions passed. They
reparsed the original recording and reread **439,000 full29 rows at 500 Hz** and
**1,392 joint extrema records**, verifying frozen plans, original goal indices,
clock sampling, applied gains, PD equations, writer equations, causal relation,
all-seven metrics and guard evidence. Raw input/manifests/plans/summaries stayed
byte-identical across readback. This is not an independent reconstruction of the
continuous trajectory between logged samples or a measured robot-response audit.

All 438 preexisting protected experiment/runtime/model files match their initial
hashes. The original dirty VR worktree Git status is unchanged. No G1 SSH,
SDK/DDS creation, publisher/subscriber, actuation, ARM deployment, real-gain,
IK damp/cost, model change or Robot/All unblocking occurred.

Compact evidence: `docs/validation/g1_pd_recorded_20260912/`.
Usage: `experiments/twist2_right_arm_manual/MUJOCO_PD_RECORDED_TARGETS.md`.

Raw PC output directories:

```text
C:\Users\user\Documents\G1_PD_RecordedTargets_20260912
C:\Users\user\Documents\G1_PD_RecordedRamp_20260912
```

Raw source JSONL and full NPZ streams remain on PC, not in GitHub. Exact raw-byte
inventories are retained; copied repository text may have Git newline normalization.
Direct CSV SHA256: `710b9435f3daf472ed57be6835dc80712fe6710d5e34ed1b01fd25beb3c85024`.
Causal CSV SHA256: `c47312ce4fdc8aab8e9e0494772732bd642481dae1530ec3ef81732db3a61772`.

## Next permitted offline work

Use these failures to separate command-timing construction from yaw gain tuning.
Keep the raw rejected dataset and conservative safety assumptions unchanged;
compare any new yaw candidate under an explicitly chosen pipeline, then repeat
prior synthetic/individual conditions for the changed vector. Do not treat a
prefiltered pass as bare-PD or existing-VR approval. More recorded sessions,
actual packet acceptance semantics, true actuator constraints, payload/noise/
thermal/backlash and free-base balance remain unverified before physical use.
