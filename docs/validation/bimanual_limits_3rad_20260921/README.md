# Bilateral 3 rad/s, 3 rad/s² — final status

Simulation/observation only. No physical gain change or G1 command execution.

- New defaults: all 14 joints, 3.0 rad/s velocity and 3.0 rad/s² acceleration.
- `source_full_tests.txt`: 116 tests, 115 pass. The remaining current-profile
  recorded-session case ended at the original recording's 5.75-second return
  boundary, before the new profile completed. It did not hit a controller fault.
- The final test explicitly continues only the generated fixed-dt clock after
  the recording ends, checking all motion/geometry bounds until ready within
  the existing 30-second return budget. The targeted test passed (11.015s wall):
  3433 recorded ticks + 65 generated ticks, return complete in 6.833333s,
  minimum clearance 5.000078524 mm, peak acceleration 3 rad/s².
  No new sensor input or measured joint samples were fabricated.
- Thus each of the 116 final tests has passed; a second full-suite run was not
  performed after the test-window correction. Earlier failure logs are retained.
- The earlier actual return recovery defect was fixed by consuming a checked
  stationary sample before reinitializing Ruckig, allowing finite-difference
  braking acceleration to settle to zero. The stop/range/collision checks remain.
- Historical exact-replay tests use their original profile and retain zero q
  mismatch. Current-profile paths are not labeled identical to old recordings.
- `runtime_preflight.json`: PASS, source/runtime parity of 13 files.
- Fresh runtime simulator inspection confirmed all 14 velocity/acceleration
  values are 3.0; no runtime Unity/robot/camera session was started in this change.
- `preservation_after.json` records preservation of unrelated sources and runtime.

`core_tests.txt` also retains an early test harness import-path error;
`motion_tests.txt` retains a comparison against the old single-arm profile.
The full suite included the corrected harness and explicit historical-profile
comparison, so these do not represent unresolved final failures.

PD values quoted to the user are historical right-arm research candidates only:
Kp=[120,300,64,100,20,30,20], Kd=[1,3,1.2,1.4,1,1,1].
They remain unselected (15/16 expanded conditions) and were not applied.
