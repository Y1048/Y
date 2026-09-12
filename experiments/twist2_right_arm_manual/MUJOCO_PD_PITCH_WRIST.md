# Recorded-pipeline pitch and wrist PD search

This is an OFFLINE research runner. Never copy its gains into the G1 launcher.
The original causal 20 ms command interpolation, score reference, all 29 joint
limits and stopping guards are fixed. No IK, gravity compensation or live edit.

## Search and evidence

The baseline is proximal Kp [100,300,64,100], Kd [1.4,3,1.2,1.4], wrist27 20/1.
Only pitch22 and wrist27 change. A process-local adapter permits pitch22 Kp up
to160 and wrist27 up to40; the original hardware cap100 and old files stay intact.
Pitch search: Kp80/100/120/140/160 x Kd1/1.4/2, three known conditions each.
Wrist search at the best all-pass pitch: Kp15/20/30/40 x Kd0.6/1/1.4, same cells.
Up to four finalists include the original baseline. Each sees both source clocks,
six known models and two new declared model mixtures. All recorded survivors see
14 known single/simultaneous/independent synthetic regressions using the original
synthetic command generation (without the recorded-input prefilter). These are
separate checks, not certification that an unchanged live pipeline passes.
Every executed cell retains full29 float64 traces, including failed trajectories.
A failed low-RMSE case cannot win. No prior gain vector passes are inherited.

## Run

Use the isolated MuJoCo3.3.7 environment described in mujoco_pd_requirements.txt.
From the repository root:

```bash
python -B experiments/twist2_right_arm_manual/mujoco_pd_recorded_pitch_wrist.py --recording experiments/twist2_right_arm_manual/data/pitch_wrist_episode_20260910.jsonl --output /absolute/new/pitch_wrist_run --workers 4
python -B experiments/twist2_right_arm_manual/mujoco_pd_recorded_pitch_wrist.py --output /absolute/new/pitch_wrist_run --audit-only
```

No output overwrite. Workers1..4 only. At least4.5GB free for formal startup;
workers preserve a2GB free-space reserve. Insufficient storage is an error, not
a completed study. The compute-bundle workflow provides only the simulation
sources, model and Python3.13 Linux wheels for isolated environments without
network access. It does not execute any robot program.

## Input provenance

The versioned JSONL is exactly original lines950..3940 of the previously used
cycle log, including the same1618outgoing targets and1373ACKrecords. No numeric
rewriting, smoothing or time stretching. The source/provenance JSON records the
full original and exported hashes. Before transfer all target arrays, clocks,
events and sequence numbers were compared and found identical. The full PC log
is not uploaded; metadata line numbers and file SHA differ for this exact slice.
This is one known operator episode, NOT new data or measured robot response.
The included session identifier is protocol bookkeeping, not a secret relay token.

Outputs are simulation-only. Research gains above100 remain incompatible with
the unchanged live input validator. Remaining validation includes other sessions,
full historical regressions, real motor noise/backlash/thermal/braking and free-base
balance. A finite coordinate-search result is not a global optimum.
