# Remediation log — LowState provenance and launcher status

Date: 2026-09-04  
Branch: `refactor/teleop-architecture`

This document records source remediation separately from runtime/physical validation.

## R21 — initial hardware seed provenance

Core receiver implementation:

```text
e4642f13fce944c6b8cabe24512f3ce0aa81f93b
fix: validate initial LowState freshness and provenance (R21)
```

`receive_initial_state.py` now requires the canonical read-only LowState schema, strict session/sequence/timestamp fields, complete 29-joint q/dq consistency and bounded packet age. It can require an exact per-run `forward_token` and stores only a boolean verification result, not the nonce itself.

The supported hardware-sync launcher now creates a new UUID-hex token for each run, passes it to `read_only_lowstate_entry.py`, requires the same token in `receive_initial_state.py`, and terminates only the forwarder carrying that token after snapshot acquisition.

Launcher integration commit:

```text
3171c2ceb9ced6b5c8488bb46dbb22a3ef97df67
fix: bind hardware pose sync to per-run LowState token (R21 R51)
```

Status:

```text
R21 supported hardware-sync path : MITIGATED
R21 generic receiver without --expected-forward-token : lower-provenance/manual mode remains possible
Runtime validation               : NOT RUN
Physical validation              : NOT RUN
```

## R51 — startup precheck source binding

Added:

```text
hardware/g1_arm_bridge/check_startup_readiness_entry.py
hardware/g1_arm_bridge/precheck_provenance_guard.py
```

The supported precheck entrypoint requires `--expected-forward-token`. It accepts a LowState packet only if the packet contains that exact nonce before the canonical Gate 5 parser is allowed to accept it. The resulting precheck artifact records:

```text
lowstate_forward_provenance.mode = per_run_token
lowstate_forward_provenance.forward_token_verified
lowstate_forward_provenance.verified_packet_count
```

The token value itself is not persisted.

Supported launchers now create a fresh token and use it at both ends of the read-only UDP bridge:

```text
tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat
tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat
tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat
tools/START_G1_GATE7_LIVE_HARDWARE.bat
```

Each launcher also terminates the exact read-only process by matching `read_only_lowstate_entry.py` plus that run token. This corrects the stale cleanup pattern that still targeted `read_only_lowstate.py` after the supported entrypoint was introduced.

Physical consumers additionally reject a startup-precheck JSON unless its token provenance is present and verified:

```text
hardware/g1_arm_bridge/gate6_arm_sdk_hold_entry.py
hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py
hardware/g1_arm_bridge/g1_right_arm_jog_entry.py
```

This prevents replacing the newly generated precheck with an older, non-token-bound `DIRECT_TELEOP_READY` artifact on supported physical paths.

Representative commits:

```text
1ac4d5f4306a4685bc3455b4ac4a53674de2fdae  supported precheck token entry
5b372308626fa7dfa3c15f85bb80b28f54ae69d4  physical precheck provenance guard
fd95d5d3a6938cfa48d4006b3b162f785b2d59f0  Jog launcher token binding
cec4dfe1c38325e7e29042b147db98fdcd4eabfa  shoulder launcher token binding
930d2ee4dbdff5331eff87ed7ac4ded2d23c499e  Gate 6 launcher token binding
19e48786e81f76c3a4c320e70529f7c429b256a1  Gate 7 launcher token binding
```

Status:

```text
R51 supported physical launchers : MITIGATED with per-run nonce
R51 generic check_startup_readiness.py direct path : OPEN / lower provenance
Sender-IP binding                : not required on supported token path
Cryptographic authentication     : NOT PROVIDED; token is process-run provenance, not a secret/auth protocol
Runtime validation               : NOT RUN
Physical validation              : NOT RUN
```

## R23 — hardware-sync launcher exit status

The hardware-sync launcher previously printed failures but could reach the end without explicitly returning the failed child status. It now preserves the snapshot receiver, pose verifier and controller return codes and exits with the selected `RC`.

Commit:

```text
b35c24a8baa8405bf2825b4d51cb40651bb6a303
fix: propagate hardware-sync launcher failures (R23)
```

Status:

```text
R23 source fix             : IMPLEMENTED
Process-level BAT execution: NOT RUN
```

## Regression tests added

```text
hardware/g1_arm_bridge/test_check_startup_readiness_entry.py
hardware/g1_arm_bridge/test_precheck_provenance_guard.py
hardware/g1_arm_bridge/test_lowstate_provenance_launchers.py
hardware/g1_arm_bridge/test_physical_precheck_provenance_entries.py
```

These tests have been committed but **have not been executed from a checked-out current branch or GitHub Actions in this remediation session**.

## Remaining provenance work

The next live-command provenance group remains:

```text
R35 — Gate 7 relay/adapter source ownership and retired-session replay
R65 — Unity→Mink sender identity, source timestamp and receive/backlog freshness
R15 — recorded/replayed command provenance where applicable
```

No hardware authorization flag was changed by this batch, and no G1/WSL/Unity runtime was started.
