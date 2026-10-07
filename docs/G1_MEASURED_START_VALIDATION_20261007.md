# Measured-state initialization before bilateral engagement — 2026-10-07

Status: **OFFLINE_AND_UNITY_EDIT_MODE_VALIDATED_PHYSICAL_XR_UNVERIFIED**.
Baseline: `eda164123958c79a95f1a035ec295932b93ae002`.

This completes the next stage after measured display isolation: initialize the inactive PC IK model from a stationary measured snapshot, acknowledge that initialization in Unity, then allow the normal bilateral alignment/engagement procedure. It is not continuous measured-feedback IK. No G1 program, physical gain, controller owner or motor was modified or started during this task.

## Problem reproduced

After the visible robot began following all 29 measured LowState joints, alignment spheres still used the old PC ready posture. In the 13:09 observation-only session the left/right command-to-measured wrist gaps were approximately 73.168/73.760 mm. Both arm posture and measured waist posture contribute. Moving only the spheres would leave the IK start inconsistent with those references.

The fixture `backend/tests/fixtures/g1_measured_start_20261007.json` retains one real stationary pose from `unity_measured_20261007_130916_51eea1f9b80c45399b3ac11ea98b01f4.jsonl`, whose SHA256 is `f1ff01df54a7cb3214bc54d51479294fa85f7e116ac695e1c4a3d6a267d70986`. It is an initialization/FK fixture, not a recording of the robot responding to this new controller.

## Current v5 procedure

The canonical existing-scene Unity sender now uses `g1.bimanual.unity.sim.v5` on the same loopback port 5020. It includes the latest validated measured snapshot, initial-head-alignment status and the revision of the initialization actually prepared by the Unity command frame.

1. While the cycle is READY and the operator is inactive, collect distinct, ordered LowState snapshots after initial HMD alignment.
2. Require a locally fresh, approximately stationary pose for at least 0.35 seconds in both local receipt time and source time. Duplicated Unity packets cannot manufacture new measurements or extend their freshness.
3. Validate the full measured pose, unchanged receiver-compatible arm ranges, collision model, authored home and return waypoint. Reject rather than clip an invalid measured pose.
4. Update the inactive model, clear its obsolete velocities/tails and create stationary checked initial tails. This remains READY and is not an active arm command.
5. Send a revision acknowledgement and the initialized non-arm body snapshot back to Unity. The backend must have announced a revision before it accepts engagement referencing it.
6. Unity prepares the command wrist references from the acknowledged body/arm state. Only its prepared revision, a matching fresh measured source and fresh backend feedback allow the existing hand-alignment dwell to engage.
7. During TRACKING and RETURNING, never reseed the model from incoming measurements. A return invalidates the initialization approval; subsequent engagement requires a new stable initialization and acknowledgement.

The visible 29-joint model remains driven by LowState. IK and checked-target markers remain separate during tracking; a tracking goal is not forced onto the measured wrist to conceal an error.

## Initialization limits and timing interpretation

| Condition | Value |
|---|---:|
| Local elapsed receipt time plus reported excess delay | at most 0.10 s |
| Maximum local/source gap between distinct samples | 0.10 s |
| Stable window in local and source time | at least 0.35 s |
| Minimum distinct samples | 3 |
| Maximum instantaneous absolute reported joint speed | 0.10 rad/s |
| Maximum pose drift from the stable-window/seed reference | 0.005 rad |

Both speed and pose-drift tests apply to all 29 joints. The initial 0.05-rad/s candidate repeatedly invalidated a virtually stationary recorded knee: reported dq reached 0.0753 rad/s while the largest q span was only about 0.0123 degrees over the inspected four seconds. The final 0.10-rad/s test is combined with the unchanged 0.005-rad drift condition; no command/input filter was added. It is not a change to the onboard physical velocity limits.

The original viewing bridge reports excess transport delay relative to the minimum observed clock offset, not synchronized absolute sample age. The 0.10-second condition is therefore **not an absolute latency guarantee or a certified realtime feedback channel**. Measurement loss, stale/reordered/malformed snapshots, source changes, motion, invalid ranges or an unmatched revision prevent initialization/engagement rather than silently falling back to the old ready pose. Actual Balance motion may legitimately prevent stationarity; do not loosen the conditions merely to force engagement without investigating the live log.

## Model and command continuity

`g1_bimanual_measured_start.py` owns snapshot validation, the stable idle gate and inactive-model initialization. The existing bilateral QP, tracking objective, gain values, range contract, collision/stopping constraints and return generator remain.

All 29 measured joint angles initialize model kinematics. The non-arm 15 joints are frozen at that snapshot for this cycle; they are not optimized, sent as new lower-body commands or continuously overwritten. The authored 14-arm home and return waypoint are preserved. The prescribed free base and Omni yaw remain unchanged. This is still a fixed-base model, not absolute robot-world localization or whole-body closed-loop control.

The first active IK step is checked from the initialized stationary command state. A different inactive internal reference is not itself a commanded physical motion: the existing G1 receiver activates arms only for TRACKING/RETURNING, not READY. This does not prove continuity from the actuator's final retained setpoint or bound the real motor acceleration. The existing final C++ arm slew limit and physical safety procedures remain necessary.

The command FK helper accepts the acknowledged body snapshot. It still saves/restores the measured rendered rotations, rather than creating a second rig or solver. Its HMD head anchor is retained from the pre-measurement startup frame: adopting a waist posture does not recenter the operator camera. The participation wrist/shoulder reference is allowed to change only through the explicit initialized command state.

## Diagnostics and compatibility

The v5 feedback has a `measured_start` block with revision, source session, readiness/reason and frozen body joints. Log rows mark an `idle_measured_initialization` explicitly. The session report verifies that such a change occurred on a READY/idle row after an inactive aligned v5 request, matches the supplied measured arm pose and has a new revision. Only then is it excluded from active-motion finite-difference calculations. Forged initialization flags on tracking rows fail validation.

The replay reconstructs feedback emission as well as inputs/ticks, because emitting the initialization acknowledgement is part of this protocol. A synthetic v5 input/feedback log reproduces the generated q path exactly in tests. This is deterministic software replay, not evidence of physical closed-loop stability.

Historical v1/v4 packets and their existing offline tests retain their previous numerical behavior. Schema changes within a live Unity session are rejected. A new canonical sender cannot silently arm using an old backend that lacks the initialization acknowledgement. Runtime provenance includes the new helper (11 source hashes).

No new worker, socket port, Python dependency, gain, output clip or command prediction was added. Omni remains optional. Canonical v5 engagement now intentionally waits for valid measured G1 state even with `--no-groot-actuation`; an entirely disconnected G1 can show an explicitly simulated waiting pose but cannot engage this measured-start path. Historical/isolated simulation and replay remain available separately.

## Validation

- Full backend: **321 tests, exit 0**.
- Full hardware: **44 tests, exit 0**.
- New measured-start tests: **16**, covering stable admission, age/order/session checks, no reseed while active/returning, invalid-range/clearance rejection without partial commit, announced/prepared revision requirements, first-step command bounds, repeat engagement, v5 exact software replay and forged inactive-event rejection.
- Actual Unity edit-mode execution: **155 existing display assertions + 18 measured-start assertions**, all passed; Unity 6000.5.4f1, process exit 0, no Play or control sockets.
- Official-prefab reconstruction: left/right gap **73.167652/73.760025 mm before**, **0/0 mm after** at the identical acknowledged pose. These are numerical Unity reference/render comparisons, not a claim of zero physical tracking error.
- Independent MuJoCo FK after the same recorded 29-joint initialization agrees with the recorded Unity measured FK to about 0.000067/0.000015 mm (floating-point/model agreement only).
- Recorded stationary LowState admission: 235 samples examined over four seconds, first ready at approximately **0.36 seconds**, then 214 synchronized samples after 21 settling samples.
- Real Unity serialization produces 2458-byte v5 input with a measurement and 1233-byte absent-state input; both are accepted by the Python decoder within its unchanged 8192-byte input limit.
- Runtime/test source hash changes during final full suites: none.

Early failed experiments and reports are retained in the evidence folder: the too-sensitive speed gate, the missing feedback-announcement replay step, and the metadata/mocked replay contract adjustments were corrected before final validation. Existing motion-quality, historical replay and safety thresholds were not loosened.

Evidence: `logs/test_results/measured_start_20261007_132608/`, including source preimages, final native Unity results, full regression logs/hashes, recorded admission/FK probe and subsequent deployment report. Original user logs are read-only.

## Operator verification and remaining limits

First use the current Editor auto-launch/Play path after closing any old session normally and allowing C# import/compilation. Run `START_G1_VR_TELEOP.bat --no-groot-actuation` with G1 and Quest connected. This invocation does not start GROOT; it does not terminate a GROOT owner already running elsewhere. No old standalone diagnostic executable was rebuilt.

The status can initially show `실측 초기화 대기 · 로봇 정지/수신 확인`. After stable initialization the pre-engagement spheres should coincide with the measured wrist references, within the permitted measured drift and rendering precision. The normal hand alignment/dwell follows. In this no-new-actuation test the physical arms, and therefore the measured rendered arms, need not follow the operator's hands; the target markers may move independently.

Physical XR appearance, live Balance-state admission, actual actuator handoff, motor wrist error, left-hand tracking loss, end-to-end delay and controlled shutdown have not been revalidated. During tracking, actual body motion can diverge from the frozen model body. Continuous measured feedback remains unimplemented and needs a separate design. Do not infer live safety, zero latency or motor convergence from these edit-mode and software tests; preserve the existing support/harness, emergency-stop and controlled-shutdown procedure.
