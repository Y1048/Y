# G1 right-arm hardware bridge

This directory is the hardware boundary between the teleoperation controller and a physical Unitree G1.

## Phase 1: read-only bring-up

`read_only_lowstate.py` is intentionally incapable of commanding the robot:

- subscribes only to `rt/lowstate`;
- creates no DDS publisher;
- reads G1 right-arm joints 22 through 28;
- prints position, velocity and estimated torque;
- writes `logs/runtime/g1_hardware_lowstate.json`;
- exits with a fault if LowState becomes stale after packets have started arriving.

Do **not** add command publishing to this file. Command output belongs in a separate bridge introduced only after read-only state validation.

## Environment

Use a Linux machine connected to the G1 network with Unitree's official `unitree_sdk2_python` installed.

Find the wired interface, for example:

```bash
ip -br link
```

Then run from the project root:

```bash
python3 hardware/g1_arm_bridge/read_only_lowstate.py eth0
```

Replace `eth0` with the interface physically connected to G1, such as `enp3s0`.

Expected startup text includes:

```text
G1 right-arm hardware bridge -- READ ONLY
DDS topic:     rt/lowstate
Publishers:    NONE
Motor command: IMPOSSIBLE from this process
```

After DDS packets arrive, the script prints the seven right-arm joint states. The values should change when the arm is moved by an approved Unitree mode/controller.

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

1. **READ ONLY** — validate DDS, joint mapping, update rate and heartbeat.
2. **HOLD** — separate publisher process, seed target from measured state and hold current pose only.
3. **MINK TARGET** — feed rate-limited Mink targets through a hardware safety gate.

The first command-capable bridge must independently enforce heartbeat, measured/target error, joint limits, command-rate limits and controlled arm-SDK release.
