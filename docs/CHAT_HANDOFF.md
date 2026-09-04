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
- **R46** is integrated into `g1_right_arm_jog.py` itself; planned/fault release share the SDK-neutral finalizer and incomplete evidence is fail-closed.
- **R40** supported physical paths bind current 29-joint/model/config evidence and raw `rt/odommodestate` position/quaternion back to startup, while requiring live base stability. Connected-G1 validation is still not done.
- **R50** supported paths supervise LowState IMU roll/pitch, motor temperature/fault/tau finiteness, and runtime base/odometry stability. Remote/deadman and CRC/integrity remain open until actual read-only SDK fields are verified.
- **R27/R32** were reconfirmed by the backend-core full-text review and remain open. R27 is generic SE(3) matrix validation; R32 is direct V1 protocol integer coercion versus strict V2.

## 4. Reconciled review coverage

Current canonical ledger:

```text
total current scoped files : 302
full_text_review           : 176
static_only                : 126
static check failures      : 0
```

Use:

```text
logs/review/20260903/source_checks.csv
logs/review/20260903/source_checks_summary_20260904.json
docs/CODE_INDEX.md
```

The latest review batch is [`REVIEW_20260904_BACKEND_CORE.md`](REVIEW_20260904_BACKEND_CORE.md). It reviewed protocol/config/calibration/transforms/camera/runtime core plus directly relevant tests and introduced no new R-number. The 126 `static_only` files remain the review queue.

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
1. Continue the 126 static-only files, prioritizing remaining backend tests/helpers and launch/test surfaces.
2. Keep R27/R32 remediation separate from review bookkeeping.
3. Do not invent R50 remote/deadman/CRC checks; verify actual read-only Unitree SDK fields first.
4. Plan simulation/WSL integration checks with hardware output locked.
5. Reconcile CODE_INDEX/source_checks after each substantial review batch.
```

Do not expand physical testing yet.

## 7. Hardware boundary

- Repository hardware authorization remains locked.
- Do not assume G1 Ethernet, WSL DDS, Unity, Quest or any publisher is currently running.
- No physical command, G1 file mutation, service/mode change or administrator network change is authorized by this handoff.
- Runtime-base changes add only read-only `rt/odommodestate` subscriptions on supported physical paths; they have not been executed against G1 in this remediation session.
- Preserve calibration and intentional local work; inspect Git state before cleanup/reset/restore.

## 8. Historical handoff

Historical detail remains in [`CHAT_HANDOFF_HISTORY_20260903.md`](CHAT_HANDOFF_HISTORY_20260903.md). Use this current handoff and `REVIEW_LATEST.md` first.
