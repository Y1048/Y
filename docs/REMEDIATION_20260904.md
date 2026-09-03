# Remediation log — 2026-09-04

Branch: `refactor/teleop-architecture`

This document records production fixes separately from the R1-R67 review documents. A finding is not treated as physically validated merely because its source fix and unit tests exist.

## Batch 1 — R64 safety-event preservation

Implementation commit:

```text
187b3e2a44466653bc099327e0ace7f18dc7fcb0
fix: preserve disengage events across UDP backlog (R64)
```

### Problem

The non-blocking receiver drained all queued Unity packets in one poll and returned only the final command plus OR-ed safety flags. A backlog such as:

```text
ACTIVE -> PINCH_DISENGAGED -> ACTIVE
ACTIVE -> WORKSPACE_EXIT   -> ACTIVE
```

could leave the runtime state ACTIVE by the end of the same poll. `MinkCommandStream` could reset and re-engage its clutch in the same update, so the downstream Mink/Gate 7 state stream might never expose the disengage or workspace-fault transition.

### Production changes

Changed:

- `backend/g1_teleop/live_receiver.py`
- `backend/g1_teleop/mink_command_stream.py`

Behavior after the change:

1. An accepted `workspace_exit`, `pinch_disengaged` or `tracking_disengaged` command terminates the current receive batch.
2. Datagrams behind that event remain queued for the next control poll.
3. An ACTIVE target accepted earlier in the same batch is cleared from `latest_active_command` when the safety barrier is reached.
4. `MinkCommandStream` does not replace its target or engage its clutch during a safety-reset update.
5. Session takeover remains separate: an explicitly accepted new session may still reset and re-engage once, preserving the existing zero-jump rebase policy.

### Regression tests added

Changed:

- `backend/tests/test_live_receiver.py`
- `backend/tests/test_mink_command_stream.py`

Added coverage for:

- active → pinch disengage → active backlog
- active → workspace exit → active backlog
- one observable non-active/fault cycle before re-engagement
- no simultaneous `reset_clutch` and `engage_clutch` for safety events
- no target replacement by the deferred ACTIVE command
- unchanged stale-session takeover behavior

### Verification performed

A focused local harness compiled the two changed production modules and both changed test modules, then ran 18 command-ingress tests:

```text
Ran 18 tests in 0.301s
OK
```

The harness used contract-equivalent stubs for unchanged package dependencies because the connected GitHub checkout was not available as an executable local repository. The committed tests themselves were not run by GitHub Actions; no workflow run was associated with the commit.

Not performed:

```text
full backend unittest discovery
Unity compilation or Play mode
Quest/Meta runtime
MuJoCo end-to-end launcher
WSL/DDS/Unitree SDK runtime
G1 connection or command
```

### Status

```text
R64 source fix             : IMPLEMENTED
Focused regression tests   : PASS
Full repository regression : PENDING
Unity/Gate 7 integration   : PENDING
Physical validation        : NOT AUTHORIZED / NOT RUN
```

## Next batch

```text
R1  Gate 7 release failure can remain passed=true/exit 0
R34 Gate 6 runtime fault can bypass release and report weight zero
R46 Jog fault result can report output disabled before zero-tail completion
```

The next batch must share a clear release-result contract without weakening hardware authorization. Required evidence fields include at least:

```text
release_attempted
release_ramp_completed
release_zero_frames_requested
release_zero_frames_sent
zero_release_completed
last_successful_weight
last_successful_write_time
release_fault
output_state_unknown
external_authority_handoff_confirmed
```

Tests must inject first-ramp failure, partial zero-tail failure, LowState loss, mode change, publisher write failure and normal completion without creating a Unitree publisher or connecting to G1.
