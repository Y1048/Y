# Display / IK frame review — 2026-09-22 16:06 session

## Evidence and changes

- Source: `logs/test_results/bimanual/unity_20260922_160612_134393.jsonl` (1,719 accepted inputs, 4,082 solver records).
- Robot logs copied read-only into `logs/test_results/review_20260922_160555/`: heading JSONL, actuation CSV, controller source. No robot commands, deployment, or mode changes were performed.
- Both-arms engage succeeded twice, at input-relative 6.657 s and 28.375 s. Left tracking loss triggered return at 19.375 s; final both-hand loss triggered return at 48.782 s.
- HMD origin minus shoulder center was approximately `(0, 0.300, 0.050)` m. All valid input wrist positions exactly matched displayed wrist positions.
- Rotation was inconsistent: Unity root -62.02 degrees vs solver root +62.02 degrees expressed in Unity axes. Restore the negative Unity-to-MuJoCo yaw conversion in the sender, leaving the displayed Omni yaw convention unchanged.
- Sender used anatomical hand orientation while cyan markers used raw wrist orientation (up to 29.5 degrees left / 172.8 degrees right difference). Send the displayed wrist rotation directly; remove this hidden orientation difference from the paired input path.
- Imported Unity pelvis is 0.793 m high, isolated IK pelvis 0.780 m. Offset only the paired simulation display root downward 0.013 m to share the solver world. Other display modes retain their existing positioning.

## Offline replay

Command:

```powershell
.\.venv-teleop\Scripts\python.exe backend/tools/replay_display_world_session.py logs/test_results/bimanual/unity_20260922_160612_134393.jsonl logs/test_results/review_20260922_160555/offline_replay.csv
```

This historical replay predates the later 90°/s² acceleration and rate-5 experiment settings. Its metrics are not validation of those later settings.

The replay uses recorded receipt times and solver tick events, corrects base yaw and wrist orientation to match the new sender, and runs the real isolated solver. It creates no sockets. Recorded engage / tracking flags and displayed positions are retained. This is a counterfactual software replay, not a prediction of changed operator behavior or physical robot dynamics. The new 1.3 cm rendering offset is source-verified but not rendered by this Python replay.

| Metric | Recorded | Corrected replay |
|---|---:|---:|
| Left position error median | 8.16 cm | 1.10 cm |
| Right position error median | 14.88 cm | 2.18 cm |
| Left position error p95 | 21.83 cm | 9.26 cm |
| Right position error p95 | 24.27 cm | 7.28 cm |
| Left position error maximum | 38.13 cm | 38.48 cm |
| Right position error maximum | 33.39 cm | 12.70 cm |

Corrected root yaw discrepancy maximum: 0.0000111 degrees. No blocked ticks or solver exceptions. After the turn (recorded input sequences 1250–1700), orientation median/p95: left 0.51/1.91 degrees, right 1.27/2.62 degrees; position median: left 0.59 cm, right 2.03 cm.

**Partial validation only:** full-session orientation p95 remains 64.7 degrees left / 60.5 degrees right, and transient position errors remain large. Do not describe this as all motion passing or physical validation. Existing motion limits and IK feasibility still constrain tracking. The recorded tracking loss remains reproduced.

## Separate lower-body finding

Robot controller used yaw_sign=-1, max_wz=0.7. Target stayed near +61 degrees while unwrapped robot yaw reached about +272 degrees relative to its first valid sample. At large errors the controller was already requesting wz=-0.7; the available logs do not prove whether the discrepancy originates in downstream command interpretation, policy response, state convention, or external motion. Raw yaw crossed ±180 degrees; quoted relative yaw is unwrapped. Do not solve this by blindly flipping another sign. Lower-body code was not changed or deployed.

## Checks

### Sender-only follow-up

No runtime receiver was modified. Saved sender source calls UDP sendto before writing command_tx, with destination 127.0.0.1:15100. This proves sendto returned successfully, not receiver acceptance. There are no command sequence gaps; the affected interior interval has a maximum send spacing of 22.1 ms. Packet sizes are 362–409 bytes, so a simple 512-byte size overflow does not explain this boundary.

A candidate arm validity rule (`abs(left_q[4]) > 1.92 OR abs(left_q[6]) > 1.57`) marks exactly sequences 2811–3620, matching the entire held-command interval. At sequence 2810 wrist roll is -1.919383; at 2811 it is -1.923592. Near recovery the roll is back in range but wrist yaw remains -1.572084 at 3620; it returns to -1.564402 at 3621, exactly when runtime wz updates again. These thresholds are inferred, not confirmed receiver limits; verify the interface contract before changing sender bounds. This makes incompatible arm payload bounds a strong candidate for why new combined packets were not reflected, rather than incorrect yaw-rate generation alone. Duplicate senders cannot be ruled out from this log; SSH inspection again timed out.

### Follow-up: overrotation narrowed to held actuation input

Cross-correlating the changing wz values before the fault aligns the actuation CSV time with heading-controller elapsed time by +3.060 s (mean squared mismatch 3.79e-8). Runtime CSV t=53.1400714 through 69.3400746 contains 811 consecutive samples with wz=+0.4553555 (16.20 s). That value exactly matches controller command seq=2810. During this hold the controller continues sending new commands, first negative (~-0.156 at runtime t=55), then -0.7 at t=57 and beyond. Runtime resumes wz=-0.7 at t=69.360. Thus the logged actuation input retained an old positive turn command while upstream was commanding reversal; the primary issue is downstream command update/acceptance or stale-command handling, not merely P gain.

The first subsequent command seq=2811 has left wrist-roll -1.923592 rad versus -1.919383 at seq=2810. Joint-range rejection of a combined arm/locomotion packet is a hypothesis worth checking in the runtime receiver; it is not proven without its source/rejection records. Inspect packet acceptance, source arbitration, per-stream freshness, and whether rejection refreshes watchdogs or retains old nonzero velocity. Robot SSH was unreachable during follow-up, so no receiver code was inspected or changed. Repeating physical motion is unnecessary before this read-only/software investigation.

- 24 existing offline unit tests passed.
- Runtime C# compiled successfully using Unity's actual Assembly-CSharp response file and bundled Roslyn; output sent to TEMP, no editor assembly overwritten. Existing deprecated API warnings only.
- Unity Play and physical robot behavior were not executed during review.
