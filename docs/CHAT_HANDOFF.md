# G1 Teleop Project Chat Handoff

> **Absolute G1 mutation rule:** Never create, delete, rename, move, or modify any file on the G1; never run a program that can create a log, publish a command, change a service or mode, or otherwise mutate G1 state without the user's explicit approval for that exact action. Inspect source before running diagnostics. Remote-to-local copy is allowed only when it reads existing G1 files and writes exclusively to the Windows project.

Last updated: 2026-09-04

## 1. Start here

For every new project conversation:

1. Work from `main`.
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

## 4. Reconciled review coverage

Current canonical ledger:

```text
total current scoped files : 302
full_text_review           : 268
static_only                : 34
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
```

The 34 `static_only` files remain the review queue. Backend diagnostic/test,
`tools/*.bat` launcher, configuration/frame and multi-strategy batches are
complete at the current scope.

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
1. Continue the 34 remaining posture-sweep, TWIST2 experiment and hardware-helper static-only files.
2. Keep R20/R24/R27/R32 remediation separate from review bookkeeping.
3. Do not invent R50 remote/deadman/CRC checks; verify actual read-only Unitree SDK fields first.
4. Plan simulation/WSL integration checks with hardware output locked.
5. Reconcile CODE_INDEX/source_checks after each substantial review batch.
```

Do not expand physical testing yet.

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
