# G1 Teleop Project Chat Handoff

> **Absolute G1 mutation rule:** Never create, delete, rename, move, or modify any file on the G1; never run a program that can create a log, publish a command, change a service or mode, or otherwise mutate G1 state without the user's explicit approval for that exact action. Inspect source before running diagnostics. Remote-to-local copy is allowed only when it reads existing G1 files and writes exclusively to the Windows project.

Last updated: 2026-09-17

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
  position-priority state now ramps orientation cost to zero instead of 25%;
  its original rotation goal is retained and restored after positional
  recovery. Runtime packets now record the priority flag and scale.

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
  torso; the infeasible raw wrist orientation is temporarily replaced by the
  current wrist orientation. Elbow reconfiguration is also disabled. When the
  raw target leaves the exclusion volume, normal position and orientation
  tracking resume. Raw/effective positions, projection distance and the
  orientation-relaxed flag remain in runtime and raw-JSON CSV diagnostics.
  Recorded-problem regression coverage bounds elbow lift below 3 cm. This is
  MuJoCo/offline validation only.

## Laptop migration checkpoint

This integration branch combines the latest published continuation with the laptop source. Read [migration status](migration/20260917/README.md) and [two-PC synchronization rules](migration/20260917/TWO_PC_SYNC.md) first. Local historical notes are preserved in [LAPTOP_CHAT_HANDOFF.md](migration/20260917/LAPTOP_CHAT_HANDOFF.md). Conflicting temporary-worktree work is stored as patches, not enabled in this checkout. This is source synchronization, not hardware validation.

### 2026-09-17 scope change and last locomotion evidence

- GitHub-to-desktop continuation is the current priority.
- Lower-body policy development in this repository is stopped. Another developer will provide that policy; later work only integrates it with the Unity/Mink upper-body target and the single LowCmd owner.
- Do not repeat the preserved velocity 12DoF physical trial. In the last `+vx=0.05` axis trial, the policy transition reached approximately roll `-0.19 rad` and pitch `+0.34 rad`, then the controller stopped on `RuntimeError: IMU roll/pitch limit` and retained the last valid full-body position command.
- The robot was reported stable in its support rig after that event. This observation is not policy validation.
- Existing locomotion sources, MuJoCo results and logs remain historical evidence. Their presence is not authorization to deploy or run them on G1.


## 1. Start here

For every new project conversation:

1. For this desktop migration, use `codex/g1-laptop-sync-20260917`. `main` remains the canonical branch after review and merge.
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
