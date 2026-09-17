# Pinch return and re-engage prototype

Body-boundary tracking diagnosis: recorded 16 blocked IK snapshots were reproduced offline. Simulation-cycle QP now uses a 0.5 mm reserve (20.5 mm proposal constraint) while exact sampled-path validation keeps its 20 mm threshold and existing tolerance. On a 500-tick fixed-goal replay this changed 500 holds to 324 and reduced position error from 126 mm to 81 mm. It improves the initial numerical boundary stall but does not guarantee a path or eliminate all holds. See `experiments/twist2_right_arm_manual/replay_mink_boundary.py` and `logs/test_results/mink_boundary_rollout_20260909.json`. New Input restart required; physical candidate profile unchanged. Blocked steps are saved to a per-run `mink_blocked_*.jsonl` file.

Latest settings: simulation acceleration is now **30 deg/s²**, superseding the older 10 deg/s² notes below. Speed caps remain 90/180 deg/s, jerk unchanged. Fresh simulation-cycle feedback also enables recovery after a transient rejected wrist pose: the next pose must pass the original step check against the last accepted position. Rejected poses never update that reference. Persistent invalid tracking still disengages after the existing 0.35 s confirmation; communication timeout and normal physical-path latching are unchanged. Restart Unity Play after recompilation and restart the simulation Input. C# build and 10 Python model/handshake tests passed; actual transient-pose recovery in VR is pending.

Current simulation caps (2026-09-09): shoulder/elbow joints 22–25 use 90 deg/s; wrist joints 26–28 use 180 deg/s. These override older 0.7 rad/s descriptions below for `--simulation-arm-cycle` only. The IK velocity constraint, planner checks and shared tracking/return Ruckig limiter use the same split limits. Acceleration remains 10 deg/s² and jerk is unchanged. Restart the simulation Input to apply. Headless tests passed; peak-speed attainment and VR behavior at these settings have not been measured. Physical G1 settings and the standalone C++ prototype are unchanged.

User verification (2026-09-09): after the Unity handshake fix, the user confirmed the VR simulation flow works: arm tracking → pinch → ready-pose return → re-engage. This supersedes earlier pending visual verification for that tested flow. It does not validate physical G1 operation or all possible return paths.

Unity handshake fix: the simulation feedback marker now blocks calibration in the Unity sender during `returning` and `await_idle`. Inactive pinch feedback advances the backend to `await_active`, after which a fresh Unity calibration is allowed. Stop Unity Play and allow script recompilation before testing this change; restart the simulation Input too. A successful standalone C# build does not verify the Editor/Quest interaction.

Update after VR diagnosis: after return completion, a fresh `pinch_disengaged` packet also satisfies the inactive confirmation. Unity retains that mode until engagement, so the older literal-idle requirement below is superseded. Release pinch and engage again after completion. The observed `trajectory_collision_hold` still needs candidate-pose diagnosis; the status log now includes `arm_cycle_rejection` with current/home/rejected q and clearance. Do not treat this input fix as resolution of the return-path failure.

## MuJoCo live simulation entry (2026-09-09)

With the physical trial ended and the existing Mink Input process closed, run from the project root:

```powershell
.\tools\START_MINK_ARM_CYCLE_SIMULATION.bat
```

Use Unity's simulation display mode. Engage and move the hand, pinch to disengage, wait for `[SIM ARM CYCLE] await_idle`, move out of the engage region so a new idle packet is sent, then engage again. Returning emits `returning`; errors emit `fault` and require restarting this local simulation. The initial pose is the startup model pose, not measured LowState. Only the right arm returns.

The new `--simulation-arm-cycle` flag connects the actual MuJoCo loop to `SimulationReturnCycle`, sharing the tracking Ruckig limiter, with 0.7 rad/s and 10 deg/s² caps. It checks four interpolated samples per shaped step using the existing planner collision/joint-limit checks; this is not continuous collision certification. Velocity is retained when switching to return. A rejected step latches a fault, and return times out at 30 seconds. Completion uses local kinematic pose/velocity near zero for 0.5 seconds, not measured motor settlement. Existing input freshness timeout remains in force.

This option disables candidate UDP 5008 sends and external Gate7 pose feedback. Unity visualization UDP 5006 and Unity input UDP 5005 remain. It starts no Robot/Relay/SSH/DDS. The normal TWIST2 launcher is unchanged. Do not run the old Input concurrently on port 5005; no process is stopped automatically.

Headless verification: actual MuJoCo model with 20 mm configured clearance, two shoulder-forward/return repetitions, preservation of other joints, speed/acceleration caps and injected collision rejection passed. Stateful-trajectory and input-handshake regression tests also passed (10 tests total). The viewer/Quest interaction and visual hand-anchor continuity are still unverified. This return implementation uses the existing Python/Ruckig path; it is not a deployment of the C++ prototype or a validation of matching real motor dynamics.

Scope: SDK-free C++ memory-only prototype in `experiments/twist2_right_arm_manual/arm_cycle_offline.hpp`. It is not included by any physical controller or launcher. Existing deployed pinch-to-damping behavior is unchanged.

## State contract

| State | Event | Result |
| --- | --- | --- |
| Waiting | idle, then fresh active | Capture input/command joint anchors; no target jump; Tracking |
| Tracking | active | Right-arm target = command anchor + input minus input anchor |
| Tracking | explicit normal pinch | Returning; retain velocity and brake toward configured ready pose |
| Returning | active | Ignore engage; continue return |
| Returning | target reached and measured settle | Waiting; require a new idle-to-active edge after completion |
| Any | fault, stale input/feedback, invalid clock/angle | Latched Stopped; no resume in this instance |

Ready pose is supplied by the caller, not inferred from the first hand packet. Only joints 22–28 change. Other target values stay fixed; this is not a model of the real lower-body policy.

Limits: 0.7 rad/s, 10 degrees/s² (0.1745329252 rad/s²). Return retains the previous velocity; an arm initially moving away from home must brake before reversing. Stopping/fault freezes override acceleration limits. Completion requires commanded residual position/velocity below 1e-6, synthetic measured position error <=0.02 rad and speed <=0.05 rad/s for 0.5 s. Numerical residuals are cleared on completion. Return timeout 30 s; input heartbeat timeout 0.25 s; maximum tick gap 0.06 s. These are prototype choices, not hardware-approved thresholds.

## Run locally

In an MSVC developer command prompt at the project root:

```bat
cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs\test_results\test_arm_cycle_offline.exe /Fo:logs\test_results\test_arm_cycle_offline.obj experiments\twist2_right_arm_manual\test_arm_cycle_offline.cpp
logs\test_results\test_arm_cycle_offline.exe
```

Tests exercise three cycles, target anchoring, ignored engage during return, velocity/acceleration bounds, preservation of other joints, fault latching, input/feedback/return timeout, NaN, unexpected idle, invalid clock and rebased joint limits. Feedback is synthetic, not G1 LowState.

## Remaining integration

### Local input handshake added 2026-09-09

`MinkCommandStream(..., simulation_return_handshake=True)` now provides an opt-in gate. Normal pinch increments `return_epoch` and enters `returning`. The local return controller must apply its returned pose to the model and verify settlement before calling `acknowledge_simulation_return(epoch, session_id)`. Wrong epoch/session and acknowledgements after faults are rejected. After acknowledgement, a newly accepted idle packet and then active packet are required. The resulting `engage_clutch` invokes the existing Mink live loop's position/orientation anchor capture. Continue polling while returning; do not accumulate an undrained input queue and then acknowledge.

The default remains off, and no existing launcher enables it. Input rejection, session change, tracking loss, workspace fault and timeout latch the opt-in gate. This is deliberately distinct from legacy stream recovery behavior.

The C++ `arm_cycle_stdio_offline.cpp` adapter uses pipes and ideal previous-target feedback. It has no SDK/socket. Build it with the same MSVC options as above, substituting its name, then run:

```powershell
py -3.11 -B -m unittest discover -s backend/tests -p test_mink_return_handshake.py
py -3.11 -B -m unittest discover -s backend/tests -p test_arm_cycle_stream_integration.py
```

The integration test connects Unity-format bytes through the actual parser/stream to the C++ cycle and back through the completion acknowledgement for two repetitions. Joint goals are synthetic; it does not run IK, FK, Unity, a network receiver or the G1. The main MuJoCo loop still needs the return producer/pose-application integration. No real-model or hand-pose jump claim follows from this pipe test.

- Build a strict packet adapter that distinguishes normal pinch from tracking loss/workspace exit, preserving session/sequence/source-age validation. This prototype accepts trusted typed test events only; it must not be fed raw unvalidated input.
- Preserve every ordered event; the prototype takes one event per tick. Actual queued UDP batching and same-tick pinch/fault handling remain to be integrated.
- Establish an explicit return-complete/re-engage handshake with Unity/Mink. Joint-space offset rebasing here does not implement hand/task-space anchoring; a shifted IK solution needs collision/workspace revalidation.
- Use fresh measured G1 feedback and validate the return path for collisions. A straight joint return is not established collision-free.
- Waiting means movement input is disabled. Omni/locomotion selection, R1 changes and AI restoration are not implemented.
- Do not deploy this prototype as a physical controller. First connect and test the local input path, then review physical integration separately.
