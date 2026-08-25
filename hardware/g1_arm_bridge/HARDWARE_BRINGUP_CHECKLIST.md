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

- [ ] `unitree_sdk2py` imports successfully in WSL2.
- [ ] Correct G1-facing network interface selected.
- [ ] `rt/lowstate` packets are received continuously.
- [ ] Runtime phase becomes `READ_ONLY_ACTIVE`.
- [ ] `publisher_present` is `false`.
- [ ] `command_output_enabled` is `false`.
- [ ] Packet age remains comfortably below the configured timeout.
- [ ] Stopping/disconnecting LowState produces `FAULT / LOWSTATE_TIMEOUT` after traffic has started.

Status file: `logs/runtime/g1_hardware_lowstate.json`

**Command authority:** NONE.

## Gate 2 — Right-arm joint mapping sanity

Verify indices 22–28 while moving only small, intentional amounts under normal robot operation.

- [ ] 22 = right shoulder pitch.
- [ ] 23 = right shoulder roll.
- [ ] 24 = right shoulder yaw.
- [ ] 25 = right elbow.
- [ ] 26 = right wrist roll.
- [ ] 27 = right wrist pitch.
- [ ] 28 = right wrist yaw.
- [ ] Sign/direction of each reported angle is understood.
- [ ] No unexpected discontinuities, NaN/Inf values, or implausible velocities appear.

**Command authority:** NONE.

## Gate 3 — Initial pose synchronization

Forward read-only telemetry to Windows UDP 5007 and run the hardware-sync launcher.

- [ ] Fresh seven-joint snapshot received from G1.
- [ ] `g1_hardware_initial_state.json` contains the same measured joint vector.
- [ ] Mink initializes from measured G1 `q`, not the fallback ready pose.
- [ ] Unity avatar initializes to the same seven measured joint angles.
- [ ] No visible target jump occurs when the teleop clutch first becomes active.

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

- [ ] Gate accepts a stationary measured-pose HOLD candidate.
- [ ] Real LowState heartbeat loss causes immediate fail-closed denial.
- [ ] Measured joints remain inside safety-margin limits.
- [ ] Logs clearly show phase, packet age, fault code, measured q and candidate q.
- [ ] No Unitree command DDS publisher exists in the process.

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
| `HOLD_READY` | Preconditions for a future HOLD publisher satisfied | No, until explicit command phase |
| `HOLD_ACTIVE` | Future command-capable HOLD mode | Future only |
| `TELEOP_READY` | Future live-target prerequisites satisfied | Future only |
| `TELEOP_ACTIVE` | Future live Mink command mode | Future only |
| `FAULT` | Fail-closed state; inspect `fault.code` | No |

## Fail-closed rule

A hardware fault is not a request to improvise another target. If a process reports `FAULT`, loses fresh LowState, or receives no `command_q_rad` from the Safety Gate, the command path must produce no new motion command and must require an explicit recovery/re-arm sequence before command output resumes.
