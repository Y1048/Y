# PC / G1 joint-range reconciliation — 2026-10-07

Status: **OFFLINE_VALIDATED_LIVE_UNVERIFIED**. This is a PC-side control-model change. No G1 source, binary, gain, policy, controller process, or motor output was modified or started by this work.

## Cause and scope

The deployed C++ bridge checks all 14 arm goals against `twist2::kLower + 0.05F` and `twist2::kUpper - 0.05F`. One invalid wrist goal rejects the entire bilateral datagram. The prior 09:56 onboard review found 285 of 1,463 active datagrams outside that guard. PC MuJoCo allowed the wider model limits, so the mismatch was in the two controllers' position-boundary contract, not a corrupted transport or an Omni requirement.

Runtime changes are confined to `g1_bimanual_limits.py` and `g1_bimanual_sim.py`. A named 14-joint table mirrors the deployed bounds; a constructor-time intersection tightens the private MuJoCo model **before** Mink's ConfigurationLimit caches its limits. Posture preference, QP stopping bounds, checked tails, return/recovery and return-waypoint validation therefore read the same effective ranges. No output clipping, additional IK solver, live SSH dependency, runtime bypass switch, or new worker was added.

Intersection preserves a stricter existing operational range. For example, the elbow minimum remains 5 degrees, while its effective maximum is limited by the C++ receiver rather than the previous 120-degree model limit. Left/right shoulder-roll bounds remain asymmetric and are associated by joint name.

C++ float32 constant/addition arithmetic is reproduced before promotion to double. A further 1e-6 rad inward numerical reserve is greater than the existing 1e-8 rad checked-stop tolerance; neither tolerance nor G1's guard was relaxed. This reserve is numerical headroom, not a physical safety certification.

For wrist pitch/yaw, the receiver bound is approximately +/-1.564429641 rad and the PC model bound +/-1.564428641 rad. The recorded first rejected left-wrist-pitch goal (-1.568725872 rad) is outside the new model boundary and can no longer be generated as a checked output.

## Reproduction of the actual 09:56 session

Reference: `unity_20261007_095646_179749.jsonl`.
SHA256: `525f7a7742b3eac6c32af2854228ee41baac56bf619b2d4c6159ebb12afd362f`.

The old split-tracking controller is reconstructed by restoring its old ranges inside this offline experiment only. It reproduces the actual recording with maximum q difference **0.0 rad**, and zero state/input-acceptance mismatches. The candidate uses the same recorded inputs and tick times, not a synthetic replacement session.

| Metric | Before | After |
|---|---:|---:|
| Output ticks violating C++ receiver bounds | 326 | 0 |
| Checked-tail configurations violating C++ bounds | 6514 | 0 |
| Checked-tail configurations examined | 24525 | 24349 |
| Braking ticks | 73 | 68 |
| Solver-error ticks | 0 | 0 |
| Minimum sampled model clearance (mm) | 18.179 | 12.500 |
| Left mean simulated wrist error (mm) | 53.085 | 53.328 |
| Right mean simulated wrist error (mm) | 44.772 | 45.081 |

These are 3,412 PC state ticks, not the 1,463 emitted active onboard datagrams in the previous review; the two violation counts have different denominators. Tail configurations include repeated cached plans, not unique physical commands. Candidate outputs and all 24,349 examined tail configurations satisfy the pinned receiver bounds. Both tracking entries and tracking-loss returns remain, finishing READY/complete. One return finishes one recorded tick earlier (about 15 ms), hence one intentional state mismatch. Candidate trajectory differences are expected from changing the feasible set.

This repair removes one reason for command rejection; it is not a new gain/latency improvement. Slightly larger simulated target error is an expected tradeoff of honoring narrower feasible bounds. Reduced model clearance must not be described as unchanged physical safety margin.

## Regression and different-recording holdout

- Full backend: 298 tests, exit 0.
- Full hardware: 44 tests, exit 0.
- New range-specific tests: 10. Cover named/asymmetric limits, numeric reserve, invalid inputs, intersection without widening, Mink cache agreement, home/waypoint, every joint's outward stop rejection under both profiles, and bounded IK plus return from an infeasible wrist-pose request.
- Existing wrist-dominance, near-hands, re-engagement, stopping and return gates are not relaxed.
- One existing geometry-only test seeded wrist pitch -1.5892583669620304 rad, now outside the valid RX domain. Replacing only that seed with -1.55 rad preserves its exact global/inter-arm clearances (6.768927/85.630996 mm); explicit in-range assertions were added. No threshold/assertion was relaxed. The first full-suite failure and its source hashes are retained as attempt1 evidence.
- Historical September fixtures retain their old ranges only in `backend/tests/bimanual_replay_profiles.py`; production always uses the reconciled ranges.
- Source changes during full suites: `[]`.
- G1.zip holdout: `PC/logs/test_results/bimanual/unity_20260923_152640_019472.jsonl`, SHA256 `885151fb18187571691fba16f5eb871ffaff80badfdd28ab2dbdb9d604364747`.
- Holdout current-profile safety/state-flow validation: True; independent receiver checks: 9474 output commands, 0 violations; minimum sampled clearance 5.001046 mm.
- The holdout is a current-profile validation, **not** an exact recreation of the archived controller or a claim about the full archive strict validator.

## Preserved behavior and deployment contract

Position/orientation rates remain 12/1.5 s^-1; tracking velocity remains proximal/wrist 150/180 deg/s, acceleration 300 deg/s^2. Return stays 90/180 deg/s, 90 deg/s^2 with the established checked transition exception. Omni optional-input handling, Balance/Walk, PTZ/video, Unity camera positioning, all C++ receiver checks and the physical actuator are unchanged.

Pinned header SHA256: `4b6a6842ab8ff8701c6d8a99e1342f6f6c78856b50288cbf22ec2339a882e53a`.
Pinned bridge SHA256: `92e9ee15d46adc4fa441e686600f2423f406184b82110c2df55785c052064a10`.
Post-work read-only SSH verification confirmed identical hashes for the header, external bridge source, actuator source/binary and optional-Omni receiver.
The committed fixture records the exact deployed header values for offline drift checks. A future deliberate onboard joint-boundary change requires updating this PC mirror and fixture together; switching PCs does not require querying or rewriting the single robot's contract at every launch.

Evidence: `logs/test_results/joint_guard_reconciliation_20261007/`. Includes pre-edit copies, pinned source/hash snapshot, old/new replay, full suites, holdout and deployment checks. Original logs and G1.zip were only read; temporary archive extraction is removed automatically.

## Remaining limits

No repaired-code physical run has been performed. Actual motor response, the existing C++ 3 rad/s arm-target slew limiter, left-hand tracking losses, end-to-end latency and controlled shutdown require separate live evidence. The logged 17.8-degree physical wrist error is not claimed fixed by this patch. Because previously rejected motion will now be accepted, first live verification must use the existing support/harness and emergency-stop precautions; do not infer physical safety from the model's 5 mm numerical floor.

Generated UTC: 2026-10-07T02:32:08.263778+00:00.
