# G1 right-arm hardware bridge

This directory is the hardware boundary between the teleoperation controller and a physical Unitree G1.

The required physical bring-up order is documented in [`HARDWARE_BRINGUP_CHECKLIST.md`](HARDWARE_BRINGUP_CHECKLIST.md). Do not skip gates when moving from read-only validation toward command-capable operation.

## Phase 1: read-only bring-up

`read_only_lowstate.py` is intentionally incapable of commanding the robot:

- subscribes only to `rt/lowstate`;
- creates no DDS publisher;
- reads G1 right-arm joints 22 through 28;
- prints position, velocity and estimated torque;
- writes `logs/runtime/g1_hardware_lowstate.json`;
- can forward measured joint telemetry over ordinary UDP for startup synchronization;
- exits with a fault if LowState becomes stale after packets have started arriving.

Do **not** add command publishing to this file. Command output belongs in a separate bridge introduced only after read-only state validation.

## Environment

The current Unitree SDK2 bridge is intended to run inside the Linux environment used for Unitree DDS. On a Windows-only development PC, the planned deployment is WSL2 once the local Windows virtualization/WSL installation is healthy.

Basic read-only test inside that environment:

```bash
python3 hardware/g1_arm_bridge/read_only_lowstate.py eth0
```

Replace `eth0` with the interface connected to G1.

Expected startup text includes:

```text
G1 right-arm hardware bridge -- READ ONLY
DDS topic:     rt/lowstate
DDS publishers: NONE
Motor command:  IMPOSSIBLE from this process
```

After DDS packets arrive, the script prints the seven right-arm joint states.

## Runtime state and fault schema

`hardware_state.py` defines the common fail-closed status format used during hardware bring-up. Every status document records:

- schema version and timestamp;
- component name;
- explicit hardware phase;
- whether a publisher exists;
- whether command output is enabled;
- fail-closed flag;
- structured fault code/message;
- component-specific details.

Current phases are:

`OFFLINE`, `READ_ONLY_WAIT`, `READ_ONLY_ACTIVE`, `SYNCED`, `HOLD_READY`, `HOLD_ACTIVE`, `TELEOP_READY`, `TELEOP_ACTIVE`, and `FAULT`.

The read-only bridge always reports both `publisher_present=false` and `command_output_enabled=false`. A stale LowState after traffic has started is written as `FAULT / LOWSTATE_TIMEOUT` before the process exits.

Offline schema tests:

```powershell
.\tools\TEST_G1_HARDWARE_STATE.bat
```

## Hardware pose synchronization

Before any command-capable phase, Mink and Unity initialize from the actual measured G1 posture.

Forward the read-only state to the Windows teleoperation side:

```bash
python3 hardware/g1_arm_bridge/read_only_lowstate.py eth0 --forward-host <WINDOWS_PC_IP>
```

This sends **telemetry only** to UDP port 5007. It still creates no DDS publisher and cannot command a motor.

On Windows, run:

```powershell
.\tools\START_MINK_G1_HARDWARE_SYNC.bat
```

The startup sequence is:

1. `receive_initial_state.py` waits for one fresh UDP 5007 snapshot.
2. The seven measured right-arm joint angles are stored in `logs/runtime/g1_hardware_initial_state.json`.
3. Mink starts with `G1_USE_HARDWARE_INITIAL_STATE=1` and uses those measured angles instead of the fallback ready posture.
4. Mink publishes its initialized right-arm state on the existing UDP 5006 channel.
5. Unity's existing `G1RobotStateUdpReceiver` / `G1UnityRightArmPreview` applies the same seven joint angles to the G1 avatar.
6. Only after this synchronization should clutch engagement be considered.

At this phase there is still **no robot command publisher**.

## Hardware Safety Gate

`safety_gate.py` is a pure-Python, fail-closed gate with no DDS dependency and no command output. A future HOLD/Mink publisher is only allowed to use the `command_q_rad` returned by an `allowed=True` decision.

Current checks:

- LowState age must be <= 250 ms;
- measured and requested vectors must contain exactly seven finite values;
- measured and requested joints must remain inside G1 joint ranges with a 2-degree safety margin;
- the teleoperation elbow policy is tightened to 5-120 degrees before the 2-degree margin;
- requested target may be at most 10 degrees away from measured state on any joint;
- output rate is limited to 15 deg/s per joint;
- any failure returns no command vector.

The underlying right-arm joint limits are taken from the official Unitree MuJoCo G1 29-DoF model used by this repository, with the existing elbow operational restriction applied on top.

Run the offline tests on Windows without Unitree SDK or G1 hardware:

```powershell
.\tools\TEST_G1_HARDWARE_SAFETY_GATE.bat
```

Passing these tests does **not** authorize robot command output. The command-capable bridge remains a separate later phase.

## Joint mapping

| Index | Joint |
|---:|---|
| 22 | right shoulder pitch |
| 23 | right shoulder roll |
| 24 | right shoulder yaw |
| 25 | right elbow |
| 26 | right wrist roll |
| 27 | right wrist pitch |
| 28 | right wrist yaw |

## Planned phases

1. **READ ONLY + INITIAL SYNC** — validate DDS, mapping, heartbeat, and initialize Mink/Unity from measured G1 pose.
2. **SAFETY GATE OFFLINE** — validate fail-closed joint/heartbeat/rate-limit logic without a publisher.
3. **REAL LOWSTATE DRY RUN** — feed actual measured G1 state through the Safety Gate while requested target equals measured pose, still with no publisher.
4. **HOLD** — separate publisher process, seed target from measured state and hold current pose only through the safety gate.
5. **MINK TARGET** — feed rate-limited Mink targets through the same safety gate only after HOLD is independently validated.

The command-capable bridge must additionally implement controlled arm-SDK acquire/release and must never bypass the safety gate.
