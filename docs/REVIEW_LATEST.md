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
- [`REMEDIATION_20260904.md`](REMEDIATION_20260904.md): implementation and verification status

The review is incomplete. A file that appears in the code index or static ledger is not thereby fully reviewed or correct.

## Coverage ledger status

`logs/review/20260903/source_checks.csv` remains the original bounded audit snapshot with 117 `full_text_review` and 147 `static_only` entries. The continuation reviews R20-R67 were recorded after that snapshot and have not yet been folded into the canonical CSV count.

Do not quote 117/264 as the current effective review coverage. Use the detailed review documents above plus `logs/review/20260903/source_checks_delta_20260904.csv` for post-snapshot work. Exact count regeneration is a separate review-administration task and must not be mixed with production safety fixes.

## Remediation status

| Finding | Status | Commit | Verification boundary |
| --- | --- | --- | --- |
| R64 | IMPLEMENTED; integration validation pending | `187b3e2a44466653bc099327e0ace7f18dc7fcb0` | Regression tests committed; not executed from a repository checkout |
| R1 | IMPLEMENTED; integration/physical validation pending | `cb5082e182b4f1f4404a3e57c1803cf3be9e9d5e` | Shared release contract integrated; committed tests not executed |
| R3 | IMPLEMENTED; integration/physical validation pending | `678b5d0bb6bd7518fa0c9864998999b7b13c1b5c` | Acquire interruption no longer jumps to maximum weight; committed tests not executed |
| R34 | IMPLEMENTED; integration/physical validation pending | `678b5d0bb6bd7518fa0c9864998999b7b13c1b5c` | Fault release records zero-tail evidence; committed tests not executed |
| R46 | SUPPORTED-LAUNCHER MITIGATION; direct controller path still open | `7b44656364cf469bdc4f70ea4c1c0c8171a4ae81` | WSL starter now uses a fail-closed result guard; direct `g1_right_arm_jog.py` physical execution remains unsupported |

Important verification correction: an earlier handoff entry stated that 18 committed R64 command-ingress tests had passed. Those committed tests were not actually run from a checked-out repository in this remediation session. That statement is superseded by `REMEDIATION_20260904.md`.

## Current priority groups

```text
release/fault finalization : R1/R3/R34 implemented pending validation; R46 internal integration still open
safety-event preservation  : R64 implemented pending integration validation
final/acquire validation   : R2, R33, R40, R41, R42
runtime state supervision  : R50
provenance/freshness       : R15, R21, R35, R51, R52, R65
```

The next production work should return to the P1 final/acquisition group. R2 and R41 are tightly related collision-evidence issues, while R33/R40/R42 cover publisher-boundary state binding. Keep R46 direct-controller integration on the remediation backlog rather than broadening physical trials.

## Safety boundary

- Repository hardware authorization remains locked.
- No physical G1 command is authorized by a review or remediation commit.
- No G1 file, service, mode or state may be mutated without explicit approval for that exact action.
- Unit, process, simulation and physical verification must remain separately labeled.
