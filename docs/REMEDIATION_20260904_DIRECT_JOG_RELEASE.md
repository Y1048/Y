# Direct Jog release remediation — 2026-09-04

Branch: `main`

This document records source and offline-CI remediation for R46. It is not a physical acceptance report.

## R46 — direct `g1_right_arm_jog.py` release finalization

Implementation commit:

```text
0049ceb268150c73de5bb5b038b680cbb025e0ec
fix: integrate direct Jog shared release finalizer (R46)
```

The direct Jog controller now imports and uses the same SDK-neutral release contract already used by the Gate 6/Gate 7 remediation:

```text
arm_sdk_release_contract.ReleaseEvidence
arm_sdk_release_contract.execute_release_sequence
```

### Behavior after the change

- The controller records `last_successful_weight` only after `publisher.Write(...)` succeeds.
- Planned release starts from that last successfully transmitted weight rather than merely the most recently computed weight.
- Ramp-down and the independent zero-weight tail are executed by `execute_release_sequence()`.
- A ramp failure does not suppress the zero tail.
- Runtime exceptions no longer immediately claim `command_output_enabled=false`.
- If a fault occurs after publisher creation and no normal release evidence exists, the `finally` path executes the shared release sequence from the last successful weight using the most recent measured LowState pose available.
- Result JSON consumes `ReleaseEvidence.as_dict()` and records `release_ramp_completed`, requested/sent zero frames, `zero_release_completed`, `last_successful_weight`, `release_fault`, `output_state_unknown`, and `external_authority_handoff_confirmed`.
- PASS requires a complete zero tail and no release fault. A complete zero tail can mark command output disabled while an earlier runtime fault still keeps the run failed.
- If no release evidence can be produced after publisher creation, the result is fail-closed with `output_state_unknown=true` and `command_output_enabled=true`.

The existing supported `g1_right_arm_jog_entry.py` result guard remains in place as a second boundary check; the core controller is no longer dependent on that wrapper for correct release-result semantics.

## Regression evidence

The one-shot migration job validated Python syntax plus the new direct-release test and the shared release-contract test before committing the production change. The temporary migration workflow was removed after the source commit.

The persistent offline safety workflow was then extended to include:

```text
hardware/g1_arm_bridge/test_g1_right_arm_jog_direct_release.py
```

Current-checkout run:

```text
workflow : .github/workflows/offline-safety-regression.yml
run      : 33823115876
result   : PASS
```

That run completed 48 unittest cases plus the Gate 6 interruption-release offline contract script. The direct Jog subset checks that the shared release contract is used in both planned/fault finalization, successful active writes precede weight bookkeeping, the exception handler does not falsely claim output disablement, and missing release evidence is fail-closed.

## Status

```text
R46 direct controller source integration : IMPLEMENTED
R46 direct-release offline regression     : PASS
Supported wrapper result guard            : retained
WSL/DDS runtime validation                : NOT RUN
Physical G1 validation                    : NOT RUN
External authority handback confirmation  : NOT PROVIDED
```

No Unitree publisher, DDS endpoint, WSL runtime, Unity/Quest runtime, or physical G1 connection was created by this remediation/CI work. Repository hardware authorization remains locked.