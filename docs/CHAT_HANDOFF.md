# G1 Teleop Project Chat Handoff

Last updated: 2026-08-26

## 0. Operating rules for any ChatGPT conversation

This file is the canonical cross-chat handoff for the project.

Any ChatGPT conversation that continues work on this project should follow these rules automatically after this file is provided or read:

1. Read this file first, then read `docs/ARCHITECTURE.md` before making project changes.
2. Treat the project state, protected local changes, safety constraints, and unresolved cautions recorded here as binding unless the user explicitly changes them.
3. Inspect the current Git/project state before destructive operations such as reset, checkout, stash cleanup, bulk restore, or conflict resolution.
4. After any meaningful milestone, design decision, debugging conclusion, important code change, environment change, or hardware-integration progress, update this file so it reflects the latest state.
5. Keep this document concise and state-oriented. Do not turn it into a raw conversation log.
6. Preserve important existing information when updating. Remove or rewrite stale information only when a newer verified state supersedes it.
7. Keep `docs/ARCHITECTURE.md` for long-lived architecture/design truth and use this file for the current operational checkpoint and handoff state.
8. When a task changes the repository through GitHub, include the handoff update in the same working session whenever practical.

For a new chat, the user should only need to say something equivalent to:

```text
Read docs/CHAT_HANDOFF.md and continue the project from there.
```

No additional explanation of the handoff workflow should be required once this file has been read.

---

This document is the operational handoff for continuing work across ChatGPT conversations.
Read this file together with `docs/ARCHITECTURE.md` before making project changes.
After meaningful work, update this file with the current state, important decisions, unresolved issues, protected local changes, and next steps.

## 1. Repository

- Repository: `Y1048/Y`
- Working branch: `refactor/teleop-architecture`
- Local Windows repo: `C:\Users\user\Desktop\G1_Teleop_Project`
- Unity project: `Unity_G1_VR`
- Main launcher: `START_VR_HAND_TO_MUJOCO.bat`

## 2. Current end-to-end simulation path

Current working path:

```text
Quest / Meta Horizon Link
    -> Unity_G1_VR
    -> UDP target stream
    -> strict packet/session validation
    -> Mink IK controller
    -> joint / velocity / collision constraints
    -> MuJoCo G1 right-arm simulation
    -> UDP robot-state feedback to Unity
```

The current control scope is the G1 **right arm only**.
Non-right-arm DOFs are constrained/frozen in the Mink controller.

Main controller entry point used by the launcher:

```text
MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py
```

Important controller properties already in place:

- Mink IK
- DAQP preferred QP solver
- right-arm control only
- configuration/joint limits
- velocity limits
- collision avoidance
- non-right-arm DOF freeze
- UDP command watchdog/session logic

Current command-state contract:

```text
tracking loss / idle / UDP timeout -> hold current robot state and preserve clutch
sustained index pinch               -> manual disengage and require realignment
alignment target hold for 0.55 s    -> zero-jump engage
new sender session after timeout   -> replace ownership and establish a new clutch
```

### 2.1 Command-stream integration completed on 2026-08-26

The launcher controller and the virtual-center experiment now use:

```text
backend/g1_teleop/mink_command_stream.py
```

This connects the already existing strict adapter, session/sequence watchdog,
and runtime state machine to the actual Mink control loops. The previous local
JSON-only receiver was removed.

The Unity live sender emits:

```text
active
idle
pinch_disengaged
```

Pinch is an intentional manual disengagement gesture; it is not treated as
tracking loss. Automatic runtime installation of `G1BackendWorkspaceAuthority`
was removed from the live path. The optional
backend-authority component remains explicit opt-in and is not present in the
live scene.

## 3. Protected local modifications

The following local modifications must not be overwritten or reverted accidentally.
Before any reset, checkout, pull conflict resolution, stash cleanup, or bulk restore, verify these files first.

### 3.1 `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py`

Contains local experimental/comment changes around the Mink/DAQP control path.
Preserve current local edits.

### 3.2 `Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs`

The palm normal / orientation cross product must remain:

```csharp
Vector3.Cross(finger_direction, palm_across)
```

Do not revert it to:

```csharp
Vector3.Cross(palm_across, finger_direction)
```

### 3.3 `config/wrist_frame_calibration.json`

Current calibration is real measured calibration and must be preserved.

```json
"calibrated": true
```

Measured rotation matrix:

```json
[
  [0.9924449310842209, -0.05620383861431516, 0.10906047538064291],
  [0.11826344367346008, 0.20158636449624312, -0.9723048367357238],
  [0.03266215938559683, 0.9778568740742197, 0.20671022512218856]
]
```

## 4. Naming policy

Project-owned naming was cleaned up from Quest-specific wording to generic VR wording where appropriate.

Use `VR` for project-owned names where the concept is headset-independent.

Do **not** globally replace genuine hardware/SDK/protocol-specific Quest names.
Examples that may legitimately remain Quest/Meta-specific include device identifiers, SDK classes, XR rig names, tracked Quest wrist axes, Meta Quest integration names, and vendor-defined concepts.

## 5. Unity status

Unity version currently used by the launcher:

```text
Unity 6000.5.4f1
C:\Program Files\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe
```

`START_VR_HAND_TO_MUJOCO.bat --check` currently passes its prerequisite checks.

Last device-level functional validation before the command-stream integration:

- Meta Horizon Link runtime detected
- Unity opens successfully
- `START_VR_HAND_TO_MUJOCO.bat` executes successfully
- Unity Play mode / Quest hand path works
- Mink/MuJoCo right arm follows correctly
- user reported the current live simulation path works very well

Current post-change verification:

- strict command-stream and Unity policy tests pass
- both Mink controller modules compile and import
- wrist-frame static contract passes
- Unity 6000.5.4f1 batch script compilation succeeds with return code 0
- `START_VR_HAND_TO_MUJOCO.bat --check` passes
- live Quest/Unity/MuJoCo behavior after this change is not yet device-tested

Backend test status:

```text
131 tests run: 130 pass, 1 pre-existing trajectory threshold failure
```

The remaining failure is
`test_fake_vr_path_stays_humanlike_and_trackable`: measured maximum tracking
error is 0.021299 m while that legacy test requires at most 0.010 m. It is not
caused by the command-stream or Unity policy changes and remains unresolved.

For the preceding command-stream change, Unity and Python were closed before
batch compilation. The newer dynamic-workspace edit below occurred during a
later live session and has a separate verification boundary.

Additional live-path corrections in this change:

- 0.5 s sustained index pinch emits `pinch_disengaged` and clears clutch
- thumb-middle pinch engagement was removed; alignment target hold is the only engagement method
- the old rectangular Unity workspace is disabled by default because it is not a physical G1 reach set
- MuJoCo advances the Cartesian target continuously under the configured speed limit
- Mink joint, velocity, configuration, and collision constraints remain authoritative
- the virtual-center live path sends the filtered Cartesian target directly;
  Mink joint velocity and collision constraints limit robot motion
- self-collision filtering excludes only direct and two-hop structural neighbors
- `structural_neighbor_distance` was restored from 3 to 2 after live evidence
  showed that 3 incorrectly removed torso-to-shoulder-roll collision pairs and
  allowed a body-penetrating IK solution

Engagement UX correction on 2026-08-26:

- engagement now uses only the wrist alignment target held for 0.55 s
- thumb-middle pinch has no command path and no HUD progress path
- after engagement, thumb-index pinch held for 0.50 s remains the manual disengage gesture
- tracking-loss hold behavior is unchanged
- 17 focused policy/command-stream tests and the smooth launcher prerequisite check pass
- Unity was in Play mode during the source edit, so stop and restart Play once before device validation

Smooth-controller target-path correction on 2026-08-26:

- orange workspace warning and automatic workspace disengagement were removed
- the blue marker is the tracked Quest wrist
- the green marker is the filtered direct Cartesian command target
- the pink marker is the actual G1 wrist returned from MuJoCo joint state
- a white line connects the blue and pink markers as a movement-direction guide
- the G1 arm follows the green target under Mink joint, velocity, and collision constraints
- Cartesian target speed increased from 0.08 m/s to 0.12 m/s after live feedback that the green target was too slow
- the obsolete auto-installed `G1ReachabilityTargetLatch` was removed
- Unity C# build completes with 0 errors
- a sparse precomputed voxel projection was removed after live evidence showed it could trap the green target near the initial wrist position
- a subsequent 12 mm target-acceptance experiment is documented below and was rolled back after device validation

Failed feasible-target experiment and rollback on 2026-08-26:

- live diagnostics showed `command delay=17.6 cm` while MuJoCo IK error was only
  `0.1 cm`; the robot was following the green target, but the sparse voxel
  projection was trapping that target near the initial wrist position
- the voxel projector remains removed from the smooth live controller
- a replacement 12 mm target-acceptance gate also failed device validation:
  live output showed `target-follow=1.22 cm`, immediately beyond its 1.20 cm
  threshold, so the green target repeatedly reverted and the arm stopped
- that acceptance/reversion gate was rolled back
- the failed acceptance gate was removed. The later direct-target correction
  removes the additional Cartesian speed limiter as documented below; Mink
  joint velocity, configuration, and collision constraints remain enabled
- wrist orientation axes are disabled in the operator view by default
- Unity C# compilation completes with 0 errors and 44 existing warnings
- 23 focused tests pass
- a 348-packet post-rollback runtime check produced 0.67 mm IK error, negligible
  command delay, and 47 mm minimum collision clearance
- the controller was restarted afterward in the neutral idle posture

Quest target divergence diagnosis and correction on 2026-08-26:

- `Unity_G1_VR/Logs/live_quest_trace.csv` proved that the tracked wrist jumped
  0.78 m in one frame at 26.52 s; the binder forward delta subsequently reached
  1.00 m, so this was a tracking-origin/reacquisition discontinuity rather than
  normal arm motion
- `use_rectangular_workspace_fallback` was false, but the sender still always
  clamped UDP positions; the Unity marker and backend therefore received
  different targets
- UDP target clamping is now conditional on the fallback flag, so the live
  default sends the same unclamped target used by the Unity visualization
- active tracking-origin jumps above 0.20 m rebase the neutral wrist by the same
  position and rotation delta, preserving the current robot target without
  changing mapping axes
- runtime and Editor C# projects compile with 0 errors
- 24 focused policy, command-stream, motion-reference, and config tests pass
- actual Quest validation after this correction is still required; stop and
  restart Unity Play before evaluating it

Engagement-feedback and follower-lag correction on 2026-08-26:

- the next live trace showed about 11 cm command delay with near-zero MuJoCo IK
  error and clear safety state; this was Cartesian rate-limit lag, not an IK or
  coordinate-frame failure
- an intermediate 0.20 m/s Cartesian target limit was tested, but live traces
  showed that it compounded lag with the Mink joint-velocity limit
- the pink actual-wrist marker had been covering the white/yellow engagement
  target at the same location
- the pink marker is now hidden until engagement becomes active; before
  engagement the target remains white, changes to yellow when aligned, and
  grows with the 0.55 s hold progress
- after engagement the smaller pink actual marker and larger green target can
  both remain visible when their positions coincide
- runtime and Editor C# projects compile with 0 errors
- 24 focused tests pass
- the virtual-center path now places the green target directly at the filtered
  operator command; only the robot is slowed by Mink joint-velocity and
  collision constraints
- a 247-packet post-correction runtime check measured 0.06 mm green-command
  delay, 1.10 mm robot-target IK error, and 47 mm minimum collision clearance
- the controller was restarted afterward in neutral idle state

Virtual-center external-frame correction on 2026-08-26:

- live traces showed that the returned backend target delta could differ from
  the Unity sender delta by about 7 cm while Mink's own target-follow error was
  near zero
- the internal position task controls `right_wrist_roll_link`, but the external
  green-marker contract is `right_wrist_yaw_link`; wrist rotation changed the
  offset between those links and made the green marker lead or trail the hand
- the external yaw-wrist target is now fixed directly from the clutch-relative
  Unity input delta
- each control cycle derives the internal roll-center target by subtracting the
  current `yaw_position - roll_position` offset
- a 283-packet runtime check measured `2.9e-17 m` input-to-green contract error,
  0.73 mm robot-to-green error, and 46.8 mm minimum collision clearance
- 24 focused tests pass and Unity runtime C# compiles with 0 errors
- the controller was restarted afterward in neutral idle state

Launcher cleanup:

- `START_VR_HAND_TO_MUJOCO.bat` keeps the baseline controller as its default
- `START_VR_HAND_TO_MUJOCO.bat --smooth` selects the virtual-center controller
- the redundant `tools/TEST_MINK_G1_VIRTUAL_CENTER_LIVE.bat` was removed

Repository cleanup on 2026-08-26:

- removed the obsolete `Unity_G1_Quest3S_TEST` project copy
- removed `Unity_G1_VR/Library_BACKUP_20260826`
- removed the ignored `archive` directory and temporary notes/launchers
- removed 12 unreferenced early learning scripts: the 2-link examples, simple
  MuJoCo/G1 viewers, and the first inspection-arm demos
- removed generated Python `__pycache__` directories
- enabled repository-local Git long-path support so Unity package paths can be
  cleaned correctly on Windows
- retained the configured/geometry/hardware paths and all current IK,
  collision, frame, fake-input, and hardware-safety regression tools

Post-cleanup validation:

- baseline launcher check passes
- `--smooth --check` virtual-center launcher check passes
- controller modules compile
- six baseline postures have zero pairs inside the 12 mm collision minimum
- backend suite remains 130/131 passing; the existing fake-trajectory maximum
  tracking error is 21.299 mm against its 10 mm threshold

### 5.1 Unity crash investigation on 2026-08-26

Unity temporarily crashed immediately while opening `Unity_G1_VR`.
Direct launch and launcher launch both reproduced the issue.

Observed Windows process exit code:

```text
-1073740791 = 0xC0000409
```

Windows Error Reporting identified the faulting module as:

```text
OVRPlugin.dll
version 1.205.0.0
exception 0xc0000409
```

Faulting package path was under:

```text
Library/PackageCache/com.meta.xr.sdk.core@.../Plugins/Win64OpenXR/OVRPlugin.dll
```

Tests performed:

- `-force-d3d11` -> crash
- `-force-d3d12` -> crash
- empty Unity 6000.5.4f1 project -> normal
- original Library renamed and rebuilt -> initially still crashed
- old-name test copy `Unity_G1_Quest3S_TEST` created -> initially still crashed
- temporary bHaptics native DLL disable coincided with first successful launch
- bHaptics DLL was then restored and Unity still opened normally
- original launcher subsequently worked normally

Conclusion at current checkpoint:

- Unity installation and GPU backend are not the primary problem.
- bHaptics was **not proven to be the root cause**.
- historical crash was clearly inside Meta `OVRPlugin.dll` initialization.
- the issue is currently not reproducing after project/package reinitialization.
- do not make unnecessary plugin changes while the system is stable.

Temporary diagnostic artifacts may exist locally:

```text
Unity_G1_VR/Library_BACKUP_20260826
Unity_G1_Quest3S_TEST
```

Do not delete them until the user explicitly decides cleanup is safe.

### 5.2 Oculus XR deprecation warning

Unity currently shows an `Oculus Plugin Deprecation` dialog stating that the Oculus XR plugin provider is deprecated on Unity 6+ and recommending OpenXR.

Current decision:

- click `OK` and continue working
- do not use `Dismiss forever` yet
- do not immediately migrate while the current teleoperation path is stable
- OpenXR migration should be treated as a separate controlled task with regression testing of Quest hand tracking, Unity XR rig/input, Meta XR SDK behavior, and build/runtime behavior

## 6. WSL / Windows environment

WSL installation is complete.

Windows / WSL observations:

```text
WSL: 2.7.12.0
WSL kernel: 6.18.33.2-2
Ubuntu: 26.04 (Resolute Raccoon)
Python in WSL: 3.14.4
```

WSL repo path:

```text
/mnt/c/Users/user/Desktop/G1_Teleop_Project
```

Git initially reported dubious ownership under WSL.
This was addressed with:

```bash
git config --global --add safe.directory /mnt/c/Users/user/Desktop/G1_Teleop_Project
```

Current WSL networking before physical G1 Ethernet work:

```text
eth0: 172.20.140.130/20
mode: default WSL2 NAT
```

Windows active interfaces observed at the checkpoint:

- Wi-Fi: MediaTek Wi-Fi 6E MT7922
- WSL virtual Ethernet: active
- physical Realtek Gaming GbE Family Controller: disconnected

## 7. Physical G1 hardware integration status

Physical G1 Ethernet integration has **not started yet**.
The user explicitly postponed it after preparing WSL.

Current hardware status:

- G1 not yet connected to PC by Ethernet
- Realtek physical Ethernet was disconnected at last check
- Unitree SDK2 not yet installed/configured in the WSL hardware path
- no real G1 actuator command has been sent from this project

Planned architecture:

```text
Quest / Unity (Windows)
    -> desired target
Mink IK controller
    -> desired right-arm joint state
Hardware Safety Gate
    -> validated command
Unitree SDK2 / DDS
    -> Physical G1 right arm
```

Planned hardware integration order:

1. Connect PC <-> G1 by physical Ethernet.
2. Verify Windows Realtek NIC link and actual G1 subnet/IP configuration.
3. Configure WSL networking suitable for DDS/multicast, likely mirrored networking if required.
4. Establish a compatible Python environment for Unitree SDK2; do not assume WSL Python 3.14 is the desired SDK runtime.
5. Install/configure Unitree SDK2.
6. Implement **read-only `LowState` reception first**.
7. Verify G1 model/DoF count, joint ordering, right-arm joint mapping, state values, packet frequency, and timeout behavior.
8. Build the project-owned Hardware Safety Gate.
9. Only after read-only and safety validation, connect the command publisher.

Do not begin physical testing by publishing `LowCmd` blindly.

## 8. Hardware Safety Gate requirements

Before allowing actual G1 right-arm commands, the hardware-side adapter/gate should independently enforce at least:

- startup state validation
- explicit operator enable/engagement state
- packet/session timeout watchdog
- joint position limits
- joint velocity limits
- per-cycle `delta q` limit
- collision/workspace fault handling
- non-right-arm DOF hold/freeze policy
- safe disengagement/hold behavior
- command rejection on invalid/stale state

Unity-side safety is not sufficient by itself; the hardware backend must enforce safety independently.

## 9. Git/stash status

`git stash list` was empty when checked on 2026-08-26. The earlier
`before-sync-f28689d` stash warning is therefore stale and no longer an active
recovery path.

The worktree remains intentionally dirty with the protected calibration and
Unity/project-generated changes listed above. Inspect `git status` and file
diffs before reset, checkout, clean, or bulk restore operations.

## 10. Current priority / next work

Immediate next task:

```text
restart the Mink controller and run one live Quest/Unity/MuJoCo regression
```

Acceptance checks for that regression:

- engagement causes no target jump
- brief tracking loss enters hold and resumes without recalibration
- duplicate or stale packets do not move the robot target
- sustained manual pinch clears engagement
- returning to the engagement target creates a new zero-jump reference
- Unity markers and MuJoCo state agree on requested, feasible-target, and actual wrist positions

After this regression passes, resume physical G1 connection preparation from
Ethernet/NIC and read-only `LowState` verification. Do not start with actuator
commands.

When that resumes, begin from Ethernet/NIC state verification, not actuator commands.

OpenXR migration is a separate later stabilization/refactor task and is not the current blocking issue.

## 10.1 Live Quest regression evidence on 2026-08-26

The live trace written at `13:48:23` contained 2,762 rows and 2,387 active
command rows. The corrected yaw-wrist frame contract is working:

- operator/sender delta to backend green-target delta: 1.35 mm average over
  the final 30 active rows, 6.29 mm maximum
- final component mismatch: less than 0.1 mm on every axis
- backend green target to actual G1 wrist: 102 mm average over the final 30
  active rows
- collision avoidance was near its configured boundary in 1,500 of 2,387
  active rows
- the final constrained pose had 5.1 mm torso-to-right-shoulder-yaw clearance
  and 11.2 mm right-elbow-to-right-wrist-yaw clearance

This means the current visible lag is no longer an input-to-green transport or
coordinate-frame error. It is in the green-target-to-robot IK/collision stage.
Do not restore `structural_neighbor_distance=3`: earlier live evidence showed
that doing so permits a body-penetrating shoulder solution. A future reachable
target planner must preserve the current collision authority while providing a
stable feasible look-ahead target.

Unity visualization cleanup after this regression:

- `G1UnityRightArmPreview` is the single owner of cyan input, white/yellow/green
  engagement target, magenta actual wrist, and the white path line
- removed the duplicate always-on magenta wrist marker that covered the
  white/yellow engagement feedback
- removed obsolete runtime overlays that searched for the no-longer-existing
  `operator_hand_target_marker` and could no longer represent the current
  preview contract
- the green marker now renders the current local Unity command directly; it is
  no longer overwritten by a delayed MuJoCo state echo, which previously caused
  up to 54 mm of transient visual lag after fast hand motion
- the magenta wrist and G1 arm remain driven only by returned MuJoCo joint state

Second live Quest regression at `14:00:36`:

- 1,765 trace rows, 1,638 active command rows
- backend target to actual G1 wrist error averaged 18.8 mm over the complete
  active interval, substantially lower than the preceding regression
- the final 30 active rows averaged 68.8 mm because the requested 6D pose became
  infeasible under the simultaneous joint/collision constraints
- final active `right_wrist_roll_joint` was exactly at its -113 degree lower
  limit; wrist pitch/yaw and elbow also reached their limits at points during
  the run
- the final nearest collision pair was torso-to-right-shoulder-yaw at 27.8 mm,
  inside Mink's 40 mm detection/slowdown range but outside the 12 mm minimum
- therefore the remaining late-run position lag is not evidence of another
  coordinate-axis regression; it is a 6D feasibility/prioritization problem

Next controller correction should preserve position tracking when requested
orientation is infeasible, redistribute wrist rotation into proximal redundancy
before the hard wrist limit, and saturate only the infeasible orientation
component. Do not weaken the torso collision pair or expand joint limits.

Adaptive wrist-limit orientation policy implemented after that regression:

- proximal orientation assistance begins at 18 degrees of remaining wrist range
  and releases only after recovery to 28 degrees
- assistance reaches full Jacobian authority within 5 degrees of a wrist limit
- orientation cost scales down to 25 percent and one-cycle orientation error is
  capped at 12 degrees near a hard wrist limit, so position remains the priority
- normal wrist motion retains zero proximal assistance and full orientation cost
- Mink's optimized `compute_qp_residual` path is explicitly covered; updating
  only `compute_qp_objective` does not affect the installed Mink solver
- offline G1 model test at -112 degree wrist roll plus a further 20 degree roll
  request kept the wrist at -113 degrees, redistributed motion proximally,
  produced 0.073 mm position drift, and left 0.484 degree orientation error
- the normal-range comparison moved only wrist roll by about 20 degrees and
  left proximal joints unchanged
- Unity state/CSV diagnostics now include orientation error, assist gain,
  orientation cost scale, and minimum wrist-limit margin

Live tuning after the next Quest test:

- the adaptive orientation policy engaged as intended at a 15.3 degree wrist
  margin with a measured assist gain of 0.185
- final 30-frame position error averaged about 9.4 mm
- operator requested a very small speed reduction, so the virtual-center live
  right-arm joint velocity limit changed from 50 deg/s to 45 deg/s
- no target mapping, orientation policy, collision margin, or joint-position
  limit changed with this speed adjustment

Broad live-motion regression after the 45 deg/s adjustment:

- 1,641 trace rows, 1,559 active rows over about 54 seconds
- the operator deliberately swept the hand in many directions; measured target
  speed averaged 0.258 m/s, reached 0.657 m/s at the 95th percentile, and peaked
  at 1.694 m/s
- peak target-to-wrist position lag was 255 mm during the fastest direction
  reversal; this was rate-limit lag rather than a lost packet or axis change
- after the hand settled, the final 30-frame position error averaged 0.37 mm
- adaptive wrist assistance activated for 120 frames, reached gain 1.0, and
  reduced orientation cost to the intended 0.25 minimum
- the test exercised both elbow operational limits (5 and 120 degrees) and the
  +113 degree wrist-roll limit without expanding any limit
- collision proximity was reported for 49 percent of active rows; no collision
  setting was weakened after the test
- keep the 45 deg/s setting: the observed large transient lag is the intended
  consequence of moving the human target much faster than the safety-limited
  robot, while settled tracking remains sub-millimeter

## 11. Inspection demonstration checkpoint

The first complete inspection task loop is now connected without changing the
teleoperation IK, collision authority, clutch semantics, or joint limits.

- MuJoCo retains the existing inspection panel and wrist-mounted probe, and now
  exposes a named target point on the robot-facing panel surface
- target evaluation uses the actual simulated `inspection_tool_tip_body`
  position, not the requested wrist target
- the state sequence is `waiting -> approach -> holding -> complete`
- approach begins within 80 mm; contact requires the tool tip to remain within
  40 mm for 0.75 seconds; leaving contact before completion resets only the
  hold timer
- completion remains latched until the next clutch engagement
- the target is blue while waiting, yellow during approach, orange while the
  contact timer fills, and green after completion in both MuJoCo and Unity
- Unity receives the panel position, panel size, target position, tool-tip
  position, distance, progress, elapsed time, and completion state through the
  existing robot-state UDP packet; it remains visualization-only
- completed runs append to `logs/inspection/inspection_runs.csv`, including
  elapsed time, final/minimum target distance, mean IK error, minimum wrist
  limit margin, and collision-nearby ratio
- target packets declare `target_source=static_demo`; a future detector can
  replace that target source without changing IK or Unity's state contract
- `START_VR_HAND_TO_MUJOCO.bat` now selects the virtual-center controller by
  default; `--baseline` is retained only for explicit comparison

Verification on 2026-08-26:

- 29 focused backend tests passed, including the new deterministic inspection
  state and CSV tests
- the generated MuJoCo model loaded with named target body/geometry present
- `Assembly-CSharp.csproj` built with 0 errors (existing warnings remain)
- the full 143-test backend run had one unrelated existing fake-VR trajectory
  tolerance failure: 21.3 mm measured against a 10 mm threshold
- Quest visual placement and a real hand-driven target completion still require
  one live run after restarting the already-running controller process

First live inspection run after this checkpoint:

- 1,416 Quest packets were accepted and none were rejected
- inspection completed in 4.171 seconds after the tool tip remained within the
  contact radius; final/minimum tool-to-target distance was 24.177 mm
- the completed run was written to `logs/inspection/inspection_runs.csv`
- Unity trace contained 1,015 active samples over 28.25 seconds
- active position error averaged 37.3 mm, peaked at 129.5 mm during motion, and
  averaged 18.4 mm over the final active second
- final active-second orientation error averaged 0.64 degrees
- the trace reported collision proximity in 13.0 percent of active samples and
  the final elbow reached its 5 degree operational lower limit
- the runtime status reported zero minimum clearance at the final posture, but
  reconstructing the same seven logged joint angles in the generated model
  produced 65.8 mm minimum clearance; treat the runtime collision diagnostic as
  unresolved rather than evidence of a physical collision
- completion intentionally remains latched after the probe retracts, so the
  later 117 mm tool-to-target distance does not invalidate the completed run

Post-test collision diagnostic and inspection ergonomics correction:

- the scalar collision helper now preserves the identity of the nearest geom
  and body pair; runtime state records both names with the measured clearance
- the controller was restarted and reported the initial nearest pair as
  `torso_link` to `right_shoulder_yaw_link` at 40.38 mm, just outside the
  configured 40 mm collision-detection distance
- the previous final `0 mm` runtime value could not be reproduced from the same
  seven logged arm joints: `mj_forward`, `mj_fwdPosition`, and Mink update all
  returned 65.8 mm; the new pair identity fields are required before treating a
  future zero reading as a physical collision
- simply increasing posture cost was rejected because it bent the elbow by
  trading away 6D wrist accuracy
- replaying the completed wrist orientation across panel target candidates
  showed that moving the target 40 mm outboard, from robot Y=-0.16 m to
  Y=-0.20 m, changed the preferred elbow from the 5 degree extension limit to
  about 20.5 degrees while retaining 0.5 mm static position error and 53.4 mm
  collision clearance
- only the static inspection target moved; IK weights, joint limits, collision
  limits, clutch behavior, and the physical panel dimensions are unchanged
- 31 focused tests pass; the complete 145-test suite still has only the known
  legacy fake-VR trajectory failure (21.3 mm against its 10 mm threshold)

Second live inspection run and follow-up correction:

- completion improved from 4.171 to 3.891 seconds; final contact distance stayed
  effectively identical at 24.172 mm
- completion-run mean IK error improved from 54.8 to 44.9 mm and its recorded
  collision-nearby ratio improved from 9.7 to 7.0 percent
- 1,556 packets were accepted with zero rejection
- the full active trace averaged 34.1 mm position error and 20.9 degrees
  orientation error; large operator motion produced 119.4 mm peak position lag
- full-run collision proximity was 28.8 percent, but the completion window had
  no collision-proximity frames
- the terminal elbow recovered to about 29 degrees, but the actual completion
  window still sat at the 5 degree elbow-extension limit; the first 40 mm target
  shift therefore did not solve the inspection-pose issue
- replaying the second run's actual completion orientation showed Y=-0.28 m
  gives about 20.2 degrees elbow bend, 0.5 mm static position error, and 47.2 mm
  clearance; the target was moved from Y=-0.20 m to Y=-0.28 m within the same
  panel dimensions
- runtime collision status once reported `right_shoulder_yaw_link` to
  `right_wrist_yaw_link` at 0 mm while reconstructing the logged joints gave
  133.5 mm for that pair and 11.6 mm for the actual nearest torso/shoulder pair
- collision diagnostics now compare current MuJoCo data against a fresh
  `MjData` forward pass from the exact same qpos and record qpos delta, distance,
  geom names, and body names for both paths
- post-integration state refresh now uses full `mj_forward` instead of partial
  `mj_fwdPosition`; the restarted idle controller reports matching 40.38 mm
  clearances, matching torso/shoulder pair names, zero qpos delta, and a 1.00 ms
  mean control cycle
- 31 focused tests pass after these changes; no IK weight, joint limit, collision
  distance, clutch rule, or tool geometry changed

Third live inspection run and operator speed adjustment:

- completion improved again to 2.969 seconds with 17.656 mm final contact
  distance and 17.519 mm minimum distance
- the completion-run mean IK error improved to 18.0 mm; the narrow completion
  window averaged 2.05 mm position error
- 1,022 packets were accepted with zero rejection
- the final 30 active frames averaged 0.67 mm position error and 0.48 degrees
  orientation error
- current-data and fresh-data collision diagnostics matched exactly with zero
  qpos delta; at the terminal posture both identified torso-to-right-shoulder
  yaw at 17.35 mm
- the complete trace spent 66 percent of active samples inside the 40 mm
  collision-detection zone, while the completion window was 8.7 percent; the
  broad-motion collision exposure remains a separate posture-planning issue
- despite moving the task point farther outboard, the actual completion window
  still reached the 5 degree elbow limit; do not claim the elbow-pose issue is
  solved by target placement alone
- at the operator's request, virtual-center right-arm joint velocity was reduced
  slightly from 45 to 42 degrees per second; no other controller setting changed

Fourth live inspection run at 42 degrees per second:

- inspection completed in 2.813 seconds with 14.243 mm final and 13.178 mm
  minimum tool-to-target distance
- completion-run mean IK error improved to 8.5 mm; the narrow completion window
  averaged 0.74 mm position error and 0.18 degrees orientation error
- completion-window elbow averaged 16.9 degrees instead of remaining on the
  5 degree extension limit, and no completion-window frame entered collision
  proximity
- 1,097 packets were accepted with zero rejection
- across all broad operator motion, position error averaged 19.9 mm and peaked
  at 116.5 mm; the final 30 active frames averaged 10.0 mm
- the whole run spent 51.4 percent of active samples within the conservative
  40 mm collision-detection zone, so this broad-motion metric should not be
  confused with the clean inspection-contact window
- current and validation collision diagnostics remained identical with zero
  qpos delta; terminal clearance was 41.96 mm between the right elbow and right
  wrist-yaw bodies
- keep the 42 degree-per-second limit and Y=-0.28 m inspection target for the
  current demonstration baseline

## 12. Handoff maintenance

### Physical G1 read-only Ethernet bring-up (2026-08-26)

- G1 is connected through the `ASIX AX88772A USB2.0 to Fast Ethernet Adapter`
  at 100 Mbps; Windows adapter alias was `이더넷 4` during bring-up.
- Passive capture confirmed the existing robot subnet before changing the host:
  `192.168.123.120`, `.161`, and `.164` were active. No G1 address was changed.
- The host adapter is configured as `192.168.123.99/24`; `.99` was not observed
  on the wire before assignment. `RESTORE_G1_ETHERNET_DHCP.bat` restores DHCP.
- WSL2 now uses mirrored networking through `%USERPROFILE%\.wslconfig`; the G1
  interface appeared as `eth3` in this session, but launchers must detect it by
  address because the interface number may change.
- `/home/user/.venvs/g1-teleop` contains Python 3.11 and the official
  `unitree_sdk2_python`; CycloneDDS 0.10.x is built under
  `/home/user/cyclonedds/install` as required by the official SDK README.
- Windows and Hyper-V firewall rules named `G1-DDS-to-WSL-Host` and
  `G1-DDS-to-WSL` allow inbound traffic only from `192.168.123.0/24`. The
  protocol rule is not port-only because fragmented DDS datagrams were being
  dropped after their first UDP fragment.
- `read_only_lowstate.py` received about 7,600 packets in eight seconds with
  typical age below 1 ms and continuously reported right-arm joints 22-28.
- The verified process contained no DDS publisher and sent no robot command.
- `tools/START_G1_READ_ONLY.bat` repeats this read-only test and automatically
  selects the WSL interface carrying `192.168.123.99/24`.
- Physical Ethernet disconnect was deliberately tested after continuous state
  reception. The monitor stopped fail-closed at `1.011 s` with
  `FAULT / LOWSTATE_TIMEOUT`, and sent no command.
- Ethernet was reconnected afterward; both `.161` and `.164` responded and
  `rt/lowstate` resumed with sub-millisecond typical age.
- Gate 1 read-only requirements are complete. Gate 2 joint index/sign mapping
  is next. Do not introduce a command publisher yet.
- Gate 2 elbow probe used manual motion while the G1 was safely suspended by
  shoulder straps. Hardware index 25 moved through 57.40 degrees; the next
  largest joint was shoulder pitch at 6.43 degrees, confirming index 25 as the
  right elbow. The sign of intentional flexion is not yet separately verified.
- The reusable read-only probe is
  `hardware/g1_arm_bridge/probe_joint_motion.py`; the recorded elbow result is
  `logs/runtime/g1_joint_mapping_elbow.json`.
- Gate 2 wrist-roll probe used the same read-only manual-motion procedure.
  Hardware index 26 moved through 102.92 degrees; wrist yaw and wrist pitch
  moved through 18.99 and 5.67 degrees respectively during the compound wrist
  motion. This confirms index 26 as right wrist roll, but its intentional
  direction/sign is not yet separately verified. The recorded result is
  `logs/runtime/g1_joint_mapping_wrist_roll.json`.
- The remaining right-arm indices use Unitree's official G1 7-DoF SDK mapping;
  the elbow and wrist-roll spot checks matched it, so further manual joint
  probing was stopped.
- Gate 3 captured a fresh physical G1 right-arm pose over read-only LowState and
  WSL-to-Windows UDP 5007: `[6.44, -2.84, -18.27, 75.01, -15.76, -6.78,
  -1.60]` degrees. The result is
  `logs/runtime/g1_hardware_initial_state.json`.
- Windows firewall rule `G1-LowState-to-Windows` permits only inbound UDP 5007
  from `LocalSubnet`; `tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat` recreates it.
- `hardware/g1_arm_bridge/verify_initial_pose_sync.py` verified the captured
  vector through the current Mink model and Unity state-packet contract. Both
  maximum errors were `3.469e-18 rad`; no viewer, DDS publisher, or robot
  command was used. Unity avatar display and first-clutch no-jump behavior still
  require a live Play-mode check.
- `tools/START_MINK_G1_HARDWARE_SYNC.bat` now validates the pose before starting
  the current virtual-center controller rather than the obsolete baseline
  controller. Hardware output remains disabled.
- Live Gate 3 startup opened the current controller on UDP 5005 and Unity on
  UDP 5006. `Unity_G1_VR/Logs/live_quest_trace.csv` reported `backend_recent=1`
  and the same seven captured joint values; the controller accepted more than
  2,000 idle Unity packets with zero rejection and remained clutch-disengaged.
- The captured hanging-arm pose is the robot's normal rest posture, so the
  operator must not be required to move the arm manually before every startup.
  It is valid for measured-pose HOLD but is not yet a teleoperation-ready pose.
- `hardware/g1_arm_bridge/diagnose_initial_pose_collision.py` compares the
  measured rest pose, configured ready pose, and all-zero pose without sending
  a command. The measured rest pose has five pairs inside the 12 mm Mink margin,
  led by right hip-pitch to wrist-yaw at 0 mm; the configured ready pose has no
  pair inside the 40 mm detection distance.
- A 101-sample direct joint interpolation from measured rest to configured
  ready is not accepted as a startup trajectory: it introduces a new
  torso-to-right-shoulder-yaw inside-margin pair and only remains permanently
  clear after approximately 49 percent of the path. Implement and dry-run a
  collision-aware `REST_HOLD -> TRANSITION_TO_READY -> TELEOP_READY` sequence
  before any command publisher is introduced.
- The upstream Mink G1 example is not a hardware startup-recovery reference. It
  resets its kinematic configuration directly to the XML `teleop` keyframe and
  registers only hand-to-table and same-side hand-to-thigh collision pairs.
- A deterministic offline startup planner was added at
  `hardware/g1_arm_bridge/plan_startup_transition.py`. All 120 one-group-at-a-
  time joint orders failed. A coordinated RRT candidate passed a coarse 0.25
  degree check but correctly failed the runtime-equivalent 0.03 degree swept
  check; the strict search therefore remains fail-closed and writes no command.
- Do not weaken the collision floor or copy the upstream keyframe into a motor
  command. The next startup experiment is an offline Mink QP recovery initialized
  with measured LowState, a low-velocity posture target, the project's complete
  right-arm collision set, and the final swept-path guard. A hardware publisher
  remains prohibited until that recovery converges repeatedly in simulation and
  acceleration/jerk and stale-state gates are present.
- That offline recovery experiment is now implemented in
  `hardware/g1_arm_bridge/simulate_startup_recovery.py`. A direct posture task
  was rejected because it crossed a mesh collision between QP endpoints. The
  accepted policy first moves the yaw-wrist frame 18 cm outward and 8 cm upward,
  brakes to a stop, then switches to the startup safe-ready posture after the
  initial proximity set clears its hysteresis boundary.
- The startup controller now runs at 500 Hz and limits velocity, acceleration,
  and jerk online to 8 deg/s, 30 deg/s^2, and 300 deg/s^3. QP velocity is capped
  at 6 deg/s, with a 0.5 deg/s fine-positioning mode. Every proposed and replayed
  update is checked at 0.001-degree startup resolution.
- Mesh-distance feature switching near the normal arm-down posture required a
  recovery policy based on the initially observed 40 mm proximity body-pair set.
  No new body pair may enter 12 mm. The initial set must completely clear 40 mm
  before the latch changes to strict 12 mm no-reentry behavior.
- The startup safe-ready posture is `[10, -30, 0, 55, 0, 0, 0]` degrees. It is a
  startup-only posture with about 50.8 mm model clearance; the previous -22 degree
  shoulder-roll posture is only about 40.4 mm from the nearest torso/shoulder-yaw
  mesh pair and remains unchanged for the existing simulation configuration.
- The accepted state sequence is `ESCAPE_BODY -> ESCAPE_BRAKE_HOLD ->
  TRANSITION_TO_READY -> READY_BRAKE_HOLD -> READY_FINE_POSITIONING`. The latest
  deterministic dry-run completed in 22.354 s with 11,178 samples, 0.302-degree
  final error, 7.468 deg/s maximum velocity, 30.000 deg/s^2 maximum acceleration,
  300.000 deg/s^3 maximum jerk, and 50.395 mm final model clearance. Independent
  swept-path replay and Safety Gate passed; stale LowState returned no command
  candidate.
- This result remains `hardware_ready=false`. The numeric motion limits are
  engineering dry-run values, not approved physical-G1 limits. Repeat from
  multiple fresh rest-pose captures and obtain hardware-side approval before a
  publisher is introduced.
- Tool cleanup on 2026-08-26 removed 17 obsolete BAT wrappers: broken launchers
  whose `scripts/...` targets no longer exist, one-time palm-center patching,
  superseded role-split/A-B experiments, and old torso-posture helpers. The
  superseded Python diagnostics tied only to those experiments were also removed.
- `tools/` now retains 20 BAT entry points covering the current VR launcher
  support, frame/FK checks, hardware read-only synchronization, safety dry-run,
  network setup/recovery, APK build, and camera foundation validation.
- Documentation no longer references the deleted BAT names, `git diff --check`
  passes, and `START_VR_HAND_TO_MUJOCO.bat --check` passes. Meta Horizon Link,
  Unity, and the Mink controller were not running during this static check.
- Unused Unity legacy assets were removed after checking active scene and code
  GUID references: DSManipulator, bHaptics, InControl, MathNet/FSharp, imported
  XR samples, and imported TextMesh Pro essentials.
- Non-G1 Unitree robot assets and superseded IK comparison/diagnostic scripts
  were removed. `START_MUJOCO_ONLY.bat` now launches the current virtual-center
  Mink controller.
- Unreferenced backend monkey-patch modules from retired controller experiments
  and their obsolete joint-posture profile were removed. The active protocol,
  command stream, Mink controller, collision diagnostics, hardware bridge, and
  camera foundation remain intact.
- Post-cleanup validation: Python compileall passed, 12 hardware bridge tests
  passed, `START_VR_HAND_TO_MUJOCO.bat --check` passed, and the Unity 6000.5.4f1
  batch validator passed after reimporting the reduced asset set.
- The first post-cleanup backend run was 144/145: the retained fake-VR
  trajectory test reported 0.021299 m maximum tracking error against a 0.01 m
  diagnostic limit.
- Follow-up diagnosis showed that failure belonged to the retained legacy DLS
  path: after a closed trajectory it remained in a path-dependent local solution
  with 0.0213 m position error, despite no collision, joint limit, or singularity.
  The obsolete DLS trajectory test and its private fake sender were replaced by
  a current virtual-center Mink convergence and velocity-limit regression test.
- Final validation is 145/145 backend tests and 12/12 hardware bridge tests.

The operating rules at the top of this file are the authoritative instructions for future ChatGPT conversations.

Future updates should maintain this document as the current project checkpoint, including:

- completed work
- current work in progress
- important design decisions
- protected local changes
- unresolved issues and cautions
- environment/hardware state
- next steps

A new chat should not require the user to restate these rules. Reading this file is sufficient.
