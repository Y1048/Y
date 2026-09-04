# Backend core full-text review — 2026-09-04

Branch: `main`

This is a **review-only** batch. No production source was changed as part of this document. The purpose is to retire a set of remaining `static_only` entries after reading the complete source and the directly relevant tests.

## Files reviewed

Production:

```text
backend/g1_teleop/__init__.py
backend/g1_teleop/protocol.py
backend/g1_teleop/config.py
backend/g1_teleop/calibration.py
backend/g1_teleop/transforms.py
backend/g1_teleop/motion_reference.py
backend/g1_teleop/mapping.py
backend/g1_teleop/camera.py
backend/g1_teleop/camera_factory.py
backend/g1_teleop/g1_camera_mount.py
backend/g1_teleop/gate7_simulation_feedback.py
backend/g1_teleop/runtime_state.py
backend/g1_teleop/unitree_image_transport.py
```

Tests:

```text
backend/tests/test_foundation.py
backend/tests/test_protocol_v2.py
backend/tests/test_teleop_config.py
backend/tests/test_motion_reference.py
backend/tests/test_runtime_architecture.py
backend/tests/test_gate7_simulation_feedback.py
```

## Findings and conclusions

### Existing R27 remains confirmed — SE(3) matrix validation is incomplete

`calibration._pose_matrix()` validates shape, finiteness and the homogeneous last row, but it does not require the upper-left 3x3 block to be orthonormal with determinant +1. `transforms.matrix_to_quaternion()`, `split_pose()` and `invert_pose()` likewise assume a valid rotation matrix rather than enforcing one at their public boundary.

This means scale/shear/reflection matrices can enter calibration APIs and later be treated as rigid transforms. This is the already-recorded **R27**; this review does not create a duplicate finding.

### Existing R32 remains confirmed — protocol V1 integer coercion differs from V2

`PosePacketV1.from_json()` and `StatePacketV1.from_json()` still use `int(...)` coercion for sequence/timestamp fields. V2 uses strict `_integer()` checks and explicitly rejects booleans. This is the already-recorded **R32**.

The current command adapter has its own stricter legacy checks, so this review does not widen R32 beyond the direct V1 protocol API without a separate caller analysis.

### Runtime workspace re-engagement is intentional in the current contract

`TeleopRuntimeStateMachine.apply(workspace_exit)` sets `workspace_reset_armed=True`, and the next valid ACTIVE command may re-enter `active`. This initially looks weaker than `trip_workspace_fault()`, which requires an explicit acknowledgement call, but `test_runtime_architecture.py` explicitly locks the distinction: a locally/explicitly observed `workspace_exit` packet is itself the re-engagement acknowledgement.

No new finding is recorded for this behavior.

### Config path is materially stricter than several legacy loaders

`load_teleop_config()` rejects booleans in numeric fields, requires integer ports/classes, enforces finite/positive/nonnegative constraints, checks ordered workspace ranges, and validates collision/task-contact structure. No new config-safety finding was found in this batch.

### Motion/mapping assumptions

`motion_reference.py` assumes valid finite position vectors and proper rotation matrices supplied by upstream protocol/mapping code. Under proper SE(3) inputs its rate limiting is mathematically consistent and its current tests verify position and angular step limits. Invalid matrix handling is covered by the broader R27 boundary issue rather than recorded as a new duplicate.

`mapping.py` applies the fixed left/right wrist basis transforms and rejects an unknown hand side. No new finding was recorded.

### Camera and image-transport surfaces

The camera modules are configuration/render/transport surfaces and do not create a robot command path. `CameraFrame` enforces image shape/dtype contracts; `CameraIntrinsics` enforces finite positive focal lengths; simulation and RealSense sources share the same frame object. `UnitreeSimImageWriter` uses a zero-timestamp pending header, writes the payload, then commits the real timestamp so readers do not intentionally consume a half-written frame.

There are lower-priority API-hardening opportunities (for example stricter type validation in the camera profile loader and stronger cleanup guarantees if RealSense startup fails after `pipeline.start()`), but this review found no evidence that merits a new P1/P2/P3 safety finding for the teleoperation control path.

### Gate 7 simulation feedback remains separated from hardware authority

The feedback contract requires `simulation_only=true`, `hardware_output_authorized=false`, exact dual-arm indices, ordered packet identity at the receiver layer, and only applies fresh `REGULAR_RETURN`/`REGULAR_HOLD` feedback while live command tracking is inactive. No new finding was recorded.

## Review status

```text
new P1 findings : 0
new P2 findings : 0
new P3 findings : 0
existing findings confirmed : R27, R32
production changes : NONE
physical/WSL/Unity runtime : NOT RUN
```

The files listed above may now be promoted from `static_only` to `full_text_review`. This does not mean R27/R32 are fixed; it means their source surfaces have been read and their current behavior is understood.
