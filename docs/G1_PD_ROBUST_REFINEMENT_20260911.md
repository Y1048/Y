# G1 PD robust refinement — 2026-09-11

## Scope and observed outcome

Base `6b1421703bfef6a8ac2a84687ced15e2be8124fa`. Tested optimization implementation `7577ed97fcf1f0ae8e9edf4777ef03f9dabaf380`.
Simulation only; no G1, DDS/SDK, live VR controller, model-limit, IK cost or physical gain change.
The fixed-pelvis joint22 +/-8-degree reference, three cycles, group gains22..25,
50Hz references,500Hz writer and mandatory all29 inner-limit rules are unchanged.

**1268 prescribed simulations were attempted and audited:**
1188 calibration runs (44pairs x27conditions), then
80 held-out runs (10 frozen pairs x8conditions).
**1240 completed, 1240 eligible, 28 rejected.**
Do not describe excluded/early-stopped trials as completed three-cycle motions.
Rejection reasons: `{"joint_stopping_envelope_exhausted": 3, "measured_velocity_limit": 8, "ready_pose_not_settled_in_final_warmup_second": 17}`.
Guard events: `{"joint_stopping_envelope_exhausted": 3}`.

The first surviving pair in frozen calibration order is **100/2**. Its worst calibration RMSE is **0.0100312489177771 rad** and worst held-out RMSE **0.00975311816778928 rad**. The nominal RMSE is **0.00755652846809067 rad**. This is a finite-grid simulation screening result, NOT hardware gains or an optimum proof.

## Prespecified optimization, not a favorable nominal shortlist

Kp72/80/88/96/100 x Kd0.6/0.7/0.8/0.9/1/1.2/1.5/2, plus controls40/5,56/3,
100/0.1,100/3. All44 pairs see the same27 conditions. The motor18 and model9
conditions retain the old assumptions; redundant nominal/dt_half model runs
are omitted. Minimum original-reference RMSE in the WORST condition is the
objective, but only after all27 trials pass the unchanged acceptance rules.
The worst error observed in an incomplete/rejected trial is not a selectable score.

After calibration, the best6 eligible pairs and fixed controls40/5,56/3,80/1,
100/1,100/2 are frozen in selection.json, including hashes of all calibration
case records. Eight holdouts were already recorded in manifest.json before
any trial: five unseen combinations of hypothetical friction/torque delay/lag
and three mass/inertia/passive-damping/friction configurations. They were not
used to choose or retune the shortlist. Preserve calibration order after
reporting holdout success/failure. No weight, bound, time or threshold was
changed to turn a failed trial into a pass.

## Full calibration table and separate holdout evidence

RMSE is radians against the ORIGINAL joint22 reference, not a clipped command.
A gain is applied as a group to22..25; only22 is excited. Other joint gains are
not independently identified. 'Not selected' is not evidence of holdout failure
or success. 'Excluded' does not mean an arbitrarily large RMSE; it has no valid
optimization score because at least one required condition failed.

| Kp | Kd | Calibration passed | Worst calibration RMSE(rad) | Holdout passed | Worst holdout RMSE(rad) |
| --- | --- | --- | --- | --- | --- |
| 100 | 0.7 | 27/27 | 0.00879774777443 | 5/8 | excluded |
| 100 | 0.8 | 27/27 | 0.00888054805455 | 6/8 | excluded |
| 100 | 0.9 | 27/27 | 0.00896567250393 | 7/8 | excluded |
| 100 | 1 | 27/27 | 0.00905308278958 | 7/8 | excluded |
| 96 | 0.7 | 27/27 | 0.00911656871783 | 5/8 | excluded |
| 96 | 0.8 | 27/27 | 0.0092051311523 | 6/8 | excluded |
| 100 | 1.2 | 27/27 | 0.00923438478558 | not selected | not tested |
| 96 | 0.9 | 27/27 | 0.00929564593546 | not selected | not tested |
| 96 | 1 | 27/27 | 0.00938810585404 | not selected | not tested |
| 100 | 1.5 | 27/27 | 0.00952075164624 | not selected | not tested |
| 96 | 1.2 | 27/27 | 0.00957882078386 | not selected | not tested |
| 88 | 0.7 | 27/27 | 0.00985492556547 | not selected | not tested |
| 96 | 1.5 | 27/27 | 0.00987847755235 | not selected | not tested |
| 88 | 0.8 | 27/27 | 0.00995370597087 | not selected | not tested |
| 100 | 2 | 27/27 | 0.0100312489178 | 8/8 | 0.00975311816779 |
| 88 | 0.9 | 27/27 | 0.0100538858171 | not selected | not tested |
| 88 | 1 | 27/27 | 0.0101557685566 | not selected | not tested |
| 88 | 1.2 | 27/27 | 0.010364636273 | not selected | not tested |
| 96 | 2 | 27/27 | 0.0104104460393 | not selected | not tested |
| 80 | 0.6 | 27/27 | 0.0106653228716 | not selected | not tested |
| 88 | 1.5 | 27/27 | 0.010691228512 | not selected | not tested |
| 80 | 0.7 | 27/27 | 0.0107697520529 | not selected | not tested |
| 80 | 0.8 | 27/27 | 0.0108751265938 | not selected | not tested |
| 80 | 0.9 | 27/27 | 0.0109819783442 | not selected | not tested |
| 80 | 1 | 27/27 | 0.0110905901413 | 8/8 | 0.0108642360181 |
| 100 | 3 | 27/27 | 0.0111485909482 | not selected | not tested |
| 88 | 2 | 27/27 | 0.0112691449146 | not selected | not tested |
| 80 | 1.2 | 27/27 | 0.0113142826429 | not selected | not tested |
| 80 | 1.5 | 27/27 | 0.0116664892491 | not selected | not tested |
| 72 | 0.6 | 27/27 | 0.0117916244566 | not selected | not tested |
| 72 | 0.7 | 27/27 | 0.0118952252838 | not selected | not tested |
| 72 | 0.8 | 27/27 | 0.0120028267557 | not selected | not tested |
| 72 | 0.9 | 27/27 | 0.0121141828196 | not selected | not tested |
| 72 | 1 | 27/27 | 0.0122290348795 | not selected | not tested |
| 80 | 2 | 27/27 | 0.0122939396417 | not selected | not tested |
| 72 | 1.2 | 27/27 | 0.0124683867763 | not selected | not tested |
| 72 | 1.5 | 27/27 | 0.0128497882272 | not selected | not tested |
| 72 | 2 | 27/27 | 0.0135352513592 | not selected | not tested |
| 56 | 3 | 27/27 | 0.0188582955634 | 8/8 | 0.0181433911882 |
| 40 | 5 | 26/27 | excluded | 6/8 | excluded |
| 88 | 0.6 | 26/27 | excluded | not selected | not tested |
| 96 | 0.6 | 26/27 | excluded | not selected | not tested |
| 100 | 0.1 | 18/27 | excluded | not selected | not tested |
| 100 | 0.6 | 25/27 | excluded | not selected | not tested |

Frozen calibration-order survivors: `[[100, 2.0], [80, 1.0], [56.0, 3.0]]`.
Holdout exclusions (all retained):

```json
[
  {
    "pair": [
      40.0,
      5.0
    ],
    "failures": [
      {
        "scenario": "motor/hold_f000_d3_l3",
        "reason": "measured_velocity_limit",
        "exclusions": [
          "measured_velocity_limit"
        ]
      },
      {
        "scenario": "motor/hold_f050_d6_l2",
        "reason": "measured_velocity_limit",
        "exclusions": [
          "measured_velocity_limit"
        ]
      }
    ]
  },
  {
    "pair": [
      96,
      0.7
    ],
    "failures": [
      {
        "scenario": "motor/hold_f000_d1_l8",
        "reason": "measured_velocity_limit",
        "exclusions": [
          "measured_velocity_limit"
        ]
      },
      {
        "scenario": "motor/hold_f000_d3_l3",
        "reason": "ready_pose_not_settled_in_final_warmup_second",
        "exclusions": [
          "ready_pose_not_settled_in_final_warmup_second"
        ]
      },
      {
        "scenario": "motor/hold_f025_d2_l8",
        "reason": "ready_pose_not_settled_in_final_warmup_second",
        "exclusions": [
          "ready_pose_not_settled_in_final_warmup_second"
        ]
      }
    ]
  },
  {
    "pair": [
      96,
      0.8
    ],
    "failures": [
      {
        "scenario": "motor/hold_f000_d1_l8",
        "reason": "ready_pose_not_settled_in_final_warmup_second",
        "exclusions": [
          "ready_pose_not_settled_in_final_warmup_second"
        ]
      },
      {
        "scenario": "motor/hold_f025_d2_l8",
        "reason": "ready_pose_not_settled_in_final_warmup_second",
        "exclusions": [
          "ready_pose_not_settled_in_final_warmup_second"
        ]
      }
    ]
  },
  {
    "pair": [
      100,
      0.7
    ],
    "failures": [
      {
        "scenario": "motor/hold_f000_d1_l8",
        "reason": "measured_velocity_limit",
        "exclusions": [
          "measured_velocity_limit"
        ]
      },
      {
        "scenario": "motor/hold_f000_d3_l3",
        "reason": "ready_pose_not_settled_in_final_warmup_second",
        "exclusions": [
          "ready_pose_not_settled_in_final_warmup_second"
        ]
      },
      {
        "scenario": "motor/hold_f025_d2_l8",
        "reason": "ready_pose_not_settled_in_final_warmup_second",
        "exclusions": [
          "ready_pose_not_settled_in_final_warmup_second"
        ]
      }
    ]
  },
  {
    "pair": [
      100,
      0.8
    ],
    "failures": [
      {
        "scenario": "motor/hold_f000_d1_l8",
        "reason": "ready_pose_not_settled_in_final_warmup_second",
        "exclusions": [
          "ready_pose_not_settled_in_final_warmup_second"
        ]
      },
      {
        "scenario": "motor/hold_f025_d2_l8",
        "reason": "ready_pose_not_settled_in_final_warmup_second",
        "exclusions": [
          "ready_pose_not_settled_in_final_warmup_second"
        ]
      }
    ]
  },
  {
    "pair": [
      100,
      0.9
    ],
    "failures": [
      {
        "scenario": "motor/hold_f000_d1_l8",
        "reason": "ready_pose_not_settled_in_final_warmup_second",
        "exclusions": [
          "ready_pose_not_settled_in_final_warmup_second"
        ]
      }
    ]
  },
  {
    "pair": [
      100,
      1.0
    ],
    "failures": [
      {
        "scenario": "motor/hold_f000_d1_l8",
        "reason": "ready_pose_not_settled_in_final_warmup_second",
        "exclusions": [
          "ready_pose_not_settled_in_final_warmup_second"
        ]
      }
    ]
  }
]
```

## Joint-limit and physical interpretation

All29 states are checked before/after each physics step, including warmup and
the final integration, with the existing additional0.05rad reserve and assumed
stopping budget. Original/XML limits, collisions, target trajectory, torque
and velocity bounds are not relaxed. Need for a target intervention excludes
a trial; measured qpos is never projected to create an artificial pass.

Minimum observed soft clearance across this entire attempt set:
**0.211798601708536rad (12.135166degrees)**; minimum XML-hard clearance:
**0.261798601708536rad (14.999955degrees)**.
These are recorded simulation observations up to completion/refusal, not a
continuous-time physical guarantee. The XML range is not a measured real
hard stop. A refused simulation is not a physical stop/hold controller.
Kp100 remains the search ceiling. Finite-grid success does not establish
local/global optimality, free-base stability or real-motor performance.

## Verification actually completed

Full experiment: isolated Windows host, Python3.11.9,
MuJoCo3.3.7, NumPy2.4.6, six workers.
Local allowlist:108 passed,1 skipped(C++ compiler unavailable),0 failures/errors.
Hosted Linux job **103231729623**, run **34589643742**, on `7577ed97fcf1f0ae8e9edf4777ef03f9dabaf380`:
**109/109 tests passed, no skips**, including C++ reference parity and the
actual eight-case smoke study. Decoded job output and success state were inspected.
Hosted CI did NOT run the full1268-case optimization.
Do not add repeated host executions to the count of distinct test coverage.

All1268 q22 NPZ traces were reloaded, with hashes/finite arrays,
500Hz continuity, complete cycle/segment coverage, actual gain fields,
RMSE/peak error/torque/speed/overshoot/settling and limiting metrics checked.
All36772 joint minimum-margin records and their witnesses,
pre/post/final-state coverage and refusal status were checked. The summary was
regenerated and exactly matched stored rankings; frozen calibration hashes matched.
Full all29 trajectories are NOT stored/reconstructed: non-q22 state is reduced
to extrema/witnesses. No stronger validation is implied.

## Reproduction and retained evidence

Usage: `experiments/twist2_right_arm_manual/MUJOCO_PD_ROBUST_REFINEMENT.md`.
The isolated MuJoCo3.3.7 environment runs this script directly; it never calls
the live VR launcher. GUI/BAT and real VR performance were not tested here.
`--smoke` is explicitly a subset. The regular command runs the full frozen plan.

Compact evidence lives at `docs/validation/g1_pd_robust_refine_20260911/`:
manifest,selection,summary,audit,all_cases.csv,all_joint_margins.csv,tests and
preservation metadata. Raw cases and traces were copied and hash-compared to
`C:\Users\user\Documents\G1_PD_RobustRefine_20260911`. The original temporary run was not erased.
CSV SHA256: `962391466414d7b9108834f8057f0c317c17e86be785fcb50f6fa5dd6ce2f39d`.
29-joint margin CSV SHA256: `c000b5a32d88610684f35903ce26a5a6bba03be8b6f1d2e71addcc95504250fd`.
Raw source hashes are of the actual Windows checkout bytes(CRLF where applicable),
not substituted with hashes from a differently normalized Linux checkout.

Next permitted work remains offline: confirm useful candidates under a separately
recorded excitation/operating-condition study or calibrate the model from reviewed
existing measurements. Do not auto-apply a new gain, tune IK cost simultaneously,
replace the user's known working VR tree, or lift Robot/All charging restrictions.
