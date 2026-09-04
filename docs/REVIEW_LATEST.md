# Current review and remediation index

Last updated: 2026-09-04

This file is the current entry point for the precision review. It does not replace the detailed evidence in the linked review documents.

## Review record

- [`REVIEW_20260903.md`](REVIEW_20260903.md): R1-R19
- [`REVIEW_20260903_CONTINUATION.md`](REVIEW_20260903_CONTINUATION.md): R20-R32
- [`REVIEW_20260903_CONTINUATION_2.md`](REVIEW_20260903_CONTINUATION_2.md): R33-R39
- [`REVIEW_20260903_CONTINUATION_3.md`](REVIEW_20260903_CONTINUATION_3.md): R40-R49
- [`REVIEW_20260903_CONTINUATION_4.md`](REVIEW_20260903_CONTINUATION_4.md): R50-R59
- [`REVIEW_20260903_CONTINUATION_5.md`](REVIEW_20260903_CONTINUATION_5.md): R60-R67
- [`REVIEW_20260904_BACKEND_CORE.md`](REVIEW_20260904_BACKEND_CORE.md): backend protocol/config/calibration/camera/runtime core review; no new finding, R27/R32 reconfirmed
- [`REVIEW_20260904_BACKEND_SUPPORT.md`](REVIEW_20260904_BACKEND_SUPPORT.md): inspection/admin/feedback/diagnostic helper review; R20 extended to `inspect_feasible_target_return.py`
- [`REMEDIATION_20260904.md`](REMEDIATION_20260904.md): R64/release batch
- [`REMEDIATION_20260904_CONTINUATION.md`](REMEDIATION_20260904_CONTINUATION.md): R2/R33/R40/R41/R42 supported-path mitigation
- [`REMEDIATION_20260904_RUNTIME_SUPERVISION.md`](REMEDIATION_20260904_RUNTIME_SUPERVISION.md): R40/R50 runtime supervision
- [`REMEDIATION_20260904_PROVENANCE.md`](REMEDIATION_20260904_PROVENANCE.md): R15/R21/R23/R35/R51/R65 provenance/freshness
- [`REMEDIATION_20260904_STATE_BINDING.md`](REMEDIATION_20260904_STATE_BINDING.md): R40 base/model/config binding
- [`REMEDIATION_20260904_DIRECT_JOG_RELEASE.md`](REMEDIATION_20260904_DIRECT_JOG_RELEASE.md): R46 direct-controller release integration

The review is still incomplete. A file appearing in the index or static ledger is not thereby fully reviewed or correct.

## Current reconciled coverage

The canonical bounded ledger and code index were regenerated from current `main` after the backend-support review batch.

```text
total current scoped files : 302
full_text_review           : 186
static_only                : 116
static check failures      : 0
```

Authoritative files:

```text
logs/review/20260903/source_checks.csv
logs/review/20260903/source_checks_summary_20260904.json
docs/CODE_INDEX.md
```

The semantic rule is deliberately conservative: prior decisions are preserved, explicit continuation deltas can promote a path to `full_text_review`, and newly discovered files default to `static_only`. Therefore 186/302 is a review-state count, not a correctness score.

## Remediation status

| Finding | Status | Current evidence |
| --- | --- | --- |
| R64 | IMPLEMENTED; integration validation pending | Command-ingress current-checkout CI PASS |
| R1 | IMPLEMENTED; integration/physical validation pending | Release regression PASS in offline safety CI |
| R3 | IMPLEMENTED; integration/physical validation pending | Gate 6 interruption/fault regression PASS |
| R34 | IMPLEMENTED; integration/physical validation pending | Gate 6 fault-release regression PASS |
| R46 | IMPLEMENTED IN DIRECT CONTROLLER; runtime/physical validation pending | Shared release finalizer integrated in `g1_right_arm_jog.py`; direct/wrapper release regressions PASS |
| R2 | SUPPORTED GATE 7 PATH MITIGATED; core path open | Final-segment collision guard tests PASS |
| R41 | SUPPORTED GATE 7 PATH MITIGATED; core parser open | Active-clearance and entry tests PASS |
| R33 | SUPPORTED GATE 7 PATH MITIGATED; core live adapter open | Acquisition freshness/order tests PASS |
| R40 | SUPPORTED PHYSICAL PATH SOURCE MITIGATION COMPLETE; physical validation pending | 29-joint/model/config binding plus raw startup/runtime `rt/odommodestate` position/quaternion continuity and live base stability checks |
| R42 | SUPPORTED JOG PATH MITIGATED; direct controller path still uses entry-installed collision/full-body guard | Permit/full-body/final-segment tests PASS |
| R50 | PARTIAL SUPPORTED-PATH MITIGATION | IMU/motor health + current runtime base/odometry stability PASS; remote/deadman/CRC remain open |
| R21 | SUPPORTED HARDWARE-SYNC PATH MITIGATED | Startup provenance tests PASS |
| R51 | SUPPORTED PHYSICAL STARTUP PATHS MITIGATED | Per-run token/precheck/raw-odom tests PASS |
| R23 | IMPLEMENTED; process validation pending | Static failure-propagation assertion PASS; BAT process run pending |
| R35 | SUPPORTED GATE 7 RELAY PATH MITIGATED | Relay token/retired-session tests PASS |
| R65 | SUPPORTED UNITY/MINK PATH MITIGATED | Source clock/backlog/sender tests PASS |
| R15 | SOURCE MITIGATION COMPLETE ON SUPPORTED LIVE PATH; runtime validation pending | Live/replay/relay/hardware provenance tests PASS |
| R20 | OPEN; additional surface confirmed | `inspect_feasible_target_return.py` can print/write `REVIEW_REQUIRED` while returning process success |
| R27 | OPEN | Full-text backend review reconfirmed that generic calibration/transform matrix boundaries do not enforce SO(3) |
| R32 | OPEN | Full-text backend review reconfirmed V1 direct protocol integer coercion differs from strict V2 |

## Current-checkout offline CI

Two robot-offline workflows are active on `main`.

```text
.github/workflows/offline-provenance-regression.yml
Run 33824261133 : PASS
```

This covers command ingress, Unity source-clock/backlog provenance, Gate 7 relay/replay/hardware provenance, startup token/state/raw-odometry binding, and live Mink producer provenance.

```text
.github/workflows/offline-safety-regression.yml
Run 33824155653 : PASS
```

This covers release finalization, Gate 7 collision/acquisition guards, LowState IMU/motor health, runtime base/odometry stability and startup/runtime odometry continuity, Jog safety/final-segment checks, and direct Jog shared-release integration.

Both workflows are offline from the robot: no Unitree publisher, DDS endpoint, WSL runtime, Unity/Quest runtime or G1 connection is created.

## Current priority groups

```text
1. Continue the 116 remaining static-only files, prioritizing remaining backend diagnostic tests/tools and launch/test surfaces
2. R20/R27/R32 remain known open backend-contract/tool issues; remediate separately from review bookkeeping
3. Do not invent R50 remote/deadman/CRC checks; verify actual read-only Unitree SDK fields first
4. Plan simulation/WSL integration checks with hardware output locked
5. Keep the reconciled ledger/CODE_INDEX current after each review batch
```

R40's source-side startup/runtime odometry continuity is closed on supported paths, but physical validation is not. Do not expand physical testing yet: actual connected-G1 SDK field compatibility, remote/deadman/CRC evidence, and WSL/DDS runtime behavior remain unverified.

## Safety boundary

- Repository hardware authorization remains locked.
- No physical G1 command is authorized by a review or remediation commit.
- No G1 file, service, mode or state may be mutated without explicit approval for that exact action.
- Unit, process, simulation and physical verification must remain separately labeled.
