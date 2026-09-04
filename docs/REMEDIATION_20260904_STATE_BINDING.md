# Startup state/model binding remediation — 2026-09-04

Branch: `main`

This document records the supported-path R40 remediation. It is not a physical acceptance report.

## R40 supported startup binding

Added:

```text
hardware/g1_arm_bridge/startup_state_binding_guard.py
```

The supported `check_startup_readiness_entry.py` now persists two additional evidence groups in the startup-precheck artifact:

```text
latest_base_state
startup_state_binding
```

`latest_base_state` is copied from the already validated read-only base-state telemetry associated with the latest accepted LowState sample. It preserves validity, packet age, normalized position/quaternion, linear velocity and yaw rate.

`startup_state_binding` contains SHA-256 identities for:

```text
config/g1_startup_precheck.json
MuJoCo G1 g1_29dof.xml
run_mink_g1_right_arm_prototype.py collision/controller source
g1_right_arm_common.py model/joint source
```

`precheck_provenance_guard.py`, which is already used by the supported Gate 6, Gate 7 and Jog physical entrypoints, now also calls `require_state_binding()`. Therefore a precheck created against a different startup config, G1 XML or collision/model source is rejected before the supported physical path can reuse it. Missing/invalid base-state evidence is also rejected.

The existing all-29-joint runtime comparison remains in the supported Gate 7/Jog guards. This means the publisher boundary now combines:

```text
per-run LowState forward provenance
fresh startup precheck
29-joint pose binding where supported
validated base-state evidence in the precheck
static model/config/collision-source identity
```

### Remaining R40 boundary

R40 is improved but not fully closed. The supported Python Arm SDK paths still do not compare a newly subscribed live base/odometry pose against the persisted precheck base sample at every publisher/control tick. LowState IMU roll/pitch supervision exists separately under R50, but absolute/current base-state rebinding remains open.

Status:

```text
R40 29-joint binding                     : MITIGATED on supported Gate 7/Jog paths
R40 precheck base-state evidence          : IMPLEMENTED
R40 model/config/collision-source hashes  : IMPLEMENTED
R40 live base-state publisher rebinding   : OPEN
Physical validation                       : NOT RUN
```

## Regression evidence

The provenance workflow was moved from the deleted refactor branch to `main` and now includes the startup state-binding assertions.

```text
.github/workflows/offline-provenance-regression.yml
Run 33822226143 : PASS
```

The safety workflow was also expanded:

```text
.github/workflows/offline-safety-regression.yml
Run 33822295391 : PASS
```

The safety run executes 44 unittest cases plus the Gate 6 interruption-release offline contract script. It covers shared/Gate 6 release, Gate 7 release/acquisition/final collision guards, LowState IMU/motor health supervision, and Jog safety/result boundaries. Both workflows are robot-offline and create no Unitree publisher or G1 command.
