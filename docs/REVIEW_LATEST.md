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
- [`REMEDIATION_20260904_PROVENANCE.md`](REMEDIATION_20260904_PROVENANCE.md): R21/R23/R51 LowState provenance and launcher status

The review is incomplete. A file that appears in the code index or static ledger is not thereby fully reviewed or correct.

## Coverage ledger status

`logs/review/20260903/source_checks.csv` remains the original bounded audit snapshot with 117 `full_text_review` and 147 `static_only` entries. Later review/remediation work has not been folded into that canonical CSV count.

Do not quote 117/264 as current effective coverage. Use the detailed review/remediation documents and `logs/review/20260903/source_checks_delta_20260904.csv` for post-snapshot work. `docs/CODE_INDEX.md` is stale after remediation additions and must be regenerated before its hashes are treated as current evidence.

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
| R40 | PARTIAL SUPPORTED-PATH MITIGATION | `df26873d1246da8de2aaa1b707a238754050757a` | All 29 joints bound; base/IMU/model parts remain open |
| R42 | SUPPORTED JOG PATH MITIGATED; direct controller open | `22cd0cf4849747a1e6d7580ab3070f916028f835` | Permit hashes config/code/model; selected-joint ticks check all 29 joints and final swept collision segment |
| R50 | PARTIAL SUPPORTED-PATH MITIGATION | `95810e0fb6ae55fefc814cbbb8eefb9cd7b902f5` | Gate6/Gate7/Jog entries supervise IMU tilt and motor temp/fault/tau finiteness; base/remote/CRC remain open |
| R21 | SUPPORTED HARDWARE-SYNC PATH MITIGATED | `e4642f13fce944c6b8cabe24512f3ce0aa81f93b` + `3171c2ceb9ced6b5c8488bb46dbb22a3ef97df67` | Canonical/fresh initial state plus per-run forward token; generic no-token mode remains lower provenance |
| R51 | SUPPORTED PHYSICAL STARTUP PATHS MITIGATED | `1ac4d5f4306a4685bc3455b4ac4a53674de2fdae` + launcher commits | Fresh UUID token binds forwarder, startup precheck and physical precheck consumers; tests not executed |
| R23 | IMPLEMENTED; process validation pending | `b35c24a8baa8405bf2825b4d51cb40651bb6a303` | Hardware-sync BAT now propagates snapshot/verify/controller return code; BAT not executed |

The committed regression tests above have not been run by GitHub Actions or a checked-out current branch during this remediation session. No status in this table is a physical validation result.

## Current priority groups

```text
release/fault finalization : direct R46 integration remains; R1/R3/R34 implemented pending validation
safety-event preservation  : R64 implemented pending integration validation
final/acquire validation   : R2/R33/R41/R42 mitigated on supported paths; R40 partial
runtime state supervision  : R50 partial; base/remote/CRC still open
startup provenance         : R21/R51 supported paths mitigated; generic direct paths remain lower provenance
live command provenance    : R35, R65, R15
```

The next implementation group is live command provenance/freshness. R35 concerns relay→Gate 7 ownership and retired-session replay; R65 concerns Unity→Mink sender identity, source timing and backlog freshness. Keep the current hardware locks in place while addressing those paths.

## Safety boundary

- Repository hardware authorization remains locked.
- No physical G1 command is authorized by a review or remediation commit.
- No G1 file, service, mode or state may be mutated without explicit approval for that exact action.
- Unit, process, simulation and physical verification must remain separately labeled.
