# OMNI to G1 lower-body input audit

## Current verified state

- Virtuix Omni Connect 1.2.93 is installed under
  `C:\Program Files\Virtuix\Omni Connect`.
- The installed application contains `OmniConnect.exe`, `MotionLibrary.dll`,
  Qt runtime files, and OpenVR support. It does not contain a Unity package,
  C# SDK source, assembly definition, C/C++ header, or import library.
- No Omni Unity SDK package was found in the current Downloads tree.
- Device pairing and account login are not yet recorded as completed.

## Current TWIST2 policy interface

The deployed TorchScript wrapper consumes a 1,432-value observation assembled
by `ObservationHistory` in `twist2_common.hpp`:

- 35 mimic values;
- 92 proprioceptive/current values;
- ten prior 127-value frames;
- another 35 mimic values.

The mimic block fixes element 2 to `0.8` and writes the 29 joint targets into
elements 6 through 34. The reviewed wrapper exposes no forward velocity,
lateral velocity, or yaw-rate command input. It is a joint-reference imitation
interface, not a conventional `cmd_vel` locomotion interface.

## Consequence

Omni walking vectors cannot be inserted directly into this TorchScript policy
without inventing an untrained observation mapping. Doing so would change the
model's input semantics and is not a valid integration path.

The final single-owner architecture remains valid: one 500 Hz full-body owner
must combine the chosen lower-body policy output with VR arm targets. The
missing part is a lower-body controller whose documented input accepts walking
commands, or a documented generator that converts Omni motion into the exact
joint-reference trajectory expected by this TWIST2 model.

## Required next artifacts

1. Obtain the matching Virtuix Omni Connect Unity SDK and record its exact
   assembly/package version.
2. Pair the Omni and record the actual SDK fields, ranges, coordinate frame,
   update rate, neutral behavior, and disconnect behavior without connecting
   them to G1.
3. Choose the lower-body command contract:
   - a locomotion policy with explicit forward/lateral/yaw commands; or
   - a verified Omni-to-mimic trajectory generator for this TWIST2 policy.
4. Add a PC-only recorder and replay fixture. Disconnect and stale input must
   produce a zero walking request while the full-body owner remains alive.
5. Integrate the verified request into the single owner only after offline
   replay and MuJoCo checks. Do not add another G1 publisher.

## Runtime ownership decision

During normal VR plus Omni operation, pinch, tracking loss, Select/B, Ctrl+C,
P, and Q return the arms to safe hold while the same full-body owner continues
lower-body control. Automatic AI selection is excluded from this runtime path.
Maintenance shutdown remains blocked until a cooperative owner handoff is
available.
