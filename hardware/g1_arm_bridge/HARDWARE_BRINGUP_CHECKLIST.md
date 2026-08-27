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

The captured arm-down rest pose may begin inside conservative Mink collision
geometry. Preserve it exactly during read-only sync/HOLD. Do not enable teleop
IK until a separately validated collision-aware transition reaches the clear
configured ready pose; direct joint interpolation is not approved.

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

## Gate 6 — Command-capable HOLD (future, explicit activation only)

This gate is intentionally not implemented yet.

Before adding or enabling a publisher:

- [ ] Gates 0–5 have passed on the physical G1 in the same session/configuration.
- [ ] Physical test area is clear and an operator can immediately stop robot operation.
- [ ] Command process starts with output disabled.
- [ ] First target is seeded exactly from fresh measured `q`.
- [ ] Safety Gate is the only source of publishable joint targets.
- [ ] Stale LowState, invalid target, limit violation, target error, or internal exception disables output.
- [ ] Arm-SDK acquire/release lifecycle is explicit and logged.
- [ ] HOLD is validated before any live Mink target is accepted.

Only after HOLD is independently validated may the project proceed to live Mink teleoperation.

## Runtime phase meanings

| Phase | Meaning | Robot command allowed by current project? |
|---|---|---|
| `OFFLINE` | Hardware bridge stopped | No |
| `READ_ONLY_WAIT` | Waiting for first LowState | No |
| `READ_ONLY_ACTIVE` | Fresh LowState is being observed | No |
| `SYNCED` | Mink/Unity seeded from measured G1 pose | No |
| `STARTUP_RECOVERY` | Future collision-aware rest-to-ready transition | No, until command gates are approved |
| `HOLD_READY` | Preconditions for a future HOLD publisher satisfied | No, until explicit command phase |
| `HOLD_ACTIVE` | Future command-capable HOLD mode | Future only |
| `TELEOP_READY` | Future live-target prerequisites satisfied | Future only |
| `TELEOP_ACTIVE` | Future live Mink command mode | Future only |
| `FAULT` | Fail-closed state; inspect `fault.code` | No |

## Fail-closed rule

A hardware fault is not a request to improvise another target. If a process reports `FAULT`, loses fresh LowState, or receives no `command_q_rad` from the Safety Gate, the command path must produce no new motion command and must require an explicit recovery/re-arm sequence before command output resumes.
