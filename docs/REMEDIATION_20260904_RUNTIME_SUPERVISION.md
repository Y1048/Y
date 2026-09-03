# Runtime supervision remediation — 2026-09-04

Branch: `refactor/teleop-architecture`

This file continues the remediation logs and records the supported-path mitigation for R50. It is not a physical acceptance report.

## R50 supported Arm SDK path mitigation

Implementation commits:

```text
95810e0fb6ae55fefc814cbbb8eefb9cd7b902f5
feat: add Arm SDK LowState health supervision guard (R50)

0f753d7f2a0d6f4941436c427712f0492c74ce77
fix: supervise Gate 7 IMU and motor health on supported path (R50)

d3b7be928e297dd9821e97ac51f8e629e3c86a5d
fix: supervise Jog IMU and motor health on supported path (R50)

bfd8eb00595e6da9e5ef748b6165a4ebef39932a
fix: supervise Gate 6 IMU and motor health on supported path (R50)

ce9452960993ccfc24cef706c649074a2348787b
fix: route Gate 6 through supported health entry (R50)

79ecd140286ddea06edf4ce7a7f61b02e5b06a9a
test: add SDK-neutral LowState health supervision checks
```

Added/changed:

- `hardware/g1_arm_bridge/lowstate_health_guard.py`
- `hardware/g1_arm_bridge/gate6_arm_sdk_hold_entry.py`
- `hardware/g1_arm_bridge/start_gate6_hold_wsl.sh`
- `hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py`
- `hardware/g1_arm_bridge/g1_right_arm_jog_entry.py`
- `hardware/g1_arm_bridge/test_lowstate_health_guard.py`

The supported Gate 6, Gate 7 and right-arm Jog WSL entrypoints now wrap the existing `LowStateBuffer.callback` and retain a health result alongside the original q/dq snapshot. Unsafe health does not discard the measured joint snapshot; this is intentional so the existing release paths can still use a measured pose.

The supported active/acquisition boundaries require the latest LowState health result to be clean. The guard currently checks:

```text
IMU roll/pitch finite and within +/-0.35 rad
motor_state[0:29].tau_est finite
motor temperature <= 75 C
motor motorstate == 0
```

When a new health condition is unsafe, the active path raises into the existing fault/release handling instead of continuing authority acquisition/tracking. Release helpers are not blocked by the health guard, so a health fault does not intentionally suppress a zero-weight release attempt.

### Explicitly still open

R50 is **not fully closed**. The following review items remain outside this wrapper:

```text
base/odometry pose and stability supervision
remote/deadman state in the Python Arm SDK paths
LowState CRC/integrity verification equivalent to the TWIST2 C++ path
explicit tau_est magnitude limits (only finiteness is checked here)
firmware/controller ownership acknowledgement after release
```

The current Python SDK field compatibility for `imu_state.rpy`, motor `temperature`, `motorstate`, and `tau_est` has not been exercised against a connected G1 in this remediation session. Missing/changed fields are designed to fail closed, but that compatibility must be verified read-only before any physical trial is widened.

Boundary:

```text
R50 IMU/motor health on supported WSL paths : MITIGATED
R50 base/remote/CRC supervision             : OPEN
Regression tests committed                  : YES
Committed tests executed                    : NO
Physical validation                         : NOT AUTHORIZED / NOT RUN
```

## Verification boundary

No WSL/DDS/G1 runtime, Unity, Quest or physical publisher test was executed for these commits. Repository hardware authorization remains locked.