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
- [`REMEDIATION_20260904_CONTINUATION.md`](REMEDIATION_20260904_CONTINUATION.md): Gate 7 collision/acquisition mitigation status

The review is incomplete. A file that appears in the code index or static ledger is not thereby fully reviewed or correct.

## Coverage ledger status

`logs/review/20260903/source_checks.csv` remains the original bounded audit snapshot with 117 `full_text_review` and 147 `static_only` entries. Later review/remediation work has not been folded into that canonical CSV count.

Do not quote 117/264 as current effective coverage. Use the detailed review documents and `logs/review/20260903/source_checks_delta_20260904.csv` for post-snapshot work. `docs/CODE_INDEX.md` is also stale after remediation additions and must be regenerated before its hashes are treated as current evidence.

## Remediation status

| Finding | Status | Primary commit | Verification boundary |
| --- | --- | --- | --- |
| R64 | IMPLEMENTED; integration validation pending | `187b3e2a44466653bc099327e0ace7f18dc7fcb0` | Tests committed; not executed from current checkout/CI |
| R1 | IMPLEMENTED; integration/physical validation pending | `cb5082e182b4f1f4404a3e57c1803cf3be9e9d5e` | Shared release contract integrated; tests not executed |
| R3 | IMPLEMENTED; integration/physical validation pending | `678b5d0bb6bd7518fa0c9864998999b7b13c1b5c` | Acquire interruption no longer jumps to max weight |
| R34 | IMPLEMENTED; integration/physical validation pending | `678b5d0bb6bd7518fa0c9864998999b7b13c1b5c` | Fault release records zero-tail evidence |
| R46 | SUPPORTED-LAUNCHER MITIGATION; direct controller open | `7b44656364cf469bdc4f70ea4c1c0c8171a4ae81` | WSL starter uses guarded result path; direct Python path unsupported |
| R2 | SUPPORTED GATE 7 PATH MITIGATED; core path open | `40e46d6538321034ab873ef189427c30b595e9f6` | Exact post-shaping frame/swept segment checked before publish on supported WSL entry |
| R41 | SUPPORTED GATE 7 PATH MITIGATED; core parser open | `40e46d6538321034ab873ef189427c30b595e9f6` | ACTIVE samples require finite clearance on supported WSL entry |
| R33 | SUPPORTED GATE 7 PATH MITIGATED; core live adapter open | `1b159819c1da97379f5db5c115de7abf5ce5bcd8` | Multiple ordered ACTIVE samples required before publisher; freshness checked during acquire |
| R40 | PARTIAL SUPPORTED-PATH MITIGATION | `df26873d1246da8de2aaa1b707a238754050757a` | All 29 joint positions bound to precheck; base/IMU/model binding still open |

The committed regression tests above have not been run by GitHub Actions or a checked-out current branch during this remediation session. No status in this table is a physical validation result.

## Current priority groups

```text
release/fault finalization : direct R46 integration remains; R1/R3/R34 implemented pending validation
safety-event preservation  : R64 implemented pending integration validation
final/acquire validation   : R42 remains primary; R2/R41/R33 mitigated on supported path; R40 partial
runtime state supervision  : R50
provenance/freshness       : R15, R21, R35, R51, R52, R65
```

The immediate P1 implementation target is R42: bind the Jog permit to model/validator provenance, collision-relevant full-body state and the final command segment. R40 base/IMU/model binding remains open and should be handled with R50 rather than pretending the 29-joint wrapper closes it.

## Safety boundary

- Repository hardware authorization remains locked.
- No physical G1 command is authorized by a review or remediation commit.
- No G1 file, service, mode or state may be mutated without explicit approval for that exact action.
- Unit, process, simulation and physical verification must remain separately labeled.
