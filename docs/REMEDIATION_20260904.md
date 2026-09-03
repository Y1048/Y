# Remediation log — 2026-09-04

Branch: `refactor/teleop-architecture`

This document records production fixes separately from the R1-R67 review documents. A finding is not treated as physically validated merely because its source fix and regression tests exist.

## Batch 1 — R64 safety-event preservation

Implementation commit:

```text
187b3e2a44466653bc099327e0ace7f18dc7fcb0
fix: preserve disengage events across UDP backlog (R64)
```

Changed:

- `backend/g1_teleop/live_receiver.py`
- `backend/g1_teleop/mink_command_stream.py`
- `backend/tests/test_live_receiver.py`
- `backend/tests/test_mink_command_stream.py`

Behavior after the change:

1. An accepted `workspace_exit`, `pinch_disengaged` or `tracking_disengaged` command terminates the current receive batch.
2. Datagrams behind that event remain queued for the next control poll.
3. An ACTIVE target accepted earlier in the same batch is cleared from `latest_active_command` when the safety barrier is reached.
4. `MinkCommandStream` does not replace its target or engage its clutch during a safety-reset update.
5. Session takeover remains separate and retains the existing zero-jump rebase policy.

Committed regression tests cover active → pinch → active and active → workspace-exit → active backlog cases. These committed repository tests have **not** been executed by GitHub Actions or a checked-out repository in this remediation session. The previous handoff text that stated 18 committed command-ingress tests had passed was too strong and is superseded by this document.

Status:

```text
R64 source fix             : IMPLEMENTED
Regression tests committed : YES
Committed tests executed   : NO
Full repository regression : PENDING
Unity/Gate 7 integration   : PENDING
Physical validation        : NOT AUTHORIZED / NOT RUN
```

## Batch 2 foundation — shared Arm SDK release contract

Commit:

```text
846b0d59991b6d84a47fca30255aef1343bdfa63
test: add SDK-neutral release finalization contract
```

Added:

- `hardware/g1_arm_bridge/arm_sdk_release_contract.py`
- `hardware/g1_arm_bridge/test_arm_sdk_release_contract.py`

The shared contract separates release evidence from Unitree SDK/DDS and records:

```text
release_attempted
release_ramp_completed
release_zero_frames_requested
release_zero_frames_sent
zero_release_completed
last_successful_weight
last_successful_write_unix_ns
release_fault
output_state_unknown
external_authority_handoff_confirmed
```

A ramp failure does not suppress the independent zero-tail attempt. `zero_release_completed=true` means the requested zero-weight frames were successfully passed through the caller's publish callback; it does **not** prove firmware ownership handback.

The pure helper logic was smoke-checked separately in the model execution environment. The committed test file itself has not yet been run from a repository checkout.

## Batch 2A — R1 Gate 7 release finalization

Implementation commit:

```text
cb5082e182b4f1f4404a3e57c1803cf3be9e9d5e
fix: make Gate 7 release fail-closed (R1)
```

Changed:

- `hardware/g1_arm_bridge/gate7_live_arm_sdk.py`
- `hardware/g1_arm_bridge/test_gate7_release_finalization.py`

Key changes:

- Gate 7 records the weight only **after** a successful `publisher.Write()`.
- Release starts from `last_successful_weight`, not merely the last calculated candidate.
- The finalizer uses the already-loaded Gate 7/hardware configuration instead of rereading files during release.
- Ramp failure is recorded but the zero-tail phase is still attempted independently.
- Release failure revokes `passed=true` and returns a nonzero process result.
- `command_output_enabled=false` is asserted only after a complete zero-weight tail; otherwise `output_state_unknown=true` remains visible.
- `external_authority_handoff_confirmed` remains false because no firmware/owner acknowledgement exists yet.

This directly addresses the original R1 false-PASS/result-reporting defect. It does not prove physical authority handback.

Status:

```text
R1 source fix              : IMPLEMENTED
Regression tests committed : YES
Committed tests executed   : NO
Physical validation        : NOT AUTHORIZED / NOT RUN
```

## Batch 2B — R3/R34 Gate 6 interruption and fault release

Implementation commit:

```text
678b5d0bb6bd7518fa0c9864998999b7b13c1b5c
fix: release Gate 6 faults from last published weight (R3 R34)
```

Changed:

- `hardware/g1_arm_bridge/gate6_arm_sdk_hold.py`
- `hardware/g1_arm_bridge/test_gate6_fault_release.py`

R3 changes:

- Ctrl+C during ACQUIRE no longer rewrites the release start to `maximum_weight`.
- Interrupted release begins from `min(current_calculated_weight, last_successful_weight)` and monotonically decreases from there.
- The old `0.02 → 0.2` authority increase path is removed.

R34 changes:

- The last successful transmitted weight/time and latest usable LowState snapshot are retained.
- Runtime faults after publisher creation invoke the shared SDK-neutral release sequence.
- Fault release uses the current/fallback measured arm pose rather than continuing to drive an old target.
- A ramp failure does not suppress the zero-tail attempt.
- Fault status reports `zero_release_completed`, `release_fault`, `last_successful_weight`, `output_state_unknown` and handback confirmation separately.
- If release cannot be proven complete, the status no longer claims command output is disabled.

Status:

```text
R3 source fix              : IMPLEMENTED
R34 source fix             : IMPLEMENTED
Regression tests committed : YES
Committed tests executed   : NO
Physical validation        : NOT AUTHORIZED / NOT RUN
```

## Batch 2C — R46 supported Jog entrypoint fail-closure

Implementation commits:

```text
7b44656364cf469bdc4f70ea4c1c0c8171a4ae81
fix: fail-close Jog release results on supported WSL path (R46)

4251c5438387719c83b2a50c7eb63789e93e95a1
test: verify supported Jog launcher uses guarded entry
```

Added/changed:

- `hardware/g1_arm_bridge/g1_right_arm_jog_entry.py`
- `hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh`
- `hardware/g1_arm_bridge/test_g1_right_arm_jog_entry.py`

The supported WSL physical launcher now executes `g1_right_arm_jog_entry.py`. The wrapper does not create a DDS entity itself; it delegates to the existing controller and intercepts only the final result write. It applies the following fail-closed result contract:

- `command_output_enabled=false` is allowed only when the configured zero-weight tail count was reached and no release error was recorded.
- An incomplete zero tail changes `output_state_unknown=true`, keeps `command_output_enabled=true`, and revokes `passed=true`.
- A recorded emergency release error keeps output state unknown even if a nominal zero-frame count is present.
- Fault runs may report `command_output_enabled=false` after a complete zero tail while still remaining `passed=false`.
- `external_authority_handoff_confirmed` remains false.

Important boundary: this is a **supported-launcher mitigation**, not yet a full internal refactor of `g1_right_arm_jog.py`. Directly invoking `g1_right_arm_jog.py` with an independently unlocked physical config still retains the original R46 result-writing logic. Supported physical BAT launchers route through `start_right_arm_jog_wsl.sh`, so their hardware execution path now passes through the guard. Direct physical execution of `g1_right_arm_jog.py` must remain unsupported until the controller itself adopts the shared release contract.

Status:

```text
R46 supported WSL path     : MITIGATED / FAIL-CLOSED RESULT GUARD
R46 direct Python path     : OPEN
Regression tests committed : YES
Committed tests executed   : NO
Physical validation        : NOT AUTHORIZED / NOT RUN
```

## Current release/fault batch state

```text
R1   implemented, validation pending
R3   implemented, validation pending
R34  implemented, validation pending
R46  supported launcher mitigated; direct controller integration still open
```

Do not call the release/fault batch completely closed until `g1_right_arm_jog.py` itself uses the shared release evidence contract and the committed tests are executed from a real checkout.

## Verification boundary for all remediation above

Not performed in this session:

```text
full backend unittest discovery
full hardware unittest discovery
Unity compilation or Play mode
Quest/Meta runtime
MuJoCo end-to-end launcher
WSL/DDS/Unitree SDK runtime
G1 connection or command
```

Repository hardware authorization remains locked. No remediation commit authorizes physical output or G1 mutation.