# Startup Recovery multi-strategy full-text review - 2026-09-04

Branch: `main`

This is a **review-only** batch. The deferred experiment was not run and active
Startup Recovery was not changed.

## 검토

The following remaining `static_only` files were read in full:

```text
experiments/startup_recovery_multistrategy/TEST_MULTI_STRATEGY.bat
experiments/startup_recovery_multistrategy/VIEW_SELECTED.bat
experiments/startup_recovery_multistrategy/candidate_runner.py
experiments/startup_recovery_multistrategy/run_experiment.py
experiments/startup_recovery_multistrategy/test_experiment.py
experiments/startup_recovery_multistrategy/view_selected.py
```

### Existing R53 remains confirmed

The experiment delegates to the current recovery module, which regenerates or
uses the repository's common generated MuJoCo XML. The summary stores paths and
numeric results but does not bind controller, model, mesh, state and result
content hashes into one immutable run manifest. The selected-result viewer then
replays the saved path using the current replay/model environment. This remains
the existing R53 provenance finding.

### Existing R55 remains confirmed

Candidate JSON/log names are reused in one default output directory. Existing
result files are not removed or bound to a run ID before each child starts, and
`subprocess.run()` has no timeout. The reviewed tests cover ranking and pose
input validation but not stale result reuse, missing rewrite, malformed result
or a hung child. This is exactly R55.

### Other conclusions

- The BAT wrappers preserve the Python exit code and label the result as
  offline-only, not hardware-approved.
- Candidate selection rejects failed candidates and uses clearance first, then
  elapsed time and jerk inside a 0.5 mm equivalence band.
- `candidate_runner.py` changes module globals only inside its isolated child
  process; it does not edit active source/config files.
- No new independent P1/P2/P3 finding was identified.

## 코드 수정

```text
Active recovery changes     : NONE
Experiment behavior changes : NONE
Authorization changes       : NONE
Review artifacts only       : YES
```

## 테스트

Executed only the isolated ranking/input tests:

```text
py -3.11 -m unittest discover \
  -s experiments/startup_recovery_multistrategy \
  -p test_experiment.py
```

Result:

```text
4 tests run
4 passed
```

The experiment, viewer, MuJoCo model generation, WSL, DDS and G1 were not run.

## 남은 항목

1. Keep the entire strategy-atlas/multi-strategy experiment deferred until the
   user explicitly resumes it.
2. Keep R53/R55 remediation separate from review bookkeeping.
3. Continue posture-sweep, TWIST2 experiment and hardware-helper static-only
   files.

Review result:

```text
new R-number findings       : 0
existing findings confirmed: R53, R55
physical validation        : NOT AUTHORIZED / NOT RUN
```
