# Remediation log — command and LowState provenance

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

The supported hardware-sync launcher creates a new UUID-hex token for each run, passes it to `read_only_lowstate_entry.py`, requires the same token in `receive_initial_state.py`, and terminates only the forwarder carrying that token after snapshot acquisition.

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

Supported launchers create a fresh token and use it at both ends of the read-only UDP bridge:

```text
tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat
tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat
tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat
tools/START_G1_GATE7_LIVE_HARDWARE.bat
```

Physical consumers additionally reject a startup-precheck JSON unless its token provenance is present and verified:

```text
hardware/g1_arm_bridge/gate6_arm_sdk_hold_entry.py
hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py
hardware/g1_arm_bridge/g1_right_arm_jog_entry.py
```

This prevents replacing the newly generated precheck with an older, non-token-bound `DIRECT_TELEOP_READY` artifact on supported physical paths.

Status:

```text
R51 supported physical launchers : MITIGATED with per-run nonce
R51 generic check_startup_readiness.py direct path : OPEN / lower provenance
Cryptographic authentication     : NOT PROVIDED; token is run provenance, not a secret/auth protocol
Runtime validation               : NOT RUN
Physical validation              : NOT RUN
```

## R23 — hardware-sync launcher exit status

The hardware-sync launcher now preserves snapshot receiver, pose verifier and controller return codes and exits with the selected nonzero `RC` instead of falling through to a successful batch exit.

Status:

```text
R23 source fix             : IMPLEMENTED
Process-level BAT execution: NOT RUN
```

## R35 — Gate 7 relay/adapter source ownership

The supported Gate 7 physical launcher creates a separate per-run `GATE7_RELAY_TOKEN`. The Windows UDP 5008 -> WSL UDP 5013 relay requires the token for live operation, and the supported WSL hardware entry requires the exact same token before command parsing.

Both relay and hardware entry use a bounded retired-session tombstone guard. If ownership changes from session A to B, delayed A traffic cannot later regain command ownership during that same process lifetime.

Status:

```text
R35 supported relay/adapter path : MITIGATED
Direct/custom UDP 5013 consumers : outside supported path
Cryptographic authentication     : NOT PROVIDED
Runtime validation               : NOT RUN
Physical validation              : NOT RUN
```

## R65 — Unity -> Mink sender/source-clock freshness

The legacy Unity packet already carries `timestamp=Time.realtimeSinceStartupAsDouble` and `source=quest3s_head_relative`. The Python adapter now preserves that source clock instead of replacing it with `None`.

A new `CommandSourceGuard` validates the expected loopback sender/source, source timestamp monotonicity, session ordering and retired sessions. It does not subtract Unity's clock epoch from Python monotonic time. Instead it anchors the first source/local arrival pair and compares elapsed source-clock progress with elapsed local-arrival progress. Excess lag therefore exposes controller pause/backlog without requiring synchronized clock epochs.

`live_receiver.py` records arrival time immediately after `recvfrom`, before JSON parsing. `MinkCommandStream` adds estimated source backlog to the downstream `input_packet_age_s` so Gate 7 does not receive a freshly rewrapped age for an old Unity input.

Status:

```text
R65 supported Unity/Mink command path : MITIGATED
Cross-machine clock synchronization   : not required by current elapsed-time method
Runtime validation                    : NOT RUN
Unity/Quest validation                : NOT RUN
```

## R15 — recorded replay vs live command provenance

Normalized `gate7_mink_replay.py` traffic now carries:

```text
command_provenance = recorded_replay
session_id          = replay-...
```

The supported Windows live relay rejects explicit `recorded_replay` packets and legacy `replay-*` sessions before forwarding. Accepted live candidates are canonicalized at the relay boundary as:

```text
command_provenance = live_mink
```

The supported WSL Gate 7 hardware entry independently requires `live_mink` in addition to the per-run relay token.

`gate7_mink_replay.py --exact-transport` can no longer target the live relay on UDP 5008. Exact transport remains available only on a dedicated offline replay port.

Compatibility boundary: the current simulation controller's UDP 5008 packet predates the explicit `command_provenance` field. The Windows relay therefore accepts a missing provenance field only as a compatibility case when the session is not `replay-*`, then emits canonical `live_mink` downstream. A later packet-contract migration should make the live Mink producer itself emit `live_mink` and remove this allowance.

Status:

```text
R15 supported physical relay path : MITIGATED
Live Mink source packet explicit provenance : PARTIAL / compatibility allowance remains
Normalized replay into live relay : BLOCKED
Exact-transport replay into UDP 5008 : BLOCKED
Runtime validation : NOT RUN
Physical validation: NOT RUN
```

## Regression coverage added/updated

```text
hardware/g1_arm_bridge/test_check_startup_readiness_entry.py
hardware/g1_arm_bridge/test_precheck_provenance_guard.py
hardware/g1_arm_bridge/test_lowstate_provenance_launchers.py
hardware/g1_arm_bridge/test_physical_precheck_provenance_entries.py
hardware/g1_arm_bridge/test_gate7_mink_wsl_relay.py
hardware/g1_arm_bridge/test_gate7_live_entrypoint.py
hardware/g1_arm_bridge/test_gate7_replay_provenance.py
backend/tests/test_source_provenance.py
backend/tests/test_mink_command_stream.py
```

Coverage includes LowState token mismatch, stale/non-provenance prechecks, wrong command sender/source, source-clock backlog, retired A -> B -> A sessions, Gate 7 relay-token mismatch, explicit replay rejection and exact-transport/live-port rejection.

## Verification boundary

The code and regression tests are committed, but they have **not** been executed from a checked-out current repository or GitHub Actions in this remediation session.

No Unity Play, Quest runtime, WSL DDS runtime or physical G1 command test was performed for this batch. Repository hardware authorization remains locked. No result in this document grants physical-output authorization.
