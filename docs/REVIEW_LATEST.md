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
- [`REMEDIATION_20260904.md`](REMEDIATION_20260904.md): R64/release batch
- [`REMEDIATION_20260904_CONTINUATION.md`](REMEDIATION_20260904_CONTINUATION.md): R2/R33/R40/R41/R42 supported-path mitigation
- [`REMEDIATION_20260904_RUNTIME_SUPERVISION.md`](REMEDIATION_20260904_RUNTIME_SUPERVISION.md): R50 runtime supervision
- [`REMEDIATION_20260904_PROVENANCE.md`](REMEDIATION_20260904_PROVENANCE.md): R15/R21/R23/R35/R51/R65 provenance/freshness
- [`REMEDIATION_20260904_STATE_BINDING.md`](REMEDIATION_20260904_STATE_BINDING.md): R40 base/model/config binding

The review is still incomplete. A file appearing in the index or static ledger is not thereby fully reviewed or correct.

## Coverage ledger status

`logs/review/20260903/source_checks.csv` remains the old bounded snapshot with 117 `full_text_review` and 147 `static_only` entries. Later review/remediation work has not been folded into that canonical count. Do not quote 117/264 as current effective coverage. `docs/CODE_INDEX.md` is also stale after the remediation additions.

## Remediation status

| Finding | Status | Current evidence |
| --- | --- | --- |
| R64 | IMPLEMENTED; integration validation pending | Command-ingress current-checkout CI PASS |
| R1 | IMPLEMENTED; integration/physical validation pending | Release regression PASS in offline safety CI |
| R3 | IMPLEMENTED; integration/physical validation pending | Gate 6 interruption/fault regression PASS |
| R34 | IMPLEMENTED; integration/physical validation pending | Gate 6 fault-release regression PASS |
| R46 | SUPPORTED-LAUNCHER MITIGATION; direct controller open | Wrapper/result tests PASS; direct core integration still open |
| R2 | SUPPORTED GATE 7 PATH MITIGATED; core path open | Final-segment collision guard tests PASS |
| R41 | SUPPORTED GATE 7 PATH MITIGATED; core parser open | Active-clearance and entry tests PASS |
| R33 | SUPPORTED GATE 7 PATH MITIGATED; core live adapter open | Acquisition freshness/order tests PASS |
| R40 | PARTIAL SUPPORTED-PATH MITIGATION | 29-joint binding + precheck base evidence + model/config/source hashes; live base rebinding remains open |
| R42 | SUPPORTED JOG PATH MITIGATED; direct controller open | Permit/full-body/final-segment tests PASS |
| R50 | PARTIAL SUPPORTED-PATH MITIGATION | IMU/motor health tests PASS; base/remote/CRC remain open |
| R21 | SUPPORTED HARDWARE-SYNC PATH MITIGATED | Startup provenance tests PASS |
| R51 | SUPPORTED PHYSICAL STARTUP PATHS MITIGATED | Per-run token/precheck tests PASS |
| R23 | IMPLEMENTED; process validation pending | Static failure-propagation assertion PASS; BAT process run pending |
| R35 | SUPPORTED GATE 7 RELAY PATH MITIGATED | Relay token/retired-session tests PASS |
| R65 | SUPPORTED UNITY/MINK PATH MITIGATED | Source clock/backlog/sender tests PASS |
| R15 | SOURCE MITIGATION COMPLETE ON SUPPORTED LIVE PATH; runtime validation pending | Live/replay/relay/hardware provenance tests PASS |

## Current-checkout offline CI

Two robot-offline workflows are now active on `main`.

```text
.github/workflows/offline-provenance-regression.yml
Run 33822226143 : PASS
```

This covers 54 tests across backend command ingress, Unity source-clock/backlog provenance, Gate 7 relay/replay/hardware provenance, startup provenance/state binding, and live Mink producer provenance.

```text
.github/workflows/offline-safety-regression.yml
Run 33822295391 : PASS
```

This covers 44 unittest cases plus the Gate 6 interruption-release offline contract script across shared/Gate 6 release, Gate 7 release/acquisition/final collision guards, LowState health supervision, and Jog safety/result boundaries.

Both workflows are offline from the robot: no Unitree publisher, DDS endpoint, WSL runtime, Unity/Quest runtime or G1 connection is created.

## Current priority groups

```text
1. R50 remaining runtime evidence: live base/odometry, remote/deadman, CRC/integrity where SDK fields are verified
2. R46 direct Jog controller release integration
3. R40 remaining live base-state publisher-boundary rebinding
4. Simulation/WSL integration checks after offline suites remain green
5. Canonical review-ledger/CODE_INDEX regeneration and remaining static-only file review
```

Do not expand physical testing yet. Offline regression coverage is now materially broader, but R40/R50 and direct R46 still contain open physical-path boundaries.

## Safety boundary

- Repository hardware authorization remains locked.
- No physical G1 command is authorized by a review or remediation commit.
- No G1 file, service, mode or state may be mutated without explicit approval for that exact action.
- Unit, process, simulation and physical verification must remain separately labeled.
