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

## Runtime base/odometry stability and startup binding

Relevant files:

```text
hardware/g1_arm_bridge/runtime_base_state_guard.py
hardware/g1_arm_bridge/read_only_lowstate_entry.py
hardware/g1_arm_bridge/check_startup_readiness_entry.py
hardware/g1_arm_bridge/startup_state_binding_guard.py
hardware/g1_arm_bridge/test_runtime_base_state_guard.py
```

The existing read-only hardware bridge establishes the repository-side SDK contract for `rt/odommodestate` using `SportModeState_`, with `position`, `imu_state.quaternion`, `velocity`, and `yaw_speed`. The supported read-only startup entry now preserves both the normalized startup base sample and the raw source-odometry position/quaternion in the token-bound precheck artifact.

Supported Gate 6/Gate 7/Jog entrypoints install a lazy **read-only** runtime `rt/odommodestate` subscriber. The runtime monitor retains both process-relative stability state and current raw source-odometry coordinates. Before publisher/acquisition authority is accepted it compares those raw coordinates to the startup-precheck sample.

Default fail-closed runtime limits are:

```text
base packet age                    <= 0.25 s
samples                            >= 3
invalid base packets               == 0
translation from runtime origin    <= 0.05 m
linear speed                       <= 0.15 m/s
yaw speed                          <= 0.25 rad/s
relative yaw drift                 <= 8 deg
startup/runtime raw odom position  <= 0.05 m
startup/runtime raw odom rotation  <= 8 deg
```

Integration points:

```text
Gate 6 : settled-state publisher boundary + continuous authority-weight guard
Gate 7 : pre-publisher full-body/base binding + acquisition + tracked Step
Jog    : pre-publisher full-body/base binding + each controlled advance
```

`--validate-only` paths for Gate 6/Jog remain SDK-free and do not install the odometry subscriber.

### R40 boundary

The earlier R40 gap was that the physical publisher boundary was not bound to current full-body/base state. The supported path now combines:

```text
29-joint startup/current comparison
startup model/config/source SHA-256 binding
per-run LowState provenance token
startup raw odometry position/quaternion
current raw odometry position/quaternion
runtime base freshness/motion limits
```

Therefore the **source-side supported path mitigation for R40 is complete**. This is not a physical-validation claim: actual connected-G1 compatibility of `rt/odommodestate` fields and runtime behavior still requires read-only/physical verification.

## Offline verification

Current relevant runs:

```text
.github/workflows/offline-safety-regression.yml
Run 33824155653 : PASS

.github/workflows/offline-provenance-regression.yml
Run 33824261133 : PASS
```

Safety coverage includes runtime base freshness, translation, linear speed, yaw speed, yaw drift, invalid packet handling and startup/runtime raw-odometry continuity. Provenance coverage includes per-run startup token verification plus required raw odometry evidence.

## Explicitly still open

R50 is not fully closed. The following remain outside the current Python Arm SDK runtime guard:

```text
remote/deadman state
LowState CRC/integrity verification equivalent to the TWIST2 C++ path
explicit tau_est magnitude limits
firmware/controller ownership acknowledgement after release
```

The repository currently contains no reviewed Python evidence for a canonical remote/deadman field or a LowState CRC validation API that can be added without guessing. Do not invent those checks. Verify the actual read-only Unitree SDK message contract first.

Status:

```text
R40 supported-path source binding            : MITIGATED + OFFLINE CI PASS
R40 connected-G1 validation                  : NOT RUN
R50 IMU/motor health                         : MITIGATED + OFFLINE CI PASS
R50 base/odometry stability                  : MITIGATED + OFFLINE CI PASS
R50 remote/deadman/CRC                       : OPEN pending verified SDK evidence
Physical validation                          : NOT AUTHORIZED / NOT RUN
```

No WSL/DDS/G1 runtime, Unity, Quest or physical publisher test was executed for this remediation evidence. Repository hardware authorization remains locked.
