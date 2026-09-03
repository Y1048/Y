# G1 Teleop Project Chat Handoff

> **Absolute G1 mutation rule:** Never create, delete, rename, move, or modify
> any file on the G1; never run a program that can create a log, publish a
> command, change a service/mode, or otherwise mutate G1 state without the
> user's explicit approval for that exact action. Inspect source before running
> any diagnostic because a nominally read-only test may still write a CSV or
> other artifact. Remote-to-local `scp` is allowed only when it reads existing
> G1 files and writes exclusively to the Windows project. Shell inspection is
> limited to commands already verified to be non-mutating, such as `ls`, `cat`,
> `sed`, `find`, `pgrep`, and `ip` without configuration options.

Last updated: 2026-09-03

## GitHub review continuation

- Branch: `refactor/teleop-architecture` in `Y1048/Y`. Start with
  `docs/REVIEW_20260903.md` (R1-R19), then `docs/CODE_GUIDE.md` and `docs/CODE_INDEX.md`.
- `logs/review/20260903/` is deliberately included as a bounded audit snapshot,
  despite the general logs ignore rule. `source_checks.csv` records 117 full-text
  reviews and 147 static-only files. Filter the `semantic_review` column to find
  the remaining files; a listed file is not proof of full review or correctness.
- This is a review handoff, not a completed safety release. Known findings remain
  unfixed. Do not remove safety checks or change gains merely to make tests pass.
  No hardware output, G1 mutation, or deferred strategy-atlas work is authorized.
- The audit hashes/results predate the intentional speed edit below. The current
  virtual-center source retains `math.degrees(0.08)` for both velocity caps; the
  later conversation about 40/100 deg/s did not change the saved file. Current
  file hashes are in CODE_INDEX.md. Recheck changed files before reusing evidence.
- Captures/runtime logs outside this audit snapshot and imported TWIST2 CSVs are
  not uploaded. Some reproduction tools require local snapshots/models/runtime
  dependencies and may not run unchanged in a GitHub-only environment.
- Prior passing tests do not establish safety of the current physical path.
  Preserve the distinction between packet/AST tests, simulation, and physical tests.

## Latest checkpoint: match static-stand default arm speed (2026-09-03)

- User requested matching the two virtual-center velocity caps to static stand.
  Local reference twist2_static_stand.cpp:52 uses kKeyboardBaseTargetRate=0.08 rad/s,
  starts keyboard_speed_multiplier at 1, and applies the same rate to all seven arm
  joints. Keys 1-9 select multiples; 1.5 rad/s is a measured-velocity fault threshold,
  NOT the target speed. The separate automatic shoulder trajectory is not this rate.
- Changed only the two Mink virtual-center velocity constants to math.degrees(0.08),
  approximately 4.583662 deg/s each, from 40/100. CODE_GUIDE current-values updated.
  Same rate number does not imply identical QP/rate-limiter dynamics or measured speed.
- No G1 access, C++ reference edits, hardware-profile changes, output unlock or launch.
  Prior review results describe the earlier snapshot; the velocity change is intentional.
  Previous trajectory accuracy/timing results are not revalidated at this slower speed.
- Verified AST syntax and the actual extracted velocity-limit helper: all seven
  limits equal the reference's 0.08 rad/s (0.076394 deg per 60 Hz step). All ten
  hardware flags remain false. Code index regenerated and --check passed; scoped
  diff whitespace check passed. No IK trajectory, Unity/Quest or physical test run.

## Previous checkpoint: camera and saved-state review continuation (2026-09-03)

- Added full-text review of ten files: camera replay and saved-LowState replay,
  four unit-test files and four camera/viewer BATs. Coverage 117/264; 147 static-only.
  Re-read the existing camera bridge, WSL starter and Unity display selection path.
- R18 (P2): saved replay, including a validation-only fallback, exports the live
  g1_lowstate_read_only source with a new timestamp. Normal saved BAT sets recorded
  mode, but the packet/Unity receiver does not enforce recorded vs live provenance.
  Python conversion reproduced offline; actual Unity mislabel runtime NOT tested.
- R19 (P3): camera replay --quality is validated but not passed to BuildReplayJpeg.
  Fake-transport main requested 40 yet produced byte-identical quality-82 JPEG.
- Existing related tests: 21 PASS with all socket creation blocked. No Unitree SDK
  import, Unity/viewer/WSL/G1 runtime. Evidence: logs/review/20260903/
  review_camera_state_checks.py, camera_state_review_checks.json,
  camera_state_related_tests.log.
- Additional boundaries recorded: synthetic camera banner distinguishes replay;
  frames_sent PASS does not prove Unity display; camera discards source timestamp;
  partial-frame blocking Read/reconnect needs runtime tests; NaN CLI values pass;
  saved LowState replay is a fixed pose, not a motion recording.
- All 264 indexed code/config hashes unchanged and ten hardware flags false.
  Code index --check passed; report's 56 local links exist; scoped docs diff check passed.
  Report/handoff/coverage ledger and ignored audit artifacts only changed.
  No production fixes, deletion, push, physical output or G1 mutation.
- Next: remaining benchmark/tests/launchers and serialized Unity assets. Keep
  R1-R3 and R15 prioritized before enlarging physical trials; review is not complete.

## Previous checkpoint: capture and replay review continuation (2026-09-03)

- Full-text review added 16 files: capture/replay/quality/regression/fault-matrix/
  virtual E2E, experimental wrapper, four tests and four BATs. Total 107/264;
  157 remain static-only. Review-only; no production fixes or hardware changes.
- R15 (P1): normalized replay rewrites timestamp/session/age and sends to the same
  5008 port as live input. Fake transport through the real relay plus hardware
  trajectory factory reached TRACK_MINK_RIGHT with SDK-neutral frames. This
  does NOT unlock hardware; risk requires an already authorized running live path.
- R16 (P2): both capture loaders accept conflicting manifest/record IDs and
  metadata/payload sequences/modes, including payload sequence 10 -> 9. Replay
  normalization hides the original sequence reversal. Payload hash excludes timing.
- R17 (P2): one-packet and zero-total-duration captures raise ZeroDivisionError
  in quality metrics, despite recorder/loader accepting them.
- Reproductions: logs/review/20260903/review_capture_checks.py and
  capture_review_checks.json. All socket creation was blocked; only fake transport,
  local fixtures, SDK-neutral controller/frame construction. Unitree SDK not imported.
- Existing quality/fault tests: 4 PASS in capture_related_tests.log. Process-level
  capture/replay and virtual E2E tests read but NOT run this pass because their
  CollisionPathValidator regenerates operational model XML. No Unity/viewer/G1.
- Clarified report boundaries: ideal measured=command feedback, always-true
  collision callbacks in some tools, different controller profiles, TRACE_ONLY or
  baseline-written not equivalent to regression comparison, validate-only not collision proof.
- All 264 code/config hashes unchanged; all 10 hardware authorization flags false.
  Report/handoff/coverage ledger and audit artifacts only updated. No deletion/push.
- Next: remaining camera/LowState replay, benchmark/test/launcher semantics and
  serialized Unity assets. R1-R3 plus R15 are priority before enlarging physical trials.

## Previous checkpoint: Unity source review continuation (2026-09-03)

- Read 13 more files fully: nine remaining scoped Unity C# files, FK exporter,
  FK BAT and two related Python test files. Coverage is 91/264; 173 remain static-only.
  All scoped Unity C# text has been reviewed, NOT all vendor code/assets or runtime.
- Report R13: scene/setup/batch validator require skeleton wrist=true, while
  runtime compatibility overwrites it false every frame. Preserve intentional
  source_hand compatibility until a single reviewed policy replaces the conflict.
- Report R14: official-model rebuild deletes the existing resource directory
  before XML/mesh/body validation; failure does not restore the old prefab.
  Do not run the rebuild merely to reproduce this in the working project.
- Clarified boundaries: hardware model display selects measured state, but green
  feasible target and live_quest_trace remain Mink candidate diagnostics. FK parity
  compares four wrist position deltas, not absolute position, orientation or all joints.
- Existing tests: 12 PASS (11 source-string tests, one copied PS1 tempfile test).
  Evidence and log: logs/review/20260903/review_unity_checks.py,
  unity_review_checks.json and unity_related_tests.log. No Unity runtime or G1 access.
- All 264 indexed code/config hashes unchanged; all ten hardware authorization
  fields remain JSON false. Updated report, review ledger and handoff only, plus
  local audit artifacts. No controller/config edits, deletion, push or physical output.
- Full serialized prefab graph/numerical FK validation remains outstanding. YAML
  parsers were unavailable in local/bundled runtimes; no packages installed and no
  regex-only substitute was presented as a complete serialized-asset validator.
- Next: remaining capture/replay/benchmark/launcher semantics and Unity runtime
  validation. R1-R3 remain the priority fixes before expanding physical trials.

## Previous checkpoint: startup and telemetry review continuation (2026-09-03)

- Added 19 full-text reviews: startup readiness, Gate 5, collision diagnostics,
  staged/RRT planner, Mink recovery, ready-pose editor, replay, live MuJoCo mirror,
  motion-mode query, joint contract, four related test files, two configs and
  three offline BAT launchers. Total is now 78/264; 186 remain static-only.
- Appended R8-R12 to `docs/REVIEW_20260903.md`. Fake-clock collection shows a
  0.9-second-old final LowState can pass readiness with a 0.25-second timeout.
  Recovery helpers reset non-right-arm qpos to defaults rather than preserving
  the measured full-body snapshot. Injected clearance 5/-2/15 mm passes the final
  recovery path validator because the existing contact pair remains unchanged.
- Telemetry parser accepts conflicting right-arm and full-body q/dq. Live mirror
  accepts old-session -> new-session -> old-session and ignores source timestamp
  freshness. Also reproduced NaN replay timestamps passing LoadRecovery before
  InterpolatePose fails with IndexError (lower priority).
- Reproduction: `logs/review/20260903/review_startup_checks.py` and
  `startup_review_checks.json`. Geometry response injection proves validator
  conditions, NOT an actual colliding G1 path. Full-body reset was tested against
  the existing MuJoCo model in memory without regenerating XML.
- Existing startup/Gate 5/collision tests: 20 PASS, saved in startup_unit_tests.log.
  One test uses localhost UDP; no robot/WSL connection or physical publisher.
- All 264 indexed code/config hashes remained unchanged from the previous
  review snapshot; all ten hardware authorization fields remain boolean false.
  Only audit artifacts, report and this handoff changed. No controller fixes,
  gain changes, G1 operations, deletion, or push. Deferred strategy atlas untouched.
- Next review: Unity preview/Editor and serialized references, then remaining
  capture/replay/benchmark/launcher files. Do not call all files fully reviewed.

## Previous checkpoint: detailed review, incomplete coverage (2026-09-03)

- User requested a detailed review of all files. The first review report is
  `docs/REVIEW_20260903.md`; do not call the entire repository fully reviewed.
- Inventoried 47,796 files excluding .git and this audit output. Scoped static
  checks cover 264 source/config files (46,832 lines); 59 received full-text
  review and 205 remain static-only. Exact paths/hashes/depth are recorded in
  `logs/review/20260903/source_checks.csv` and `reviewed_paths.txt`.
- Confirmed offline: Gate 7 release exceptions can retain passed=true/exit 0;
  Gate 6 acquire interruption raises weight from 0.02 to 0.2; string "false"
  authorizes the hardware config loader; old source timestamps can be treated
  as fresh commands. Ruckig-shaped active output has no final collision check.
- Unity review found no session/sequence freshness rejection in state display,
  and sender filters/disengage timers use nominal send_interval rather than
  actual elapsed time. Unity runtime reproduction remains outstanding.
- Backend 210 and hardware 168 tests PASS. Seven extracted TWIST2 joint-math
  tests/reference comparison PASS. The existing tests do not cover the above
  faults adequately. Strict XML parsing rejects the duplicate closing tag in
  vendor g1/scene.xml, but installed MuJoCo loads it; not an active runtime failure.
- Review-only: no production control/config edits, authorization changes, G1
  access or physical commands. Added local audit artifacts and this report.
- Before expanding physical trials, address release reporting, acquire-stop
  continuity, and final-command collision validation. Continue the remaining
  file review from the explicit static-only ledger; do not infer completion.

## Previous checkpoint: shared code documentation (2026-09-03)

- Resumed the interrupted documentation work. No control restructuring, source
  renaming, gain/limit changes, G1 access or physical commands were performed.
- `docs/CODE_GUIDE.md` now gives a reading order, library roles, three separate
  execution paths, a one-cycle walkthrough, modification impact map and parameter
  provenance rules. UDP 5005 position/rotation conversion stages are distinguished.
- README now matches the current unmodified rotation Jacobian and explicit Unity
  display modes; hardware mode does not substitute simulation for lost measured data.
  The existing Gate 7 physical path is documented separately from TWIST2 manual control.
- Short input/output comments were added in the active controller/planner/command
  stream/relay and Unity sender/receiver. Original TWIST2 C++ remains unchanged.
- `backend/tools/build_code_index.py` generates `docs/CODE_INDEX.md` without
  executing the indexed modules. `--check` detects a stale inventory. The index
  covers 264 scoped source/config files, NOT every repository asset. It distinguishes
  input/output review from file discovery; neither means every function was audited.
- Vendor assets, original references, models, recorded data and Unity serialized
  assets are explicitly outside this source index. Do not infer they are unused.
- Verification: backend 210 tests and hardware bridge 168 tests PASS. Index freshness,
  three generator tests, local document links and 15 unchanged config hashes PASS.
  Logs: `logs/cleanup/20260903/backend_docs_final.log` and `hardware_docs_final.log`.
  Unity compilation, Quest runtime and physical behavior were not retested.
- Remaining documentation work is detailed file/function review, not completed by
  generating the index. Use neutral technical wording without personal honorifics.
  The APF/NET discussion did not authorize replacing the active controller.

## Previous checkpoint: local cleanup and code explanation (2026-09-03)

- User requested removal of unused code plus concise comments and a separate
  explanation guide. `docs/CODE_GUIDE.md` now separates Unity/Mink simulation,
  Arm SDK Gate 7, and the minimal TWIST2 C++ derivative; it explains installed
  Mink 1.3.0 task cost/gain/Jacobian/QP, actual constants and PD provenance.
- Removed 20 unused source/test/BAT files, plus unused package exports and old
  config monkey-patch functions. Exact list/reasons: `docs/CLEANUP_20260903.md`.
  Old DLS camera/math consumers now use the active common model/transforms.
- The default launcher still runs virtual-center. The file named `prototype`
  remains a required shared module and explicit baseline, NOT discarded code.
  The experimental stateful controller is used by saved-capture replay and kept.
- `START_MUJOCO_ONLY.bat` no longer passes unsupported `--scene/--view`
  arguments to the current virtual-center parser; no controller behavior changed.
- Preserve all current runtime/diagnostic tests, hardware profiles, vendor
  assets, original references, minimal right-arm derivative, captures and the
  deferred Startup Recovery experiments. No G1 access or publisher was created.
- Only three short explanatory comments were added to active Mink source.
  No control arithmetic, gains, limits or hardware authorizations changed.
  C++ source/reference verifier still passes exact allowed derivative edits.
- Validation: final backend discovery 207 tests (including 3 new installed-Mink
  cost-math tests) PASS;
  hardware bridge 168 tests PASS; camera render/axes/transport PASS; all seven
  extracted TWIST2 right-arm math tests PASS. No Quest/Unity Play or physical
  retest was performed. Existing captured IK local-limit stall remains unresolved.
- Recovery archive and hash/reference evidence are local-only under
  `logs/cleanup/20260903/`; do not restore the whole dirty checkout from Git.
- Next control work remains right-arm sign/response verification followed by
  a socket input in the existing full-body C++ owner, with exact G1 approval.
  Historical entries below describe older intermediate states, not new defaults.

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
tracking loss. Workspace feedback and pinch handling now live in the active
sender; the unused optional authority and standalone pinch components were
removed.

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

Future research note from the supervising researcher (2026-08-27):

- Consider applying an artificial potential field after the current baseline is
  stable. The operator wrist/inspection target would provide an attractive
  term, while the torso, self-collision geometry, joint-limit or singularity
  neighborhoods, and later environment obstacles could provide repulsive terms.
- Do not replace Mink hard joint/collision constraints or the hardware Safety
  Gate with a potential field. First evaluate it in MuJoCo as target shaping or
  a secondary QP objective layered before/inside the existing constrained IK.
- Compare against the current Mink baseline using wrist tracking error, minimum
  clearance, joint velocity/acceleration/jerk, unnecessary proximal motion,
  oscillation, and recovery from local minima. Potential-field local minima and
  gain sensitivity must be treated as explicit failure modes before any live G1
  test.
- This is a later research item, not a change to the currently validated
  Startup Recovery or Quest teleoperation path.

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
- The cleanup initially retained 19 BAT entry points covering the current VR launcher
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
- All eight cleanup-era `tools/TEST_*.bat` entry points now print an absolute
  result path before pausing. Seven console-only tests persist their output
  under `logs/test_results/`; startup recovery retains its structured result at
  `logs/runtime/g1_startup_mink_recovery.json`. The startup recovery script also
  reports its four long-running calculation stages so it no longer appears hung.
- The six short non-Unity offline BAT tests and the Unity FK parity BAT test
  passed after this logging change.
  The two UDP E2E tests must run sequentially because both intentionally bind
  `127.0.0.1:5008`; their sequential runs pass. The long startup calculation was
  not rerun after this output-only BAT change; its Python calculation passed
  immediately before the progress-output patch.
- A follow-up orphan audit removed the missed legacy wrist-frame calibration
  bundle: `tools/CALIBRATE_WRIST_FRAME.bat`, its dedicated Python script, and
  `config/wrist_frame_calibration.json`. These belonged to the already-deleted
  `run_geometry_g1_teleop.py` path; no current runtime read the JSON or handled
  its freeze flag. All 19 tool BAT files remaining at that point were documented and their
  referenced scripts exist.
- The repository-wide follow-up audit checked tracked source, tool targets,
  documentation links, Unity GUID/meta pairs, duplicate classes/files, package
  dependencies, and ignored residue. It removed the unreferenced
  `MuJoCo_G1_Controller/unity` source copies, old Oculus smoothing scripts,
  the unused fake-hand CSV and compatibility launcher, duplicate Unity workspace
  and pinch components, unused Black/XRI settings assets, and stale
  `Zone.Identifier` residue. The current Meta XR runtime, G1 assets, camera
  regression receiver, tested backend modules, and read-only hardware tools were
  retained intentionally.
- Direct Unity dependencies on XR Interaction Toolkit and XR Hands were removed
  because no project source used them. XR Hands remains only as a transitive
  dependency of Meta XR SDK Core, which is required by the current Quest runtime.
- Korean responsibility and safety comments were added without changing control
  behavior across the active Unity G1 scripts, packet/protocol/state/transform
  backend, Mink model and virtual-center controllers, read-only LowState path,
  hardware safety gate, and offline startup recovery.
- Final post-comment validation passed: Python compileall, 145/145 backend tests,
  12/12 hardware bridge tests, Unity asset/meta and package JSON checks,
  `START_VR_HAND_TO_MUJOCO.bat --check`, `git diff --check`, and the Unity
  6000.5.4f1 batch validator. The Unity validation log is
  `logs/unity/final_cleanup_batch_validation.log`.
- On 2026-08-27, `G1HeadLockedCamera` was added to
  `G1_Teleoperation_System`. Its first live Quest test exposed a frame error:
  changing only `CenterEyeAnchor.position` left the tracked hand in room
  coordinates, so a whole-body side step became a false wrist command. The log
  showed Mink reaching the supplied target with essentially zero solver error
  while the Unity wrist delta itself changed by tens of centimeters.
- Translating the full `VR_XR_Rig` was rejected after the next live test. Meta XR
  anchor updates and the root correction accumulated: the logged wrist Y moved
  from about `-0.29 m` to `-1.67 m`, and Mink consequently reached extreme but
  mathematically valid joint-limit poses. That implementation was removed.
- The corrected mapping leaves the XR rig untouched. A first attempt mixed the
  `UnityEngine.XR` head position with Meta wrist transforms; the live log exposed
  a false `+1.056 m` vertical delta and a `2.104 m` target height. That mixed API
  path was removed. At engage the binder now stores `CenterEyeAnchor.position`
  and the wrist transform in the same Unity world frame, then commands only
  `(current wrist - current head) - (neutral wrist - neutral head)`. Rendering
  restores only `CenterEyeAnchor.position` after the binder has consumed the
  pose, while HMD rotation remains tracked. Invalid hand frames can no longer
  modify the tracking-jump neutral reference.
- The Unity regression validator simulates a 25 cm equal head-and-hand side step
  and requires zero robot hand delta. Unity compiled without errors and the
  in-editor teleoperation project validator passed before the mixed-frame bug
  was found. Unity compile/validator and live Quest verification must be repeated
  for the same-world-frame correction.
- The 2026-08-27 11:03 live Quest retest confirmed that the mixed-frame blow-up
  was removed. During 20.7 seconds of active control, the head-relative binder
  delta stayed within `X -0.34..0.18 m`, `Y -0.12..0.11 m`, and
  `Z 0.00..0.25 m`; the previous false `+1.056 m` vertical delta did not recur.
  No packet was rejected and no joint reached its configured limit. The minimum
  wrist-limit margin was `25.55 deg`.
- The same retest isolated the remaining tracking error to collision-constrained
  IK rather than joint limits. The operator target crossed as far as robot
  `Y=+0.18 m`, i.e. across the torso for the right arm. Collision proximity was
  reported for 535 of 745 active samples, including continuous intervals of
  `5.18 s` and `4.12 s`. At the final low/inboard target the nearest pair was
  `torso_link` versus `right_elbow_link`, clearance reached `0 mm`, and wrist
  position error grew to about `10.5 cm`. The next controller change should
  address collision-boundary target handling and recovery from the constrained
  branch; the official joint-limit table should not be loosened for this symptom.
- A subsequent head-yaw-only test showed that the head camera position itself
  remained fixed near `(0.007, 1.070, -0.003) m`, but the Meta right-hand pose
  drifted by more than `10 cm` and its quaternion changed rapidly immediately
  before `IsTracked` became false. The binder previously accepted those
  low-confidence transition frames. Hand input now requires both
  `OVRHand.IsTracked` and `OVRHand.IsDataHighConfidence`; low-confidence frames
  hold the last valid target without disengaging the clutch. Tracking-origin
  neutral correction uses the same confidence gate.
- The first retest with that confidence gate confirmed that the fully invalid
  pose is held, but Meta still reported `IsDataHighConfidence=true` for roughly
  `0.4 s` while the head-relative wrist drifted about `35 cm` before loss. The
  binder now also rejects implausible head-relative wrist steps above `1.10 m/s`,
  latches the last accepted target, and recovers only after five frames return
  within `8 cm` of the last accepted pose. This adds an independent plausibility
  gate without changing clutch or workspace-exit semantics.
- A far head-turn retest then caused genuine Quest hand-tracking loss. The pose
  gate rejected the `5.20 m/s` wrist jump and the backend correctly entered
  HOLD, but the older tracking-origin-jump correction had already moved the
  neutral wrist reference by more than a metre. That obsolete neutral mutation
  was removed; discontinuities are now handled only by holding the last accepted
  head-relative wrist target. Requiring the hand to return within `8 cm` proved
  too strict and could leave an engaged clutch permanently in HOLD. Automatic
  rebasing at a newly observed hand pose was rejected because it silently changes
  the hand-to-robot mapping. The final policy is: brief loss holds the last target,
  but `0.35 s` of continuous invalid tracking emits `tracking_disengaged`, clears
  both Unity calibration and the backend clutch, and requires the normal
  wrist-alignment/hold procedure before a new engagement.
- Gate 5 read-only hardware preparation was added on 2026-08-27. The WSL
  `read_only_lowstate.py` forwarder now emits the strict
  `g1.lowstate.right_arm.v1` UDP 5007 packet with bridge session ID, increasing
  DDS receive sequence, source timestamp, measured right-arm `q/dq`, and explicit
  no-publisher/no-output flags. Existing initial-pose receivers remain compatible
  because the original joint fields are unchanged.
- `hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py` receives that packet
  on Windows and evaluates `measured_q == requested_q` through the existing
  `safety_gate.evaluate_target`. An allowed vector is diagnostic only and is
  written to status; it is never forwarded. The process imports no Unitree SDK,
  creates no DDS publisher, and has no `LowCmd` path.
- The Gate 5 monitor latches the bridge session and increasing sequence. Invalid
  schema/data, session replacement, sequence rollback, joint-limit denial, or a
  LowState age over 250 ms creates a fail-closed `FAULT`; denied status always
  records `candidate_q_rad=null`. Runtime status and append-only events are
  `logs/runtime/g1_gate5_lowstate_safety.json` and `.jsonl`.
- `tools/START_G1_GATE5_READ_ONLY.bat` runs the real read-only forwarder and Gate
  5 monitor. `tools/TEST_G1_GATE5_READ_ONLY.bat` uses synthetic UDP telemetry and
  records `logs/test_results/g1_gate5_read_only.log`. The six new focused tests
  passed, including a process-level fresh-HOLD then stale-timeout run. This raises
  the current tool count to 21 BAT entry points and the hardware bridge test count
  to 18. Actual physical-G1 Gate 5 validation remains pending and command authority
  remains `NONE`.
- The 2026-08-27 Quest trace after tracking-loss disengagement showed why the
  green Mink target could remain far from the robot wrist: workspace limiting
  was never active, while collision limiting was active for 80.2% of the 1,268
  command frames and position error reached 23.8 cm. Reconstructing the maximum
  error pose showed that the only geometry inside the 40 mm detection band was
  local three-hop structure (`right_elbow_link` versus `right_wrist_yaw_link`,
  and at nearby poses `torso_link` versus `right_shoulder_yaw_link`). These are
  normal parts of the connected arm assembly, not independent self-collision
  obstacles. `STRUCTURAL_NEIGHBOR_DISTANCE` was therefore corrected from 2 to
  3. Independent protection such as `torso_link` versus `right_elbow_link`,
  opposite-arm, pelvis, and lower-body collision pairs remains enabled and is
  covered by a regression test.
- The first live retest after excluding local three-hop collision pairs reduced
  mean wrist error from 8.9 cm to 5.1 cm and collision-limited frames from 80.2%
  to 36.9%; minimum wrist-limit margin remained 37.9 degrees. Continuous camera
  position locking was then removed because fixing the rendered eye position
  while the operator physically translates causes severe visual-vestibular
  mismatch. The camera now aligns to the G1 head mount once at startup and then
  follows normal Quest position and rotation. Whole-body translation still does
  not enter the arm command because the binder uses wrist motion relative to the
  tracked head in the same Unity world frame.
- The next live test exposed a control-frame flaw in that last sentence: always
  subtracting head translation also turns head-only motion into an equal and
  opposite arm command. The binder now estimates body translation incrementally
  and subtracts it only when wrist and head steps have matching direction,
  comparable magnitude, and small residual. Head-only motion and wrist-only
  motion are not classified as body translation. Wrist pose plausibility is also
  evaluated in wrist world coordinates, so ordinary head motion cannot trip the
  wrist outlier latch.
- A head-only retest still produced up to 26 cm of Quest wrist drift while the
  head translated only 1.5 cm. This was not body-translation leakage: the hand
  provider gradually re-estimated the wrist while the headset rotated. The
  first mitigation froze wrist position and orientation above 8 deg/s of head
  angular speed. The 12:48 live trace proved that this was too aggressive:
  85 of 159 calibrated samples (53%) were held, and valid commands fragmented
  into four short intervals even though Mink received packets without rejection.
  This was an input-gating regression, not an IK solver failure. The angular-speed
  hold and its resume/outlier latch were removed. Head angular speed remains a
  diagnostic-only trace field and cannot invalidate tracking or block commands.
  The established 0.35 s confirmed tracking-loss disengagement and wrist-speed
  outlier gate remain unchanged. A Quest live retest is required; any remaining
  head-turn wrist drift must be corrected at the tracking/frame source without
  gating the entire IK stream.
- The next live test exposed an actual upper-arm/torso penetration. Replaying the
  final logged joint pose measured `torso_link` to `right_shoulder_yaw_link` at
  `-4.35 mm`, but the pair was absent from the Mink QP because the global
  structural-neighbor exclusion had been widened from two to three kinematic
  hops. The global exclusion is restored to two hops. Only the previously
  measured false-positive pair `right_elbow_link` to `right_wrist_yaw_link` is
  explicitly exempted. The torso/upper-arm and torso/elbow pairs are again in
  the collision constraint set; generated Mink collision pairs increased from
  234 to 243. All 150 backend tests pass. Live Quest/MuJoCo confirmation remains
  required before treating the visual collision regression as closed.
- The live Quest retest after restoring torso/upper-arm collision protection ran
  for 31.47 s as one uninterrupted active-command segment (1,132 samples).
  Pose plausibility was 100%, no head-motion hold or workspace-limit frame was
  produced, and all UDP packets were accepted. The user reported that head-only,
  hand-only, and whole-body motions were all approximately correct. Collision
  limiting was active for 70.2% of command samples, with mean wrist tracking
  error 4.67 cm and maximum 13.95 cm; this is now treated as the conservative
  simulation baseline rather than immediately loosening the restored torso
  protection.
- The 2026-09-02 LowState Gate 7 dry-run initially appeared to disconnect even
  though Quest and LowState transport ages stayed below 16 ms. Event analysis
  showed repeated `TRACK_MINK_RIGHT <-> SAFETY_HOLD` transitions caused by
  legitimate torso/right-upper-arm collision samples, not network loss. The
  live Mink QP and the downstream Gate 7 hard stop had both used the same 12 mm
  threshold, leaving no numerical or discrete-time margin. The live virtual-
  center controller now targets 20 mm while Gate 7 remains fail-closed at
  12 mm. Startup Recovery constants and hardware authorization are unchanged.
  Gate 7 event logs now include Mink clearance and nearest collision geom/body
  names for the next live confirmation.
- The first 20 mm live retest reduced active collision holds from 70 to 22;
  all Quest and LowState transport ages remained below 32 ms. The remaining
  three long disengagements were explicit Unity input transitions through
  `idle` to `tracking_disengaged`, not Gate 7 packet loss. The final intentional
  pinch coincided with a collision flag and was incorrectly consumed by the
  collision HOLD before Regular return could start. Pinch now requests the
  independently collision-validated Regular-return path before current-pose
  collision HOLD evaluation; an unsafe return remains rejected by the existing
  path validator.
- The next 105.9-second retest confirmed both intentional pinch returns reached
  `REGULAR_HOLD`, but exposed 157 one-frame collision holds. Logged clearance
  repeatedly jumped from 20-77 mm to exactly 0 and back in 31-94 ms across
  unrelated mesh pairs, despite bounded joint motion and healthy transport.
  This matches the repository's existing MuJoCo isolated-zero regression: a
  mesh pair can report exactly zero without an actual `data.contact`, while
  `1e-7 rad` adjacent probes remain centimetres apart. Runtime nearest-distance
  reporting now uses that established robust check. Exact contacts and zeros
  that cannot be resolved by probes remain fail-closed at zero; Mink's QP
  collision constraint set is unchanged.
- The 58.7-second confirmation run produced no exact-zero clearance samples.
  Intentional pinch completed `REGULAR_RETURN -> REGULAR_HOLD`, Quest and
  LowState transport stayed below 32 ms, and 581 active samples tracked
  normally. The only remaining active collision interval was continuous and
  physically plausible: `torso_link <-> right_wrist_yaw_link` decreased below
  the 12 mm hard line at 10.88 mm and reached 0.53 mm. Gate 7 correctly held
  instead of following the hand through the torso. The isolated-zero runtime
  correction is therefore confirmed; this final hold is intended safety
  behavior, not a transport or collision-distance regression.
- The offline Startup Recovery was rerun after the collision-policy correction
  and passed again: 21.798 simulated seconds, 10,899 steps, initial-contact
  escape complete, ready pose reached within 0.302 degrees, and no command
  output. `hardware/g1_arm_bridge/replay_startup_recovery.py` and
  `tools/VIEW_G1_STARTUP_RECOVERY.bat` now replay that validated result in a
  MuJoCo-only viewer. The viewer holds the measured rest pose for 3 seconds,
  plays the 21.8-second trajectory at 0.5x, and holds the final TELEOP_READY
  pose. It imports no Unitree SDK and opens no DDS, UDP, or robot command path.
- Startup Recovery's ready posture is no longer hard-coded. The seven named
  right-arm values and viewer-only playback settings are in
  `config/startup_recovery.json`. The loader rejects missing/unknown joints,
  non-finite values, and poses outside the existing Safety Gate range before
  planning. The viewer default was changed from 0.5x to 1.0x with a 2-second
  initial hold. Changing the ready pose requires rerunning the offline recovery;
  changing only viewer speed does not alter the validated trajectory or any
  future hardware motion limit.
- `hardware/g1_arm_bridge/edit_startup_ready_pose.py` and
  `tools/EDIT_G1_STARTUP_READY_POSE.bat` provide an offline MuJoCo keyboard
  editor for that named seven-joint pose. Number keys select a joint, arrows or
  `A/D` adjust it, `,/.` changes the step, and `S` saves only after the existing
  Safety Gate ranges and Mink's 12 mm static collision clearance pass. The previous
  config is copied to `logs/runtime/startup_ready_pose_previous.json`. This
  static save is not a validated transition and must be followed by
  `TEST_G1_STARTUP_RECOVERY_OFFLINE.bat` and visual replay. No Unitree SDK,
  DDS, UDP, network socket, publisher, or robot command is opened by the editor.
  A live Viewer smoke test selected joint 2, changed shoulder roll from -30 to
  -29 degrees, printed a valid static result, restored -30 degrees, and closed
  normally without saving. The editor save/backup unit tests and the full 152
  backend tests also pass.
- The first recovery run after the user saved
  `[0, -7, 2, 57, 0, 0, 0]` degrees exposed a policy error: the 40 mm initial
  escape distance had been used as the QP minimum for the entire transition.
  That target is statically clear by 20.4 mm and therefore satisfies Mink's
  actual 12 mm hard minimum, but the old QP stopped shoulder roll near -20.16
  degrees. Startup Recovery now uses 40 mm only while escaping the initial
  contact and switches to 12 mm after `escape_complete`. The unchanged user
  pose then passed in 21.724 seconds with 0.302 degree final error, 20.339 mm
  final clearance, and complete swept-path validation. No DDS or command output
  was enabled.
- The failed run also reproduced a MuJoCo mesh-mesh distance degeneracy: at two
  isolated sub-microdegree samples, `mj_geomDistance` returned exactly 0 mm for
  torso-to-right-shoulder-yaw although `data.ncon` was zero and symmetric
  `1e-7` rad probes returned about 39.996 mm. Read-only collision diagnostics
  now re-probe only an exact-zero/no-contact result in both directions and keep
  the minimum nonzero value. Real contacts, negative distances, unresolved
  zeros, and any result below the active safety margin remain blocked. A
  regression test preserves this exact failure posture.

### 2026-08-27 lower-body integration checkpoint

- The current project has **no G1 command authority**. It subscribes to official
  Unitree SDK2/CycloneDDS `rt/lowstate` on DDS domain 0 and observes right-arm
  joints 22-28. It contains no `rt/lowcmd`, `ChannelPublisher`, or `LowCmd`
  publisher. Gate 5 also sends no robot command.
- The previously verified host-side network used `192.168.123.99/24` without
  changing the G1 network configuration. The WSL interface name is detected
  from that address and must not be assumed to remain `eth3` after reboot.
- `tools/START_G1_READ_ONLY.bat` is the first physical connection check.
  `tools/START_G1_GATE5_READ_ONLY.bat` is the next read-only check through the
  Safety Gate. The offline Startup Recovery remains `hardware_ready=false` and
  must not be applied to the physical G1.
- The intended operating sequence is locomotion active -> locomotion stopping
  -> confirmed stopped -> upper-body teleoperation -> upper-body disarmed/HOLD
  -> locomotion may resume. A single authority or command arbiter must own each
  joint and mode; independent processes must not write overlapping commands.
- Before command integration, obtain the lower-body controller's current
  executable/repository and commit, run location, SDK/API, DDS domain and exact
  topics/services, control frequency, owned joints, waist 12-14 ownership, arm
  behavior during locomotion, confirmed-stop signal, transition protocol,
  watchdog, emergency stop, and disconnect recovery behavior. Also inventory
  all files, services, startup scripts, and network settings installed on the
  G1 computer; do not overwrite or reconfigure them.
- Historical lower-body notes describe an experimental `rt/lowcmd` pipeline
  with 12 policy-controlled leg joints, 17 PD-held waist/arm joints, 50 Hz
  policy output, and about 500 Hz LowCmd output. The current lower-body owner
  has stated that the present controller is not low-level, so those notes are
  context only and must not be treated as the current interface.
- The minimum joint/mode contract to write down together is: `LOCOMOTION`,
  `STOPPING`, `UPPER_TELEOP`, and `FAULT`; for each mode record lower-body,
  waist, and arm ownership plus the exact transition condition. Required
  handshake meanings include lower-body stopped, upper-body ready, teleop
  active/done, watchdog fault, and emergency stop.
- Startup Recovery was shortened on 2026-08-27 without relaxing its 12 mm hard
  collision minimum. The Cartesian contact-release task and ready-posture task
  now run concurrently from the first QP step. Initial contact pairs become
  strictly unable to re-enter after clearing 12 mm; the escape task remains only
  as a routing assist until those same pairs clear 20 mm, then disappears with
  no intermediate stop. The phase sequence is now
  `CONTACT_RELEASE_AND_RECOVERY -> CLEARANCE_ASSIST_AND_RECOVERY ->
  TRANSITION_TO_READY -> TERMINAL_READY_BLEND`.
- The current captured-pose dry-run cleared 12 mm at 0.30 s, removed the escape
  assist at 0.48 s, and reached the saved `[0, -7, 2, 57, 0, 0, 0]` degree pose
  in 3.828 s instead of 21.724 s. The 1,915-sample path passed the 0.001-degree
  swept-path replay, motion limits, Safety Gate, and stale-LowState denial, with
  zero final error and 20.417 mm final model clearance. The 12 mm and
  15 mm immediate-assist-release variants were rejected by swept-path collision
  validation, so 20 mm is retained as a soft routing-assist release value only.
  This remains `hardware_ready=false`; no DDS publisher or command output was
  added.
- The earlier 12.140 s version entered `READY_BRAKE_HOLD` at about 2 degrees,
  stopped completely, restarted at 0.5 deg/s, and stopped a second time. Its
  jerk-limited velocity tracker repeatedly crossed zero during those holds,
  producing the visible stop/restart and joint-direction zigzag. It is replaced
  by a boundary-matched quintic terminal trajectory: at 5 degrees remaining it
  preserves the current discrete q/v/a and reaches the exact ready q with final
  velocity and acceleration equal to zero. Candidate duration is accepted only
  after joint-limit, velocity, acceleration, jerk, and collision replay checks.
  The selected terminal blend starts at 2.70 s and lasts 1.152 s. A later
  8-degree entry was tested and rejected because no candidate satisfied all
  limits, so the validated 5-degree entry remains active.
- Live virtual-center teleoperation now separates joint velocity limits instead
  of accelerating the entire arm: shoulder/elbow joints remain capped at
  40 deg/s, while wrist roll/pitch/yaw are capped at 100 deg/s. These are
  project-specific tested limits, not values copied from Mink's G1 example. The split is
  applied by `virtual_center_velocity_limits()` and is covered by policy and
  mixed-pose trajectory tests. This affects MuJoCo/Mink only; no physical G1
  command path was enabled.
- All current root and `tools/` batch launchers now pair every `[FAIL]`,
  `[ERROR]`, `[BLOCKED]`, or `[FAULT]` message with a nearby `[ACTION]` that
  states the next concrete recovery step. Test launchers also append that action
  to their saved result log. `backend/tests/test_batch_failure_guidance.py`
  enforces this convention for future batch-file changes.

### 2026-08-28 live G1-to-MuJoCo read-only mirror

- `tools/VIEW_G1_LIVE_MUJOCO.bat` was added as a separate live observation
  path. It starts the existing official SDK2/CycloneDDS `rt/lowstate`
  subscriber in WSL, forwards all 29 joint positions and velocities at 30 Hz
  over UDP 5009, and continuously applies those measured joint positions to the
  MuJoCo G1 model. It is not the one-shot initial-pose sync controller.
- The first valid packet is applied exactly. Later 30 Hz samples use a 35 ms
  first-order display interpolation that cannot overshoot. If no valid packet
  arrives for 250 ms, the viewer freezes at the last measured pose; it does not
  extrapolate or fabricate motion. A restarted bridge session is accepted, but
  non-increasing packets within one session are rejected.
- This path imports no Unitree command type, creates no DDS publisher, and
  sends no robot command. Closing the viewer stops the dedicated UDP 5009 WSL
  forwarder. Legs, waist, and both arms are mirrored. The MuJoCo base remains
  fixed because the 29 motor positions do not encode global base pose.
- The existing firewall helper now permits only the two read-only LowState
  telemetry ports, UDP 5007 and 5009, from `LocalSubnet`. Run it once again if
  a machine still has the older 5007-only rule.
- Static/model validation, eight live-viewer unit tests, batch guidance tests,
  and all 155 backend regression tests pass. Actual continuous motion with a
  physically connected G1 has not yet been verified and remains the next
  hardware check.

### 2026-08-28 Startup Recovery initial-posture sweep

- A separate offline experiment now exists under
  `experiments/startup_recovery_posture_sweep/`. It leaves the active Startup
  Recovery unchanged, generates deterministic synthetic initial right-arm
  poses, invokes the current recovery in isolated subprocesses, and records a
  JSON summary, CSV table, per-case full result/log, and an HTML success map.
- The map uses shoulder roll versus elbow as its two axes and supports multiple
  shoulder-pitch slices. Shoulder yaw and all wrist joints retain the captured
  base values. Every sample retains the current QP, joint-limit, collision,
  velocity, acceleration, jerk, Safety Gate, and 0.001-degree swept-path
  validation. It has no Unitree SDK, DDS, network, or command path.
- The first quick map used the captured `[6.44, -2.84, -18.27, 75.01, -15.76,
  -6.78, -1.60]` degree pose and sampled roll/elbow offsets of `-15, 0, +15`
  degrees at the base shoulder pitch. Three of nine exact poses passed. Five
  were rejected by swept-path collision validation, and the inward-roll/base-
  elbow sample ran the full 30 simulated seconds before failing with
  `terminal_blend_entry_not_reached`. No case remained unresolved.
- The passing samples were `(roll offset, elbow offset) = (-15, -15),
  (-15, 0), (0, 0)` degrees. This is a sparse sampled map, not proof that the
  unsampled region between green cells is safe. A denser three-pitch-slice
  command is documented in the experiment README and should be run before
  claiming a broader recovery envelope.
- The current map is at
  `logs/experiments/startup_recovery_posture_sweep/latest_map.html`; its summary
  reports 9 evaluated, 3 passed, 6 failed, and 0 infrastructure errors. The
  runner supports resuming only `ERROR` cells with a longer wall-clock timeout.
- The standard three-slice sweep has now also completed. It evaluated 75 poses:
  shoulder-pitch offsets `[-15, 0, +15]` degrees crossed with shoulder-roll and
  elbow offsets `[-30, -15, 0, +15, +30]` degrees. The final result is 29 pass,
  46 fail, and zero unresolved/infrastructure errors. Pass counts by pitch
  slice were 13, 10, and 6 respectively.
- Of the 46 standard-sweep failures, 41 were rejected by the 0.001-degree
  swept-path collision validation, four ran the full 30 simulated seconds but
  never reached the terminal-blend entry, and one could not construct a
  limit-compliant terminal ready blend. Passing recovery times ranged from
  3.828 to 8.036 seconds and their minimum post-release clearance was at least
  12.000 mm. These are model/sample results, not a physical hardware envelope.
- `latest_map.html`, `latest_summary.json`, and `latest_results.csv` now point
  to the completed 75-pose standard run `standard_20260828_initial`. The earlier
  9-pose quick run remains under its timestamped run directory for provenance.
- The next planned experiment is intentionally **deferred**. When resumed, use
  the 75-pose baseline results as input, run the existing alternate escape
  strategies only for the 46 failed cells, stop each cell at its first fully
  validated success, and generate a strategy atlas that records which recovery
  strategy succeeds. Do not start this experiment until the user explicitly
  resumes it. A later 7.5-degree boundary refinement can follow the atlas.
- The physical G1 read-only connection was verified on 2026-08-28 after the
  robot finished booting. Windows reported the ASIX USB Ethernet adapter
  (`이더넷 4`) as `Up` at 100 Mbps with `192.168.123.99/24`, and WSL exposed it
  as `eth3`. Both observed G1-side addresses `.161` and `.164` replied.
  `rt/lowstate` then delivered more than 11,000 packets during the bounded
  check with sub-millisecond packet age for most samples. The measured right
  arm was approximately `[7.25, 0.42, -31.61, 74.40, -22.56, 12.76, -7.23]`
  degrees. No DDS publisher or robot command was created.
- `VIEW_G1_LIVE_MUJOCO.bat` was subsequently launched and both its WSL UDP 5009
  forwarder and Windows MuJoCo viewer processes were confirmed running. Visual
  agreement between the physical arm and MuJoCo was then confirmed by the
  operator, completing the first physical live-mirror check.
- The inspection panel, panel marker, and right-hand inspection stick remain in
  the generated MuJoCo model but are hidden by default only in the read-only
  live mirror. Pass `--show-inspection-scene` directly to
  `live_lowstate_mujoco.py` to display them again. The regular teleoperation
  model and its collision/safety behavior were not changed.
- The operator observed that the firmware's default 3-DoF-waist Regular Mode
  posture already keeps the hands visibly separated from the pelvis. Startup
  Recovery should therefore become a conditional fallback rather than an
  unconditional launch step: after a fresh measured-pose sync, bypass recovery
  when the mode is appropriate, joint velocity is low, all joint limits pass,
  and the modeled arm has no penetration and satisfies the configured hard
  collision clearance; otherwise retain the existing validated recovery path.
  Do not delete Startup Recovery because damping, abnormal, or fault-return
  poses can still require it.
- The cable-connected Regular Mode pose was subsequently captured as
  `[16.67, -12.61, 0.95, 56.47, -10.17, 1.60, 0.83]` degrees. Read-only
  Mink/Unity pose synchronization passed with a maximum error of
  `1.735e-18 rad`. The active collision model found no pair inside the 12 mm
  hard minimum; the nearest configured pair was `torso_link <->
  right_shoulder_yaw_link` at 27.52 mm. The direct segment from this measured
  pose toward the configured ready pose introduced no new inside-minimum body
  pair. This confirms that the captured Regular Mode pose qualifies for the
  collision portion of a recovery-bypass precheck.
- The conditional recovery-bypass precheck is now implemented as
  `tools/CHECK_G1_TELEOP_STARTUP.bat`. It performs a separate read-only
  `MotionSwitcherClient.CheckMode()` query, then observes one second of the
  existing read-only `rt/lowstate` stream and checks packet freshness/order,
  Gate 5 joint limits, right-arm pose span, right-arm velocity p95, and the
  active Mink collision model using all 29 measured joint positions. It never
  calls `SelectMode()` or `ReleaseMode()`, creates no motor-command publisher,
  and sends no robot command.
- `mode_machine=5` must not be described as the Regular/Damping selector. The
  official examples use it as the G1 machine/configuration value. While the
  operator explicitly confirmed the current 3-DoF-waist Regular Mode, the
  read-only MotionSwitcher query returned `form="0", name="ai"`; that exact
  firmware-specific signature is pinned in `config/g1_startup_precheck.json`.
  A different robot/firmware signature blocks startup until a human verifies
  and updates it rather than being learned automatically.
- The latest full hardware BAT run returned `DIRECT_TELEOP_READY`: 25 forwarded
  packets, maximum right-arm pose span `0.0021 deg`, maximum per-joint velocity
  p95 `1.230 deg/s`, no Gate 5 rejection, and minimum modeled dual-arm collision
  clearance `27.76 mm` for `torso_link <-> left_shoulder_yaw_link`, above the
  configured `12 mm` hard minimum. The hardware precheck now evaluates 406
  collision pairs involving either arm rather than only the right-arm pair set.
  This permits bypassing Startup Recovery for that measured startup state only;
  it does not authorize a command or delete the Recovery fallback. Results are stored in
  `logs/runtime/g1_startup_precheck.json` and
  `logs/runtime/g1_motion_mode_query.json`.
- Verification after the implementation passed 32 hardware-bridge tests, 155
  backend tests, and 8 startup-recovery experiment tests. The new BAT was also
  run end to end against the connected G1 and produced the same
  `DIRECT_TELEOP_READY` decision without a robot command.

### 2026-08-28 Gate 6 measured-pose Arm SDK HOLD boundary

- Gate 6 is now implemented as a separate command boundary, but physical output
  remains deliberately locked. `config/g1_gate6_hold.json` has
  `hardware_output_authorized=false`; no `rt/arm_sdk` publisher has been
  activated and no physical G1 motor command has been sent.
- The implementation follows the official Regular-Mode coexistence path:
  subscribe to `rt/lowstate`, publish only to `rt/arm_sdk`, store the blend
  weight in `motor_cmd[29].q`, and never use `rt/lowcmd`. Because this weight
  applies to the dual-arm command, Gate 6 seeds and validates both arms 15-28
  from the same fresh measured snapshot even though current teleoperation scope
  is the right arm.
- Waist 12-14 and all lower-body joints are excluded from the dynamic command
  set. Their command mode and gains remain zero in the Gate 6 frame. This does
  not resolve the final upper/lower-body ownership handshake; the lower-body
  owner must still confirm there is no overlapping arm/waist writer before a
  physical publisher is enabled.
- `arm_sdk_hold_contract.py` validates fresh LowState, both physical arm joint
  ranges, maximum measured-target error, the 35-slot HG LowCmd layout, and the
  acquire/HOLD/release weight schedule. `gate6_arm_sdk_hold.py` defaults to a
  read-only preparation path and imports/creates `ChannelPublisher` only inside
  the explicitly authorized hardware-output branch.
- The first physical candidate is deliberately limited to maximum blend weight
  0.2 with a 3 s ramp-up, 3 s HOLD, and 3 s ramp-down followed by 25 zero-weight
  frames. Proximal gains are 80/3 and wrist gains are 40/1.5, matching the
  current official xr_teleoperate controller defaults. These values have not
  yet been physically approved in this project.
- `tools/TEST_G1_GATE6_HOLD_OFFLINE.bat` passed. It includes 12 Gate 6 unit
  tests plus a WSL check against the installed Unitree SDK2 commit
  `65691c8a8bc53b98d3976dba4dbf9d5d20b2e7f5`; the actual SDK accepted the
  35-slot message, weight index, disabled waist slots, and generated CRC without
  creating ChannelFactory or a publisher.
- The complete hardware-bridge suite now passes 45 tests. A forced hardware-
  output invocation while locked returned `OUTPUT_NOT_AUTHORIZED` with
  `publisher_present=false` and `published_frames=0`.
- `tools/PREPARE_G1_GATE6_HOLD.bat` was run against the connected suspended G1
  in confirmed Regular Mode. It returned `HOLD_READY` on `eth3`, observed 840
  settle samples, measured a 2.72 deg/s maximum instantaneous dual-arm velocity,
  and accepted the exact measured dual-arm HOLD target. It created no publisher
  and sent no command. Results are in
  `logs/runtime/g1_gate6_arm_sdk_hold.json` and
  `logs/test_results/g1_gate6_hold_prepare.log`.
- Before the first physical HOLD, rerun Gates 0-5 and a less-than-60-second-old
  `DIRECT_TELEOP_READY` precheck, confirm the test area/stop operator and command
  ownership, review the 0.2 weight and gains, then obtain explicit user approval
  before changing `hardware_output_authorized`. The first physical test must be
  HOLD only; live Mink targets remain prohibited until acquire/release and
  interruption behavior are observed and documented.
- Operational correction: Regular Mode is the ground-standing state in which
  the G1 lower-body motion service actively balances the robot. The earlier
  suspended read-only `HOLD_READY` run remains valid only as DDS reception,
  measured-pose, and no-publisher evidence; it does not authorize physical
  output. The first command-capable Gate 6 HOLD must be performed with both feet
  on a level floor, no suspension carrying robot weight, a clear test area, and
  an operator ready to stop the robot. The hardware-output path now requires a
  second exact `G1_IS_GROUNDED_IN_REGULAR_MODE` confirmation in addition to the
  existing command-authorization phrase. Hardware output remains locked.
- After this correction, the connected G1 was checked again without output.
  `CHECK_G1_TELEOP_STARTUP.bat` returned `DIRECT_TELEOP_READY` with 25 packets,
  0.0027 degree right-arm span, 1.143 deg/s velocity p95, and 27.76 mm minimum
  dual-arm collision clearance. `PREPARE_G1_GATE6_HOLD.bat` then returned
  `HOLD_READY` with 833 settle samples and 2.55 deg/s maximum instantaneous
  dual-arm velocity. Both runs reported no DDS publisher and no robot command.
  Software cannot verify floor contact, loading of a support strap, area
  clearance, stop-operator readiness, or external command writers, so explicit
  current operator confirmation remains mandatory before any physical HOLD.
- The first physical Gate 6 measured-pose HOLD was explicitly approved and run
  with the operator reporting grounded Regular Mode, a clear area, `L2+B`
  readiness, and no other arm/waist writer. A fresh startup check initially
  exposed a diagnostic defect: isolated zero mesh distances for a left-arm pair
  were probed using right-arm joints only. `diagnose_initial_pose_collision.py`
  now probes both arm chains, and a focused regression test covers the left-arm
  case. The corrected check measured 27.13 mm clearance.
- A later fresh precheck passed with 25 packets, 0.1263 degree right-arm span,
  and 2.197 deg/s velocity p95. Gate 6 then published the measured dual-arm pose
  to `rt/arm_sdk` with a bounded `0 -> 0.2 -> 0` weight schedule. The run
  completed normally with 2275 frames; final status was `HOLD_READY`, weight
  zero, publisher absent, and no fault. The one-time authorized config was
  deleted and permanent `hardware_output_authorized=false` was confirmed.
- The operator subsequently confirmed there was no visible abnormality during
  the completed physical HOLD. Abnormal-sound confirmation and an intentional
  interruption test remain pending. Do not connect live Mink targets until both
  are documented.

### 2026-09-02 Gate 6 interruption and control-return test prepared

- A dedicated Gate 6 interruption test was added without changing the normal
  Gate 6 HOLD or Gate 7 runtime configurations. It reuses the verified
  measured-pose Arm SDK HOLD implementation with a separate 300-second HOLD so
  the operator can request Ctrl+C after weight reaches 0.2.
- Ctrl+C follows the existing graceful stop path: Arm SDK weight ramps from
  0.2 to zero over 2 seconds, then 25 zero-weight frames are transmitted before
  the publisher exits. The dual-arm target remains the fresh measured startup
  pose; waist and lower-body command modes and gains remain disabled.
- `tools/TEST_G1_GATE6_INTERRUPT_RELEASE_OFFLINE.bat` deterministically validates
  the complete release profile without importing Unitree SDK2, creating a DDS
  entity or publisher, or sending a robot command. Results are written below
  `logs/test_results` and the console prints the exact result path.
- The future physical launcher is
  `tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat`. Its independent config
  `config/g1_gate6_interrupt_release_test.json` remains fail-closed with
  `hardware_output_authorized=false`. It must not be unlocked or run until the
  user separately approves that exact grounded Regular-Mode physical test.
- The physical acceptance criteria remain pending: natural return of Regular
  controller authority after Ctrl+C, no arm jump, no abnormal sound, and no
  balance disturbance. Live Gate 7 output remains locked until this is observed.
- The dedicated physical interruption test was subsequently explicitly approved
  and run on `eth3`. The first launch stopped before any publisher because the
  offline checker incorrectly required its config to remain locked after the
  one-time authorization; the checker was corrected to validate the release
  contract independently of authorization state. That failed attempt sent no
  robot command.
- The second launch acquired Arm SDK authority from zero to weight 0.2, held the
  exact measured dual-arm startup pose, then received Ctrl+C and decreased
  weight continuously to zero over approximately 2 seconds. It completed after
  1,883 frames with `phase=HOLD_READY`, `schedule_phase=COMPLETE`,
  `publisher_present=false`, and no fault. Waist targets remained disabled.
  Runtime evidence is in
  `logs/runtime/g1_gate6_interrupt_release_test.json` and `.jsonl`.
- The one-time config was immediately restored to
  `hardware_output_authorized=false`, and no Gate 6, Gate 7, or Jog command
  process remained. Operator confirmation of no arm jump, abnormal sound, or
  balance disturbance is still required before closing the physical acceptance
  item and considering live Gate 7 authorization.
- The operator confirmed the expected measured-pose behavior: the arms did not
  move, there was no abnormal sound, and there was no balance disturbance.
  Gate 6 acquire/interruption/release acceptance is therefore complete. This
  does not prove useful target tracking; the next physical prerequisite is the
  previously prepared weight-1.0 shoulder-pitch authority trial with the revised
  1.5-degree 14-axis arming tolerance.
- Old one-time authorizations were also found still enabled in
  `g1_right_arm_jog.json` and
  `g1_right_shoulder_pitch_full_authority_trial.json`. No related process was
  running, and both configs were restored to
  `hardware_output_authorized=false`. The full Gate 7 config remains locked.

### 2026-08-28 full-body state observation decision

- Command ownership and state observation are now explicit and separate. The
  project may command only its approved arm joints, but it subscribes to and
  preserves all 29 G1 motor positions and velocities for operator UX,
  collision context, logging, and simulation display. This does not grant waist
  or lower-body command ownership.
- The existing SDK2/CycloneDDS `rt/lowstate` bridge was already extracting all
  29 `q` and `dq` values while retaining the legacy right-arm fields. The live
  MuJoCo viewer now validates the exact 29-name motor order and mirrors legs,
  waist, and both arms instead of discarding every joint outside indices 22-28.
  Missing, non-finite, duplicate, or reordered full-body data is rejected.
- Mink feedback on UDP 5006 now carries optional `all_joint_names` and
  `all_joint_q_rad` fields in addition to the unchanged `right_arm` object.
  Unity validates the canonical 29-name order and applies it to the official G1
  rig; legacy right-arm-only packets still work. These new fields are display
  state only and do not alter the right-arm-only IK/frozen-DOF policy.
- All 29 motor angles reconstruct articulation, not world motion. Exact global
  body translation/orientation will require a separately defined base-state
  source such as IMU plus odometry before a moving physical G1 can be represented
  in Unity or MuJoCo without a fixed base.
- The new 29-joint packet/model mapping passed 156 backend tests, 49 hardware
  bridge tests, Python compilation, both Unity C# assemblies, and the Unity
  prefab/project batch validator. A connected-G1 rerun of
  `VIEW_G1_LIVE_MUJOCO.bat` is still required before claiming that the new
  full-body live visualization itself has been physically verified.
- The G1 was disconnected because its battery was depleted. Offline development
  can continue with `tools/VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat`, which replays a
  saved 29-joint document through the same local UDP 5009 parser and MuJoCo
  application path without WSL, DDS, Ethernet, a publisher, or a motor command.
  The existing physical status file predates full-body logging, so the launcher
  currently identifies and uses the pose-sync validation artifact as a visible
  fallback. After the next connection, one `START_G1_READ_ONLY.bat` capture will
  become the automatic preferred source. Do not describe the fallback's static
  legs, waist, and left arm as measured hardware state. The expanded hardware
  bridge suite passes 54 tests; the backend suite remains at 156 passing tests.

### 2026-08-31 read-only G1-to-Unity full-body preview

- The physical/read-only G1 display path is now separate from the Mink control
  feedback path. UDP 5006 remains `state_source=mink_simulation` and remains the
  only receiver used by `G1ExistingTargetUdpSender` for workspace/collision
  feedback. Actual or saved LowState display packets use UDP 5010 with
  `state_source=g1_lowstate_read_only`; these packets cannot become IK targets or
  motor commands.
- `g1_unity_state_bridge.py` converts only a validated canonical 29-joint
  LowState document into the Unity display packet. All 29 names, positions, and
  velocities are required and must be finite. It preserves the bridge session
  and sequence and marks the compatibility `right_arm` state inactive.
- `live_lowstate_mujoco.py` can now forward each newest accepted UDP 5009 packet
  to the Unity display port. `VIEW_G1_LIVE_MUJOCO.bat` enables this on UDP 5010,
  so one read-only subscriber updates both MuJoCo and Unity. No Unitree command
  type or DDS publisher was added.
- `replay_saved_lowstate_mujoco.py` and
  `VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat` use the same UDP 5010 display path without
  G1, Ethernet, WSL, DDS, or VR. The currently selected artifact is still
  `g1_hardware_pose_sync_validation.json`, so its static legs, waist, and left
  arm are fallback validation data and must not be described as a physical
  full-body capture.
- Unity now has distinct state receiver components on ports 5006 and 5010.
  `G1UnityRightArmPreview` prefers a fresh complete hardware state for the
  official 29-DoF G1 rig and falls back to Mink state when hardware data is
  unavailable. The hardware receiver rejects packets with a missing or wrong
  source. Automatic workspace disengagement remains disabled as required by the
  current scene validator.
- Verification passed: 58 hardware-bridge tests, 156 backend tests, Python
  compilation, saved-state Unity-packet validation, both Unity C# assemblies,
  and the Unity project batch validator. The physical G1 was disconnected, so
  live `rt/lowstate -> Unity` motion has not yet been visually verified on the
  robot. The next physical check is Unity Play mode plus
  `VIEW_G1_LIVE_MUJOCO.bat`; it remains observation-only.
- `docs/NETWORK_QUICK_REFERENCE.md` is the operator-facing one-page memo for
  UDP 5005-5010, DDS domain/topic names, host addresses, launcher mappings, and
  the distinction between Mink feedback on 5006 and hardware display on 5010.
- Stale documentation was synchronized with the active launcher: virtual-center
  is now the default, `--baseline` is comparison-only, and the current wrist
  assist hysteresis is 18/28 degrees. No controller behavior changed.

### 2026-08-31 delayed XR head-pose initialization fix

- A Unity Play run showed the CenterEye pose at `(0, 0, 0)` for roughly the
  first 5.28 seconds, followed by the valid Quest floor-space head pose at about
  `y=1.23 m`. The one-time camera alignment had already completed while the pose
  was zero, so the later tracked height was added on top of the G1 head mount and
  the first-person view appeared above the robot.
- `G1HeadLockedCamera` now waits until Meta reports EyeCenter position and
  orientation as both tracked and valid for 0.15 seconds before applying the
  one-time TrackingSpace translation. Loss of validity before alignment resets
  the timer. The applied correction, camera position, and mount position are
  logged once for diagnosis.
- The current operator requirement supersedes the earlier VR comfort policy:
  after the one-time horizontal heading and position alignment, the camera
  position is corrected every frame to the current G1 `head_camera_mount`.
  Continuous correction changes TrackingSpace translation only, so Quest head
  rotation remains untouched. If the displayed G1 head moves, the camera follows
  it; global walking motion still requires a separate base pose or odometry
  source because 29-joint `rt/lowstate` data contains articulation but no world
  translation.
- The scene setup and batch validator now enforce the 0.15-second stable-tracking
  delay and the four-part tracked/valid pose contract. Device verification still
  requires stopping and restarting Play mode with Quest connected.
- The first device retest showed that Meta's tracked/valid flags can precede the
  actual CenterEyeAnchor transform update: alignment logged zero correction with
  both camera and mount still at `(0, 0, 0)`, then the camera jumped to about
  `y=1.10 m`. The readiness gate therefore also requires a finite floor-space
  CenterEye local height of at least 0.4 m before starting the 0.15-second timer.
- The second device retest corrected height but exposed the same ordering defect
  in yaw: the official G1 preview anchored while the head pose was still zero,
  then the real Quest orientation arrived and the operator initially faced the
  robot's rear. Preview anchoring and engagement-frame capture now wait for the
  same validated head-pose gate.
- The frame ownership was then corrected: the connected G1 must not be rotated
  to match the operator. The Unity G1 root remains fixed at the robot-frame
  origin with identity rotation, while XR TrackingSpace receives one horizontal
  yaw rotation and one translation so CenterEyeAnchor coincides with
  `head_camera_mount` and faces the G1 forward direction. `rt/lowstate` supplies
  joint articulation but no global base pose, so the fixed Unity robot frame is
  the explicit base-pose assumption until IMU/odometry is integrated.
- A connected, controller-driven read-only integration test was then completed.
  The operator visually confirmed that the physical G1 full-body joint motion
  was reproduced in both MuJoCo and Unity, and that the Unity camera remained at
  the displayed G1 head mount while preserving Quest head rotation. Post-test
  inspection showed `READ_ONLY_ACTIVE` on `eth2`, all 29 `q` and `dq` values,
  no active fault, `publisher_present=false`, and
  `command_output_enabled=false`; one snapshot observed 2,348,181 received
  packets with 0.27 ms packet age. Unity also confirmed UDP 5010 reception from
  the read-only G1 source without a G1 packet-contract rejection. Walking world
  displacement remains intentionally absent until a base pose or odometry source
  is integrated.

### 2026-08-31 read-only G1 base-pose integration

- A subscriber-only live topic probe on `eth2` established the actual base-state
  source instead of assuming the common sport-mode topic name. On this G1,
  `rt/odommodestate` delivered `SportModeState_` at about 500 Hz and
  `rt/lf/odommodestate` at about 20 Hz; `rt/sportmodestate` delivered no samples.
  The high-rate `rt/odommodestate` topic is now the sole base source.
- `read_only_lowstate.py` now creates two DDS subscribers and still creates zero
  publishers: `rt/lowstate` supplies all 29 `q`/`dq` values, while
  `rt/odommodestate` supplies position, IMU quaternion, velocity, and yaw rate.
  No command-capable Unitree message or output path was added.
- `g1_base_state.py` validates the Unitree WXYZ quaternion, captures the first
  valid odometry sample as the run origin, rotates translation/velocity into the
  initial heading frame, computes the relative orientation, and emits normalized
  XYZW data. This prevents a previous absolute odometry origin from moving the
  Unity or MuJoCo model at startup.
- The optional `base_state` object is carried through the strict UDP 5009 parser
  and UDP 5010 Unity display adapter. Old saved packets without this object remain
  valid and use a fixed base. A missing or stale base stream does not stop the
  29-joint mirror; it holds the last base pose.
- `live_lowstate_mujoco.py` applies the relative base pose to the fixed model's
  `pelvis` body only for visualization, with no-overshoot translation smoothing
  and normalized shortest-path quaternion smoothing. Unity applies the same pose
  to the official G1 root using the explicit G1-to-Unity axis mapping. The
  head-mounted camera therefore follows displayed robot translation while Quest
  rotation remains operator-controlled.
- Verification completed in this change: 71 hardware-bridge tests, all 156
  backend tests, Python compilation, and both Unity C# builds passed with zero
  errors. A bounded live subscriber probe received 6,869 LowState packets
  and 3,205 odometry packets with no invalid base packet; the final status had
  `publisher_present=false`, `command_output_enabled=false`, a 1.1 ms base age,
  and a normalized near-identity relative pose. A separate live packet check
  then verified the complete UDP 5009 parser and UDP 5010 adapter output:
  `state_source=g1_lowstate_read_only`, 29 joints, and a valid
  `rt/odommodestate` base object. The new live viewer/forwarder was restarted.
  `VIEW_G1_LIVE_MUJOCO.bat` now also records each exact UDP 5009 source packet
  to `logs/runtime/g1_live_state_YYYYMMDD_HHMMSS.jsonl` and prints that path.
  The recording check saved 84 valid records with increasing sequences, 29
  joints, a valid base object, and both command flags false.
  A controller-driven directional visual check of translation and yaw is still
  required before claiming the base-axis behavior is physically verified.
- The operator then performed the controller motion test. Its captured run had
  8,559 ordered records over 364.65 seconds, one bridge session, 100% valid base
  states, zero malformed 29-joint records, zero command/publisher flags, and a
  maximum base age of 10.3 ms. Motion covered 0.208 m from the run origin and a
  yaw range of -15.8 to +25.9 degrees. The largest 18 mm position step and 1.82
  degree yaw step were consistent with the simultaneously reported maximum
  speed, rather than a coordinate discontinuity.
- That run exposed a display telemetry timing issue: the 20 ms polling sleep
  quantized the requested 30 Hz forwarder to 23.47 Hz. The read-only loop now
  sleeps to the actual next report/forward deadline and carries the forward
  deadline instead of resetting it each frame. After restart, the operator's
  106.394-second test captured 3,193 ordered records at 30.002 Hz with a
  33.857 ms p95 interval. Base pose was valid in 3,192 of 3,193 records, with
  only the expected first packet arriving before the odometry subscriber
  established its origin. Base age stayed below 7.8 ms, all records contained
  29 joints, and no publisher or command-output flag appeared. No control path
  changed.
- A subsequent review found that UDP 5010 still forwarded the unsmoothed 5009
  source immediately while MuJoCo displayed its 35 ms interpolated pose. Final
  displacement converged, but the two applications could visibly disagree
  during motion. The viewer now sends the exact joints/base pose applied in the
  current MuJoCo frame to Unity. The packet also carries source-versus-display
  position, orientation, and maximum joint interpolation errors. Unity checks
  that its actual G1 root transform equals that displayed pose and emits a
  `G1 BASE MIRROR` line once per second. Live runs automatically save
  `logs/runtime/g1_visual_mirror_YYYYMMDD_HHMMSS.jsonl` so the next operator
  test can be assessed numerically rather than by visual estimation. This is a
  subscriber/display-only change; no DDS publisher or motor-command path was
  added.

### 2026-08-31 Unity G1 head-camera PiP

- Operator situational awareness no longer depends on reproducing or reading
  the robot's world displacement in Unity. The strict 29-joint and optional
  base-state telemetry remain available for diagnostics and replay, while the
  actual surroundings are presented through a small G1 head-camera window.
- `G1HeadCameraPiP` now creates a 4:3 world-space canvas under
  `CenterEyeAnchor`, so the window stays in the operator's view. It establishes
  a receive-only Unity WebRTC connection to the TeleImager `/offer` endpoint,
  displays the received `VideoStreamTrack`, detects stale frames, and retries
  automatically. The status indicator is gray while offline, amber while
  connecting, green while frames are current, and red after a connection or
  stale-frame failure.
- `G1HeadLockedCamera` creates and owns the PiP at runtime without a
  name-based scene lookup. The default endpoint is the official-style private
  G1 PC2 URL `https://192.168.123.164:60001/offer`; the scene field remains
  configurable because the actual laboratory endpoint has not yet been
  measured. Self-signed certificate acceptance is restricted to loopback and
  RFC1918 private-network URLs.
- The PiP is an observation-only path. It creates no UDP control packet, DDS
  publisher, IK target, or joint command, and camera loss does not alter
  engagement or robot safety state. The existing right-arm command authority
  remains unchanged.
- Unity now resolves `com.unity.webrtc` 3.0.0 and both runtime and editor C#
  projects build with zero errors. Existing deprecation and JSON-deserialization
  field warnings elsewhere in the project remain. The editor also reports that this Unity WebRTC
  package is deprecated on the current Unity version; live G1 testing must
  therefore confirm receive/runtime behavior before treating this as the final
  production transport.
- The camera foundation validator was corrected so an unrelated legacy arm IK
  fixture cannot fail a camera transport test. It now gates only mount/optical
  axes, nonblank 640x480 BGR output, and Unitree shared-memory round-trip; the
  arm pose is retained as a non-gating reference. Verification passed the
  camera foundation, all 156 backend tests, Python compilation, and the runtime
  and editor C# builds with zero errors. A live TeleImager frame was not available
  during this change and remains the only unverified part.

### 2026-08-31 G1 camera measured path correction and local verification

- This section supersedes the TeleImager/WebRTC assumptions in the preceding
  historical section. The measured G1 at `192.168.123.164` did not listen on
  TCP 60001, so there was no TeleImager `/offer` service to receive.
- The official Unitree SDK2 Python `VideoClient.GetImageSample()` succeeded on
  WSL interface `eth2` and returned complete live JPEG frames from the G1 front
  camera. The SDK uses CycloneDDS domain 0 and the `videohub` request-response
  service. No G1 internal setting was changed.
- `g1_camera_tcp_bridge.py` now polls that read-only API at 20 Hz, validates each
  complete JPEG, adds a versioned 24-byte `G1CM` header, and forwards it only to
  Unity loopback TCP `127.0.0.1:5011`. It cannot create motor, mode, camera-setting
  or joint commands.
- `G1HeadCameraPiP` now owns a loopback `TcpListener`, decodes JPEGs on the Unity
  main thread, and preserves the existing world-space PiP and gray/amber/green/red
  status behavior. The unused `com.unity.webrtc` dependency was removed.
- `START_VR_HAND_TO_MUJOCO.bat` detects the G1 Ethernet path and automatically
  starts `tools/START_G1_CAMERA_TO_UNITY.bat`; the bridge waits safely until Unity
  enters Play mode.
- Local end-to-end verification displayed the live laboratory camera frame in
  the Unity Game view with a green status indicator. UDP 5005 and 5006 were both
  bound for the Mink simulation path, and TCP 5011 was established between the
  WSL bridge and Unity. This remains observation-only; Gate 6 and physical arm
  output remain locked.
- Future remote operation should retain the PiP but replace the local JPEG/TCP
  source with authenticated H.264/WebRTC. Do not expose DDS or TCP 5011 directly
  to a public network.
- After the first local operator test, the PiP was moved from the upper-right
  offset `(0.28, 0.16, 0.80) m` to the CenterEye forward axis
  `(0.00, 0.00, 0.80) m`. Size, distance, camera transport and safety behavior
  were not changed.
- The Unity inspection stick and panel had remained visible because the earlier
  hide change applied only to the read-only MuJoCo mirror. Their two independent
  runtime creators now default to hidden: `G1OfficialRig.show_inspection_tool`
  and `G1UnityRightArmPreview.show_inspection_scene` are both `false`. The model,
  inspection state receiver and demo code remain available; this is a reversible
  visualization setting and does not change IK, collision policy or command
  authority. Scene/model rebuild tools and the batch validator preserve this
  hidden default.
- `tools/TEST_CAMERA_REPLAY_TO_UNITY.bat` now exercises the same Unity TCP 5011
  PiP path while the G1 is powered off. `g1_camera_replay_tcp.py` generates a
  visibly labeled moving synthetic JPEG, wraps it with the shared `G1CM` frame
  contract and sends it only to loopback. It imports neither Unitree SDK nor DDS
  and cannot create a robot command. The launcher refuses to compete with an
  active real-camera bridge or another TCP 5011 source. Every run prints and
  saves `logs/camera/camera_offline_replay_*.json` with explicit offline and
  command-disabled flags.
- Pillow 12.3.0 was installed for Python 3.11 to generate the replay JPEGs. Four
  focused unit tests passed. A loopback integration receiver also verified a
  complete version-1 `G1CM` header and a 40,588-byte decodable JPEG; the replay
  saved its result JSON. Actual rendering in the Unity PiP remains the final
  visual acceptance check.
- The operator completed that Unity visual acceptance check. The saved result
  `camera_offline_replay_20260831_165426.json` passed with 369 frames sent over
  118.827 seconds and zero send errors. The 50 connection errors occurred while
  the replay was waiting for Unity to enter Play mode and do not indicate a
  broken frame after connection. The operator confirmed the labeled moving test
  pattern rendered in the centered PiP.

### 2026-08-31 Gate 7 locked Mink target adapter and Regular return

- The next hardware command contract was implemented as a separate, locked
  offline Gate 7. It does not import Unitree SDK2, open a network socket, create
  a DDS entity or publisher, or send a robot command. The existing Gate 6
  `hardware_output_authorized=false` boundary remains unchanged.
- Unity already emitted distinct `pinch_disengaged` and
  `tracking_disengaged` command modes. `MinkCommandStream` now preserves that
  original mode separately from Mink's computed `active/hold/idle` control
  state, and both Mink runners include it in the versioned UDP 5008 packet
  `g1.mink.right_arm.state.v1` together with sequence and measured minimum
  collision clearance.
- `arm_sdk_teleop_contract.py` strictly validates schema, source, canonical
  29-joint order, right-arm parity, session/sequence, packet age and collision
  fields. Active samples produce rate-limited right-arm 22–28 candidates.
  Missing/stale input, tracking loss, workspace exit and actual clearance below
  12 mm hold the measured dual-arm posture for up to 10 seconds. Valid active
  input before the timeout cancels the timer and resumes tracking.
- An active-to-`pinch_disengaged` edge plans an immediate return. An unintended
  disengagement that remains for 10 seconds plans the same return. The target is
  the captured grounded Regular dual-arm pose in
  `config/g1_regular_arm_pose.json`. Because Arm SDK weight is global to both
  arms, the return covers 15–28 while waist and lower-body command mode/gains
  remain zero.
- The Regular return is a velocity, acceleration and jerk bounded
  minimum-jerk trajectory. Gate 7 requires an external validator and checks
  every 250 Hz sample against the active MuJoCo/Mink dual-arm collision pair
  set before accepting any return candidate. Missing validation or any sample
  below 12 mm fails closed to HOLD.
- `tools/TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat` is the only Gate 7 launcher at
  this checkpoint. The final offline integration generated 312 SDK-neutral
  arm-only candidate frames, reached Regular with zero final joint error and
  measured 27.133 mm minimum collision clearance over 251 return-path samples.
  It recorded `publisher_present=false`, `command_output_enabled=false`, and
  `hardware_output_authorized=false` in
  `logs/test_results/g1_gate7_mink_arm_sdk_offline_final.json`.
- Verification passed 156 backend tests and 94 hardware-bridge tests. Unity
  runtime and editor C# projects built with zero errors; existing deprecation
  and JSON field warnings remain. Unity 6000.5.4f1 batch validation also passed
  the scene, official G1 prefab, receiver separation, camera and hidden-default
  checks. No VR or physical G1 runtime test was performed for this Gate 7 change.
- Before any future live-target run, Gate 7 still needs live LowState feedback
  on every command tick, explicit acquire/release and interruption handling, a
  grounded Regular test, and separate user authorization. Do not connect the
  offline candidate directly to the Gate 6 publisher.

### 2026-08-31 Gate 7 ten-second HOLD fallback and remote-controller decision

- `config/g1_gate7_mink_arm_sdk.json` now pins
  `unintended_hold_before_regular_return_s=10.0`.
- The timer is armed only after the current session has produced a valid ACTIVE
  command. Initial waiting or idle cannot cause autonomous arm motion.
- Tracking loss, stale input, workspace exit, collision violation, inactive
  input or rejected active target enters `SAFETY_HOLD`. On entry, the command
  candidate is reset to measured dual-arm q so the hold does not continue toward
  an old target.
- Valid ACTIVE input before 10 seconds clears the timer and resumes
  `TRACK_MINK_RIGHT`. A persistent fault starts `REGULAR_RETURN` using the same
  collision-prevalidated minimum-jerk trajectory as intentional pinch.
- Once an intentional pinch return has started, later hand-tracking loss does
  not cancel it. A new session still cancels and resynchronizes fail-closed.
- The handheld G1 remote will remain part of the final system for emergency stop
  and operator mode control. It does not numerically drive the arm return; the
  current Gate 7 implementation only produces a saved-Regular dual-arm command
  candidate. Returning authority to the onboard Regular motion service through
  Arm SDK weight release remains a separate unimplemented and unauthorized
  grounded-hardware step.
- Offline validation passed 15 focused controller tests. The Gate 7 integration
  additionally verified both immediate pinch return and the 10-second timeout
  transition, with no Unitree SDK import, DDS entity, publisher or robot command.
  The result was saved as
  `logs/test_results/g1_gate7_mink_arm_sdk_offline_20260831_191609.json`.

### 2026-09-01 Gate 7 live dry-run stream adapter

- Added `hardware/g1_arm_bridge/gate7_live_dry_run.py`. It consumes the real
  strict Mink UDP 5008 stream at the configured 250 Hz Gate 7 command rate,
  applies the existing session/watchdog/cause/10-second-HOLD/Regular-return
  contract, validates measured-to-target error and builds SDK-neutral 35-slot
  Arm SDK candidate frames.
- The process imports no Unitree SDK, creates no DDS entity or publisher and
  has no robot-command function. Permanent
  `hardware_output_authorized=false` remains mandatory.
- Default `--measured-source mink` is an ideal-following shadow plant for long
  VR tests without a G1. Optional `--measured-source lowstate` consumes strict
  29-joint UDP 5007 telemetry; stale LowState over 250 ms or target error over
  10 degrees removes the candidate frame. Because no command is sent, sustained
  movement in LowState mode is expected to reach that error boundary.
- Every new Mink packet, state transition and denied frame is written to a
  timestamped JSONL event log. Ctrl+C or a bounded-duration run writes a result
  JSON and prints both absolute paths.
- Added `tools/START_G1_GATE7_LIVE_DRY_RUN.bat` as the user-facing VR launcher
  and `tools/TEST_G1_GATE7_LIVE_DRY_RUN.bat` as the automated verifier. The old
  A temporary compatibility wrapper forwarded to the strict Gate 7 launcher;
  that redundant wrapper was removed during the 2026-09-01 BAT cleanup.
- Updated the fake Mink sender to emit `g1.mink.right_arm.state.v1` with the
  canonical 29-joint order, session, sequence and safety fields while retaining
  compatibility with the older seven-joint safety receiver.
- Verification passed four focused core tests, a real localhost UDP process
  E2E test, the existing fake-Mink safety E2E test, and dependency validation.
  No physical G1 or VR runtime test was performed in this checkpoint.

### 2026-09-01 MuJoCo inspection scene default visibility fix

- `START_VR_HAND_TO_MUJOCO.bat` stated that the inspection stick and panel were
  hidden, but `g1_right_arm_common.make_demo_xml()` still generated the panel,
  stick/probe/tip and inspection target marker with visible alpha values.
- The generated model now preserves every inspection body and geom but assigns
  alpha zero by default. IK, body transforms, metrics and future inspection
  reuse remain available.
- `run_mink_g1_right_arm_virtual_center_live.py` accepts
  `--show-inspection-scene` to make the preserved scene visible deliberately.
  The default launcher passes no such flag, so normal arm/camera testing hides
  it. Dynamic marker-color updates no longer make the hidden marker reappear.
- Added two visibility contract tests. The complete backend suite passed 158
  tests after this change. No headset visual test was performed in this
  checkpoint.

### 2026-09-01 Gate 7 Regular-return MuJoCo feedback

- Added strict schema `g1.gate7.simulation_feedback.v1` on localhost UDP 5012.
  Every packet requires `simulation_only=true`,
  `hardware_output_authorized=false`, exact dual-arm indices 15..28, a process
  stream ID and increasing sequence.
- `gate7_live_dry_run.py` now sends each valid candidate to UDP 5012 in addition
  to logging it. This is a visualization datagram only; Unitree SDK, DDS entity,
  DDS publisher and physical command output remain absent and locked.
- The existing virtual-center MuJoCo process receives the stream. It ignores
  active tracking and all HOLD states, and applies only fresh
  `REGULAR_RETURN/REGULAR_HOLD` candidates while the Unity command is inactive.
  Only the 14 arm qpos values change; waist, legs and other joints remain
  untouched.
- `START_VR_HAND_TO_MUJOCO.bat` detects stale already-running controllers that
  do not listen on 5012 and tells the operator to restart them. The user can now
  observe the 10-second HOLD followed by minimum-jerk Regular return in the same
  MuJoCo window without a G1.
- Added packet-boundary, authorization-lock, freshness/state gating, UDP order
  and real MuJoCo qpos-application tests. Actual headset visual verification is
  still required after restarting all old MuJoCo/Gate 7 windows.

### 2026-09-01 Pinch-return start-pose synchronization fix

- The 10-second fault return looked smooth, but the user observed a jump on an
  intentional pinch return. The saved run did not contain a pinch transition,
  so the exact visual jump was not captured; code inspection identified that
  `measured_source=mink` only initialized its shadow pose once and then followed
  ideal Gate 7 candidates instead of re-synchronizing to each fresh UDP 5008
  MuJoCo pose.
- Gate 7 now updates the shadow measured 29-joint pose on every fresh Mink
  packet. The pinch edge therefore starts its minimum-jerk trajectory at the
  latest pose actually visible in MuJoCo. Between 60 Hz Mink packets the shadow
  still advances with accepted 250 Hz candidates.
- Added a regression test with a deliberately displaced current pose. The first
  `intentional_pinch_return` candidate has progress zero and exactly equals the
  latest measured dual-arm pose. Event JSONL now records measured dual-arm q and
  maximum target/measured error for future visual-jump diagnosis.

### 2026-09-01 Active-shadow regression and correction

- The next live run exposed `active_target_rejected` errors up to 30.73 degrees
  and 2,181 denied candidate frames in the prior completed run. The current run
  also logged `dual_arm_target_error:15.33deg`. Quest and MuJoCo packet parsing
  were healthy; the regression came from re-synchronizing the 250 Hz ideal
  Gate 7 shadow to every 60 Hz active MuJoCo sample.
- The shadow now remains on the accepted rate-limited candidate timeline during
  normal active tracking. It re-synchronizes to the latest visible MuJoCo pose
  only at initialization or when leaving active control through pinch,
  tracking/workspace/collision loss. This preserves zero-jump return starts
  without mixing active measurement timelines.
- Added separate regression tests for both invariants: active packets retain the
  rate-limited shadow and produce an allowed frame, while a pinch edge starts at
  the latest visible dual-arm pose with zero progress. Synthetic UDP E2E now
  requires zero denied frames.

### 2026-09-01 Regular-hold rearm and collision-shadow correction

- The saved live result
  `logs/test_results/g1_gate7_live_dry_run_20260901_125623.json` confirmed that
  intentional pinch return itself was correct: its first return candidate had
  zero progress and zero target/measured error, and the simulated arms reached
  the exact Regular pose smoothly.
- The same run then accumulated 5,944 denied frames. 5,896 occurred after the
  operator re-engaged while Gate 7 remained in terminal `REGULAR_HOLD`; MuJoCo
  accepted the new active Unity input, but Gate 7 continued validating the old
  Regular target. This was a state-machine rearm defect, not an IK or UDP packet
  failure.
- A fresh, valid active sample can now rearm `REGULAR_HOLD`. Gate 7 synchronizes
  its measured shadow to the visible MuJoCo pose, resets the safety-hold timer
  and resumes `TRACK_MINK_RIGHT` through the normal validation path. No stale or
  inactive packet can perform this transition.
- `collision_limited=true` can describe proximity handling before the hard
  safety boundary. It no longer replaces the active rate-limited shadow when a
  numeric minimum clearance is still at or above the configured 12 mm minimum.
  Shadow resynchronization occurs only for an actual sub-limit clearance, an
  incomplete collision state, workspace exit, inactive control or deliberate
  rearm.
- Focused tests cover safe nearby-collision tracking and rearming after Regular
  hold. The localhost UDP E2E also completes with no denied candidate frames.
  A new headset run must still verify: smooth pinch return, successful
  re-engagement after Regular hold, no `active_target_rejected` events and
  `denied_frames=0` in the saved result.

### 2026-09-01 Regular-hold rearm live verification

- The headset run saved
  `logs/test_results/g1_gate7_live_dry_run_20260901_130822.json` and passed.
  It received 4,767 valid Mink packets with zero rejected packets, generated
  9,976 candidate frames and denied zero frames. All 9,976 simulation-feedback
  frames were sent to localhost UDP 5012.
- Intentional pinch return began at `t=139.969 s` with zero progress and zero
  target/measured error. It reached Regular hold at approximately `t=142.110 s`.
  A later active input left terminal Regular hold, briefly entered collision and
  inactive/tracking-loss safety holds, and resumed `TRACK_MINK_RIGHT` at
  `t=150.469 s`. The terminal-state rearm defect is therefore fixed in a live
  headset run.
- A separate tracking-loss interval correctly triggered the 10-second
  unintended-hold timeout return at `t=163.063 s` and ended in exact Regular
  hold. Maximum validated target/measured error was 8.654 degrees, below the
  configured 10-degree rejection threshold.
- No Unitree SDK was imported, no DDS entity or publisher existed, and physical
  output remained disabled and unauthorized. Short `input_stale` and
  `collision_hold` transitions occurred during active motion but caused no
  rejected candidates; retain them as an observation item if the operator sees
  visible hesitation in a later run.

### 2026-09-01 Real-LowState Gate 7 launcher preparation

- Added `tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat` for the next connected-G1
  read-only experiment. It verifies that WSL sees `192.168.123.99/24`, starts
  the existing Cyclone DDS `rt/lowstate` subscriber, forwards all 29 joints to
  Windows UDP 5007 at 100 Hz, starts Gate 7 with
  `measured-source=lowstate`, and then opens the existing Unity/Mink/MuJoCo
  path.
- The launcher checks UDP 5007/5008 conflicts, validates the locked Gate 7
  configuration, verifies that the WSL forwarder stayed alive and prints a
  concrete action after every startup failure. It creates no DDS publisher and
  contains no G1 command path.
- Local dependency/config validation can be performed without a robot. The
  complete launcher intentionally cannot be runtime-verified until a powered
  G1 in Regular Mode is connected by Ethernet. Acceptance requires fresh
  LowState, zero malformed packets, expected 10-degree candidate rejection and
  no unintended motion because output remains absent.

### 2026-09-01 Bounded physical right-elbow publish experiment

- Added a separate intermediate hardware experiment; it is not the Gate 7 live
  VR publisher. The launcher is now named
  `tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat` and runs a read-only
  MotionSwitcher query and fresh startup precheck, validates both ±5-degree
  right-elbow paths with the active MuJoCo collision set, opens the existing
  actual-LowState MuJoCo mirror, and requires two exact operator confirmations
  before starting any publisher.
- `g1_right_arm_jog.py` publishes bounded 35-slot messages to `rt/arm_sdk` at
  250 Hz. Only the right-elbow target at hardware index 25 differs from measured
  LowState. The other 13 arm targets are reseeded from current measurements;
  waist and lower-body mode/gain/dq/tau remain zero. Target requests use Up/Down
  in 1-degree steps, are clamped to ±5 degrees from startup, rate-limited to
  5 deg/s and time-limited to 30 seconds with maximum Arm SDK weight 0.2.
- `Q`, duration expiry, signal or runtime fault initiates a release path. Normal
  release ramps weight to zero over one second and sends 25 additional zero
  frames. The `finally` path also attempts the missing zero frames after an
  exception. The handheld remote must remain ready for L2+B emergency stop.
- `VIEW_G1_LIVE_MUJOCO.bat` remains the source of visual truth: it mirrors actual
  29-joint `rt/lowstate`, not the requested elbow target. Added offline config,
  controller, authorization and endpoint-path tests. No physical G1 command was
  sent while implementing or verifying this checkpoint; the first grounded test
  remains explicitly pending.

### 2026-09-01 BAT launcher cleanup

- Removed `tools/START_MINK_G1_SAFETY_DRY_RUN.bat`. It contained no independent
  behavior and only forwarded to `START_G1_GATE7_LIVE_DRY_RUN.bat`; all current
  documentation now names the strict Gate 7 launcher directly.
- Retained `START_MINK_G1_HARDWARE_SYNC.bat` because it remains the only launcher
  that refreshes `g1_hardware_initial_state.json` for the offline Startup
  Recovery path. Retained the remaining BAT files because each still provides a
  distinct runtime, read-only hardware, network recovery, offline replay, or
  regression-test entry point.
- `backend.tests.test_batch_failure_guidance` passes after the cleanup. No robot
  connection, DDS publisher, or physical command was used during this change.

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
## 2026-09-01 - Startup precheck TimedPacket serialization fix

- The launcher now named `START_G1_RIGHT_ARM_JOG_MUJOCO.bat` reached the
  read-only startup precheck,
  collected valid LowState data, and then failed while saving the result because
  `check_startup_readiness.py` accessed `all_joint_*` directly on `TimedPacket`.
- `TimedPacket` contains `telemetry` and `age_s`; the 29-joint fields belong to
  `TimedPacket.telemetry`. Result serialization now uses
  `latest_full_body_snapshot()` and explicitly rejects a missing 29-joint state.
- This failure happened before the physical confirmation stage. The launcher did
  not create an `rt/arm_sdk` publisher and sent no robot command.

## 2026-09-01 - G1 network alias and elbow-jog mirror readiness

- The temporary Windows/WSL Ethernet alias `192.168.10.99/24` caused the
  Cyclone DDS interface to expose two IPv4 subnets. After the alias was removed,
  the existing `192.168.123.99/24` path again completed the read-only
  MotionSwitcher query with `form=0, name=ai`.
- A physical elbow-jog launch then passed the startup precheck with 102 LowState
  packets, 0.1442 deg maximum right-arm span, 2.549 deg/s velocity p95, and
  27.49 mm modeled clearance. Both +/-5 deg elbow paths passed collision checks.
- Step 4 falsely reported that UDP 5009 was not bound. The timestamped LowState
  and visual-mirror logs prove that the nested viewer did start and receive
  packets. The parent waited only four seconds while the nested viewer itself
  spends three seconds starting its forwarder before loading MuJoCo.
- The elbow-jog launcher now polls the Windows UDP endpoint for up to 15 seconds
  before deciding that the mirror failed. This run never reached the explicit
  physical confirmation and created no `rt/arm_sdk` publisher.
- The two long typed physical-output phrases in the BAT UX were replaced by one
  explicit `Y/N` key confirmation after the grounded-Regular, clear-area, and
  remote-ready conditions are displayed. The launcher still passes both exact
  authorization tokens to the Python boundary, so the command-side contract was
  not weakened or made implicit.
- The first post-fix attempt was blocked before publisher creation because the
  instantaneous initial arm velocity was 7.03 deg/s. Its result records
  `publisher_created=false`, `command_output_enabled=false`, and zero published
  frames. The velocity guard remains unchanged.
- The copied lower-body `twist2_static_stand.cpp` releases the `ai` motion
  service and publishes full-body `rt/lowcmd` at 500 Hz. Its normal end path
  sends a damping tail but does not select `ai` again. The companion
  `restore_g1_ai_mode.py` explicitly calls `SelectMode("ai")`; it is a mutating
  recovery utility, not a read-only check. The robot-local check confirmed that
  `ai` was already active and no TWIST2 process was running.

## 2026-09-01 - Lower-body TWIST2 standalone physical run

- With explicit operator action, the G1-local
  `g1_twist2_cpp_static_stand` binary completed its default physical run:
  1 s capture, 4 s leg-only blend, 2 s TWIST2 policy, then 3 s damping.
- The run reported `status=completed` and
  `reason=planned policy duration completed`. It produced 349 policy steps and
  4,962 full-body `rt/lowcmd` frames at 496.23 Hz. Active inference mean/p99/max
  were 2.69/7.58/7.93 ms. Maximum roll and pitch were 0.0208 and 0.0875 rad.
  Maximum predicted torque was 17.68 Nm and the torque limiter activation ratio
  was zero.
- As designed, the process ended in damping and did not restore the `ai` motion
  service. Do not start `rt/arm_sdk` testing until the operator explicitly
  restores `ai`, verifies `CheckMode` reports `form=0,name=ai`, and reruns the
  measured startup precheck.
- The program created the disclosed G1-local CSV
  `/home/unitree/twist2_deploy/g1_twist2_static_stand_1787641124.csv`. Do not
  copy, remove, rename, or modify it without explicit approval.

## 2026-09-01 - Copied G1 upper-body script review

- Existing G1 files were copied read-only to Windows under
  `references/lower_body/` and reviewed locally. No copied script was executed.
- `g1_upper_body_ab_test.py` is command-capable, not an inspection utility. It
  publishes `LowCmd` to `rt/arm_sdk` at 50 Hz, controls both arm ranges 15-28 by
  default, optionally controls waist 12-14, ramps Arm SDK weight from 0 to 1 in
  three seconds, and runs until Ctrl+C. It also creates and flushes a CSV on the
  G1. Its CLI offsets only move both shoulder-pitch joints together and optional
  waist pitch; it is not a general interactive seven-DoF arm jogger.
- That script lacks the current project's measured-state settling gate, joint
  range/path collision validation, bounded displacement/duration, stale-state
  watchdog, remote-stop integration, and maximum 0.2 weight. It must not be run
  as-is for the present right-arm test.
- `g1_check_arm_mode.py` is a LowState-only subscriber, but its hardcoded
  interpretation accepts `mode_machine=9` and labels `2` as whole-body. The
  connected 29-DoF G1 currently reports `mode_machine=5`, so this script's mode
  interpretation does not match the verified robot/firmware and must not be
  used as an authorization gate.
- `g1_inspect_arm_sdk.py` subscribes to `rt/arm_sdk` for three seconds and prints
  selected command slots. It creates no publisher and writes no file, but any
  future G1-side execution still requires explicit approval under the absolute
  mutation rule.

## 2026-09-01 - Physical right-elbow Arm SDK jog passed

- The earlier `RECOVERY_REQUIRED` result was caused by the G1 not being in its
  Regular pose. The measured right rubber hand-to-right hip clearance was only
  0.16 mm, so the precheck correctly blocked output and created no publisher.
- After restoring Regular mode, the same launcher produced
  `DIRECT_TELEOP_READY` with 27.79 mm minimum modeled clearance and no blockers.
- The then elbow-only launcher, now replaced by
  `START_G1_RIGHT_ARM_JOG_MUJOCO.bat`, completed a bounded physical test:
  `rt/arm_sdk` publisher created, 5,790 command frames sent, maximum weight 0.2,
  start-relative range limited to +/-5 degrees, and target rate limited to
  5 deg/s.
- The operator ended the run with `Q`. The result records 25 zero-weight release
  frames and `command_output_enabled=false`, confirming the command path was
  released rather than left active.
- The recorded maximum command-to-measurement error was 4.49 degrees. This is a
  successful transport/authority/release test, but it is not yet evidence of
  high-accuracy tracking under the low 0.2 command weight.
- Evidence: `logs/test_results/g1_right_elbow_jog_20260901_154448.json` and
  `logs/runtime/g1_startup_precheck.json`.

## 2026-09-01 - Right-arm single-joint jog expanded to 7 DoF

- Replaced the elbow-specific tool with
  `tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat`. One run selects exactly one joint:
  right shoulder pitch/roll/yaw, elbow, or wrist roll/pitch/yaw (indices 22-28).
- Up/Down changes only the selected target in 1-degree steps. The start-relative
  target range is capped at +/-10 degrees, target rate remains 5 deg/s, maximum
  Arm SDK weight remains 0.2, and the 30-second lifetime and zero-weight release
  behavior are unchanged.
- Before publisher creation, the launcher validates both +/-10-degree endpoint
  trajectories for the selected joint against the current 29-joint precheck
  pose in MuJoCo. Either direction failing the 12 mm collision clearance blocks
  the entire run; the safety threshold is not reduced to force a test through.
- The WSL publisher process compares its settled dual-arm LowState against the
  exact pose used by the Windows collision precheck. A maximum difference above
  1 degree blocks output so a stale collision path cannot authorize a changed
  physical pose.
- Local contract tests cover all seven indices and confirm that only the selected
  target differs while non-arm command slots remain disabled. On the latest
  captured Regular pose, shoulder pitch/yaw, elbow and all three wrist joints
  passed both +/-10-degree directions. Positive shoulder-roll motion fell to
  11.44 mm clearance and was correctly blocked.
- No DDS publisher or G1 command was created while implementing this expansion.
  Offline evidence is stored as
  `logs/test_results/g1_right_arm_jog_path_<joint>.json`.

## 2026-09-01 - TWIST2 left-arm jog comparison and integration decision

- The new right-arm Jog reuses the control concept from
  `g1_twist2_cpp_static_stand`: capture measured joint positions, change a
  selected target from keyboard input, clamp it to joint limits, rate-limit the
  applied target, and monitor command-to-measurement error.
- The command architectures are intentionally different. TWIST2 releases the
  AI motion service and publishes a single 500 Hz full-body `rt/lowcmd`: policy
  legs 0-11, captured waist/right arm, and keyboard left arm 15-21. It ends in
  damping and writes a CSV on the G1.
- The current laptop Jog keeps Regular/AI mode, publishes `rt/arm_sdk` at 250 Hz,
  selects one right-arm joint 22-28 per run, limits it to 5 deg/s and +/-10
  degrees, caps Arm SDK weight at 0.2, runs for at most 30 seconds, and exits by
  sending zero-weight frames. Legs and waist receive no active gains.
- Do not run an independent Arm SDK publisher in parallel after TWIST2 takes
  full-body LowCmd ownership. Final locomotion/upper-body integration should
  reuse the tested keyboard/VR target-generation and safety logic inside one
  command owner that assembles the 29-joint LowCmd: TWIST2 legs 0-11, assigned
  waist owner 12-14, VR left arm 15-21, and VR right arm 22-28.

## 2026-09-01 - Live 1-7 right-arm selection and adaptive angle permit

- `START_G1_RIGHT_ARM_JOG_MUJOCO.bat` no longer fixes one joint before startup.
  During the active 30-second window, keys `1..7` select shoulder pitch/roll/yaw,
  elbow, wrist roll/pitch/yaw; Up/Down changes the selected target by 1 degree.
- A joint switch cannot occur at an arbitrary displaced pose. The old joint is
  commanded back to its exact precheck/start angle at 5 deg/s, and both command
  and measured angle must be within 1 degree before the next joint becomes
  active.
- The configured displacement cap increased from +/-10 to +/-20 degrees, but it
  is not blindly applied. Before any publisher is created, MuJoCo scans each
  direction in contiguous 1-degree paths and stops at the first collision-path
  failure. The resulting permit is tied to the exact precheck timestamp and
  exact 29-joint pose; stale or mismatched permits are rejected in WSL.
- Local validation using the latest saved Regular pose produced: shoulder pitch
  `-20/+20`, shoulder roll `-20/+4`, shoulder yaw `-20/+10`, elbow `-20/+20`,
  wrist roll `-20/+20`, wrist pitch `-20/+20`, wrist yaw `-20/+14` degrees.
  This is local MuJoCo evidence only; a new connected-G1 run always creates a
  fresh precheck and permit before physical output.
- The directional search deliberately uses sequential 1-degree checks instead
  of binary search because collision safety is not guaranteed to be monotonic
  with joint angle. No DDS publisher or G1 command was created during this
  implementation and local validation.

## 2026-09-01 - Right-arm Jog tracking-lag correction

- Physical result `g1_right_arm_jog_20260901_161511.json` was not a pass. It
  selected shoulder pitch/roll/yaw and elbow, published 7,299 frames, then the
  command-to-measured difference reached the unchanged 8-degree hard gate.
  Emergency release sent all 25 required zero-weight frames. The apparent
  Regular return afterward came from releasing Arm SDK authority back to the
  existing AI/Regular controller, not from a Jog Regular-pose command.
- Proximal joint target rate is now 2.5 deg/s for the three shoulder joints and
  elbow. Wrist roll/pitch/yaw remain at 5 deg/s. Maximum Arm SDK weight remains
  0.2 and the 8-degree hard target-error gate is not weakened.
- Before accepting each Up/Down step, the runtime previews the next target. If
  that target would be more than 2 degrees ahead of measured LowState, it prints
  `INPUT BLOCKED`, counts the rejected input, and continues tracking the current
  target. This prevents rapid key presses from building a large target queue.
- Fault results now record active/pending joint, switch-return state, requested,
  commanded, and measured joint angles so the next hardware result can identify
  the exact failure phase.

## 2026-09-01 - Right-arm Jog weight 0.25 trial

- The first corrected-speed physical run passed and released normally, but the
  shoulder-pitch command moved from about 16.7 to 18.7 degrees while measured
  LowState remained near 16.8 degrees. It published 4,371 frames, blocked nine
  excessive queued steps, and held maximum command-to-measured error to 1.96
  degrees. This proves command publication but not useful physical tracking.
- For the next single-step hardware trial only, Jog maximum Arm SDK weight is
  raised one stage from 0.20 to 0.25. The code hard cap is also 0.25. Proximal
  speed remains 2.5 deg/s, wrist speed 5 deg/s, step lead 2 degrees, hard error
  gate 8 degrees, fresh pose-bound collision permit, 30-second lifetime, and
  repeated zero-weight release are unchanged.
- Gate 6 HOLD and Gate 7 configurations are not changed by this Jog-specific
  experiment. No physical command was sent while preparing the 0.25 trial.

## 2026-09-01 - Jog precheck expiry during path scan fixed

- The first 0.25-weight attempt was blocked before publisher creation because
  all seven directional path scans plus confirmation took 81.1 seconds while
  the precheck age limit was 60 seconds. Result
  `g1_right_arm_jog_20260901_163350.json` records zero published frames.
- The path scanner previously rebuilt the complete MuJoCo model and collision
  pair set for every 1-degree probe. It now constructs one
  `CollisionPathValidator` and reuses it across every direction and all seven
  joints; each validation call still resets and evaluates its path metrics.
- Jog precheck age allowance is 180 seconds to cover deterministic path scan
  and operator confirmation. This does not remove the publisher-boundary
  safety check: WSL still reads a new settled LowState window, verifies mode,
  and rejects the run if any measured arm joint differs from the exact
  collision-permit pose by more than 1 degree.
- A local no-publisher rerun on the same saved precheck completed the optimized
  all-joint scan in about 35 seconds and reproduced the same directional limits:
  pitch `-20/+20`, roll `-20/+4`, yaw `-20/+9`, elbow and wrist roll/pitch
  `-20/+20`, wrist yaw `-20/+12` degrees.

## 2026-09-01 - Jog authority acquisition moved after joint selection

- The next 0.25 trial was also blocked safely. While the operator had not yet
  selected a joint, the runtime ramped measured-pose hold weight to 0.25. At the
  first selection attempt, the arm had drifted 1.13 degrees from the permit
  pose, exceeding the unchanged 1-degree stale-pose gate. Result
  `g1_right_arm_jog_20260901_163801.json` contains an empty selection history,
  724 pre-selection frames, and 25 zero-weight release frames.
- Waiting now publishes only zero-weight measured frames. The first accepted
  `1..7` selection revalidates the current arm pose, then starts both the
  0-to-0.25 authority ramp and the 30-second active timer. This removes command
  authority acquisition before the operator chooses a target joint.
- A separate 15-second selection timeout prevents an indefinitely stale permit.
  Expiry ends with weight zero and no active joint. No physical command was sent
  while implementing this sequencing correction.

## 2026-09-01 - Jog per-joint tracking evidence added

- The first correctly sequenced 0.25-weight run passed, selected right shoulder
  pitch, published 2,467 frames, had zero blocked steps, stayed below 1.00 degree
  command-to-measured error, and released with 25 zero-weight frames after the
  30-second duration. Its final post-release pose matched the precheck pose, so
  that result alone cannot distinguish real motion from a stationary joint.
- Every subsequent result now stores `joint_tracking_summary` per selected
  joint: start angle; requested, commanded, and measured minima/maxima; maximum
  requested/commanded/measured excursion; maximum command-to-measured error;
  and accepted/blocked step counts. Control behavior and limits are unchanged.

## 2026-09-01 - Weight 0.25 tracking result

- Physical result `g1_right_arm_jog_20260901_164826.json` passed its transport,
  watchdog and release checks. It published 5,746 frames, ended on the
  30-second limit, and sent all 25 zero-weight release frames.
- Right shoulder pitch started at 16.682 degrees. Requested and commanded
  extrema reached 14.682 and 18.682 degrees, a 2.000-degree excursion in both
  directions, while measured LowState ranged only from 16.465 to 16.870 degrees.
  Maximum measured excursion was 0.217 degrees, about 10.8 percent of commanded
  excursion. Six steps were accepted and six were blocked by the 2-degree lead
  gate; maximum command-to-measured error was 1.862 degrees.
- Conclusion: rt/arm_sdk publication is functioning, but 0.25 Arm SDK weight
  does not provide useful shoulder tracking while the AI/Regular controller
  remains active. Do not call this successful position control and do not raise
  weight again without a separately reviewed bounded trial.

## 2026-09-01 - Separate weight 1.0 shoulder-pitch trial prepared

- The existing `0.25 / seven-joint` Jog remains unchanged. A separate locked
  config and launcher were added for one diagnostic question: whether full Arm
  SDK authority produces useful measured shoulder tracking while AI/Regular is
  active.
- `trial_mode=full_authority_shoulder_pitch_trial` is the only runtime mode that
  may set weight to `1.0`. Validation requires right shoulder pitch only,
  `+/-1 degree`, `1 deg/s`, a 5-second ramp, a 15-second active limit, fixed
  initial targets for all 14 Arm SDK joints, and blocked direction input during
  authority acquisition. Changing the ordinary Jog config to weight 1 is still
  rejected.
- After key `1`, the runtime fixes the measured 14-axis arm pose and ramps
  weight from 0 to 1. It prints `[ARMED]` only after full weight is reached and
  the largest target-to-LowState error across all 14 joints is at most 1 degree.
  Failure to settle within 10 seconds faults and uses the existing smooth and
  repeated zero-weight release path.
- Dedicated files are
  `config/g1_right_shoulder_pitch_full_authority_trial.json`,
  `tools/TEST_G1_SHOULDER_PITCH_FULL_AUTHORITY_OFFLINE.bat`, and
  `tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat`. The collision
  permit scanner evaluates only the joint enabled by the selected config.
- Offline validation passed, including 30 focused tests and the full 137-test
  hardware bridge suite. No physical G1 publisher was started while preparing
  or verifying this trial. A connected, grounded Regular-mode acceptance test
  remains required before drawing a physical tracking conclusion.

## 2026-09-01 - First weight 1.0 trial safely blocked during ARMING

- Physical result `g1_right_arm_jog_20260901_170014.json` created the publisher,
  selected right shoulder pitch, published 2,525 frames, accepted no Jog input,
  and faulted because the 14-axis hold did not settle below the original
  1.0-degree ARMING tolerance within 10 seconds. The emergency release sent all
  25 required zero-weight frames.
- Timestamp-aligned read-only LowState shows the limiting joint was left
  shoulder roll at about 1.13 degrees from its captured target. Right shoulder
  pitch differed by only about 0.18 degrees. This is consistent with a small
  loaded PD hold offset, not a shoulder-pitch command or path fault.
- The ARMING threshold is now 1.5 degrees. Weight 1.0, the 5-second ramp,
  shoulder-pitch-only authority, +/-1-degree travel, 1 deg/s rate, 10-second
  ARMING timeout and 15-second active duration are unchanged. Future results
  record latest and maximum ARMING error for every one of the 14 arm joints.

## 2026-09-02 - Full-authority shoulder-pitch tracking confirmed

- The revised full-authority trial was explicitly approved and run on the
  grounded G1. It created the `rt/arm_sdk` publisher only after the fresh mode,
  LowState, startup-pose and collision-path checks passed.
- Weight reached 1.0 after a 5.004-second acquisition. The largest 14-axis
  arming error was 1.037 degrees, so the revised 1.5-degree stability condition
  passed and keyboard shoulder-pitch input became active.
- Two shoulder-pitch steps were accepted and one was blocked. Requested and
  commanded excursion was 1.000 degree; measured LowState excursion was 1.340
  degrees and maximum command-to-measurement error was 0.432 degree. This
  confirms useful physical shoulder tracking at full Arm SDK authority, unlike
  the earlier 0.25-weight result.
- The run ended on its 15-second maximum-duration guard rather than Q, then
  completed the 2-second weight release and all 25 zero-weight frames. The final
  result passed with 5,729 published frames and no command process remaining.
- Result evidence is
  `logs/test_results/g1_right_arm_jog_20260902_150717.json`. The one-time full-
  authority config was immediately restored to
  `hardware_output_authorized=false`. Gate 7 remains locked. Operator
  confirmation of no unexpected jump, abnormal sound or balance disturbance
  is still required before the first live-target trial.
- The operator subsequently confirmed no unexpected jump, abnormal sound, or
  balance disturbance during the successful full-authority movement. The
  shoulder authority prerequisite is complete. The current Gate 7 algorithm
  still specifies `command_weight=0.2`, which the earlier physical Jog showed
  is insufficient for useful tracking on this G1. Do not unlock that existing
  profile unchanged. Prepare and offline-validate a separate first-live profile
  that acquires weight 1.0 while tightly limiting time and target excursion.

## 2026-09-02 - Gate 7 live hardware foundation prepared while shoulder test is deferred

- The existing Gate 7 dry-run and physical Jog paths were not replaced. A new
  hardware path was added separately so it can be reviewed offline before any
  VR target reaches the real robot.
- `gate7_mink_wsl_relay.py` binds Windows localhost UDP 5008, validates strict
  Mink schema and session/sequence order, then forwards the original datagram
  to WSL UDP 5013. It contains no Unitree SDK or DDS publisher.
- `gate7_live_arm_sdk.py` combines direct DDS `rt/lowstate` with the existing
  Gate 7 state machine. Its physical branch requires explicit CLI approval,
  exact confirmations, a separate unlocked config, fresh startup precheck,
  expected MotionSwitcher/motor modes, settled LowState and precheck-pose match
  before publisher construction.
- Publisher construction also waits up to 120 seconds for a valid packet on
  WSL UDP 5013, so Arm SDK authority is not acquired before Unity/Mink exists.
- The adapter acquires the measured dual-arm pose with a five-second weight
  ramp, changes only right-arm targets 22-28, holds the left arm, and keeps
  waist/legs disabled. Fault or stop uses a two-second release followed by 25
  zero-weight frames.
- `config/g1_gate7_live_hardware_output.json` remains intentionally locked with
  `hardware_output_authorized=false`. `START_G1_GATE7_LIVE_HARDWARE.bat`
  therefore exits before any publisher until the bounded shoulder test is
  reviewed and accepted.
- Offline verification passed: the dedicated foundation BAT, seven new tests,
  and the complete 144-test hardware bridge suite. No G1 DDS publisher or
  physical command was created during this preparation.

## 2026-09-02 - Virtual Gate 7 hardware E2E added

- Added `gate7_hardware_virtual_e2e.py` and
  `TEST_G1_GATE7_VIRTUAL_HARDWARE_E2E.bat` to exercise the future hardware data
  path without G1. Synthetic Mink packets traverse the real Windows UDP 5008
  validator/relay and arrive on UDP 5013 before entering Gate 7 with an ideal
  virtual LowState plant.
- The acceptance run forwarded eight valid packets and rejected one duplicate
  sequence plus one malformed JSON packet. Active command candidates were
  generated, collision input entered `SAFETY_HOLD`, unintended loss began
  `REGULAR_RETURN` after ten seconds, and stale LowState removed the frame.
- The same result verifies the configured authority lifecycle: acquire weights
  `0.0/0.1/0.2`, release weights `0.2/0.1/0.0`, then 25 zero-weight cycles.
- Result `g1_gate7_hardware_virtual_e2e_20260902_095807.json` passed. The full
  hardware bridge suite now has 145 passing tests. Unitree SDK, DDS entities,
  publisher and physical robot commands remained absent.

## 2026-09-02 - VR Mink capture and deterministic regression prepared

- Added a strict recording proxy. `gate7_mink_capture.py` owns localhost UDP
  5008, stores exact datagram bytes plus arrival offsets in JSONL, and forwards
  only accepted packets to Gate 7 dry-run on UDP 5014.
- `gate7_mink_replay.py` preserves recorded arm targets and command states while
  normalizing session ID, sequence, timestamp and packet age for a fresh run.
- `gate7_capture_regression.py` replays the capture against ideal virtual
  LowState at the configured 250 Hz. It hashes every state/reason/frame/14-axis
  target tick and compares capture/config hashes, state counts, frame counts
  and final state against a saved baseline.
- Regression includes a 13-second post-roll so stale detection, the ten-second
  unintended HOLD, minimum-jerk return and final `REGULAR_HOLD` are covered.
- Added `START_G1_GATE7_VR_RECORDING.bat`,
  `TEST_G1_GATE7_CAPTURE_REPLAY_OFFLINE.bat`, and
  `TEST_G1_GATE7_LATEST_CAPTURE_REGRESSION.bat`. The offline socket/process test
  passed and the complete hardware bridge suite now has 146 passing tests.
  Unitree SDK, DDS publisher and G1 command output remained absent.

## 2026-09-02 - Gate 7 offline fault-injection matrix added

- Added `gate7_fault_injection_matrix.py` and
  `TEST_G1_GATE7_FAULT_MATRIX_OFFLINE.bat`. The latest real VR capture can run
  the same matrix through `TEST_G1_GATE7_LATEST_CAPTURE_FAULT_MATRIX.bat`.
  Neither path imports Unitree SDK or creates DDS entities.
- Eight scenarios cover a sub-timeout packet gap, stale packet recovery,
  tracking loss, workspace exit, collision clearance, persistent packet loss,
  duplicate/reordered sequence rejection and stale LowState frame removal.
- Recoverable faults must freeze the current target and resume tracking on a
  fresh valid packet. Persistent loss must pass through `SAFETY_HOLD` and
  `REGULAR_RETURN` before ending in `REGULAR_HOLD`.
- This matrix is an offline fail-closed contract check. It does not prove VR
  tracking quality, physical G1 response, floor balance or real network timing.
- The synthetic matrix BAT passed all eight scenarios and saved
  `g1_gate7_fault_matrix_20260902_101203.json`. The complete hardware bridge
  suite passed 147 tests and batch failure guidance passed two tests. No real
  VR capture exists in `logs/captures` yet, so the latest-capture matrix remains
  the only unexecuted part of this addition.

## 2026-09-02 - First real Quest capture regression passed

- Recorded `g1_mink_capture_20260902_104056.jsonl` from Quest/Unity without G1.
  The recorder accepted 22,729 packets and rejected zero over 751.719 seconds.
  The interval from first to last packet was 734.609 seconds at 30.94 Hz mean;
  p95 packet gap was 47 ms and maximum gap was 141 ms, below the current
  350 ms input watchdog.
- Command-mode distribution was 21,501 idle, 726 active and 502
  `tracking_disengaged` packets. The capture therefore contains actual engaged
  tracking as well as a real tracking-loss segment; it is not an idle-only
  recording.
- The real-capture fault matrix passed all eight scenarios and saved
  `g1_gate7_capture_fault_matrix_20260902_105328.json`.
- A deterministic baseline was written and immediately compared. Both runs
  produced trace SHA-256
  `c8584458c64bb3ca75231e61a761908577ffbf0df98ac9221bb3dcc6ed10791a`.
  This proves repeatable controller output for the recorded packet stream, but
  not physical G1 tracking, balance or real DDS command behavior.

## 2026-09-02 - Quest capture quality report and MuJoCo replay added

- Added `gate7_capture_quality.py`,
  `ANALYZE_G1_GATE7_LATEST_CAPTURE.bat`,
  `gate7_capture_mujoco_replay.py` and
  `VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat`. All remain offline and create no
  Unitree SDK object, DDS entity, publisher or robot command.
- The quality analyzer separates raw 30 Hz Mink targets from the 250 Hz Gate 7
  ideal-following command candidate. It reports packet timing, active segments,
  joint ranges and derivatives, IK pose error, collision clearance, wrist limit
  margin, Gate 7 state counts and configured derivative-limit exceedances.
- Actual capture `g1_mink_capture_20260902_104056.jsonl` contains two active
  segments, 726 active packets and 23.702 seconds of engaged time. Of those,
  537 packets were collision-limited. Active minimum clearance reached 0 m,
  position-error p95 was 0.18863 m, orientation-error p95 was 24.595 degrees,
  and wrist limit margin reached 0 degrees.
- Gate 7 candidate velocity remained at the configured 40 deg/s proximal and
  100 deg/s wrist caps. The active path does not yet apply the configured
  acceleration and jerk limits: finite differences recorded 7,464 acceleration
  and 11,205 jerk exceedance ticks. Keep physical Gate 7 output locked until a
  stateful velocity/acceleration/jerk limiter is implemented and this capture is
  re-evaluated.
- The MuJoCo viewer automatically selects 1,295 packets spanning the 42.172 s
  engage-through-tracking-loss window, hides the preserved inspection scene and
  loops at recorded timing. Model/window validation passed; visual playback
  still requires an operator to open the viewer and inspect the motion.
- The first viewer launch exposed a Windows batch path-discovery bug: the
  PowerShell `for /f` command stored a single blank as the capture path. Both
  latest-capture BAT files now use `dir /b /a-d /o-d` instead. Running
  `VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat --validate-only` selected the correct
  70 MB capture and passed model/window validation without opening MuJoCo.
- The next visual launch exposed a replay-clock race where a second monotonic
  clock read could turn the requested sleep negative. The MuJoCo replay now
  sleeps only for a previously calculated positive remainder; the same latent
  pattern was corrected in `gate7_mink_replay.py`. The new timing unit test
  passed, and the real MuJoCo replay remained running for a 20-second smoke test
  instead of raising `ValueError: sleep length must be non-negative`.

## 2026-09-02 - Ruckig derivative-limited offline replay

- The first homegrown stateful limiter was rejected and removed after stricter
  direction-reversal tests exposed target overshoot and state-transition
  discontinuities. It must not be promoted to a physical command path.
- The replacement uses `ruckig==0.19.4`. One persistent online trajectory
  generator receives every Gate 7 command state, including active tracking,
  HOLD and Regular return. Per-joint synchronization is disabled so one slow
  joint cannot delay every other joint.
- Step and direction-reversal tests check finite-difference velocity,
  acceleration, jerk and target overshoot. The Ruckig wrapper and experimental
  Gate 7 controller tests pass.
- The original physical Gate 7 limits and code path are unchanged and remain
  locked. The current visible comparison is offline only: maximum velocity is
  scaled from 40/100 to 50/125 deg/s, acceleration to 3x and jerk to 6x. The
  actual Quest capture produced zero exceedances against those effective
  experimental limits.
- `VIEW_G1_GATE7_LIMITED_CAPTURE_MUJOCO.bat` replays 10,544 frames over the
  same 42.172-second capture window. It verifies the Ruckig dependency and
  prints the exact install command if missing. Validate-only passes. No Unitree
  SDK object, DDS entity, publisher or robot command is created.
- The current report is
  `g1_gate7_capture_quality_ruckig_faster_20260902.json` and `.html` under
  `logs/quality`. Operator visual review is still required before choosing a
  final offline profile, and any later physical profile needs a separate safety
  review.

## 2026-09-02 - Locked physical Gate 7 Ruckig candidate prepared

- Extracted `RuckigGate7TeleopController` as the common no-I/O trajectory layer.
  It preserves Gate 7 session, watchdog, collision, HOLD and Regular-return
  decisions, then applies one persistent Ruckig trajectory to every command
  state. Joint synchronization is disabled so joints are independently bounded.
- `gate7_live_arm_sdk.py` now constructs this controller before its publisher
  boundary. The physical profile is pinned in
  `g1_gate7_live_hardware_output.json` to Ruckig 0.19.4, velocity scale 1.0,
  acceleration scale 1.0 and jerk scale 1.0. Effective limits remain 40/100
  deg/s, 80/200 deg/s2 and 320/800 deg/s3.
- The repository hardware config still has `hardware_output_authorized=false`.
  No publisher or physical command was created. The eventual runtime dependency
  belongs in the laptop WSL environment; nothing is installed or changed on G1.
- The virtual UDP 5008-to-5013 hardware E2E passes with the physical Ruckig
  profile and virtual LowState. The real Quest capture also reports zero
  velocity, acceleration and jerk exceedances through
  `TEST_G1_GATE7_RUCKIG_HARDWARE_PROFILE_OFFLINE.bat`.
- Current physical-profile report:
  `logs/quality/g1_gate7_ruckig_hardware_profile_20260902_123138.json` and
  `.html`. Existing capture warnings about collision-limited IK frames remain
  review items; this derivative pass does not authorize physical output.
- Ruckig 0.19.4 and MuJoCo 3.11.0 are installed only in the laptop WSL virtual
  environment at `/home/user/.venvs/g1-teleop`. The live launcher checks that exact interpreter.
  The initial system `python3` check was intentionally abandoned because that
  unrelated Python 3.14 installation has no pip. No G1 filesystem was touched.
- `START_G1_GATE7_LOWSTATE_DRY_RUN.bat` now explicitly selects
  `--trajectory-generator ruckig`. It is the next no-output G1-connected test:
  real read-only LowState drives the same 40/100 physical candidate while all
  generated Arm SDK frames remain SDK-neutral logs only.
- The first real-LowState run exposed repeated false
  `ruckig_target_error` holds: because the test publishes nothing, G1 remains
  still while the candidate moves, so candidate-versus-physical error must
  eventually exceed 10 degrees. The no-output launcher now enables
  `--simulate-command-following`: actual LowState remains authoritative for
  initialization, freshness and mode, while an internal shadow applies accepted
  candidate frames. The physical adapter still compares commands against actual
  LowState and retains the 10-degree fail-closed gate.
- The same run received 10,704 valid Mink packets and 35,277 valid LowState
  packets with zero parse rejects; maximum LowState age was 125 ms. Remaining
  genuine disengagement reasons were embedded input stale, tracking loss and
  three collision holds. New logs include the embedded input age/mode/active
  fields and both shadow and actual LowState arm poses for exact separation.
- The follow-up 60-second run removed every `ruckig_target_error`, confirming
  the shadow fix. It then exposed a scheduler bug: the loop drained UDP before
  checking whether the 250 Hz tick was due, so packets received on non-tick
  iterations were discarded. Although 1,646 valid Mink packets arrived with
  zero rejects, active control repeatedly reached the 0.35-second stale gate.
  The loop now retains the newest pending Mink sample until the next control
  tick. The UDP E2E test explicitly rejects any `input_stale` event while the
  latest embedded sample is active.

## 2026-09-02 - Separate first physical Gate 7 VR profile prepared

- Physical Gate 6 interruption/release and the bounded weight-1 shoulder-pitch
  authority trial had already completed without operator-observed jump,
  abnormal sound or balance disturbance. Their one-time configs were returned
  to `hardware_output_authorized=false`.
- The standard Gate 7 profile was preserved. A separate first-live profile was
  added with Arm SDK weight 1.0, 20-second maximum active time, Ruckig limits of
  10/25 deg/s velocity, 20/50 deg/s2 acceleration and 80/200 deg/s3 jerk.
- The live adapter now checks all 14 commanded arm joints against the measured
  publisher-acquisition pose before every physical write. The first-live limit
  is 3 degrees; 3.00 degrees is accepted and 3.01 degrees raises
  `start_pose_excursion_limit`, after which the existing release path applies.
  The standard profile uses a 180-degree compatibility value, so its previous
  runtime behavior is not narrowed by this addition.
- `TEST_G1_GATE7_FIRST_LIVE_OFFLINE.bat` validates the exact two first-live
  configs and runs a profile-specific virtual UDP E2E. It passed with eight
  accepted packets, two rejected malformed/duplicate packets, collision HOLD,
  LowState stale removal, and no Unitree SDK, DDS publisher or robot command.
- `START_G1_GATE7_FIRST_LIVE_TRIAL.bat` is a dedicated physical wrapper. Its
  locked-launch smoke test stopped at `hardware_output_authorized=false` before
  any WSL adapter or publisher could start. No physical Gate 7 run was made.
- Regression status after the addition: 163 hardware bridge tests and 163
  backend tests passed. The first-live profile remains locked pending an exact
  physical-run approval.
- The first approved launch passed MotionSwitcher and the fresh startup
  precheck (`27.44 mm` clearance) but the parent BAT declared UDP 5013 missing
  after a fixed three-second delay. The adapter result showed
  `publisher_created=false`, `published_frames=0`; no physical command was sent,
  and the wrapper restored authorization to false. The launcher now waits up to
  20 seconds for SDK initialization and LowState settling before reporting a
  distinct bind timeout.
- A second approved launch still stopped before publisher creation because the
  new process-existence check ran during the WSL/Python startup gap and falsely
  classified the adapter as exited. Its result again recorded zero published
  frames and zero observed excursion. The one-run authorization was restored to
  false manually. The unreliable early `pgrep` branch was removed; the parent
  now waits only for the actual UDP 5013 bind for the full bounded 20 seconds.
- The third approved attempt also created no publisher or command. Its adapter
  log was empty and no runtime result JSON was created, proving the Python
  adapter never launched. The cause was Windows BAT quoting around a `bash -lc`
  pipeline added for logging. The BAT now contains no shell pipeline: it passes
  a plain `G1_GATE7_ADAPTER_LOG` environment variable, and the existing laptop
  WSL start script duplicates its own output with Bash process substitution.
  This repair remains locked and requires a new explicit physical approval.
- The fourth approved attempt reached the corrected logger and exposed the
  actual dependency fault: `/home/user/.venvs/g1-teleop` lacked Mink and its QP
  solvers. The adapter again exited before publisher creation with zero command
  frames. Installed only in the laptop WSL venv: `mink==1.3.0`,
  `qpsolvers==4.13.0`, `daqp==0.9.1` and resolver dependency SciPy 1.17.1.
  Imports and the exact adapter `--validate-only` path passed afterward with no
  SDK/DDS/publisher. The physical launcher now checks all pinned Mink, DAQP,
  MuJoCo and Ruckig versions before the operator confirmation step. Hardware
  authorization is false and a further physical run needs explicit approval.
- The fifth approved attempt passed dependency checks and reached the live
  adapter, which rejected startup before publisher construction because one
  instantaneous dual-arm `dq` sample was 3.16 deg/s against the first-live
  3.0 deg/s maximum. The independent one-second startup p95 was only
  1.055 deg/s and the physically completed Gate 6 HOLD/interruption profiles
  use a 5.0 deg/s instantaneous limit. The first-live instantaneous limit now
  matches that validated 5.0 deg/s value; the 3 deg/s p95 gate, 3-degree motion
  envelope, 10/25 deg/s trajectory limits and all authorization locks remain.
- The sixth approved attempt still produced zero publisher/command frames. A
  new no-publisher diagnostic mode then ran the identical WSL initialization
  path successfully: Unitree imports, DDS factory, read-only MotionSwitcher,
  839 LowState samples, 2.46 deg/s maximum instantaneous arm dq, collision
  controller construction and UDP 5013 bind all passed in 7.2 seconds. This
  isolated the remaining failure to the parent BAT's separate `ss` readiness
  polling. The adapter now writes a timestamped laptop-side ready JSON only
  after the real socket bind, and the BAT waits for that evidence file instead
  of inferring readiness from another WSL process. The file explicitly records
  `publisher_created=false`; publisher construction still occurs later, only
  after a valid Mink packet and all existing rechecks.
- The next approved attempt reached the real adapter and wrote its UDP 5013
  ready evidence, but stayed at `waiting for a valid relayed Mink packet`.
  The latest result still had `publisher_created=false`, `published_frames=0`;
  therefore the physical arm correctly remained still. The cause was transport,
  not IK or Arm SDK: `hostname -I` returned multiple mirrored WSL addresses and
  the launcher selected the unrelated first address. In addition, the full
  diagnostic Mink JSON was about 1,690 bytes, exceeding the 1,500-byte Ethernet
  MTU; fragmented Windows-to-WSL UDP was dropped. The launcher now derives the
  WSL source IP from `ip -4 route get 192.168.123.164` (currently
  `192.168.123.99`), and the relay strictly parses the original packet before
  forwarding a canonical command packet capped at 1,400 bytes. A real
  Windows-Python-relay to WSL-UDP-5013 no-output test received 1,359 bytes with
  accepted=1/rejected=0. Twelve focused tests pass. First-live authorization is
  restored to false; a new physical run still requires explicit approval.
- The first run after the route/MTU repair reached physical publication:
  `publisher_created=true`, 5,000 Arm SDK frames, 25 zero-weight release frames,
  no fault, and a bounded maximum command excursion of 1.25 degrees. The user
  could not see physical arm movement. Since 1.25 degrees is visually subtle
  and the old result did not record measured motion, this run does not prove
  whether firmware tracking occurred. The adapter now reports every 0.5 s and
  stores per-joint maximum command delta, measured LowState delta,
  command-to-measurement error, received Mink mode counts, and maximum weight.
  This is observability only; publisher, gains, limits and trajectory behavior
  were not changed. Twelve focused tests pass and authorization is false.
- The observability-enabled rerun proved physical command acceptance. Gate 7
  created the publisher, sent 2,248 Arm SDK frames at weight 1.0, observed up
  to 1.92 degrees of measured arm motion, then sent all 25 zero-weight release
  frames. The run intentionally faulted when a requested joint trajectory
  reached 3.04 degrees against the 3.00-degree first-live envelope. The largest
  accepted command before that fault was 2.98 degrees and the maximum recorded
  tracking error was 1.78 degrees. Only 16 received Mink packets were active,
  so the physically commanded interval was brief and visually subtle. This
  confirms the relay, publisher, Arm SDK and LowState feedback path; the next
  escalation should be a separate reviewed 5-degree visible-motion profile,
  not removal of the excursion guard. First-live authorization is false.
- A separate locked visible-motion profile is now prepared without changing
  the proven 3-degree profile. It uses weight 1.0, the same 10/25 deg/s joint
  speeds, a 5-degree start-relative envelope, a 30-second maximum duration,
  and the existing 5-second acquisition plus 2-second/25-frame release. Its
  dedicated launcher is `START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat`; automatic
  relocking targets only its own hardware config. Nine focused tests and its
  no-output virtual UDP E2E passed (8 accepted, 2 malformed/duplicate rejected,
  collision HOLD and LowState-stale removal verified). All physical configs
  remain locked pending exact one-run approval.
- The approved 5-degree visible-motion trial reached the complete physical
  path. It created the `rt/arm_sdk` publisher, sent 2,029 command frames at a
  maximum weight of 1.0, and returned all 25 zero-weight release frames. The
  maximum measured right-arm changes were 2.61, 1.55, 1.00, 0.66, 3.50, 3.80,
  and 0.28 degrees for motor indices 22-28. The run stopped fail-closed when a
  requested trajectory reached 5.02 degrees against the configured 5.00-degree
  start-relative envelope; this expected limit stop is why the result field is
  `passed=false`, not a transport or publisher failure. The largest accepted
  command stayed at 4.96 degrees, collision clearance remained clear in the
  latest Mink status, the release completed, and the visible-motion one-run
  authorization automatically returned to false.
- Since the 5-degree envelope was too narrow for evaluating practical hand
  following, the same locked `VISIBLE_MOTION` profile is prepared for the next
  stage with a 10-degree start-relative envelope. The proven 3-degree profile
  and the completed 5-degree result remain unchanged as evidence. The launcher
  is still `START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat`; its physical authorization
  remains false and requires a new explicit one-run approval.
- The first approved 10-degree run completed 7,500 Arm SDK frames but received
  776 Mink packets all in `idle` and zero in `active`. Consequently its largest
  right-arm command was only 1.85 degrees and no intended VR motion was sent;
  the user's observation that the G1 did not move is consistent with the log.
  This was not a 10-degree-envelope failure. The live adapter previously began
  publisher acquisition and its 30-second timer after any valid packet, even
  an idle one. It now waits specifically for both Mink `active=true` and
  `command_state=active` before publisher construction. Before engagement it
  therefore creates no `rt/arm_sdk` publisher and starts no physical-run timer.
  The completed run automatically restored the visible-motion authorization
  to false; another physical attempt requires fresh explicit approval.
- The next approved 10-degree run received 28 active Mink commands and produced
  visible physical motion. It published 1,466 Arm SDK frames; measured right
  shoulder motion reached 4.47 degrees and measured wrist motion reached 8.83
  degrees. It stopped fail-closed when the requested trajectory crossed the
  10-degree envelope (10.06 degrees requested, 9.96 degrees accepted) and sent
  all 25 zero-weight release frames. The user's report that this motion did not
  appear in Unity was also correct: the physical launcher had no process
  feeding the existing Unity hardware receiver on UDP 5010. Gate 7 now mirrors
  the exact direct `rt/lowstate` snapshots already used by its safety loop to
  Unity UDP 5010 at 30 Hz. This adds no DDS subscriber or robot publisher and
  does not alter Arm SDK commands; Unity's existing hardware receiver gives
  this fresh measured full-body state priority over the simulated Mink state.
  The one-run authorization returned to false.
- The first Unity-measured-state verification attempt stopped before any
  publisher because the previous Windows Gate 7 relay still owned UDP 5008.
  The exact stale `gate7_mink_wsl_relay.py` process was identified and stopped;
  Windows UDP 5008 and WSL UDP 5013 were then both free, and the one-run config
  was confirmed false. The launcher now checks WSL 5013 first. Only when no
  hardware adapter is listening may it automatically stop an exact stale Gate
  7 relay owning UDP 5008; an unknown UDP owner still causes a fail-closed stop.
- The next Unity measured-state physical attempt exposed a regression in the
  newly added UDP 5010 mirror block. The user heard mechanical chatter at
  engage and the robot stopped. Logs showed 227 Arm SDK frames, only 26 Unity
  packets, a right-wrist command near 10 degrees during the nominal acquisition
  phase, measured wrist motion up to 8.21 degrees, and tracking error up to
  8.15 degrees. The 10-degree envelope stopped the run at 10.07 degrees and all
  25 zero-weight release frames were sent. Root cause was an indentation error:
  the control `else` had accidentally attached to the 30 Hz Unity-send branch,
  so every non-Unity-send tick bypassed the five-second acquisition and ran
  active IK. The original acquisition/control branch is restored and Unity
  forwarding now runs independently after frame selection. An AST regression
  test requires the acquisition branch to own its `else` and the Unity branch
  to have no `else`. Physical output remains locked; do not retry this path
  until offline regression checks are complete and a new approval is given.

## 2026-09-02 - Gate 6 HOLD passed and Gate 7 three-degree retest prepared

- The approved Gate 6 measured-pose HOLD/interruption-release physical test
  completed normally. It published 2,030 `rt/arm_sdk` frames while holding the
  measured dual-arm pose, ramped Arm SDK weight down to zero, completed the
  zero-weight release, removed its publisher, and reported no fault. Its
  one-run `hardware_output_authorized` value automatically returned to false.
- After restoring the Gate 7 acquisition/control branch, the separate locked
  three-degree first-live profile was revalidated without physical output.
  Configuration validation, four first-live profile tests, eight live-adapter
  regression tests, and the virtual UDP end-to-end test all passed. The virtual
  relay accepted eight valid packets, rejected two malformed or duplicate
  packets, entered collision HOLD when required, and removed a stale LowState
  frame. No Unitree SDK, DDS publisher, or robot command was created.
- The offline E2E result is
  `logs/test_results/g1_gate7_first_live_virtual_e2e_20260902_165159.json`.
  The three-degree physical profile remains locked and requires a new explicit
  one-run authorization before `START_G1_GATE7_FIRST_LIVE_TRIAL.bat` is run.

## 2026-09-02 - Repaired Gate 7 branch passed three-degree physical retest

- The repaired acquisition/control branch completed a new three-degree Gate 7
  physical test. The adapter created the `rt/arm_sdk` publisher, sent 1,379
  command frames at weight 1.0, forwarded 154 measured LowState packets to
  Unity, and observed up to 2.03 degrees of measured arm motion.
- The run stopped fail-closed when the next requested trajectory reached 3.05
  degrees against the 3.00-degree envelope. The largest accepted excursion was
  2.99 degrees, all 25 zero-weight release frames were sent, UDP 5008/5013 were
  released, and the one-run authorization automatically returned to false.
- The next staged test uses the separate visible-motion profile reduced from
  10 degrees to a five-degree start-relative envelope. Its launcher argument,
  console description and profile regression test now all identify five
  degrees. Configuration validation, one profile test, eight live-adapter
  regression tests and the virtual UDP E2E passed without Unitree SDK, DDS
  publisher or robot command. The physical profile remains locked pending a
  new explicit one-run authorization.
- The five-degree offline E2E result is
  `logs/test_results/g1_gate7_visible_motion_virtual_e2e_20260902_172656.json`.

## 2026-09-02 - Repaired Gate 7 branch passed five-degree physical retest

- The approved five-degree visible-motion test created the `rt/arm_sdk`
  publisher and sent 1,394 command frames at maximum weight 1.0. Nineteen
  active Mink packets were received and 155 direct LowState telemetry packets
  were forwarded to Unity.
- The maximum accepted command excursion was 4.95 degrees. Measured right-arm
  motion reached 4.04 degrees, with the largest recorded command-to-measurement
  error at 1.99 degrees. The run stopped fail-closed when the next requested
  trajectory reached 5.04 degrees against the 5.00-degree envelope.
- All 25 zero-weight release frames were sent, command output and the publisher
  stopped, UDP 5008/5013 were released, and the one-run visible-motion
  authorization automatically returned to false. The result field is false
  because the deliberate excursion limit ended the run, not because transport,
  publication, Unity feedback or release failed.
- Physical result:
  `logs/test_results/g1_gate7_live_hardware_20260902_172941.json`.
- The operator observed no chatter, vibration, sudden motion or other abnormal
  physical behavior during this five-degree run, so the staged five-degree
  checkpoint is accepted. Adapter timing shows the 1.99-degree peak error was
  transient: the measured pose shifted about 1.11 degrees while the command
  remained fixed during the five-second acquisition, then the physical joints
  followed a rapidly increasing wrist target until the five-degree envelope
  stopped the short run. There is no evidence of a continuously diverging
  command/measurement error in this result.
- The same separate visible-motion profile is returned to a locked ten-degree
  envelope for the next staged test. The proven three- and five-degree result
  files remain unchanged as evidence. A fresh offline validation is required
  before any new one-run physical authorization.

## 2026-09-02 - Repaired Gate 7 branch completed ten-degree physical retest

- The approved ten-degree visible-motion run created the `rt/arm_sdk`
  publisher, sent 1,459 command frames at weight 1.0, received 26 active Mink
  packets, and forwarded 163 direct LowState telemetry packets to Unity.
- The largest accepted start-relative command was 9.98 degrees. Measured
  right-arm motion reached 8.91 degrees and the run stopped fail-closed when
  the next requested command reached 10.08 degrees against the 10.00-degree
  envelope. All 25 zero-weight release frames were sent, UDP 5008/5013 were
  released, and the one-run authorization automatically returned to false.
- The operator reported no chatter, vibration or sudden movement in the prior
  five-degree stage, but described this ten-degree motion as visually awkward.
  The per-joint maxima show that wrist roll/pitch consumed about 10 degrees
  while the elbow command changed only 0.73 degrees. This matches the current
  virtual-center policy, which normally assigns orientation to the three wrist
  joints and only recruits proximal joints near wrist limits. Do not widen the
  physical envelope until the operator identifies whether the objection is
  excessive wrist twist, elbow posture, timing/lag, or another visible motion.
- Physical result:
  `logs/test_results/g1_gate7_live_hardware_20260902_173416.json`.
- The subsequently approved three-degree physical retest reached the complete
  hardware path after the acquisition/Unity-mirror branch repair. It created
  the `rt/arm_sdk` publisher, sent 1,379 command frames at weight 1.0, received
  17 active Mink packets, and forwarded 154 measured LowState packets to Unity.
  The largest accepted start-relative command was 2.99 degrees; measured
  right-arm motion reached up to 2.03 degrees. The run then stopped
  fail-closed when the next requested trajectory reached 3.05 degrees against
  the 3.00-degree envelope and sent all 25 zero-weight release frames. The
  one-run authorization automatically returned to false and UDP 5008/5013
  were free afterward. Result:
  `logs/test_results/g1_gate7_live_hardware_20260902_165427.json`.

## 2026-09-03 - New Quest recording exposes simulation tracking limits

- Latest completed recording: `logs/captures/g1_mink_capture_20260903_091138.jsonl`,
  capture ID `a39765f6e824405e90aef55dfde3d970`. Recorder accepted 1,860 packets
  and rejected zero. One active segment contains 588 packets over 19.281 s;
  mean stream rate is 30.561 Hz and maximum recorded packet gap is 47 ms.
- Offline analysis result: `logs/quality/g1_gate7_capture_quality_20260903_091138.json`
  (matching HTML report). Status is REVIEW_REQUIRED, not a physical-test pass.
  Active position error p95/max is 8.246/9.372 cm and orientation error p95/max
  is 56.101/88.762 degrees. Wrist yaw reaches its -92.5-degree model limit.
- Relative to the first active sample, maximum absolute right-arm excursions
  in shoulder pitch/roll/yaw, elbow, wrist roll/pitch/yaw order are
  [48.05, 16.25, 36.22, 39.49, 81.12, 46.10, 92.50] degrees. These are observed
  IK excursions, NOT validated required ranges or proposed physical limits.
  The recording starts at [10, -22, 0, 55, 0, 0, 0] degrees, not the physical
  Regular-mode acquisition pose, so it cannot directly authorize that path.
- First 12 active seconds show position errors up to 9.37 cm with orientation
  errors below 6.61 degrees; seconds 12-16 show wrist-limit exhaustion and
  orientation error up to 88.76 degrees. Raw Quest orientation is absent from
  this packet contract, so a strict position-only versus rotation-only input
  classification and the root cause of the rotation mismatch remain unproven.
- The collision flag appears in 403/588 active packets (68.5%), but minimum
  recorded clearance remains 19.84 mm. This is a proximity/limiting flag, not
  evidence of physical contact or penetration. The analyzer also reports
  derivative violations for its baseline velocity-only candidate; its separate
  Ruckig candidate has zero velocity/acceleration/jerk limit exceedances. Do not
  attribute baseline warnings to the physical Ruckig adapter.
- Earlier claims that the small physical excursion envelope alone explains
  poor following were too strong: it shortened those physical trials, but this
  longer no-output recording also exposes IK/model-limit tracking failures.
  Keep hardware locked and investigate these before expanding physical limits.
  No controller/gain/limit changes or physical commands were made in this review.

## 2026-09-03 - Offline virtual-center IK correction, awaiting Quest retest

- The operator approved continuing the offline investigation. No physical run,
  robot-side file operation, authorization unlock, or hardware-limit expansion
  was performed. All eight Gate 6/7 authorization fields were verified false.
- Found a mathematical inconsistency: the orientation task multiplied proximal
  Jacobian columns by a wrist-margin gain (normally zero), although proximal
  motion still changes the actual wrist orientation. A central finite-difference
  check at the neutral target gave maximum derivative error 1.0 for the legacy
  task versus 2.78e-10 for the true Jacobian.
- `run_mink_g1_right_arm_virtual_center_live.py` now keeps the true orientation
  Jacobian. Wrist-first behavior comes from posture regularization: proximal
  cost stays 0.04; wrist cost is 0.002 (0.05 times the previous posture cost).
  Simply restoring the Jacobian with equal posture costs was rejected because
  a 25-degree wrist-roll trajectory induced 11.11 degrees of proximal motion.
  Increasing damping alone did not remove that redistribution either.
- The selected weighted-posture variant limits maximum proximal excursion to
  0.062/0.334/0.024 degrees in separate roll/pitch/yaw wrist-only FK trajectories
  (25-degree sinusoid, 12-second period). Rotation error p95 is about 0.402
  degrees. These are model tests, not measured physical performance.
- Five static FK goals taken from the captured robot poses also converged:
  selected-variant final position error at most 0.245 cm, final orientation
  error at most 0.000257 degrees after six simulated seconds. Compared with
  legacy, transient rotation p95 drops from 3.81 to 0.037 degrees for the first
  goal, and 58.41 to 38.00 degrees for the largest rotation goal. Large target
  steps still take time; this does not guarantee all Quest poses are reachable.
- Reproducible A/B tool: `backend/tools/verify_virtual_center_kinematics.py`.
  Result: `logs/quality/virtual_center_kinematics_20260903.json`.
  It compares legacy, exact orientation, yaw-position task, stronger damping,
  and selected weighted posture. The FK goals use recorded output poses,
  NOT the missing original Quest target rotations. Thus this is not evidence
  that the old recording's 88.76-degree error has been eliminated.
- New regression tests check the numerical Jacobian, wrist-only motion, a mixed
  reachable target, per-tick collision clearance, joint limits, velocity limits,
  frozen non-arm joints, and diagnostic serialization through the Gate 7 parser.
  The A/B report samples clearance every ten ticks; regression safety assertions
  check every tick. Backend and hardware-bridge offline suites pass.
- Added optional `right_arm.target_rotation_matrix_robot`,
  `wrist_rotation_matrix_robot`, and `orientation_solver_policy` to UDP
  feedback/capture as well as status JSON. These are model-frame rotation
  matrices, not physical measurements. `orientation_assist_gain` remains a
  compatibility diagnostic, no longer a Jacobian multiplier. See PROTOCOL.md.
- Preserved matching Unity trace as
  `logs/captures/g1_mink_capture_20260903_091138_unity_trace.csv` before another
  Play session can overwrite it. The original capture remains unchanged.
- Unchanged: roll-center position mapping, clutch reference/axis mapping,
  engagement/pinch logic, 20 mm IK clearance, 40/100 deg/s IK speed caps,
  physical Ruckig limits, and all physical-output locks. Physical acceptance
  of the previous solver does not authorize this changed solver.
- Next operator action: with G1 output disabled, restart the local Unity/Mink
  session through `tools/START_G1_GATE7_VR_RECORDING.bat`; engage, hold hand
  position while separately rotating the wrist, then translate slowly and test
  a mixed motion. Finish the recording with Ctrl+C in its recorder window.
  Review the newly captured 6D goals and errors before any physical retest.

## 2026-09-03 - Quest retest 093017 still needs tracking investigation

- User reported test complete. Inspected `g1_mink_capture_20260903_093017.jsonl`
  (capture ID `4feaf988e7a84f8c8dbb2f3f06226faa`). All 1,614 available packets
  carry `exact_jacobian_weighted_posture_v1` and the new target/actual rotation
  matrices, confirming the changed solver was running. No recorder result JSON
  was present; these findings concern the available capture, not proof of a
  clean recorder shutdown. The capture manifest keeps physical output false.
- Analysis saved to `logs/quality/g1_gate7_capture_quality_20260903_093017.json`
  and matching HTML. REVIEW_REQUIRED: 390 active packets in three segments,
  overall rate 31.122 Hz, maximum packet gap 47 ms. Active position error
  p95/max = 10.057/12.569 cm; rotation p95/max = 68.519/86.243 degrees.
  Different input motions prevent treating these numbers as a controlled A/B
  with the previous capture. Do not declare the operator tracking problem fixed.
- Segment 1: 209 packets, 6.75 s; position p95/max 8.33/9.88 cm, rotation
  3.37/6.40 degrees. Segment 2: four packets, 0.11 s. Segment 3: 177 packets,
  5.625 s; position p95/max 11.57/12.57 cm, rotation 78.20/86.24 degrees.
  Minimum wrist-limit margin in segment 3 remains 25.25 degrees, unlike the
  previous recording's zero margin. Wrist limit exhaustion alone is not the
  explanation for this segment's large error.
- Segment 3 target orientation changes at p95/max 619.6/1134.7 deg/s; these
  are end-frame angular rates, not directly equivalent to individual joint
  speed caps. Determine whether these reflect deliberate fast hand rotation,
  tracking-frame changes, or input-processing behavior before changing limits.
  The preserved Unity trace has fast changes too. An apparent 89-degree raw
  jump at Unity time 27.023 s crosses an invalid-to-valid tracking transition,
  so it must NOT be counted as uninterrupted valid hand motion.
- Held four selected recorded 6D goals stationary in offline Mink for six
  simulated seconds, starting from the corresponding recorded joint pose and
  using that pose as the posture reference. For segment 3's max-rotation sample,
  86.24-degree rotation error converged to 0.000289 degrees and 0.047 cm position
  error. Its max-position sample converged from 12.57 cm/57.67 degrees to
  0.347 cm/0.000171 degrees. Thus those particular targets can be approached
  when held; this supports transient lag rather than unreachable orientation.
- Segment 1's max-position target retained 3.315 cm error after the same test,
  although orientation reached 0.012 degrees. This is a residual convergence
  issue, not a proof of geometric impossibility or of a global IK solution.
  Holding a goal and resetting the posture reference is not exact sequence replay.
- Minimum captured clearance 19.22 mm; 135 active proximity flags are not
  actual collision events. Analyzer baseline acceleration/jerk warnings still
  belong to its velocity-only candidate; the separate experimental limiter has
  zero reported velocity/acceleration/jerk exceedances.
- Preserved `logs/captures/g1_mink_capture_20260903_093017_unity_trace.csv`.
  No controller, speed, limit, engagement, or physical authorization change was
  made during this review. Next useful test is separate slow translation and
  wrist rotation with several-second stationary holds, or exact recorded-goal
  offline replay; do not widen the physical limits based on this result.

## 2026-09-03 - Recorded 6D speed/hold comparison, hardware still locked

- Implemented `backend/tools/compare_recorded_pose_speeds.py`. Uses the 093017
  capture's actual target position/rotation samples at 1x, 0.5x, and 0.25x,
  then holds the final target for five simulated seconds. Each active segment
  is separate and starts from its preceding simulation feedback pose; session
  changes never reuse another session's reference. No interpolation is used.
  This is sampled-goal offline replay, NOT exact runtime timing, physical
  dynamics, the full acquisition/release pipeline, or a new safety permit.
- Nine cases completed. Report:
  `logs/quality/recorded_pose_speed_comparison_20260903_093017.json`.
  Segment 3 motion-only position p95 at 1x/0.5x/0.25x is
  11.255/5.053/3.514 cm; orientation p95 is 78.818/36.877/10.131 degrees.
  Slower target progression reduces transient rotation error substantially.
- Five-second holds still leave 4.11 cm position error in segment 3 and about
  4.97 cm in segment 1, while final rotation error is about 0.015 degrees.
  None meets the sustained one-second 1 cm / 5 degree settling criterion.
  This shows a remaining position-task/feasibility/convergence problem, not
  proof that slowing all motion fixes tracking. Do not increase robot speed
  or ask for repeated hardware trials to compensate.
- Also found nominal-clearance undershoot in the replay: segment 1 at 0.25x
  reaches 15.756 mm despite the unchanged 20 mm QP target. No penetration was
  observed in these cases, but nominal target clearance is not guaranteed by
  linearized discrete steps. The 12 mm hardware gate was not run by this tool.
  This evidence is REVIEW_REQUIRED, not a physical safety pass.
- Corrected the offline comparison harness: its position FrameTask had used
  the desired yaw rotation instead of the current roll-frame rotation used by
  the real controller. These are not interchangeable in the SE(3) log even
  when orientation cost is zero. Runtime controller was already correct and
  was NOT changed. This correction supersedes exact values in prior offline
  hold/A-B descriptions, but not the actual captured-error measurements.
  Re-ran prior A/B under corrected harness and saved separately to
  `logs/quality/virtual_center_kinematics_corrected_harness_20260903.json`.
  Wrist-only proximal excursions remain 0.062/0.334/0.024 degrees; maximum
  final static FK-goal position error is 0.251 cm. Existing findings that
  pure Jacobian restoration alone redistributes wrist motion still hold.
- Added regression tests for segment/reference isolation, time stretching,
  final holds, valid rotation matrices, and refusal to fabricate missing 6D
  targets. Backend suite: 172 tests passed. No live controller, speed, limit,
  engage logic, robot-side files, or physical authorization was modified.
- Next engineering step: investigate persistent position residuals using the
  recorded 6D targets and the same collision constraints; compare wrist-center
  task formulation and posture bias without changing hand-coordinate mapping
  or disabling safeguards. Additional physical trials are premature.

## 2026-09-03 - Persistent position residual explained by unreachable targets

- Added `backend/tools/diagnose_recorded_reach.py` and generated
  `logs/quality/recorded_reach_diagnosis_20260903_093017.json`.
  Uses actual model body translations along the right shoulder-pitch to
  wrist-yaw chain. All joints on that path are origin-centered hinges, so the
  triangle inequality gives a rigorous 0.4103940645 m distance upper bound.
  This is NOT the true workspace and does NOT certify targets inside it.
  It refers to wrist-yaw origin, not the dummy palm or inspection tool tip.
- Reconstructed the 29-joint recorded configurations before evaluating each
  target. Maximum FK wrist-position mismatch is 7.64e-14 m, ruling out an
  obvious model/root-frame mismatch for this recording. The diagnostic fails
  rather than judging reachability if reconstruction error exceeds 10 microns.
- 94/390 active targets exceed the bound: segment 1 = 74/209, segment 2 = 4/4,
  segment 3 = 16/177. Maximum requested distances are 45.70/43.64/44.35 cm.
  Segment-end distances are 43.92/43.52/43.82 cm, all beyond the 41.04 cm
  upper bound. Consequently the previously observed persistent end-position
  errors cannot be eliminated by faster following, lower posture cost, or
  exchanging the roll-center/yaw-center position task alone.
- Offline six-second static comparisons confirm this: selected segment 1
  remains at about 4.95-4.98 cm error, segment 3 at 4.10-4.12 cm, even with
  posture bias removed. The zero-posture experiment is diagnostic only and
  was NOT applied to the runtime controller. Direct yaw-position tests also
  retain the residual. A Cartesian-only position-task experiment gave the same
  outcome and was discarded, rather than adding another live control path.
- The static solver does not settle smoothly at these unreachable goals:
  last-step elbow velocity reaches +/-40 deg/s while position error barely
  changes (roughly 0.005 cm peak-to-peak over the final second in segment 1).
  This is simulated boundary oscillation, not an observation of physical G1
  vibration. Explicit feasible-target handling and boundary stabilization need
  validation before another physical trial.
- Extended the existing offline harness only with frame/cost comparison
  parameters and final velocity/error diagnostics. Added four bound regression
  tests including 1,000 deterministic FK configurations and rejection of an
  unrelated branch or an unsupported joint offset. Backend: 176 tests passed.
- No live IK gains, hardware speed/range/clearance settings, G1-side files,
  publishers, or authorization locks were changed. The next implementation
  should preserve the raw hand target, produce a separate achievable target
  through IK plus collision/joint checks, and prevent repeated pursuit of
  an impossible target. A 41 cm spherical clamp alone is not sufficient because
  orientation and collision constraints reduce the actual reachable set.

## 2026-09-03 - Checked local feasible target applied to simulation

- User approved proceeding with the separate feasible-target implementation.
  Added `MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py` and connected
  it to the current virtual-center live controller. No hand-axis remapping,
  clutch rebasing, velocity-cap increase, joint-limit relaxation, or physical
  authorization was made. The 40/100 deg/s simulation caps remain unchanged.
- The former `feasible_target_position = external_target_position.copy()` was
  only a raw-goal alias. Now a separate Mink configuration plans three short
  steps from the current simulation q. The simulation executes the first
  accepted step and reports FK of the final accepted look-ahead pose as green.
  Existing raw target/error fields remain untouched for honest diagnostics.
- Keeps the same true-Jacobian, weighted-posture, damping and QP constraints.
  Rejects nonfinite/over-speed/nonfrozen velocity, checks joint bounds and
  nonlinear model geometry at four substeps, and backtracks the proposed joint
  step until the actual yaw-wrist pose objective improves. If no improving
  step exists, holds current q; a new inward goal is reconsidered immediately.
  Predicted wrist-limit hysteresis is not committed as actual-controller state.
  A start already below the 20 mm model margin is invalid, NOT auto-recovered.
- This is LOCAL, sampled, kinematic validation: not a global nearest-workspace
  solution, continuous collision proof, acceleration/jerk guarantee, physical
  dynamics simulation, or a replacement for hardware Safety Gate / Recovery.
- Added optional feasible position/delta/valid/status/policy feedback fields.
  Unity green uses the backend feasible delta in the unchanged calibration
  frame. It checks freshness, active state, sender session and post-calibration
  state revision. Missing or stale feasible feedback does not fall back to raw
  cyan input. White/yellow engage feedback, index pinch disengage, axis-hidden
  setting, pink robot wrist and white discrepancy line remain unchanged.
- Offline replay tool: `backend/tools/verify_feasible_target.py`. Report:
  `logs/quality/feasible_target_verification_20260903_093017.json`.
  Replayed the three actual 093017 active segments, held each final goal six
  seconds, then requested the segment's initial wrist pose for six seconds.
  All three stationary-boundary final seconds have ZERO joint motion, versus
  the old solver's repeated +/-40 deg/s elbow motion at impossible goals.
  Return errors are 0.244 / 0.000050 / 0.084 cm; no reference reset was used.
  Minimum executed/look-ahead endpoint clearance was 19.999954 mm (within
  the explicit 0.0001 mm numerical tolerance); all accepted intermediate
  samples also pass the check. Caps and frozen DOFs pass.
- Raw impossible-goal gaps remain 4.97 / 4.59 / 4.13 cm, intentionally visible.
  Segment 3 moving-goal p95 remains 11.25 cm / 78.82 degrees under rapid input:
  this patch is NOT proof of perfect 1:1 tracking or a speed-lag fix.
  Measured planner p95 was 17.2 / 8.8 / 13.4 ms, worst 37.9 ms with other
  local tests running. These are not hard real-time guarantees; headset UX
  and live loop timing still need a new Quest-only recording.
- Tests added for reachable goals, boundary hold/inward return, wrist-only FK,
  stationary no-drift, invalid starts/velocities, collision rejection, and the
  actual main-loop packet path (mocked viewer and sockets). Gate 7 parser
  accepts the extended feedback. C# `dotnet build Assembly-CSharp.csproj`
  succeeds with 0 errors (61 warnings, including serialization/deprecation).
  Hardware bridge offline suite: 167 passed. Full backend suite: 184 passed,
  including the final runtime smoke test. Scoped diff whitespace check passes;
  unrelated pre-existing Scene YAML whitespace was left untouched.
- Three Gate 7 hardware-output profiles remain `hardware_output_authorized=false`.
  No SDK/DDS physical publisher or G1-side change was used for this work.
- Next user check: stop the old simulation/recording processes and Unity Play,
  then run `tools/START_G1_GATE7_VR_RECORDING.bat`. Engage, slowly extend,
  hold at the boundary, then bring the hand inward. Confirm green stops at a
  feasible point, pink does not oscillate, and inward tracking resumes without
  changed axes. Also check white/yellow engage feedback. Do not use a physical
  Gate 7 launcher for this verification. VR visual acceptance is still pending.

## 2026-09-03 - 101314 test: Unity feedback rejected; optional-object parser fixed

- Reviewed actual capture `logs/captures/g1_mink_capture_20260903_101314.jsonl`,
  ID `a82fd5aa7526421b899a6ef99498f0ec`. 2,171 packets, 378 active packets,
  one 13.140 s active segment. All packets use checked_local_lookahead_v1.
  Active statuses: following 293, local_limit 84, settled 1; invalid targets 0.
  Modes: idle 1,608, active 378, pinch_disengaged 185. No recorded tracking-loss
  disengagement; the end was deliberate pinch, not a workspace disconnect.
- MuJoCo active raw-goal position median 2.30 cm, maximum 13.32 cm; final
  0.328 cm / 0.047 degrees. Green-to-MuJoCo-wrist maximum 1.378 cm.
  Minimum model clearance 20.0154 mm. The body-boundary interval 2.609-3.047 s
  after engage has only 0.0208 degree joint span and then resumes following.
  Do NOT interpret every local_limit packet as frozen: the look-ahead may stop
  after an already accepted first step. Rapid rotation still causes large
  transient error (raw rotation error max 102.86 degrees). This is not a full
  tracking-quality pass or a physical test.
- Existing quality report saved as
  `logs/quality/g1_gate7_capture_quality_20260903_101314.json` and `.html`,
  status REVIEW_REQUIRED. Its p95 errors (discrete percentile method) are
  10.167 cm / 54.298 degrees. Baseline acceleration/jerk warnings concern the
  ideal-following velocity-only candidate; the separate Ruckig candidate has
  zero derivative-limit exceedances. No hardware permission follows from this.
- IMPORTANT: Unity did not receive usable feedback during this test. Preserved
  its matching trace at `logs/captures/g1_mink_capture_20260903_101314_unity_trace.csv`.
  All 473 command-valid trace samples have backend_recent=0 and NaN joint
  fields. Unity Editor.log reports `Rejected G1 state packet with an invalid
  base-state contract.` Preview logs also show 16-24 cm wrist discrepancy
  while backend-derived diagnostic values default to zero. Those zeros are
  MISSING feedback, not zero tracking error.
- The recorded Mink payloads omit optional base_state/mirror_diagnostics.
  The receiver used JsonUtility and tested nested DTO presence by non-null;
  this path rejected the arm-only payloads as malformed optional base data.
  Replaced only receiver deserialization with the already-installed Newtonsoft
  JsonConvert, explicit TypeNameHandling.None and MaxDepth=32. Missing/null
  optional objects stay null. Present malformed base/mirror data still go
  through the unchanged validators and are rejected. Malformed JSON is caught
  per datagram; no control, IK, axis, engage, speed, clearance or lock changes.
- Added `backend/tools/verify_unity_state_packets.ps1`. It invokes the actual
  compiled C# receiver parser and pure validation methods by reflection, without
  invoking any MonoBehaviour lifecycle, socket, SDK or viewer. All 2,171 stored
  packets and all 378 active feasible targets pass. Fixtures cover missing,
  null, valid, malformed optional objects and malformed JSON. Result:
  `logs/quality/unity_state_packets_20260903_101314.json`.
  Assembly-CSharp dotnet build: 0 errors, 61 warnings. This is not live Unity
  UDP/headset verification; that remains pending.
- Next: rerun the SAME Quest-only recording launcher after Unity recompiles
  and the old simulation/recorder windows are closed. First confirm robot and
  green marker receive feedback, then extend/hold/return. Do not tune IK or
  widen physical limits to compensate for a Unity receiver rejection.

### 2026-09-03 10:24 Quest recording review after receiver fix

- Source: `logs/captures/g1_mink_capture_20260903_102446.jsonl`, capture ID
  `8b5aeec0d79648e8b1a257dd50ecd5e9`. Recorder and offline simulator were still
  running after Unity Play stopped. Preserved a 10,896-packet snapshot at
  `logs/quality/g1_mink_capture_20260903_102446_review_snapshot.jsonl` and the
  matching trace at `logs/captures/g1_mink_capture_20260903_102446_unity_trace.csv`.
  Windows directory metadata reported zero length for the open capture, but
  reading its bytes confirmed recorded data. Do not interpret metadata as loss.
- Receiver fix is verified in live Unity logs: all 1,475 command-valid trace
  rows have backend_recent=1. The latest Play session has no invalid-base
  rejection; Unity replay diagnostics report 0.0 cm at displayed precision.
  This validates feedback ingestion, not headset visual quality or perfect IK.
- Snapshot has 1,239 active packets in three segments (11.531, 17.266, 12.171 s).
  All feasible targets are valid; following=955, local_limit=280, settled=4.
  Unity logs show intentional thumb-index pinch disengagements. No recorded
  tracking-loss mode appears. Ending state is pinch_disengaged / REGULAR_HOLD.
- Green-to-simulated-wrist gap: median 0.167 cm, p95 0.939 cm, max 1.339 cm.
  Minimum sampled model clearance is 20.002667 mm. Collision-nearby flag occurs
  in 605 active packets; that flag alone does not prove motion was blocked.
- User-goal tracking remains REVIEW_REQUIRED: report p95 position 15.639 cm,
  orientation 35.336 deg; maximum recorded position error 19.759 cm.
  Segment final position/orientation errors: 0.073 cm / 0.047 deg,
  14.930 cm / 7.281 deg, 1.204 cm / 1.086 deg. Do not classify all remaining
  error as speed lag or unreachable geometry without replay evidence.
- Analysis initially failed with division by zero: four adjacent packet pairs
  share receive timestamps. Patched only `_raw_metrics` to retain pose samples,
  count zero-dt active intervals, skip undefined derivatives and reset derivative
  history at those intervals. Added regression coverage; three quality tests pass.
  Re-running full capture analysis succeeds. Reports:
  `logs/quality/g1_gate7_capture_quality_20260903_102446.json` and `.html`.
  Derivative warnings concern the offline baseline candidate; the experimental
  Ruckig candidate reports zero derivative-limit exceedances. Not hardware proof.
- No IK, mapping, speed, collision thresholds or hardware authorization changed.
  All three physical output profiles remain false. No G1 access or publisher.
  Next useful offline work: replay the second/third active segments and separate
  reachable-goal tracking lag from local QP/clearance/operational-limit stalls.

### 2026-09-03 explicit Unity display source selection

- User correctly distinguished accepting Mink packets for simulation from
  displaying them as measured G1 state. The receiver parser fix remains valid.
  Found a separate actual bug: GetDisplayStateReceiver selected hardware when
  recent, then automatically fell back to simulation on missing/stale hardware.
- Replaced that fallback with explicit per-Play Simulation / Hardware / Recorded
  modes in G1UnityRightArmPreview. Selection comes from local
  `logs/runtime/unity_display_mode.json` (schema g1.unity.display.v1).
  Missing/invalid config blocks display updates; a detected mode change during
  Play latches a block until Play restarts. Config is polled every 0.5 s, not every
  frame. This file and its helper authorize NO robot output.
- Hardware mode only applies fresh full-body hardware receiver state with exact
  g1_lowstate_read_only source. Stale/missing data leaves the last displayed pose
  untouched, never replaces it with Mink. Before any first hardware packet the
  prefab/default posture is not measured. Simulation uses only the Mink receiver.
  Port 5010 source filter is now strict even if Inspector settings allow legacy.
- Added head-relative TextMesh status: SIMULATION, G1 LIVE - MEASURED, G1 STATE
  LOST / WAITING - POSE FROZEN, RECORDED G1 - NOT LIVE, or restart/missing-mode
  status. Tracking/engagement markers hide when display state is unavailable.
  Existing hardware watchdog/command control is unchanged; a display freeze is
  NOT a motor stop. Green target remains separate Mink diagnostic feedback, not
  measured joints. UnityReplayError is NaN outside simulation to avoid treating
  actual-vs-simulated differences as mesh replay errors.
- `tools/SET_UNITY_DISPLAY_MODE.ps1` atomically writes local mode selection.
  Root START_VR_HAND_TO_MUJOCO defaults to simulation; --hardware-display selects
  hardware. Gate 7 live launcher selects hardware before starting its processes
  and passes that flag to the root launcher. Live LowState viewer selects hardware;
  saved LowState replay selects recorded. Existing Quest recording/dry-run paths
  retain simulation. Stop Play before switching, then start Play again.
  Current local selection was initialized to simulation with the helper only.
- The source label is provenance metadata, not authentication; do not run stored
  hardware-state replay and the live mirror simultaneously on shared ports.
- Verification: 185 backend tests pass; compiled C# mode matrix 32 cases,
  valid/invalid/missing configs, strict hardware-source rejection, and 10,896
  recorded packet parser/contract checks pass. Build: 0 errors, 63 warnings.
  Result: `logs/quality/unity_display_mode_verification_20260903.json`.
  Windows PowerShell helper executed successfully in simulation mode.
  VR status visibility and live hardware disconnect/reconnect have NOT been
  tested; no physical run, G1 access, or publisher was initiated. All three
  hardware output profiles verified false; IK/caps/collision parameters unchanged.

### 2026-09-03 display mode helper repeated-launch repair

- User reported `File.Replace` throwing "The path is not of a legal form".
  Reproduced in the BAT's Windows PowerShell 5.1.26100.9168. Initial creation
  had passed, but the existing-file replacement branch failed with `$null`
  supplied to the string backup-path argument.
- Replaced that argument with `[NullString]::Value`, preserving atomic file
  replacement and temporary-file cleanup. No display policy or control changes.
- Added `backend/tests/test_unity_display_mode_launcher.py`: copies the actual
  helper to an isolated temporary workspace (including spaces in its path), runs
  Windows PowerShell for first creation, repeated simulation, hardware/recorded
  selection and return to simulation; checks exact JSON and no leftover temp
  files. Invalid mode must fail without changing the previous file. Test passes.
  Hardware/recorded fixture selections only touch the temporary workspace.
- Ran the real local helper twice in simulation mode; both replacements pass.
  G1 was not accessed, no physical launcher/publisher was run. User should stop
  Unity Play and rerun the same START_VR_HAND_TO_MUJOCO launcher. Full launcher
  and headset playback remain user-side verification.

### 2026-09-03 11:30 Quest test: user reports catching/sticking IK

- Latest test used the root simulation launcher, not the capture proxy. Only
  the Mink process started at 11:30:33 remains running; there is no new complete
  UDP capture for this session. Preserved Unity trace (1,154 rows) as
  `logs/quality/quest_trace_20260903_113033_ik_review.csv` and a post-test runtime
  snapshot as `logs/quality/mink_status_20260903_113033_after_test.json`.
- Unity confirms SIMULATION mode and fresh backend state on all 926 active
  trace rows. Active position error median 1.655 cm, p95 18.131 cm, max 20.025 cm;
  orientation p95 82.877 degrees, max 115.061 degrees. Collision-nearby flag is
  set in 584 active rows, not equivalent to 584 blocked solves.
- Sampled joint motion is nearly stationary (<0.1 deg/s maximum across seven
  joints) at Unity times 20.376-21.183, 22.548-23.828, 27.615-28.506,
  30.218-31.360, 33.463-34.464 s. Durations 0.807-1.280 s; end position errors
  3.65-14.56 cm. All have collision-nearby flag. Elbow reaches the configured
  operational 5-degree lower limit. Post-test nearest pair is torso vs right
  shoulder-yaw link, distance 20.00042 mm; this is NOT a full-run minimum.
- Display/PowerShell fixes did not change IK, but the earlier green-target
  work DID change the executed control path: FeasibleTargetPlanner runs Mink
  then accepts backtracked steps only if external wrist 6D merit decreases and
  four intermediate configurations satisfy joint/20-mm clearance checks.
  No acceptable step means hold. Thus this is not the upstream example unchanged.
- Verified upstream examples/humanoid_g1.py at
  https://github.com/kevinzakka/mink/blob/main/examples/humanoid_g1.py :
  solve_ik then integrate_inplace, 200 Hz, hand FrameTasks at palm sites, torso/
  feet/CoM/posture tasks, and selected hand-table/hand-thigh pairs at 5 mm.
  Our fixed-body wrist-center tasks, 243 pairs, 20 mm margin, velocity caps,
  operational joint limits and post-QP merit gate are different conditions.
- Strong candidates for catching are the custom step-acceptance gate and active
  geometric/operational boundaries; trace alone cannot isolate which rejection
  caused each stop. Do not claim original Mink guarantees exact tracking or
  remove torso collision protection as a fix. Next comparison should keep the
  same model/goals/limits and isolate the added merit/backtracking acceptance
  offline, with explicit rejection reasons, before altering live control.
- This turn only inspected code/logs/upstream and preserved evidence. No IK
  tuning, rollback, hardware permission change, G1 access, or physical output.

### 2026-09-03 offline step-acceptance comparison: boundary deadlock reproduced

- Added OFFLINE ONLY `backend/tools/compare_mink_step_acceptance.py` and four
  tests in `backend/tests/test_mink_step_acceptance_comparison.py`. Replays the
  three active windows of the fixed 10:24:46 review snapshot, followed by a
  six-second final-goal hold and six-second return to initial FK wrist pose.
  This is a deterministic first-step kinematic comparison, not exact live timing,
  physical dynamics, a reachability proof, or a new recording of the 11:30 test.
- Numerical parity with production Plan.next_q passed on three goals over 12
  steps each. All variants keep 243 collision pairs, the 20 mm sampled FK guard,
  operational joint bounds, non-right-arm freeze and 40/100 deg/s speed caps.
  The green look-ahead is not executed by this test. No socket/SDK/publisher.
- Removing only the external merit condition does NOT resolve the deadlock.
  Segment 2: current / no-merit hold-end errors 15.010 / 14.733 cm; return-end
  errors 36.033 / 36.335 cm. All 360 hold steps fail the geometric check in both.
  Results: `logs/quality/mink_step_acceptance_comparison_20260903_102446.json`.
- Boundary audit isolates actual clearance rejection, not joint-limit rejection
  or missing pairs. At segment 2 time 0.567 s, wrist-yaw vs hip-roll distance is
  20.1016 mm, yet the QP proposes approximately 5.111 mm linear approach. Full
  integration gives 15.1155 mm; even 1/32 gives 19.9425 mm, so the post-check holds.
  Both QP and guard contain 243 pairs. At the later torso/shoulder-yaw boundary,
  tangential steps can briefly cross the guard tolerance before moving outward;
  reducing to the existing minimum step does not always resolve this.
  Detailed q, velocity, nearest bodies and inequalities are saved in
  `logs/quality/mink_boundary_audit_20260903_102446_s2_current_merit.jsonl`
  and the corresponding geometry_only JSONL.
- Installed Mink and upstream main inspected this turn use a delta-q QP, but the
  collision h is gain*(distance-minimum)/dt. Offline IncrementCollisionLimit
  multiplies h by dt to express the velocity-form bound in increment units.
  The two-sphere regression verifies 60/200 Hz leave the same distance margin.
  Source: https://github.com/kevinzakka/mink/blob/main/src/mink/solve_ik.py and
  https://github.com/kevinzakka/mink/blob/main/src/mink/limits/collision_avoidance_limit.py .
  This is an investigated unit inconsistency, not an upstream-accepted fix.
  Do NOT edit site-packages or apply a blanket second dt correction elsewhere.
- Increment-unit correction alone still sticks at the exact FK boundary.
  A fourth OFFLINE variant additionally sets QP avoidance to 20.5 mm while
  leaving the final FK guard at 20 mm. The extra 0.5 mm is an experimental
  linearization reserve, NOT an optimized or hardware-approved parameter.
  Segment 2 hold-end error improves to 0.3525 cm; return-end to 0.0462 cm.
  Recorded-motion stalled durations (error >1 cm or >5 deg, speed <0.1 deg/s):
  current = 0.583 / 3.283 / 4.350 s; reserve = 0 / 1.250 / 1.667 s.
  Segment 3 still has a 1.4-second uninterrupted stall. NOT a complete fix.
  All three reserve variants settle and return, but sharp velocity changes still
  occur; no acceleration/jerk smoothness or hardware safety claim is supported.
  Minimum sampled distance remains >=19.9999 mm (existing 1e-7 m tolerance).
  Results: `logs/quality/mink_increment_bound_comparison_20260903_102446.json`
  and `logs/quality/mink_increment_reserve_comparison_20260903_102446.json`.
- Verification: 190 backend tests pass, including four comparison regressions.
  All offline comparison runs completed. Active IK, installed Mink, Unity,
  physical configs and running simulator were NOT changed. Three Gate 7 physical
  output profiles rechecked false. No G1 access or physical output occurred.
- Next: examine remaining segment 2/3 boundary holds and test the candidate on
  other stored captures before adopting it in the simulation controller. Do not
  remove collision protection or deploy this exploratory subclass to hardware.

### 2026-09-03 continued offline comparison: mesh witness mismatch isolated

- Scope remains OFFLINE ONLY. Updated the comparison tool and its tests, not
  production IK, Unity, launchers, installed Mink, or G1. There is no new default
  behavior to test by restarting START_VR_HAND_TO_MUJOCO.bat yet.
- Reproduced an isolated zero from mj_geomDistance at segment 3 time 5.65 s of
  the 10:24:46 snapshot, for torso vs right shoulder-yaw mesh. Existing FK guard
  resolves distance to 20.03902021 mm by tiny joint probes, but the original QP
  uses the unresolved witness normal. For the same proposed velocity, that
  normal predicts +0.0410557 m/s separation; finite differences show -0.0988231
  m/s approach. This is a concrete inconsistency, not missing collision pairs.
- Experimental ResolvedCollisionLimit resolves distance AND closest points at
  one matching probed configuration, then computes its Jacobian there. It uses
  separate MjData, preserves the input configuration, and raises on unresolved
  witnesses. A regression checks the normal against finite differences and
  confirms that the previously unsafe velocity fails the corrected inequality.
- Current resolved variants also use increment-unit bounds, a 20.5 mm QP
  reserve with the unchanged 20 mm sampled FK guard, and signed clearance
  recovery inside the reserve. These remain experimental, not upstream fixes
  or hardware approvals. Future reports record comparison_revision and tool
  SHA256. Earlier resolved_witness_comparison / resolved_no_merit_comparison
  reports predate signed reserve recovery; do not conflate their revisions.
- With the original virtual-center tasks AND merit gate retained, recorded
  longest stalls (>1 cm or >5 deg error, <0.1 deg/s speed) change from
  0.583/2.367/1.867 s to 0/0.083/0.067 s across the three 10:24:46 segments.
  No geometry_hold occurred during those candidate recorded phases. Their
  minimum sampled distances are 20.503/20.453/20.465 mm. All joint speed caps,
  operational joint limits and frozen-body constraints remain enforced.
- Important remaining limitation: segment 2 final-goal hold stops at 4.082 cm
  and 8.901 deg error because of merit rejection; initial-goal return reaches
  0.124 cm. Its final target is NOT proven unreachable. Do not call this full
  hand matching or deploy it merely because moving stalls are shorter.
- Secondary 09:30:17 recording: final errors are 4.970/4.586/4.130 cm, with
  stationary final joints and successful return. Its held targets exceed the
  0.410394 m shoulder-to-wrist chain-length upper bound (existing recorded reach
  diagnosis). Unreachable-target residuals are distinct from geometric deadlock.
- Rejected alternatives: removing merit eliminates moving stalls but produces
  sustained joint oscillation near held targets; replacing the virtual-center
  position task with a yaw-wrist task worsens segment 2 orientation to 22 deg.
  Increasing frame-task LM damping from 1e-5 to 1.0 leaves segment 2 at 4.109 cm
  / 8.400 deg, so damping tuning was not adopted. No acceleration/jerk or
  real-time computational-budget validation has been established.
- Result summaries (each has matching per-segment JSONL traces):
  `logs/quality/mink_resolved_guarded_20260903_102446.json`,
  `logs/quality/mink_resolved_guarded_20260903_093017.json`,
  `logs/quality/mink_resolved_reserve_recovery_20260903_102446.json`,
  `logs/quality/mink_resolved_reserve_recovery_20260903_093017.json`,
  `logs/quality/mink_consistent_wrist_20260903_102446.json`,
  `logs/quality/mink_consistent_wrist_20260903_093017.json`,
  `logs/quality/mink_resolved_damped_20260903_102446.json`,
  `logs/quality/mink_resolved_damped_20260903_093017.json`.
- Verification: 192 backend tests pass, including six comparison regressions.
  All comparison runs completed. Rechecked all three Gate 7 hardware output
  profiles: hardware_output_authorized=false. No G1 access or physical output.
- Next bounded task: isolate the segment 2 held-goal merit rejection using its
  exact target and configuration; compare the QP descent direction with the
  actual external-wrist merit gradient. Do not change wrist calibration, remove
  collision checks, or apply more arbitrary gain tuning. Only after resolving
  this and measuring solve cost should a simulation-only integration be tested.

### 2026-09-03 held-goal diagnosis: mismatched merit and local constraints

- Continued entirely offline in compare_mink_step_acceptance.py and its tests.
  Added exact held-q/goal snapshots and per-task versus numerical external-wrist
  merit gradients. Default launcher/controller/Unity and physical locks unchanged.
- Reproduced the previous segment 2 stop at 4.082225 cm / 8.901293 deg. The
  proposed velocity has actual merit derivative +0.0662606 (worsening), so
  rejecting it is correct. Elbow is at 120 degrees and wrist roll at its lower
  bound; clearance is 20.467775 mm, inside the experimental 20.5 mm QP reserve
  but outside the unchanged 20 mm final check.
- The virtual-center position task differentiates the roll-link point with a
  frozen roll-to-yaw offset; the external merit differentiates the actual
  yaw-wrist point, including displacement caused by wrist joints. At this q,
  their position gradients differ. Experimental WristPositionTask computes the
  exact world-space yaw-wrist position Jacobian. Its position gradient plus the
  uncapped orientation gradient matches numerical merit within 2.34e-10 here.
  This changes neither the user's tracking frame nor calibration. It is NOT yet
  installed in the production planner.
- A second mismatch appears when near-limit orientation error is clipped to
  12 degrees in the QP while merit uses the full angle. Experimental
  FullOrientationErrorTask retains joint limits, speed caps and adaptive costs,
  but uses the full rotation error. Tests verify the combined analytic/numeric
  gradient agreement also near wrist limits. Position-only correction is not
  acceptable: held rotation error rises to 21.528 degrees.
- Even consistent gradients are not sufficient: mandatory reserve restoration
  can require a temporary merit increase. At the consistent-merit stopped q,
  a linear program over +/-0.001 rad per joint with all increment constraints
  has minimum merit change +0.00015038 with reserve recovery, versus -0.00002414
  when only the reserve's negative bounds are floored at zero. The latter step
  actually lowers merit by 0.00001905, remains valid, and has 20.488357 mm
  clearance. This is a local diagnostic, not a connecting-path safety proof.
- Added consistent_tangent variant: allow zero/tangential velocity within the
  QP reserve, retaining the independent 20 mm FK check, 243 pairs, frozen body,
  operational ranges and 40/100 deg/s caps. Segment 2 recorded longest stall
  is 0.05 s; final hold is 3.049822 cm / 16.842572 deg; return is 0.008057 cm /
  0.024765 deg. Minimum sampled hold clearance is 20.007716 mm. It settles but
  is NOT a full match and is NOT selected for production. Rapid joint velocity
  changes still occur. Consistent-merit with reserve recovery instead ends at
  3.172609 cm / 18.168521 deg. Neither is better in every acceptance metric.
- Checked 12 deterministic joint-bounded least-squares seeds for this exact
  held target, with other joints frozen and independent final FK clearance
  checks. None passed the pose-match AND 20 mm clearance criteria. Near-exact
  solutions included 2.85 mm / 15.60 mm clearance and penetrating solutions.
  This is evidence of restrictive geometry, NOT proof that no valid solution
  or path exists. Do not lower the clearance or command one of these endpoints.
  The shoulder-to-target distance is 0.342114 m, within the 0.410394 m chain
  upper bound, so the simple reach sphere cannot prove this target impossible.
- New result JSONs (with corresponding replay JSONL where applicable):
  `logs/quality/mink_held_merit_audit_20260903_102446.json`,
  `logs/quality/mink_cartesian_merit_20260903_102446_s2.json`,
  `logs/quality/mink_consistent_merit_20260903_102446_s2.json`,
  `logs/quality/mink_consistent_tangent_20260903_102446_s2.json`,
  `logs/quality/mink_held_endpoint_audit_20260903_102446_s2.json`.
  The endpoint tool mode consumes an existing held audit and checks capture
  SHA256 before searching. It does not replay or execute endpoints.
- Timing samples include extra rejected-candidate diagnostic collision checks
  and are NOT production-controller benchmarks. Consistent-tangent first-step
  p50/p95/max is 6.586/35.152/114.107 ms in this diagnostic run; do not promise
  60 Hz based on these results or omit profiling before integration.
- Next decision: do not stack another arbitrary gain change on these variants.
  Separate collision-constrained endpoint feasibility from path feasibility for
  this fixed goal, then evaluate one selected consistent objective on held-out
  captures including wrist-only motion and near-boundary returns. Current
  evidence is insufficient to replace the working controller or unlock G1.
- Verification after this work: 196 backend tests pass, including 10 comparison
  regressions; both edited Python files compile. All comparison runs completed.
  All three Gate 7 hardware_output_authorized flags rechecked false. No G1
  access, DDS publisher, physical command, or production-controller edit occurred.

### 2026-09-03 constrained endpoint and path found for the held goal

- Added `backend/tools/diagnose_mink_collision_feasibility.py` and five tests in
  `backend/tests/test_mink_collision_feasibility.py`. Offline only; no production
  controller, Unity, startup strategy, G1 access or output permission changes.
  The tool verifies capture/source hashes and saved held-merit FK parity.
- This supersedes any inference that the previous twelve failed endpoints mean
  the goal is infeasible. SciPy SLSQP maximizes minimum collision distance while
  enforcing exact 6D wrist pose equalities and existing operational joint bounds.
  It refines the same twelve seeds; five find independently valid endpoints.
  Frozen joints and base remain exactly the held configuration. This search is
  diagnostic and not a real-time or certified global optimizer.
- Four seeds converge to effectively the same endpoint: clearance 25.142869 mm,
  target position/rotation residual approximately numerical precision. A fifth
  endpoint has 21.642152 mm clearance, but its direct path fails near the start.
  A valid endpoint alone is therefore explicitly NOT treated as a valid path.
- A direct joint interpolation from the consistent_tangent held q to the first
  endpoint passes both 0.25-degree (619 samples) and refined 0.05-degree (3088
  samples) independent geometry/joint checks. Minimum sampled clearance is
  20.007726 mm, at the starting pose. The original 20 mm guard is unchanged.
  These are discrete checks, not continuous-collision or physical safety proofs.
- Crucial UX limitation: right shoulder yaw changes +154.311 degrees, elbow
  -79.262 degrees, wrist roll +149.347 degrees. Wrist position error initially
  3.049822 cm reaches 13.874274 cm before converging; maximum orientation error
  is 37.053140 degrees. Merit rises from 0.081132 to 1.332636 and increases on
  1495 sampled intervals. Thus the existing monotone-merit acceptance rejects
  THIS valid sampled route. This does not prove every possible route must have
  the same detour, nor justify removing all acceptance checks.
- Velocity-only duration lower bound at 40/100 deg/s is 3.858 s. This is NOT a
  recommended duration or a dynamics-validated trajectory; acceleration/jerk,
  motor tracking, external obstacles and real hardware were not tested. Large
  unannounced joint rearrangements are unsuitable for automatic VR following.
- Reports: `logs/quality/mink_constrained_endpoint_20260903_s2.json` and
  `logs/quality/mink_constrained_endpoint_fine_20260903_s2.json`. Both complete
  with SAMPLED_DIRECT_PATH_FOUND; contain per-seed solver outcomes, endpoint q,
  invalid path fractions, and refined path-error/excursion metrics.
- Reproduction (offline, from project root):
  `py -3.11 backend/tools/diagnose_mink_collision_feasibility.py logs/quality/mink_consistent_tangent_20260903_102446_s2.json logs/quality/mink_held_endpoint_audit_20260903_102446_s2.json --path-spacing-deg 0.05 --result-json logs/quality/mink_constrained_endpoint_fine_20260903_s2.json`
- Decision: do not deploy this large branch transition into ordinary following.
  Endpoint/path existence for this fixed goal is now established at sampled
  model level. Remaining work is selecting a low-excursion route or a separately
  reviewed reconfiguration behavior, then validating held-out captures and
  performance. No default BAT behavior changed; no user/physical retest needed.
- Verification: all 201 backend tests passed; new Python files compile; held
  start FK merit difference is exactly 0 in the current model. All three Gate 7
  hardware_output_authorized flags remain false. Offline runs are complete.

### 2026-09-03 lower-excursion endpoint and waypoint route comparison

- Extended the existing offline collision-feasibility diagnostic; no production
  IK, Unity, launcher, G1 access, or physical permission changes. Added a
  joint-distance objective (sum of squared unwrapped joint changes in radians)
  with an explicit >=20 mm clearance constraint and unchanged exact 6D pose /
  operational joint bounds. This is a local search, NOT a global optimum claim.
- Reused the twelve earlier endpoints, held q, and five valid solutions as 18
  seeds. Ten converge to the same smaller-movement valid endpoint. Maximum
  joint change drops from 154.311 to 125.279 deg; angular Euclidean displacement
  is 189.822 deg. Final FK pose matches numerically and clearance is 20 mm.
  Every direct path to these smaller-movement endpoints fails immediately near
  the start (fraction 0.001995, distance 19.998287 mm at 0.05-degree sampling).
  The diagnostic correctly does not accept endpoint validity as path validity.
- Added a finite waypoint search using the previously checked path as a source
  of candidate via poses. Fractions tested: 0, .01, .025, .05, .1, .2, .3, .4,
  .5, .6, .7, .8, .9, 1. New connections are screened at .25 deg and accepted
  only after independent .05-degree sampling. Saved endpoint flags are not
  trusted: current model FK pose/clearance and frozen coordinates are rechecked.
- Six waypoint routes pass; the lowest joint-space path length among them uses
  the .5 baseline fraction. Maximum joint excursion is 125.279 deg; summed
  joint-space path length is 194.265 deg versus original 231.602 deg. The latter
  is the sum of Euclidean segment lengths, not the sum of seven joint angles.
- The selected route still reaches 13.874 cm target-position error and 36.713
  deg rotation error along the way; large rearrangement is NOT solved. Minimum
  sampled clearance is 20.000000 mm at the endpoint, leaving no additional
  numerical/model-uncertainty reserve beyond the configured margin. Do not
  interpret this as physical safety or enable an automatic large branch change.
- Velocity-only duration lower bound is 3.132 s versus 3.858 s, but corner
  velocity continuity, acceleration, jerk, torque and dynamics are unvalidated.
  Neither number is an executable or recommended motion duration.
- Results: `logs/quality/mink_minimum_joint_endpoint_20260903_s2.json` and
  `logs/quality/mink_lower_excursion_route_20260903_s2.json`. The latter stores
  selected q_nodes, all tested fractions, leg-level metrics, and provenance.
- Reproduce endpoint optimization using the existing tool with
  `--objective joint-distance --seed-result logs/quality/mink_constrained_endpoint_fine_20260903_s2.json --maxiter 300`.
  Reproduce waypoint search with the same held/endpoint audit inputs and
  `--seed-result logs/quality/mink_constrained_endpoint_fine_20260903_s2.json --shortcut-endpoints logs/quality/mink_minimum_joint_endpoint_20260903_s2.json`.
  Both modes require `--result-json` and perform no robot output.
- Decision: the selected route is smaller but remains unsuitable for seamless
  VR following. Do not describe this as a completed tracking fix, change
  calibration, or silently relax collision limits. Further work must address
  avoiding the bad posture branch earlier or deliberately separating a reviewed
  reconfiguration mode from ordinary following; existing runtime stays unchanged.
- Verification: all 204 backend tests pass, including eight collision-feasibility
  tests; edited Python files compile. Both offline searches completed, and the
  shortcut search was rerun after endpoint revalidation was added. All three
  Gate 7 physical output authorization flags remain false.

### 2026-09-03 preventive redundancy-centering experiment (not deployed)

- Added `nullspace_center` to the existing offline step-acceptance comparison.
  It uses the consistent_tangent tasks/guards, then minimizes normalized joint
  distance from each operational range midpoint in the wrist Jacobian's 1D
  nullspace. The scalar adjustment is bounded by the existing QP inequalities.
  No future recorded targets enter this calculation. This preserves the linear
  wrist increment only, NOT exact finite-step pose; existing merit/backtracking
  and four intermediate FK geometry checks still decide acceptance.
- Rank deficiency or invalid constraints retain the primary solution. Invalid
  centered velocity or rejected finite steps fall back to the primary IK path.
  No velocity/geometry limit was relaxed. Added tests for first-order invariance,
  frozen DOFs, constraint satisfaction, normalized-cost reduction, invalid/rank
  fallback, and primary-step fallback. Trace rows now include right-arm q and
  joint-limit margins; summaries measure time spent within 5 degrees of limits.
- Replay of all three 102446 capture segments completed. After a 6-second final
  target hold, position/rotation errors were 0.0482 cm/0.0043 deg, 0.2708 cm/
  0.0799 deg, and 0.0245 cm/0.0193 deg. Minimum sampled clearance across all
  recorded/hold/return phases was 20.3254 mm. These are fixed-dt kinematic replay
  observations, not real-time performance or physical safety validation.
- Segment 2 improves from consistent_tangent's held 3.0498 cm/16.8426 deg, but
  moving position p95 is 9.6814 cm versus 9.6428 cm: NOT an overall tracking fix.
  The candidate still has a 140.10 deg/s adjacent-frame velocity change there;
  40/100 deg/s speed caps alone do not establish smooth acceleration or jerk.
- Added `--wrist-only` FK-generated cycles from the existing regression posture
  [10,-22,0,55,0,0,0] deg, one wrist axis at a time, +/-25 deg over 12 seconds.
  These are explicitly labeled synthetic inputs, NOT Quest capture motions.
  For wrist roll, maximum proximal excursion grows from 0.0632 to 14.1247 deg;
  for wrist pitch it grows from 0.00481 to 1.3381 deg; for wrist yaw it grows
  from 0.0188 to 6.6521 deg. All six synthetic runs completed. Small wrist error alone
  therefore hides unwanted shoulder/elbow reconfiguration.
- Decision: reject unconditional midpoint centering for production. Do not
  insert it into the active planner, change calibration, or ask for hardware
  authorization based on this result. A later candidate must preserve the
  existing wrist-only quiet-proximal behavior while addressing limit approach;
  any selective assistance needs the same full replay and wrist-only checks.
- Reports: `logs/quality/mink_nullspace_center_20260903_all.json` and
  `logs/quality/mink_nullspace_wrist_cycles_20260903.json`, with per-step JSONL
  traces and console logs alongside. Use `--variants nullspace_center` with the
  102446 review snapshot for capture replay; add `--wrist-only --variants
  consistent_tangent nullspace_center` for the separate synthetic comparison.
  All runs require an explicit `--result-json` path. The capture hash retained
  in a synthetic report is provenance only, not its generated target source.
- Verification: 210 backend tests pass; modified Python files compile. All
  three Gate 7 hardware authorization flags remain false. Production IK,
  Unity, launchers and G1-side files were not changed in this experiment.

### 2026-09-03 selective near-limit assistance candidate (offline only)

- Added `limit_avoidance` to `backend/tools/compare_mink_step_acceptance.py`.
  Unlike rejected unconditional midpoint centering, the 1D nullspace objective
  penalizes only intrusion into an 18-degree joint-limit band. It minimizes
  squared distance outside the inner band, selecting the nearest minimizer to
  zero within the existing QP interval. The 18-degree value reuses the current
  wrist assistance entry setting, but applying it to all seven joints is an
  experimental policy, NOT an optimized or physically validated safety margin.
- Far from limits there is no midpoint attraction. Targets/calibration remain
  unchanged, no future input is read, and all previous speed/geometry/merit
  checks and primary-solution fallbacks remain. Nullspace invariance is still
  only first order; finite-step FK geometry checks are required.
- Initial v4 implementation rejected intervals not containing exactly zero.
  QP numerical residuals can produce a tiny strictly positive/negative feasible
  interval; skipping it suppressed assistance. Fixed v5 to start at the feasible
  point closest to zero and solve WITHIN that interval, without expanding any
  bound. Truly empty intervals and material primary infeasibility still fall
  back. Tests cover positive/negative intervals, closest-boundary rather than
  midpoint motion, conflicting limits, inactive parity, and active Jacobian /
  inequality / frozen-DOF preservation. Keep v4 reports as diagnostic evidence.
- v5 all-three-segment replay completed for the 102446 review snapshot. Final
  position/rotation errors after the 6-second hold: 0.0481 cm/0.0069 deg,
  0.2708 cm/0.0799 deg, 0.0245 cm/0.0193 deg. Minimum sampled clearance across
  all phases: 20.3190 mm, unchanged 20 mm guard and 40/100 deg/s caps.
- Segment 2 held error falls from consistent_tangent's 3.0498 cm/16.8426 deg
  to 0.2708 cm/0.0799 deg. In the moving phase, 28 nontrivial near-limit
  corrections were accepted; wrist-roll minimum margin is 17.62 deg, rather
  than reaching its limit. Elbow still reaches its operational limit during
  part of the motion, so do NOT claim all joint limits are avoided.
- Moving target error remains: segment 2 position p95 is 9.6873 cm versus
  baseline 9.6428 cm. Adjacent-frame velocity change reaches 139.93 deg/s.
  Therefore these results establish an improved held-goal outcome for this
  capture, NOT universal tracking improvement, smooth dynamics or hardware
  readiness. Do not add a blind post-IK filter that invalidates collision checks.
- Reports: `logs/quality/mink_selective_limit_v5_20260903_all.json` and separate
  segment-2 reproduction `logs/quality/mink_selective_limit_v5_20260903_s2.json`.
  Reproduce with the 102446 capture and `--variants limit_avoidance --result-json
  <local-report.json>`; use `--wrist-only` for the synthetic FK cycles. Per-step
  traces and console logs are stored alongside the report. This remains an
  opt-in offline comparison; default variants and every production BAT are
  unchanged. No G1-side access or physical publisher was used.
- Verification: 214 backend tests passed and both changed Python files compile.
  All three Gate 7 hardware authorization flags remain false. Active Unity,
  IK controller, hardware bridge and Startup Recovery remain unchanged.
- All three v5 wrist-only cycles also completed:
  `logs/quality/mink_selective_limit_v5_wrist_20260903.json`. Maximum proximal
  excursions are roll 0.063186 deg, pitch 0.004810 deg, yaw 0.018796 deg, equal
  to consistent_tangent baseline within 1e-8 deg. Each cycle meets the existing
  <0.5 deg proximal / <0.1 cm position-p95 / <0.5 deg rotation-p95 criteria.
  Both report sets were checked for unchanged sampled-clearance and velocity
  bounds; capture replay frozen-DOF velocity was also checked below 1e-7 rad/s.
- Decision: retain selective v5 as a promising offline candidate, not a default
  runtime replacement. The neutral-pose wrist-only regression is resolved for
  these tests; arbitrary near-limit wrist motions are not yet covered. Next
  validation needs a separate capture and the actual stateful, rate-limited
  simulation loop, checking both transient motion and geometry after any speed
  smoothing. No additional user physical trial is needed at this checkpoint.

### 2026-09-03 lookahead validation and collision-distance blocker

- Continued the selective candidate OFFLINE ONLY. Added opt-in
  `--horizon-steps 3` to `backend/tools/compare_mink_step_acceptance.py`:
  execute only the first accepted step, predict the remaining steps at the
  current target, then restore actual-step hysteresis and orientation cost.
  Tests compare the baseline adapter with production `FeasibleTargetPlanner.Plan`;
  this is not a full Unity/network/watchdog runtime test.
- Independent capture 101314 (378 packets) shows held position error 0.2605 cm
  for both baseline and selective candidate, with rotation about 0.0251 deg.
  Report: `logs/quality/mink_selective_limit_holdout_101314.json`.
- Hard segment 2, 1756 frames: three-step lookahead preserves actual executed
  joint values exactly versus v5 first-step replay. Held error remains
  0.2708 cm / 0.0799 deg. Reports:
  `logs/quality/mink_selective_runtime_h3_102446_s2.json` and
  `logs/quality/mink_selective_runtime_h3_holdout_101314.json`.
  Diagnostic planning p95 was about 94-102 ms, including extensive geometry
  audits and concurrent load. This is NOT a production benchmark or evidence
  of meeting the 60 Hz budget.
- IMPORTANT: independent reconstruction of preview frame 864 (t=14.4 s)
  contradicted the replay's internal clearance result. Therefore the earlier
  logged positive clearances are NOT independent collision-safety validation.
  Do not deploy this candidate on the strength of those clearance metrics.
- Reran with full actual/preview qpos and model hash recorded:
  `logs/quality/mink_selective_runtime_h3_fullstate_102446_s2.json` and its
  `_s2_limit_avoidance.jsonl` trace. Exact saved qpos gives consistent positive
  pair distance. Reconstructing frozen coordinates changes q by at most
  2.9186e-14, yet the shoulder-yaw / wrist-pitch mesh pair becomes inconsistent.
- Added `backend/tools/diagnose_mink_distance_invariance.py`. For canonical
  frozen qpos, global x translation of +/-1e-12 m changes the guard distance
  from -76.4004 mm to +76.4004 mm. Raw MuJoCo distance also alternates between
  zero and positive distance. Vertex projection yields a positive separating
  gap even at the negatively classified pose. This is an observed numerical
  inconsistency, not a verified upstream bug diagnosis or a physical contact.
  Existing zero-distance joint-perturbation fallback can propagate an erroneous
  negative probe. Do not bypass it by taking absolute values, choosing the
  largest positive distance, or weakening clearance requirements.
- Durable reproducer, MuJoCo 3.11.0:
  `py -3.11 backend/tools/diagnose_mink_distance_invariance.py
  logs/quality/g1_mink_capture_20260903_102446_review_snapshot.jsonl
  logs/quality/mink_selective_runtime_h3_fullstate_102446_s2_s2_limit_avoidance.jsonl
  --result-json logs/quality/mink_distance_invariance_20260903_s2_frame864.json`
  (Run as one command.) Report status is `BLOCK_DEPLOYMENT`.
  Canonical pose fails invariance; exact saved pose has no inconsistency in
  this small perturbation test. A support gap is only evidence for the tested
  mesh convex hull pair, not whole-robot or real-world safety certification.
- Next priority: validate a reliable collision-distance/geometry consistency
  approach against this reproducer and genuine contact cases, before deploying
  the candidate or tuning further smoothing. Production IK, Unity, launchers,
  Startup Recovery and G1 files remain unchanged; no physical publisher or G1
  access was used. All three Gate 7 authorization flags were rechecked false.
- Verification: all 222 backend unit tests pass (58.194 s), including new
  lookahead-state and distance-diagnostic tests. Four changed Python files
  compile. Test log: `logs/quality/backend_tests_distance_invariance.txt`.
  Passing detector tests do NOT mean the collision inconsistency is fixed.

### 2026-09-03 independent separation check and isolated MuJoCo 3.12 comparison

- Extended the existing distance diagnostic with `GetSeparationCertificate`:
  support projections of the compiled mesh vertices, or conservative enclosing
  boxes for primitive geoms, produce a LOWER bound, not an exact distance.
  Only a bound exceeding 20 mm plus a numerical reserve certifies this sampled
  pair. Missing separating directions mean UNRESOLVED, never collision and
  never permission to move. Unknown geometry and invalid inputs fail closed.
  This is OFFLINE only; neither QP normals nor production guards use it.
- Added contact, penetration, insufficient-clearance, rotated-box (150 seeded
  cases), shared-point-hull (200 seeded cases), invalid-input and compiled
  geometry tests. The analytic mesh-box cases also check native signed distances
  for overlap, touching and separation. No negative distance is replaced by its
  absolute value, and no collision pair or required clearance was removed.
- `--scan-stride 1` checks every canonical PREVIEW ENDPOINT in a saved trace;
  it does not check intervening swept paths, actual feedback, or unregistered
  body pairs. `--geom-pair <name> <name>` pins the same pair across engine
  versions, rather than accidentally testing each engine's different nearest
  pair. The original reproducer is now independently separated by at least
  74.4667 mm in all seven global-translation perturbations.
- Upstream investigation found the related official issue and fix:
  https://github.com/google-deepmind/mujoco/issues/3383
  https://github.com/google-deepmind/mujoco/commit/35342f403fdc0370df7f3b4dea8c97ff547e7f1b
  GitHub compare confirms the fix is after tag 3.11.0 and included in 3.12.0.
  It adds a final separation check after early GJK exit. The docs discourage
  using legacy libccd for distance queries, so that was not adopted:
  https://mujoco.readthedocs.io/en/latest/computation/#geom-distance
- Installed official PyPI `mujoco==3.12.0` with `--no-deps --only-binary=:all:`
  into `logs/offline_dependencies/mujoco312`. No global upgrade and no changes
  to BATs, Unity, production IK source, robot files, or hardware authorization.
  Select it only in a temporary shell with
  `$env:PYTHONPATH="$PWD\logs\offline_dependencies\mujoco312"`.
  A new ordinary shell still imports MuJoCo 3.11.0 from Python311 site-packages.
- Same pinned shoulder-yaw/wrist-pitch pair, same saved trace and model XML:
  3.12.0 returns +76.4004 mm for BOTH exact saved and canonical frozen poses,
  consistently under all seven translation perturbations (span < 5e-17 m).
  Report: `logs/quality/mink_distance_invariance_312_20260903_frame864.json`.
  This resolves that particular native-distance reproducer, not all tracking
  problems or all contact cases. Do not treat an upstream fix as hardware approval.
- An older unit test required this class of separated pose to return exactly
  zero. Updated it to also accept the measured corrected ~39.99645 mm distance
  within 1 micrometer, retaining strict geometric bounds. A separate mock test
  now checks both zero fallback and exact-contact preservation independently
  of whether the installed engine still exhibits the old defect.
- Both default 3.11.0 and isolated 3.12.0 pass all 230 backend tests after that
  compatibility correction. Analytic mesh-contact tests separately pass on
  both engines. Logs: `logs/quality/backend_tests_separation_certificate.txt`
  and `logs/quality/backend_tests_separation_certificate_312.txt`.
- Re-solved independent capture 101314 under isolated 3.12.0 with unchanged
  `limit_avoidance` settings and horizon 1:
  `logs/quality/mink_selective_limit_312_holdout_20260903.json`.
  Held error is 0.2604645 cm / 0.0251130 deg, essentially unchanged from 3.11.
  Recorded-phase position p95 8.5778 cm and rotation p95 49.1967 deg remain;
  the engine fix is NOT an end-to-end tracking/smoothness fix. This replay's
  internally measured minimum clearance is 20.4735 mm. The new independent
  endpoint scan applies to the earlier hard-segment trace, not this new path.
- Full matched endpoint comparison completed: 1756 frames x 243 registered
  pairs = 426708 queries. Model XML, trace and capture hashes match across
  engines. Reports:
  `logs/quality/mink_separation_certificate_20260903_all_frames.json` (3.11)
  and `logs/quality/mink_separation_certificate_312_20260903_all_frames.json`.
  3.11: 169 raw-distance/lower-bound contradictions; 426692 pair endpoints
  certified and 16 unresolved. The unresolved results are NOT proof of contact.
  3.12: zero contradictions, all 426708 pair endpoints certified; minimum
  conservative bound 20.437844 mm. Elapsed audit time was 351 s versus 323 s,
  under concurrent work, NOT a real-time performance comparison.
- Decision: the observed engine-distance blocker is resolved on this matched
  dataset by isolated 3.12.0, without relaxing collision geometry or margins.
  Keep report state REVIEW_REQUIRED: sampled preview endpoints do not certify
  swept trajectories, dynamic tracking, missing geometry, or physical motion.
  Next step is to rerun the difficult segment's IK solve and wrist-only motion
  checks on isolated 3.12.0 before changing the simulation default. Do not
  deploy a custom separation-distance/normal fallback merely because its audit
  succeeds; prefer evaluating the upstream engine fix first.
- Production remains MuJoCo 3.11.0; all three Gate 7 hardware locks remain false.
  Three changed Python files compile; diff whitespace checks pass. No G1-side
  access or command publisher was used. Active source paths and launchers were
  not modified; tests may regenerate their existing local generated model XML.

### 2026-09-03 re-solved difficult segment on isolated MuJoCo 3.12

- Re-solved capture 102446 segment 2 using the unchanged offline
  `limit_avoidance` candidate with three-step lookahead. Production IK, Unity,
  BATs, default Python packages and hardware locks are unchanged. This is a
  new IK solve, not replaying the old joint values into the new engine.
- Report: `logs/quality/mink_selective_312_h3_hard_20260903.json`, with
  `_s2_limit_avoidance.jsonl` full-state trace and `.log` alongside.
  Relative to the 3.11 full-state trace, all 1756 frames match within
  9.24074e-8 rad (0.000005295 deg) in the seven executed joint values.
- Held position/rotation error: 0.2708402 cm / 0.0798729 deg. Return position
  error: 0.000065315 cm. No sustained error-stall detected by this diagnostic.
  Internally sampled minimum clearance: 20.438432 mm for actual and preview
  checks. Maximum frozen-DOF velocity: 5.943e-13 rad/s.
- Limits retained: shoulder/elbow 40 deg/s, wrist 100 deg/s, original geometry
  pairs, operational joint bounds and 20 mm guard. Elbow is within five degrees
  of its operational limit for 5.1833 s and reaches the bound; this is NOT
  removed by the engine fix. Recorded position/rotation p95 remain
  9.6873 cm / 14.2044 deg. Adjacent-frame joint velocity change reaches
  139.9333 deg/s. Do not claim smoothness, 1:1 moving-hand tracking, or hardware
  readiness from the accurate held pose.
- Planning p95 is 58.13 ms in this audit-heavy concurrent run, not a production
  timing result. Full real-time Unity/network behavior remains unverified.
- Re-solved all three 12-second, +/-25-degree FK wrist cycles plus hold/return
  on 3.12.0, comparing `consistent_tangent` and `limit_avoidance`:
  `logs/quality/mink_selective_312_wrist_20260903.json` and per-cycle traces.
  Maximum proximal (shoulder/elbow) excursions: roll 0.06318627 deg,
  pitch 0.00481021 deg, yaw 0.01879617 deg. These match the baseline and
  previous 3.11 results; selective assistance does not introduce midpoint
  attraction on these neutral-pose cycles. Position p95 stays below 0.032284 cm,
  rotation p95 below 0.402388 deg, and sampled clearance above 40.35 mm.
  Arbitrary near-limit wrist-only cycles remain outside this test set.
- Saved explicit result checks to `logs/quality/mink_312_replay_contract_20260903.json`:
  215 checks pass, covering source engine/model, expected cycles/horizon,
  held-error regression, wrist quietness and baseline parity, reported joint
  bounds, frozen DOFs, 40/100 deg/s caps and sampled 20 mm clearance.
  The 0.271 cm / 0.081 deg held-error checks are tolerances around the prior
  result, not universal accuracy requirements. This contract report is not
  swept-path or physical safety approval.
- Fresh full backend suite on isolated 3.12.0: 230 tests pass (50.446 s).
  Log: `logs/quality/backend_tests_mujoco312_replay_20260903.txt`.
- Independent endpoint audit of the NEWLY SOLVED 3.12 trace completed:
  `logs/quality/mink_selective_312_h3_hard_certificate_20260903.json`.
  Trace hash matches the new `_s2_limit_avoidance.jsonl`, not the older 3.11
  trace. All 1756 x 243 = 426708 registered-pair preview endpoints have a
  conservative separation bound >= 20 mm; minimum is 20.437845 mm. There are
  zero distance contradictions and zero unresolved endpoint cases. Both exact
  and canonical frozen frame-864 perturbation checks are consistent. Audit
  time was 336.47 s, not control-loop performance.
- Decision: this offline engine/candidate regression checkpoint passes.
  Do not infer continuous swept-path, dynamic, real-time, or hardware approval.
  Default runtime remains 3.11.0 and the experimental candidate remains opt-in.
  Next useful step is an isolated runtime-cost benchmark using the same target
  stream and planner without diagnostic audit overhead, then simulation-only
  integration if the timing and behavior pass. Do not blindly add post-IK
  smoothing, widen bounds or change hardware output to make this pass.
  All three Gate 7 authorization flags were rechecked false; no G1 was accessed.

### 2026-09-03 planner-only runtime cost and exact-parity optimization

- Added `backend/tools/benchmark_mink_candidate.py` for the isolated 3.12.0
  selective candidate, with 30 untimed warmup steps and two sequential full
  hard-segment repeats. No rendering, UDP, SDK, pacing, physical dynamics or
  robot command occurs. No other offline Python test was running during the
  timed repeats; ordinary desktop background activity is not controlled.
- Added opt-in `diagnostic_geometry=False` to the experimental comparison
  functions; default remains True, preserving existing audits. This skips
  geometry diagnostics only for candidates already rejected by the required
  merit test, as the production planner already does. Accepted candidates
  still undergo all four intermediate configuration/collision checks, with
  unchanged QP, limits, clearance and fallback rules. Undiagnosed holds are
  labeled `no_accepted_step`, not falsely classified as collision or merit-only.
- The benchmark optionally caches only the last EXACT full qpos clearance
  query for its immutable model. Copies prevent input aliasing; different q,
  failed query or NaN invalidates reuse. This is not a time-based cache and
  is not suitable for mutable geometry or hardware feedback without further
  design. The cache and skipped diagnostics are NOT used by production.
- Reference: `logs/quality/mink_selective_312_h3_hard_20260903.json` and its
  full trace. Capture/model/engine/horizon are checked before benchmarking.
  Both repeats match all 1756 actual qpos and preview qpos exactly (max error
  0.0), and accepted-step counts also match exactly. Thus this optimization
  has not changed the tested path or invalidated its prior endpoint audit.
- Timing report: `logs/quality/mink_candidate_runtime_cost_20260903.json`.
  Repeat 1: mean 10.280 ms, p95 16.715 ms, p99 18.772 ms, max 21.652 ms;
  95/1756 frames (5.410%) exceed the 60 Hz budget of 16.667 ms.
  Repeat 2: mean 8.642 ms, p95 14.191 ms, p99 16.552 ms, max 19.456 ms;
  16/1756 frames (0.911%) exceed budget. Recorded moving-phase miss rates are
  8.108% and 1.544%. Do not hide these by quoting only the mean or p95.
  Each repeat reused 20006 identical clearance queries and performed 15961.
- Decision is `DEADLINE_MISSES`, NOT real-time ready. Full application adds
  further work and OS scheduling; even zero misses here would not certify it.
- Separate cProfile run preserved trajectory parity, but its instrumented
  timings are not comparable to the normal benchmark. Saved
  `logs/quality/mink_candidate_runtime_20260903.prof` and
  `logs/quality/mink_candidate_profile_instrumented_20260903.json`.
  Including warmup, 6,161,720 mj_geomDistance calls consumed 7.904 s self time;
  guard nearest-pair calculation consumed 9.777 s cumulative, solve_ik 5.725 s
  and CenterRedundancy 5.683 s (nested times overlap, do not add them).
- Next: reduce redundant distance/constraint work with exact trajectory and
  accepted-path check parity before any simulation default integration. Do
  not remove collision pairs, weaken clearance or slow the loop merely to
  relabel this benchmark successful. Production and all hardware locks remain
  unchanged; default MuJoCo remains 3.11.0.
- Verification: all 235 backend unit tests passed in 46.637 s under isolated
  MuJoCo 3.12.0; the three changed Python modules passed compilation. The
  three hardware authorization flags were rechecked false, and default
  Python still imports MuJoCo 3.11.0. Repository-wide whitespace checking
  reports existing trailing spaces in SampleScene.unity at lines 282, 398
  and 419; that unrelated Unity scene was not edited in this benchmark work.

### 2026-09-03 conservative clearance broadphase benchmark

- Added opt-in `--broadphase` to the existing offline benchmark, not to the
  runtime planner. `BoundedClearance` uses compiled `geom_rbound` spheres and
  world `geom_xpos`, following the sphere-filter principle inspected in the
  installed Mink `CollisionAvoidanceLimit._broadphase_survivors` source.
- Only supported finite positive-radius shapes may be rejected, and only
  when their enclosing spheres are farther apart than the unchanged 0.20 m
  distance-query cutoff plus 1e-9 m. Planes, unsupported/invalid bounds and
  boundary cases remain in narrow phase. Pair order and robust distance
  handling remain unchanged. This assumes immutable model geometry.
- No collision pairs were removed from the policy. The QP, clearance,
  intermediate four-sample checks, velocity limits and objective are unchanged.
  The new filter saves narrow-phase calls for pairs proven beyond the cutoff;
  it is not an approximation to the minimum clearance within that cutoff.
- Tests cover sphere contact/penetration/cutoff, planes, invalid radius and
  64 seeded full-body G1 poses including penetration. A separate full-trace
  audit compared actual and preview clearance against all 243 pairs at each
  of 3512 states: zero mismatches, minimum 0.0204384324 m. Audit artifact:
  `logs/quality/mink_broadphase_trace_audit_20260903.json`.
- Benchmark: `logs/quality/mink_candidate_broadphase_cost_20260903.json`.
  Each of two 1756-frame repeats exactly matched reference actual qpos,
  preview qpos and accepted-step counts. Per repeat, 3,120,546 of 3,878,523
  guard pair evaluations were skipped (80.46%); 757,977 remained. These are
  guard pair counts, not total engine calls or total planner time reduction.
- Repeat 1: mean 7.868 ms, p95 12.502 ms, p99 14.014 ms, max 15.853 ms,
  zero frames above the 16.667 ms budget. Repeat 2: mean 7.818 ms,
  p95 12.683 ms, p99 14.582 ms, max 21.170 ms; 3/1756 frames (0.171%)
  exceeded budget. Earlier unfiltered repeats missed 95 and 16 frames.
  Desktop load was not controlled; do not attribute all timing differences
  to this change. The deterministic saved pair counts are the stronger proof
  of reduced work. Report remains DEADLINE_MISSES, not real-time approval.
- Next candidate: inspect repeated collision-QP constraint computation at
  the same configuration in solve_ik and CenterRedundancy. Validate exact
  constraint/trajectory parity before any integration; do not weaken limits.
- This turn changed only the offline benchmark, its tests and this record.
  Default MuJoCo remains 3.11.0; experiments use isolated 3.12.0. All three
  hardware authorization flags remain false. No G1 or physical output used.
- Verification: all 237 backend tests passed under isolated MuJoCo 3.12.0
  (46.258 s), both edited Python files compiled, and scoped diff whitespace
  checking passed. Test log: `logs/quality/backend_tests_broadphase_20260903.txt`.

### 2026-09-03 exact-state collision constraint reuse

- Inspected the installed Mink build_ik path and experimental CenterRedundancy:
  both query collision inequalities at the same configuration and timestep.
  Added benchmark-only `--constraint-cache` with CachedCollisionLimit, a
  ResolvedCollisionLimit subclass; default remains uncached and no runtime
  planner/Unity/launcher/hardware profile was changed.
- Reuse requires the same configuration object, exact full qpos bytes,
  mocap position/quaternion bytes, dt, gain, collision minimum/detection
  distances, relaxation, broadphase settings and reserve-recovery setting.
  Model geometry and collision pairs MUST remain immutable. Caller-modifiable
  G/h arrays are copied both into and out of the cache. A miss invalidates
  the old key before calculation; exceptions, nonfinite G, NaN/negative-inf h
  do not populate it. Positive-inf inactive bounds remain valid.
- Focused tests cover exact input invalidation, mutation isolation, failed
  queries, invalid dt, mocap changes/configuration identity and 32 seeded
  G1 poses comparing fresh/cached G/h matrices exactly.
- Full trace matrix audit: 3512 actual/preview states, 7024 comparisons of
  cached and uncached G/h, zero mismatches (including inactive rows).
  `logs/quality/mink_constraint_cache_trace_audit_20260903.json`.
- Two full 1756-frame repeats with clearance broadphase and both caches
  matched reference actual qpos, preview qpos and accepted steps exactly.
  Each repeat reused 5274 collision constraints and recomputed 3688 out of
  8962 requests, saving 58.85% of these computations. Guard pair queries
  remain 757977, with 3120546 sphere rejections; all four accepted-path
  samples, collision bounds, velocity limits and objectives remain intact.
- `logs/quality/mink_candidate_constraint_cache_cost_20260903.json`:
  repeat 1 mean 6.580 ms, p95 10.848 ms, p99 12.459 ms, max 14.016 ms;
  repeat 2 mean 6.668 ms, p95 11.741 ms, p99 13.469 ms, max 18.5145 ms.
  60 Hz budget misses were respectively 0 and 1/1756 (0.05695%). The latter
  occurred in the recorded moving phase. Desktop background load is not
  controlled, so this is not a hard real-time guarantee or causal speedup
  measurement; exact saved computations and matrix/path parity are stronger
  evidence. Status remains DEADLINE_MISSES; no hardware approval follows.
- Next useful check is a longer, paced simulation-only experiment measuring
  scheduling and rendering overhead in addition to planner time. Keep the
  default launchers untouched and report stalls, tracking error and collision
  decisions rather than declaring success from mean latency alone.
- Verification: 241 backend tests passed in 27.520 s under isolated MuJoCo
  3.12.0; both edited Python files compiled and scoped whitespace check passed.
  Test log: `logs/quality/backend_tests_constraint_cache_20260903.txt`.
  Default import remains 3.11.0 and all three hardware authorization flags
  were rechecked false. No G1 access or physical publisher occurred.

### 2026-09-03 paced offscreen-render replay load test

- Added `backend/tools/benchmark_mink_rendered_replay.py`, reusing the
  experimental cached/broadphase candidate without changing default launchers.
  Verified the same capture/model/engine/horizon before loading the reference.
  It performs fixed-step IK, MuJoCo GPU rendering/readback at 640x480 EVERY
  frame, pixel checks, tracking diagnostics and real-time pacing on one thread.
  Inspection props are hidden only in the render scene; geometry/collision
  policy is unchanged. No mj_step dynamics, network, DDS, Unity or Quest runs.
- Next release is previous ACTUAL start + 1/60 s. No catch-up bursts or dropped
  input frames; an overrun slows replay, which is explicitly measured. This
  is NOT live-input freshness handling. Repeats reset to the original q and
  re-warm the planner/renderer; reset jumps are not validated transitions.
  PNG writes, initialization and 30 warmup frames per repeat are excluded.
- Five repeats completed: 8780 measured frames, nominal 146.333 s, measured
  loop time 149.858 s. Each repeat exactly matches reference executed qpos,
  preview qpos and accepted-step counts. Each makes 19479 configuration
  checks (no rejected tested sample); minimum sampled path clearance is
  20.4384324 mm. This is not continuous swept-volume/dynamic certification.
- Work-only deadline misses: 130, 79, 19, 96, 147 (471/8780 = 5.36%).
  Release-to-finish misses, INCLUDING scheduler wake lateness: 187, 112, 25,
  138, 200 (662/8780 = 7.54%). Maximum work time 31.291 ms. Mean work by
  repeat: 11.757, 11.120, 10.683, 11.548, 11.749 ms; mean renderer time
  2.947-3.339 ms. Minimum actual start interval across repeats 16.6679 ms,
  so there was no compressed catch-up. Wall-minus-nominal per repeat was
  0.621-0.771 s. Desktop background load is uncontrolled.
- Tracking is unchanged, NOT fixed by faster computation. Recorded moving
  phase position p95 9.687 cm, max 10.650 cm; rotation p95 14.204 deg,
  max 23.378 deg. Hold endpoint error 0.270840 cm / 0.079873 deg. No stall
  meeting the diagnostic definition (all joint speeds below 0.1 deg/s with
  position error >1 cm or rotation error >5 deg). Adjacent-frame velocity
  change still reaches 139.933 deg/s; no claim of smooth physical motion.
- Report: `logs/quality/mink_rendered_paced_20260903.json`, plus matching log
  and 20 PNGs. Pixel checks found nonblank/changing frames in all repeats;
  manually viewed the initial smoke render and r1_f585 snapshot to verify
  G1 framing and arm display. This does NOT verify a VR headset or Unity UI.
- Decision: DEADLINE_MISSES. Do not change production defaults or unlock
  hardware. Next experiment should decouple rendering from the IK loop
  using bounded latest-state delivery, reflecting the existing separation
  between backend and Unity. Measure missed deadlines and state age; do not
  conclude the actual separated application has this single-thread result.
- Verification: 243 backend tests passed in 49.364 s under isolated MuJoCo
  3.12.0, including positive-only sleeps and no compressed catch-up tests.
  New/edited Python files compiled. Test log:
  `logs/quality/backend_tests_rendered_pacing_20260903.txt`.
  Default engine remains 3.11.0, all three hardware authorization flags
  remain false, and no G1 access or physical command occurred.

### 2026-09-03 decoupled offline rendering and renderer-stall injection

- Added `backend/tools/offline_render_worker.py` and opt-in
  `--decoupled-render` on the rendered benchmark. IK stays in the parent;
  a spawned process owns its own MuJoCo model/data/OpenGL context. No existing
  launcher, Unity script, IK policy, hardware profile or G1 file changed.
- LatestStateSlot contains exactly one full qpos + goal + preview snapshot,
  sequence and publication timestamp. Both sides use a nonblocking lock;
  writes/reads are coherent copies. Busy producer attempts drop DISPLAY
  updates only, never IK input steps. Slow consumers skip superseded display
  states. The report distinguishes skipped sequences and producer lock drops.
  No unbounded queue or catch-up replay is used. This local shared-memory
  experiment is not the production UDP transport.
- Renderer readiness, exit and final report are checked; each owned child is
  joined/closed, with bounded cleanup on failure. Each displayed full qpos is
  compared exactly against the reference frame selected by sequence.
- Normal test: `logs/quality/mink_decoupled_render_20260903.json` and log.
  Five repeats, 8780 IK frames, 8779 rendered snapshots. All executed/preview
  qpos and accepted steps match; all displayed qpos also match. One display
  update was dropped due to the nonblocking lock; all final states arrived.
  Images were nonblank/changing; r1_s440 was manually inspected for G1 framing.
- Work-only 60 Hz misses: 1, 5, 2, 3, 4 = 15/8780 (0.171%). Including
  scheduler wake lateness: 6, 8, 5, 3, 6 = 28/8780 (0.319%). The previous
  single-thread test was 662/8780 (7.54%) by this latter measure. Background
  desktop load was not controlled; this is an observed comparison, not a
  causal or hard real-time guarantee. Work mean by repeat 8.394, 8.346,
  8.274, 8.133, 8.566 ms; max 25.333 ms. Loop wall time totals 149.543 s
  for 146.333 s nominal replay. No compressed control interval was measured.
- Publication-to-render-completion state age p95 is 5.478-6.043 ms across
  normal repeats, maximum 11.144 ms. This begins AFTER IK and ends at
  offscreen readback, not at Quest sampling or headset/monitor display.
  No normal frame exceeded the diagnostic 50 ms stale threshold.
- Fault injection: `logs/quality/mink_decoupled_render_stall_20260903.json`.
  Added an 80 ms renderer-only sleep every 120 displayed states, 14 times.
  All 1756 IK frames preserved the reference path; control work max 16.756 ms,
  work misses 1, release-to-finish misses 2. Renderer displayed 1707 states,
  skipped 49 (including one producer lock drop), and received final seq 1756.
  All displayed qpos still matched. Injected frames aged up to 86.766 ms;
  the next post-stall frames aged 3.028-20.569 ms, so stale history did not
  accumulate. Display latency during the injected stall still exists.
  The worker hash and post-stall-age diagnostics were added between the
  normal and fault-injection runs; these do not alter the control loop.
- Final result classification also checks display age: a fast controller
  cannot produce PACED_RENDER_BUDGET_MET if renderer age exceeds its 16.667 ms
  diagnostic budget. Both measured reports remain DEADLINE_MISSES due to
  control timing; neither authorizes integration or physical output.
- Clearance and tracking are unchanged: minimum sampled clearance 20.438 mm,
  moving-phase wrist position p95 9.687 cm. Next useful work is to separate
  speed-limited tracking lag from IK/operational-bound error using the same
  recorded targets, without relaxing collision constraints or changing the
  default execution path. Timing optimization has not solved hand alignment.
- Verification: 247 backend tests passed in 47.924 s under isolated MuJoCo
  3.12.0; new/edited Python files compiled and scoped whitespace check passed.
  Tests include single-slot coalescing, coherent copy isolation, nonblocking
  lock contention, invalid payload rejection and stale-display classification.
  Log: `logs/quality/backend_tests_decoupled_render_final_20260903.txt`.
  Default MuJoCo remains 3.11.0 and all three hardware authorization flags
  were rechecked false. No G1 access or physical publisher was used.

### 2026-09-03 tracking lag versus unreachable captured goals

- Added `backend/tools/diagnose_mink_tracking_lag.py` and four regression
  tests in `backend/tests/test_mink_tracking_lag.py`. This is an offline
  diagnostic, not a production IK change. Same optimized candidate, horizon
  3, fixed 1/60 s solver dt, 40/100 deg/s caps, operational joint bounds and
  sampled collision checks. No G1 access, SDK publisher or hardware unlock.
- Inputs: segment 2 of
  `logs/quality/g1_mink_capture_20260903_102446_review_snapshot.jsonl` and
  `logs/quality/mink_selective_312_h3_hard_20260903.json`.
  Model/capture/engine identity is checked by LoadReplay. The 1x executed
  qpos path matched the 1756-frame reference exactly, with identical
  accepted lookahead counts. Two frozen-target tests reconstructed their
  entire prefixes to preserve policy state and also matched qpos exactly.
- Reproduce with isolated MuJoCo 3.12.0 (default installation stays 3.11.0):
  `$env:PYTHONPATH="$PWD\logs\offline_dependencies\mujoco312"`, then
  `py -3.11 backend/tools/diagnose_mink_tracking_lag.py logs/quality/g1_mink_capture_20260903_102446_review_snapshot.jsonl logs/quality/mink_selective_312_h3_hard_20260903.json --result-json logs/quality/mink_tracking_lag_20260903.json`.
- Report and log: `logs/quality/mink_tracking_lag_20260903.json` / `.log`.
  Five sibling JSONL traces preserve qpos, targets, decisions and margins.
  Replay stretches input time only (1x, 0.5x, 0.25x); robot speed limits do
  NOT change. Each speed also has a 6 s final hold and 6 s inward return.

| Input speed | Position p95 cm | Rotation p95 deg | Inside reach upper bound position p95 cm |
| --- | --- | --- | --- |
| 1x | 9.687 | 14.204 | 6.262 |
| 0.5x | 9.638 | 6.198 | 2.954 |
| 0.25x | 9.641 | 5.710 | 2.858 |

- Reused `diagnose_recorded_reach.GetReachUpperBound`: the chain-length
  upper bound from right shoulder pitch origin to yaw-wrist origin is
  0.410394 m. This is NOT a spherical collision-free workspace; a target
  inside it can still violate orientation/joint/collision constraints.
  At 1x, 196/1036 moving frames (18.919%) are provably outside this bound.
  The maximum target distance is 0.485088 m, so at least 7.469 cm position
  error is geometrically unavoidable there, even ignoring other limits.
- Worst-position frame 852 (14.2 s): initial error 10.650 cm / 1.664 deg.
  After holding that exact goal 10 s, error remains 10.642 cm / 1.308 deg
  and the final second has zero motion. The whole hold target is outside
  the geometric upper bound. Joint-bounded endpoint search (12 seeds)
  found no matching solution, but that numerical failure alone is NOT an
  infeasibility proof. The independent chain-length bound is the proof.
- Worst-rotation frame 154: initial error 8.201 cm / 23.378 deg. Holding
  the goal settles within 1 cm / 5 deg after about 0.283 s and stays there
  through the hold, ending at 0.0474 cm / 0.0047 deg. This supports a
  transient tracking-lag interpretation for that particular sample.
- All executed sampled paths retained at least 20.438 mm clearance and
  respected velocity, frozen-joint and operational joint bounds within
  numerical tolerance. This is kinematic/offline evidence, not dynamics,
  continuous collision certification, or physical authorization.
- Next work: audit how the recorded model-frame wrist goals are formed
  (reference/calibration/workspace mapping) before another IK speed change.
  Do not silently clamp raw hands, change axes, remove collision limits,
  or promote the experimental candidate to production. Inside-bound p95
  is still 2.858 cm at quarter input speed; hand alignment is NOT solved.
- Verification: 251 backend tests passed in 53.776 s, Python compile and
  scoped whitespace checks passed. Test log:
  `logs/quality/backend_tests_tracking_lag_20260903.txt`.
  All three hardware authorization flags remain false.

### 2026-09-03 wrist target mapping audit (no control changes)

- Added `backend/tools/audit_wrist_target_mapping.py` and four tests in
  `backend/tests/test_wrist_target_mapping_audit.py`. The audit reads the
  same review capture and `logs/captures/g1_mink_capture_20260903_102446_unity_trace.csv`.
  Report: `logs/quality/wrist_target_mapping_audit_20260903.json`.
  No production code, scene setting, calibration, scale, safety limit or
  hardware authorization was changed. No G1 access or publisher was used.
- Current source path:
  - `G1ExistingHandTargetBinder.Calibrate` records the operator wrist neutral.
    `CaptureEngagementFrame` locks OperatorHeading. During active motion,
    body-compensated wrist displacement is expressed in this fixed heading,
    then multiplied by movement_scale and smoothed.
  - `G1ExistingTargetUdpSender.SendTarget` applies forward scale and a
    low-pass filter; `OperatorToRobot` maps delta to `[z, -x, y]` and adds
    robot_center + position_offset. The current scene uses unit movement
    and forward scales, and position_smoothing=1.
  - `run_mink_g1_right_arm_virtual_center_live.py` captures the first input
    and robot yaw-wrist pose at clutch engagement. Its requested target is
    `robot_wrist_at_engage + (input_position - input_position_at_engage)`.
    Therefore the constant sender center `[0.42, -0.16, 1.05]` cancels;
    changing that center is NOT a solution to the recorded reach overflow.
  - The original target is not clamped. FeasiblePlan creates a separate
    checked local preview; workspace_limited is emitted false on this path.
- Evidence from all three captured active segments:
  - First requested target equals the recorded wrist exactly; first delta
    is zero. Reconstructed target-minus-delta anchors stay constant within
    2.3e-17 m. Model FK matches captured wrist positions within 4.3e-14 m.
  - Unity sender position mapping fits `[z,-x,y] + constant_center` with
    maximum 1.42e-6 m residual (CSV precision). All inferred centers are
    `[0.42, -0.16, 1.05]`. No repeated axis conversion or drifting backend
    anchor is evidenced by these checks.
  - Segment 2 has 100/522 actual recorded packets outside the chain-length
    upper bound. Prior 196/1036 counts used 60 Hz resampling, not packets.
    Segments 1 and 3 have no targets outside this necessary bound; that
    does NOT prove all their 6D targets are feasible.
  - Worst packet 427 / capture offset 107.954 s requests relative robot
    movement `[0.44853, 0.08552, 0.17478]` m. The goal is 48.509 cm from
    the shoulder against the 41.039 cm chain upper bound. Its exact target
    delta also appears in Unity feedback at CSV time 45.573252 s.
    The nearest third-segment worst-target feedback differs by 3.03 mm;
    do not pretend every packet has an exact CSV counterpart.
- Counterfactual only, NOT applied: segment-2 uniform scales 1/.9/.8/.7
  leave 100/87/36/0 packets outside the sphere. The mathematical largest
  scale <=1 satisfying this necessary bound for this recording is 0.75845.
  This is an overfit position-only bound, NOT a recommended gain, full IK
  solution, safe path or reason to silently change the user's 1:1 mapping.
- Limits: current source/scene are not recording-time Inspector snapshots.
  The CSV lacks the precise calibration neutral, locked heading, accumulated
  body-motion estimate and packet/session IDs. Exact raw-hand-to-binder
  reconstruction, packet identity and transport latency remain unverified.
  Do not equate a matching sender map with validation of the full XR chain.
- Next work should preserve raw hand intent and inspect the feasible target
  behavior for these impossible goals; any ergonomic scaling/recentering
  policy must be explicit and separately tested. The current diagnostic
  does not fix inside-bound IK residuals or authorize physical deployment.
- Verification: 255 backend tests passed in 45.281 s under isolated MuJoCo
  3.12.0; Python compilation and scoped whitespace check passed. Log:
  `logs/quality/backend_tests_mapping_audit_20260903.txt`.
  All three hardware_output_authorized flags were rechecked false.

### 2026-09-03 infeasible-goal hold and inward-return preview check

- Added `backend/tools/inspect_feasible_target_return.py` and three focused
  tests in `backend/tests/test_feasible_target_return.py`. No control or
  Unity code/settings changed; the hardware profiles remain locked.
- Scenario: reconstruct segment 2 up to worst-position frame 852, keep
  that exact unreachable 6D goal for 10 s, interpolate the target inward
  to the initial FK wrist pose over 4 s, then hold it for 6 s. Position is
  linear and rotation uses SciPy Slerp; no goal mutation, re-engagement,
  calibration reset or raw-target clamping occurs. This is a constructed
  return trajectory, not a new Quest recording.
- Two separate processes tested the current planner with installed MuJoCo
  3.11.0 and the optimized experimental candidate with isolated 3.12.0.
  The candidate prefix matched the reference qpos exactly. Because both
  algorithm and engine differ, this is not a single-variable ablation.
- Reports/traces/screenshots:
  `logs/quality/feasible_return_current_20260903.json` and
  `logs/quality/feasible_return_candidate_20260903.json`, sibling JSONL,
  log files and four PNGs per variant. Each trace records actual and
  preview qpos, independently reconstructed FK, goal and collision data.
- Both runs: zero invalid preview endpoints, preview-position/FK residual
  zero, unchanged 40/100 deg/s caps and frozen joints. During the final
  second of the unreachable hold, both actual joint speed and preview
  position spread are zero; preview and actual wrist coincide. The raw
  goal stays separate, with 10.671 cm current / 10.642 cm candidate error.
- Inward return resumes without changing the reference. At the end of the
  4 s target return: current error 0.328 cm / 0.75 deg, candidate error
  0.480 cm / 0.745 deg. After the final hold both position and rotation
  errors are below 0.001 cm / 0.001 deg (kinematic numerical residuals,
  not real hardware accuracy). Both reports are OFFLINE_CRITERIA_MET.
- Actual sampled clearance minima are about 20.000 mm current and
  20.468 mm candidate; preview endpoints also passed CheckConfiguration.
  Planner-internal intermediate checks remain enabled. This is NOT a
  continuous collision proof, dynamics/PD test or physical authorization.
- Static Unity code inspection: green uses LatestFeasibleTargetOperatorDelta
  only with fresh matching-session feedback and valid calibration. It is
  the FK of a short predicted configuration, not an independent hand
  follower or a guarantee that the white straight line is a safe path.
- Offline screenshots show the robot pose/framing. The unrelated unnamed
  XML mocap marker is hidden only in this diagnostic renderer. At a stop,
  the preview sphere can be occluded inside the wrist mesh; numeric FK
  checks, not these screenshots, establish marker correspondence. No claim
  is made that actual Unity/Quest UX was tested.
- Verification: 258 backend tests passed in 49.344 s with isolated 3.12.0;
  log `logs/quality/backend_tests_feasible_return_20260903.txt`. Python
  compilation passed. The later diagnostic-only marker-hide change was
  exercised by rerunning both full scenarios. No G1 access or publisher.
- Conclusion: this tested boundary/return path does not reproduce a stuck
  feasible target. Do not loosen constraints or change raw-hand scale on
  this evidence. Inside-bound tracking residuals and other paths remain
  open; actual Quest display/interaction still needs direct validation.

### 2026-09-03 15:24 local Quest boundary test prepared

- Started the existing production virtual-center controller with default
  Python 3.11 / MuJoCo 3.11.0, not the isolated experimental candidate.
  No IK, speed, mapping, or hardware authorization changes.
- Set local Unity display mode to simulation. Existing Unity editor and
  Meta Link runtime were running; headset tracking and Play are not verified.
- Local-only processes: MuJoCo PID 44320 (UDP 5005/5012), capture PID
  42808 (5008 -> 5014), dry-run PID 46796 (5014 -> simulation feedback).
  Capture and dry-run have 900-second durations from 15:24:03; close the
  MuJoCo window separately. PIDs are historical, verify before stopping.
- Recording: `logs/captures/g1_mink_capture_20260903_152403.jsonl`.
  Process stdout/stderr: `logs/runtime/quest_boundary_20260903_152403_*`.
  After the user finishes, preserve `Unity_G1_VR/Logs/live_quest_trace.csv`
  next to this capture before another Play session overwrites it.
- Verified dry-run validate-only PASS, all four local ports bound, empty
  process stderr, and no UDP 5013 listener. All three hardware profiles
  remain locked. No WSL/camera/G1 connection or DDS publisher started.
- User test pending: engage, extend slowly to the reach boundary, hold
  3 seconds, move inward, then thumb-index pinch to disengage. Compare
  raw wrist, feasible preview, actual wrist, and recovery without re-engage.

### 2026-09-03 15:27 Quest boundary test reviewed

- User completed the prepared local Quest test. Preserved Unity trace as
  `logs/captures/g1_mink_capture_20260903_152403_unity_trace.csv` and copied
  the still-recording capture into the immutable review input
  `logs/quality/g1_mink_capture_20260903_152403_review_snapshot.jsonl`.
- Existing capture-quality and wrist-mapping tools completed successfully.
  Reports: `logs/quality/quest_boundary_20260903_152403_quality.json`,
  sibling HTML, and `quest_boundary_20260903_152403_mapping.json`.
- Snapshot contains 8690 packets, one 325-packet active interval lasting
  10.625 s (capture offsets 203.359 to 213.984), then pinch_disengaged.
  Recorded mean packet rate 30.923 Hz; maximum gap 47 ms.
- Boundary-and-return behavior recovered without another engage: at about
  2.5-6.5 s after engage the preview reported local_limit; at 7.52 s it
  returned to following. Raw wrist position error peaked at 11.075 cm,
  fell to 1.023 cm at 7.52 s, and ended at 0.370 cm before pinch.
- All 325 active preview samples were valid. Feasible-preview to simulated
  wrist separation p95 0.422 cm, maximum 0.470 cm. This is numerical evidence,
  not a direct observation of marker visibility inside the headset.
- Mapping audit found no backend anchor drift (2.08e-17 m), zero initial
  target jump, and sender-axis fit residual below 1.5e-6 m. Raw-hand to
  binder reconstruction remains incomplete because the CSV lacks exact
  reference/heading/body-compensation state.
- 170/325 active raw goals were provably outside the model's necessary
  position bound: worst shoulder distance 49.76 cm versus chain upper
  bound 41.04 cm. Do not remove constraints or silently reduce 1:1 scale.
- Minimum reported clearance 32.9 mm; collision_limited appeared in 166
  active packets but is not proof of actual contact/penetration. Rotation
  error p95 0.905 deg, maximum 1.793 deg.
- Overall quality report remains REVIEW_REQUIRED: raw goal error p95
  10.743 cm and finite-difference acceleration/jerk checks exceed the
  hardware comparison limits. The experimental limiter passes its own
  bounds but was not applied to this live simulation. No hardware approval.
- No control-code or configuration changes in this review. Local recorder
  and dry-run retain their existing 900-second automatic stop; no G1 access.

### 2026-09-03 15:33 Quest rotation / combined-motion review

- New user test is NOT a clean pass. Preserved the newer Unity CSV as
  `logs/captures/g1_mink_capture_20260903_152403_second_unity_trace.csv`
  and the growing recorder as
  `logs/quality/g1_mink_capture_20260903_153321_review_snapshot.jsonl`.
  Earlier snapshots were not overwritten.
- Full recorder contains five active intervals across three Unity sessions.
  The latest CSV contains only the final two intervals, from session
  `82ed274d410540d2a5c0cab807261b3e`. Analysis uses derived
  `logs/quality/quest_motion_20260903_153321_session.jsonl`, filtered to
  that session with sequential analysis indices. Original indices, exact
  payloads and capture offsets are retained; manifest records provenance.
  The first audit rejected un-reindexed data, then passed on the explicitly
  derived capture. Do not combine the old boundary test with this result.
- Latest session: 903 active packets in 27.953 s and 1.594 s intervals.
  Reports: `logs/quality/quest_motion_20260903_153321_quality.json` / HTML,
  `_mapping.json`, and `_diagnostics.json`.
- In the long interval, all seven joint values remained stationary within
  0.0001 deg per sample from relative t=5.468 to 8.531 s (3.063 s).
  Raw target moved up to 7.733 cm and rotated up to 108.157 deg during
  this stop. Preview status was local_limit. Worst rotation error was
  125.629 deg at t=7.890 s; nearest pair torso_link/right_shoulder_yaw_link
  had 20.014 mm clearance. Wrist margin was still 80.161 deg.
  Other freeze intervals lasted 0.969 s and 0.531 s near the same 20 mm
  clearance boundary. This is a local-planner stall, not lost input;
  whether merit rejection or sampled collision checks block a safe escape
  still needs offline replay. Do not assume a collision-free alternative.
- Long interval position error p95 8.382 cm, max 16.979 cm, final 5.281 cm;
  orientation p95 116.392 deg. Short final interval ends at 0.0722 cm and
  0.0550 deg, but does not invalidate the earlier stall.
- Both segments retain fixed backend anchors (max 8.67e-18 m); FK and
  sender-axis checks pass. Only 40/854 and 0/49 raw targets are outside
  the necessary chain-length bound. Sphere interior alone is not 6D or
  collision feasibility. All 903 feasible-preview samples were valid.
- No 3 s continuous target hold met the diagnostic criteria of <=5 mm
  position excursion and <=3 deg rotation excursion. Hence a deliberate
  full 3-second settle test and isolated wrist-only proximal-motion
  assessment are not established by this mixed movement recording.
- Quality remains REVIEW_REQUIRED, including acceleration/jerk comparison
  warnings. No control edits, safety weakening, hardware unlocking or G1
  access. Next: reproduce the t=5.468-8.531 s recorded stall offline and
  instrument the local planner's rejection reasons before another Quest test.

### 2026-09-03 Isaac Lab G1 source comparison

- User approved reviewing the linked NVIDIA forum example, not replacing
  Unity/MuJoCo or changing hardware controls. Source review is recorded in
  `docs/ISAACLAB_G1_IK_COMPARISON.md` with commit-pinned links.
- Inspected Isaac Lab commit `b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8`:
  fixed-base G1 environment, TriHand retargeter, Pink action/config/controller,
  LocalFrameTask, NullSpacePostureTask, and kinematics configuration.
  This is current source, not proven identical to the forum author's version.
- G1 frame costs are 8/2 (same base numbers as ours), but same-wrist 6D
  task, gain/LM settings, selected null-space posture, controlled waist,
  physics feedback and timestep differ. No explicit collision barrier is
  wired into the inspected IK solve, so smooth demo motion is not evidence
  of superiority under our torso/upper-arm clearance constraints.
- Candidate ideas: compare a same-wrist task and projected posture objective
  independently. Preserve raw targets, right-arm-only control, speed caps,
  collision pairs and margins. Do not copy tracking-loss zero poses or
  frame offsets into our existing Unity path.
- No simulator install/run, code/default changes, physical unlocking or G1
  access. Next task remains instrumentation/replay of the captured local-limit
  stall before proposing or promoting an experimental control change.

### 2026-09-03 supervisor proposal: TWIST2 right-arm sign / socket tests

- User relayed the supervisor's proposed sequence: adapt the existing G1
  static-stand left-arm manual control to the right arm, compare positive
  and negative joint motion with the PC model, then add a socket or ROS
  command interface. This is not permission to deploy or run on the G1.
- Read local reference `references/lower_body/twist2_deploy/cpp_g1_twist2/`
  `twist2_static_stand.cpp` and `twist2_common.hpp`. Current G1-side files
  may differ; this inspection did not access the robot.
- Existing program is a full-body owner, not an arm_sdk adapter: 50 Hz
  policy/keyboard updates, 500 Hz rt/lowcmd output, TWIST2 legs, captured
  waist/unselected arm targets, AI service handoff and damping on exit.
  It writes a CSV. Do not run alongside our physical rt/arm_sdk path or
  another LowCmd publisher. Damping is not guaranteed standing support.
- Local preparation should preserve the source reference and use an isolated
  right-arm variant. Move the controlled slice 15..21 to 22..28 together
  with labels, limits, safety checks and telemetry. Right-side roll limits
  differ from the left; never negate all seven angles as a mirror shortcut.
  Existing zero-key means absolute zero rad, not captured-start posture.
- Sign validation should bypass VR/IK: selected joint q_start +/- small
  reviewed delta -> actual outgoing LowCmd q -> measured LowState q ->
  MuJoCo joint q -> Unity display. Log degrees/radians explicitly and compare
  measured deltas to baseline; visual direction alone is not a sign test.
- Proposed network path: PC joint target -> explicit socket receiver in the
  same C++ owner -> validation / limits -> single full-body LowCmd writer.
  ROS is an alternative input transport, not a requirement or a second motor
  publisher. Require session/sequence, freshness, finite values, units,
  joint order and timeout behavior before actuation. Start with receive-only
  logging and simulated packets. Reuse existing VR/IK upstream only after
  joint sign and physical-response validation.
- No source adaptation, socket listener, G1 write, physical output or
  hardware unlocking performed in this turn. Existing IK stall evidence
  remains unresolved; the manual test isolates command delivery from IK.

### 2026-09-03 local TWIST2 right-arm manual derivative prepared

Historical preparation below; its added gates were removed by the user's
subsequent request in the correction entry that follows.

- Follow-up to the supervisor proposal, isolated under
  `experiments/twist2_right_arm_manual/`. Do not treat this as deployment or
  physical-run approval. No G1 access, file transfer, SDK publisher, live
  configuration unlock or production Unity/Mink edit was performed.
- Added `twist2_right_arm_trial.cpp`: mechanically derived from the local
  static-stand reference. Controlled indices, checks and telemetry now use
  right arm 22..28; waist/left-arm targets remain captured. Common 29-joint
  limits/gains and policy remain unchanged. Preserve imported source style
  so the derivative diff can be audited against the reference.
- Added `right_arm_trial_gate.hpp`: default compilation blocks before policy
  loading or DDS initialization. Explicit reviewed builds accept only the
  keyboard-right-arm argument form, not the inherited automatic 30-degree
  shoulder path. CMake physical target creation is OFF by default.
- Inherited behavior is NOT a newly approved safety envelope: 0.02 rad key
  steps, 0.08 rad/s times 1..9 target rate, 300 s keyboard mode, absolute-zero
  keys, full-body AI handoff and damping termination. Q increases shoulder
  pitch here; P requests damping. This differs from the laptop Arm SDK Jog.
  Collision safety is not established by preserving torque/joint limits.
- `TEST_OFFLINE.bat` runs `verify_offline.py` locally. Reference SHA-256 and
  exact allowed derivative edits checked. Extracted real common-header math
  and right-side constants compiled with local WSL g++; all 7 joint tests
  and 16 compiled argument-gate cases passed. Gate test executables contain
  no policy/SDK/controller and never initialize DDS, even in the reviewed
  argument-validation case.
- Evidence: `logs/test_results/twist2_right_arm_offline_20260903_162639/result.json`.
  This verifies source/keyboard math only. Full Torch/SDK2 binary compilation,
  current G1-source equality, real joint signs, physical response and collision
  behavior remain UNVERIFIED. No socket listener implemented yet.
- Next: local full-build prerequisites and reviewed per-joint physical-test
  envelope, then exact approval for G1 files/CSV creation and execution. Keep
  one full-body LowCmd owner and do not run alongside Arm SDK publishers.

### 2026-09-03 correction: minimal left-to-right adaptation only

- User explicitly rejected additional behavior changes: preserve the working
  left-arm program and change only arm indices and corresponding names.
- Removed the added argument gate/include/header, keyboard-only restriction,
  CMake review option/definition, and obsolete gate tests from the isolated
  right-arm experiment. Original CLI modes, --enable-actuation, P confirmation,
  remote protections, damping and controller flow are retained unchanged.
- Entire derivative source is checked against the reference with only these
  transformations: Left/left -> Right/right, both arm-start/pitch indices
  15 -> 22, held-arm label right -> left, program/CSV naming. No added source
  header comments or control blocks remain. Common header SHA-256 is pinned.
- User states original PD gains were arbitrary, not validated optimal gains.
  Preserve them for this comparison; tuning is a separate future task.
- Offline verifier retains compiled checks for all seven right-arm joints and
  saves source_changes.diff with result.json. It does not run the controller.
  Full controller build and real physical signs remain unverified.
- No G1 access, deployment or actuation. Existing production hardware-output
  configuration locks and Unity/Mink paths are unrelated and remain untouched.

### 2026-09-03 full local TWIST2 right-arm build passed

- Completed full compilation and linking without changing the controller source.
  Binary was NOT executed. No G1 access, file transfer, remote installation,
  DDS publisher or physical output occurred.
- Local WSL Ubuntu 26.04 x86_64, g++ 15.2.0; reused existing CMake 4.4.2.
  Installed isolated CPU PyTorch 2.8.0+cpu / Python 3.11.16 and cloned official
  Unitree SDK2 commit 9754cd153af3da471b0fe5f3aa535e426fb11db3 into
  /home/user/.local/share/g1-right-arm-build/. Existing control venv unchanged.
- CMake configure and full build exit 0. Third-party header warnings observed;
  do not describe this as warning-free. Notebook ELF x86-64 binary:
  /home/user/.local/share/g1-right-arm-build/build/g1_twist2_cpp_right_arm_trial.
- Build evidence with commands/hashes:
  logs/test_results/twist2_right_arm_build_20260903_164053.json.
  Source/reference preservation and all seven compiled math tests re-passed:
  logs/test_results/twist2_right_arm_offline_20260903_164053/result.json.
  The math verifier's full_controller_build_verified=false is its own test
  scope, not a claim that this separate full-build result did not pass.
- G1-target architecture/dependency compatibility, actual policy execution,
  physical signs, response, collision safety and arbitrary PD gains remain
  unverified. Do not copy the notebook binary to G1 as a deployable artifact.
  Next: agree exact G1 deployment/build/run actions with the user and owner;
  a generic next-step request does not permit G1 writes or actuation.
