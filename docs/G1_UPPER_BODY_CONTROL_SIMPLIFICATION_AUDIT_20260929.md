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
