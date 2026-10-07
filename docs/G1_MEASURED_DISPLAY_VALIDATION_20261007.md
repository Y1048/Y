# Measured G1 display and independent diagnostics — 2026-10-07

> **Superseding stage:** measured engagement-time initialization is now implemented separately; see `docs/G1_MEASURED_START_VALIDATION_20261007.md`. The no-reseed descriptions below record this display-only phase. Continuous measured-feedback IK is still not implemented.

Status: **EDIT_MODE_VALIDATED_PHYSICAL_XR_UNVERIFIED**.
Baseline: `9c4ecf81437b18b291da362518e892a4c3e0b4b6`.

This implements the first stage of measured-state adoption: correct the visible robot and separate measured/command diagnostics without feeding measured joint values into the IK generator. Automatic engagement-time resynchronization and continuous measured-state IK remain pending separate design and validation. No G1 source, policy, gains, running control process or motor commands were changed by this work.

## Root cause

`G1LowStateLegView` received the 29-joint LowState stream on loopback UDP 55073, but receiving a sample did not apply it. `G1UnityRightArmPreview.UpdateOfficialRobotPose()` called `ApplyMeasuredPose()` only when `!UsesBimanualSimulation`. The canonical existing-scene bilateral mode therefore skipped actual-joint application and rendered the 14 simulated IK joints. Its status text nevertheless claimed measured joints based only on the existence/freshness of a received sample.

A one-line removal of the condition was insufficient. The same rendered rig supplied the head-alignment mount, shoulder center and wrist engagement references. Replacing that rig pose with measured waist/arm angles would also have changed control/alignment references and existing outgoing world-diagnostic fields. That coupling is separated here.

## Display behavior

| Received state | Rendered joints | Explicit source label |
|---|---|---|
| No valid measured sample yet in this Play session | Existing startup/held IK command pose | IK simulation; measured state waiting |
| Valid, fresh LowState | All 29 measured joint angles | G1 measured joints; IK target separate |
| Once-valid stream becomes stale | Last measured 29-joint pose, never new IK joints | Last measured pose held; receive stale |
| Valid new source session | Newly measured joints only | Measured after successful application |
| Malformed/CRC/ordering/retired-session rejection | Previous accepted measured state retained | Fresh/stale follows its original receipt age |
| Rig contract cannot apply the measured state | Prior display retained | Measured pose application error |

The receiver now checks the rig's application result. Receipt logs describe RX availability rather than asserting that the renderer used it. The operator's existing HMD status strip includes a fourth row describing the actual selected display source.

This is a measured **joint** model, not an absolute world-pose mirror. The display root remains at the existing fixed position with the prescribed Omni yaw. IMU/base localization, actual body translation and synchronized physical hand-tip position are not newly estimated. PiP/HMD-follow and one-time alignment policy are unchanged.

The existing tracked-hand and IK/checked-stop goal markers remain separate from the actual rendered wrist. A visible goal marker or simulated FK is not labeled as measured physical motion.

## Command/reference isolation

`G1BimanualCommandFrame` owns command-only head/wrist reference transforms and the cached command shoulder/root values. It reuses the existing rig for FK: save the rendered joint rotations, temporarily evaluate the startup lower-body pose plus latest 14-joint command, cache reference transforms, and restore all rendered rotations in a `finally` block. No duplicate rendered robot, second IK solver, network worker or physics simulation is created.

The initial lower-body pose is captured before any measured state can be applied. Live measured waist and arm motion cannot redefine the operator alignment or command engagement targets.

For the canonical bilateral mode:

- `TryGetBimanualWorldFrame()` continues to provide the command/control frame, not measured display FK.
- Initial HMD alignment and both engagement targets use command references.
- Existing outbound `unity_*wrist_world_m` and shoulder diagnostics retain their command-frame meaning; actual measured FK is in the new diagnostic stream.
- `LatestJoints` still comes exclusively from validated PC IK feedback.
- Requested world goals and checked-stop target markers remain distinct.
- LowState never reseeds the Python configuration, command velocity, checked stopping tail, engagement state or return generator.

The helper is evaluated synchronously inside the preview before rendering. Its temporary FK evaluation restores the measured pose before the frame is displayed. Runtime overhead and final headset presentation still need a live XR check; edit-mode correctness is not a timing guarantee.

## Read-only measured/command diagnostics

New files are written during the next actual Play session to:

```text
logs/test_results/measured_tracking/
  unity_measured_<date_time>_<session>.jsonl
```

Schema: `g1.measured_tracking.diagnostic.v1`. Sampling is 5 Hz; output is buffered and flushed at most once per second. This is an observational diagnostic, not a new realtime controller or a high-rate latency measurement channel. IO failure disables diagnostics and does not alter robot commands. End-of-session disposal flushes when normal application cleanup occurs; power-loss durability is not guaranteed.

Each record distinguishes:

- `q_measured_rad` and `dq_measured_rad_s`: 29 actual joint measurements.
- `q_command_rad`: 14 current PC IK joint goals, not a claim about the actuator's final applied targets.
- Measured source session/sequence/timestamp and Unity receipt age.
- PC feedback backend identity/sequence and Unity receipt age.
- Measured-applied, measured-fresh, command-fresh and comparison-valid flags.
- Per-arm-joint measured-minus-command error and maximum joint error when both sources are fresh.
- Measured model wrist FK, independent command FK and requested IK goal in the declared fixed display frame.
- Wrist-distance comparisons only while the corresponding snapshots are valid.

Comparison snapshots are selected by local receipt time, not by synchronized robot/PC clock alignment. `age_s` remains the existing bridge's excess transport delay estimate. `absolute_transport_latency_available=false` and `absolute_robot_world_pose_available=false` are explicit. A 5 Hz comparison is unsuitable for claiming end-to-end latency or for proving physical stopping clearance.

Receiver display freshness now combines elapsed local receipt time and reported excess delay with the existing 0.5-second display budget. This is not a new control-grade freshness contract. Already retired source sessions cannot overwrite a newer reconnect session; accepted arrays are cloned to avoid external alias mutation.

## Verification

### Actual Unity edit-mode execution

`G1MeasuredDisplayValidation.RunBatch` executed in Unity `6000.5.4f1` on the actual official G1 prefab in a disposable PreviewScene. It did not enter Play, start the sender/receiver sockets, load an operator control scene for execution, or contact G1.

Result: **10 scenarios, 155 assertions, PASS**, Unity process exit 0.

The scenarios checked:

1. Before the first measured sample, the model is explicitly simulated.
2. All 29 rendered joint rotations equal the chosen measured sample.
3. Measured waist/arm changes do not change command head/shoulder/wrist references or the outgoing control-frame diagnostic packet. Serialized packet equality was tested.
4. Measured/command arrays and mismatch diagnostics remain distinct without feedback.
5. Stale measured input holds its pose even while the command changes.
6. Reconnect updates only the display, rejects retired sessions, and does not reset IK command state.
7. Invalid fields, CRC, names, lengths, sequence ordering and alias mutation cannot replace valid measurements.
8. Local elapsed time plus reported excess delay determine diagnostic freshness.
9. Measured joint application does not move or rotate the display root.
10. No Play transition or control sockets were created by the validation.

The editor-only validator can also be invoked from `G1 Teleop/Validate Measured Display Isolation`. Its Library request hook refuses to run while Play is active or pending. It does not stop/start an operator session.

The first raw-shell batch attempt failed before code execution because Unity Package Manager could not start its IPC server. The successful attempt used the existing launcher's process-local `unity_environment()` plus the missing `COMSPEC`. No global environment/OS setting or launcher logic was modified. The old source compiler response file lacked package references; a separate semantic compile used the operator project's existing Unity/OVR/UI/Newtonsoft references. Both runtime and Editor assemblies compiled with zero errors, then native Unity executed the behavioral validation successfully.

### Regressions

- Full backend: **305 tests, exit 0**.
- Full hardware: **44 tests, exit 0**.
- New source-contract tests: 7; paired with the existing LowState tests, 10 targeted tests passed. These source checks are not used as a substitute for the actual Unity transform tests.
- Runtime/test source hash changes during full suites: none.
- Python IK, joint-range contract, safety, return, LowState bridge, optional-Omni receiver, hand binder and HMD camera-alignment sources match the baseline.

## Operation, scope and next decision

The current supported operator path remains the existing automatic Unity Editor launch/Play workflow. The old Windows standalone diagnostic binary was not rebuilt by this change. Applying source updates requires the Editor's normal compilation/reload before the next session. Do not treat the old standalone binary as containing this repair.

No new launch flags, ports or Python dependencies were added. No automatic G1 discovery/provenance enforcement or IK-on-LowState control loop was introduced.

Before implementing measured-based initialization or continuous feedback, validate the new measured display on a real Quest/G1 session and examine the separately identified snapshots. A future closed-loop controller must explicitly handle command continuity, state freshness, joint velocity, incoming-state jumps, cached safety tails and actual plant response. Replaying old LowState against different hypothetical commands cannot establish closed-loop stability.

Physical hand tracking, the earlier left-hand losses, motor tracking error, complete shutdown and actual headset readability/performance have not been revalidated by this edit-mode task. Existing harness/E-stop/controlled-shutdown requirements remain. This patch does not claim to fix physical latency or the logged wrist motor error.

Evidence folder: `logs/test_results/measured_display_20261007_115640/`. Contains pre-edit snapshots, semantic compile logs, the failed raw-environment batch log, successful Unity JSON/log, full regression output and hashes. Portable synchronization and commit identity are recorded in its release report after deployment.

## Portable source deployment verification

The 12 scoped source/test/document files were synchronized to `C:\Users\user\Desktop\G1_Teleop_Portable` after checking that known teleop workers, relevant loopback sockets and a pending automatic Play request were absent. Existing Portable files were compared with the baseline and backed up before copying; all final source/Portable hashes match. A temporary Windows delete-sharing denial on the preview source was recovered by a verified direct write, not by changing permissions or terminating the operator Editor. Only this task's temporary replacement file was removed.

Portable embedded Python validation: **53 tests, exit 0**, covering the display contracts, LowState validation, launcher and Portable environment. Source and Portable `DevAgentSettings.asset` hashes were preserved. The operator's Editor was not started/stopped or sent a Play request. Its next normal import/reload must compile these source changes before use; the successful real Unity behavioral run was performed in the source project's separate edit-mode process. The old prebuilt standalone executable remains unchanged.
