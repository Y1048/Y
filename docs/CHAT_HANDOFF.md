# G1 Teleop Project Chat Handoff

## 2026-09-18 session report and near-hands return v2

Read [near-hands return v2](BIMANUAL_NEAR_HANDS_RETURN_20260918.md) and
[session reporting](BIMANUAL_SESSION_REPORT_20260918.md). The report tool selected the latest
real operator log behind newer headless smokes and exposed a historical return BLOCKED at seq 697.
The preserved fixture now triggers a v2 path: checked stop -> one-arm separation -> existing safe
waypoint -> home -> settle. Original/mirrored cases choose left/right respectively and both finish
in 510 ticks with >=5.696 mm sampled clearance. Existing normal returns keep the old direct route.
Report strict exit propagation, EOF latest scan, malformed-row handling and state/reason counting
are regression-tested. Current new logs must show return_policy=bimanual_staged_return_v2.
Simulation only; 5 mm hard clearance/0.25-degree swept checking remain unchanged.
Final isolated-source and installed-runtime suites both pass 89/89. A trigger-specificity regression
keeps near-hands disabled at 6.769 mm global / 85.631 mm inter-arm clearance. Runtime backup:
`logs/backups/bimanual_near_hands_return_20260918_210946/`; 385 protected files were unchanged.
The headless BAT smoke used loopback port 57287, not production port 5020.

## 2026-09-18 performance micro-optimization stop point

Read [performance stop point](BIMANUAL_PERFORMANCE_STOP_POINT_20260918.md).
No code after `1e28597` was accepted. Squared sphere masking had zero decision mismatches but
no reproducible full-replay gain; hybrid AABB and small-distmax variants were slower/inconsistent.
Early unsafe-pair exit saved just 0.0133% of exact pair calls. Keep the current sphere broadphase
and safety sampling unchanged. Future performance work must be architectural and independently
prove identical sampled decisions, zero-distance handling, Quest replay and reproducible A/B gain.

## 2026-09-18 conservative sphere broadphase

Read [sphere broadphase validation](BIMANUAL_PERFORMANCE_SPHERE_20260918.md).
Stopping-tail threshold checks now reject certainly distant collision pairs with bounding
spheres enclosing each local geom AABB; surviving pairs still use exact geometry distance.
No clearance/sweep/motion limit changed. Recorded + random exact-distance rechecks found
zero bad exclusions. Quest replay q remains identical at 5.032 mm minimum clearance.
Clean detached suite 77/77 PASS; runtime targeted 16/16 PASS. A/B p95 mean improved
20.902 -> 17.300 ms under the same host load. Parallel session-report work was preserved.

## 2026-09-18 clearance kinematics optimization

Read [second clearance optimization](BIMANUAL_PERFORMANCE_KINEMATICS_20260918.md).
Normal sampled distance checks now use `mj_kinematics`; exact zero distance alone promotes
to `mj_fwdPosition` and the existing robust contact/probe path. All collision margins,
sweep samples and motion limits remain unchanged. Quest replay q is still identical.
Repeated A/B p95 mean: 15.055 -> 12.274 ms; source/runtime suites 76/76 PASS each.
Two files installed with backup, 277 protected files unchanged, BAT smoke passed.

## 2026-09-18 clearance performance optimization

Read [performance/clearance validation](BIMANUAL_PERFORMANCE_CLEARANCE_20260918.md).
Profiling the confirmed Quest replay showed checked stopping-tail clearance checks
were the main tracking cost; QP solve itself averaged about 0.044 ms. Clearance now
uses `mj_fwdPosition` instead of full `mj_forward`, without changing collision samples,
5 mm hard clearance, motion/return policies, or speed/acceleration bounds.
500 random poses matched full-forward distance/pair/contact results exactly. Quest replay
q remained identical. Direct old/new p95: about 16.42 -> 14.63 ms; source/runtime 74/74 PASS.
The user process was left running; the installed optimization loads on next Python start.

## 2026-09-18 Quest pinch/re-engage confirmed

Read [Quest confirmation and replay](BIMANUAL_QUEST_CONFIRMED_20260918.md).
The user confirmed the current Quest behavior works. The same session log shows
two pinch staged returns with one successful re-engage between them. A compact
recorded fixture replays 2,927 state ticks with 0 rad max logged-q difference,
5.032 mm minimum sampled clearance and the 60 deg/s^2 output acceleration bound.
Source and runtime bimanual suites: 73/73 PASS each. This is Quest simulation confirmation,
not physical G1 validation or a claim of continuous host-side 60 Hz timing.

## 2026-09-18 pinch re-engage and startup follow-up

Read [re-engage/startup validation](BIMANUAL_REENGAGE_STARTUP_20260918.md).
A real BimanualSimulation/UnityCycle regression now covers motion, pinch return,
staged waypoint/home/settle, active-only rejection, inactive rearm and re-engage.
Source bimanual suite: 71/71 PASS; return suite: 11/11 PASS.

The existing leave-zone release condition is now a testable production helper;
592 engage/leave combinations and 17 backend-generation/order cases passed after
a full Unity-reference C# compile with zero errors. Unity was open, so this
semantics-preserving C# refactor was not hot-copied into the runtime project.

Fresh MuJoCo 3.12 imports (10) took about 0.201-0.268s and five headless full
startups took about 1.196-1.277s. The earlier intermittent long import delay was
not reproduced and remains unexplained. No new Quest or physical G1 validation.

## 2026-09-18 observed staged-return replay and laptop path deployment

Read [observed run validation](BIMANUAL_OBSERVED_RUN_20260918.md).
Added a selected recorded-input fixture and two regression tests covering
3,433 state ticks through tracking-loss braking and staged return. The source
recording's five Python hashes match `7e74219`; replayed q matches exactly.
Observed return: 6.063s recorded time, 5.75s simulation time, waypoint/home/
0.5s zero-speed settling, no replans. Minimum sampled bilateral clearance was
about 5mm, not generous margin. No new comfort, re-engage, or physical validation.

Installed the nine existing Windows path patches into the laptop Desktop-folder
project after baseline checks and backup; preserved 508 other code/scene files.
Four actual BAT path-only checks passed. No Unity, robot, DDS, APK, or compiler
execution. Separate desktop deployment remains unverified. An auxiliary engine
import stalled again; its interrupted attempt is not counted as a pass.


## 2026-09-18 staged bimanual return restored on the same laptop

Read [return parity and validation](BIMANUAL_RETURN_PARITY_20260918.md).
The reported return regression was a different return implementation, not reduced
speed caps in the preceding boundary fix. Tracking retains the shared QP and
motion policies. Return now uses the original right-arm Ruckig profile/waypoint,
mirrored to the left, then home and 0.5s at zero speed before READY. Every output
keeps bilateral geometry and checked stopping-tail validation.
Source/runtime suites: 68/68 each. Same-start 60Hz durations: 10.733 -> 5.933s,
9.833 -> 5.350s. Latest recorded prefix replay and actual BAT startup passed.
Seven files installed with backup, 363 protected files unchanged. No Unity/C#
edit, user process restart or physical G1 control. New return Quest feel remains
unverified. This is historical v1 parity evidence. Current restarted Python should report return_policy=bimanual_staged_return_v2.

## 2026-09-18 bimanual boundary fixes installed (simulation only)

Read [boundary fixes and verification](BIMANUAL_BOUNDARY_HARDENING_20260918.md).
Short tracking loss now consumes checked braking commands, with output qpos
continuity and zero-speed READY checks. Known solver errors use the tail or
BLOCKED; malformed JSON is rejected before updating the cycle. Engage origins
use the filter's normalized quaternion. New backend identity/start ordering and
feedback sequence reset the C# calibration and reject delayed/old feedback.

Source and installed-runtime suites: 58/58 PASS each. C# compilation with actual
references, 17 backend-order cases and 576 engage combinations passed. Nine
files installed with backup; 604 protected files and the scene/right-arm policy
unchanged. Stop Play and the old Python normally, then restart both together;
check boundary_policy=bimanual_boundary_v1 in the new run log.

Intermittent engine-import delay remains unexplained; stage timestamps are now
logged. A stopped auxiliary test is not counted as passed. Quest feel, full
Unity Play restart and physical G1 behavior have not been tested.

**최신 GPT 인계 요약: [GPT_BIMANUAL_HANDOFF_20260918.md](GPT_BIMANUAL_HANDOFF_20260918.md).**
아래 기록은 역순 작업 이력이며, 과거의 미해결 표시는 이후 수정 결과와 구분한다.

## 2026-09-18 bimanual motion corrections installed on the same laptop

Read [motion correction validation](BIMANUAL_MOTION_CORRECTION_20260918.md).
Per-arm motion preferences now restore target-approach braking, wrist priority,
shoulder comfort, torso projection, elbow assistance and reversible orientation
priority inside the shared 14-DOF QP. The original single-right-arm controllers,
Unity scene/C# and exact checked stopping-tail function remain unchanged.
Paired input filtering and log-only runtime/policy diagnostics were added.

Final installed-runtime suite: 45/45 PASS. Actual BAT headless idle smoke: PASS.
Selected reported-motion replay: 1,404 ticks, 667 tracking ticks, one checked
braking tick, >=19.69mm sampled clearance, return to ready. No Quest verification
of the corrected behavior yet; no physical G1 control. Old user Unity/Python
processes were not restarted: stop/restart normally before comparing behavior.
Backup: laptop runtime logs/backups/bimanual_motion_install_20260918_114658/.

## 2026-09-18 environment clarification and runtime checkpoint

- User clarification: all work from the beginning through now has remained on
  the same laptop. No additional development on a separate desktop PC has started.
- `C:/Users/user/Desktop/G1_Teleop_Project` is the laptop's Windows Desktop-folder
  runtime project. The clean source worktree under `Documents/Codex/.../g1-integration`
  is on the same laptop. Folder names and device hostnames do not establish a PC migration.
- Runtime engine parity fix `d52c2aa` and its 29/29 offline test record are in the
  source worktree; that fix has not been copied into the laptop's runtime folder.
  See [runtime validation](BIMANUAL_RUNTIME_VALIDATION_20260918.md).
- Latest Quest feel remains unverified. Historical desktop-migration instructions
  below are plans/reference material, not evidence that desktop development occurred.

## 2026-09-18 coupled IK checked braking (offline verified)

- Fix previous next-step-only planning: each accepted joint velocity now has
  a discrete stopping tail checked before committing the step. Every tail
  step respects the existing 60 deg/s^2 acceleration, 90/180 deg/s speed,
  joint ranges, frozen non-arm pose, and >=5mm sampled clearance.
- If a subsequent QP is infeasible or its stopping tail invalid, follow the
  previously checked tail instead of resetting velocity or latching BLOCKED.
  At zero velocity retain its checked hold and retry tracking on later input.
  No valid cached tail still fails closed. This assumes fixed kinematic
  geometry; it is NOT a physical braking controller or continuous collision proof.
- World-AABB separation excludes only certainly distant collision pairs;
  remaining pairs still use the existing robust geometry distance. 120 seeded
  poses match the full collision decision. No XML/mesh limits were changed.
- Recorded Quest/Unity fixture committed with provenance: original sequence
  607 QP failure (+2.188s) now passes. 209 ticks, 24 checked-braking ticks;
  joint range/speed/acceleration/clearance checked throughout. This is NOT
  measured G1 data. Original laptop source JSONL preserved.
- Executed: `py -3.11 -m unittest discover -s backend/tests -p "test_bimanual*.py"`
  with isolated MuJoCo 3.12.0 PYTHONPATH: 17 PASS, 13.213s total.
  Replay tick p95 13.34ms / max16.14ms on this run, not a hard real-time guarantee.
- Original project installed selectively with backup. Current Python process
  retains old code: stop simulation/Unity Play and reopen START_BIMANUAL_UNITY_SIM.bat,
  then Play. Quest feel remains unverified. No G1/SSH/DDS/motor execution.


## 2026-09-18 sequential engagement and recorded IK failure

- User finds simultaneous stable hand alignment uncomfortable. Each hand now
  remembers completed stable alignment for 4 seconds. Both current alignment
  gates and tracking must still pass at engage. Pinch, loss, stale feedback,
  return/rearm invalidate memory. Neutral origins are captured together.
- Compiled Unity/Meta references PASS; 576 engage combinations plus memory,
  invalidation, expiry and final current-position gate checks PASS. No Quest
  verification of this UX yet. Runtime selectively backed up and installed.
- Latest laptop recording unity_20260918_094323_0712614.jsonl, session
  2a9d0dc13c574a208a64b4c50f1ab6de: engage sequence 529, then sequence 607
  qp_infeasible at +2.188s. Unity feedback stayed fresh; this was IK BLOCKED,
  not a UDP disconnect. Exact event replay reproduces the same sequence.
- Offline diagnostic removing only 28 acceleration inequalities makes that
  QP feasible. At failure clearance .020925990836630545m; maximum joint
  velocity .9528789799160351rad/s. This does NOT establish collision or
  physical safety and does not justify removing acceleration constraints.
- Solver is unchanged; interrupted tracking REMAINS UNRESOLVED. Next work:
  implement and regression-test checked braking viability for coupled IK,
  preserving range/clearance and using this replay. Do not claim fixed tracking.
- Replay script/report live under logs/test_results/same_scene_bimanual/ in
  source worktree; source recording remains laptop-local, not in GitHub.


## 2026-09-18 camera-attached bimanual status strip

- Replaced paired sender floating TextMesh with a world-space UI strip attached
  to the existing camera PiP bottom edge: 6 canvas-unit gap, 48-unit height.
  Two columns show Korean left/right tracking/alignment/progress/ready status;
  lower row shows concise cycle state. No detailed distances in headset UI.
- Child canvas sorting order is camera order + 1; text is rendered after
  background. No overlap with video rectangle. Headset-relative fallback uses
  camera default geometry if PiP is absent, without creating a camera receiver.
- Hide duplicate preview TextMesh in bimanual mode. Original right-arm mode
  keeps existing display. Engage logic, initial pose and robot paths unchanged.
- Actual Unity/Meta-reference C# compilation PASS; diff whitespace check PASS.
  Installed into original project with selective backup. Quest visual readability
  and occlusion verification remain pending. Stop Play and restart after compile.


## 2026-09-18 marker parity and engage audit (Quest success NOT verified)

- Previous repair was compile-verified only. User reports engage still fails.
- Confirmed cyan wrist diameter mismatch: right .060m, left .025m. Right
  requested target was also cyan, unlike left green. Now both tracked markers
  use .060m and targets .055m, with white/yellow alignment and green active.
- Latest runtime capture unity_20260918_094323_0712614.jsonl and Editor.log
  show tracked hands but no demonstrated simultaneous completed alignment.
  Do not claim a proven single cause for failed engage or a successful fix.
- Remove extra simultaneous .35s timer in existing-scene mode; both binders
  still require their configured stable hold, valid tracking and alignment.
  Fresh ready feedback, released pinch, and rearm conditions remain required.
- Add per-second combined [BIMANUAL ENGAGE] diagnostics for backend freshness,
  pinch, rearm and both alignment errors/progress. Explicit pinch instruction.
- Actual Unity/Meta reference compilation PASS; compiled sender CanEngage
  executed under Mono: 576 boolean/progress combinations PASS. Shared marker
  diameter check PASS. This is not Unity Play/Quest end-to-end verification.
- Installed two C# changes selectively in original project with backup.
  No robot, SSH, SDK/DDS or motor execution.


## 2026-09-18 same-scene engage/left-marker repair

- User capture `unity_20260918_093446_2442044.jsonl`: 800 inputs; 625 had
  both hands tracked, none engaged; backend remained ready. Saved left binder
  had reference_transform=0 and head_camera_alignment=0, unlike the right binder.
- Explicitly wire both references in installer and runtime Awake to repair
  existing scenes on next Play. Add missing left cyan tracked-wrist marker,
  green left target and per-hand alignment distance/hold status.
- Keypad bootstrap now runs AfterSceneLoad so the bimanual marker is present
  before its guard is evaluated; earlier log showed unwanted keypad startup.
- Unity/Meta DLL-reference compilation passed. Quest retest and actual
  runtime bootstrap suppression remain unverified; no G1/robot execution.


## Same-scene bimanual extension (2026-09-18, current)

- User rejected the separate-scene workflow. Use existing SampleScene menu
  `G1 Teleop/Arms/Use Both Arms (Simulation)` or `Use Original Right Arm` with
  Play stopped, then save. No separate project/scene is needed.
- Current right-hand binder settings are reused; left binder clones them.
  Existing preview/head alignment/camera remain. Paired joint feedback now
  drives both arms of the existing official rig, not just a PC MuJoCo window.
- Original right-arm mode bypasses all new preview/input branches. The coupled
  14-axis IK remains a candidate: original one-arm elbow/torso/orientation
  refinements have NOT all been generalized. Do not claim identical IK behavior.
- See `docs/BIMANUAL_SAME_SCENE_20260918.md`. Local source installation is backed
  up; menu/Quest Play is not auto-executed. No physical G1 action.

## 2026-09-18 original laptop Desktop-folder project: bimanual simulation installed

- Selectively copied the paired Unity/MuJoCo simulation files from source commit
  `0a83dc3` into the laptop's existing Desktop-folder project at the user request.
- Backup: `logs/backups/bimanual_install_20260918_090952/`: tracked dirty diff,
  pre-install copies of affected existing files, original SampleScene, hashes.
- Keypad Install/Awake received only the two simulation-scene guards; no broad
  overwrite/reset/pull of this dirty worktree. Original SampleScene hash unchanged.
- Runtime checkout: 13 offline/generated/loopback tests passed on MuJoCo 3.12.0.
  Open Unity recompiled Assembly-CSharp and Assembly-CSharp-Editor; both new types
  were found in the resulting DLLs. Scene creation and Quest Play remain untested.
- Use the existing Unity project menu G1 Teleop -> Create Separate Bimanual
  Simulation Scene, then tools/START_BIMANUAL_UNITY_SIM.bat. G1 is not used.


> **Absolute G1 mutation rule:** Never create, delete, rename, move, or modify any file on the G1; never run a program that can create a log, publish a command, change a service or mode, or otherwise mutate G1 state without the user's explicit approval for that exact action. Inspect source before running diagnostics. Remote-to-local copy is allowed only when it reads existing G1 files and writes exclusively to the Windows project.

Last updated: 2026-09-18

## Unity paired-hand simulation input (2026-09-18)

- Laptop work in clean sync checkout: added `G1BimanualSimulationSender`,
  separate-scene editor menu, `g1_bimanual_unity_sim.py`, and
  `tools/START_BIMANUAL_UNITY_SIM.bat`. See `docs/BIMANUAL_UNITY_SIM_20260918.md`.
- Fixed localhost UDP 5020 by default; distinct simulation-only schema. Both
  hands engage together; either-hand pinch for 0.5s returns both; fresh ready
  and a new inactive/active edge permit re-engage. No G1 connection.
- Added an opt-in scene marker guard to keypad Install/Awake, because the
  existing automatic UDP 5016 sender would otherwise run even in the new scene.
  Existing right-arm IK, original scene, physical paths and dirty runtime stay untouched.
- MuJoCo 3.12.0: 13 generated/unit/loopback tests passed. C# compiled against
  installed Unity/Meta assemblies. Full Unity import/scene generation/Play,
  actual Quest input and runtime bootstrap suppression still need verification.
- The new scene is generated through the menu, not checked in. Logs are PC-local.
  Do not describe this source-level connection as a completed Quest/G1 trial.

## Bimanual simulation candidate (not Unity or G1 connected)

- Added isolated `MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py` and
  `tools/START_BIMANUAL_SIM.bat`: coupled 14-axis IK, both hand collision meshes,
  bilateral/body collision constraints, sampled-path guard, constrained home return.
- Existing right-arm controller, runtime checkout, Unity, UDP, G1, gains and model
  assets remain unchanged. This is a new kinematic candidate, not a replacement
  for every right-arm posture refinement or a physical stopping controller.
- Generated tests: 6 passed on MuJoCo 3.11.0 and 6 on 3.12.0. A 1,800-tick demo
  reached ready after return. GUI and live Quest two-hand input remain untested.
- Read `docs/BIMANUAL_SIM_20260917.md` for launcher, paired JSONL schema,
  collision-check limitations, and the remaining Unity two-hand integration.

## Omni raw and mapped time-series CSV recorder

- Run `tools\RECORD_OMNI_TIMESERIES_CSV.bat`. Optional arguments are total
  duration and preparation delay in seconds; defaults are `120 20`.
- Each `g1.omni.timeseries.v1` row records one received Omni sample with the
  same timestamp and sequence: raw `mx`, `my`, `arm_yaw_deg`,
  `omni_yaw_rate_deg_s`; mapped `vx`, `vy`, `yaw_rate`; relative
  `yaw_diff_deg` and per-sample `yaw_step_diff_deg`; calibration state; and the
  exact source JSON in the final column.
- CSV files are written to `logs/test_results/omni_timeseries/`. The launcher
  uses `--dry-run`: no G1 discovery, UDP output, SDK, DDS, or motor command.
- Offline verification passed: 12 mapper/schema unit tests, a fake WebSocket to
  discovery/UDP test with 10 accepted command packets and final zero, and a
  loopback fake-G1 CSV test with 72 rows.
- A user-operated Omni capture was subsequently recorded on the laptop at
  `C:\Users\user\Desktop\G1_Teleop_Project\logs\test_results\omni_timeseries\omni_timeseries_20260917_171846.csv`
  (10,344 rows; 7,880 calibrated rows). The raw CSV and its generated interactive
  visualization are laptop-local artifacts and are not tracked by Git, so a
  desktop checkout of this branch will not contain them. Copy them separately
  if the desktop must inspect the exact same recording. Code, tests, schema and
  these handoff notes are in Git.
- The default mapped yaw-rate ceiling was raised from `0.8 rad/s` to
  `1.6 rad/s` (about `91.7 deg/s`) after the user-operated recording showed
  sustained clipping in both turn directions. The limit remains finite; this
  is a PC Gateway setting change and was not run against a physical G1.

## Current method audit: neither current behavior nor priority prototype accepted

- User requested a rigorous review instead of further tuning followed by VR
  feedback. Read `docs/IK_WRIST_ARM_METHOD_REVIEW_20260917.md` before more edits.
- Source/runtime remain at the `6c32983` tracking implementation, SHA256
  `fe0ab3273bb6a470fe5d982aa9d00faa7b106e25358ff5d610b7f806444b5ba3`.
  No controller, launcher, model, gain, or hardware file was changed this turn.
- Latest16:39 CSV: inferred wrist penalty disabled for654/669 active samples
  (97.8%) because remaining position error>=8mm. At17.50-18.50s target position
  range1.56mm/rotation10.25deg nevertheless recruits shoulder roll/yaw6.04/6.43deg,
  with>=36.5mm clearance. Earlier position backlog also requires some valid
  proximal motion; do not freeze the arm based on stationary input alone.
- Independent generated hold test: current posture objective causes4.74/6.80deg
  proximal motion during2s of an unchanged nonneutral wrist target, still moving
  at2.05/2.97deg/s afterward. This masks fine-motion intent and was missing from
  the previous neutral-pose regression suite.
- Local model FK confirms pitch-to-yaw offset46mm; neutral wrist pitch origin
  translation Jacobian norm=.046m/rad. Fixed arm plus30deg wrist pitch moves the
  tracked origin23.8mm. Do not silently change the task frame to hide this error.
- New OFFLINE ONLY `prototype_mink_task_priority.py` is a research comparison:
  wrist6D primary, then minimize proximal velocity while preserving linear Jv.
  It greatly improves some precise rotations but regresses cumulative shoulder
  spread/elbow lift on full records. NOT approved for launcher/runtime use.
- New `audit_mink_precision.py` fixes31 generated scenarios and predeclared
  engineering criteria. Final matching-engine MuJoCo3.12.0 results:
  current24pass/7fail; prototype27pass/1fail/3inconclusive. accepted=false BOTH.
  Each run9,660test+3,720prelude ticks with no geometric, frozen-joint, velocity
  or acceleration violations. Data are simulated; no measured G1 validation.
- Complete reports/hashes are committed under
  `docs/validation/ik_method_review_20260917/`.3.11 exploratory results remain in
  ignored logs. Generated scenario comparisons have controller-dependent prelude
  poses; same-CSV replay is separately labeled. No failed results were removed.
- Next implementation must preserve fine task motion and assess cumulative
  posture/continuity, not just instantaneous proximal speed. Do not request
  another VR trial for the rejected prototype or raise thresholds to pass it.
  More precise release criteria/remaining coverage are listed in the review.

## Current excessive elbow spread correction (after the 16:30 simulation)

- User clarified the problem is excessive sideways/upward elbow spread, not
  failure to lift. The newest closed CSV is
  `mink_v5_right_arm_20260917_163007_600.csv` (601 active samples). Recorded
  shoulder yaw reaches 90 degrees, shoulder roll reaches -58.2 degrees, and
  final wrist position error is 15.9 cm. These are simulated model values,
  not actual G1 measurements or evidence of the human elbow position.
- Tested removing/weakening the fixed elbow Y/Z preference. Alone this did
  not eliminate the 90-degree yaw excursion. A global posture penalty reduced
  excursion but could suppress the useful front lift. Those sweep candidates
  were not copied to the runtime; local reports remain under `logs/test_results`.
- Added `ShoulderComfortTask`: a soft squared excess-angle objective, with
  zero error/Jacobian within engage-relative roll +/-20 and yaw +/-45 degrees.
  Cost is 0.6 and gain follows the scheduled wrist task gain. Beyond those
  bands the solver prefers less shoulder roll/yaw but can still cross them
  to reach the target. This is not a new hard joint limit or a motor PD gain.
  Existing +/-90 yaw envelope, collision constraints, wrist priority, velocity,
  acceleration, elbow reference, return logic and model limits are unchanged.
- Same-input A/B replay versus `8921f42`, newest CSV, 1,158 ticks:
  shoulder yaw max 90.0 -> 77.98 degrees; roll excursion max 37.98 -> 34.95
  degrees; final elbow lift 6.81 -> 5.15 cm. Peak elbow lateral distance from
  shoulder decreases only 19.86 -> 19.39 cm; final lateral distance increases
  10.70 -> 10.94 cm. Do not claim every pose is less spread. Wrist position
  p95 remains 13.87 cm and final two-second rotation error 14.76 -> 14.72
  degrees. Two checked braking steps, no hard holds or acceleration violations.
- Earlier front-target CSV (15:58), 1,529 ticks: shoulder yaw max 90 -> 80.28
  degrees, roll excursion 53.65 -> 40.79 degrees, maximum elbow lift
  11.72 -> 7.96 cm. Position p95 20.38 -> 19.39 cm; final rotation error
  2.98 -> 2.93 degrees. All steps accepted, no acceleration violations.
  Reports: `logs/test_results/elbow_comfort_latest_20260917.json` and
  `logs/test_results/elbow_comfort_front_20260917.json`.
- Added a finite-difference Jacobian and neutral-band regression. Existing
  tests preserve the front-lift, non-ratcheting, return and stationary wrist
  behavior. Executed five regression suites: **51 tests +21 subtests passed**.
  This is a preference candidate, not an optimal/naturalness proof:
  the input has wrist pose but no measured human elbow/swivel target. User
  visual acceptance after restarting Input remains necessary. No G1 execution,
  SDK/DDS, motor output, or gain changes were performed.

## Current stationary wrist rotation correction

- User confirmed the front-elbow change improved motion, but observed arm
  recruitment during stationary wrist rotation. The newest 16:19 CSV was still
  zero bytes when inspected; do not describe this as an analysis of that run.
- The active upstream tracking QP used the standard proximal/wrist damping
  costs 0.25/0.015. The legacy banner's proximal cost 100 refers to the other
  task path and does not describe this QP. A reachable fixed-position synthetic
  30-degree local roll rotation recruited up to 6.12 degrees of proximal motion.
- Added a finite proximal velocity penalty in `UpstreamMinkTracking`. It is an
  IK objective, not motor Kd or a hard joint lock. Maximum extra cost is 5.
  Its weight fades with position error (full <=2 mm, zero >=8 mm), rotation
  error (full >=3 degrees, zero at zero error), wrist joint margin (full >=28
  degrees, zero <=5 degrees), and clearance (full >=25 mm, zero <=5 mm).
  Reset and BeginReturn clear it. Elbow assistance, yaw envelope, original
  rotation target, speed/acceleration, exact geometry, and hardware files stay
  unchanged. Finite cost allows proximal compensation for offset wrist axes.
- Reproducible synthetic experiment:
  `python experiments/twist2_right_arm_manual/compare_mink_stationary_rotation.py --baseline-ref a709874 --output logs/test_results/wrist_stationary_priority_20260917.json`.
  Initial-pose wrist position stays fixed; rotate 30 degrees over 2 seconds,
  hold 4 seconds, separately around each local axis. Baseline -> candidate
  maximum proximal joint excursion: roll 6.12 -> 0.33 degrees, pitch 3.73 ->
  3.44 degrees, yaw 1.83 -> 0.10 degrees. Final orientation errors <=0.29 degrees.
  Pitch compensation is necessary for this model's offset wrist pivot; do not
  promise absolutely fixed shoulders for every wrist rotation. Maximum pitch
  position error increased from 0.70 to 5.60 mm; regression requires final
  position error below 2 mm. Other two axes stay below 0.1 mm throughout.
- Replayed the 15:58 recorded simulation targets (789 samples, 1,529 ticks)
  against a709874. Final elbow lift remains +4.18 cm, final rotation error
  remains 2.98 degrees, position p95 remains 20.38 cm. Rotation p95 changed
  75.06 -> 76.01 degrees; this is not a global tracking improvement. All replay
  steps accepted; no acceleration violations. Report:
  `logs/test_results/wrist_priority_front_replay_20260917.json`.
- Tests include generated three-axis stationary rotations with position,
  orientation, proximal excursion, exact geometry, frozen joints, velocity,
  and inter-step acceleration checks, plus existing straight reach, front
  elbow, return and simulation boundary regressions. Executed five suites:
  **50 tests and 21 subtests passed**. Reports identify the tested source hash;
  only explanatory comments were added to tracking code afterward. No live G1 validation;
  user must restart Input to assess appearance in VR. No robot execution.

## Current front-of-torso elbow correction (after the 15:58 simulation)

- `mink_v5_right_arm_20260917_155826_842.csv` contains 789 active samples.
  During the front-of-torso plateau, yaw reached the added 45-degree envelope,
  elbow joint coordinate was at its 5-degree bound, and projection disabled the
  old elbow-assist trigger. Joint coordinate 5 degrees must not be equated with
  a human-visible elbow bend angle; use FK elbow height to judge elevation.
- Front-face proximity is now checked against the model's expanded torso
  boxes. When the effective wrist position error exceeds 2 cm and elbow joint
  coordinate is below 20 degrees, a lateral/vertical elbow preference can
  activate even for a projected goal. It releases outside the front area,
  within 2.5 cm of the captured wrist target, on reset, or on pinch return.
- The old `FrameTask` Z cost acted in a rotating local frame, not world height.
  `ElbowClearanceTask` uses actual world Y/Z position error and `mj_jacBody`.
  It anchors lateral position to the engage elbow and vertical target to
  engage elbow +8 cm, capped 4 cm below the shoulder. Re-entry recomputes from
  the same engage reference rather than adding height to the current elbow.
  This is a soft pose preference, not an absolute 8 cm bound on every motion.
- The added yaw envelope is now +/-90 degrees from engage (previously +/-45).
  The 45-degree restriction prevented the required repositioning; increasing
  elbow cost alone worsened wrist reach. This change is an IK pose-envelope
  adjustment, not a velocity or hardware joint-limit change. Model/XML,
  velocity/acceleration limits, and original wrist rotation targets remain intact.
- A/B replay against `0be2f4c`, same target timestamps, 1,529 ticks:
  final elbow height relative to engage was -1.39 -> +4.18 cm (5.57 cm higher);
  final two-second wrist direction error 2.77 -> 2.98 degrees;
  position error p95 19.12 -> 20.38 cm (a regression, not an overall accuracy gain);
  minimum clearance 5.50 -> 31.74 mm; no rejected/braking steps or acceleration
  violations. Earlier 15:38 replay also retained rotation recovery (final error
  10.35 -> 9.83 degrees), with no rejected steps or acceleration violations.
- Added a recorded simulation snapshot test: fixed front target raises the
  elbow by 4-10 cm, maintains wrist rotation within 5 degrees and effective
  position error below 8 cm, and preserves non-arm joints/checked geometry.
  Forced repeated re-entry proves the assist target cannot ratchet upward.
  A finite-difference test checks the world-frame Jacobian; original return
  position/orientation tolerances remain unchanged.
- Validation executed: five focused suites, 48 tests +18 subtests passed;
  after adding constructor initialization, the initialization and front-target
  regressions passed (2 tests). Earlier assertions forbidding all projected
  elbow assistance were replaced by the bounded-lift requirement intentionally.
- Replay reports: `logs/test_results/elbow_front_final_ab_20260917.json` and
  `logs/test_results/wrist_elbow_final_ab_20260917.json`. These reports precede
  the constructor-only initialization addition; their source hashes identify
  that tested source. That addition does not change the Reset-based replay.
- Natural appearance still needs user confirmation after restarting Input.
  These are simulation/replay results, not measured G1 validation. No G1 SSH,
  SDK/DDS initialization, publisher, motor output, PD changes or model changes.

## Current wrist-orientation correction (after the 15:38 simulation)

- Torso projection now changes only the position target. The original user
  wrist rotation remains the QP target, including while the position lies
  inside the torso exclusion volume. `collision_orientation_relaxed=false`
  no longer conceals an overwritten rotation target.
- Position-priority orientation cost scale is now 0.5 rather than 0.1.
  Mink squares cost-weighted residuals, so the orientation term retains 25%
  rather than 1% of its normal strength. Projected goals retain full cost.
- Velocity/acceleration limits, the current +/-45 deg shoulder-yaw envelope,
  collision checks, and return behavior were not changed in this correction.
- A/B replay against `51b9035` used the same 840 active targets from
  `mink_v5_right_arm_20260917_153809_875.csv`, held according to recorded
  send timestamps at the fixed IK timestep (1,629 ticks per variant).
  Rotation median: 50.24 -> 20.11 deg; p95: 96.83 -> 78.83 deg;
  final two seconds median: 96.79 -> 10.35 deg. Position p95:
  18.59 -> 17.75 cm. Both variants had no rejected/braking steps or
  acceleration violations, minimum clearance >=5.49 mm, and yaw <=45 deg.
- A recorded final-pose fixture, initialized at rest for a static regression,
  reduces >90 deg rotation error to <5 deg within 600 ticks while remaining
  collision checked, rate limited, and preserving other joints. This fixture
  is derived from simulated joint values, not measured G1 state.
- Remaining: fast rotation still produces a maximum ~119.58 deg transient
  in both A/B runs. This change corrects sustained orientation abandonment;
  fast transient response is not solved. Live Quest retesting remains pending.
- Executed validation: upstream tracking, standard Mink, virtual-center
  trajectory, simulation handoff boundary, and runtime compatibility suites:
  **46 tests and 18 subtests passed**. The static fixture finished at 1.50 deg
  rotation error, 5.50 mm clearance, and 45 deg shoulder yaw. Local simulation
  runtime receives the identical tracking source; restart Input to load it.
- Reproduce from the repository root (Python with the existing Mink dependencies):

  ```powershell
  py -3.11 experiments/twist2_right_arm_manual/compare_mink_rotation_replay.py <simulation.csv> --baseline-ref 51b9035 --output logs/test_results/wrist_rotation_ab.json
  ```

  The script rejects multi-episode input, uses no transport, and includes
  source/CSV hashes in the report. Original logs are preserved. Timing between
  logged targets is reconstructed; this is not exact replay of unlogged IK ticks
  or hardware validation. No G1 SSH, SDK/DDS initialization or output occurred.

- The current Unity scene and sender now require a continuous 1.0 s
  thumb-index pinch before emitting `pinch_disengaged` (previously 0.5 s).
  This follows a recorded false/accidental sustained-pinch disconnect; it does
  not alter tracking-loss handling or any G1 output path.
- Raw Quest tracking loss is now distinct from a wrist-pose speed outlier.
  A pose outlier holds the last valid target without clearing calibration or
  starting the return cycle; a real loss of tracked/high-confidence input for
  0.35 s still emits `tracking_disengaged`. This addresses a recorded run where
  raw tracking stayed valid but computed wrist speed jumped to 9.18-12.01 m/s.
- User clarification established that the triggering motion was intentional and
  fast. The wrist input gate is therefore 5.0 m/s instead of 1.1 m/s, and its
  diagnostic speed uses consecutive observed frames instead of distance from
  the last accepted frame. Joint velocity/acceleration limits remain unchanged.
- A subsequent run retained 69 mm position error with elbow joint 25 at its
  5-degree lower limit while orientation error fell to 5.65 degrees. The
  position-priority state originally ramped orientation cost to zero instead
  of 25%; subsequent corrections used a 10% floor and now use a 50% cost
  floor (see current correction above). Its original rotation goal is retained and restored after
  positional recovery. Runtime packets record the priority flag and scale.
- The next replayed live run exposed a separate hysteresis gap: position error
  settled near 33 mm with elbow 25 at its 5-degree limit, below the old 80 mm
  entry threshold, so position priority never activated. Entry is now 25 mm
  while constrained, and full orientation cost returns only below 10 mm or
  after leaving the constrained region.

## 2026-09-17 IK/Omni time-series capture

- Added a receive-only Mink logger for `g1.mink.right_arm.state.v1` on Windows loopback UDP 5008. It validates the complete 29-joint order and the duplicated right-arm indices 22-28, then records the seven targets in radians before any G1 relay/controller.
- The final IK CSV column, `raw_json_text`, preserves the complete UTF-8 UDP JSON plaintext alongside the parsed fields.
- Extended the existing Omni read-only CSV with raw `movementXY`/arm yaw, yaw relative to the first sample, wrapped per-sample yaw difference, raw yaw rate, and mapped `vx/vy/yaw_rate` with explicit units.
- Operator instructions and field definitions are in [IK_OMNI_TIMESERIES_20260917.md](IK_OMNI_TIMESERIES_20260917.md).
- No G1 SSH, SDK, DDS, publisher, relay, or motor output was used. Tests use generated fixtures only; Quest/Omni hardware capture remains an operator step.
- Restored the selected fast Quest-following limits in the standard virtual-center path: shoulder/elbow 90 deg/s, wrist 180 deg/s, and all right-arm joints 60 deg/s^2. This source change is not physical-G1 validation.
- Restored the user-confirmed simulation v5 path for IK CSV capture. It now
  separates the raw Quest wrist target from a model-derived collision-effective
  target. A wrist target inside the torso exclusion volume is projected to the
  nearest outside face using the torso mesh bounds, wrist collision radius and
  configured clearance. While projection is active, position continues moving
  along that outside boundary so an operator can route the hand around the
  torso. The old behavior replaced raw wrist orientation with the current
  wrist orientation; the current correction above removes that substitution.
  The front-of-torso correction above now permits bounded elbow assistance
  for projected targets. When the
  raw target leaves the exclusion volume, normal position and orientation
  tracking resume. Raw/effective positions, projection distance and the
  orientation-relaxed flag remain in runtime and raw-JSON CSV diagnostics.
  Recorded-problem regression coverage bounds elbow lift below 3 cm. This is
  MuJoCo/offline validation only.

## Laptop migration checkpoint

This integration branch combines the latest published continuation with the laptop source. Read [migration status](migration/20260917/README.md) and [two-PC synchronization rules](migration/20260917/TWO_PC_SYNC.md) first. Local historical notes are preserved in [LAPTOP_CHAT_HANDOFF.md](migration/20260917/LAPTOP_CHAT_HANDOFF.md). Conflicting temporary-worktree work is stored as patches, not enabled in this checkout. This is source synchronization, not hardware validation.

### 2026-09-17 scope change and last locomotion evidence

- GitHub-to-desktop continuation was the 2026-09-17 migration plan; see the
  2026-09-18 clarification above. Current work remains on the laptop.
- Lower-body policy development in this repository is stopped. Another developer will provide that policy; later work only integrates it with the Unity/Mink upper-body target and the single LowCmd owner.
- Do not repeat the preserved velocity 12DoF physical trial. In the last `+vx=0.05` axis trial, the policy transition reached approximately roll `-0.19 rad` and pitch `+0.34 rad`, then the controller stopped on `RuntimeError: IMU roll/pitch limit` and retained the last valid full-body position command.
- The robot was reported stable in its support rig after that event. This observation is not policy validation.
- Existing locomotion sources, MuJoCo results and logs remain historical evidence. Their presence is not authorization to deploy or run them on G1.


## 1. Start here

For every new project conversation:

1. For current laptop bimanual work and any later desktop migration, use `codex/g1-laptop-sync-20260917`. `main` remains the canonical branch after review and merge.
2. Read this file, [`ARCHITECTURE.md`](ARCHITECTURE.md), and [`REVIEW_LATEST.md`](REVIEW_LATEST.md).
3. Read the relevant review/remediation log before changing a reviewed defect.
4. Read [`CODE_GUIDE.md`](CODE_GUIDE.md) before changing a control path.
5. Inspect current HEAD and working-tree state before edits or cleanup.
6. Keep review findings, production changes and physical tests separately labeled.

Do not remove safety checks, loosen limits or change gains merely to make a test pass. Do not treat unit/static/simulation/transport tests as physical validation.

## 2. Repository checkpoint

```text
Repository : Y1048/Y
Primary branch : main
Old main archive : archive/old-main-20260820
```

`main` contains the former `refactor/teleop-architecture` work. The old refactor branch has been retired by the user. Do not target it in new automation or Codex instructions.

The default launcher remains:

```text
START_VR_HAND_TO_MUJOCO.bat
```

It launches the provenance-marking virtual-center entrypoint; `--baseline` uses the corresponding prototype entrypoint.

## 3. Current remediation/review state

The precision review records R1-R67 and remains incomplete. `REVIEW_LATEST.md` is authoritative for current status.

Key state:

- **R15/R35/R65** supported command provenance/freshness paths are source-mitigated and current-checkout CI is green.
- **R21/R51** supported LowState startup paths use per-run forward tokens and provenance/state/raw-odometry-bound prechecks.
- **R1/R3/R34/R64** have source fixes with offline regression coverage.
- **R2/R33/R41/R42** supported Gate 7/Jog collision/acquisition guards have offline regression coverage.
- **R46** is integrated into `g1_right_arm_jog.py`; planned/fault release share the SDK-neutral finalizer and incomplete evidence is fail-closed.
- **R40** supported physical paths bind current 29-joint/model/config evidence and raw `rt/odommodestate` position/quaternion back to startup, while requiring live base stability. Connected-G1 validation is still not done.
- **R50** supported paths supervise LowState IMU roll/pitch, motor temperature/fault/tau finiteness, and runtime base/odometry stability. Remote/deadman and CRC/integrity remain open until actual read-only SDK fields are verified.
- **R20/R24/R27/R32** remain open. Latest full-text review reconfirmed R20 benchmark/replay exit semantics, extended R24 to remaining stale velocity tests, retained R27 as the generic SE(3) matrix-validation boundary, and left R32 as direct V1 protocol integer coercion versus strict V2.
- **R53** remains open. Camera validation and inspection-scene tests add shared generated-MuJoCo-XML writer surfaces to the existing model/evidence provenance finding.
- The bounded 308-file source inventory is fully read. This closes the review queue only; it does not close any R-number or authorize physical output.

## 4. Reconciled review coverage

Current canonical ledger:

```text
total current scoped files : 311
full_text_review           : 311
static_only                : 0
static check failures      : 0
```

Use:

```text
logs/review/20260903/source_checks.csv
logs/review/20260903/source_checks_summary_20260904.json
docs/CODE_INDEX.md
```

Latest review batches:

```text
docs/REVIEW_20260904_BACKEND_CORE.md
docs/REVIEW_20260904_BACKEND_SUPPORT.md
docs/REVIEW_20260904_BACKEND_DIAGNOSTICS.md
docs/REVIEW_20260904_BACKEND_DIAGNOSTICS_2.md
docs/REVIEW_20260904_BACKEND_DIAGNOSTICS_3.md
docs/REVIEW_20260904_LAUNCHERS.md
docs/REVIEW_20260904_CONFIG_AND_FRAME.md
docs/REVIEW_20260904_RECOVERY_MULTISTRATEGY.md
docs/REVIEW_20260904_REMAINING_EXPERIMENTS_AND_HARDWARE_HELPERS.md
```

The current bounded inventory has no remaining `static_only` files. This is
full-text review coverage, not a correctness or physical-validation claim.

## 5. Offline regression evidence

```text
.github/workflows/offline-provenance-regression.yml
Run 33824261133 : PASS
```

```text
.github/workflows/offline-safety-regression.yml
Run 33824155653 : PASS
```

These workflows are robot-offline and create no Unitree publisher, DDS endpoint, WSL runtime, Unity/Quest runtime or G1 connection.

## 6. Immediate next work

```text
1. Keep R20/R24/R27/R32 remediation separate from completed review bookkeeping.
2. Preserve the experimental TWIST2 R43-R45/R49 block before any further physical use.
3. Do not invent R50 remote/deadman/CRC checks; verify actual read-only Unitree SDK fields first.
4. Plan simulation/WSL integration checks with hardware output locked.
5. Reconcile CODE_INDEX/source_checks whenever scoped files change.
```

The first explicitly approved right-shoulder-pitch sign/response trial completed
on 2026-09-04. `Q` increased raw q and moved the arm backward; `Z` decreased raw
q and moved it forward. The run also included an absolute-zero `A` input, so it
is not a strict +/- one-step acceptance test. See
[`PHYSICAL_TEST_20260904_TWIST2_RIGHT_SHOULDER_PITCH.md`](PHYSICAL_TEST_20260904_TWIST2_RIGHT_SHOULDER_PITCH.md).
Do not expand physical testing without a new exact approval.

The captured 1,538-row full-body CSV now has a local-only visual replay at
`experiments/twist2_right_arm_manual/VIEW_PHYSICAL_CSV_MUJOCO.bat`. It maps
measured `q_0..q_28` directly to the canonical MuJoCo motor order and creates no
Unitree SDK, DDS, socket, publisher or robot command. Automated schema/model
validation passes; the human visual sign comparison is still pending.

## 6A. Rejected Mink collision-boundary experiment

The temporary split-clearance experiment was rejected after the first
Quest/MuJoCo visual test. It allowed the torso/right-shoulder-yaw pair to reach
12.0018 mm and produced an abnormal arm posture. The rejected 20/12 mm split is
not active and the policy identifier remains `checked_local_lookahead_v1`.
Collision settings are selected explicitly. Local Unity/MuJoCo launchers now
default to Mink's 5/10 mm distances. The Gate 7 hardware launcher passes
`--hardware-display`, which always forces the guarded 20/40 mm profile. The
physical adapter still applies its independent 12 mm hard stop.

Do not reapply the rejected 20 mm QP / 12 mm post-QP split. Evaluate the
MuJoCo-only 5/10 mm profile before changing planner merit or tangent behavior,
and do not use it as an implicit physical-output policy. See
`docs/REMEDIATION_20260904_MINK_COLLISION_PROGRESS.md`.

A 2026-09-04 automatic wrist-only preference experiment was rejected and
removed after the first Quest test. Per-frame hand-motion classification
latched during ordinary motion; the 51.08-second active trace drove the elbow
from 55 to its 5-degree lower limit, reported collision limiting for 738 frames,
and produced 16.19 cm position-error p95. Do not restore that detector or its
target-position latch. The pre-existing wrist/proximal redundancy issue remains
open and needs a continuous objective or explicit operator mode, not this
discarded heuristic.

The first retest after this rollback did not exercise the local 5/10 mm
profile: PID 35608 was still bound to UDP 5005/5012 with the old explicit
`--collision-profile hardware-guarded` command. Runtime status showed the
torso/right-shoulder-yaw pair stopped at 20.0005 mm. The local stale process was
identified and closed; the next ordinary launcher run starts with 5/10 mm.

The subsequent 5/10 mm retest reached the true local boundary at 5.0011 mm.
Local simulation now uses `mink_local_detour_checked_v1`: a 5.5 mm QP reserve with
a 5.0 mm nonlinear validation floor, and geometry-safe tangent steps do not
need strict per-frame merit decrease. `hardware-guarded` remains monotone and
unchanged. Reconstructed first-step evidence changed the saved boundary pose
from zero motion to a 0.0764 degree maximum joint step without dropping below
5.0011 mm. This is local avoidance, not a global path planner; APF or a broader
path layer is still required if the short waypoint reaches another local minimum. The first
local detour is an 8 cm outward waypoint, held for at most 30 frames before the
unchanged operator target is retried. A measured-pose 180-frame offline
regression requires at least 120 moving frames, lower final target error and a
5 mm minimum checked clearance.

## 7. Hardware boundary

- Repository hardware authorization remains locked.
- Do not assume G1 Ethernet, WSL DDS, Unity, Quest or any publisher is currently running.
- No physical command, G1 file mutation, service/mode change or administrator network change is authorized by this handoff.
- Runtime-base changes add only read-only `rt/odommodestate` subscriptions on supported physical paths; they have not been executed against G1 in this remediation session.
- Preserve calibration and intentional local work; inspect Git state before cleanup/reset/restore.

## 8. Historical handoff

Historical detail remains in [`CHAT_HANDOFF_HISTORY_20260903.md`](CHAT_HANDOFF_HISTORY_20260903.md). Use this current handoff and `REVIEW_LATEST.md` first.

## 9. 2026-09-14 main-baseline continuation

Fetched `origin/main` and confirmed it exactly matched
`0da866f7833c21ee1898c3e3ccf7932cdb401475`. The older dirty
`codex/g1-regular-handoff-20260910` worktree was left untouched; continuation
uses a clean branch from current main.

Phase 1 of `G1_REAL_SYSTEM_ID_NEXT_20260913.md` now has an offline foundation:
`real_response_log.py` supplies a versioned, strict, asynchronous local trace
sink, while `real_response_identification.py` supplies a gap-refusing low-order
offline fitter skeleton. Neither module imports Unitree SDK/DDS, creates a
publisher/socket, emits `LowCmd`, modifies gains, or connects to G1. See
`G1_REAL_RESPONSE_LOGGER_20260914.md` for schema, tests, limits and remaining
integration work. This is offline infrastructure, not measured-G1 evidence or
a hardware gain recommendation. The five new focused tests and the existing
recorded-target parser regression pass on Windows Python 3.14.

The same branch now integrates a passive `real_response.jsonl` sink at the
existing single LowCmd owner's completed 500 Hz writer frame. It separates the
original joints 22..28 target from the final shaped command and pairs both with
the LowState, estimated torque, IMU, temperature and status values already read
by that writer. Two focused C++ offline tests pass with strict warnings enabled.
The Unitree/ARM controller has not been linked, deployed or run, so the next
step is an ARM compile-only review followed by a separately authorized small
measurement—not immediate gain optimization.

## 2026-09-14 read-only system-identification foundation, isolated continuation

Current user priority supersedes earlier PD48/5 and mode-research plans:
measurement -> real model identification -> unused-episode validation -> PD
optimization. Mode research stays HOLD. Later clarification permits data
acquisition, but no robot connection/actuation was needed or performed here.

Fetched remote and compared local branches/worktrees. origin/main0da866f,
origin/codex/g1-main-continuation-20260914=5de8586; main is an ancestor.
The former isolated worktree contains uncommitted unrelated shutdown/diagnostic
work; it is preserved. New initially clean independent working copy:
C:/Users/user/AppData/Local/Temp/g1_sysid_offline_20260914, same continuation branch.
The dirty live tree remains on05d4ebf with423status entries at initial inventory.

Added sysid_capture.py (29-axis v2 immutable-byte queue/file sink and parser),
sysid_model.py (training-only delay/first-order fit and separate recursive
validation), test_sysid_pipeline.py and G1_SYSID_OFFLINE_PIPELINE_20260914.md.
No inherited controller/hook, v1 logger, launcher, gains, model, IK or transport
files changed. New module is not connected to the existing writer. v1 files are
legacy, not automatically converted or used by this v2 identification pipeline.

Actually executed: Windows Python3.14 unittest,21new generated-fixture tests plus
5existing v1 tests =26passed,0failed. Known fixture40msdelay and first-order lag
recovered; independent session validation passes; changed-delay validation fails
without retuning. Preservation test, ordering, malformed/nonfinite, clock/gap,
exact bytes, queue/file failure and leakage cases covered. No new MuJoCo runs,
ARM/C++ build, SDK/DDS, SSH, physical output, hardware gains or mode switching.

actual parameter identification is data-blocked: no suitable excited and held-out
real v2 episodes available. Earlier handoff-only trace has constant arm commands.
Effective delay/lag are fixture-only closed-loop estimates, NOT motor latency or
inertia; physical damping/friction/inertia/load require additional identifiable
models/data and remain null. recommended_hardware_gains=null always.
Uniform aligned-clock fitter deliberately rejects asynchronous real frames;
future timestamp-aware fitting/adapter timing validation remains separate work.
Current task delivers the offline foundation, not a deployed hardware recorder.

## 2026-09-14 next data-readiness check

User explicitly permits data acquisition and reports powered-on ZeroTorque.
Read-only SSH inventory only (no controller launch/setter/SDK/DDS): known response
build/cycle directories contain only the already retrieved real_response.jsonl
under trial1789346113063495_6812; PID6812 is absent at this observation.
No new trace copied and no physical state changed. Does not prove no other PID.
Local v1 inspection:2500records,4.997848125s,0sequence gaps,2repeated states,
0conflicting repeats; all7command excursions0rad. Report in
validation/g1_sysid_20260914/legacy_readiness.json, raw source hash retained.
Added reusable sysid_inspect_legacy.py; it does NOT fabricate29-axis fields,
write-begin timestamps, missing clock metadata or receipts. fit_ready=false.
23tests actually passed (2new inspector+21v2 pipeline); preservation scope still
excludes only explicitly new file-only sysid modules/tests. No hardware gains.

Next meaningful implementation is a reviewed native observer adapter that
captures all required existing writer values without changing control decisions,
plus timestamp-aware fitting. Actual excited training and separate validation
captures remain missing. More stationary ZeroTorque samples alone cannot fill
that gap. No new motion authorized/executed by this data-inventory step.

## 2026-09-14 native observer hook candidate (not deployed)

Added sysid_native_observer.hpp: SDK/transport-free fixed-size2048-slot SPSC ring,
POD29-axis snapshot and worker-only JSON/file encoding. Lock-free index assertion,
nonthrowing Offer, overflow/failure receipt, exclusive file creation. Producer
makes no allocations, file writes or queue waits in Offer; actual callback timing
is not benchmarked/guaranteed. A native receiver/publisher is NOT created by it.

Existing Controller start_response_log optionally starts v2 only when
G1_SYSID_CAPTURE_V2=1. Defaults and launchers are unchanged. Records include actual
write-begin/end steady-clock nanoseconds, original full target, post-limiter
command/dq/gains/feedforward, paired29-axis q/dq/torque/temperature/status and
IMU rpy/gyro/acceleration. Mode is null (no extra RPC), acceptance unknown.
Output is real_response.jsonl.v2.jsonl with SHA-bound receipt on explicit finish.
Native Finish detaches under writer mutex, then drains/hashes outside it; native
setup/finish failure only reports incomplete recording. Existing v1 logger code
and its exception/lifecycle semantics are inherited, not repaired by this patch.
A killed process/destructor-only cleanup has no completion receipt: reject it.

Actually executed:2 SDK-free C++/Python tests in WSL using g++17 mode and
-Wall -Wextra -Werror (ring full/empty, exact29-axis mapping through Python parser,
exclusive output, nonfinite encoding/worker failure), plus21Python v2 tests on
Windows. All passed. Source comparison confirms motor equation block unchanged
and no added publisher Write call. Preservation test now explicitly excludes the
reviewed observer hook cpp; its command equations are checked separately.
Full Controller ARM compile, SDK field compatibility, callback timing, real v2
capture and asynchronous fitter integration remain unverified. No G1 SSH,
deployment, mode or gain change this turn. Do not run the candidate yet.

### 2026-09-14: asynchronous offline identification and compile-only check

Added sysid_async_model.py and generated tests: shared-host-clock asynchronous
command/state integration, frozen delay/lag grid, independent episode validation,
leakage/gap/invalid-model rejection. See G1_SYSID_OFFLINE_PIPELINE_20260914.md for
commands and interpretation limits. Actual parameter identification is data-blocked;
recommended_hardware_gains=null. No PD optimization or hardware recommendation.

Full local WSL x86_64 controller compile/link passed with Torch header warnings;
controller binary was not executed or deployed. Windows numerical/schema tests32
and WSL SDK-free native tests2 passed (native suite initially failed under Windows
because g++ was absent, then rerun in WSL). Fixtures are generated, not measured.
Existing motor equations, gains, model and launch paths remain unchanged this turn.
No SSH, SDK/DDS initialization, motor output, mode work or live worktree changes.
ARM/runtime timing/real v2 capture remain pending; do not interpret compilation as
hardware approval. Prior ZeroTorque/hold data is insufficient for dynamic fitting.

### 2026-09-14: standalone read-only DDS capture on G1

Added `sysid_readonly_dds.cpp`, a subscriber-only aarch64 logger for `rt/lowcmd`
and `rt/lowstate`, plus strict parser, quiet-summary utility and tests. Static
checks require zero `ChannelPublisher`, motion client and command-write symbols.
It uses an asynchronous heap ring. An initial pre-fix launch segfaulted before
creating a file because the large ring was on the stack; moving it to the heap
fixed the issue. That failed attempt produced no command and no measurement file.

The corrected ARM binary SHA is
`80d854e0492a6adadfef329d9447ae66f26bec994c4d7109aa9cd91646f4a1ad` in
`/home/unitree/g1_sysid_observer_437db16`. Three 5 s subscriber-only runs in the
user-reported ZeroTorque state produced 15,742 LowState records, zero observed
LowCmd records and zero ring drops. No actuation or mode change was performed.
Raw logs/receipts are durably copied to
`C:/Users/user/Documents/G1_SysID_Data/20260914_zerotorque_readonly`; Git contains
only their hashes/statistical summary and deployment receipt. Repeated state tick
values occurred 263/262/264 times while data changed, so tick is diagnostic, not
treated as a unique sequence number.

Actual state data now exists, but actual dynamic parameter identification remains
blocked on controlled command excitation and an unused validation capture.
`recommended_hardware_gains=null`. Do not use the existing PD sweep: it changes
Kp 40/48/56 and reaches the deferred mode-handoff path. Next code task is a fixed
current-gain, bounded per-joint identification trajectory with an explicit
termination/ownership contract; physical execution requires separate review.

### 2026-09-14: offline excitation-plan contract

Implemented the next code task as `sysid_excitation_plan.py`, an offline-only
plan generator with no execution/SDK/DDS/network/controller path. It requires a
SHA-bound controller, exact29-axis start/soft-limit/Kp/Kd vectors and explicit
seven-axis amplitudes, speed and acceleration limits. It produces sequential
one-joint quintic moves; analytic peak velocity/acceleration are bounded and
training/validation reverse joint order and initial sign. Output explicitly says
`command_capable=false`, `execution_authorized=false` and
`recommended_hardware_gains=null`.

The termination owner is an explicit unresolved/reviewed contract in the input.
Current status remains unresolved because handoff research is on hold, so this
plan is not connected to LowCmd and is not a physical-run instruction. See
`G1_SYSID_EXCITATION_PLAN_20260914.md`. Generated tests cover order, limits,
analytic bounds, deterministic hash binding, malformed/nonfinite inputs and
absence of transport imports. No G1 connection or output was performed.

Added `sysid_excitation_readiness.py` as the next offline gate. It compares the
plan against a strict completed `g1.sysid.readonly-dds.v1` capture and reports
tail pose error, right-arm velocity, observed modes, command coverage and gain
agreement. Pose/velocity tolerances are mandatory caller inputs so no unmeasured
physical threshold is invented. Missing LowCmd produces unknown gain agreement;
it is never relabelled as a match. The output always keeps
`physical_execution_authorized=false` and `recommended_hardware_gains=null`.
Generated tests cover matching evidence plus pose, motion, gain and unresolved-
owner blockers. The three existing ZeroTorque captures were not converted into
an excitation plan because they have no commands and their posture is not an
approved controlled start. No G1/DDS/controller execution occurred.

Added `sysid_excitation_request.py` to remove manual29-vector transcription.
It extracts literal gains/soft limits from the chosen C++ common header, derives
a median start pose only from a caller-bounded stable tail, and hash-binds the
capture plus common/controller sources. All motion limits and ownership text
remain required in a separate draft spec; there are no physical defaults. It
rejects moving, short or variable-mode captures and validates the resulting
request through the plan builder. The output receipt remains explicitly
non-authorizing. Generated tests verify the current right-arm gain extraction,
hash binding, motion rejection, malformed-source refusal and absence of command
imports. Existing ZeroTorque data was not promoted to an approved start pose.

Added `G1_SYSID_EXCITATION_DRAFT_SPEC_20260914.json`. It reuses the existing
joint22 small-signal shape (±8deg,20deg/s,60deg/s²,3cycles) across seven
sequential axes only as a review draft. The extension to joints23..28 is marked
unvalidated, tail thresholds are not claimed as measured noise, and termination
ownership remains unresolved. Draft receipts now hash and retain a mandatory
human-readable parameter basis. This does not authorize or implement motion.

Fixed an ambiguity in the offline plan: every post-move hold now carries the
active joint index/name and exact held offset. Added `sysid_excitation_preview.py`
to expand plans to sample-level training/validation CSV plus a hash-bound summary.
It rejects discontinuities, off-grid segments and nonzero final offsets and has
no command path. The current draft shape computes to169segments and116.252s per
episode (232.504s combined), but no actual start pose has been selected and no
physical run is authorized or claimed.

Added `sysid_excitation_reference.hpp` as an SDK-free C++ implementation of the
same grid-rounded quintic waveform used by the offline Python plan/preview. It is
pure trajectory math and is not included by any LowCmd writer, DDS process or
robot controller. The native C++ test checks the complete 2 ms grid, endpoint
clamping, monotonic position and the draft 20 deg/s and 60 deg/s² bounds; a Python
test checks constants/formulas and the expected 0.878 s move duration. This is an
offline integration reference only. No G1/DDS/controller was run, command-owner
and termination behavior remain unresolved, physical execution is unauthorized,
and `recommended_hardware_gains=null`.

Added `sysid_excitation_sequence.hpp`, an SDK-free deterministic C++ sequence
core over the reference quintic. It consumes an explicit 29-axis start vector and
in-memory hold/move segments, rejects nonfinite/off-grid/discontinuous/non-returning
plans and only permits active joints 22..28. Its native test sequentially moves all
seven right-arm joints and proves every inactive joint is held exactly, targets do
not overshoot, and the final 29-axis vector equals the start. The sequence core
has no writer integration, DDS, publisher or robot executable; its separate
offline saved-plan adapter is recorded below. Command-owner and termination work
remain on hold.

Added `sysid_excitation_plan_adapter.hpp` and the file-only
`sysid_excitation_plan_check.cpp`. The adapter refuses executing/authorized plans,
non-null hardware recommendations, wrong 29-axis/right-arm identity, soft-limit
breaches, discontinuities, nonfinite values and altered analytic peak metadata.
It constructs training and validation sequences without any SDK, DDS, network,
publisher or controller path. The compiled checker successfully opened a plan
produced by the Python generator and reported matching 47,906-tick episodes at
2 ms. Native malformed-plan tests and static dependency tests passed. Nothing was
connected to the robot runtime; physical acquisition and gain selection remain
blocked pending a reviewed procedure, and `recommended_hardware_gains=null`.

Added the file-only C++ `sysid_excitation_plan_dump.cpp` and Python
`sysid_excitation_crosscheck.py`. The native dumper expands a saved episode while
the Python checker independently compares every time, segment, active-joint,
seven-offset, velocity and acceleration field. An executed generated-fixture run
matched all 47,907 rows in both training and validation; maximum numeric error was
`8.526512829121202e-14`. Tests reject changed, missing and nonfinite samples and
statically exclude transport/robot dependencies. This is generated evidence, not
measured G1 data, and no physical execution or gain recommendation follows.

Added detached `sysid_excitation_writer_hook.hpp` after confirming the existing
policy loop is 50 Hz while LowCmd construction is 500 Hz. Passing the 2 ms plan
through the policy loop would drop nine of ten samples, so the candidate models
the later writer boundary but is not included by the physical controller. It
returns only seven right-arm targets, holds the final start pose and rejects
unarmed use, wrong writer period, start-pose mismatch, current Kp/Kd mismatch and
nonfinite inputs. The adapter now retains/validates planned 29-axis Kp/Kd for this
check. Native and static tests passed; the physical controller SHA remains
`aa38a2e7d7e1686493b9c535ee2d13636856025f1a67928ef4c9290da5e01359`.
No CLI option, SDK/DDS execution, publisher, gain change or G1 access was added.
Actual integration still requires reviewed arming tolerances and completion/fault
ownership. `recommended_hardware_gains=null`.

Added detached `sysid_excitation_runtime.hpp` with explicit disarmed, running,
complete-hold and fault-hold states. Each sample carries plan/request hashes,
contract, termination-owner status, episode, tick, segment and active joint. A
latched fault after the first valid sample freezes the last seven targets, reports
zero planned velocity/acceleration, preserves the first reason and stops tick
advance; normal completion holds the original arm start. The adapter now validates
and retains request/contract/owner provenance. Tests cover both hold paths, bad
hashes and pre-sample fault rejection. This remains detached from the observer and
physical controller, which is still unchanged. No G1/DDS/publisher/gain action was
performed and `recommended_hardware_gains=null`.

Added detached `sysid_excitation_observer_bridge.hpp` and an optional fixed-size
excitation tag to `sysid_native_observer.hpp`. It preserves plan/request/contract/
episode provenance and records runtime state, tick, segment, active joint, seven
planned arm positions, velocity/acceleration and bounded fault reason through the
existing asynchronous ring. Existing observer callers remain source-compatible
and emit the prior schema shape when no excitation context is supplied. The bridge
does not assign target/command/measured/gain/torque arrays; native tests compare
those arrays before/after and exercise the asynchronous file worker. Focused
Python tests 28 and SDK-free C++ bridge/runtime tests passed; the existing native
observer's two tests also passed when rerun with the WSL worktree Git path supplied.
The first native rerun had one environment-only Git worktree-path error while its
ring/schema test passed; the corrected rerun passed both. The physical controller
is still not connected or changed. No G1, DDS, publisher, gain or motor action was
performed; `recommended_hardware_gains=null`.

Final bridge verification also ran the full 73-test Python regression set, every
SDK-free excitation C++ test/tool, and a complete local x86_64 compile/link of
`g1_twist2_mink_cycle_trial` using the existing Unitree SDK/Torch files. All
completed successfully; the controller binary was not executed. Third-party SDK
and Torch warnings remain. This is compile/offline evidence only, not ARM timing,
hardware validation or execution authorization.

Connected the excitation runtime to the actual 500 Hz writer source as a dormant
integration seam. `twist2_mink_cycle_trial.cpp` has no CLI/launcher caller and its
runtime pointer defaults null, so existing executable behavior is unchanged. A
future installation is rejected unless it precedes writer start, capture is ready,
the owner contract says `reviewed`, current gains/start pose match and V2 logging
is enabled. The checked-in draft remains `unresolved` and cannot install. When
installed, only desired joints22..28 come from the 2 ms sequence; the existing
slew/range/torque clamps and single `publisher_->Write(command)` remain unchanged,
and the observer separates plan target from actual constructed command. Static
tests confirm there is exactly one installation method definition and no caller or
`--sysid-excitation` option. Focused Python28, native C++ runtime/bridge, native
observer2 and full local x86_64 controller compile/link passed. The binary was not
executed. New controller source SHA is
`af9f8e7bf988766b42210e75c9f909826bba0d2d0d369531d1f11b65a07c75a6`.
No G1/SSH, DDS initialization, deployment, publisher execution, motor output or
gain change occurred. Termination ownership and a physical caller remain blocked;
`recommended_hardware_gains=null`.
## 2026-09-17 position-priority posture correction (simulation only)

- The latest simulation CSV `mink_v5_right_arm_20260917_150853_846.csv` showed that the apparent excessive elbow bend was not elbow flexion: joint 25 reached its 5 deg extension limit while right shoulder yaw reached its 150 deg upper limit and wrist pitch approached -80 deg.
- Root cause: the position-priority fallback reduced wrist orientation cost to zero, leaving the redundant 7-DOF solution free to wind shoulder yaw toward its limit.
- Position priority now retains 10% of the normal orientation cost and temporarily raises only the right shoulder-yaw posture cost to 8.0, referenced to the captured engage posture. Normal orientation and posture costs are restored when priority ends, on pinch return, and on reset.
- Offline replay of the 1,238 active targets from that CSV reduced maximum shoulder yaw from the recorded 150 deg to 79.98 deg. This replay does not reproduce Unity timing exactly and is simulation evidence only.
- Verification: `backend/tests/test_upstream_mink_tracking.py` and `backend/tests/test_standard_mink_live.py` passed (35 tests, 2 subtests). No G1 SDK/DDS, publisher, SSH, or physical output was used.

### Follow-up: remove the perceived slowdown

- The temporary shoulder-yaw posture cost of 8.0 reduced not only winding but also requested shoulder-yaw velocity (recorded-target replay: about 79.5 deg/s at cost 2 versus 65.9 deg/s at cost 8). The user's slower-motion observation was therefore plausible even though the configured 90/180 deg/s caps had not changed.
- Replaced that cost penalty with a checked shoulder-yaw tracking envelope of +/-65 deg from the captured engage posture. It is expressed as acceleration-aware QP velocity bounds, so no posture penalty is applied inside the envelope; return behavior remains unchanged.
- The same 1,238-target offline replay held shoulder yaw at 65.0 deg, preserved the configured velocity limits, and reduced replay position-error p95 from 0.1795 m with the cost-8 experiment to 0.1571 m. Replay timing differs from Unity and is simulation evidence only.
- Verification: 45 tests and 18 subtests passed across upstream tracking, standard live Mink, virtual-center trajectory, simulation handoff boundary, and runtime refactor compatibility. No G1 output was used.

### 2026-09-17 follow-up simulation result and second correction

- The next simulation CSV `mink_v5_right_arm_20260917_153207_224.csv` confirmed the 65 deg envelope exactly: shoulder yaw stayed in 0..65 deg, with no tracking stop and only two acceleration-limited braking samples. Compared with the preceding cost-8 run, shoulder pitch/roll p95 speeds increased from 4.8/13.5 to 11.8/19.0 deg/s; the perceived whole-arm slowdown was not present, although shoulder yaw was intentionally constrained.
- The pose was still visually excessive because the solver repeatedly reached the 65 deg envelope and shoulder roll reached -62.7 deg. Recorded-target replay favored a 45 deg shoulder-yaw envelope: position-error p95 was 15.67 cm at 45 deg versus 16.12 cm at 65 deg.
- The QP approach-rate braking allowance was also changed from a 4x to the standard 2x acceleration-distance factor, without changing the configured 60 deg/s2 acceleration or 90/180 deg/s velocity caps. On the same replay, position-error p95 improved to 14.17 cm and most shoulder/wrist p95 speeds rose by roughly 15-30%.
- Verification after both changes: 45 tests and 18 subtests passed. Evidence remains simulation/replay only; no G1 output was used.
