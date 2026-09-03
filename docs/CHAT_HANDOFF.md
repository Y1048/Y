# G1 Teleop Project Chat Handoff

> **Absolute G1 mutation rule:** Never create, delete, rename, move, or modify any file on the G1; never run a program that can create a log, publish a command, change a service or mode, or otherwise mutate G1 state without the user's explicit approval for that exact action. Inspect source before running diagnostics. Remote-to-local copy is allowed only when it reads existing G1 files and writes exclusively to the Windows project.

Last updated: 2026-09-04

## 1. Start here

For every new project conversation:

1. Read this file.
2. Read [`ARCHITECTURE.md`](ARCHITECTURE.md).
3. Read [`REVIEW_LATEST.md`](REVIEW_LATEST.md) and the detailed review documents it links.
4. Read [`REMEDIATION_20260904.md`](REMEDIATION_20260904.md), [`REMEDIATION_20260904_CONTINUATION.md`](REMEDIATION_20260904_CONTINUATION.md), [`REMEDIATION_20260904_RUNTIME_SUPERVISION.md`](REMEDIATION_20260904_RUNTIME_SUPERVISION.md) and [`REMEDIATION_20260904_PROVENANCE.md`](REMEDIATION_20260904_PROVENANCE.md) before changing a reviewed defect.
5. Read [`CODE_GUIDE.md`](CODE_GUIDE.md) before changing a control path.
6. Inspect the current branch and HEAD before editing; documentation commits may follow code commits.
7. Keep review findings, production changes and physical tests in separate commits and reports.
8. Update this handoff after a meaningful implementation or verification milestone.

Do not remove safety checks, loosen limits or change gains merely to make a test pass. Do not treat unit, static, simulation or transport tests as physical validation.

## 2. Repository checkpoint

```text
Repository : Y1048/Y
Branch     : refactor/teleop-architecture
Recent provenance chain:
  5cb4d657  R15 live/replay provenance helpers
  f87b9201  replay packets marked recorded_replay
  e302dd98  live relay rejects replay and emits live_mink
  4bebf749  Gate 7 hardware entry requires live_mink
  490c1650  relay provenance regression coverage
  c84a7927  Gate 7 entry provenance assertion
  51064ae9  replay provenance regression fixture
```

Earlier remediation commits for R64/R1/R3/R34/R46/R2/R33/R40/R41/R42/R50/R21/R23/R35/R51/R65 remain documented in `REVIEW_LATEST.md` and the remediation logs. Query current branch HEAD before editing.

The default Windows launcher remains:

```text
START_VR_HAND_TO_MUJOCO.bat
```

The default simulation controller remains:

```text
MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py
```

Current control scope is the G1 right arm. The simulation path is Unity/VR -> UDP 5005 -> strict source/session/freshness guards -> Mink differential QP/DAQP -> MuJoCo -> Unity state UDP 5006, with a separate Gate 7 candidate stream on UDP 5008. Physical Arm SDK and TWIST2 paths remain separate from the default simulation launcher.

## 3. Current review and remediation state

The precision review records findings R1-R67 and remains incomplete. Use [`REVIEW_LATEST.md`](REVIEW_LATEST.md) as the current index.

### Implemented / supported-path mitigations, pending broader validation

- **R64**: safety transitions are receive-batch barriers; later ACTIVE packets wait until the next poll.
- **R1/R3/R34**: shared release semantics and fail-closed release evidence are integrated on the relevant Gate 6/Gate 7 paths.
- **R46**: supported Jog launcher uses guarded result semantics; direct controller execution remains unsupported/open.
- **R2/R33/R41/R42**: supported Gate 7/Jog paths have final collision, acquisition freshness and permit/final-segment guards.
- **R40/R50**: partial supported-path full-body/runtime supervision exists; some base/remote/model/CRC concerns remain open.
- **R21/R51**: supported LowState startup paths use per-run forward tokens and provenance-bound prechecks.
- **R23**: hardware-sync BAT propagates child failure codes.
- **R35**: supported Gate 7 relay/adapter path uses a per-run relay token and retired-session tombstones.
- **R65**: Unity -> Mink path checks loopback/source identity, source-clock progress and backlog freshness; downstream packet age includes estimated source lag.
- **R15**: normalized replay is marked `recorded_replay`, live relay rejects replay/`replay-*`, canonical hardware-side packets are `live_mink`, and exact transport cannot target UDP 5008.

### R15 compatibility boundary

The current live Mink simulation packet does not yet originate with an explicit `command_provenance=live_mink` field. The Windows relay temporarily accepts a missing provenance field only when the session is not `replay-*`, then canonicalizes the downstream packet as `live_mink`.

Therefore the next provenance code change should be source-side protocol migration: make the live Mink producer itself emit `live_mink`, update its tests/consumers, then remove the relay's missing-provenance compatibility allowance.

### Verification boundary

Regression tests for the remediation work are committed but **have not been run from a checked-out current repository or GitHub Actions during this remediation session**.

No Unity Play, Quest runtime, WSL/DDS runtime or G1 command test has been performed for these provenance commits. Repository hardware authorization remains locked.

## 4. Coverage ledger

`logs/review/20260903/source_checks.csv` is the original bounded snapshot: 117 `full_text_review`, 147 `static_only`. It does not include the later R20-R67 continuation/remediation work and must not be quoted as current effective coverage.

Post-snapshot implementation/review deltas are recorded in:

```text
logs/review/20260903/source_checks_delta_20260904.csv
```

The canonical CSV count still requires deliberate regeneration from the current branch. `docs/CODE_INDEX.md` is also stale after remediation additions and must be regenerated before using its hashes as current evidence.

## 5. Hardware and environment boundary

- Repository hardware authorization remains locked.
- Do not assume G1 Ethernet, WSL DDS, Unity, Quest or any publisher is currently running. Verify current process/network state before use.
- Read-only LowState tools and physical-output tools must remain clearly separated.
- No physical command, G1 file mutation, service/mode change or administrator network change is authorized by this handoff.
- Preserve measured wrist calibration and any intentional local work; inspect `git status`, stash contents and diffs before reset, restore or cleanup.

## 6. Historical handoff

The complete pre-remediation handoff history was preserved at:

[`CHAT_HANDOFF_HISTORY_20260903.md`](CHAT_HANDOFF_HISTORY_20260903.md)

Use it for historical decisions, prior test logs, WSL setup, Unity crash investigation and older checkpoints. Current work should follow this concise file, `REVIEW_LATEST.md` and the remediation documents first.
