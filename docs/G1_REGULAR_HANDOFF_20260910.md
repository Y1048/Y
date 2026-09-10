# G1 TWIST2 Regular handoff worktree handoff

## Current state

- The G1 is powered off for battery charging. Do not assume
  `192.168.123.164` is reachable.
- Do not start a DDS publisher or a motor-output program while continuing this
  handoff.
- `tools/START_TWIST2_MINK_CYCLE_CANDIDATE.ps1` blocks every `Robot` and `All`
  launch before SSH.
- The launcher hash is from the last confirmed build. A later `--clean-first`
  build lost SSH before completion, so the remote executable and hash must be
  checked again after the G1 reconnects.

## PD identification change

The large full-forward reach was rejected after the G1 showed a backward-fall
tendency during the first Kp 40 candidate. `--pd-sweep-trial` now moves only
right shoulder pitch joint 22 around the ready pose:

1. `ready -> +8 deg`
2. `+8 deg -> -8 deg`
3. `-8 deg -> ready`

It uses quintic smoothstep segments, a 20 deg/s velocity limit, a 60 deg/s^2
acceleration limit, and three cycles for each proximal Kp candidate 40, 48,
and 56 with Kd 5. The other 28 targets remain equal to the supplied baseline.
The old `--pd-reach-trial` implementation remains available in source but must
not be used for another physical run.

## Regular handoff candidate

FSM 500/501 is a verification value, not the mode-change command. The command
is `MotionSwitcherClient.SelectMode("ai")`.

The candidate sequence is:

1. Continue the final LowCmd position target.
2. Require joints 15..28 to stay within 0.1 rad position error and 0.1 rad/s
   measured speed for one second.
3. Stop and destroy the 500 Hz writer.
4. Call `SelectMode("ai")`.
5. Require `CheckMode == ai`, the captured starting FSM ID, and valid LowState
   for one continuous second.
6. Destroy the publisher and print `SHUTDOWN COMPLETE`.

If selection cannot be verified, LowCmd resumes only when `CheckMode` succeeds
and reports an empty service. If `ai`, another service, or an unknown result is
observed, LowCmd remains stopped to avoid overlapping owners and the process
continues monitoring instead of exiting.

`--handoff-only-trial` holds the initially measured 29 targets, performs the
one-second capture and four-second TWIST2 blend, then runs only this handoff.
It accepts no UDP input, arm trajectory, or PD gain override.

The settle check reads the mutex-protected `WriterFrame.target` snapshot. It
does not read the writer-owned `last_target_` concurrently.

## Verified locally

- Python control-flow regression tests: 10 passed.
- C++ tests passed for the PD option parser, small-signal trajectory, Regular
  handoff gate, and 10,000 concurrent WriterFrame publications/reads.
- These are offline/software checks and are not physical G1 safety validation.

## Next actions after the G1 reconnects

1. Read-only check for an existing `g1_twist2_mink_cycle_trial` process.
2. Inspect the remote source/build state left by the interrupted build.
3. Rebuild the ARM target only and record its SHA-256. Do not execute it.
4. Keep `Robot` and `All` blocked until the final binary and exact command are
   reviewed.
5. The first physical candidate is `--handoff-only-trial`; it has no intended
   arm motion. Treat any mode change, loss of support, unexpected sound, or
   movement as a failed physical test.

Do not reset or clean the wider working tree. It contains extensive unrelated
local work.
