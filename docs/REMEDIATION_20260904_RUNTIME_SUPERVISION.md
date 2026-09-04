# Runtime supervision remediation — 2026-09-04

Branch: `main`

This file records the supported-path mitigation for R50. It is not a physical acceptance report.

## R50 supported Arm SDK path mitigation

The supported Gate 6, Gate 7 and right-arm Jog WSL entrypoints wrap the existing `LowStateBuffer.callback` and retain a health result alongside the original q/dq snapshot. Unsafe health does not discard the measured joint snapshot so the release path can still attempt a measured-pose zero-weight handoff.

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

The supported active/acquisition boundaries require the latest health result to be clean. A new unsafe condition raises into the existing fault/release handling rather than allowing authority acquisition/tracking to continue. Release helpers themselves are not blocked by the health guard.

### Verification now available

The current `main` safety workflow includes `test_lowstate_health_guard.py`.

```text
.github/workflows/offline-safety-regression.yml
Run 33822295391 : PASS
```

The R50 subset contains 7 passing tests covering nominal state, IMU tilt fault, motor temperature fault, motor fault state, non-finite torque, supported-entry guard references and supported WSL starter routing.

The same safety workflow also verifies release, Gate 7 acquisition/final collision and Jog result boundaries; the complete run contains 44 unittest cases plus the Gate 6 interruption-release offline contract script.

### Explicitly still open

R50 is not fully closed. The following remain outside the current Python Arm SDK runtime guard:

```text
live base/odometry pose and stability supervision
remote/deadman state
LowState CRC/integrity verification equivalent to the TWIST2 C++ path
explicit tau_est magnitude limits
firmware/controller ownership acknowledgement after release
```

R40 now separately persists a validated startup base-state sample and binds the startup result to current model/config hashes, but that does not replace a live runtime base-state subscription.

The actual Unitree Python SDK field compatibility for `imu_state.rpy`, motor `temperature`, `motorstate` and `tau_est` still requires read-only verification against the connected G1 before widening physical trials. Missing/changed fields are intended to fail closed.

Status:

```text
R50 IMU/motor health on supported WSL paths : MITIGATED + OFFLINE CI PASS
R50 live base/remote/CRC supervision         : OPEN
Physical validation                          : NOT AUTHORIZED / NOT RUN
```

No WSL/DDS/G1 runtime, Unity, Quest or physical publisher test was executed for this remediation evidence. Repository hardware authorization remains locked.
