# G1 Teleop Project Chat Handoff

> **Absolute G1 mutation rule:** Never create, delete, rename, move, or modify any file on the G1; never run a program that can create a log, publish a command, change a service or mode, or otherwise mutate G1 state without the user's explicit approval for that exact action. Inspect source before running diagnostics. Remote-to-local copy is allowed only when it reads existing G1 files and writes exclusively to the Windows project.

Last updated: 2026-09-04

## 1. Start here

For every new project conversation:

1. Work from `main`.
2. Read this file, [`ARCHITECTURE.md`](ARCHITECTURE.md), and [`REVIEW_LATEST.md`](REVIEW_LATEST.md).
3. Read the relevant remediation log before changing a reviewed defect.
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

## 3. Current remediation state

The precision review records R1-R67 and remains incomplete. `REVIEW_LATEST.md` is authoritative for current status.

Key current state:

- **R15/R35/R65** supported command provenance/freshness paths are source-mitigated and current-checkout CI is green.
- **R21/R51** supported LowState startup paths use per-run forward tokens and provenance/state/raw-odometry-bound prechecks.
- **R1/R3/R34/R64** have source fixes with offline regression coverage.
- **R2/R33/R41/R42** supported Gate 7/Jog collision/acquisition guards have offline regression coverage.
- **R46** is integrated into `g1_right_arm_jog.py` itself. Planned and fault release use the shared SDK-neutral finalizer, last successful transmitted weight is tracked after successful writes, and incomplete/missing release evidence is fail-closed. The wrapper remains as an additional result guard.
- **R40** supported physical paths now bind current 29-joint/model/config evidence and raw `rt/odommodestate` position/quaternion back to the startup precheck, while also requiring live base stability. This is source-side complete for the supported path but still lacks connected-G1 physical validation.
- **R50** supported paths supervise LowState IMU roll/pitch, motor temperature/fault/tau finiteness, and current runtime base/odometry stability. Remote/deadman and CRC/integrity checks remain open because no reviewed Python SDK field/API contract has yet been established for them.

## 4. Reconciled review coverage

The canonical review ledger and code index were regenerated from the current `main` checkout.

```text
total current scoped files : 302
full_text_review           : 158
static_only                : 144
static check failures      : 0
```

Use these files as the current administrative record:

```text
logs/review/20260903/source_checks.csv
logs/review/20260903/source_checks_summary_20260904.json
docs/CODE_INDEX.md
```

The 144 `static_only` files are the remaining review queue; the review is not complete.

## 5. Offline regression evidence

Active workflows on `main`:

```text
.github/workflows/offline-provenance-regression.yml
Run 33824261133 : PASS
```

This covers command ingress, source-clock/backlog handling, relay/replay provenance, startup token/state/raw-odometry binding and live Mink producer provenance.

```text
.github/workflows/offline-safety-regression.yml
Run 33824155653 : PASS
```

This covers release finalization, Gate 7 acquisition/final collision checks, LowState IMU/motor health, runtime base/odometry stability, startup/runtime odometry continuity, Jog full-body/permit/final-segment safety, direct Jog shared-release integration and wrapper result semantics.

These workflows create no Unitree publisher, DDS endpoint, WSL runtime, Unity/Quest runtime or G1 connection.

## 6. Immediate next work

```text
1. Continue the 144 static-only files, prioritizing backend protocol/config/calibration and launch/test surfaces.
2. Do not invent R50 remote/deadman/CRC checks; verify actual read-only Unitree SDK fields first.
3. Plan simulation/WSL integration checks with hardware output locked.
4. Reconcile CODE_INDEX/source_checks again after each substantial review batch.
```

Do not expand physical testing yet.

## 7. Hardware boundary

- Repository hardware authorization remains locked.
- Do not assume G1 Ethernet, WSL DDS, Unity, Quest or any publisher is currently running.
- No physical command, G1 file mutation, service/mode change or administrator network change is authorized by this handoff.
- Runtime-base changes add only read-only `rt/odommodestate` subscriptions on supported physical paths; they have not been executed against the G1 in this remediation session.
- Preserve calibration and intentional local work; inspect Git state before cleanup/reset/restore.

## 8. Historical handoff

Historical detail remains in [`CHAT_HANDOFF_HISTORY_20260903.md`](CHAT_HANDOFF_HISTORY_20260903.md). Use this current handoff and `REVIEW_LATEST.md` first.
