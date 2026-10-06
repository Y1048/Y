# Split tracking validation — 2026-10-06

Status: **OFFLINE_VALIDATED_LIVE_UNVERIFIED**. Actual G1 software, processes and motors were not changed or started by this validation.

## Applied contract

One bilateral QP still solves all 14 arm joints. Each arm has a position-only FrameTask at 12 s^-1 and an orientation-only FrameTask at 1.5 s^-1. Position is not extrapolated or rewritten. No prediction/filter/extra IK solver was deployed.

Tracking: proximal/wrist caps 150/180 deg/s; acceleration 300 deg/s^2; shoulder yaw comfort +/-15 deg at cost 1.2; wrist-priority proximal damping remains 14. Staged return and near-hands trajectory generation: 90/180 deg/s, 90 deg/s^2, jerk 1.28 rad/s^3. Hard geometry floor remains 5 mm.

Transition exception: a conservative stop is checked first. If a slower stop would cross a guard, the exact previously validated tracking stop tail is retained until rest. Its deceleration may exceed 90 deg/s^2 but not the tracking envelope. This is not a newly generated high-acceleration return. A current velocity above the return cap is stopped before Ruckig is seeded. Two fault-injection regression tests cover these cases; lowering the test threshold was not used to hide them.

## Reference replay

Reference: `unity_20261006_153832_043972.jsonl`

SHA256: `2e6e2af9a393e4ecfbb22569f7883a7ad5ffec6f803a74cd45b41b9f6f0e8bbe`

Reconstructing the pre-split controller reproduces every recorded q sample with maximum difference `0.0` rad. Candidate q differences are intentional.

| Metric | Pre-split | Split candidate |
|---|---:|---:|
| left mean position error (mm) | 66.730 | 40.373 |
| left p95 position error (mm) | 119.457 | 92.572 |
| left legacy sample-fit lag (ms) | 500.000 | 150.000 |
| left fixed-window timestamp-fit lag (ms) | 595.000 | 165.000 |
| right mean position error (mm) | 70.216 | 42.547 |
| right p95 position error (mm) | 126.621 | 86.473 |
| right legacy sample-fit lag (ms) | 516.667 | 166.667 |
| right fixed-window timestamp-fit lag (ms) | 555.000 | 180.000 |
| minimum sampled clearance (mm) | 10.963 | 11.147 |
| braking ticks | 22.000 | 23.000 |
| solver-error ticks | 0.000 | 0.000 |
| peak proximal speed (deg/s) | 59.038 | 129.149 |
| peak wrist speed (deg/s) | 37.461 | 156.909 |

The 977 valid tracking samples per case exclude braking/invalid-target states from the position-fit metric. The fixed-window fit uses recorded monotonic timestamps, 5 ms search increments and identical eligible samples for every tested delay; intervals separated by more than 50 ms are not bridged. A best-fitting trajectory shift is not a literal packet delay. No physical 255–272 ms claim is supported by this replay.

## Regression and holdout

- backend: 276 tests, exit 0; log `backend.log`.
- hardware: 44 tests, exit 0; log `hardware.log`.
- Code files changed during the full suites: `[]`.
- Historical September 18 exact replays retain the old combined SE(3) controller in test-only reconstruction; production contains no historical controller selector.
- G1.zip holdout entry: `PC/logs/test_results/bimanual/unity_20260923_152640_019472.jsonl`.
- Holdout current-profile pass: `True`; failures `[]`; minimum clearance `5.004041` mm.
- The G1.zip check here validates current-profile safety and state-flow on a different recording. It is not an exact archived-controller replay, and it does not claim the legacy full-archive strict validator passes with a changed motion profile.

## Evidence and remaining limits

Local evidence folder: `logs/test_results/split_tracking_validation_20261006_200416/`. It retains test stdout, JSON summaries, source hashes, and offline replay scripts. Large extracted archive data was temporary and removed; the original G1.zip and 15:38 log were only read.

Remaining: live Quest/G1 motion quality, physical stop/clearance margin, simultaneous camera/Omni load, and end-to-end latency. Model clearance values near 5 mm are numerical kinematic validation, not a physical safety certification. Faster simulated tracking does not establish a globally optimal tuning or guarantee the physical robot has the same response.
