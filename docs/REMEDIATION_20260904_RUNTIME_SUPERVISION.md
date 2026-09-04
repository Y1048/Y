# Runtime supervision remediation — 2026-09-04

Branch: `main`

This file records supported-path mitigation for R40/R50. It is not a physical acceptance report.

## LowState IMU/motor health

The supported Gate 6, Gate 7 and right-arm Jog WSL entrypoints wrap the existing `LowStateBuffer.callback` and retain a health result alongside the original q/dq snapshot. Unsafe health does not discard the measured joint snapshot so release can still attempt a measured-pose zero-weight handoff.

Current guard:

```text
hardware/g1_arm_bridge/lowstate_health_guard.py
```

Checks:

```text
IMU roll/pitch finite and within +/-0.35 rad
motor_state[0:29].tau_est finite
motor temperature <= 75 C
motor motorstate == 0
```

The active/acquisition boundaries require the latest health result to be clean. A new unsafe condition raises into the existing fault/release handling rather than allowing authority acquisition/tracking to continue. Release helpers themselves are not blocked by this guard.

## Runtime base/odometry stability

Added:

```text
hardware/g1_arm_bridge/runtime_base_state_guard.py
hardware/g1_arm_bridge/test_runtime_base_state_guard.py
```

The existing read-only hardware bridge already establishes the repository-side SDK contract for `rt/odommodestate` using `SportModeState_`, with `position`, `imu_state.quaternion`, `velocity`, and `yaw_speed`. The new supported-path guard reuses that same source contract through a lazy **read-only** subscriber. It does not create a Unitree publisher or command message.

At runtime the base pose is normalized against the first valid odometry sample of that controller process. The supported Gate 6/Gate 7/Jog entrypoints now require a recent stable base at their existing publisher/acquisition/control guard boundaries.

Default fail-closed limits are:

```text
base packet age          <= 0.25 s
samples                  >= 3
invalid base packets     == 0
translation from origin  <= 0.05 m
linear speed             <= 0.15 m/s
yaw speed                <= 0.25 rad/s
relative yaw drift       <= 8 deg
```

Integration points:

```text
Gate 6 : settled-state boundary and every authority-weight evaluation
Gate 7 : pre-publisher snapshot binding, acquisition-weight evaluation, every tracked Step
Jog    : pre-publisher/full-body binding and every controlled joint advance
```

`--validate-only` paths for Gate 6/Jog remain SDK-free and do not install the odometry subscriber.

### R40 boundary

This materially improves R40 because a supported publisher can no longer proceed solely from a historic 29-joint startup artifact while the current base is absent, stale, moving, or has drifted beyond the bounded runtime origin.

It does **not** prove that the runtime odometry normalizer has exactly the same origin as the earlier startup-precheck forwarder. The new runtime monitor intentionally establishes a fresh process-local origin. Therefore R40 remains **partial** rather than fully closed: exact startup-base-to-publisher-base origin continuity is still not proven.

## Offline verification

Current `main` workflow:

```text
.github/workflows/offline-safety-regression.yml
Run 33823568106 : PASS
```

The run contains 58 unittest cases plus the Gate 6 interruption-release offline contract script. The new runtime-base subset contains 10 passing tests covering nominal multi-sample state, stale state, translation drift, linear speed, yaw speed, yaw drift, invalid packet handling, read-only source structure, supported-entry integration, and validate-only SDK isolation.

The same run also keeps the existing LowState health, release, Gate 7 collision/acquisition, and Jog safety/release regressions green.

## Explicitly still open

R50 is not fully closed. The following remain outside the current Python Arm SDK runtime guard:

```text
remote/deadman state
LowState CRC/integrity verification equivalent to the TWIST2 C++ path
explicit tau_est magnitude limits
firmware/controller ownership acknowledgement after release
```

The repository currently contains no reviewed Python evidence for a canonical remote/deadman field or a LowState CRC validation API that can be added without guessing. Do not invent those checks. Verify the actual read-only Unitree SDK message contract first.

The actual connected-G1 compatibility of the Python fields used by both health and odometry guards still requires read-only verification before widening physical trials. Missing/changed fields are intended to fail closed.

Status:

```text
R50 IMU/motor health on supported WSL paths : MITIGATED + OFFLINE CI PASS
R50 base/odometry stability                 : MITIGATED + OFFLINE CI PASS
R50 remote/deadman/CRC                      : OPEN pending verified SDK evidence
R40 current-runtime base stability          : MITIGATED
R40 exact startup/runtime base-origin bind  : OPEN
Physical validation                         : NOT AUTHORIZED / NOT RUN
```

No WSL/DDS/G1 runtime, Unity, Quest or physical publisher test was executed for this remediation evidence. Repository hardware authorization remains locked.
