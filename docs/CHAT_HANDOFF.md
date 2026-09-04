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

`main` now contains the former `refactor/teleop-architecture` work. The old refactor branch has been retired by the user. Do not target it in new automation or Codex instructions.

The default launcher remains:

```text
START_VR_HAND_TO_MUJOCO.bat
```

It launches the provenance-marking virtual-center entrypoint; `--baseline` uses the corresponding prototype entrypoint.

## 3. Current remediation state

The precision review records R1-R67 and remains incomplete. `REVIEW_LATEST.md` is authoritative for current status.

Key current state:

- **R15/R35/R65** supported command provenance/freshness paths are source-mitigated and current-checkout CI is green.
- **R21/R51** supported LowState startup paths use per-run forward tokens and provenance-bound prechecks.
- **R1/R3/R34/R64** have source fixes with offline regression coverage.
- **R2/R33/R41/R42** supported Gate 7/Jog collision/acquisition guards have offline regression coverage.
- **R40** now persists validated base-state evidence and SHA-256 binding for startup config, G1 XML, collision controller and common model source; supported consumers reject mismatched artifacts. Live base-state rebinding at the publisher boundary remains open.
- **R50** supported paths supervise LowState IMU roll/pitch and motor temperature/fault/tau finiteness. Live base/odometry, remote/deadman and CRC/integrity remain open.
- **R46** supported Jog wrapper/result semantics are guarded, but the direct core controller still has its legacy internal release implementation.

## 4. Offline regression evidence

Active workflows on `main`:

```text
.github/workflows/offline-provenance-regression.yml
Run 33822226143 : PASS
```

54 tests cover command ingress, source-clock/backlog handling, relay/replay provenance, startup provenance/state binding and live Mink producer provenance.

```text
.github/workflows/offline-safety-regression.yml
Run 33822295391 : PASS
```

44 unittest cases plus the Gate 6 interruption-release offline contract script cover release finalization, Gate 7 acquisition/final collision checks, LowState health supervision and Jog safety/result boundaries.

These workflows create no Unitree publisher, DDS endpoint, WSL runtime, Unity/Quest runtime or G1 connection.

## 5. Immediate next work

```text
1. R50: only add live base/remote/CRC checks after verifying actual Unitree SDK fields read-only.
2. R46: integrate the shared release contract into g1_right_arm_jog.py itself.
3. R40: add current base-state publisher-boundary comparison if a reliable live base source is confirmed.
4. Plan simulation/WSL integration checks with hardware output locked.
5. Regenerate the canonical review ledger/CODE_INDEX and continue remaining static-only file review.
```

Do not expand physical testing yet.

## 6. Coverage/admin debt

`logs/review/20260903/source_checks.csv` is the old 117/264 bounded snapshot and is not current effective coverage. Post-snapshot work is recorded in `source_checks_delta_20260904.csv`. `docs/CODE_INDEX.md` is stale after remediation additions.

## 7. Hardware boundary

- Repository hardware authorization remains locked.
- Do not assume G1 Ethernet, WSL DDS, Unity, Quest or any publisher is currently running.
- No physical command, G1 file mutation, service/mode change or administrator network change is authorized by this handoff.
- Preserve calibration and intentional local work; inspect Git state before cleanup/reset/restore.

## 8. Historical handoff

Historical detail remains in [`CHAT_HANDOFF_HISTORY_20260903.md`](CHAT_HANDOFF_HISTORY_20260903.md). Use this current handoff and `REVIEW_LATEST.md` first.
