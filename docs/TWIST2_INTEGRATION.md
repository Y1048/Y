# TWIST2 Integration Notes

## Purpose

This project does not vendor or copy TWIST2 controller code. TWIST2 is used as an architectural reference for future upper/lower-body integration on Unitree G1.

Reference repository:

- `amazon-far/TWIST2`
- License: MIT

## Patterns worth adopting

TWIST2 separates high-level motion generation from low-level robot control. Its teleoperation path produces high-level whole-body targets, while simulation/real low-level controllers consume those targets and publish robot state. It also uses explicit teleoperation states and smooth transitions between idle, teleop, pause, and exit.

The useful design ideas for this repository are:

1. Separate operator intent from robot-specific control.
2. Keep simulation and physical-robot controllers behind the same logical interface.
3. Make teleoperation state transitions explicit and testable.
4. Smooth re-engagement instead of applying large target jumps.
5. Define joint ownership before combining independently developed upper- and lower-body controllers.

## Proposed G1 integration boundary

```text
Quest 3S / Unity
        |
        v
PosePacketV2 / Legacy adapter
        |
        v
InternalCommand
        |
        v
High-level teleop state machine
        |
        +----------------------+----------------------+
        |                                             |
        v                                             v
Right-arm IK                                 Lower-body policy
        |                                             |
        v                                             v
right_arm[7]                                base whole-body target
        |                                             |
        +----------------------+----------------------+
                               |
                               v
                    Whole-body coordinator
                               |
                               v
                      canonical G1 29-DoF target
                               |
                      +--------+--------+
                      |                 |
                      v                 v
                    MuJoCo          Physical G1
```

## Initial joint ownership

For the current 29-DoF G1 ordering used by the lower-body reference controller:

| Group | Indices | Initial owner |
| --- | --- | --- |
| left leg | 0-5 | lower-body policy |
| right leg | 6-11 | lower-body policy |
| torso | 12-14 | lower-body policy |
| left arm | 15-21 | lower-body policy until left-arm teleop exists |
| right arm | 22-28 | current arm teleoperation IK |

The coordinator must be the only component that produces the final 29-DoF target. Individual controllers publish only the joint groups they own.

## Important compatibility rule

The current live Unity Legacy V0 packet does not have the same coordinate semantics as `PosePacketV2`.

- Legacy position is already mapped toward the controller/robot target frame by Unity.
- Legacy wrist rotation is still converted by the Python controller.
- V2 declares `unity_ovr_tracking` and is intended to carry a canonical tracked pose contract.

Therefore V2 must not be connected directly to the live right-arm IK until a dedicated coordinate-normalization stage converts both protocols into the same robot-frame target representation. This prevents a silent double transform or axis inversion.

## Integration phases

### Phase A — completed foundation

- Versioned V2 protocol contract
- Legacy/V2 parsing adapter
- Explicit runtime state-machine foundation
- 29-DoF joint-group ownership and composition utility

### Phase B — next

- Add coordinate-normalization stage after `InternalCommand`
- Move Legacy live receiver to `parse_command_packet()` without changing Legacy behavior
- Gate V2 live commands until normalization is complete
- Add receiver-level regression tests

### Phase C — whole-body integration

- Accept a lower-body 29-DoF base target
- Overlay right-arm IK target on indices 22-28 while teleop is active
- Return right-arm ownership to the lower-body controller when teleop is disabled if desired
- Define torso ownership explicitly before enabling simultaneous reaching and locomotion

### Phase D — sim/real parity

- Keep the same coordinator output contract for MuJoCo and the physical G1
- Put Unitree SDK-specific transport below the coordinator
- Add watchdog, freshness, joint-limit, and emergency-stop handling at the physical-robot boundary

## Attribution

TWIST2 is an external reference project by its original authors. If source code from TWIST2 is later copied or substantially adapted, retain the MIT copyright and permission notice required by its license and document the affected files. The current integration work uses architectural ideas only.
