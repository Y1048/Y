# G1 right-arm hardware bring-up checklist

This checklist is the required progression from offline development to physical G1 control.
Do not skip a gate. A failed gate returns the system to a non-commanding state.

## Gate 0 — Windows / WSL2 platform

- [ ] Windows repair/update has completed without a pending-reboot loop.
- [ ] `wsl --status` reports WSL2 available.
- [ ] `vmcompute` and `hns` are present/running as required by WSL2 networking.
- [ ] WSL2 Ubuntu starts normally.
- [ ] The Ethernet adapter dedicated to G1 is visible and has the intended network configuration.

**Command authority:** NONE.

## Gate 1 — Unitree SDK2 read-only LowState

Run only `read_only_lowstate.py` first.

- [x] `unitree_sdk2py` imports successfully in WSL2.
- [x] Correct G1-facing network interface selected.
- [x] `rt/lowstate` packets are received continuously.
- [x] Runtime phase becomes `READ_ONLY_ACTIVE`.
- [x] `publisher_present` is `false`.
- [x] `command_output_enabled` is `false`.
- [x] Packet age remains comfortably below the configured timeout.
- [x] Stopping/disconnecting LowState produces `FAULT / LOWSTATE_TIMEOUT` after traffic has started.

Status file: `logs/runtime/g1_hardware_lowstate.json`

**Command authority:** NONE.

## Gate 2 — Right-arm joint mapping sanity

Use Unitree's official G1 7-DoF arm mapping for indices 22-28. The elbow and
wrist-roll indices were additionally spot-checked by small manual motions while
the robot was suspended.

- [x] 22 = right shoulder pitch (official SDK mapping).
- [x] 23 = right shoulder roll (official SDK mapping).
- [x] 24 = right shoulder yaw (official SDK mapping).
- [x] 25 = right elbow.
- [x] 26 = right wrist roll.
- [x] 27 = right wrist pitch (official SDK mapping).
- [x] 28 = right wrist yaw (official SDK mapping).
- [x] Model and hardware use the same official joint-coordinate convention.
- [ ] No unexpected discontinuities, NaN/Inf values, or implausible velocities appear.

**Command authority:** NONE.

## Gate 3 — Initial pose synchronization

Forward read-only telemetry to Windows UDP 5007 and run the hardware-sync launcher.

- [x] Fresh seven-joint snapshot received from G1.
- [x] `g1_hardware_initial_state.json` contains the same measured joint vector.
- [x] Mink initializes from measured G1 `q`, not the fallback ready pose.
- [x] Unity avatar initializes to the same seven measured joint angles.
- [ ] No visible target jump occurs when the teleop clutch first becomes active.

An arm-down or abnormal captured pose may begin inside conservative Mink
collision geometry. Preserve it exactly during read-only sync/HOLD. Such a pose
must use the separately validated collision-aware transition; direct joint
interpolation is not approved. A firmware Regular pose may bypass that
transition only when the read-only startup precheck below passes in the same
session.

- [x] Offline Mink startup recovery reaches the configured ready pose from the captured rest pose.
- [x] Recovery solves contact release and ready-posture convergence concurrently.
- [x] Every accepted recovery step passes a 0.001-degree startup swept-path check.
- [x] Safety Gate accepts the offline samples and rejects stale LowState.
- [x] Velocity, acceleration, and jerk limits are implemented and pass offline replay.
- [ ] Velocity, acceleration, and jerk limits are approved for hardware.
- [ ] Startup recovery is repeatable from multiple real rest-pose captures.

Latest offline result: 3.828 s at 500 Hz, zero final ready-pose error,
7.528 deg/s maximum velocity, 30.000 deg/s^2 maximum acceleration, and
300.000 deg/s^3 maximum jerk, with 20.417 mm final model clearance. The complete 1,915-sample replay passed the
0.001-degree startup swept-path validation and Safety Gate. This remains
offline evidence and does not authorize a motor command.

**Command authority:** NONE.

### Gate 3A — Conditional Regular-pose recovery bypass

Run `tools/CHECK_G1_TELEOP_STARTUP.bat` immediately before initial sync.

- [x] MotionSwitcher `CheckMode()` read-only query succeeds without calling
  `SelectMode()` or `ReleaseMode()`.
- [x] Operator-confirmed Regular Mode signature is pinned as `form=0, name=ai`
  for the current G1/firmware; `mode_machine=5` is not used as the
  Regular/Damping selector.
- [x] At least 20 fresh UDP packets are observed over one second.
- [x] Gate 5 accepts every measured-pose HOLD sample.
- [x] Right-arm pose span remains below 0.5 degrees and velocity p95 remains
  below 3.0 deg/s.
- [x] The hardware precheck collision model uses all 29 measured joint
  positions, checks collision pairs involving either arm, and reports at least
  12 mm clearance.
- [x] Latest physical run returned `DIRECT_TELEOP_READY` with 27.76 mm minimum
  dual-arm clearance and no robot command.

Any mismatch produces `REGULAR_MODE_REQUIRED`, `WAIT_AND_RETRY`,
`RECOVERY_REQUIRED`, or `STARTUP_BLOCKED`; it does not silently learn a new
mode signature. `DIRECT_TELEOP_READY` only permits skipping Startup Recovery.
It does not grant command authority or skip Gates 4–6.

Result: `logs/runtime/g1_startup_precheck.json`

**Command authority:** NONE.

## Gate 4 — Safety Gate validation

Required offline tests must remain green before any command-capable process is introduced.

- [ ] `TEST_G1_HARDWARE_SAFETY_GATE.bat` passes.
- [ ] `TEST_G1_HOLD_DRY_RUN.bat` passes.
- [ ] `TEST_MINK_SAFETY_PIPELINE.bat` passes.
- [ ] `TEST_FAKE_MINK_SAFETY_E2E.bat` passes.
- [ ] `TEST_G1_HARDWARE_STATE.bat` passes.
- [ ] LowState timeout remains 250 ms at the Safety Gate.
- [ ] Joint safety margin remains 2 degrees.
- [ ] Target-to-measured maximum error remains 10 degrees.
- [ ] Command candidate rate remains limited to 15 deg/s per joint.
- [ ] Every denied decision returns no command vector.

**Command authority:** NONE.

## Gate 5 — Real LowState through Safety Gate, still no publisher

Use actual measured G1 state as the Safety Gate measurement source while the requested target is the measured pose itself.

Implementation and offline regression are ready:

- [x] `gate5_lowstate_safety_monitor.py` imports no Unitree SDK and creates no DDS publisher.
- [x] UDP telemetry carries a schema, bridge session ID, increasing sequence, source timestamp, measured `q`, and measured `dq`.
- [x] `TEST_G1_GATE5_READ_ONLY.bat` accepts a fresh measured-pose HOLD candidate and produces no candidate after a synthetic 250 ms heartbeat loss.

Physical-G1 verification (run `START_G1_GATE5_READ_ONLY.bat`):

- [ ] Gate accepts a stationary measured-pose HOLD candidate.
- [ ] Real LowState heartbeat loss causes immediate fail-closed denial.
- [ ] Measured joints remain inside safety-margin limits.
- [ ] Logs clearly show phase, packet age, fault code, measured q and candidate q.
- [ ] No Unitree command DDS publisher exists in the process.

Status: `logs/runtime/g1_gate5_lowstate_safety.json`

Append-only events: `logs/runtime/g1_gate5_lowstate_safety.jsonl`

**Command authority:** NONE.

## Gate 6 — Command-capable HOLD (implemented, output locked)

The command boundary exists, but repository config deliberately blocks physical
output. `TEST_G1_GATE6_HOLD_OFFLINE.bat` and `PREPARE_G1_GATE6_HOLD.bat` are the
only approved Gate 6 launchers at this checkpoint.

Implementation and no-output verification:

- [x] Command process defaults to read-only preparation with no publisher.
- [x] Both arms 15–28 are seeded exactly from fresh measured `q` because the
  Arm SDK blend weight applies to the dual-arm command.
- [x] Waist 12–14 and lower-body joints are excluded from the dynamic target
  set and have command mode/gains equal to zero.
- [x] Stale LowState, invalid target, physical arm-limit violation, target
  error, mode mismatch, or internal exception stops command production.
- [x] Normal 3 s acquire / 3 s HOLD / 3 s release lifecycle ends with repeated
  zero-weight frames.
- [x] Actual installed Unitree SDK2 accepts the 35-slot HG `LowCmd_` layout and
  produces a CRC without creating ChannelFactory or a DDS publisher.
- [x] Hardware-output arguments are blocked while
  `hardware_output_authorized=false`; the blocked result records no publisher
  and zero published frames.
- [x] Connected-G1 read-only preparation returned `HOLD_READY` with 840 settle
  samples and 2.72 deg/s maximum dual-arm velocity. This observation was made
  while the G1 was suspended, so it verifies DDS reception and the HOLD
  contract only; it is not physical Regular-Mode output approval.

Before enabling a physical publisher:

- [x] Gates 0–5 have passed on the physical G1 in the same session/configuration.
- [x] A new `DIRECT_TELEOP_READY` startup precheck is less than 60 seconds old.
- [x] G1 is standing with both feet on a level floor and balancing in confirmed
  Regular Mode. It is not suspended and no support strap is carrying its weight.
- [x] Physical test area is clear and an operator can immediately stop robot operation.
- [x] Lower-body operator confirms no overlapping arm/waist command writer.
- [x] `maximum_weight=0.2`, gains, and the expected firmware signature are reviewed.
- [x] The user explicitly approves one-time hardware output authorization.
- [x] Both hardware confirmation phrases are supplied: command authorization and
  grounded-Regular operator confirmation.
- [x] Limited measured-pose HOLD completes acquire, hold, and release while G1
  is standing and balancing in Regular Mode.
- [x] Operator confirms that the physical robot showed no visible arm jump or
  balance disturbance during the completed HOLD.
- [x] Operator confirms that no abnormal sound occurred during the completed HOLD.
- [x] Output interruption behavior is observed and documented before live Mink targets.

The dedicated interruption path is prepared but has not been run physically:

- [x] `TEST_G1_GATE6_INTERRUPT_RELEASE_OFFLINE.bat` verifies a deterministic
  `0.2 -> 0` release over 2 seconds followed by 25 zero-weight frames.
- [x] Its separate config remains locked with
  `hardware_output_authorized=false` and the offline path creates no SDK, DDS
  entity, publisher, or robot command.
- [x] With separate explicit approval, run
  `START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat` on grounded Regular Mode and press
  Ctrl+C only after weight reaches 0.2.
- [x] The software completed the 2-second release with final weight zero,
  `publisher_present=false`, no fault, and 1,883 published frames.
- [x] Operator confirmed natural Regular control return with no arm movement or
  jump, no abnormal sound, and no balance disturbance.

Only after the limited HOLD is independently validated may the project proceed
to live Mink teleoperation.

## Gate 7 — Live-target contract (offline only, output locked)

- [x] UDP 5008 packet has strict schema, sequence and original input cause.
- [x] Active samples update only the right arm while both-arm Arm SDK slots are seeded.
- [x] An active-to-`pinch_disengaged` edge starts immediate Regular-pose return.
- [x] Tracking loss, stale input, workspace exit and collision violation hold the measured pose for up to 10 seconds.
- [x] Persistent unintended disengagement starts the same validated return after 10 seconds; active recovery cancels the timer.
- [x] Return uses velocity, acceleration and jerk bounded minimum-jerk motion.
- [x] Every return sample is checked against the active MuJoCo/Mink collision pair set.
- [x] Waist and lower-body command mode/gains remain zero in every candidate frame.
- [x] Offline regression creates no Unitree SDK, DDS entity, publisher or robot command.
- [ ] Run `START_G1_GATE7_LOWSTATE_DRY_RUN.bat` with a connected G1 and verify that live LowState replaces the shadow measured feedback at every command tick.
- [x] Publisher interruption and weight-release behavior passed a dedicated grounded test.
- [ ] Verify that the handheld remote retains emergency-stop and mode-transition authority during every live test.
- [ ] The user must explicitly authorize a separate first live-target experiment.

Prepared first-live profile, still locked:

- [x] Standard Gate 7 profile remains unchanged at weight 0.2 and 40/100 deg/s.
- [x] Separate first-live profile uses weight 1.0, 10/25 deg/s velocity,
  20/50 deg/s2 acceleration, 80/200 deg/s3 jerk and a 20-second limit.
- [x] Initial instantaneous arm-velocity rejection is 5 deg/s, matching the
  physically completed Gate 6 HOLD/interruption profile; the separate startup
  p95 stability gate remains 3 deg/s.
- [x] All 14 arm command joints are limited to 3 degrees from the measured
  publisher-acquisition pose, checked before every `publisher.Write`.
- [x] Boundary tests accept 3.00 degrees and reject 3.01 degrees with
  `start_pose_excursion_limit`.
- [x] The profile-specific UDP virtual E2E passed with no Unitree SDK, DDS
  entity, publisher or robot command.
- [x] `START_G1_GATE7_FIRST_LIVE_TRIAL.bat` was verified to stop at the false
  authorization lock before WSL or DDS startup.
- [ ] Review the exact first-live limits and obtain explicit one-run approval
  before changing either authorization lock.

**Command authority:** NONE. `hardware_output_authorized=false`.

## Bounded right-elbow publish experiment

- [x] Right-elbow hardware index is fixed to `25`.
- [x] Requested range is clamped to ±5 degrees from measured startup pose.
- [x] Commanded elbow target is limited to 5 deg/s and 30 seconds.
- [x] Remaining 13 arm targets are seeded from fresh measured LowState.
- [x] Waist and lower-body mode/gain/dq/tau remain zero.
- [x] Both elbow endpoint paths are checked with the active MuJoCo collision set.
- [x] Fresh startup precheck and two exact runtime confirmations are required.
- [x] Normal and fault exits attempt repeated zero-weight Arm SDK release frames.
- [ ] Perform the first grounded Regular-Mode physical test with remote E-stop ready.
- [ ] Confirm actual index 25 motion in LowState and MuJoCo, with no other joint excursion.
- [ ] Review the saved result before considering any live VR target publisher.

**Command authority:** right-elbow target only during the explicitly confirmed,
bounded experiment. No waist or lower-body authority.

## Full-authority right shoulder-pitch trial

- [x] Separate trial limits command ownership to right shoulder pitch index 22.
- [x] Full Arm SDK weight is acquired over 5 seconds while all 14 arm targets
  remain fixed at the measured startup pose.
- [x] Arming completed with the 14-axis maximum error below 1.5 degrees.
- [x] Physical command was limited to +/-1 degree at 1 deg/s for 15 seconds.
- [x] Two step inputs were accepted; commanded excursion was 1.00 degree and
  measured excursion was 1.34 degrees with 0.43-degree maximum tracking error.
- [x] Maximum-duration stop completed the 2-second release and 25 zero-weight
  frames with no command process left running.
- [x] The one-time trial authorization was restored to false immediately after
  the run.
- [x] Operator confirms no unexpected jump, abnormal sound, or balance
  disturbance during this full-authority movement test.

Result: `logs/test_results/g1_right_arm_jog_20260902_150717.json`

## Runtime phase meanings

| Phase | Meaning | Robot command allowed by current project? |
|---|---|---|
| `OFFLINE` | Hardware bridge stopped | No |
| `READ_ONLY_WAIT` | Waiting for first LowState | No |
| `READ_ONLY_ACTIVE` | Fresh LowState is being observed | No |
| `SYNCED` | Mink/Unity seeded from measured G1 pose | No |
| `STARTUP_RECOVERY` | Future collision-aware rest-to-ready transition | No, until command gates are approved |
| `HOLD_READY` | Measured dual-arm HOLD contract satisfied; output still disabled | No |
| `HOLD_ACTIVE` | Explicitly authorized `rt/arm_sdk` HOLD publisher active | Yes, only for the approved bounded HOLD |
| `TELEOP_READY` | Future live-target prerequisites satisfied | Future only |
| `TELEOP_ACTIVE` | Future live Mink command mode | Future only |
| `FAULT` | Fail-closed state; inspect `fault.code` | No |

## Fail-closed rule

A hardware fault is not a request to improvise another target. If a process reports `FAULT`, loses fresh LowState, or receives no `command_q_rad` from the Safety Gate, the command path must produce no new motion command and must require an explicit recovery/re-arm sequence before command output resumes.
# G1 mutation prohibition

- Do not create, delete, rename, move, or modify any file on the G1 without
  explicit approval for that exact operation.
- Do not execute a diagnostic until its source has been checked for file output,
  DDS publishers, service calls, mode changes, and other state mutation.
- A program described as read-only may still write logs. Treat any such write as
  a mutation requiring approval.
- Copying existing files from G1 to Windows is permitted only when the remote
  side is read-only and all output is written to the Windows project.
