# G1 Teleop Project Chat Handoff

> **Absolute G1 mutation rule:** Never create, delete, rename, move, or modify any file on the G1; never run a program that can create a log, publish a command, change a service or mode, or otherwise mutate G1 state without the user's explicit approval for that exact action. Inspect source before running diagnostics. Remote-to-local copy is allowed only when it reads existing G1 files and writes exclusively to the Windows project.

Last updated: 2026-09-04

## 1. Start here

For every new project conversation:

1. Read this file.
2. Read [`ARCHITECTURE.md`](ARCHITECTURE.md).
3. Read [`REVIEW_LATEST.md`](REVIEW_LATEST.md) and the detailed review documents it links.
4. Read the remediation logs before changing a reviewed defect.
5. Read [`CODE_GUIDE.md`](CODE_GUIDE.md) before changing a control path.
6. Inspect the current branch and HEAD before editing.
7. Keep review findings, production changes and physical tests in separate commits and reports.
8. Update this handoff after a meaningful implementation or verification milestone.

Do not remove safety checks, loosen limits or change gains merely to make a test pass. Do not treat unit, static, simulation or transport tests as physical validation.

## 2. Repository checkpoint

```text
Repository : Y1048/Y
Branch     : refactor/teleop-architecture
Recent R15/CI chain:
  5c3e0a85  live Mink provenance helper
  e25de6e7  virtual-center provenance entrypoint
  c264d3ad  baseline provenance entrypoint
  9e2ad167  root launcher uses provenance entrypoints
  fb40acca  relay requires explicit live_mink
  0c83d080  strict relay regression update
  983ca9b4  producer provenance regression coverage
  0e1afbda  add offline provenance GitHub Actions workflow
  26e25d1c  keep relay packet below 1400-byte MTU budget
  31c7e003  scope CI workflow to relevant paths
```

Query current branch HEAD before editing; later documentation commits may be at the tip.

The default Windows launcher remains:

```text
START_VR_HAND_TO_MUJOCO.bat
```

It now launches:

```text
MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py
```

which marks Gate 7 candidate packets `command_provenance=live_mink` before delegating to the existing virtual-center controller. `--baseline` uses the corresponding prototype entrypoint.

## 3. Current remediation state

The precision review records R1-R67 and is still incomplete. `REVIEW_LATEST.md` is the current status index.

Important current state:

- **R15** supported live producer -> relay -> WSL hardware provenance is source-mitigated. Missing provenance and recorded replay are rejected at the live relay; exact replay cannot target UDP 5008.
- **R35** supported relay/adapter path has a per-run relay token plus retired-session tombstones.
- **R65** Unity -> Mink command input checks loopback/source identity, source-clock progress and estimated backlog age.
- **R21/R51** supported LowState startup/precheck paths use per-run forward tokens.
- **R64** safety events remain receive-batch barriers.
- **R40/R50** remain partial P1 work. Full base/model/state binding and broader runtime supervision are not closed.
- **R46** direct Jog controller release integration remains open; supported launcher mitigation exists.

## 4. Offline regression evidence

Workflow:

```text
.github/workflows/offline-provenance-regression.yml
```

The first current-checkout run (`33819076146`) failed because provenance+relay-token metadata pushed the canonical Gate 7 UDP packet beyond the existing 1400-byte no-fragmentation budget. That was a useful regression finding, not ignored.

Commit `26e25d1c620243c86a031812c05ba0034368fcf4` kept the 1400-byte cap and changed relay-only joint serialization from 10 to 7 decimal places. The right-arm values are copied from the same rounded 29-joint array, so parser consistency is maintained.

Runs `33819176285` and `33819253842` both passed. The workflow executes **54 tests** covering backend command ingress, source-clock backlog freshness, Gate 7 relay/replay provenance, startup provenance guards and live Mink producer provenance.

This CI is robot-offline. It creates no Unitree publisher, no DDS endpoint, no WSL runtime and no G1 connection. Unity/Quest and physical behavior remain unvalidated by this CI.

## 5. Immediate next work

```text
1. R40: close remaining publisher-boundary full-state/model binding gaps.
2. R50: extend runtime supervision to remaining base/remote/CRC concerns where supported evidence exists.
3. R46: integrate shared release semantics into the direct Jog controller, not only the wrapper.
4. Expand offline release/collision regression coverage.
5. Only then plan separate simulation/WSL integration checks.
```

Do not expand physical testing yet.

## 6. Coverage ledger

`logs/review/20260903/source_checks.csv` is the old bounded snapshot and must not be quoted as current effective coverage. Post-snapshot changes are tracked in:

```text
logs/review/20260903/source_checks_delta_20260904.csv
```

`docs/CODE_INDEX.md` is stale after the remediation additions and should be regenerated before relying on its hashes.

## 7. Hardware boundary

- Repository hardware authorization remains locked.
- Do not assume G1 Ethernet, WSL DDS, Unity, Quest or any publisher is running.
- Read-only LowState tools and physical-output tools remain separate.
- No physical command, G1 file mutation, service/mode change or administrator network change is authorized by this handoff.
- Preserve wrist calibration and intentional local work; inspect Git state before cleanup/reset/restore.

## 8. Historical handoff

Historical detail remains in [`CHAT_HANDOFF_HISTORY_20260903.md`](CHAT_HANDOFF_HISTORY_20260903.md). Use current handoff + `REVIEW_LATEST.md` first.
