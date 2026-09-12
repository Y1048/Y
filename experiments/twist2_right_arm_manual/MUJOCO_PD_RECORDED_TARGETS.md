# Recorded Mink target PD comparison (offline only)

This stage reads one explicit recorded cycle JSONL file. It does not capture live
VR, import the relay, create SDK/DDS channels, connect to G1, or deploy gains.
The previous VR launcher and hardware gain bounds remain unchanged.

## Input and interpretation

`send_attempt` is a PC-side outgoing target, NOT measured robot motion. ACK state
labels alone do not establish that a particular LowCmd was accepted or applied.
The parser extracts complete idle/active/release/return/idle target episodes,
requires contiguous sequence/source-clock data, and records every extraction
exclusion. It rejects missing returns, stale source data and malformed packets.
No scaling, smoothing, time stretching, IK rerun or target bias is applied.

The source clock and the PC-send clock are separate replay assumptions. Neither
is a measured motor arrival clock. Identical send timestamps retain original
order and the latest target is sampled by the50Hz reference loop. This is NOT
an emulation of the runtime protocol state machine or packet acceptance.

The fixed-pelvis model starts at the unchanged ready pose. Only recordings
beginning at that target are accepted by the dynamics. Initialization is not an
estimate of the robot's actual starting state. Warmup3s and final hold5s are
simulation additions, not part of the operator recording. Scores exclude both.

## Frozen candidates and conditions

Kp22..25=[100,300,64,100] and [100,300,72,100], both Kd=[1.4,4,1,1.4].
Other gains, including wrists, are unchanged. These research vectors are NOT
hardware-approved: rollKp300 exceeds the untouched live input cap100.

Each qualified episode sees two candidates, two replay clocks and the same six
nominal/half-timestep/heavy/delayed model conditions:24integrations per episode.
No candidate retuning or conditional deletion of failed cases is performed.
Data-derived episode selection never uses a candidate's resulting performance.

The new writer reproduces the captured today/yesterday speed profile. Original
writer torque/position equations are retained and yesterday parity is tested.
The inherited conservative1.5rad/s measured upper-joint velocity gate remains;
it is NOT the more permissive live-today wrist velocity allowance. A failure
of this offline gate must not be described as observed hardware instability.
All29inner-limit/stop-distance/pre-step/post-step/final-step guards remain.

Seven-axis RMSE is against ORIGINAL recorded targets, not rate-limited commands.
The whole last1s of the appended5s hold must satisfy all seven position errors
<=0.02rad and speeds<=0.1rad/s. The last100ms uses p2p<=0.005rad and RMS speed
<=0.05rad/s. Contacts, warnings, speed/limit violations or incomplete runs fail.
These are declared recorded-replay endpoint checks, not retrospective new
certification of older synthetic endpoint tests. No endpoint guarantees are
claimed at arbitrary unlabelled pauses in a human recording.

## Run

From the repository root using the existing isolated simulation environment:

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_recorded_study.py --recording "C:\path\to\cycle_packets.jsonl" --output "C:\path\to\new_result" --workers 4
```

Existing output is refused. Large logs (>32MiB), absent qualified episodes and
more than8episodes require a separately reviewed scope; they are not silently
trimmed. The command copies the original source into the NEW output, freezes
source/model hashes, saves all29states and normalized input indices, then audits.

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_recorded_study.py --output "C:\path\to\result" --audit-only
```

Audit recalculates target sampling, the applied PD equation and writer limiter,
all-seven metrics and final hold, all29guard evidence, sources and the exact
matrix. Original source JSONL is reparsed; altered evidence is refused. A
completed experiment may select NO candidate. That is not repaired by changing
limits or scoring a partial run. No command here starts the original live entry.


## Separate causal command-pipeline experiment

The unfiltered24cases were refused by the command governor at wrist pitch27;
these failed results are retained and never reclassified. A separate runner
connects each previous known50Hzgoal to the current known goal over20ms. No
future sample is used. Original ref stays unchanged and remains the score target.
This adds command lag and constitutes a DIFFERENT pipeline, not PD-only proof.

Run mujoco_pd_recorded_ramp_study.py with the same --recording/--output/--workers
arguments, using a different new output directory. Audit with that runner and
--audit-only. The saved writer_reference exposes the causal relation explicitly.

The exploratory24case comparison completed22cases; two delay-boundary PC-send
clock cases stopped at the unchanged1.5rad/s observed-speed threshold on yaw24.
No vector passes the entire declared matrix. Do not weaken bounds, deploy gains,
or claim the original controller passed. Full results are in the dated report.
