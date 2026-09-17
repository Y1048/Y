# Mink v4 -> G1 integration status (2026-09-09)

## Current conclusion

The model-to-packet joint order is verified offline. The existing robot launcher
is **not compatible with the new cycle behavior or motion profile**. No robot
connection, binary inspection, deployment, publisher or physical output was
performed for this review.

| Item | Current simulation cycle | Existing robot route, from local source |
|---|---|---|
| Velocity caps | Shoulder/elbow 90 deg/s; wrist 180 deg/s | All right-arm joints 0.7 rad/s (~40.1 deg/s) |
| Acceleration | 60 deg/s^2 | 10 deg/s^2 |
| Initial basis | Model home; no live LowState initialization | Native receiver captures robot state and moves both arms to ready pose |
| Normal pinch/tracking release | Checked model return, acknowledgement, fresh re-engage | InputValidator returns input_disengaged; native trial stops in damping |
| Joint interpretation | Model qpos converted by named joints to G1 29-vector | MinkUdpTarget uses absolute right-arm 22..28 values |
| Other joints | Model joints outside right arm frozen | Policy drives legs; waist held; left arm ready pose |
| Transport | Unity state feedback; candidate UDP 5008 disabled | Relay 5008 -> G1 UDP 5014, then native full-body owner |

Source references: `tools/START_TWIST2_MINK_UDP.ps1`,
`experiments/twist2_right_arm_manual/mink_udp_target.hpp`,
`validate_input.hpp`, `twist2_mink_udp_trial.cpp`.
The selected remote directory is `g1_vr_07_10deg_trial_20260908`.
Its installed binary/configuration was not checked; the table describes local
source and launcher selection, not a newly verified robot deployment.

## Evidence from latest user simulation

Runtime marker: `mink_goal_braking_elbow_assist_v4`, snapshot 13:52:05.

- 13:49:32 tracking release -> 13:49:34 return acknowledgement -> 13:49:36 active.
- 13:50:20 tracking release -> 13:50:23 return acknowledgement.
- 13:50:25 input_timeout. No return collision rejection in this run.

This confirms two model returns and one subsequent re-engage. It does not prove
all return paths safe: an earlier pinch return was blocked at 4.910 mm clearance.
It also does not validate a real LowState initial pose or robot return.

## Completed offline boundary checks

- Real model qpos -> named G1 29-vector -> right-arm 22..28 correspondence.
- Live packet canonicalization retains all 29 values (7-decimal rounding) and
  pinch/tracking release events. Fake sender only; no packet transmission.
- Cycle feedback now has command_provenance=simulation_only,
  simulation_only=true, hardware_output_authorized=false. Live relay rejects
  these markers and simulation_arm_cycle metadata even if an old live label
  remains. The existing no-candidate-output branch remains in place.
- Unity cycle feedback structure and state_source are retained. No Unity source
  changes were necessary; actual display after this marker change is untested.

Re-run from project root:

```powershell
py -3.11 -B -m unittest discover -s backend/tests -p test_simulation_handoff_boundary.py
py -3.11 -B -m unittest discover -s backend/tests -p test_mink_return_handshake.py
py -3.11 -B -m unittest discover -s hardware/g1_arm_bridge -p test_gate7_mink_wsl_relay.py
```

## Required next implementation before robot use

Update: the separate **offline** sample consumer now exists in
`experiments/twist2_right_arm_manual/mink_cycle_candidate_offline.hpp`.
Its contract and reproducible build/replay are documented in
`experiments/twist2_right_arm_manual/MINK_CYCLE_CANDIDATE_OFFLINE.md`.
24 C++ scenarios and 579 real-model samples passed. The following physical
adapter/owner items are still required; no robot candidate was deployed.

1. Prepare a separate native candidate with the 7-joint speed/acceleration
   profile and validated cycle events. Keep the existing working physical trial
   intact. `ArmCycleOffline` is a trusted-event, relative-anchor prototype with
   old limits; it cannot replace the absolute Mink receiver unchanged.
2. Define explicit tracking/return/waiting phases and session/epoch completion
   handshake. Active=false alone cannot distinguish return execution from a
   fault. Retain R1/Select/B/p emergency stops, timeout and malformed-input stops.
   Do not simply remove InputValidator's input_disengaged check.
3. Validate return trajectory and completion against fresh measured state in
   that candidate while the single TWIST2 lowcmd owner continues leg control.
   Do not authorize fresh model-home simulation packets as live hardware input.
4. Offline replay candidate behavior, then inspect/review deployment artifacts
   before any separately authorized robot-side change. PD tuning follows actual
   target-vs-measured logs after this integration, not model-only motion.

Remaining local issues: some wrist goal residual and return-path failures;
recorded elbow-assist timing p99 ~38 ms has not established 60 Hz real-time
operation. No claim of robot safety or readiness is made by these tests.


Local progress: `mink_cycle_owner_offline.hpp` now provides native-packed
feedback/control validation and single-owner reference composition. 20 synthetic
native-byte tests passed; it has no DDS transport or motor writer. The 24 cycle
tests and 579-sample model replay also passed again. Ready transition, 500 Hz
resampling, actual policy/feedback runtime and stop integration remain pending.
See the candidate document for the exact adapter call sequence.


Resampling update: separate fixed-grid C++ component now passes 16 scenarios and
an isolated MuJoCo 3.12.0 audit of 4,909 model output segments. Default 3.11.0
rejects the same fixture at 6.256 s; this runtime discrepancy remains unresolved
for live use. Neither the resampler nor the isolated runtime is connected to the
physical owner. See CHAT_HANDOFF and the candidate document for evidence/limits.


Latest local integration: owner resample=true now uses bounded 500 Hz arm output
and gates return ACK on fresh settled output plus measured state. Eight integrated
scenarios added. Offline IK and output audit now both use isolated MuJoCo 3.12.0;
the simulation-only launcher pins that same runtime and fails closed on mismatch.
No controller window or physical path was run. Actual Unity/Quest verification,
network/real-time policy binding and physical stop integration are still pending.


Policy cadence update: offline owner now accepts request-bound 50 Hz policy
results and reuses them for 500 Hz reference composition, preserving original
input age (<=25 ms) and rechecking current feedback/controls/geometry on every
output. Eleven new synthetic scenarios pass. This is not a running Torch worker,
real-time scheduler or physical writer; the existing physical route is unchanged.
