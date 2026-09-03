# G1 Teleop Project Chat Handoff

> **Absolute G1 mutation rule:** Never create, delete, rename, move, or modify any file on the G1; never run a program that can create a log, publish a command, change a service or mode, or otherwise mutate G1 state without the user's explicit approval for that exact action. Inspect source before running diagnostics. Remote-to-local copy is allowed only when it reads existing G1 files and writes exclusively to the Windows project.

Last updated: 2026-09-04

## 1. Start here

For every new project conversation:

1. Read this file.
2. Read [`ARCHITECTURE.md`](ARCHITECTURE.md).
3. Read [`REVIEW_LATEST.md`](REVIEW_LATEST.md) and the detailed review documents it links.
4. Read [`CODE_GUIDE.md`](CODE_GUIDE.md) before changing a control path.
5. Inspect the current branch, commit and working tree before destructive Git operations.
6. Keep review findings, production changes and physical tests in separate commits and reports.
7. Update this handoff after a meaningful implementation or verification milestone.

Do not remove safety checks, loosen limits or change gains merely to make a test pass. Do not treat unit, static, simulation or transport tests as physical validation.

## 2. Repository checkpoint

```text
Repository : Y1048/Y
Branch     : refactor/teleop-architecture
Code head  : 187b3e2a44466653bc099327e0ace7f18dc7fcb0
```

The default Windows launcher remains:

```text
START_VR_HAND_TO_MUJOCO.bat
```

The default simulation controller remains:

```text
MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py
```

Current control scope is the G1 right arm. The simulation path is Unity/VR → UDP 5005 → Mink differential QP/DAQP → MuJoCo → Unity state UDP 5006, with a separate Gate 7 candidate stream on UDP 5008. Physical Arm SDK and TWIST2 paths remain separate from the default simulation launcher.

## 3. Current review and remediation state

The precision review currently records findings R1-R67. The review is not complete. Use [`REVIEW_LATEST.md`](REVIEW_LATEST.md) as the current index.

### R64 implementation checkpoint

Commit `187b3e2a44466653bc099327e0ace7f18dc7fcb0` implements the first remediation batch for R64:

- `workspace_exit`, `pinch_disengaged` and `tracking_disengaged` are command-batch barriers.
- Later ACTIVE datagrams remain queued until the next control poll.
- An earlier ACTIVE target from the same batch is not exposed after the safety event.
- A safety reset cannot engage the clutch again in the same `MinkCommandUpdate`.
- Stale-session takeover behavior remains unchanged and may still reset/re-engage once for a new session.

Focused syntax and 18 command-ingress tests passed in an isolated local harness. The committed repository tests cover active→pinch→active and active→workspace-exit→active backlogs. Full repository discovery, Unity Play, Quest and hardware runtime were not executed for this batch, so R64 is implemented but integration validation remains pending.

### Next implementation batch

```text
release/fault finalization : R1, R34, R46
```

That batch must make Gate 7, Gate 6 and Jog release reporting reflect the last successfully transmitted weight, zero-tail completion and release failure. It must not create or authorize physical output during testing.

## 4. Coverage ledger

`logs/review/20260903/source_checks.csv` is the original bounded snapshot: 117 `full_text_review`, 147 `static_only`. It does not include the later R20-R67 continuation work and must not be quoted as current effective coverage.

Post-snapshot implementation/review deltas begin at:

```text
logs/review/20260903/source_checks_delta_20260904.csv
```

The canonical CSV count still requires a deliberate regeneration from the current branch. Until then, the detailed review documents and delta file are the authoritative continuation record.

## 5. Hardware and environment boundary

- Repository hardware authorization remains locked; the R64 commit changed only backend command-ingress code and tests.
- Do not assume G1 Ethernet, WSL DDS, Unity, Quest or any publisher is currently running. Verify current process/network state before use.
- Read-only LowState tools and physical-output tools must remain clearly separated.
- No physical command, G1 file mutation, service/mode change or administrator network change is authorized by this handoff.
- Preserve measured wrist calibration and any intentional local work; inspect `git status`, stash contents and diffs before reset, restore or cleanup.

## 6. Historical handoff

The complete pre-remediation handoff history was preserved byte-for-byte at:

[`CHAT_HANDOFF_HISTORY_20260903.md`](CHAT_HANDOFF_HISTORY_20260903.md)

Use it for historical decisions, prior test logs, WSL setup, Unity crash investigation and older checkpoints. Current work should follow this concise file and `REVIEW_LATEST.md` first.
