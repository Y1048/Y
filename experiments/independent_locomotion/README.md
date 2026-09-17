# Independent G1 locomotion setup

## Current state (2026-09-15)

- GPU measured on Windows and WSL: RTX 5070 Laptop, 8151 MiB dedicated VRAM.
- Windows driver: 610.62. Windows C: free space was about 103.7 GB decimal.
  The WSL virtual filesystem advertises more space than the backing Windows
  disk; use the Windows free-space value when planning downloads.
- Existing WSL virtual environments: `g1-teleop`, `twist2-vr-build`. A separate
  environment is being created under the new source checkout below.
- Isaac Sim current official minimum is 16 GB VRAM, so the initial local
  training candidate changes from Isaac Lab to **mjlab (MuJoCo-Warp)**.
  This is a feasibility choice, not evidence that 8 GB will train our final task.
- Source: https://github.com/mujocolab/mjlab
- Pinned commit: `8ee51fbcf806a7419189f706d9e394cbeb7790fa`, package 1.6.0.
- WSL checkout: `/home/user/g1-learning/mjlab-20260915`.
- Install: `uv sync --python 3.12 --extra cu128 --no-dev --locked`.
- The pinned environment is installed and the CUDA runtime check passed.

Upstream source is Apache-2.0 with separately licensed portions. CUDA/PyTorch,
bundled robot models, RL dependencies and delivery requirements must be included
in the eventual license inventory. HOMIE code/configs/checkpoints are not used.

## Verification

From Windows PowerShell:

```powershell
wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/experiments/independent_locomotion/verify_mjlab.sh
```

The script synchronizes the pinned environment, lists tasks, creates four G1
GPU environments and takes 50 zero-action steps, then runs two PPO iterations
on 16 environments with local TensorBoard logging. No WandB upload is requested.
The smoke script checks finite observations/rewards. Zero actions may lead to
falls/resets in simulation: this tests runtime functionality, not balancing.

Each execution creates a new `logs/test_results/mjlab_setup_<UTC>/` directory.
`smoke.json` proves the smoke test completed. `SETUP_CHECK_COMPLETE` in
`console.log` proves both stages exited successfully. Their absence is not a pass.
Any two-iteration checkpoint is only a generated pipeline fixture, not a trained
walking controller, and must never be used on G1.

The completed base-runtime evidence is under
`logs/test_results/mjlab_setup_20260915T060836Z/`. It includes four G1
environments stepped for 50 zero-action steps and a 16-environment, two-iteration
PPO pipeline check.

## Upper-body-conditioned task skeleton

`upper_body_conditioned_env.py` derives a local task from the upstream flat G1
configuration. The policy action contains exactly the 12 leg joints. Seventeen
waist/arm target positions are generated separately and added to actor and critic
observations. This first fixture uses bounded deterministic sine targets; it is
not yet the final Mink target distribution.

Run both the structural and PPO pipeline checks from PowerShell:

```powershell
wsl -d Ubuntu -- bash /mnt/c/Users/user/Desktop/G1_Teleop_Project/experiments/independent_locomotion/verify_upper_body_conditioned.sh
```

The completed evidence is under
`logs/test_results/mjlab_upper_conditioned_20260915T062006Z/`:

- `environment_smoke.json`: 4 environments, 100 steps, 12 leg actions, 17 upper
  targets, finite observations/rewards.
- `training_smoke.json`: 16 environments, 2 PPO iterations, local TensorBoard,
  and two generated checkpoints.
- `COMPLETE`: completion marker written only after both checks succeed.

The environment smoke reset all four environments and the two-iteration run also
reported falls. That is expected from an untrained actor and is direct evidence
that these generated checkpoints are pipeline fixtures, not walking policies.
They must not be deployed to G1.

## Frozen trajectory split and evaluation gate

`prepare_mink_trajectory_split.py` converts seven existing PC-side Mink command
sessions into a versioned bank. Five complete source sessions are assigned to
training and two different sessions to validation. The split operates at source
file/session level and checks source SHA-256 values, so fragments of one session
cannot appear in both sets. Values are right-arm command offsets from the first
active sample. They are neither measured G1 motion nor bilateral arm recordings.

The manifest is `data/mink_command_trajectories_v1.json`; its compressed numeric
data is adjacent as `.npz`. `evaluation_protocol_v1.json` freezes the held-out
seeds, command grid, metrics and initial research thresholds before a trained
candidate is evaluated. Changing a candidate after inspecting validation makes
that validation consumed and requires a new held-out set.

The combined verifier now replays only validation trajectories in the structural
environment test and only train trajectories in the PPO pipeline test. Dataset
tests reject content overlap and nonfinite samples.

`evaluate_upper_body_conditioned.py` is the checkpoint evaluation entrypoint.
It fixes each velocity command at every step, stops accumulating an episode at
its first fall, and reports velocity RMSE, maximum roll/pitch magnitude and foot
slip. It snapshots all actor parameters and observation-normalizer buffers before
and after inference and rejects mutation. `--steps` and `--max-seeds` are only
pipeline-smoke overrides; their presence marks the result
`protocol_compliant=false`.

The first evaluator smoke result is
`logs/test_results/mjlab_upper_conditioned_eval_smoke_20260915.json`. It used one
seed and 50 steps, loaded the generated two-iteration fixture, and verified that
weights and normalizers remained unchanged. Its zero falls over only one second
is not a walking result and cannot be compared against the frozen 20-second gate.

## Matched stage-1 training

`run_matched_training_stage1.sh` completed fixed-upper and recorded-upper models
with the frozen settings in `matched_training_stage1.json`: seed 1509, 256
environments, 500 iterations and 3,072,000 train samples per model. It did not
read or run the validation split. Results and checkpoints are under
`logs/test_results/mjlab_matched_stage1_20260915/`.

The last 50 train iterations are summarized in `train_summary.json`. Fixed-upper
mean episode length was 185.84 steps (3.72 s); recorded-upper was 121.87 steps
(2.44 s). Recorded-upper had lower train velocity-error and foot-slip log values,
but shorter episodes and a higher `fell_over` log value. The latter is an mjlab
episode log scalar, not a normalized validation fall rate. Neither model is ready
for the frozen 20 s validation gate, and no model-selection decision was made.

## Next work

1. Continue both models with equal train-only budgets until training survival and
   reward stop improving; preserve matched seeds and checkpoints.
2. Run the final baseline and conditioned candidate exactly once under the
   complete frozen validation protocol with matched seeds, commands and
   disturbances. Do not select from validation episodes.
3. Export or deploy only after a separately reviewed simulation result; the
   current generated checkpoints are explicitly excluded.

No SDK/DDS, physical robot connection, publisher, or actuator command is in these
setup scripts. Live launchers and existing control files are untouched.

Sources checked:
- https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html
- https://github.com/mujocolab/mjlab/blob/main/README.md
- https://github.com/mujocolab/mjlab/blob/main/LICENSE
## Continue the matched training yourself

Double-click `tools\START_MJLAB_MATCHED_CONTINUATION.bat` from Windows. It
resumes both stage-1 `model_499.pt` checkpoints in order: fixed upper body first,
then recorded Mink upper body. The default is 500 additional PPO iterations per
model. To choose another amount, run this from PowerShell at the repository root:

```powershell
.\tools\START_MJLAB_MATCHED_CONTINUATION.bat 1000
```

The continuation selects the newest fully completed continuation for each mode,
falling back to stage-1 only when no completed continuation exists. Interrupted
or malformed runs are ignored. It creates a new timestamped directory and copies
each source checkpoint before resuming, so earlier artifacts are not overwritten. The
policy, critic, optimizer, observation normalizers, and iteration state are
restored from the checkpoint. Keep the training window open until it prints
`[COMPLETE]`; closing it interrupts the current run.

To inspect the latest phase and recent console output, double-click or run:

```powershell
.\tools\CHECK_MJLAB_MATCHED_TRAINING.bat
```

This path is simulation-only. It does not initialize the G1 SDK or DDS and does
not create a publisher or motor output. A completed continuation is still not a
G1-deployable policy; held-out validation remains a separate step.

## Recorded-upper curriculum

After unchanged full-amplitude replay plateaued, use the separate curriculum
launcher:

```powershell
.\tools\START_MJLAB_RECORDED_CURRICULUM.bat
```

The default run gives both models another 1,000 train iterations. Fixed-upper
continues unchanged. Recorded-upper starts at 25% of the frozen train trajectory
offset, reaches 100% over 800 iterations, and then trains for 200 iterations at
full amplitude. The target observation contains the same scaled target sent to
the simulated upper joints. Validation remains unread during this run.

Optional total and ramp iteration arguments are:

```powershell
.\tools\START_MJLAB_RECORDED_CURRICULUM.bat 1000 800
```
