# G1 right-arm hardware bridge

This directory is the hardware boundary between the teleoperation controller and a physical Unitree G1.

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

Use a Linux machine connected to the G1 network with Unitree's official `unitree_sdk2_python` installed.

Find the wired interface, for example:

```bash
ip -br link
```

Basic read-only test:

```bash
python3 hardware/g1_arm_bridge/read_only_lowstate.py eth0
```

Replace `eth0` with the interface physically connected to G1, such as `enp3s0`.

Expected startup text includes:

```text
G1 right-arm hardware bridge -- READ ONLY
DDS topic:     rt/lowstate
DDS publishers: NONE
Motor command:  IMPOSSIBLE from this process
```

After DDS packets arrive, the script prints the seven right-arm joint states. The values should change when the arm is moved by an approved Unitree mode/controller.

## Hardware pose synchronization

Before any command-capable phase, the Windows teleoperation PC can initialize Mink and Unity from the actual measured G1 posture.

On the Linux G1-side machine, forward the read-only state to the Windows PC:

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
2. **HOLD** — separate publisher process, seed target from measured state and hold current pose only.
3. **MINK TARGET** — feed rate-limited Mink targets through a hardware safety gate.

The first command-capable bridge must independently enforce heartbeat, measured/target error, joint limits, command-rate limits and controlled arm-SDK release.
