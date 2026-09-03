# Remediation log continuation — 2026-09-04

Branch: `refactor/teleop-architecture`

This file continues [`REMEDIATION_20260904.md`](REMEDIATION_20260904.md). It records source changes separately from physical validation.

## Batch 3A — R2/R41 supported Gate 7 collision guards

Implementation commit:

```text
40e46d6538321034ab873ef189427c30b595e9f6
fix: guard Gate 7 active clearance and final command collision (R2 R41)
```

Added/changed:

- `hardware/g1_arm_bridge/gate7_live_safety_guard.py`
- `hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py`
- `hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh`
- `hardware/g1_arm_bridge/test_gate7_live_safety_guard.py`
- `hardware/g1_arm_bridge/test_gate7_live_entrypoint.py`

Supported WSL Gate 7 behavior now adds two fail-closed boundaries before the existing live adapter may publish a tracking frame.

### R41 mitigation

An ACTIVE Mink sample must contain a finite numerical `minimum_clearance_m`. ACTIVE input with null/missing/non-finite clearance is rejected by the supported entrypoint instead of being interpreted as safe merely because `collision_limited=false`.

### R2 mitigation

After the existing Gate 7 controller/Ruckig path creates an SDK-neutral final frame, the supported entrypoint constructs a bounded swept dual-arm segment from the latest measured 29-joint LowState pose to the exact final frame target. The existing `CollisionPathValidator` is called on that segment using the measured full-body pose. Missing validator, validator exception, non-boolean result, rejected clearance, or an unexpectedly large one-cycle segment all fail closed and remove the frame before the live adapter's `publisher.Write()` boundary.

The segment sampler uses a maximum 0.25-degree joint increment and rejects a one-cycle command that would require more than 64 segments. This bound is a validation/sampling guard, not a new motion-speed setting.

Boundary:

```text
R2 supported WSL Gate 7 path  : MITIGATED
R2 direct/internal path       : OPEN
R41 supported WSL Gate 7 path : MITIGATED
R41 base parser contract      : OPEN
Regression tests committed    : YES
Committed tests executed      : NO
Physical validation           : NOT AUTHORIZED / NOT RUN
```

Direct invocation of `gate7_live_arm_sdk.py`, direct use of `parse_mink_arm_sample()`, and non-supported dry-run/internal consumers do not automatically receive these wrapper guards. Full closure requires moving the rules into the core parser/controller/live adapter after repository tests can be executed.

## Batch 3B — R33 acquisition freshness and R40 29-joint binding

Implementation commits:

```text
d89458cba72431bab0b6bbdacd97299989ebec49
feat: add Gate 7 acquisition freshness guards (R33 R40)

df26873d1246da8de2aaa1b707a238754050757a
fix: enforce continuous Gate 7 acquisition stream (R33 R40)

1b159819c1da97379f5db5c115de7abf5ce5bcd8
fix: require multiple fresh samples before Gate 7 publisher boundary

c76cb179ec36a074b14b21e49b49f9467f9f7769
test: add Gate 7 acquisition and full-body guards

00e8d76dbd98fc4989c4ca4b4179a9138772ee2f
test: assert Gate 7 acquisition guards are installed
```

Added/changed:

- `hardware/g1_arm_bridge/gate7_acquisition_guard.py`
- `hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py`
- `hardware/g1_arm_bridge/test_gate7_acquisition_guard.py`
- `hardware/g1_arm_bridge/test_gate7_live_entrypoint.py`

### R33 mitigation

The supported Gate 7 entrypoint now requires more than one ACTIVE packet before the existing code crosses the publisher boundary. The initial accepted ACTIVE sample seeds a session/sequence guard; a second ordered ACTIVE sample must arrive within the configured Gate 7 `input_timeout_s` before `WaitForFirstActiveMink` returns to the live adapter.

During the acquire ramp, every call to the existing `AcquireWeight()` first drains the latest Mink sample and requires:

```text
same session
strictly increasing sequence when a new sample arrives
ACTIVE input mode / ACTIVE controller state
embedded input_packet_age_s <= configured input timeout
local receive age <= configured input timeout
```

If the stream disappears, changes session, goes inactive, becomes embedded-stale, or exceeds the local freshness window, `AcquireWeight()` raises and the existing outer fault/release path runs instead of continuing to raise authority for the full acquisition duration.

The supported entry also rechecks `validate_measured_hold()` when the live adapter builds acquisition HOLD frames with an explicit hold config, so measured/target joint limits and target error are evaluated while authority is being acquired.

### R40 partial mitigation

The live adapter's existing arm-only `validate_snapshot_matches_precheck()` is wrapped by a stricter check over all 29 joint positions. A waist or leg joint change beyond the same publisher-boundary tolerance therefore invalidates reuse of the startup precheck on the supported path.

This does **not** fully close R40 because the current `LowStateSnapshot` and startup precheck contract do not yet bind base/IMU evidence or model/config hashes. Those parts remain open and overlap R50/runtime supervision.

Boundary:

```text
R33 supported WSL Gate 7 path : MITIGATED
R33 core live adapter         : OPEN
R40 29-joint binding          : MITIGATED on supported Gate 7 path
R40 base/IMU/model binding    : OPEN
Regression tests committed    : YES
Committed tests executed      : NO
Physical validation           : NOT AUTHORIZED / NOT RUN
```

## Batch 3C — R42 supported Jog permit/runtime binding

Implementation commits:

```text
f6fc83d6657a4ecd92c9918800ea1a4a07f5d178
feat: add Jog permit provenance and runtime safety guards (R42)

149a274ddaa8e47d27a2409f564b6e1cee40a28a
feat: bind Jog permits to code config and model provenance (R42)

22cd0cf4849747a1e6d7580ab3070f916028f835
fix: bind supported Jog runtime to permit and full-body collision state (R42)

3f517f479165fe5aa1c5095707108f7feb8389ed
fix: generate provenance-bound Jog permit on supported launcher (R42)

16a21c446189f691da828050cacf9beaa29cfce8
fix: generate provenance-bound full-authority Jog permit (R42)

377f6c0019de259ac9f8aa8b857259c5d48155bc
test: add Jog provenance and final-segment guards
```

Added/changed:

- `hardware/g1_arm_bridge/right_arm_jog_safety_guard.py`
- `hardware/g1_arm_bridge/validate_right_arm_jog_collision_path_entry.py`
- `hardware/g1_arm_bridge/g1_right_arm_jog_entry.py`
- `hardware/g1_arm_bridge/test_right_arm_jog_safety_guard.py`
- `tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat`
- `tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat`

The two supported physical Jog launchers now create the path permit through the provenance-aware generator. A passing permit records SHA-256 identities for the selected Jog config, generated MuJoCo collision model, base permit generator, collision validator, and Jog controller source.

The supported WSL Jog entrypoint constructs the current `CollisionPathValidator` before delegating to the physical controller. `load_path_permit()` is wrapped so the permit hashes must exactly match the current config/code/generated model before Unitree imports and publisher creation continue.

While a selected Jog controller is active, every `ArmJointJogController.advance()` on the supported path now:

1. compares all 29 measured joint positions against the startup precheck tolerance,
2. computes the existing Jog candidate frame,
3. validates a swept segment from the latest measured full-body pose to that exact final frame through the current collision validator,
4. raises into the existing fault/release path if the full-body binding or final segment is rejected.

This makes permit invalidation sensitive to waist/leg drift during active Jog ticks and adds a final command collision check instead of relying only on the precomputed per-joint offset range.

Boundary:

```text
R42 supported bounded/full-authority launchers : MITIGATED
R42 direct g1_right_arm_jog.py path            : OPEN / UNSUPPORTED
Permit provenance/model hash check             : ADDED on supported path
29-joint runtime drift check                    : ADDED on selected-joint ticks
Final swept-segment collision check             : ADDED on selected-joint ticks
Base/IMU runtime binding                        : NOT COVERED (R40/R50 overlap)
Regression tests committed                      : YES
Committed tests executed                        : NO
Physical validation                             : NOT AUTHORIZED / NOT RUN
```

As with the Gate 7 wrappers, this is not core-path closure. Direct execution of the legacy permit generator or `g1_right_arm_jog.py` bypasses the supported wrapper contract and must remain unsupported for physical use.

## Current P1 state after Batch 3

The primary P1 wrapper-level mitigations are now in place for R2, R33, R41 and R42, with R40 partially covered at the 29-joint level. Core integration and regression execution remain outstanding. The next high-priority work should move to runtime supervision R50 and the remaining base/IMU portion of R40 rather than broadening physical trials.

## Verification boundary

No repository test suite, Unity, MuJoCo live launcher, WSL/DDS runtime or G1 command was executed while making Batch 3. Hardware authorization remains locked.