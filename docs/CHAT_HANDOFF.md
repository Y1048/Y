# G1 Teleop Project Chat Handoff

> **Absolute G1 mutation rule:** Never create, delete, rename, move, or modify any file on the G1; never run a program that can create a log, publish a command, change a service or mode, or otherwise mutate G1 state without the user's explicit approval for that exact action. Inspect source before running diagnostics. Remote-to-local copy is allowed only when it reads existing G1 files and writes exclusively to the Windows project.

Last updated: 2026-09-04

## 1. Start here

For every new project conversation:

1. Read this file.
2. Read [`ARCHITECTURE.md`](ARCHITECTURE.md).
3. Read [`REVIEW_LATEST.md`](REVIEW_LATEST.md) and the detailed review documents it links.
4. Read [`REMEDIATION_20260904.md`](REMEDIATION_20260904.md) before changing a reviewed defect.
5. Read [`CODE_GUIDE.md`](CODE_GUIDE.md) before changing a control path.
6. Inspect the current branch, commit and working tree before destructive Git operations.
7. Keep review findings, production changes and physical tests in separate commits and reports.
8. Update this handoff after a meaningful implementation or verification milestone.

Do not remove safety checks, loosen limits or change gains merely to make a test pass. Do not treat unit, static, simulation or transport tests as physical validation.

## 2. Repository checkpoint

```text
Repository : Y1048/Y
Branch     : refactor/teleop-architecture
Current remediation chain:
  187b3e2  R64 command-backlog safety-event preservation
  846b0d59 shared SDK-neutral release contract
  cb5082e1  R1 Gate 7 fail-closed release
  678b5d0b  R3/R34 Gate 6 interrupted/fault release
```

Documentation commits may be newer than the code commits above. Always query the branch HEAD before editing.

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

### Implemented, pending broader validation

**R64** — `workspace_exit`, `pinch_disengaged` and `tracking_disengaged` are now receive-batch barriers. A later ACTIVE packet stays queued until the next controller poll, and safety reset cannot re-engage the clutch in the same update.

**R1** — Gate 7 release now uses a shared SDK-neutral finalizer. It records only successfully published weight, does not reread config during finalization, still attempts the zero tail after a ramp failure, revokes PASS on release failure, and distinguishes unknown output state from confirmed zero-tail completion.

**R3** — Gate 6 Ctrl+C during ACQUIRE no longer jumps to configured maximum weight. Interrupted release starts from the last successfully published/current lower weight and decreases from there.

**R34** — Gate 6 runtime faults after publisher creation now attempt a measured-pose release and independent zero tail. Fault status records release evidence instead of unconditionally claiming weight zero/output disabled.

The common release evidence contract lives in:

```text
hardware/g1_arm_bridge/arm_sdk_release_contract.py
```

It deliberately does not claim external firmware/controller authority handback.

### Immediate next code item

```text
R46 — g1_right_arm_jog.py fault result must not claim output disabled before a complete zero-weight tail.
```

After R46, return to the P1 final/acquisition group:

```text
R2, R33, R40, R41, R42
```

### Verification boundary

Regression test files were added for R64, the shared release helper, R1 and R3/R34. They have **not** been run from a checked-out repository or GitHub Actions during this remediation session. The earlier handoff statement claiming 18 committed R64 tests had passed was too strong and is superseded by `REMEDIATION_20260904.md`.

No Unity Play, Quest runtime, WSL/DDS runtime or G1 command test has been performed for these remediation commits.

## 4. Coverage ledger

`logs/review/20260903/source_checks.csv` is the original bounded snapshot: 117 `full_text_review`, 147 `static_only`. It does not include the later R20-R67 continuation work and must not be quoted as current effective coverage.

Post-snapshot implementation/review deltas begin at:

```text
logs/review/20260903/source_checks_delta_20260904.csv
```

The canonical CSV count still requires deliberate regeneration from the current branch. Until then, the detailed review documents and delta file are the authoritative continuation record.

## 5. Hardware and environment boundary

- Repository hardware authorization remains locked.
- Do not assume G1 Ethernet, WSL DDS, Unity, Quest or any publisher is currently running. Verify current process/network state before use.
- Read-only LowState tools and physical-output tools must remain clearly separated.
- No physical command, G1 file mutation, service/mode change or administrator network change is authorized by this handoff.
- Preserve measured wrist calibration and any intentional local work; inspect `git status`, stash contents and diffs before reset, restore or cleanup.

## 6. Historical handoff

The complete pre-remediation handoff history was preserved at:

[`CHAT_HANDOFF_HISTORY_20260903.md`](CHAT_HANDOFF_HISTORY_20260903.md)

Use it for historical decisions, prior test logs, WSL setup, Unity crash investigation and older checkpoints. Current work should follow this concise file, `REVIEW_LATEST.md` and `REMEDIATION_20260904.md` first.
