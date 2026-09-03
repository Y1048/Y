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
- [`REMEDIATION_20260904.md`](REMEDIATION_20260904.md): R64/release batch implementation status
- [`REMEDIATION_20260904_CONTINUATION.md`](REMEDIATION_20260904_CONTINUATION.md): R2/R33/R40/R41/R42 supported-path mitigation
- [`REMEDIATION_20260904_RUNTIME_SUPERVISION.md`](REMEDIATION_20260904_RUNTIME_SUPERVISION.md): R50 supported-path runtime supervision
- [`REMEDIATION_20260904_PROVENANCE.md`](REMEDIATION_20260904_PROVENANCE.md): R15/R21/R23/R35/R51/R65 provenance and freshness status

The review is incomplete. A file that appears in the code index or static ledger is not thereby fully reviewed or correct.

## Coverage ledger status

`logs/review/20260903/source_checks.csv` remains the original bounded audit snapshot with 117 `full_text_review` and 147 `static_only` entries. Later review/remediation work has not been folded into that canonical CSV count.

Do not quote 117/264 as current effective coverage. Use the detailed review/remediation documents and `logs/review/20260903/source_checks_delta_20260904.csv` for post-snapshot work. `docs/CODE_INDEX.md` is stale after remediation additions and must be regenerated before its hashes are treated as current evidence.

## Remediation status

| Finding | Status | Verification boundary |
| --- | --- | --- |
| R64 | IMPLEMENTED; integration validation pending | Command-ingress regression subset PASS in current-checkout CI |
| R1 | IMPLEMENTED; integration/physical validation pending | Release tests exist; not part of current provenance workflow |
| R3 | IMPLEMENTED; integration/physical validation pending | Release tests exist; not part of current provenance workflow |
| R34 | IMPLEMENTED; integration/physical validation pending | Release tests exist; not part of current provenance workflow |
| R46 | SUPPORTED-LAUNCHER MITIGATION; direct controller open | Direct-controller release integration remains open |
| R2 | SUPPORTED GATE 7 PATH MITIGATED; core path open | Collision guard tests committed; broader collision suite pending |
| R41 | SUPPORTED GATE 7 PATH MITIGATED; core parser open | Supported Gate 7 provenance/entry static tests PASS |
| R33 | SUPPORTED GATE 7 PATH MITIGATED; core live adapter open | Supported entry static tests PASS; runtime acquire test pending |
| R40 | PARTIAL SUPPORTED-PATH MITIGATION | All 29 joints bound; base/IMU/model parts remain open |
| R42 | SUPPORTED JOG PATH MITIGATED; direct controller open | Permit/final-segment tests committed; broader suite pending |
| R50 | PARTIAL SUPPORTED-PATH MITIGATION | IMU/motor guard source exists; base/remote/CRC remain open |
| R21 | SUPPORTED HARDWARE-SYNC PATH MITIGATED | Startup provenance static subset PASS; generic no-token path lower provenance |
| R51 | SUPPORTED PHYSICAL STARTUP PATHS MITIGATED | Token/precheck guard tests PASS in current-checkout CI |
| R23 | IMPLEMENTED; process validation pending | Static launcher failure-propagation assertion PASS; BAT process run pending |
| R35 | SUPPORTED GATE 7 RELAY PATH MITIGATED | Relay token/retired-session tests PASS in current-checkout CI |
| R65 | SUPPORTED UNITY/MINK PATH MITIGATED | Source clock/backlog/sender tests PASS in current-checkout CI |
| R15 | SOURCE MITIGATION COMPLETE ON SUPPORTED LIVE PATH; runtime validation pending | Live producer/replay/relay/hardware provenance tests PASS in current-checkout CI |

## Current-checkout offline CI

Workflow:

```text
.github/workflows/offline-provenance-regression.yml
```

Run 1 exposed a real regression: after adding command provenance and relay nonce, the canonical UDP relay packet exceeded the existing 1400-byte no-fragmentation budget. The code was corrected by preserving the 1400-byte limit and serializing relay joint values to 7 decimal places, still below microradian resolution.

Runs 2 and 3 passed. The passing workflow executes **54 tests** across:

```text
backend command ingress
Unity source-clock/backlog provenance
Gate 7 relay/replay/hardware provenance
startup LowState/precheck provenance guards
live Mink producer provenance
```

This workflow is offline from the robot: no Unitree publisher, DDS endpoint, WSL runtime, Unity/Quest runtime or G1 connection is created.

## Current priority groups

```text
1. Remaining partial P1 state binding/supervision: R40, R50
2. Direct Jog release integration: R46
3. Broader release/collision regression suite: R1/R2/R3/R34/R41/R42/R64
4. Simulation/WSL integration checks after offline suites stay green
```

Do not expand physical testing yet. The provenance subgroup now has current-checkout offline evidence, but the remaining R40/R50 gaps and direct R46 path are still open.

## Safety boundary

- Repository hardware authorization remains locked.
- No physical G1 command is authorized by a review or remediation commit.
- No G1 file, service, mode or state may be mutated without explicit approval for that exact action.
- Unit, process, simulation and physical verification must remain separately labeled.
