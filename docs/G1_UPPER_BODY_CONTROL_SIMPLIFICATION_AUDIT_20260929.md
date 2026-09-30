# G1 Upper-Body Control Simplification Audit — 2026-09-29

Baseline: f0b6828 on main. G1.zip full offline validation PASS.

Purpose: make the bilateral upper-body controller traceable by a person. This audit does not authorize a behavior change. It separates the canonical path into target mapping, IK objective, safety, return motion, and diagnostics; identifies dead, legacy, and preview-only logic; inventories material tuning parameters; and defines an ablation order.

## Main conclusion

The controller has two different complexity problems.

1. Maintainability complexity: Quest pose preparation, engagement, orientation heuristics, IK task construction, collision shaping and stop-tail validation are spread across several large classes/files and mutate the meaning of the target at multiple stages.
2. Compute complexity: the Mink/QP solve itself is not the dominant cost. Full future stopping-tail geometry validation on every accepted tracking tick is.

The current core path is roughly 3,700 lines across the main Unity/Python files. A person cannot currently answer why a joint moved a certain way by following one short path.

Target architecture:

    Raw Quest pose
      -> TargetMapper        # one coordinate/hand-frame conversion
      -> BilateralIK         # one QP, explicit objective terms
      -> SafetyEnvelope      # joint/velocity/accel/collision only
      -> Integrate q_next

    Return request
      -> ReturnPlanner       # separate from live tracking
      -> SafetyEnvelope
      -> Integrate q_next

Diagnostics must observe these stages, not modify them.

## Canonical world-frame path

Current SampleScene uses G1BimanualSimulationSender.useExistingScene=true, schema g1.bimanual.unity.sim.v4, frame unity_display_world_v1.

Actual IK pose source:

    OVRSkeleton wrist/finger bones
      -> G1ExistingHandTargetBinder.UpdateTrackedWrist()
      -> TrackedWristPosition
      -> DisplayedWristRotation (anatomical frame when valid)
      -> G1BimanualSimulationSender.ReadBinder()
      -> UDP position_m / quaternion_wxyz
      -> UnityCycle
      -> BASIS conversion
      -> ArmMotionPolicy
      -> shared bilateral QP

Important finding: ReadBinder sends TrackedWristPosition and DisplayedWristRotation directly. It does not send OperatorTargetDelta, BodyCompensatedTrackingDelta, MappedHandRotation, or target_transform.

Therefore these Binder calculations are not part of the current world-frame IK command itself:

- body-translation compensation
- movement_scale
- position_smoothing
- position_offset
- MappedHandRotation
- preview target_transform placement

They may still affect preview or engagement diagnostics, so split them out before deletion rather than assuming they are harmless.

## Clear dead or misleading structure candidates

### Python

BimanualSimulation.__init__ creates initial left/right FrameTask objects in self.tasks, uses only their keys to capture home_targets, then replaces self.tasks with ArmMotionPolicy.wrist_task. The initial FrameTasks are redundant.

self.constraints stores a DofFreezingTask, but the canonical call uses build_ik(... constraints=[]). The stored constraint is unused.

### Unity

use_reference_yaw is serialized but has no code reference beyond its declaration.

Current scene fixes position_smoothing=1, movement_scale=(1,1,1), position_offset=0, use_palm_center=false, apply_position=true and apply_rotation=true. Several of these are preview-only in the canonical IK path.

G1HeadLockedCamera.OnEnable overrides serialized values:
- scene lock_position=true, runtime immediately sets false
- scene head_tracking_stable_duration=0.15, runtime clamps to at least 1.0

The effective behavior is deterministic but the scene lies to a human reader.

### Legacy input filter

PairedHandFilter contains 60 ms position and 50 ms rotation filters for the old relative-frame path. In current unity_display_world_v1, UnityCycle.receive resets the filter on every accepted tracking packet, so smoothing is not active in the canonical world-frame path.

Do not delete historical replay support blindly. First isolate legacy-relative input from the canonical class.

## G1.zip activation evidence

Tracking diagnostic rows: 9,129.

| Heuristic | Left | Right | Interpretation |
|---|---:|---:|---|
| torso target projection | 0 | 0 | did not activate in recorded session |
| elbow assist | 0 | 67 | rare; right only in this session |
| wrist priority nonzero | 69 | 52 | rare |
| position-priority state | 703 | 1,373 | material |
| orientation cost scale < 1 | 761 | 1,460 | material |
| minimum orientation scale | 0.5 | 0.5 | dynamic rotation objective reduction occurred |

Checked braking occurred on 49 rows:
- QP infeasible: 4
- swept clearance: 42
- temporary tracking unavailable: 3

Orientation priority cannot be classified as dead from this recording. Torso projection and wrist/elbow helpers are stronger ablation candidates, but still need synthetic boundary tests.

## Runtime profile from exact G1.zip replay

Full replay:
- 46,570 state rows
- 7,837 input rows
- exact replay PASS
- profiler wall time about 61.2 s

| Function | Cumulative time | Notes |
|---|---:|---|
| UnityCycle.tick | 48.35 s | top-level tracking path |
| BimanualSimulation.step | 47.58 s | live IK/safety step |
| checked_stop_plan | 24.97 s | future stop-tail validation |
| clearance | 24.87 s | geometry safety queries |
| mj_geomDistance | 14.47 s | 10.9 million calls |
| nearest-pair distance | 8.17 s | geometry queries |
| ArmMotionPolicy.prepare | 4.34 s | all per-arm heuristic/task preparation |
| collision QP inequality construction | 3.54 s | Mink collision bounds |
| mink.build_ik | 2.58 s | QP construction |
| target projection | 1.19 s | ran every arm/tick despite 0 activation |
| wrist priority update | 1.14 s | heuristic |
| orientation priority update | 0.80 s | heuristic |
| elbow assist update | 0.62 s | heuristic |
| actual qpsolver call | 0.47 s | not the dominant cost |

Key point: the expensive part is not Mink solving IK. The major cost is geometry and proving a complete acceleration-bounded stopping tail every tracking frame.

The current live step also overlaps safety concepts: collision QP bound, collision braking headroom, joint-limit braking headroom, acceleration QP bound, then a full sampled future stop-tail check. This may be justified for safety, but it must be isolated behind one safety API so the IK code remains understandable.

## Parameters that influence upper-body behavior

### A. Quest/world alignment

- initial tracking-space alignment: once
- runtime stable-head requirement: effectively at least 1.0 s
- minimum head height: 0.4 m
- operator height above shoulders: 0.30 m
- operator forward offset: 0.05 m
- Omni body yaw: prescribed base yaw
- G1OmniBodyHeading CorrectInputPosition/Rotation: identity in current implementation

These alter the world frame seen by the arm target even though they are not IK gains.

### B. Engagement and tracking gate

- engagement distance: 0.07 m
- orientation tolerance: 30 deg, but orientation alignment is not required
- engagement hold: 0.35 s
- engagement position stability: 0.015 m
- engagement rotation stability: 10 deg
- engagement-frame initialization delay: 0.25 s
- wrist plausibility maximum speed: 5 m/s
- minimum wrist step allowance: 0.02 m
- tracking-loss grace before return: 0.35 s
- input freshness timeout: 0.75 s
- pinch hold before return: 0.5 s

These mainly determine whether a target is accepted or held.

### C. Target mapping

- Unity to MuJoCo basis: [[0,0,1],[-1,0,0],[0,1,0]]
- anatomical wrist frame from Middle1, Index1 and Pinky1
- skeleton wrist preferred
- world-frame packet converted once by BASIS
- prescribed base yaw rotates MuJoCo base before world target solve

Canonical rule should become: one wrist position, one wrist rotation, one basis conversion, one base pose. Any extra transform needs a named physical reason.

### D. IK objective

- control rate: 60 Hz
- wrist position cost: 8.0
- wrist orientation cost: 2.0
- posture cost: 0.04
- base FrameTask gain constant: 0.35
- effective tracking gain at 60 Hz: min(0.35, dt*1.0) ~= 0.01667
- LM damping: 1e-5
- build_ik damping: 1e-6
- proximal DampingTask cost: 0.25
- wrist DampingTask cost: 0.015
- ShoulderComfortTask cost: 0.6 per component
- shoulder comfort bands: roll 20 deg, yaw 45 deg
- ElbowClearanceTask cost: [8,8]
- elbow task gain: 0.6*dt ~= 0.01

These all shape motion even though they are not velocity or acceleration limits.

### E. Dynamic IK heuristics

Orientation priority:
- normal scale: 1.0
- position-priority target scale: 0.5
- collision constrained: clearance < 12 mm
- joint constrained: minimum margin < 5 deg
- elbow extension constrained: elbow lower-limit margin < 5 deg
- activate at position error >25 mm with elbow-extension constraint, or >80 mm with generic constraint
- release candidate: error <10 mm, or clearance >25 mm and margin >8 deg
- dwell: 0.3 s
- scale slew: at most dt per tick

Wrist priority:
- position window: 2-8 mm
- rotation normalization: 3 deg
- wrist joint margin window: 5-28 deg
- clearance window: 5-25 mm
- extra proximal damping: 5 * combined_weight

Shoulder yaw envelope:
- +/-90 deg around engage/reference posture
- stopping-speed factor: 0.8

Elbow assist:
- torso-front condition
- wrist position error >20 mm
- initial elbow <20 deg
- target lift up to reference +80 mm and at least 40 mm below shoulder

Torso target projection:
- expands torso boxes by wrist collision radius + 5 mm
- moves target position outside the box
- preserves requested orientation

### F. Hard and safety envelope

- proximal max joint velocity: 90 deg/s
- wrist max joint velocity: 180 deg/s
- joint acceleration: 90 deg/s^2
- hard checked clearance: 5 mm
- Mink collision minimum: 6 mm
- collision detection distance: 150 mm
- collision gain: 0.85
- elbow operational range override: 5-120 deg
- model joint ranges for all other joints
- hard joint-limit stopping factor: 0.8
- collision stopping-headroom coefficient: 0.25
- checked-stop swept substep: <=0.25 deg
- checked-stop horizon long enough to brake from max velocity at 90 deg/s^2

These are safety behavior and should not be removed merely because they are expensive.

### G. Return-only parameters

Return is a separate problem and should stay out of the live IK mental model.

- jerk: 1.28 rad/s^3
- acceleration: 90 deg/s^2
- velocity caps: same 90/180 deg/s
- right waypoint: [10,-35,0,70,0,0,0] deg; mirrored for left
- settle: 0.5 s
- maximum duration: 30 s
- maximum replans: 2
- near-hands threshold: 12 mm
- separation probe maximum: 10 s
- Ruckig synchronization disabled

There is currently no canonical G1 arm motor publisher. Physical motor Kp, Kd, torque/current limits, impedance and feed-forward torque are not part of the current upper-body command path.

## Classification

### KEEP — core semantics or safety

- one world-frame target mapping
- one bilateral wrist IK solve
- hard joint ranges
- velocity caps
- acceleration cap
- collision avoidance
- robust stop/brake behavior
- input/session/freshness/tracking validity
- return as a separate path

### REMOVE OR SPLIT FIRST — behavior-preserving cleanup candidates

- redundant initial BimanualSimulation self.tasks FrameTasks
- unused self.constraints
- unused use_reference_yaw
- misleading scene/runtime overrides in G1HeadLockedCamera
- legacy-relative PairedHandFilter separated from canonical world frame
- preview-only Binder compensation/scaling/smoothing separated from actual pose source
- constant canonical toggles currently fixed by scene and validator
- identity CorrectInputPosition/Rotation wrappers removed from command path

The first pass should preserve numerical output bit-for-bit or within the existing exact replay tolerance.

### ABLATE ONE AT A TIME — not immediate deletion

Recommended order:
1. torso target projection
2. elbow assist
3. wrist priority task
4. shoulder comfort task
5. shoulder-yaw comfort envelope
6. dynamic orientation priority

Reason: actual G1.zip activation frequency increases significantly by the time orientation priority is reached.

Each ablation must run:
- backend regression
- hardware regression
- G1.zip archive-validate --strict
- synthetic near-torso reach
- joint-limit reach
- inter-arm near-hands case
- return from difficult posture

Exact replay is expected to change once a real motion heuristic is removed. At that stage compare safety and tracking metrics rather than requiring historical q equality.

## Safety simplification problem

Current live step layers:

    Mink VelocityLimit
    + Mink CollisionAvoidanceLimit
    + custom zero-distance collision correction
    + acceleration QP bound
    + hard-joint stopping-speed bound
    + shoulder-yaw stopping-speed bound
    + collision stopping-headroom bound
    + full future checked_stop_plan

Do not remove checked_stop_plan first. Expose one interface:

    safe_velocity = safety.accept_or_brake(
        q=current_q,
        qd=current_velocity,
        proposed_qd=ik_velocity,
    )

Initially this interface can keep every existing check. Once the rest of the controller is simple, offline ablation can determine which safety constraints are redundant.

Potential later choices:
1. conservative: keep stop-tail, isolate it and optimize geometry/caching
2. simpler/faster: prove acceleration + joint braking + collision braking bounds establish the invariant, then replace the full future tail with bounded one-step/swept validation

Use option 1 for the structural refactor. Option 2 is a later engineering decision.

## Proposed file architecture

Unity:

    G1QuestHandPoseSource.cs
      raw tracking + anatomical frame + plausibility only

    G1BimanualEngagement.cs
      ready / engage / pinch / tracking-loss only

    G1BimanualSimulationSender.cs
      serialize already-defined targets; no target shaping

    G1HeadLockedCamera.cs
      startup world alignment only

    G1OmniBodyHeading.cs
      body yaw state only

Python:

    g1_bimanual_input.py
      schema / order / freshness; current world frame only

    g1_bimanual_target.py
      BASIS + prescribed base pose -> two SE3 targets

    g1_bimanual_ik.py
      task construction + one bilateral QP

    g1_bimanual_safety.py
      hard limits / braking / collision checks

    g1_bimanual_return.py
      return-only Ruckig state machine

The top-level loop should read almost like pseudocode and contain no hidden tuning math.

## Refactor gates

A behavior-preserving cleanup is accepted only if:
- working tree is clean except intended patch
- backend and hardware regressions pass
- G1.zip archive-validate --strict passes
- bimanual state/reason mismatch stays 0
- max q replay difference stays within the existing exact-replay tolerance
- no network or motor-output path is introduced

A behavior-changing heuristic deletion gets a separate commit and a separate before/after report.

## Recommended next action

Do not tune any new gain yet.

Start R1 behavior-preserving structural cleanup only:

1. remove proven dead Python members
2. make scene/runtime settings tell the truth
3. split canonical world-frame input from legacy-relative filtering
4. split Binder pose source from preview/engagement calculations
5. centralize current effective upper-body parameters into named read-only profiles
6. keep all existing motion and safety math numerically unchanged

After R1, a human should be able to follow one target from Quest wrist to QP to safety output without opening legacy/preview code. Only then begin heuristic ablation.

## R1a implementation result — 2026-09-30

Behavior-preserving structural cleanup completed:

- removed redundant initial BimanualSimulation.self.tasks FrameTasks
- removed unused self.constraints
- moved canonical absolute world-frame target math to g1_bimanual_target.py
- moved historical relative-frame filter/mapping to g1_bimanual_legacy_input.py
- current world-frame engagement no longer captures an unused relative pose origin
- centralized current effective tuning constants in immutable g1_bimanual_profile.py
- removed canonical-scene no-op Binder options: palm-center, apply position/rotation toggles, reference-yaw flag, movement scale, position offset and smoothing
- made G1HeadLockedCamera serialized defaults equal the already-effective runtime behavior: one-time alignment, no continuous position lock, 1.0 s stable-head gate
- preserved dormant old right-arm Unity sender/preview code for a separate cleanup because Unity semantic compilation is currently blocked by Package Manager IPC

Validation after the full R1a working tree:

- backend: 223/223 PASS
- hardware: 38/38 PASS
- G1.zip archive-validate --strict: PASS
- exact replay: true
- accepted/state/reason mismatch: 0 / 0 / 0
- maximum q difference: 2.00062189037453e-13 rad
- changed C# files: Roslyn syntax diagnostics 0

Unity Editor batch validation remains environmentally blocked before package initialization by UnityPackageManager IPC startup failure. The generated Assembly-CSharp.csproj is also stale and references four C# files already deleted before R1a, so its direct build failure is not evidence against the patch.

R1a deliberately did not remove or retune any live heuristic. The next structural step is to isolate/remove the dormant right-arm-only Unity sender and then place the existing safety calculations behind a named safety boundary before starting any heuristic ablation.

## R1b implementation result — 2026-09-30

The dormant single-right-arm Unity command path was removed after R1a established the canonical bilateral path.

- deleted `G1ExistingTargetUdpSender.cs` and its scene component
- removed `existingSender`/`target_sender` wiring from the bilateral sender and preview
- removed preview logic that depended on the old sender: command overlay, legacy feasible-target/session coupling, workspace-command diagnostics, and old transport error logging
- retained hardware/read-only display selection and the separate simulation-state receiver because they still serve display/inspection diagnostics independently of command output
- updated the Unity batch validator to validate the bilateral sender directly
- changed C# files pass Roslyn syntax parsing with 0 errors

No Python controller or live heuristic was changed in R1b. The next structural step is to put the existing live safety calculations behind one named safety boundary while preserving numerical behavior.

## R1c implementation result — 2026-09-30

The existing hard safety math is now behind one named `BimanualSafetyEnvelope` boundary in `g1_bimanual_safety.py`.

Owned by the safety boundary:

- Mink configuration/velocity/collision limits
- zero-distance collision witness correction
- collision stopping-headroom QP bounds
- acceleration QP bounds
- hard joint-limit stopping-speed bounds
- per-arm shoulder-yaw stopping bounds
- hard geometry clearance data/calculation
- acceleration-bounded sampled checked stopping tail

`g1_bimanual_sim.py` now reads as task preparation -> `mink.build_ik` -> `safety.constrain_problem` -> QP solve -> `safety.checked_stop_plan` -> apply command. Compatibility aliases/proxies (`sim.limits`, `sim.clearance`, `sim.checked_stop_plan`, geometry check data) remain because return logic, diagnostics and regression fault-injection tests already depend on them.

No safety formula or tuning value was intentionally changed. A historical 60 deg/s^2 replay regression initially exposed that the new module had captured the default 90 deg/s^2 profile independently; this was corrected by making the safety boundary share the simulation's exact profile instance. A later hard-clearance move initially bypassed the public `sim.clearance` fault-injection hook; checked-stop validation was corrected to call through that proxy while implementation ownership remains in the safety object.

Final validation after these corrections:

- backend: 226/226 PASS
- hardware: 38/38 PASS
- `G1.zip archive-validate --strict`: exact PASS
- accepted/state/reason mismatch: 0 / 0 / 0
- maximum q difference: `2.00062189037453e-13 rad`

R1 structural cleanup is now sufficient to start separate heuristic ablation work. Any removal of torso projection, elbow assist, wrist priority, shoulder comfort/yaw envelope, or orientation priority must be a behavior-changing experiment with its own before/after evidence; it must not be folded into structural cleanup.

## Heuristic ablation 1: torso target projection — removal ACCEPTED (2026-09-30)

This behavior-changing experiment removed only `ArmMotionPolicy._project_target_outside_torso`. All hard safety limits and every other motion heuristic remained active. Compatibility diagnostics remain present but now report `target_projected=false` and `target_projection_distance_m=0`, so historical logs can still be compared exactly.

### Ordinary recorded session

`G1.zip archive-validate --strict` after removal:

- exact replay PASS
- 46,570 state rows / 7,837 input rows
- accepted/state/reason mismatch: 0 / 0 / 0
- maximum logged q difference: `1.74527059471075e-13 rad`

The projection had never activated in this recording, so normal recorded behavior is unchanged.

### Static torso-intrusion comparison

Both arms were tested at targets 5%, 25%, 50% and 90% inside the former expanded torso exclusion box.

Projection ON:

- no blocked case
- no checked braking in this static depth sweep
- position-priority remained inactive
- it rewrote the requested target before IK

Projection OFF:

- no hard-clearance violation
- no blocked case
- shallow intrusion remained near the 6 mm collision constraint
- deeper impossible targets caused more checked braking and position-priority activity
- the raw operator target remained unchanged

This first comparison alone was not enough to justify deletion because projection reduced braking.

### Boundary-local comparison

A second experiment found the exact home-to-torso entry boundary and tested raw targets 1, 5, 10, 20 and 40 mm inside it.

With projection OFF:

- no blocked case on either arm
- no checked braking in these boundary-local cases
- minimum clearance remained about 6 mm
- raw targets were preserved exactly
- at 20–40 mm intrusion, orientation position-priority took over instead of hidden target rewriting

The hard collision/safety envelope therefore already performs the actual feasibility enforcement.

### Continuous torso-crossing comparison

A continuous target was moved from the home wrist through the torso to the opposite side and then back.

Both ON and OFF:

- remained out of blocked state
- respected the 5 mm hard checked clearance
- recovered back to the home wrist

Projection ON:
- left checked braking: 102 steps
- right checked braking: 67 steps
- left position-priority: 124 ticks
- right position-priority: 114 ticks
- maximum effective-target step: about **295.6–295.8 mm**

Projection OFF:
- left checked braking: 193 steps
- right checked braking: 178 steps
- position-priority: 557 ticks on each side
- maximum effective-target step: about **1.34 mm**

The ~296 mm discontinuity is the decisive failure of the projection approach. While the raw target moved continuously, the pre-IK projection could hold the effective goal on the current side of the torso and then jump to the opposite-side raw target as soon as it exited the exclusion box. That makes the target path substantially harder for a person to reason about than letting the safety layer reject/slow an impossible command.

### Deterministic randomized torso sweep

With projection forcibly OFF, 24 seeded torso-intrusion/recovery cases were tested across both arms with varied depth and lateral/vertical offsets.

Seed: `20260930`

Results:
- cases: 24
- hard-clearance violations: 0
- blocked cases: 0
- home-recovery failures: 0
- minimum observed clearance: **5.0357 mm**
- maximum checked-braking count in a case: 8
- maximum final home error: **1.338 mm**

### Regression after actual code removal

Targeted tests passed after the real code path was changed:

- motion-quality: 16/16 PASS
- marker feedback: 6/6 PASS
- safety-boundary: 4/4 PASS
- joint/boundary tests: 13/13 PASS
- near-hands sweep: 2/2 PASS
- staged return: 17/17 PASS
- recorded-session replay: 3/3 PASS
- `G1.zip archive-validate --strict`: exact PASS

### Final decision

Removal is accepted.

The reason is not that torso intrusion is harmless. It is that torso/body feasibility already belongs to `BimanualSafetyEnvelope`, which maintained hard clearance and recovery without target projection. The projection duplicated that responsibility by silently replacing the operator target and introduced a large discontinuity in a continuous crossing case.

The canonical contract is now:

`operator wrist target stays unchanged -> IK objective -> SafetyEnvelope constrains/brakes unsafe motion`

Repeated braking when the operator requests a physically impossible torso-penetrating target is explicit safety behavior and is preferable to a hidden pre-IK target rewrite. Further reduction of the resulting orientation-priority/braking activity, if desired, must be handled as separate heuristics or safety-policy work rather than by mutating the target.

## Heuristic ablation 2: elbow assist — removal REJECTED (2026-09-30)

The second experiment disabled only ArmMotionPolicy._update_elbow_assist. Projection, wrist priority, orientation priority, shoulder comfort, all limits and return behavior remained unchanged.

Recorded G1.zip result with elbow assist disabled:
- state rows: 46,570
- input rows: 7,837
- accepted/state/reason mismatch: 0 / 0 / 0
- exact replay: false
- maximum logged q difference: 0.38547881457045896 rad (about 22.1 deg)
- minimum sampled clearance: 5.5297 mm

The original log contains one contiguous right-arm assist interval, feedback_sequence 42272-42338 (67 ticks). In this interval:
- elbow angle moves from about 13.38 deg to the 5 deg operational lower limit
- orientation priority is already active at scale 0.5
- wrist priority is zero

Normal logged interval:
- right wrist position error mean: 95.71 mm
- minimum/mean clearance: 5.23 / 9.18 mm
- tracking-braking rows: 0

Elbow assist disabled:
- right wrist position error mean: 93.50 mm
- minimum/mean clearance: 5.53 / 7.31 mm
- new checked-braking steps: 18
- maximum joint divergence within the 67-tick interval: 7.83 deg

Interpretation: elbow assist is not a tracking-error optimizer. Disabling it slightly reduces mean wrist position error, but the arm path loses clearance on average and requires repeated checked braking. Across the full session the altered joint trajectory diverges by about 22 deg even though high-level state/reason transitions remain unchanged.

Conclusion: removing elbow assist would simplify code but push more work into the emergency braking layer and materially change the arm posture. Removal is rejected. Keep it as an explicit boundary-posture helper; future simplification may rename or relocate it, but it should not be removed without a replacement that preserves or improves clearance while avoiding the 18 added braking steps observed here.

## Heuristic ablation 3: wrist priority — removal REJECTED (2026-09-30)

This experiment disabled only ArmMotionPolicy._update_wrist_priority by keeping wrist_priority_weight at zero and the extra proximal damping task cost at zero.

G1.zip with wrist priority disabled:
- accepted/state/reason mismatch: 0 / 0 / 0
- current validation: PASS
- exact replay: false
- maximum logged q difference: 0.3643487350081593 rad (about 20.9 deg)
- minimum sampled clearance: 5.7881 mm
- maximum output acceleration remained 90 deg/s^2

Recorded activation was sparse:
- left: 69 ticks in two intervals
- right: 52 ticks in three intervals
- maximum recorded weight: about 0.406 left / 0.721 right
- activation occurred while orientation priority was inactive, so these two heuristics are not duplicates in the recorded cases

Rotation-only 45 deg ablation with wrist position fixed showed the intended effect clearly.

X-axis rotation:
- left proximal peak: 8.56 deg ON vs 15.87 deg OFF
- right proximal peak: 8.51 deg ON vs 15.75 deg OFF
- wrist rotation remained about 43 deg ON but only about 34 deg OFF

Z-axis rotation:
- left proximal peak: 2.99 deg ON vs 7.50 deg OFF
- right proximal peak: 3.50 deg ON vs 7.28 deg OFF
- wrist yaw remained about 44 deg ON vs about 43 deg OFF

Final position and orientation errors remained sub-millimeter / about 0.05 deg in both modes, and no checked braking occurred in these clean rotation-only tests. The main difference is motion allocation: without wrist priority, shoulders and elbows participate much more in a command that can be achieved mostly by the wrist.

Conclusion: this is not redundant damping. It encodes a useful kinematic preference: near an already-reached wrist position, hand rotation should preferentially use wrist joints instead of visibly moving the whole arm. Removal is rejected. Keep it, but document it as a wrist-rotation allocation preference rather than generic damping.

## Heuristic ablation 4: shoulder comfort task — removal REJECTED (2026-09-30)

Shoulder comfort was disabled by zeroing only the ShoulderComfortTask contribution. Other IK preferences and all limits remained active.

G1.zip result without shoulder comfort:
- accepted/state/reason mismatch: 0 / 0 / 0
- current validation: PASS
- exact replay: false
- maximum logged q difference: 0.9309293196700652 rad (about 53.3 deg)
- minimum sampled clearance: 5.1206 mm
- maximum output acceleration remained 90 deg/s^2

Synthetic 12 cm reaches show when the task matters:
- forward reach: ON and OFF were identical; shoulder roll/yaw stayed near 1.2 / 3.25 deg
- outward reach: ON and OFF were identical; shoulder roll/yaw stayed near 14 / 13 deg
- upward reach: the comfort bands became active

For the upward reach on both arms:
- ON: shoulder roll peak about 27.43 deg; yaw about 12.56 deg
- OFF: shoulder roll peak about 49.78 deg; yaw about 54.77 deg
- ON final wrist position error: about 38.62 mm
- OFF final wrist position error: about 30.71 mm
- no checked braking occurred in either mode

Interpretation: the task is dormant for ordinary reaches inside its band. For a difficult high reach it deliberately trades about 8 mm of wrist tracking accuracy for a much less extreme shoulder posture. It is therefore not redundant with the main wrist task or generic posture cost.

Conclusion: removal is rejected. Keep it as an explicit shoulder-posture preference. Its current name is appropriate; future tuning may revisit band/cost values, but that is a separate behavior decision from code simplification.

## Heuristic ablation 5: shoulder-yaw envelope — keep as isolated fallback (2026-09-30)

The +/-90 deg shoulder-yaw stopping envelope was removed experimentally by returning no yaw-bound rows from each arm policy.

The model hard shoulder-yaw range is about +/-150 deg, so the envelope is not mathematically identical to the hard joint limit.

G1.zip with the envelope disabled:
- exact replay: PASS
- accepted/state/reason mismatch: 0 / 0 / 0
- maximum logged q difference: 1.745270594710746e-13 rad
- logged shoulder yaw stayed roughly within -21..42 deg left and -46..45 deg right

Additional targets were generated from valid configurations with shoulder yaw at 100 deg and 120 deg. With the current posture and shoulder-comfort objectives enabled, IK chose equivalent solutions around 43-45 deg shoulder yaw. Envelope ON and OFF produced identical joint trajectories, errors, clearance and braking in these tests.

Conclusion: no current test demonstrates that this envelope changes normal behavior. However it remains an independent fallback because the model hard range extends to +/-150 deg. Unlike the earlier spaghetti structure, it is now isolated inside the named safety boundary and adds only two simple QP rows per arm. Removing a conservative fallback with no demonstrated runtime or maintenance benefit is not justified. Keep it inside SafetyEnvelope; do not treat it as a user-facing tuning heuristic.

## Heuristic ablation 6: dynamic orientation priority — removal REJECTED (2026-09-30)

The final planned heuristic ablation forced orientation priority to remain at scale 1.0, disabling the position-priority state machine while leaving every other task and limit unchanged.

G1.zip without dynamic orientation priority:
- accepted/state/reason mismatch: 0 / 0 / 0
- current validation: PASS
- exact replay: false
- maximum logged q difference: 0.3525696625646579 rad (about 20.2 deg)
- minimum sampled clearance: 5.1361 mm

The recorded log contains substantial activation: 761 left-arm ticks and 1,460 right-arm ticks.

Long right-arm active interval, feedback_sequence 38327-39420 (1,094 ticks):
- position error mean: 100.04 mm ON vs 101.44 mm OFF
- rotation error mean: 7.61 deg ON vs 4.44 deg OFF
- no checked braking in either case
- clearance remained similar

This confirms the intended trade: position priority deliberately allows more orientation error to reduce position error.

Boundary-heavy right-arm interval, feedback_sequence 42196-42406 (211 ticks):
- position error mean: 69.93 mm ON vs 74.25 mm OFF
- rotation error mean: 30.30 deg ON vs 28.99 deg OFF
- normal checked-braking rows: 0
- priority disabled checked-braking steps: 44
- minimum clearance: 5.23 mm ON vs 5.14 mm OFF

Conclusion: in ordinary constrained motion the trade can look modest, but near the hard boundary the state machine prevents repeated emergency braking and keeps position tracking better while intentionally giving up some rotation accuracy. Removal is rejected.

## Heuristic ablation summary

| Component | Removal result | Decision |
|---|---|---|
| torso target projection | hard boundary still safe, but clearance margin collapses and braking rises | KEEP as target-feasibility guard |
| elbow assist | slightly lower wrist error OFF, but lower mean clearance and 18 extra braking steps in active interval | KEEP as boundary-posture helper |
| wrist priority | OFF roughly doubles proximal motion during wrist-only rotation | KEEP as wrist-rotation allocation preference |
| shoulder comfort | dormant in normal reach; OFF produces about 50-55 deg shoulder roll/yaw in high reach | KEEP as shoulder-posture preference |
| shoulder-yaw +/-90 deg envelope | no current trajectory effect, but independent fallback inside +/-150 deg hard model range | KEEP inside SafetyEnvelope |
| dynamic orientation priority | OFF improves rotation slightly but worsens position and causes 44 extra braking steps in boundary interval | KEEP as constrained-position priority |

The ablation series did not find a live heuristic that can be deleted without losing a deliberate behavior or moving more work into emergency braking. The simplification gain therefore comes from the R1 structural separation, removal of dead/legacy paths, explicit naming, and central parameter ownership—not from deleting these remaining behaviors.
