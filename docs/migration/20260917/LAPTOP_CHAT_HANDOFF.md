# G1 Teleop Project Chat Handoff

> **Absolute G1 mutation rule:** Never create, delete, rename, move, or modify any file on the G1; never run a program that can create a log, publish a command, change a service or mode, or otherwise mutate G1 state without the user's explicit approval for that exact action. Inspect source before running diagnostics. Remote-to-local copy is allowed only when it reads existing G1 files and writes exclusively to the Windows project.

Last updated: 2026-09-10

## 2026-09-10 backward-abort CSV retrieval and first review

- After the user reconnected the powered G1, copied `policy.csv`, `run.json`,
  and `result.json` read-only from
  `/home/unitree/g1_mink_cycle_compare_20260909/g1_twist2_trial_1787641096780049_8769`
  to `logs/test_results/g1_pd_backward_abort_20260910`.
- Local hashes match the hashes embedded in `result.json`. The CSV has 575
  rows: capture 49, blend 200, arm initialization 133, settling 57, initial
  trial hold 50, and only 86 outbound samples. Only proximal Kp 40/Kd 5 was
  observed; Kp 48 and 56 did not run.
- Added `analyze_pd_abort.py` and generated `abort_review.json`. The largest
  sampled error was joint 22 shoulder pitch at 11.500 s: target -0.6751 rad,
  measured -0.4420 rad, absolute error 0.2331 rad. The writer checks at 500 Hz,
  while CSV samples near 50 Hz, which explains why the recorded safety reason
  says the intervening error exceeded 0.25 rad although the sampled maximum is
  lower.
- Recorded IMU pitch moved from about +0.0428 rad at the trial hold to +0.0004
  rad at the final CSV sample; roll stayed within 0.0165 rad. IMU sign/history
  alone does not disprove the user's observed backward-fall tendency. Joint 22
  tracking lag clearly dominates this incomplete trial, so the run is not a
  valid PD candidate comparison and must not be ranked as one.

## 2026-09-10 fixed-reach static COM audit

- Added `analyze_pd_reach_com.py` and evaluated the exact polynomial reference
  in `pd_reach_reference.hpp` against the same isolated 29-DoF MuJoCo model.
  This was static forward kinematics only; pelvis and legs were fixed, with no
  Torch policy, contacts, DDS, or physical output.
- Across 201 path samples, the endpoint whole-robot COM moved +15.37 mm in
  MuJoCo world x, +3.84 mm in y, and +12.32 mm in z. Peak horizontal shift was
  15.84 mm at the endpoint. The report is
  `logs/test_results/pd_reach_static_com_20260910.json`.
- The reference therefore does not statically move COM backward. The observed
  backward-fall tendency cannot be attributed to the static arm-mass direction
  alone; lower-policy compensation, tracking lag, momentum, contact/support
  response, or their interaction remain candidates. Static COM is only a
  trajectory-screening metric and does not validate balance.
- Existing offline policy replay code can evaluate policy/observation wiring,
  but its available fixtures are not a validated reproduction of this physical
  event. Do not use them to clear the large reach for another G1 run.

## 2026-09-10 PD sweep physical abort due backward balance motion

- The user ran the explicit PD sweep. During the first Kp 40 forward segment,
  the robot began moving toward a backward fall, so the user stopped the test.
  The Robot console reached about 11 s in `pd_trial_2`; Kp 48 and 56 were never
  attempted.
- The controller independently latched on
  `upper measured tracking error exceeded 0.25 rad`, sealed the CSV at
  `/home/unitree/g1_mink_cycle_compare_20260909/g1_twist2_trial_1787641096780049_8769/policy.csv`,
  wrote `result.json`, and entered its persistent position-hold path. The PC
  SSH console then recorded `client_loop: send disconnect: Connection reset`.
  A follow-up read-only SSH connection timed out, so current G1 process/mode
  state was not remotely verified.
- The automated large reach is not accepted as a PD identification excitation
  under the current lower-body controller. The observation is consistent with
  upper-body center-of-mass motion exceeding the available balance response,
  but exact causality and the stopping action remain to be confirmed from the
  robot state and CSV.
- Re-blocked all Robot/All launcher modes, including `-PdSweep`, immediately
  after the event. Do not rerun this sweep. Offline analysis and remote CSV
  retrieval may resume only after the user confirms the robot is stable and
  connectivity returns.

## 2026-09-10 PD-sweep-only launcher enablement

- Added `tools/START_TWIST2_PD_SWEEP_TO_VR.bat`. It starts the existing four
  windows with the `today` profile and `-PdSweep`; Robot still requires the
  operator to review its summary and type `P` manually.
- The general Robot/All path remains blocked. Only the explicit `-PdSweep`
  path may reach SSH. Its one owner performs Kp 40/48/56, then remains alive in
  `udp_ready` for VR tracking. Closing the Robot/SSH window while it owns
  LowCmd is still prohibited because no successor-owner shutdown exists.
- Updated the no-overlap launcher regression to enforce that narrow exception.
  This change only prepared the user-run command; Codex did not launch it.

## 2026-09-10 one-owner PD sweep to VR transition

- Changed the completed `--pd-sweep-trial` behavior: after Kp 40, 48, and 56
  each finish their three cycles, the process does not latch or stop. It keeps
  the same 500 Hz TWIST2 LowCmd owner, marks the sweep complete, and transitions
  to the existing `udp_ready` state so Unity/Mink can engage and re-engage.
- The G1 UDP socket is bound before the sweep begins so an already-running
  Windows relay does not receive a closed-port ICMP failure. Incoming packets
  are not enabled as commands during the sweep. At transition, the bounded
  pre-sweep socket backlog is discarded before the watchdog and normal live
  receiver are enabled; only subsequent fresh idle/active packets can engage.
- Added `pd_sweep_completed` to result metadata and a `-PdSweep` launcher
  switch that selects `--pd-sweep-trial` only in the Robot command while Input,
  Relay, and Camera retain their existing roles. The main Robot/All execution
  block remains in place pending a complete operating procedure.
- Persistent-runtime, sweep-analysis, and no-overlap checks passed (7 tests),
  PowerShell Check mode parsed the new switch, and the current source clean
  built on the G1 ARM toolchain. The deployed aarch64 ELF SHA256 is
  `bf0670343edecfeb0f84e5df5f2c0203bd29ada1e479d7adee2a87659aeeb916`.
  The executable was not run; no DDS publisher or motor output was created.
- A subsequent control-flow audit found that PD initialization was not feeding
  current measured q/dq into `MinkLiveCycleTarget`; that could leave a real PD
  run waiting in `arm_initializing` indefinitely. The PD branch now supplies
  all 29 measured positions and velocities with the current LowState receipt
  time before evaluating initializer readiness. The regression source check
  covers this call. The final corrected ARM rebuild succeeded and the current
  deployed ELF SHA256 is
  `812a7aabb51aa935fed86d8cec4f4b6baf78bfa1dd331c83892e9bc57785ef9e`.

## 2026-09-10 detached-owner feasibility boundary

- Read-only G1 inspection found no `tmux` or `screen`. `/usr/bin/setsid` and
  `/usr/bin/systemd-run` exist; the unitree user manager is active, but login
  linger is disabled. No matching TWIST2/LowCmd process was running during the
  check.
- A detached process would reduce accidental SSH-window termination but would
  not create a verified successor owner or a safe way to terminate that
  process. It was therefore not adopted or started, and no linger/service
  setting was changed.
- Added sweep-analysis regression coverage: a complete synthetic 40/48/56
  trace ranks by recorded proximal RMSE, while a missing candidate cycle/phase
  is rejected instead of producing a misleading winner.

## 2026-09-10 one-owner three-candidate PD sweep build

- Added `--pd-sweep-trial`: one process and one continuous TWIST2 LowCmd owner
  runs the same three-cycle reach/return at proximal Kp 40, 48, then 56, with
  proximal Kd fixed at 5 and wrist gains unchanged at 20/1. Each gain change
  occurs only after the preceding trajectory has returned to its ready pose.
- The 500 Hz writer takes a mutex-protected gain snapshot per command cycle, so
  the policy thread cannot race a partially updated Kp/Kd array. Effective
  gains remain recorded in every writer frame, which identifies each candidate
  segment without relying on console timing.
- Added `analyze_pd_sweep.py`. It requires all three candidates and all phases
  of all three cycles, then ranks proximal tracking RMSE while also reporting
  per-joint peak error, speed, and estimated torque. A lowest-RMSE candidate is
  only eligible after torque limiting, oscillation, body attitude, completion,
  and operator observations are accepted.
- Transferred the updated controller and gain parser to the existing isolated
  G1 folder and clean-built the ARM target. Compilation and linking reached
  100%. The surrounding SSH wrapper returned exit 1 because its shell return
  code variable was incorrectly escaped, but a separate read-only check
  confirmed the output is an ARM aarch64 ELF. A final source update added the
  completed-sweep status classification and was rebuilt successfully; the
  current deployed SHA256 is
  `5eefb927745c987612f00d7095f2aec580742e18f1d6c91bfd9ca25382351b69`.
  The executable was not run and no DDS publisher or motor output was created.

## 2026-09-10 persistent-owner PD reach build

- Enabled the existing fixed three-cycle `--pd-reach-trial` in the current
  no-AI-select/no-damping cycle controller. Kp/Kd overrides remain runtime
  arguments, so changing a candidate does not require another compile.
- A completed trial returns to the reference ready pose. Before entering the
  controller's non-returning TWIST2 position hold, the code now closes the
  periodic CSV and writes `result.json`, including
  `owner_state=persistent_twist2_position_hold`. This prevents the useful
  comparison record from being left unsealed merely because the sole LowCmd
  owner intentionally stays alive.
- Added `test_persistent_pd_runtime.py`. The persistent-PD invariants, existing
  no-overlap checks, gain-comparison tests, and PD offline analysis tests all
  passed: 13 tests total. These were source/offline checks without DDS output.
- Transferred the two current source files to the existing isolated G1 folder
  `/home/unitree/g1_mink_cycle_compare_20260909` and clean-built the ARM target.
  Build and link completed at 100%; the output is an ARM aarch64 ELF with
  SHA256 `e8659e5c1704abd477b7057980e1b1a00a48688a74c9eacddc381aa406495f8f`.
  Existing SDK/Torch warnings and a G1/PC clock-skew warning were emitted; no
  compile or link error occurred. The executable was not run.
- The launcher expected hash was updated, but Robot/All remains blocked. One
  PD candidate can now finish and seal its data without dropping ownership,
  but safely switching from that persistent owner to a second candidate is
  still unresolved. Running separate candidates by closing SSH would recreate
  the owner-loss problem; a single-process multi-candidate sequence or a
  verified successor-owner transition is required first.

## 2026-09-10 safe rebuild and saved two-cycle PD replay review

- With the user's instruction to transfer the source, copied the no-AI-select
  `twist2_mink_cycle_trial.cpp` and `mink_live_cycle_contract.hpp` into the
  existing isolated G1 folder
  `/home/unitree/g1_mink_cycle_compare_20260909` and completed a clean ARM
  build. The new aarch64 ELF SHA256 is
  `7a58959e9b89f1e994e109bed1feb1ef4b73a599639e256149934faccafe6f6d`.
  No controller or motor-output program was run.
- Preserved the earlier successful two forward/return VR movements from
  `/home/unitree/g1_mink_cycle_compare_20260909/g1_twist2_trial_1787641939651017_9307`
  under `logs/test_results/pd_replay_source_20260910`. The copied CSV SHA256
  matches `result.json`:
  `5b2fd408c72ad3c0e5929879e98976c5ffd675ca7e148aa32155ab2f73e525c8`.
  It contains 871 unique `arm_tracking` samples over 17.40 s.
- Added `analyze_vr_pd_replay.py` and an offline unit test. The generated
  `vr_pd_replay_review.json` reports joint-by-joint target range, RMSE, MAE,
  p95/peak error, approximate lag, and peak measured speed. The largest RMSE
  in this run was joint 22 at 0.0641 rad; joint 23 was 0.0587 rad and joint 25
  was 0.0535 rad. Applied gains were Kp/Kd 40/5 for joints 22-25 and 20/1 for
  joints 26-28.
- This one-gain closed-loop trace can score the gains that were actually used,
  and is retained as a fixed replay/reference trace. It cannot rank untried PD
  gains by replay alone because changing Kp/Kd changes the subsequent measured
  positions, velocities, torque limiting, and body response. Counterfactual
  gain search requires either a separately validated plant model or several
  controlled excitation runs with different gains. Offline replay is not a
  physical safety validation.
- Updated the PC launcher's required hash to the safe ELF. Robot/All launch
  remains blocked because there is still no verified successor-owner shutdown;
  closing SSH while this LowCmd owner is active can remove motor effort.
- Added a minimal follow-up plan generated from the replay review. It fixes Kd
  at the user-selected value 5 for proximal joints, leaves wrist gains at 20/1,
  and compares proximal Kp 40, 48, then 56 on the same scripted three-cycle
  reach. This is a data-collection order rather than an offline prediction of
  the optimum; stop criteria prevent advancing after a fault, torque limiting,
  growing oscillation, or failed baseline repeatability.

## 2026-09-10 OMNI lower-body input audit

- Inspected the installed Omni Connect 1.2.93 files. The application runtime is
  present, but no Unity package, C# SDK, assembly definition, native header, or
  import library is installed; no matching Unity SDK package was found in
  Downloads. Pairing/login remain unverified.
- Inspected the actual TWIST2 observation builder. Its 1,432-value input is
  built from 35 mimic values, 92 proprioceptive/current values, ten historical
  127-value frames, and another mimic block. The exposed mimic input contains a
  fixed 0.8 value and 29 joint references, with no documented forward,
  lateral, or yaw-rate command slot.
- Therefore an Omni walking vector cannot be inserted directly into the current
  TorchScript observation without inventing untrained semantics. The next
  dependency is the matching Omni Unity SDK plus either a lower-body policy
  with an explicit velocity-command contract or a verified Omni-to-mimic
  trajectory generator. Detailed checklist: `docs/OMNI_TWIST2_INPUT_AUDIT.md`.
- No Unity project, G1 file, DDS path, publisher, service, or physical output was
  changed during this audit.


## 2026-09-10 controller-overlap noise incident

- During the failed Q shutdown, the native TWIST2 process remained alive in its
  latched 500 Hz LowCmd position-hold loop (remote PID 6970). The user then ran
  `python3 ~/restore_g1_ai_mode.py eth0`. The robot immediately produced a loud
  repeated mechanical noise, so the user removed the battery and powered it
  down. Do not power on or repeat this recovery sequence until the robot has
  been physically inspected.
- The checked local copy of `restore_g1_ai_mode.py` performs `CheckMode()`, then
  unconditionally calls `SelectMode("ai")`, then checks the mode again. It does
  not detect an existing TWIST2/LowCmd owner and does not coordinate ownership.
- The most plausible current explanation is a control-ownership overlap or
  abrupt controller transition between the still-running 500 Hz LowCmd writer
  and the selected AI service. This is an inference; no motor-side diagnostic
  was captured before battery removal, so the exact mechanical source is not
  proven.
- The current explicit-Q candidate also calls `SelectMode("ai")` while its
  LowCmd writer remains active. This physical incident invalidates that handoff
  design as a test candidate. Do not run the deployed Q ELF or the standalone
  restore script while any TWIST2/LowCmd process exists. Disable the Q AI-select
  path before any later deployment.
- The PC launcher now blocks `All` and `Robot` modes, so the deployed Q ELF
  cannot be started accidentally. The local C++ Q key was changed to checked
  safe return plus persistent TWIST2 hold and no longer arms the AI-select path.
  This safer local source has not been transferred or built on the powered-off
  G1.
- The Q state-machine failure preceding the incident was separate: Q was issued
  while the cycle was already `udp_ready`; it unnecessarily entered Returning,
  never received/completed the new return stream, and latched after the return
  timeout. The stored request reason masked the actual timeout in the message.
- Local state-machine remediation now treats a handback request received in
  Waiting/`udp_ready` as immediately safe-hold-ready without changing epoch or
  entering Returning. A later real contract failure overwrites the request
  label, so `input_timeout` or `return_timeout` is reported as the fault.
  Regression coverage increased to 40 C++ scenarios; the verified-handoff gate
  and all 15 Python bridge/relay tests also pass. No G1 source transfer, build,
  service call, DDS publisher, or motor output was performed for this fix.
- The dangerous AI-select implementation was then removed entirely from the
  local `twist2_mink_cycle_trial.cpp`; the file now contains no
  `SelectMode("ai")` call. Q can only request a checked safe return followed by
  continued TWIST2 ownership. The deployed G1 ELF is still the blocked older
  build and must not be run.
- The local reference `restore_g1_ai_mode.py` now scans `/proc` before importing
  or initializing the Unitree SDK and refuses with exit code 3 if a known
  TWIST2/LowCmd candidate is running. Two offline guard tests pass. This guard
  is only a known-process interlock, not proof that no other publisher exists,
  and it has not been copied to the powered-off G1.
- SDK/source review found no atomic owner-swap operation: the available pattern
  consists of `ReleaseMode`, `SelectMode`, and `CheckMode`. Selecting AI before
  stopping LowCmd can overlap controllers; stopping LowCmd first creates an
  unowned interval whose physical behavior is not guaranteed. A no-damping,
  no-overlap handoff therefore needs an owner-side integration/acknowledgement
  mechanism rather than another timing-only retry.
- Final runtime direction after the incident: keep one full-body owner alive for
  the whole teleoperation session. OMNI/lower-body policy remains active while
  pinch, tracking loss, Select/B, Ctrl+C, P, or Q return the arm to safe hold;
  none of those events selects AI or terminates LowCmd. Shutdown is a separate
  maintenance boundary until a cooperative successor-owner acknowledgement is
  available.
- Updated all active Q help text to say safe arm return and continued TWIST2
  ownership; removed the stale `Q=end`/`SHUTDOWN COMPLETE` launcher wording.
  Added `test_no_overlap_runtime.py`, which asserts that the live controller has
  no `SelectMode("ai")` call and that `All`/`Robot` are blocked before the SSH
  command. Both new regression tests pass, along with the 40 C++ cycle cases,
  15 bridge/relay cases, and two restore-script process-guard tests.


## 2026-09-10 explicit Q verified-Regular handoff build

- After the first physical Q attempt, the user closed the Robot PowerShell
  during the checked return. The SSH-owned controller then disappeared before
  verified handoff, Input reported `return_timeout`/feedback-loss synchronization,
  and the robot fell back to damping. Arm tracking before shutdown was reported
  successful. This does not establish that the Q handoff itself completed.
- Added unambiguous Robot-window messages: Q acceptance warns not to close the
  window, verification failure says TWIST2 hold remains active, and only a
  successful verified handoff prints `[SHUTDOWN COMPLETE]`. The launcher also
  identifies the Robot window as the only place to press Q.
- Re-ran 38 C++ candidate scenarios, the verified-handoff gate test, and 15
  Python bridge/relay tests successfully. Clean ARM rebuild completed; the new
  deployed ELF SHA256 and launcher-required hash are
  `7a127384b22a7e019802972febaa2a41e264208112baf78c60b3f5888e23606d`.
  The rebuilt controller has not been run physically.

- Added a local explicit `Q` shutdown candidate. It waits for the arm's checked
  safe return, selects the `ai` motion service, requests the Regular FSM captured
  at startup, and keeps the existing LowCmd writer alive while requiring the
  `ai` service name, expected FSM, and valid fresh LowState continuously for one
  second. The writer stops only after that combined verification succeeds.
- If selection, FSM restore, or the eight-second verification fails, the code
  attempts to release the selected mode and remains in the existing position-hold
  owner instead of sending damping output.
- Offline validation passed: the verified-handoff gate test, 38 C++ candidate
  contract scenarios, and 15 Python bridge/relay tests. These checks created no
  SDK object, DDS publisher, or motor command.
- With explicit user approval, transferred only
  `twist2_mink_cycle_trial.cpp` and `verified_regular_handoff.hpp` to
  `/home/unitree/g1_mink_cycle_compare_20260909` and clean-built
  `g1_twist2_mink_cycle_trial`. The aarch64 build completed at 100%; its SHA256 is
  `bafd5e88786aafdec68546a1b889682e3f0c0f691787a81a976e63e6ace2606c`.
  The build emitted existing SDK, Torch, unused-variable, and clock-skew warnings
  but no compiler/linker error.
- The new ELF was not executed. After separate explicit approval, the launcher
  expected hash was updated to this exact ELF. Physical ownership transfer,
  avoidance of an effort gap,
  and Regular stabilization remain unverified. `SelectMode("ai")` while the
  TWIST2 writer is still active may have controller arbitration behavior that
  offline tests cannot establish; a physical Q test requires separate approval.

## 2026-09-10 persistent TWIST2 owner after failed automatic handoff

### First persistent-owner physical result and post-return relay fix

- The physical run recorded in
  `cycle_packets_20260910_134342_5029522.jsonl` successfully entered one
  17.4-second active interval (1,026 active packets). The user moved the arm
  forward and back twice during that engage. Active packet source age remained
  at or below 47 ms and G1 ACK state remained `tracking`.
- One pinch changed the stream to `return`; G1 ACK changed to `returning` and
  reached `waiting` about 4.3 seconds later. The Input console displayed G1
  measured `READY`, so the checked return itself completed.
- After that completed cycle, Unity stopped refreshing idle input. The relay
  dropped stale idle at 266 ms once but then treated it as fatal because its
  old exemption applied only before the first active packet. That relay exit
  caused the later PC feedback-loss synchronization exception. It was not a
  tracking-time G1 fault.
- G1 `result.json` reports `reason=operator signal`, 3,987 policy samples, and
  the console reports 39,880 LowCmd writes at 500.000 Hz. It reports no damping
  command and no automatic AI handoff; the final phase was `udp_ready`.
- The relay now discards stale `idle` packets both before engage and after a
  completed return. Active/return packets still require source age at most
  250 ms. All 15 offline Python bridge/relay tests pass after adding the
  post-active stale-idle regression. No G1 C++ binary change or physical rerun
  was made for this relay-only fix.

### Ctrl+C no longer stops the active owner (deployed, not run)

### Explicit Q verified-Regular shutdown candidate (local only)

- A separate `Q` command is now staged locally. It first requests the same
  checked safe-waypoint/ready return. Pinch, Select/B, P, Ctrl+C, tracking loss,
  and faults do not request service ownership transfer.
- Only after the safe return reports ready does Q call `SelectMode("ai")`,
  restore the captured Regular FSM ID, and require the `ai` service name,
  matching FSM ID, and fresh valid LowState continuously for one second. The
  LowCmd writer remains active during this verification and stops only after
  the entire gate passes.
- A failed `SelectMode`, `SetFsmId`, state check, or eight-second verification
  attempts `ReleaseMode` rollback and latches the existing TWIST2 position
  hold. It never treats service-name selection alone as successful.
- `verified_regular_handoff.hpp` isolates the stable-success gate. Its offline
  test verifies the full one-second window and reset on wrong FSM, service,
  result code, or invalid state. The new gate test, all 38 cycle-contract
  scenarios, and all 15 bridge/relay tests pass without SDK, DDS, publisher, or
  physical output.
- This code has not yet had a full ARM SDK compile and has not been transferred
  to G1. The handoff still needs a supported physical trial because offline
  tests cannot establish how this G1 arbitrates simultaneous LowCmd hold and
  `SelectMode("ai")`.

- The user ended the first persistent-owner trial with Ctrl+C because no
  shutdown procedure was available. The deployed revision interpreted that as
  `operator signal`, stopped the 500 Hz writer, and had no successor owner;
  consequently motor effort was lost even though the program emitted no
  damping LowCmd.
- The local C++ candidate now counts operator signals. Before takeover,
  Ctrl+C still cancels preflight. After takeover, Ctrl+C requests the same
  checked safe-waypoint/ready return used by other recoverable events. It does
  not leave the policy loop, latch the controller, stop LowCmd, or exit. After
  return, TWIST2 continues position hold as the sole owner.
- A latched hard-fault hold also no longer stops the writer after another
  Ctrl+C/SIGTERM: `Controller::finish()` is non-returning and keeps the last
  valid position command active. Only external process destruction, host loss,
  or power loss can terminate that hold in this interim design.
- Unitree's public `MotionSwitcherClient` API exposes only `CheckMode`,
  `SelectMode`, and `ReleaseMode`. The official XR teleoperation helper exits
  debug mode with `SelectMode("ai")`, but it does not define an atomic handoff
  or a G1 Regular-FSM stabilization condition. Because this G1 previously
  reported service `ai` while Regular restoration verification failed, service
  selection alone is not accepted as permission to stop LowCmd.
- This prevents signal-driven owner loss but deliberately does not yet provide a
  completed process shutdown. A normal shutdown still needs a verified
  successor-owner protocol; force-killing or closing the SSH window can still
  remove motor effort.
- Offline verification remains 38 passing C++ contract scenarios and 15
  passing Python bridge/relay tests. These tests do not exercise SDK, DDS, or
  physical output. After connection, the corrected source was transferred to
  `/home/unitree/g1_mink_cycle_compare_20260909` and the ARM clean build linked
  successfully. The first build exposed and did not link an incorrect wrapper
  call with two arguments; that call was corrected to the wrapper's one-argument
  API and a second clean build reached 100%. Deployed source SHA256 is
  `ef123197924d31cf7ae595180eb6a9ac51d8a17328b31b774e87e18193daf60f`;
  deployed aarch64 ELF SHA256 is
  `3806d6f8d30b486025c8dc65922bf795e5d5137708d77a27982adb2afc925316`.
  The launcher now requires that ELF hash. The controller was not run.

- The latest physical attempt did not apply a VR arm target. The G1 CSV ended
  in `udp_ready` with `arm_alpha=0`; the PC packet record shows that ACKs
  stopped before the first active packet. While Waiting, the Windows input
  sequence advanced from 16 to 83 and its sample clock jumped by about 1.14 s.
  The strict native sample-clock check rejected that later idle packet. Engage
  exposed the already-lost feedback condition rather than causing the original
  failure.
- The controller then attempted the previous automatic `ai`/Regular handoff.
  Its result recorded `automatic Regular restore verification failed`, and the
  user observed the robot in damping after disconnection. The user restored it
  manually and confirmed that the supported robot was stable.
- With the user's explicit acceptance of the operating risk, the cycle
  candidate no longer calls `SelectMode("ai")` and no longer stops its LowCmd
  writer automatically on a recoverable return or fault. After a checked
  safe-waypoint/ready return, it clears the return state and continues as the
  single TWIST2 command owner so a later engage can resume tracking. A latched
  hard fault holds the last valid position command until the operator
  interrupts the process; no damping LowCmd is generated by this candidate.
- Waiting/idle packets may now rebase one long source-clock gap instead of
  latching a hard error. Normal Tracking and Returning clock continuity remains
  strict. If G1 feedback ACK disappears after a session has been established,
  the PC bridge requests a checked return once and continues sending that
  return stream instead of immediately crashing.
- Limits: total PC-to-G1 loss prevents the PC-generated waypoint path from
  reaching the robot, so the G1 side can only hold its last valid target. An
  invalid LowState also cannot support a measured return. Killing the sole
  owner or losing power is outside this program's continuity guarantee. This
  is an explicitly approved integration experiment, not a physical safety
  validation.
- Offline verification after the change passed 38 C++ contract scenarios and
  15 Python bridge tests. These tests create no Unitree SDK object, socket,
  publisher, or physical output. Static search of the active candidate path
  found no R1 behavior, `SelectMode("ai")`, or legacy restore function.
- The three changed C++ files were copied to
  `/home/unitree/g1_mink_cycle_compare_20260909` and the ARM target was rebuilt
  with `--clean-first`. Build and link reached 100%. Deployed hashes are
  `30196c13abad2211bed4445cdd25dcd61fa8290498e8a4d6a2aa21c30d7dd2f2`
  for `twist2_mink_cycle_trial.cpp`,
  `538111b90f482c94da9fb6b095abcc1b5b3c16fe280adeaf566c0abe179dc1a7`
  for `mink_live_cycle_contract.hpp`,
  `92bae6b8af5ed3e0ef6128bef4c98fb102abfa3d0d700da43549e01598f11499`
  for `mink_live_cycle_target.hpp`, and
  `cab40e851cbd02cf0b744f27e3a87c5c860c0ff29da25ebea4f095dcf6905e99`
  for the aarch64 executable. The launcher now requires that executable hash.
  The physical controller was not run as part of this change.

## 2026-09-10 Regular restore validation after unsupported balance query

- The first FSM-aware physical start stopped before `ReleaseMode` with
  `fsm_result=0 fsm_id=501 balance_result=7301`. No lowcmd takeover or arm
  motion occurred. FSM 501 was readable, while this installed locomotion
  service did not provide the balance-state query used by the first draft.
- Per explicit user approval, balance-mode capture is now optional when that
  query is unavailable. The Regular FSM requirement remains mandatory: startup
  still requires a successful FSM read and ID 500 or 501.
- Automatic restore now succeeds only after selecting service `ai`, restoring
  and rereading the captured FSM, and observing one continuous second of fresh,
  valid LowState. The stability check includes the preflight joint-speed,
  joint-margin, IMU, motor-state and leg-home-error checks. A captured balance
  mode is also restored and verified when the API supports it.
- If service selection succeeds but FSM/LowState verification fails, lowcmd is
  left stopped to avoid two command owners and the console reports handoff state
  as unknown. It no longer incorrectly claims that the previous position-hold
  writer is active after ownership transferred.
- Local `g++ -std=c++17 -Wall -Wextra -Werror` regression verification passed
  all 36 offline cycle-contract scenarios without SDK, socket or publisher.
- The updated C++ source was copied to
  `/home/unitree/g1_mink_cycle_compare_20260909/twist2_mink_cycle_trial.cpp`.
  The first ordinary rebuild compiled the object but retained the old binary
  because the generated Makefiles were about 21 minutes ahead of the G1 clock.
  A target `--clean-first` rebuild then compiled and linked to 100%. The new
  aarch64 ELF SHA256 is
  `2515d1ac26ade4fe7d822e258cbaff70b97f2d5a846c85fb8aca3920a1b3a13c`;
  deployed source SHA256 is
  `7dad2172c835f46c6151dc5eabe195f0e2a29c627b351e1d82bc179ef779c707`.
  No physical controller was started in this deployment step.
- `START_TWIST2_MINK_CYCLE_CANDIDATE.ps1` now checks that exact G1
  executable hash with `sha256sum -c` before it can launch the candidate. The
  launcher's Check and All/Preview paths completed locally without starting a
  process.

## 2026-09-10 Regular FSM 501 capture and restore added

- Read-only queries on the powered G1 returned MotionSwitcher
  `form=0,name=ai` and locomotion `fsm_id=501`. The installed Python client did
  not expose `GetFsmMode`, but the installed C++ `LocoClient` exposes
  `GetFsmId`, `GetBalanceMode`, `SetFsmId`, and `SetBalanceMode`.
- Diagnosis correction: the preceding `ai_restored=true` only proved that
  MotionSwitcher selected the `ai` service. It did not prove restoration of the
  Regular locomotion FSM, so the status could be true while the robot remained
  in or passed through a damping state.
- Before `ReleaseMode`, the candidate reads and requires an actual Regular FSM
  ID of 500 or 501. The initial version also required balance-mode capture; the
  newer section above records why that query became optional while FSM and
  LowState verification remain mandatory.
  Generic `LocoClient::Start()` is deliberately not used because it hardcodes
  FSM 500 while this 3-DoF-waist G1 reported Regular FSM 501.
- Result fields and messages now use `regular_restore_attempted`,
  `regular_restored`, and `automatic_regular_restored`; service selection alone
  is no longer labeled a successful AI/Regular restore.
- The updated G1 ARM target compiled and linked successfully and was not run.
  New ELF SHA256:
  `9d6cd1002de23d6247a887b7a7b3970f2ef3d83bee11fbbcb557cd025180e6b4`.
  Physical verification of the FSM handback remains pending.

## 2026-09-10 Pre-engage input-timeout false stop fixed

- The first no-damping physical candidate run remained in `udp_ready` with
  `arm_alpha=0` and never entered arm tracking. It stopped after 14.18 seconds;
  the summary reported `ai_restore_attempted=true` and `ai_restored=true`.
  The copied CSV is `logs/test_results/policy_20260910_start_damping.csv`.
- Root cause: one fresh pre-engage `idle` packet set the native contract's
  `seen_` flag. When the upstream Unity sample later became older than 0.25 s,
  the relay correctly stopped forwarding stale idle packets, but the native
  unconditional packet watchdog then raised `input_timeout` while still in
  Waiting. The user perceived the resulting immediate handback as damping;
  the CSV confirms no tracking target was applied and verified AI restore
  completed.
- `MinkLiveCycleContract::Poll` now applies the 0.25 s input watchdog only in
  Tracking and Returning. Waiting can remain idle indefinitely before engage;
  feedback, state, motor and operator guards remain active. Once motion starts,
  loss of fresh input still requests the established return/AI handback.
- Added a regression scenario that receives idle, waits past 0.25 s, and must
  remain Waiting. WSL `g++ -std=c++17 -Wall -Wextra -Werror` verification passed
  36 offline scenarios with no SDK, socket or publisher.
- The corrected header was deployed and the G1 ARM target rebuilt but not run.
  New ELF SHA256:
  `ec28f56bc40e46c552cc66b795ba67f48d7ed2168db09afe17329ef463d505d8`.

## 2026-09-10 R1 removal and no-damping handback candidate deployed

- User corrected the requirement from "R1 release has no effect" to complete
  removal of the R1 feature. The current local cycle candidate has no `kR1`,
  R1 button read, deadman condition, `Controls.r1` field, R1 test scenario, or
  R1 launcher/runtime message. `Controls` now contains only the abstract stop
  field used by offline contract tests; live Select/B is handled as a checked
  safe-waypoint return request in the controller.
- Static search across the current cycle source, contract, target wrapper,
  stdio fixture, contract test and candidate launcher found zero `R1`, `.r1`,
  `kR1`, or `deadman` references. MSVC `/W4 /WX` contract test passed 35
  scenarios; measured initialization/ACK wrapper test passed.
- After the user powered and connected the G1, `twist2_mink_cycle_trial.cpp`,
  `mink_live_cycle_contract.hpp`, and `mink_live_cycle_target.hpp` were copied to
  `/home/unitree/g1_mink_cycle_compare_20260909` and the ARM target was rebuilt
  with `--clean-first`. The build completed at 100%; clock-skew warnings came
  from future-dated generated Makefiles but did not prevent compilation/linking.
- The current controlled joints use the last valid position target with their
  configured `kp`/`kd` while an untrusted-state handback is attempted. They are
  not sent a zero-gain damping command. Valid-state stop/fault requests use the
  checked outward waypoint and ready-pose return before AI handback. If direct
  AI selection fails, position hold remains active rather than releasing motor
  effort. This fallback cannot claim to traverse the waypoint when robot state
  is already stale or invalid.
- Remote static search confirmed zero `R1` or `deadman` references in the three
  deployed sources. The rebuilt aarch64 ELF SHA256 is
  `c34d9ff755db6472b17309ca98dd2585f0d83d17fe80eeb86c19e37c75474925`.
  It was compiled and inspected only; it was not executed and no physical G1
  behavior was validated in this deployment step.

## 2026-09-10 R1 deadman removed; Select/B uses controlled AI handback

- Per user instruction, the live cycle candidate no longer reads R1 as an
  arming, tracking, or return condition. R1 may be released before startup and
  throughout operation without changing the cycle state.
- Preflight still requires active AI standing, fresh valid LowState, acceptable
  pose/velocity/IMU and healthy motors. It now only requires Select/B to be
  released; no person must hold R1.
- During live tracking, Select or B requests the existing two-stage checked
  return: current pose -> outward safe waypoint -> Mink ready pose -> measured
  settle -> stop the single lowcmd writer -> SelectMode("ai") -> verify `ai`.
  Keyboard P and normal 300-second completion use the same controlled handback.
- Select/B is therefore no longer an immediate damping command in this
  candidate. Invalid/stale robot state, communication loss, motor fault,
  excessive IMU attitude, true hard joint-bound crossing, Ctrl+C/process
  interruption, or failed AI selection remain hard fault paths because the
  return trajectory cannot be trusted or completed in those conditions.
- Offline native contract: 36 scenarios passed, including continued Tracking
  with `R1=false` and Select/B automatic return/settle. The G1 ARM target built
  successfully and was not executed.
- G1 backup before this change:
  `/home/unitree/g1_mink_cycle_compare_20260909/backup_no_r1_20260910`.
  Final deployed ARM ELF SHA256 is
  `c542d86006508687f62544a5a67774a42101ae3d94df6c4810008668f025c668`.
  It is an ARM aarch64 ELF; it was compiled only and not executed.

## 2026-09-10 Joint-limit log diagnosis and safe-waypoint AI handback

- Latest physical run CSV `g1_twist2_trial_1787640906033582_8071/policy.csv`
  stopped at right shoulder-yaw joint 24. Final measured q was 2.5679438 rad;
  the native upper soft-stop boundary was 2.5680 rad, while the requested target
  was 2.5636153 rad. This was a 0.00433 rad measured-following difference at a
  target that had only 0.00438 rad reserve, not a position/orientation IK error.
- Live PC joint bounds now keep 0.0801 rad from the native hard bounds rather
  than 0.0501 rad. The existing native state guard stays at 0.05 rad, leaving
  about 0.03 rad for braking and measured servo following.
- Ordinary R1 release, pinch/tracking loss, protocol acceleration/speed/path
  rejection, and right-arm approach to the 0.08 rad boundary now enter the
  checked return flow. G1-originated return ACKs explicitly start the same PC
  return planner.
- Return is two stage: the controlled right arm first reaches the outward
  waypoint `[10, -35, 0, 70, 0, 0, 0] deg`, then reaches the existing Mink ready
  pose. Only after measured ready settling does the owner stop lowcmd, select
  `ai`, and verify the selected mode. This keeps the existing single lowcmd
  owner through the return.
- Select/B, invalid/stale LowState, motor fault/temperature, IMU/mode faults, a
  true hard joint-bound crossing, or failed AI selection remain emergency
  damping paths. Removing those would make a checked return depend on state that
  the controller has already classified as untrustworthy.
- Offline verification: actual MuJoCo model completed the collision-checked
  waypoint/home return twice; 14 bridge/ACK synchronization tests passed; the
  native target wrapper compiled with MSVC `/W4 /WX` and passed. G1 ARM target
  compiled and linked successfully but was not executed.
- G1 backup: `/home/unitree/g1_mink_cycle_compare_20260909/backup_safe_waypoint_20260910`.
  New ARM ELF SHA256:
  `75463325758a58722831c0aeb2f49965517e35c33050f7fb8158a2fedb6a1417`.
  This build result is not physical validation of the new return trajectory or
  AI handback.

## 2026-09-10 Recoverable fault return and verified AI handback candidate

- User approved all deployment steps. Existing G1 source and binary were copied
  to /home/unitree/g1_mink_cycle_compare_20260909/backup_auto_ai_20260910;
  preserved binary SHA256 is 6985bdc5fd3991fbf18f760e032f8b8f776f853b39dedbfcfe98cff54cdb4761.
- Updated three source files were transferred and compiled on G1 ARM. Clock skew
  initially skipped recompilation, so sources were touched and the target rebuilt
  with --clean-first. New binary SHA256 is
  99372ded16a4af6e34b8fb93389bcd66761ec5b9722a5c9e535bd1d396fe87fe;
  strings confirms automatic_ai_restored and the R1-release handback message.
  The binary was not executed and no motor command was sent.

- User clarified the final operational flow should not require a damping cycle
  after ordinary tracking faults. Local candidate now classifies joint_limit,
  speed, acceleration, unexpected_tracking_event and path_rejected while tracking
  as recoverable: preserve the last accepted target, enter the existing PC-generated
  return protocol, and require the measured initial-pose settle gate before handback.
- After that gate, the native owner stops its lowcmd writer, calls
  MotionSwitcher SelectMode("ai"), and verifies CheckMode name=="ai". A nonzero
  SelectMode result restarts the existing damping writer; if selection succeeds
  but verification fails, lowcmd remains stopped to avoid competing command owners.
- LowState/feedback/input timeout, malformed/provenance/session/clock faults,
  Select/B/p stops and robot-state protections remain hard damping
  conditions because a checked return cannot be generated from untrusted state.
- R1 release is now an ordinary handback request, including while the initial
  pose is still settling: finish initialization, use the checked return protocol,
  stop lowcmd, then select and verify AI. Select/B remains the independent
  immediate damping control. Preflight still requires R1 held before takeover.
- Offline contract test: PASS 36 scenarios, including R1 release and automatic return/settle and
  hard-stop separation. Full Linux x86_64 candidate links successfully against
  the existing Unitree SDK/Torch build. No G1 file was changed, no binary deployed,
  no DDS publisher or motor command was run. Physical return and AI restoration
  remain unverified.

## 2026-09-10 Trial 4698 acceleration stop reproduced and hold trajectory fixed

- Exact packet log cycle_packets_20260910_094148_5444604.jsonl: native last ACK
  was tracking. First contract violations occurred at input sequence 1845 when
  four target velocities became exactly zero in one 1/60 s step. Joint25 changed
  -0.1019505 -> 0 rad/s, yielding 6.11703 rad/s^2 versus 1.04720 limit;
  joints22/26/27 also exceeded. This proves an abrupt PC target stop caused this
  trial's acceleration rejection, not measured G1 acceleration.
- Previous transient-idle fix correctly kept the native event active, but the PC
  controller still skipped trajectory.Track whenever command_active was false.
  It therefore froze configuration instantly during command-stream hold.
- Added live_tracking_active: validated control_state=hold now keeps the local IK
  trajectory running toward the held last hand target, so its existing QP
  acceleration-limited braking remains active. Idle before engagement remains
  inactive; explicit pinch/tracking loss still uses the return state machine.
- Added reusable offline analyze_cycle_packets.py and regressions for active,
  hold and idle classification. 13 bridge tests and cadence replay passed;
  recorded trial analysis deterministically reports sequence1845/joints22,25,26,27.
  No acceleration threshold, PD, native C++, G1 file/state or motor command changed.
- PC-only restart required. Physical hold transition and subsequent acceleration
  behavior remain unverified.

## 2026-09-10 Trial 4169 unexpected_tracking_event fixed on PC

- Packet log cycle_packets_20260910_093608_4827814.jsonl proves 1313 active
  packets were followed by idle at sequence 2574 while the last G1 ACK remained
  state=tracking. Native correctly rejected idle in Tracking as
  unexpected_tracking_event.
- Root cause was loss of the validated PC command-stream distinction: a transient
  Unity idle becomes control_state=hold (hold last safe target), but
  LiveCycleBridge mapped every right_arm.active=false packet to protocol idle.
- LiveCycleBridge now maps command_state=hold to an active event with the held
  joint target. Explicit pinch/tracking disengage still transitions the local
  return state and emits pinch/return as before; an actual idle before first
  engagement remains idle. Native C++ and all stop thresholds are unchanged.
- Added regression for active -> transient idle/hold -> active protocol events.
  Windows Python: 12 bridge tests passed; cadence replay also passed 60 live IK
  samples. No network, G1 execution, remote file change or physical validation.
- PC-only fix; restart candidate launcher to load it. Physical transient tracking
  loss, pinch return and re-engage remain to be checked.

## 2026-09-10 Omni Connect PC installation completed

- User confirmed prerequisite installation. SteamVR app250820 manifest StateFlags4,
  all download/staging bytes complete. Resumed signed Omni installer; user handled UAC.
- Bootstrap self-update logged MoveFile183 then extracted/launched new installer;
  final wizard explicitly reports installation complete. Registry shows Omni Connect
  1.2.93 at C:/Program Files/Virtuix/Omni Connect. Installed executable signature Valid.
- Launched OmniConnect.exe and visually verified Welcome / Get Started screen.
  Auto-launch on Windows startup and system tray were unchecked on finish page.
  Installer completion window may remain; automated Finish click did not close it.
- Account login, Bluetooth device pairing, Unity OmniConnect SDK and G1 lower-body
  integration not completed. No G1 action or existing Unity project change.
- Local status updated: references/omni/installation_status.json. Setup log:
  C:/Users/user/Downloads/OmniConnect_install_20260910.log.

## 2026-09-09 Omni PC installation requested (SteamVR prerequisite pending)

- User requested Virtuix Omni installation based on supplied ZIP, pausing arm
  acceleration investigation. Reference is Omni Connect + Unity OmniConnectSdk
  + Go2/WebRTC example, not NVIDIA Omniverse or a G1 lower-body policy package.
  Source markdown saved under references/omni/omni_go2_reference.md.
- Official https://virtuix.com/pc download link retrieved OmniConnectSetup.exe
  1.2.93.0 to Downloads. Authenticode Valid, Virtuix Inc. Hash/status recorded in
  references/omni/installation_status.json.
- Installer /VERYSILENT /SUPPRESSMSGBOXES /NORESTART attempted; custom prerequisite
  message requires SteamVR. Steam library has no app250820 manifest. Opened
  steam://install/250820 and asked user to click Install. Omni installation is NOT
  complete; installer message is pending. Log: Downloads/OmniConnect_install.log.
- No G1 mutation/run, no Unity project/package changes or Go2 sender installed.
  Document UDP5005 conflicts with existing G1 hand input; future Omni input needs
  separate routing into one robot command owner. Device pairing/login, Unity SDK
  availability and G1 lower-body integration remain separate, unfinished work.

## 2026-09-09 Trial 11396 acceleration stop: exact packet capture added

- User reports overhead reach then acceleration rejection at ~73 s. This is
  native input target finite-difference acceleration, not measured acceleration.
  Existing PC status has braking diagnostics but lacks exact rejected packet and
  correspondence to receiver sequence; cannot attribute this failure to braking,
  packet loss or numeric tolerance from current evidence.
- Relay optional --record now writes line-buffered send_attempt/ACK records with
  monotonic time and full payload except relay token. Candidate launcher supplies
  a unique logs/test_results/cycle_packets_<timestamp>.jsonl path. This records
  attempts, not proof of network delivery. Source session remains for replay.
- Existing 11 bridge tests passed; mock real file test verified exact payload,
  token omission and flush on interrupt. No motor/remote execution or G1 edits.
  No acceleration/PD/stop threshold changed. Root cause remains unresolved until
  failed stream is captured/replayed; future logs enable precise local analysis.
- User summary also reports max tracking error .239264 rad, near existing .25 rad
  stop; do not infer raising acceleration is appropriate from this failure.

## 2026-09-09 Trial 10833 joint_limit and PC/native range alignment

- User reported arm_tracking at 60 s then native joint_limit. Read-only copied
  existing CSV to logs/test_results/joint_limit_10833_policy.csv. Last accepted
  wrist-roll target 1.92125666 rad, close to native upper 1.922222 rad; exact
  rejected packet not logged, so joint26 is a likely culprit, not proven.
- Confirmed code mismatch: native uses joint hard range inset .05 rad; PC live
  model had only existing operational constraints (elbow 5..120 deg). Live-only
  model bounds now intersect existing ranges with native float32 constants inset
  .0501 rad (additional .0001 numerical reserve), before ConfigurationLimit and
  planner construction. Existing IK joint-bound braking uses these model bounds.
  No post-hoc target clamp, native guard relaxation or G1 changes.
- Added live_joint_bounds in g1_mink_speed_profiles.py and applied it in live
  controller. Unit check reads actual C++ constants, verifies all seven bounds;
  4 speed comparison tests passed. Physical boundary behavior remains unverified.
- No G1 rebuild required. Restart PC Input via candidate launcher for new bounds.
  Tracking did run in this trial; pinch return/re-engage success is not established.

## 2026-09-09 Wrist-roll readiness margin and initial WAIT diagnostics DEPLOYED

- User explicitly requested slightly looser readiness conditions and application.
  Wrist roll tolerance (both arms initial; right arm return) .020 -> .025 rad.
  Other joint tolerances, .05 rad/s measured speed, .5 s dwell, all physical
  runtime tracking/torque/timeout/remote-control stops remain unchanged.
- Initializing ACK includes ready_blockers with joint, angle error, tolerance,
  speed and speed limit, plus initial_target_complete. PC displays these at most
  once per second. This detailed blocker list currently covers initialization;
  returning still uses existing RETURNING state display.
- Tests: initialization with recorded .020062 wrist offset and blocker ACK passed;
  34 contract scenarios and 11 Python bridge tests passed. Mock PC display verified
  joint26, limit .025 and rate limiting. No physical test executed by agent.
- Backed up headers and executable in candidate/backup_wrist_ready_20260909.
  Transferred only two headers; remote hashes match PC:
  cc0c6e68f5938f870ef0d57e469a6beb251bce439306a43655e784e8afd21446 (contract),
  da291622745d80a9a2db7c9f579dffffe05d82231ae7bb1f1a8ee16fb3965575 (target).
  G1 ARM cmake target build exited 0. Evidence: mink_cycle_wrist_ready_g1_build.log
  and mink_cycle_wrist_ready_g1_hashes.txt under logs/test_results.
- Same candidate launcher; restart PC Input to load WAIT diagnostics. Wait actual
  G1 ROBOT READY before engage. Physical initialization/return retry pending.

## 2026-09-09 Trial 9593 readiness blocker identified

- Read-only copy of existing remote trial 1787641324638467_9593/policy.csv to
  logs/test_results/ready_wait_9593_policy.csv; summary in ready_wait_9593_summary.json.
- Last 5 s (251 policy samples): right wrist roll joint26 positional error
  0.020013656..0.020061594 rad, exceeding unchanged 0.020000 rad ready tolerance
  in every sample. All other arm joints passed their adjusted positional limits;
  all arm speed maxima below 0.05 rad/s in these samples. This single wrist
  threshold explains the observed arm_initializing wait at sampled times.
- Not proof of a visibly moving arm: initial-ready rejection is based on a tiny
  excess over the position acceptance boundary (up to 0.0000616 rad / 0.00353 deg).
  Display was reporting actual controller state. Higher-rate samples are not all
  captured by this 50 Hz CSV, but persistent joint26 error is sufficient to block.
- No code, thresholds, PD or G1 state changed. Next candidate: narrowly add wrist
  roll readiness margin and expose blocking joint/error/limit in native ACK so
  another readiness stall can be diagnosed immediately on PC, before any trial.

## 2026-09-09 Live sample cadence fix after acceleration stop (trial 9241)

- User reached udp_ready then native acceleration rejection. This contract checks
  differences of input target velocities, not measured physical acceleration.
- Found a PC timing defect: IK advances fixed DT every loop, but live send shared
  the wall-clock next_state display gate. A short wall interval can skip sending
  an IK step while bridge sample_time still increments by only one DT per send.
  Collapsed motion is then interpreted as excess acceleration by the contract.
- Changed live controller gate to `if live_cycle or now >= next_state` so each live
  IK iteration emits a sample. Other modes retain their prior timer. No threshold,
  PD, G1 source/binary, stop control or commanded speed/acceleration cap changed.
- New test_live_cycle_cadence.py uses real bridge packets and the compiled C++
  contract sink with jittered wall times: old gate reproduced acceleration stop;
  fixed gate accepted all 60 samples. Existing 11 bridge tests also passed.
  No network/robot execution in these tests. No G1 rebuild needed.
- The exact rejected live packet was not recorded, so this is a reproduced code
  defect consistent with the symptom, not proof it was the sole cause of trial
  9241. Live retry remains pending. Restart Input to load the changed loop.

## 2026-09-09 input_timeout after Unity startup, trial 8935

- User supplied native reason input_timeout, policy_steps 435. Current PC Input
  and Relay processes remain running. Runtime snapshot at 17:08:11: 162 received,
  idle, source age 49.078 s; at 17:08:13 same 162, age 51.578 s. Thus Unity input
  had stopped advancing by observation time; this snapshot alone does not locate
  the exact first gap during the trial or establish why Unity stopped sending.
- Contract input watchdog begins after the first valid packet, including idle,
  not after engage. Relay drops stale pre-active idle without making it fresh;
  native therefore stops after 0.25 s without valid input. READY initialization
  must have instantiated the contract before this particular reason can occur.
- Unity sender is Update-driven and uses Time.deltaTime. runInBackground is already
  enabled. Multiple Unity projects are running; shared Editor.log contains DeadAir
  errors and must not be attributed to G1. No Unity code/settings or timeout changed.
- Next operator sequence: start G1 Unity Play and establish continuous input before
  Robot P, then wait measured READY before engage. Still missing: whether Unity
  Play paused/stopped or another startup interruption caused the original gap.

## 2026-09-09 Readiness adjustment DEPLOYED after explicit approval

- User approved the proposed two-header backup/transfer/build via "진행".
  Backed up old headers and binary under candidate/backup_readiness_20260909;
  transferred only mink_live_cycle_contract.hpp and mink_live_cycle_target.hpp.
  Remote hashes match local 551e9b5fc1d1f832acb2ae5b1e2e4879f2161341e32020d0538c74b8206a0e82
  and 954ad7452e8dd9fdf370ae9489f96cca611b86191db8c38280c4d87646b0070d.
- cmake --build build --target g1_twist2_mink_cycle_trial -j 1 exited 0 on G1.
  ARM aarch64 executable SHA256 d0291ccc653bd08d35a54f45b31402a5cf99acb54b6d1a9580c1f377a7c2c161.
  Backup old binary remains 5e50fba17d2deaa98b4959d178e4decb9cc7794c97694a7daabce1fb34614ee4;
  yesterday original remains 87191a1e4ecc940997b9983b8e3893cdfebdf75eae05e5dcda5e52695be5ff39.
- Build warnings include existing SDK/Torch and unused keyboard helper warnings.
  Evidence: logs/test_results/mink_cycle_ready_g1_build.log and
  mink_cycle_ready_g1_hashes.txt. No motor executable run, DDS publisher created,
  mode/service change or package install by agent.
- Same START_TWIST2_MINK_CYCLE_CANDIDATE.bat now selects rebuilt candidate.
  User must observe [G1 ROBOT] READY before engage. First measured-ready and
  pinch return/re-engage physical trial after this change remain unverified.
  Supersedes the pending deployment statement below.

## 2026-09-09 Readiness offset candidate prepared locally (NOT deployed)

- User agreed to adjust initial/return readiness after trial 7966 diagnosis.
- Shared measured readiness helper in mink_live_cycle_contract.hpp: shoulder roll
  0.09 rad, elbow 0.04 rad, all other arm joints unchanged 0.02 rad. Both-arm
  initialization in mink_live_cycle_target.hpp uses the same local joint limits;
  return/re-engage uses them for the right arm. Speed <=0.05 rad/s, 0.5 s dwell,
  feedback freshness and exact commanded-home/zero-command-velocity remain.
- These are candidate acceptance margins above this trial's observed offsets,
  not certified safe limits. Runtime 0.25 rad upper tracking stop, PD, trajectory
  speeds/acceleration, R1 and communication stops are unchanged.
- MSVC /W4 /WX: initialization test with measured shoulder/elbow offsets passed;
  contract 34 offline scenarios passed, including tolerance boundaries, excess
  speed/error rejection, return dwell, offset return/re-engage and prior stops.
  Initial test expectation counted the pinch sample incorrectly; corrected the
  test to account for its existing contribution to dwell, no dwell code change.
- Pending exact remote approval: copy only these two candidate headers to
  /home/unitree/g1_mink_cycle_compare_20260909 (retain backups), then compile its
  g1_twist2_mink_cycle_trial target. Do not execute robot program. Existing G1
  binary still has old .02 rad readiness and will exhibit the original wait.

## 2026-09-09 Measured-ready wait diagnosed from G1 existing CSV

- Read-only SSH listing and remote-to-PC copy of existing trial
  g1_twist2_trial_1787640564571638_7966/policy.csv; no remote mutation or execution
  of robot programs. Local ready_wait_7966_policy.csv and summary.json under logs/test_results.
- 1865 policy samples, 37.300 s, phases capture/blend/arm_initializing only.
  Last 5 s: joint16 error 0.06911..0.06919 rad, joint23 0.07676..0.07678,
  joint18 0.02649..0.02654, joint25 0.02669..0.02673. These four failed the
  0.02 rad initial-ready tolerance at every logged sample. All arm measured
  speed maxima were below 0.05 rad/s in that window. Thus sustained positional
  offsets, not continued large arm motion, blocked the sampled ready condition.
- User stopped waiting; subsequent no-fresh-feedback is consistent with stopped
  ACK transmission. Logs do not establish physical cause of the offsets.
- No thresholds or PD changed. Next work must distinguish ready acceptance from
  runtime tracking protection and cover both initial ready and return/re-engage;
  .02 rad return checks may encounter the same offsets. Snapshot analysis does
  not validate a replacement tolerance or physical safety.

## 2026-09-09 PC display of actual G1 readiness

- LiveCycleBridge now prints [G1 ROBOT] WAIT / READY / TRACKING / RETURNING /
  STOPPED from validated G1 ACK states, only on state changes. No feedback or
  feedback older than 0.25 s displays WAIT, including before initial engagement.
- READY means fresh native waiting (udp_ready), not the PC model return state.
  Existing local cycle print is explicitly labeled PC LOCAL (not G1 readiness).
- Existing 11 transport tests passed; mock display check passed WAIT -> initializing
  -> READY -> stale WAIT and duplicate suppression. No G1 run or rebuild.
- Display only: early engage still triggers native engage_before_measured_ready.
  Wait for [G1 ROBOT] READY before engagement. Actual live display not yet observed.

## 2026-09-09 Relay age/clearance rejection diagnosis

- User supplied Relay ValueError age/clearance. This combined message cannot
  establish which field failed. Split errors into source_age_s, sample_time_s,
  clearance_m with actual numeric values and limits.
- Before any active packet is forwarded, stale idle packets are dropped with
  a rate-limited WAIT INPUT message, allowing startup to wait for fresh input.
  No stale packet is forwarded. Once active has been forwarded, age failures
  still terminate Relay. Collision, provenance and other validation failures
  retain existing rejection behavior; no threshold or native stop logic changed.
- Windows tests: 11 passed, including stale idle -> fresh idle -> active,
  post-active stale rejection, distinct error reasons and prior UDP regressions.
  PC-only change, no G1 execution or rebuild. Actual failing field and live retry
  remain to be confirmed from the new diagnostic output.

## 2026-09-09 Windows UDP WinError 10054 handling

- User reported Input feedback recvfrom failed with ConnectionResetError 10054.
  This is consistent with a Windows UDP ICMP port-unreachable notification
  (for example Relay not yet listening); the exact unavailable peer was not established.
- PC LiveCycleBridge and both Relay receive loops now consume only Windows
  error 10054 and continue their bounded polling. Other socket errors still raise.
  No ACK is synthesized or refreshed; the existing 0.25 s active feedback timeout,
  token/profile validation, native timeout and stop controls remain unchanged.
- test_mink_live_cycle_bridge.py: 9 tests passed on Windows Python 3.11,
  including reset-before-ACK, timeout despite reset, unrelated error propagation,
  both relay sockets and loopback UDP roundtrip. No robot communication or execution.
- No G1 rebuild required. End-to-end retry remains pending; if a feedback timeout
  follows, inspect Relay/Robot output rather than extending the timeout.

## 2026-09-09 Windows cycle Relay startup WinError 10022 fixed

- User reported outbound.recvfrom before the first input crashed with WinError 10022.
  The UDP feedback socket was unbound until sendto. Added explicit wildcard bind
  to an OS-assigned ephemeral port before nonblocking receive; preserves G1 reply
  routing and existing feedback source/token/profile checks. Setup failures close sockets.
- Changed hardware/g1_arm_bridge/gate7_mink_cycle_relay.py and added a regression
  in experiments/twist2_right_arm_manual/test_mink_live_cycle_bridge.py.
- Windows Python 3.11: all 7 tests passed, including empty receive before first
  send and real loopback UDP request/reply using ephemeral ports only.
  No G1 connection, DDS publisher, physical execution or remote file changes.
- PC-only fix; no G1 rebuild needed. Stop any current physical trial using its
  existing stop controls before restarting the candidate launcher with a fresh
  shared token. Actual end-to-end VR/G1 operation after this fix remains unverified.

## 2026-09-09 G1 cycle candidate DEPLOYED after exact transfer/build approval

- User approved source transfer and ARM compilation to the named new directory.
  Created /home/unitree/g1_mink_cycle_compare_20260909 only; transferred verified
  bundle SHA256 2539d2cc2f223f02e774a980320cd21ca33c54a24823f3cfe938b2d487ec75d7.
  New-folder extraction only; tar -m avoided future source timestamps because G1
  wall clock differs from PC. No system clock change or package installation.
- Configured using existing SDK /home/unitree/unitree_sdk2-main, existing Torch
  /home/unitree/.local/lib/python3.8/site-packages/torch, ABI1. GNU9.4.0 ARM build
  of g1_twist2_mink_cycle_trial completed exit0, -j1. No executable run.
- ARM binary SHA256 5e50fba17d2deaa98b4959d178e4decb9cc7794c97694a7daabce1fb34614ee4.
  Preserved old binary SHA256 87191a1e4ecc940997b9983b8e3893cdfebdf75eae05e5dcda5e52695be5ff39
  unchanged. No existing G1 source/binary/service/mode modified.
- User entry: .\tools\START_TWIST2_MINK_CYCLE_CANDIDATE.bat
  Menu1 yesterday limits; menu2 today limits; both current v5 IK. All opens Input,
  Relay, Camera, Robot with same token/profile. Close prior Input/Relay first.
  Robot requires user's SSH login, manual P and held R1; wait for udp_ready before
  engage. Pinch -> checked return -> measured ready ACK -> idle/new engage.
  R1/Select/B/p/errors still damping; AI is not automatically restored.
- Logs: logs/test_results/mink_cycle_g1_build.log, mink_cycle_g1_deployment.json.
  Earlier pending-deployment section is superseded. Actual coupled Quest/network/
  G1 cycle has NOT been run or validated. Do not claim physical safety from build.


## 2026-09-09 existing-path live cycle candidate: code connected, G1 deployment pending

- User explicitly prioritized actual VR->G1 over further unrelated simulation
  studies. Prepared separate candidate based on preserved twist2_mink_udp_trial.cpp:
  twist2_mink_cycle_trial.cpp. Existing lower policy, AI handoff, writer, PD gains,
  torque/joint protections and R1/Select/B/p damping retained. No physical run.
- PC --live-cycle-candidate uses today's v5 IK, checked return trajectory and
  explicit yesterday/today profile. It is mutually exclusive with simulation mode.
  Simulation-only provenance remains blocked. The old launcher is unchanged.
- New live schema g1.mink.cycle.live.v1 is carried by gate7_mink_cycle_relay.py
  over existing localhost5008 -> G1:5014. Reply goes via relay to localhost5015.
  Exact profile, per-run nonce, source IP, session/sequence, epoch, finite values,
  source age and PC clearance checked. Nonce is NOT cryptographic authentication.
  Planned sample time controls speed/acceleration validation; physical writer still
  has target-rate and torque clamps, not a certified acceleration bound.
- MinkLiveCycleContract: pinch/tracking release -> returning; only return samples
  while returning. Requires target at home plus measured right q within.02rad and
  dq within.05rad/s for.5s before waiting ACK. Return30s timeout; source.25s,
  feedback.05s. Duplicate/stale/mismatched/invalid samples latch stop. Fresh idle
  then active required after ACK. PC ignores hand engage during return; packet-level
  early active is a protocol error, not silently accepted. Missing ACK stops PC
  after.25s once active, so G1's source watchdog stops continued motion.
- Initial ready similarly requires both arms measured settled; original .08rad/s
  initializer retained. Runtime feedback is refreshed from actual LowState in the
  writer watchdog. ACK session/epoch/profile/freshness gates PC re-engagement.
  Existing full-body mode remains TWIST2 policy legs + held waist/left + right IK,
  including during return/wait. No automatic AI restoration.
- Profiles: yesterday all.7rad/s,10deg/s^2; today proximal90/wrist180deg/s,
  60deg/s^2. Source rate/acceleration checked per profile. Candidate writer's right
  rate cap follows profile (old upper writer cap.8rad/s would clip today).
  Measured right velocity stop is selected cap+.8rad/s: yesterday1.5; today
  proximal2.3708/wrist3.9416rad/s. This guard change is candidate-only, not a
  hardware-validated envelope. Existing .25rad upper tracking-error stop retained.
- Geometry is still checked in PC Mink model; native wrapper does NOT implement a
  new measured full-body collision engine. Do not describe its permissive callback
  or reported PC clearance as physical collision-safety validation.
- Local checks:26 C++ protocol scenarios; measured-init/ACK/stale-feedback wrapper;
  6 Python bridge/relay/ACK checks;23 existing handshake/tracking/provenance tests;
  3 profile tests; actual PC emitter -> relay validation -> C++ pipe replay269
  packets for EACH profile, measured lag blocks ACK, reengage completes.
  All passed. Linux x86_64 candidate compiled against existing WSL SDK/Torch;
  executable NOT run. Native build has inherited SDK/Torch warnings.
- New launcher tools/START_TWIST2_MINK_CYCLE_CANDIDATE.bat menu selects both profiles;
  corresponding ps1 All passes same profile/token to Input/Relay/Robot/Camera.
  Preview verified without process launch. Selected profile also recorded in PC
  status/diagnostic filenames and native run manifest. Close old Input/Relay before
  switching; ports5005/5008/5015 cannot be shared. No processes were terminated.
- Read-only SSH succeeded at192.168.123.164 (aarch64), host key pinned to existing
  known_hosts SHA256:b49bi+OYx/3BYWPsTlMZF1psSs5FW8FnpmFfHpfoDrk. Preserved remote
  source hash1e1bfc21daec1a3b646860a993c0183ac046eee6bba59a515d36d9db2dde0ab5
  and common.hpp hash2db4dea94bf469429010563bee36f1cab8005d688c87a2eb8772aca1f51dbba6
  match local baseline. Old binary hash87191a1e4ecc940997b9983b8e3893cdfebdf75eae05e5dcda5e52695be5ff39.
- Transfer-ready bundle logs/deployment/mink_cycle_compare_20260909.tar.gz (23
  source/build files plus manifest), SHA256
  2539d2cc2f223f02e774a980320cd21ca33c54a24823f3cfe938b2d487ec75d7.
  Intended NEW destination /home/unitree/g1_mink_cycle_compare_20260909; preserve
  /home/unitree/g1_vr_07_10deg_trial_20260908 entirely. Source transfer/ARM compile
  not yet performed; exact remote mutation approval rule at top still applies.
  Remote known dependencies: SDK /home/unitree/unitree_sdk2-main; Torch
  /home/unitree/.local/lib/python3.8/site-packages/torch; ABI1.
- Next action is new-directory source transfer and cmake configure/build of
  g1_twist2_mink_cycle_trial using existing dependencies only. No motor executable,
  service/mode change or automatic P/R1 input during deployment. Then user runs
  new launcher; real network/VR/G1 behavior remains unverified. Do not return to
  unrelated floating-base studies before completing this deployment.


## 2026-09-09 same-IK speed comparison presets (simulation ready; G1 integration pending)

- User prioritizes using today's IK on G1 and comparing yesterday/today speed.
  Current upstream v5 is explicitly simulation-arm-cycle only. Do NOT claim new
  comparison launcher is G1 capable or redirect simulation-marked packets to relay.
  Actual PC->legacy G1 integration remains unfinished; next priority is that
  integration, not more unrelated floating-base simulation refinement.
- Added g1_mink_speed_profiles.py: yesterday = seven joints0.7rad/s,
  acceleration10deg/s^2; today = shoulder/elbow90deg/s, wrist180deg/s,
  acceleration60deg/s^2. This compares velocity AND acceleration as a preset,
  not isolated velocity effects. Same v5 IK, geometry, PD (not simulated here),
  ready pose, return behavior and jerk setting; only speed/acceleration differ.
  'Yesterday' means yesterday's limits on today's IK, not full old-software replay.
- Controller --speed-profile yesterday|today configures QP velocity limits,
  tracking acceleration, return limiter and report values together. Default
  simulation remains today. Explicit profile without simulation-arm-cycle rejects.
  Diagnostics filenames include profile; status records speed_comparison_profile.
- Added tools/START_MINK_SPEED_COMPARISON.bat menu 1=yesterday,2=today.
  Also accepts yesterday/today argument. Existing simulation launcher accepts same
  argument (no argument=today). Same isolated MuJoCo3.12.0, no Relay/Robot,
  candidate UDP5008 stays disabled. Stop current Input before switching (UDP5005).
  Commands:
  .\tools\START_MINK_SPEED_COMPARISON.bat yesterday
  .\tools\START_MINK_SPEED_COMPARISON.bat today
- Existing upstream tracking regression:8 tests passed under MuJoCo3.12.0.
- test_mink_speed_comparison.py:3 tests passed. Exact unit conversions, invalid
  profile rejection, same8cm wrist target through actual v5 IK for180 ticks each;
  both velocity/acceleration bounds and other joints held checked. Report:
  logs/test_results/mink_speed_comparison.json. Caps need not be reached on this
  short target; no hardware tracking/safety conclusion.
- Existing START_TWIST2_MINK_UDP and legacy physical C++ unchanged. They still
  use yesterday's limits and older IK path. Today's new cycle/IK/limits have NOT
  been deployed to G1. Need concrete reviewed local hardware candidate, compatible
  receiver rate/stop behavior, then explicit exact remote deployment approval.
  No G1 connection, file mutation, WSL, publisher or control execution this turn.


## 2026-09-09 stance/contact isolation: baseline is not balanced

- Added diagnose_mujoco_stance_offline.py. Five controlled local dynamics cases,
  same current PD/torque caps and attitude0.2rad / speed4rad/s stop criteria.
  No changes to production/physical C++, model XML, gains or active IK.
- Found initial foot-floor gap13.825516mm at root .793m. First contact54ms.
  Diagnostic-only root translation brings foot geometry to ground (residual<1e-8m),
  contact2ms. This is geometric alignment, NOT a settled measured initialization.
- Constant ready-joint PD WITHOUT any policy: original root stops1.378s on attitude;
  grounded root stops1.416s, peak joint speed drops2.8365 ->0.9230rad/s.
  Policy-default arm pose grounded also stops1.140s. Constant PD does not establish
  a balanced stance in this model; cannot attribute tilt solely to VR/policy.
- Grounded ready case at1.3s: COM x0.11696m vs foot contact x range
  [-0.04358,0.12642]m, pitch0.13475rad; bilateral normal loads168.23/167.92N.
  COM moves toward front of feet. Contact range is diagnostic, not a stability
  guarantee or a support-polygon/ZMP acceptance test.
- Replaying prior policy command trace (OPEN LOOP, no new inference) reproduces
  prior1.442s stop; grounded variant stops1.506s. Last recorded command is held
  after trace ends. Ground alignment alone does not resolve baseline imbalance.
- Five executable checks pass: initial gap, alignment residual, earlier grounded
  contact, no-policy attitude failure, prior-policy stop reproduction within10ms.
  Report logs/test_results/mink_stance_diagnosis.json includes all pose/contact
  rows, input hash and checks. Run:
  py -3.11 -B experiments/twist2_right_arm_manual/diagnose_mujoco_stance_offline.py
  Exit0 means diagnostic assertions reproduced, NOT a successful standing trial.
- Next: establish a separately validated balancing/startup reference or match the
  original TWIST2 simulation observation/action/startup configuration. Do not tune
  arm PD or relax tilt limits to compensate for this unvalidated standing fixture.
  Full-body dynamics/collision approval and hardware validation remain incomplete.
- No G1/SSH/WSL/DDS, publisher, robot command, service/mode change or deployment.
  Existing user changes preserved. Startup Recovery strategy atlas still deferred.


## 2026-09-09 MuJoCo dynamics feedback to CPU policy/C++ owner: connected, rollout stopped

- Added mujoco_feedback_offline.py local JSONL subprocess using existing Unitree
  scene_29dof.xml (floating pelvis, gravity, floor, pelvis IMU), MuJoCo3.12.0.
  Resolves 29 joint/actuator indices by name. Torque = kp*(qcmd-q)-kd*dq,
  desired dq zero; clamps against BOTH current common.hpp torque limits and XML
  motor ctrlrange. Reads current kp/kd; no gain edits. Integration <=1 ms,
  observations at owner ticks and intervening60 Hz input timestamps.
- Extended mink_torch_owner_stdio_offline.cpp with optional dynamics callbacks:
  measured q/dq/quaternion/gyro/acc/rpy -> native2092 CRC fixture -> existing
  owner/history. Commands remain separate from measurements; history commits
  accepted command (not actual q). Feedback represents simulation only; R1/mode,
  motor torque/temperature/fault fields are synthetic, not measured hardware.
- Runner --dynamics implies combined moving-arm pose fixture. Each policy request
  asserts Python measured state matches C++ observation gyro/rpy/q/dq (including
  zero ankle velocity observations). Existing event/ACK coverage not extended.
- Immediate unblended policy step first hit velocity_limit at0.008s (4.244rad/s).
  Added explicit FOUR-second smoothstep leg blend in this dynamics fixture only,
  preserving limits. This approximates reference transition, not physical AI
  takeover/startup: XML root .793m, ready joints, zero velocity, no settled seed.
- Final rollout:72 accepted actual inferences; last completed response712 outputs.
  Dynamics progressed to1.442s /1500 substeps, then owner attitude_limit:
  pitch0.2008647rad, roll-0.0034239rad, root height0.7623842m.
  Max measured joint speed2.8317359rad/s, max applied torque18.5293Nm;
  no torque clipping. Full intended488-inference run NOT completed.
  Additional ticks after last completed response are in dynamics rows, not runner
  trace. Geometry callback remains permissive; this is NOT full collision approval.
- Tests:5 adapter cases passed (named joints, pelvis quaternion/gyro frame,
  torque response without instant q assignment, malformed input and time rejection).
  Static regression50 inferences/492 outputs and MSVC /W4 /WX build passed.
  CPU observation mapping checks passed through stop; real IMU calibration and
  model parameters remain unvalidated. No PD tuning conclusion from this run.
- Reproduce: .\tools\TEST_MINK_TORCH_OWNER_OFFLINE.bat dynamics
  Current expected exit1: attitude_limit. Reports:
  logs/test_results/mink_torch_dynamics_replay.json and mink_mujoco_feedback.json
  (state history, gains/XML hashes, joint order, torque caps).
- Next: validate settled initial stance, ground contact and policy transition
  against known-good reference behavior before a longer dynamics/full-body audit.
  Do not relax attitude/speed checks to label this rollout successful. Real-time
  deadlines, transport/ACK, runtime geometry and physical damping remain pending.
- No G1/SSH/WSL/DDS, physical output, remote change or controller run. Existing
  physical control C++/Robot launcher and prior user changes preserved.


## 2026-09-09 moving v5 arm + actual policy geometry audit: FAILED offline

- Extended mink_torch_owner_stdio_offline.cpp / replay_mink_torch_owner.py with
  optional combined fixture. Reuses v5 generated arm pose samples, policy default
  legs and Mink ready upper body. Observation mimic follows incoming arm target.
  Continuous active pose replay only: return/re-engage event/ACK protocol is NOT
  exercised by this combined fixture (covered separately in previous tests).
- Actual CPU TorchScript: 488 inferences, 488 history commits, 4,872 logical
  500 Hz outputs; latest max computation 0.8519 ms, none over20 ms. Static mode
  regression: 50 inferences /492 outputs. MSVC /W4 /WX build passed.
- Added audit_mink_torch_combined_geometry.py, pinned MuJoCo3.12.0. Expands to606
  robot self-collision pairs using existing structural/exemption rules, checks
  all29 joint ranges and held waist/left arm, samples each segment at four points.
  Post-generation audit, NOT a runtime geometry gate; generation callback remains
  explicitly permissive. Ground contact, balance, dynamics and real timing absent.
- Audit FAILED at index101 /0.202 s, left knee vs right knee, clearance
  -0.074506815 m. 101 prior segments checked; remaining trace unvalidated.
  Raw geometry distance and four actual model contact distances agree. Perturbing
  shoulder-independent left hip pitch by +/-1e-8 and +/-1e-6 rad reproduces it.
  This is a reproducible geometric overlap in this synthetic pose, NOT evidence
  that real G1 has this collision. Fixture assumes immediate command tracking,
  zero dq/gyro and fixed root; it cannot establish closed-loop policy behavior.
- Reports: logs/test_results/mink_torch_combined_replay.json and
  mink_torch_combined_geometry.json (input hashes, failure pose/pair/contact).
  Reproduce: .\tools\TEST_MINK_TORCH_OWNER_OFFLINE.bat combined
  Expected current result: exit1 at collision audit. Default invocation retains
  the static inference test. No threshold/exemption was relaxed to obtain a pass.
- Next necessary work: replace ideal synthetic feedback with validated MuJoCo
  dynamics observations (joint order, root/IMU frame, gains, history/action mapping)
  before interpreting full-body policy behavior. Full combined geometry validation
  remains incomplete. Asynchronous deadlines and transport/damping also pending.
- No G1/SSH/WSL/DDS, publisher, physical output, remote change or controller run.
  Existing physical control C++ and robot launchers preserved; no deployment.


## 2026-09-09 actual CPU TorchScript -> new owner integration (offline)

- Reused existing logs/diagnostics/twist2_cpu_venv (Torch 2.14.0+cpu); default
  Python lacks Torch. No new package install or global runtime change performed.
  ReadVerifiedPolicy verifies SHA256 463be0376c2c1f551b996d0bf9ab97833854f2cc098b9d4fea735f17ec2e9015
  and loads those same bytes into torch.jit.load on CPU, one thread, ten warmups.
- Added mink_torch_owner_stdio_offline.cpp and replay_mink_torch_owner.py.
  Existing OfflineObservationHistory builds 1432-D input from captured synthetic
  native state and prior accepted command; actual model returns [1,29] float32.
  Validated/clipped action -> default + .5*action -> soft joint-range clamp for
  legs only, matching existing guarded composition. Arms/waist remain held.
- New owner's request-bound SubmitPolicy/ComposeHeldPolicy path accepted 50 real
  inferences, 50 observation-history commits, 492 logical output ticks. Measured
  compute maximum 5.4338 ms, no samples over20 ms in this run. Report:
  logs/test_results/mink_torch_owner_replay.json (per-request timings and q).
- Inference/tensor/output computation duration is rounded UP to a 2 ms synthetic
  completion slot; owner advances logical 500 Hz outputs with old policy while
  waiting. Initial inference precedes logical output epoch. This is NOT a real
  asynchronous worker/deadline or IPC timing validation.
- Fixture feedback follows previous command ideally with zero dq and default
  policy arm pose. Geometry callback is explicitly permissive / geometry_checked
  false. No MuJoCo dynamics, real LowState, v5 moving arm or physical safety claim.
- MSVC /W4 /WX build passed. Injected 28-value output rejects with action shape;
  delayed completion rejects with policy_expired. Existing core files unchanged.
- Reproduction: tools/TEST_MINK_TORCH_OWNER_OFFLINE.bat (new local-only batch).
  Existing Torch warns NumPy is absent and JIT API deprecated; no NumPy operations
  are used here and shape/finite/result checks passed. No SDK/publisher, G1/SSH,
  WSL, service change, controller window or physical output was run.
- Remaining: real asynchronous scheduling / wall-clock deadlines, measured ready
  transition and feedback binding, v5 moving-arm + full-body geometry combined
  replay, authenticated event/ack transport and actual damping/stop integration.

## 2026-09-09 50 Hz policy / 500 Hz owner handoff (offline)

- User requested next step after visually confirming v5 orientation recovery.
  Existing v5 IK behavior unchanged. Added policy request/result cache interface
  to MinkCycleOwnerOffline; no actual policy worker, SDK, socket or robot run.
- BeginPolicy captures immutable decoded LowState copy + request ID. SubmitPolicy
  binds result to that request/input sequence even when newer LowState arrived
  during inference. Only one pending request; duplicate/stale/mismatched result
  fails closed. Existing direct Compose contract remains available unchanged.
- ComposeHeldPolicy reuses validated leg positions for min(policy_age,25 ms),
  measured from original INPUT state receipt, not completion or output time.
  Every 500 Hz call still validates fresh state/R1 and full-body geometry before
  merging resampled right arm. Failure clears reference and policy cache.
  Reference records current state sequence AND policy input sequence/created time.
- New test_mink_policy_hold_offline.cpp: 11 scenarios pass, including 201 logical
  output ticks / 21 policy requests at 50 Hz, delayed completion, strict expiry,
  wrong result, and changed safety conditions while reusing a policy.
  Fixture policy_age=.025; existing narrower configured budgets unchanged.
- TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat includes new build/test (/W4 /WX).
  Full checks: 79 C++ scenarios, 8 Python tracking tests, 579 source samples with
  return/re-engage, and 4,909 MuJoCo 3.12 output geometry segments.
- Single-thread owner interface only: future inference thread must communicate
  through serialized bounded handoff. Real Torch inference/action conversion,
  initial ready transition, network/epoch-ack and physical damping remain pending.
  No G1/SSH/WSL/DDS or controller window started; no physical files changed.
  Actual deadline timing has not been measured by synthetic logical-clock tests.

## 2026-09-09 user confirmed v5 wrist-orientation recovery visually

- After the 15:25:56 log review, user explicitly confirmed that moving the hand
  back restored the robot/model wrist orientation to the intended target.
- This is user visual confirmation of the simulation v5 orientation-recovery
  behavior, alongside the logged two completed return/re-engage cycles.
  It does not quantify residual error or validate actual G1 motor tracking.
- Final input_timeout remains as recorded; user did not state its cause.
  No further controller, parameter, or robot changes made for this confirmation.

## 2026-09-09 user v5 test completion / log review 15:25:56

- User reported test completed; no explicit visual success report yet. Saved
  current status to mink_v5_user_trial_20260909_152556.json before overwrite.
- Runtime marker confirms v5. Received 2,420 packets, zero rejected packets.
  15:25:16 tracking_disengaged -> return -> await_active 15:25:20 -> active 15:25:21.
  Another tracking release -> return -> active 15:25:23. No arm_cycle_rejection.
  Final tracking release at 15:25:50 ends in input_timeout fault at 15:25:53;
  no logged final return acknowledgement. Do not assume intentional app closure.
- One saved braking snapshot, valid probe clearance 9.635 mm, no joint violation.
  Final scale=1 and priority=false are inactive/post-return state; near-zero final
  pose error cannot prove active-hand orientation recovery. Current diagnostic
  file does not preserve a priority/rotation time series. Visual confirmation
  of hand-back orientation recovery still needed; no blanket success claim.
- No controller, physical G1 or configuration change performed during review.

## 2026-09-09 position priority with original-orientation recovery (simulation v5)

- User explicitly chose position priority in difficult regions but requested
  original wrist orientation recovery when the hand comes back. Implemented in
  g1_upstream_mink_tracking.py; original clutch-relative SE3 target is retained.
  No target rebasing, orientation reset-to-current, physical C++/PD/limit change.
- Activate after >80 mm wrist-position error AND clearance <12 mm or any right
  joint margin <5 deg persist for 0.3 s. Orientation cost scale ramps 1 -> .25
  at 1/s (normal cost 2 -> .5); position objective remains unchanged.
  Recover after error <30 mm OR clearance >25 mm AND all joint margins >8 deg
  persist 0.3 s; scale ramps back to 1. This is a local scheduling heuristic,
  not an infeasibility certificate. Neither stage guarantees reaching every goal.
- Reset and BeginReturn restore scale=1 and clear dwell/priority state. Pinch
  return uses the existing checked Ruckig path and then normal re-engage mapping.
  Existing speed/acceleration caps, exact segment geometry and frozen DOFs remain.
- Runtime marker now mink_position_priority_recovery_v5. Status reports
  position_priority_active and orientation_priority_scale. Restart simulation
  Input to load it; no controller window or G1/SSH/WSL/DDS output was run here.
- Replayed both recorded difficult goals for 600 ticks (10 s), then their original
  reachable wrist SE3 for 900 ticks (15 s). Difficult-region residuals:
  52.84/59.36 mm, orientation 34.24/44.74 deg, scale .25. After returning:
  1.960/2.041 mm, orientation .07392/.07335 deg, scale 1. No holds; clearance
  >=5.3748 mm, observed acceleration <=60 deg/s^2 (roundoff tolerance).
  Report: mink_orientation_priority_recovery_20260909.json. These are held-goal
  model replays, not instantaneous recovery timing or physical tracking evidence.
- Added two regression tests and the two-pose fixture. All 8 upstream tracking
  tests pass in isolated MuJoCo 3.12.0, including prior no-overshoot, boundary
  elbow lift, braking, return seeding and exact rejection tests. Existing 579
  source-sample return/re-engage replay and 4,909 output geometry segments pass.
- Fixed-cost diagnosis script explicitly disables adaptive weighting and sets
  its baseline cost so previous orientation-cost comparisons remain meaningful.
- Remaining: user VR visual validation of position-priority / restored direction;
  unreachable goals may still leave position error. Actual G1 route unchanged.

## 2026-09-09 recorded wrist mismatch: no live IK change promoted

- User agreed to investigate/fix whole-arm reconfiguration. Replayed both latest
  saved poses in isolated MuJoCo 3.12.0. The previous statement that elbow
  repositioning alone would solve the mismatch was too strong: no tested change
  improved both objectives enough to justify promotion. Active controller, gains,
  joint limits, geometry checks and physical files remain unchanged.
- Flexion bias toward 60 deg (cost .5/2/5) at 240 ticks: stronger bias moved elbow
  to ~49-54 deg but worsened position residual to 172-186 mm. Rejected candidate.
  Elbow z-cost 0/2/4/8 and assist gain 1.2/2 sweeps also failed to give a consistent
  worthwhile improvement. No alternate settings copied into the live planner.
- Nine hand-chosen and 24 deterministic random bound-constrained least-squares
  starts were explored for the first goal. Best found residual ~83.41 mm with
  ~3.45 deg orientation and ~6.4 mm endpoint clearance. This is NOT proof of
  global infeasibility, nor an executable collision-free path; no such claim made.
- 600-tick fixed-goal comparison (10 simulated seconds, not new VR observations):
  orientation cost 2/current: position 84.31/95.28 mm, rotation 2.69/2.44 deg;
  cost 1: position 75.81/89.67 mm, rotation 12.25/12.75 deg;
  cost .5: position 54.54/59.19 mm, rotation 35.47/44.86 deg.
  Sacrificing orientation reduces position error but does not solve both. Such
  a change requires a user objective preference, not an automatic gain tweak.
- Added diagnose_mink_wrist_tradeoff.py for reproducible offline comparisons with
  exact configuration checks, frozen-joint checks, speed and observed acceleration
  assertions on every step. Existing goals, constraints and limits preserved.
  Reports: mink_elbow_flex_sweep_20260909.json, mink_elbow_zcost_sweep_20260909.json,
  mink_elbow_gain_sweep_20260909.json, mink_wrist_goal_feasibility_20260909.json,
  mink_wrist_multistart_20260909.json, mink_wrist_tradeoff_verified_20260909.json.
- The requested tracking improvement is not complete. Need user decision before
  trading wrist orientation accuracy for position; raw/clutch display alignment
  also remains unverified for the entire trial (only two braking snapshots saved).
  No G1/SSH/WSL/UDP/publisher/controller run was performed.

## 2026-09-09 user wrist / green marker mismatch diagnosis

- Read latest 15:06:54-15:07:31 status and two saved braking snapshots in
  mink_blocked_1788934014238453300.jsonl. No runtime/controller changes or robot run.
- Current entry uses clutch-relative position AND orientation: engage captures
  input wrist and model wrist baselines, then applies deltas. Absolute hand/model
  rotations are not supposed to be equal; this alone cannot explain every error.
- In upstream mode, feasible_target_position is planner FK during the solved step,
  not the raw user wrist target. Unity uses LatestFeasibleTargetOperatorDelta for
  the green feasible marker. It can lag/differ from the user's requested wrist.
- Recomputed FK using isolated MuJoCo 3.12: two recorded blocked/braking samples
  have position residual 174.84 / 176.90 mm, orientation residual 36.15 / 33.21 deg,
  elbow flexion at the 5 deg operational lower limit, clearance 9.147 / 5.369 mm.
  Thus an actual IK tracking residual exists, not just an Euler display mismatch.
  These two samples do not represent the entire trial or prove calibration wrong.
- Report: logs/test_results/mink_wrist_display_diagnosis_20260909.json.
  Likely next investigation is elbow/whole-arm reconfiguration under simultaneous
  wrist position/orientation constraints; distinguish raw goal from FK marker.
  No automatic gain/limit/mapping changes made based on these limited snapshots.

## 2026-09-09 integrated resampled owner / simulation runtime pin (offline)

- MinkCycleOwnerOffline resample=true now composes the 500 Hz right-arm output
  with policy legs, preserved waist/left arm, and measured-to-full-body path check.
  Candidate return settling additionally gates on <=2 ms old composed output at
  ready and stopped; then all target/output/measured conditions must hold 0.5 s.
  Default standalone candidate/owner behavior retained for prior fixtures.
- 8 integrated scenarios cover four pinch/tracking return/re-engage cycles with
  stationary/moving measured feedback, missed output tick, geometry failure,
  emergency stop and stale-output ACK rejection. Existing 60 C++ scenarios pass.
  These use synthetic native bytes and injected geometry checkers, not robot state.
- Both offline IK producer and output checker now explicitly use isolated MuJoCo
  3.12.0. Same-runtime replay: 579 accepted source samples, two returns/re-engage,
  4,909 output segments all pass geometry; max speed .12532697 rad/s, acceleration
  1.04719755 rad/s^2. Old 3.11 failed report retained; no collision guard relaxed.
- START_MINK_ARM_CYCLE_SIMULATION.bat pins process-local G1_MINK_SIM_MUJOCO_ROOT;
  entrypoint validates simulation-only flag, version and actual module location.
  Four runtime bootstrap checks and four simulation provenance tests passed.
  Global packages and physical Robot launcher unchanged. No simulation window,
  G1, SSH, WSL, DDS publisher or physical output was started this turn.
- Existing open simulation must restart to pick up the pin. Actual Unity/Quest
  display under 3.12 remains unverified. The simulation launcher remains Python;
  it does not start the C++ owner. Integrated owner currently uses fixed punctual
  source/receipt and output logical clocks, not a network or real-time scheduler.
- Remaining before hardware: measured ready transition/ABI, actual policy worker
  and DDS/transport/event-ack binding, timing and damping/stop integration. Model
  geometry audit and native-owner synthetic tests remain separate verification.
  Contract/reproduction: MINK_CYCLE_CANDIDATE_OFFLINE.md.

## 2026-09-09 60 Hz / 500 Hz resampler (offline; runtime discrepancy retained)

- Added mink_resampler_offline.hpp, test_mink_resampler_offline.cpp and batch
  fixture generator; no SDK/publisher, existing physical C++/Robot launcher and
  default MuJoCo installation untouched. Working tree changes preserved.
- Fixed 60 Hz source grid -> continuous-velocity quadratic B-spline evaluated on
  500 Hz logical grid. 90/180 deg/s, 60 deg/s^2 checks; non-arm values preserved.
  Convex knot range, final hold exact; corners smoothed, ramp delay 41.7 ms and
  final settling lag <=50 ms with continuing hold input. Not exact waypoint tracking.
  Trusted segment callback required; owner failure, malformed/stale input,
  missed output tick, underrun or path rejection invalidates output and latches stop.
- 16 resampler scenarios / 15,204 output samples passed including actual 90/180
  cap attainment and bounded deceleration; synthetic limits are not robot settings.
  Existing 20 owner + 24 cycle scenarios passed; MSVC /W4 /WX builds passed.
- Extended model replay generates a marked-unvalidated 500 Hz batch fixture.
  Separate audit checks all output segments. Default MuJoCo 3.11.0 rejects at
  6.256 s (midpoint reports -133.350 mm); isolated 3.12.0 same pose is +40.442 mm.
  3.12.0 passes all 4,909 output segments, max speed .12532229 rad/s and max
  acceleration 1.04719755 rad/s^2. Reports saved as mink_resampler_geometry_*.json.
  Default failure was reproduced and retained; no guard was disabled.
- TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat now explicitly audits using existing
  isolated 3.12.0 (not a global runtime change). Existing 579-sample input replay
  still completes two returns and re-engages. No G1/SSH/WSL/DDS/physical run.
- Remaining: select/verify consistent IK + geometry runtime before live use;
  connect resampled output to owner and make return acknowledgement wait for
  buffered output plus measured settling; real scheduler timing and stop integration.
  Actual 500 Hz deadline performance was NOT measured by the logical-clock tests.
  Details and default-failure reproduction command are in MINK_CYCLE_CANDIDATE_OFFLINE.md.

## 2026-09-09 native-feedback / owner reference adapter (offline)

- Added mink_cycle_owner_offline.hpp and test_mink_cycle_owner_offline.cpp;
  existing physical C++ and Robot launcher remain untouched. No G1/SSH/WSL,
  DDS subscriber/publisher, service change or physical output was run.
- Reuses pinned native-packed LowState CRC decoder, measured q/dq and R1/Select/B,
  existing 20 ms receipt/tick continuity, configurable health checks. Policy leg
  positions must match state sequence and inference time. Composes 0..11 policy,
  12..21 supplied ready baseline, 22..28 cycle absolute target. This is an offline
  reference snapshot, not a motor command or a 500 Hz write authorization.
- Trusted arm/full-body geometry callbacks required. Every fault clears reference
  and latches stop. New input/state invalidates previous reference. This adapter
  does not execute damping; a future physical owner must handle the stop result.
- Updated TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat: MSVC /W4 /WX passed, 20 new
  synthetic native-byte adapter scenarios + 24 existing cycle scenarios passed.
  Existing model-to-stdio replay again accepted 579 samples, two returns and
  re-engage. That replay does not exercise the new native-byte adapter.
- Remaining: actual LowState ABI/runtime binding and ready transition, 500 Hz
  bounded resampling with geometry checks, producer epoch/ack transport, policy
  inference/action conversion, physical stop integration and timing validation.
  Next priority is resampling; do not wire 60 Hz samples directly to 500 Hz output.
  See MINK_CYCLE_CANDIDATE_OFFLINE.md for call sequence and verification limits.

## 2026-09-09 separate C++ absolute cycle candidate (offline)

- User requested next implementation. Added mink_cycle_candidate_offline.hpp,
  dedicated C++ tests, local stdio adapter, real-model Python replay and
  tools/TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat. Existing physical trial, validator,
  target receiver, old cycle prototype and Robot launcher remain unchanged.
- New explicit offline-only schema/profile; absolute seven-joint samples with
  90/180 deg/s and 60 deg/s^2 derivative checks, caller-supplied bounds/path check,
  session/sequence/epoch validation, explicit return phase and measured settling.
  Release does not silently turn inactive data into active targets. Return epoch
  is generated by C++; fresh idle/re-engage follows acknowledged completion.
- No SDK/socket/publisher/policy/physical writer. Controls and feedback are
  supplied by the offline harness. Latched stop preserves target; future owner
  integration must enact its own damping/stop response, not ignore the state.
- MSVC /W4 /WX builds passed; 24 C++ scenarios passed. Real Mink/Ruckig model ->
  local C++ pipe accepted 579 samples, two return cycles (107/106 ticks), then
  re-engaged. Model feedback is ideal prior target, not measured robot state.
  Report: logs/test_results/mink_cycle_candidate_model_replay.json.
- See experiments/twist2_right_arm_manual/MINK_CYCLE_CANDIDATE_OFFLINE.md for
  protocol, exact command, validation and remaining integration. Remaining:
  trusted geometry/LowState adapter, event acknowledgement back to producer,
  500 Hz resampling and single-owner integration, timing and robot validation.
  Neither source nor executable was transferred to G1. No WSL/SSH/DDS run.

## 2026-09-09 v4 return / G1 handoff boundary review

- User approved the next local validation/preparation step. Latest v4 snapshot
  13:52:05 shows two tracking-release returns and one re-engage (13:49:32 ->
  :34 -> :36; 13:50:20 -> :23). Later input_timeout, no return collision rejection.
- Reviewed actual launcher/local receiver sources. Existing robot route remains
  0.7 rad/s, 10 deg/s^2 and input_disengaged -> damping. Simulation is 90/180
  deg/s, 60 deg/s^2 and return/re-engage. Remote binary not inspected. No G1,
  WSL, DDS, camera, SSH, launcher or robot program was executed.
- Added docs/MINK_V4_G1_HANDOFF.md with verified mapping, mismatches and exact
  native-candidate work remaining. Old ArmCycleOffline also uses old limits and
  relative anchoring; it is not interchangeable with the absolute Mink receiver.
- Boundary fix: simulation feedback previously inherited a live_mink label from
  the shared entrypoint factory despite candidate UDP output being disabled.
  New mark_simulation_cycle_packet explicitly marks simulation-only feedback;
  relay rejects simulation-only/cycle metadata even with an old live label.
  This does not enable any new transport or change the existing robot C++.
- Added test_simulation_handoff_boundary.py: actual model qpos/G1 joint mapping,
  fake relay preservation of 29 values and both release modes, and rejection
  of simulation packet variants without calling sendto. Fixture initially used
  contract names without model '_joint' suffix; corrected, 4 tests passed.
  Existing relay 12 tests passed using mocks, without actual UDP transmission.
  Return handshake 10 and producer provenance 6 also passed: 32 tests total.
- Existing known return-path collision issue and replay timing >16.7 ms remain;
  the two successful user returns do not close those general issues. Next is a
  separate local native candidate/event contract, not using the old Robot mode
  with simulation packets. No physical deployment or PD changes this turn.

## 2026-09-09 60 deg/s^2 and elbow reconfiguration v4

- User requested acceleration 60 deg/s^2 plus elbow reconfiguration. Simulation
  tracking/return settings, launcher, diagnostics and offline fixture now use
  60 deg/s^2; velocity caps 90/180 deg/s and goal approach braking retained.
  No robot/C++/SSH/DDS edits or execution; running Input was not restarted.
- Added local elbow-height secondary objective when elbow flexion <20 deg and
  clearance <12 mm. Fixed target rises up to 8 cm, capped 4 cm below shoulder
  height. Deactivates above 25 mm clearance or on reset/return. Wrist objective
  remains in QP; no promise of exact wrist pose during reconfiguration.
- Found raw MuJoCo zero-distance artifact for an elbow/hip-roll geom pair at
  the saved stuck pose (~125 mm with existing robust distance probe). Mink QP
  and final exact checker previously disagreed. Suspicious zero/no-contact pairs
  now use the same robust distance and finite-difference right-arm Jacobian.
  Actual/unresolved contacts remain constrained. No site-packages modification.
- 0.5 mm QP clearance reserve, acceleration-aware contact approach speed bound,
  and joint-limit stopping-speed bounds avoid repeatedly hitting the exact
  boundary at nonzero velocity. All final candidates/braking remain exact-checked.
  These are project extensions to Mink, not vanilla upstream behavior.
- Recorded failing pose fixture: backend/tests/fixtures/mink_elbow_boundary_20260909.json,
  from last row of mink_blocked_1788928048329940800.jsonl. Final 300-tick replay:
  all 300 following; elbow world height +78.95 mm; wrist position error
  121.52 -> 49.74 mm; minimum clearance 5.002445 mm; max observed acceleration
  1.0471975512 rad/s^2 (60 deg/s^2). Elbow flexion ends at 5 deg: the elbow is
  spatially raised through shoulder rotation, not merely elbow flexion.
  Output: logs/test_results/mink_elbow_assist_v4_20260909.json.
- Local replay timing p99 38.24 ms, max 42.54 ms: 60 Hz real-time performance
  is NOT established. Robust zero-distance probes can add latency. No VR
  validation yet; optimize/inspect timing if responsiveness suffers.
- 30 tests passed: stream, return handshake, model return, fixed 2/5 cm
  overshoot at 60 deg/s^2 and new recorded-boundary regression (lift >5 cm,
  error <6 cm, no hard hold, limits, acceleration and other joints unchanged).
  Before joint/contact stopping bounds, the elbow replay had 5 hard holds;
  final replay above supersedes that intermediate result.
- Runtime marker mink_goal_braking_elbow_assist_v4, diagnostics include
  elbow_reconfiguration_active and corrected_zero_distance_pairs. Restart
  START_MINK_ARM_CYCLE_SIMULATION.bat. Remaining: nonzero wrist residual,
  varied hand/orientation goals, VR timing, and collision-aware return paths.

## 2026-09-09 acceleration restored to 30 deg/s^2 with goal braking retained

- User approved restoring acceleration after reporting 10 deg/s^2 too slow.
  Simulation tracking/return caps, console/status, launcher and offline fixture
  now use 30 deg/s^2. Goal-braking v3 and velocity caps 90/180 deg/s unchanged.
  No G1 changes, physical execution or simulation process restart performed.
- All 29 stream/handshake/model/tracking tests passed, including fixed 2/5 cm
  goal overshoot, measured acceleration and frozen-joint regressions at 30.
- Comparison: logs/test_results/mink_goal_acceleration_comparison_20260909.json.
  With v3 at both accelerations, time first within 5% of target displacement:
  2 cm: 3.667 -> 3.400 s; 5 cm: 8.917 -> 5.150 s (10 -> 30 deg/s^2).
  All four 600-tick trials: zero forward overshoot and no hard holds.
  These are fixed-target local-model trials, not live VR/robot validation.
- Restart START_MINK_ARM_CYCLE_SIMULATION.bat to load. Elbow reconfiguration
  stall and collision-aware return remain separate unresolved work.

## 2026-09-09 13:28 log review: elbow reconfiguration stall

- Latest status 13:28:48 confirms goal_braking_v3. Recorded input path:
  mink_blocked_1788928048329940800.jsonl, 23 sampled diagnostics: 21 braking,
  2 hard holds. Last 18 samples have identical full qpos despite changing hand
  goals: actual stall, not just slow acceleration.
- Stalled right elbow is exactly its 5-degree lower bound; shoulder roll
  -0.926 deg, yaw 23.469 deg. Current exact clearance is 5.002445 mm, almost
  the 5 mm boundary. One earlier rejected candidate exceeded elbow lower
  limit; the other had 4.998993 mm clearance. No rejected pose was applied.
- Current planner optimizes local wrist pose + posture + damping, then checked
  braking. It has no explicit elbow-height/redundancy objective or alternate
  posture/path search. Braking reaches zero and cannot escape this boundary.
  Raising elbow spatially needs shoulder/arm reconfiguration, not simply raising
  the elbow flexion angle. Feasibility of that alternate pose/path is unverified.
- 13:28:11 pinch -> return; 13:28:17 input_timeout -> fault, no collision return
  rejection recorded this time. Snapshot's zero position error is inactive and
  must not be treated as successful tracking of the last hand goal.
- Read-only diagnosis plus this record only. Next improvement: test redundant
  arm reconfiguration on this exact saved pose while retaining wrist objective,
  joint/geometry constraints and path validation; do not just relax limits.

## 2026-09-09 target overshoot correction / acceleration 10 deg/s^2

- User requested 10 deg/s^2 and clarified the symptom is passing a target then
  returning (overshoot). Simulation tracking AND return acceleration changed
  from 30 to 10 deg/s^2; velocity caps remain 90/180 deg/s. Launcher text and
  runtime diagnostics match. Physical TWIST2/G1 path unchanged; no restart/run.
- Root code issue: fixed FrameTask gain .35 at 60 Hz requests rapid error
  removal regardless of the acceleration-limited stopping distance. Lowering
  acceleration alone increases braking distance, not overshoot protection.
- Local goal approach scheduling in g1_upstream_mink_tracking.py estimates joint
  correction using the wrist Jacobian and limits approach rate to
  min(1/s, sqrt(a_i/(4*abs(correction_i)))); wrist gain is dt*rate capped by its
  old gain. Posture gain receives the same ratio to preserve equilibrium.
  Gains are restored after QP construction. Existing constraints, exact geometry
  check, checked braking and hard-stop fallback remain. This is project-specific
  local scheduling, not an upstream Mink default/global no-overshoot guarantee.
- Offline comparison at 10 deg/s^2, fixed wrist orientation, model home, 600 ticks
  (10 seconds): 2 cm forward target old overshoot 5.403 mm -> new 0;
  5 cm old 11.895 mm -> new 0. New final position errors 0.224 / 2.251 mm;
  both have zero hard holds. logs/test_results/mink_goal_overshoot_20260909.json.
  Slower settling remains a tradeoff; moving targets/orientation changes and
  unreachable/collision-constrained goals are not covered by these two trials.
- Added regression for both fixed targets, observed acceleration <=10 deg/s^2,
  frozen joints unchanged, no hard holds, <=0.1 mm forward overshoot and final
  3D position error <3 mm. All 29 stream/handshake/model/upstream tests pass.
- Runtime marker: mink_reduced_velocity_qp_goal_braking_v3. Restart
  tools/START_MINK_ARM_CYCLE_SIMULATION.bat to apply. VR visual validation and
  existing collision-aware return problem remain outstanding.

## 2026-09-09 13:08 user log review

- Latest g1_mink_status.json at 13:08:35 confirms
  mink_reduced_velocity_qp_checked_braking_v2; 1442 packets, 0 rejected.
- 13:07:37 tracking_disengaged -> returning; 13:07:40 return acknowledged,
  await_active; 13:07:43 active/ready. Tracking-loss return/re-engage succeeded.
- 13:08:06 pinch triggered return then trajectory_collision_hold fault. Rejected
  return sample clearance 4.910254 mm vs required 5 mm; the rejected candidate
  was not applied. input_timeout is a later input fault, not the first stop cause.
- mink_blocked_1788926820940609400.jsonl has 16 sampled diagnostics: 13 checked
  braking and 3 hard holds. All 3 hard holds report model joint ID 26 below its
  5-degree lower bound (4.9705, 4.9931, 4.9474 degrees approximately), not measured
  body collisions. Model joint IDs must not be confused with G1 motor indices.
- Samples are rate-limited diagnostics, not full-tick statistics. No evidence
  here establishes overall tracking improvement or a failure percentage.
  This turn reviewed logs only; no control changes or runtime actions.

## 2026-09-09 sluggish tracking: reduced QP and checked braking

- User asked to fix sluggish/stop-start tracking. Local simulation changes only;
  no robot, DDS, SSH, runtime restart or gain/speed/acceleration setting changes.
  Current configured caps remain 90/180 deg/s and 30 deg/s^2. The latter still
  requires at least 3/6 seconds to accelerate from rest to those speed caps.
- g1_upstream_mink_tracking.py now builds the Mink objective, eliminates frozen
  DOFs and solves a 7-variable velocity QP. Scales/normalizes constraints and
  objective for numerical conditioning. Rejects non-freezing equality constraints.
  Installed Mink 1.3.0 CollisionAvoidanceLimit h is gain*(distance-min)/dt;
  build_ik uses delta-q, so the adapter multiplies that h by dt. Other limit
  bounds retain their native delta-q units. This is a project adapter, not an
  unchanged upstream example. Review conversion if Mink implementation changes.
- Failed solve or rejected candidate first attempts a checked deceleration step
  from previous velocity. Only if that also fails exact geometry validation does
  it hold/reset. This preserves acceleration continuity on ordinary fallback;
  hard geometry stops remain exceptions. Return retains Ruckig velocity seeding.
- Added tests for 120-tick free motion with observed velocity-difference checks,
  and injected solver failure with nonzero velocity. 28 tests pass across stream,
  handshake, model return and upstream tracking. Free motion remains within
  30 deg/s^2 without instantaneous resets; no physical safety claim.
- Final recorded replay: mink_checked_braking_replay_20260909.json, 18 saved
  poses x 120 ticks, 35 hard holds, 10/18 reduced position error, minimum
  0.00499990055 m (existing exact-check tolerance 1e-7 m). Non-held ticks include
  braking/zero velocity; do not count them all as successful target following.
- A 0.5 mm recovery-margin candidate failed the free-motion regression and was
  removed. Intermediate 500-tick results mink_smooth_replay_20260909.json and
  mink_smooth_margin_replay_20260909.json are not final-code validation.
  DAQP proximal/tolerance tuning was also tried (mink_checked_braking_daqp_replay_20260909.json);
  hard holds increased to 40, so those solver settings were reverted. Final
  replay has 392 following, 1733 braking, 35 hard-hold ticks; peak observed
  acceleration including hard holds is 19.897 rad/s^2. The 30 deg/s^2 bound
  applies to accepted normal/braking steps, not hard collision stops.
- Runtime tracking_collision_flow now identifies
  mink_reduced_velocity_qp_checked_braking_v2. Restart the simulation Input to
  load it. Actual VR smoothness and remaining collision-boundary stalls require
  a new user trial; continuous obstacle detouring is still unresolved.
- git diff --check reported an existing blank line at handoff EOF outside this
  edit; left unrelated content intact.

## 2026-09-09 tracking_disengaged return and re-engage

- User requested tracking_disengaged to return to the initial pose like pinch.
  In the simulation_return_handshake path, a fresh accepted tracking_disengaged
  packet after engagement now starts returning instead of latching fault.
  Uses the same checked return trajectory, epoch/session acknowledgement and
  post-return inactive packet requirement as pinch. Continued tracking_disengaged
  packets count as inactive; only a fresh active input starts a new clutch.
- Before the first engage, old disengage packets still do not trigger return.
  Repeated disengage during return does not restart the trajectory. Premature
  active packets cannot bypass completion. Input timeout, rejected packets,
  session change and existing workspace/shutdown faults remain faults.
- Modified backend/g1_teleop/mink_command_stream.py and handshake tests;
  simulation launcher description updated. Existing non-simulation behavior and
  robot C++ unchanged. No process restart, robot command or deployment performed.
- Offline verification: 26 tests passed across command stream, return handshake,
  model return and upstream tracking. Covers three tracking-loss/re-engage cycles,
  fresh anchor, queued tracking-loss before active, and timeout during return.
- User next step: restart START_MINK_ARM_CYCLE_SIMULATION.bat and verify actual
  Unity tracking loss -> model return -> re-engage. Collision rejection can still
  fault the return; this change does not bypass collision checks. Live VR unverified.

## 2026-09-09 upstream vanilla Mink collision path (local simulation only)

- User requested GitHub vanilla Mink collision handling. Reviewed upstream
  https://github.com/kevinzakka/mink/blob/main/examples/humanoid_g1.py and
  https://github.com/kevinzakka/mink/blob/main/src/mink/limits/collision_avoidance_limit.py.
  Installed Mink 1.3.0 CollisionAvoidanceLimit is used without editing site-packages.
- START_MINK_ARM_CYCLE_SIMULATION.bat now selects --upstream-mink-collision.
  This flag requires vanilla + simulation-arm-cycle; candidate UDP 5008 remains disabled.
  START_TWIST2_MINK_UDP and robot C++ paths were not changed by this work.
- g1_upstream_mink_tracking.py uses solve_ik -> integrate_inplace, upstream G1
  example minimum 5 mm / detection 150 mm. Existing project body geom pairs,
  task weights, frozen non-right-arm DOFs remain project-specific. This is an
  integration of the upstream limit, not an identical copy of the G1 example.
- Shoulder/elbow 90 deg/s, wrist 180 deg/s and acceleration 30 deg/s^2 are
  QP constraints. Tracking no longer passes through Ruckig and has no jerk cap.
  Return still uses checked Ruckig; optional initial velocity/acceleration seeds
  preserve the tracking-to-return state. Existing limiter callers retain defaults.
- Direct upstream integration alone failed recorded-pose validation:
  mink_upstream_replay_20260909.json had minimum -4.704 mm (model overlap).
  Isolated MuJoCo 3.12 replay also went below 5 mm. Therefore exact geometry
  sampling remains after integration; rejected steps hold rather than applying.
- Checked replay: logs/test_results/mink_upstream_checked_replay_20260909.json:
  11 recorded poses x 500 ticks, all 11 reduced position error, minimum 5.004 mm,
  4598 held ticks. This does NOT solve continuous obstacle detouring; upstream
  local IK plus acceleration constraints can remain infeasible or stuck.
  Hold resets velocity; acceleration continuity across emergency model holds
  is not guaranteed. Do not reuse this experimental path for hardware output.
- Validation: model return 2, stateful trajectory 3, return handshake 8,
  new upstream tracking/return seed + forced collision hold 2 tests passed.
  Initial handshake package-style invocation failed on test helper import;
  unittest discovery with -s backend/tests passed. New tests initially used
  uninitialized qpos; corrected fixture to the actual model initial pose.
- No robot/SSH/WSL/DDS actions, no viewer restart or new live VR trial performed.
  Existing dirty tree preserved. Next: user simulation test and investigate
  recorded QP infeasibility/geometry rejection if continuous tracking still stops.

## 최신: QP 여유 수정 후 사용자 로그 검토 (2026-09-09 10:51)

- g1_mink_status 최신10:51:29: simulation=true,수신1667/reject0,exact거리0.020/QP0.0205m로 수정 적용 확인. mink_blocked_1788918626048672200.jsonl 11개 sampled block 중 IK8/trajectory3,관절한계위반0.
- IK8개는 현재 clearance20.059618mm에서 collision_hold/accepted0. trajectory3개는 IK accepted3 이후 shaped sample clearance19.998746/19.998985/19.997199mm로20mm 검사에 거부. 즉 QP reserve가 일부 초기경계 정지를 개선했으나 IK 경계정지와 속도·가속도 후처리 경로불일치가 모두 남음. sampled block 수를 전체 틱/전체 실패율로 해석하지 말 것.
- 상태전이10:51:11 returning→10:51:14 await_idle/await_active: 모델 초기자세 복귀 정상완료 확인.10:51:17 input_timeout은 복귀 후 발생; 사용자가 Play를 종료했는지 이 로그만으로 확정 불가.
- 이번 요청은 로그검토만 수행. 제어값/코드/실기 변경이나 재시작 없음. 다음 개선 대상은 단순 충돌거리 완화가 아니라 IK와 Ruckig 후처리의 경계 일관성 및 남은 IK 정지 원인.

## 최신: 평소 추종 몸통 경계 정지 재현·시뮬레이션 QP 여유 수정 (2026-09-09)

- 사용자 몸통 쪽 손 추종 재현 완료. logs/test_results/mink_blocked_1788918337245842200.jsonl 16개 snapshot 모두 IK collision_hold/accepted_steps0/trajectory_planner_hold. 마지막 시작 자세 clearance0.020048166m,관절한계위반 없음. 사후 input_timeout은 시험 종료 이후일 수 있어 최초 정지 원인과 분리.
- g1_tracking_diagnostic.py 추가,simulation-arm-cycle에서만 최대4Hz/2400개 blocked snapshot JSONL 저장. full current q,손 goal pose,IK target,rejected shaped sample,거리/관절위반/상한 기록. 종료 후에도 last_blocked_tracking이 상태에 남음. 실제 모델로 IK/trajectory 구분 및 관절거부/throttle 검사 통과.
- replay_mink_boundary.py 추가 및 동일16개 입력/자세 재생. 기존 QP 최소거리20mm에서16/16 zero-step 재현. QP에0.5mm reserve를 주고 후검사20mm 유지 시16/16 다음 움직임 승인. 단순 거리 완화가 아님; 선형화 제약과 실제검사 경계 불일치가 적어도 초기 정지의 한 원인이라는 근거.
- 마지막 snapshot으로 실제 Ruckig 포함500틱 비교: 기존500hold,위치오차0.12623m 고정. reserve0.5mm는324hold,위치오차0.08107m,최대관절변화0.45477rad. 최소clearance0.019999995m(기존1e-7m 검사 허용오차 안). 이후 정지는 남아 있어 완전한 우회/목표도달 보장 아님. 결과 mink_boundary_rollout_20260909.json,초기 one-step mink_blocked_replay_20260909.json.
- simulation-arm-cycle QP 최소거리에 기존 MINK_DEFAULT_QP_RESERVE_M=0.0005 적용. exact validation20mm,속도90/180°/s,각가속도30°/s² 유지. 실기/비-cycle guarded 경로 변경 없음. 실제 모델 복귀2개 및 문법/whitespace 검증 통과.
- 제가 시작한/확인된 local simulation만 재시작하여 사용자 재현을 기록했다. G1/WSL/DDS/물리 출력 없음. 최종 reserve수정 이후 Input 재시작 및 VR 개선 확인은 아직 안 함. 다음은 새 시뮬레이션 실행으로 같은 몸통 접근 동작 비교; 남은 정지는 저장된 snapshot으로 별도 분석.

## 최신: 시뮬레이션 일회성 손목 튐 회복·각가속도30°/s² (2026-09-09)

- 사용자 승인에 따라 simulation-arm-cycle 각가속도를30°/s²(0.5235988rad/s²)로 변경. 추종/복귀 Ruckig·콘솔·배치·상태 로그 일치. 속도90°/s(22~25)/180°/s(26~28),기존 jerk 유지. 기존 실기 및 비-cycle 제한 불변.
- Unity binder RecoverTransientPoseOutlier 비직렬화 옵션 추가. sender가 신선한 simulation_arm_cycle 피드백에서만 활성화. 일회성 위치 튐은 목표에 반영하지 않고 마지막 승인 위치 보존, 다음 입력을 그 승인 위치 기준으로 다시 검사하여 정상일 때 latch를 해제하고 추종 재개. 거부 위치를 새 기준으로 삼거나 계속 멀어진 위치를 자동 승인하지 않는다.
- 기존 위치 검사 기준1.1m/s 및 최소2cm,Meta 신뢰도,추적손실0.35초,통신 timeout 유지. 지속 비정상은 기존 tracking_disengaged로 이어짐. 정상 실기 피드백에서는 기존 latch 유지.
- Unity C# MSBuild 성공,실제 MuJoCo 모델 새 가속도 복귀 시험2개+handshake8개 통과. diff whitespace 검사 통과. Unity Editor 재컴파일 및 실제 일회성 튐 회복/빠른 VR 추종은 아직 미확인. Play 중지/재컴파일 후 Input 재시작 필요. G1 실행/변경/배포 없음.

## 최신: 시뮬레이션 팔90°/s·손목180°/s 적용 (2026-09-09)

- 사용자 기준 확인에 따라 --simulation-arm-cycle에서 오른팔22~25(어깨3+팔꿈치) 최대90°/s=π/2rad/s,26~28(손목3) 최대180°/s=πrad/s로 변경. cycle_velocity_limits()를 IK VelocityLimit/플래너/추종·복귀 Ruckig에 공통 적용해 이전0.7rad/s 병목이 남지 않도록 했다.
- 각가속도10°/s²와 기존 jerk 유지. 속도 상한 변경이 짧은 동작에서 해당 속도 도달을 보장하지 않는다. 정지에서90/180°/s까지 가속도만 고려해도 최소9/18초이며 jerk 때문에 더 길어질 수 있다.
- 배치 안내/실행 콘솔/상태 로그 실제 관절별 상한 갱신. 정상 비-cycle 및 실제 G1 배치/PD/제어 코드/배포 변경 없음. 실행 중 프로세스 재시작이나 G1/VR 시험은 하지 않았다.
- 실제 MuJoCo 모델 이동·복귀2회와 상한/타관절 검사2개,trajectory3개,handshake8개 총13개 통과. 새 속도상한에서 실제 VR 추종과 최고속도 도달은 미확인. 다음 새 START_MINK_ARM_CYCLE_SIMULATION 실행부터 적용.

## 최신: 사용자 VR 복귀·재engage 정상 확인 (2026-09-09)

- Unity 조기 engage 차단 수정 후 사용자 '잘됐다'로 시뮬레이션 팔 조작→pinch→초기자세 복귀→재engage 동작 정상 확인. 직전 미확인 기록을 갱신하는 사용자 화면/조작 확인이며 추가 자동 로그 분석은 하지 않았다.
- 확인 범위는 START_MINK_ARM_CYCLE_SIMULATION의 Unity/MuJoCo 경로. 실제 G1 배포/복귀/재engage, 다리 모드 전환, AI 자동복귀 검증이 아니다. 기존 실기 배치 pinch→damping 및 R1 조건 불변.
- 이전 특정 복귀 후보의 trajectory_collision_hold 원인을 규명한 것은 아니며 모든 복귀 경로의 충돌 통과를 보장하지 않는다. 이번 성공 흐름과 오류 시 중단 경계를 유지할 것.

## 최신: Unity 조기 engage 차단 연결 (2026-09-09)

- 사용자 추가 확인: 팔 초기자세 복귀는 완료됐고 재engage만 실패. Python은 복귀 중 active를 무시하나 Unity는 이미 calibrated 상태를 유지할 수 있어 완료 후 새 inactive→active가 오지 않는 연결 누락 확인. 이전 timeout 기록만으로 최초 실패 원인을 단정하지 않는다.
- G1RobotStateUdpReceiver가 simulation_arm_cycle(state/candidate_output_disabled) 마커를 읽어 returning/await_idle/fault 또는 해당 피드백 stale 시 engage를 차단. ready/await_active에서 허용. 이 마커는 새 시뮬레이션 옵션만 송신하며 일반 실기 피드백에는 적용 안 함.
- G1ExistingTargetUdpSender는 차단 중 binder.ResetCalibration, pinch_disengaged 상태 유지, 필터 reset. 복귀 완료 await_idle에 비활성 확인을 보내 Python이 await_active로 전환하면 새 Unity calibration/active를 허용. Unity와 backend의 조기 engage 상태 어긋남 방지.
- Unity Assembly-CSharp.csproj MSBuild /restore /t:Build 성공. 기존 obsolete 및 JSON 역직렬화 필드 경고 있음. 최초 assets.json 없음 오류는 restore로 해결. Unity Editor의 실제 재컴파일/Play 동작은 별도 확인 필요하며 외부 MSBuild만으로 Editor 반영 완료를 단정하지 않음.
- 사용자 다음: Unity Play 중지, Unity 재컴파일 완료 후 시뮬레이션 Input 재시작, Play→engage→이동→pinch→복귀→pinch 풀고 새 engage. G1 변경/실기실행 없음. 실제 수정 후 반복 성공은 아직 미확인.

## 최신: VR 재engage 실패 진단·입력 조건 수정 (2026-09-09)

- 추가 재시험도 사용자 실패 보고. 다음 기록은 trajectory rejection이 없고 input gate fault였음. 세부 원인 기록 누락을 보강하여 이후 최신10:19:11 input_timeout 확인(706수신/reject0). 사용자가 시험 후 Play를 종료해서 생긴 timeout인지 재engage 실패 선행 원인인지 미확정. 추측으로 해결 완료 처리하지 않는다.
- 처음 engage 전 남은 tracking_disengaged/pinch는 fault/return로 처리하지 않도록 수정, 실제 engage 후 timeout/추적손실 latch 유지. handshake7개 통과. 해당 수정 이후에도 실패 보고 받았으므로 원인이 이것만은 아님.
- 이후 상태 전이 최근32개를 status에 기록하도록 추가했으나 이 변경은 현재 실행 프로세스에 반영되려면 재시작 필요. Unity의 조기 재engage가 복귀 중 active 상태로 유지되면 이후 새 비활성 edge가 없어 대기할 가능성도 검토 필요; 아직 Unity에 복귀 상태 기반 calibration 차단은 연결하지 않았다. 다음 확인은 실패 시 초기자세 복귀 완료 여부/실제 state 전이이며 무분별한 제한 완화는 하지 말 것.

- 사용자 확인: engage 후 팔은 움직였으나 pinch 후 재engage 불가. 로컬 시뮬레이션 재시작 후 수신836/reject0, pinch_disengaged→trajectory_collision_hold fault 확인. 유지 자세 clearance0.04048m이나 거부된 후보는 기록되지 않아 실제 충돌/관절한계 중 원인은 미확정. 해당 메시지는 두 검사 실패를 포함한다.
- Unity G1ExistingTargetUdpSender.cs는 재engage 전까지 pinch_disengaged를 계속 송신한다. 새 idle 필수 조건이 프로토콜과 불일치하여 완료 ack 이후 새 pinch_disengaged도 비활성 확인으로 인정하도록 옵션 경로 수정. 복귀 중 active 차단/fault latch 유지. handshake6+model return2+trajectory3=11개 통과.
- 상태 로그에 cycle 상태/거부 sample/current/home/clearance를 추가해 다음 실패 원인 확인 가능. 제가 시작한 --simulation-arm-cycle 로컬 프로세스만 식별 후 재시작. 수정 후 사용자 재시험 요청 대기,10:15:26 ready/수신0. 복귀 경로 거부 자체는 아직 해결하지 못했음. 다음 logs/runtime/g1_mink_status.json arm_cycle_rejection 분석 필요.
- G1/SSH/WSL/DDS/실기 실행/배포 없음. 기존 실기 배치 보존. 수정 후 실제 VR 반복 성공은 아직 미확인.

## 최신: 실제 MuJoCo 루프 복귀·재engage 연결 (2026-09-09)

- run_mink_g1_right_arm_virtual_center_live.py 기존 변경사항을 보존하고 --simulation-arm-cycle 선택 옵션 추가. 기본/실기 배치 동작 불변. g1_mink_return_cycle.py가 실제 configuration과 기존 StatefulMinkTrajectory/Ruckig를 공유해 pinch 시 속도를 유지한 채 초기 모델 자세로 복귀한다.
- 0.7rad/s·10deg/s² 제한, shaped step마다 기존 관절/충돌 검사 4분할 샘플, 거부 시 fault latch. 30초 복귀 timeout. 모델 목표/속도 정착0.5초 후 handshake ack, 새 idle→active에서 기존 clutch가 손 위치·방향/현재 FK를 재설정. 실제 LowState 정착이나 연속 충돌 보증이 아니다.
- 새 옵션은 UDP5008 candidate 송신과 외부 Gate7 feedback을 차단한다. Unity5005입력/5006표시는 유지. tools/START_MINK_ARM_CYCLE_SIMULATION.bat 추가; 기존 Input을 종료한 다음 사용. Robot/Relay/SSH/DDS를 시작하지 않는다. --initial-lowstate-seed와 동시 사용 거부.
- 실제 MuJoCo 모델20mm clearance에서 shoulder 목표 이동·복귀2회, 타관절보존/속도·가속도/충돌 거부 정지 시험2개 통과. 기존 trajectory3개+handshake5개 통과, entrypoint --help 및 diff whitespace 검사 통과. C++ 상태기를 실기로 연결한 것이 아니라 Python/Ruckig 실제 모델 루프에 대응 동작을 추가한 것이다.
- docs/ARM_CYCLE_OFFLINE.md 실행 절차 추가. 실제 GUI/Quest 시험은 아직 안 함. 다음: 전용 배치와 Unity simulation에서 engage→움직임→pinch→await_idle→engage 영역 밖→재engage 확인. 초기 복귀 경로가 막히면 fault로 정지하며 자동 우회는 하지 않는다.
- G1/WSL/UDP/Unity 물리 또는 GUI 실행/배포 없음. 실기 START_TWIST2_MINK_UDP는 여전히 pinch→damping이며 R1/AI 자동복귀 변경 없음.

## 최신: Mink 입력 복귀 handshake·C++ 로컬 통합 (2026-09-09)

- 실제 입력 경로 검토: backend/g1_teleop/mink_command_stream.py가 Unity 입력을 검증하며, live_receiver는 pinch 시 batch를 끊어 뒤의 active가 해제를 숨기지 않음. virtual_center_live.py는 engage_clutch에서 현재 손 위치/방향 및 모델 FK를 anchor로 저장하는 기존 로직을 갖고 있다.
- MinkCommandStream에 기본 False인 simulation_return_handshake 옵션 추가. 정상 pinch→returning, epoch/session 확인된 로컬 복귀 완료→await_idle, 새 idle→active에서 engage_clutch 재발행. 복귀 중 active 차단. 입력 거부/세션 변경/추적 해제/workspace fault/timeout은 fault latch. 실기 실행기는 이 옵션을 켜지 않는다.
- test_mink_return_handshake.py: 3회 반복, 잘못된 ack/조기 active, queued pinch, tracking loss/timeout/invalid input 검사. 관련 test_mink* Python 122개 통과(98.684s; benchmark 실패 문구는 의도된 실패 경로 테스트 출력이며 suite OK).
- arm_cycle_stdio_offline.cpp와 test_arm_cycle_stream_integration.py: Unity 형식 bytes→실제 stream→C++ synthetic cycle→completion ack를 pipe로 연결한 2회 반복 통합 시험 통과. C++ /W4 /WX 빌드 성공. 입력 관절값은 합성, 피드백은 직전 목표값으로 실기 dynamics가 아님.
- docs/ARM_CYCLE_OFFLINE.md에 API/실행 방법/경계 추가. 남은 핵심: MuJoCo 실제 loop에 복귀 producer 및 pose 적용 연결, 실제 IK/충돌 검사, Unity 시각 확인. 이번에는 실제 hand/task-space no-jump를 확인한 것이 아니며 기존 clutch를 다시 호출하는 이벤트와 최신 손 입력 전달까지만 검증했다.
- G1/WSL/DDS/UDP/Unity 실행 및 실기 배포 없음. START_TWIST2_MINK_UDP의 동작은 여전히 pinch→damping. R1·AI 복귀 변경 없음. 사용자가 요청한 최종 복귀·재engage 동작의 실사용 연결은 아직 미완료다.

## 최신: pinch 복귀·재engage 오프라인 상태 전이 (2026-09-09)

- 사용자 목표 확정: 팔 조작 → 정상 pinch 해제 → 팔 초기자세 복귀 → 대기 → 새 engage로 팔 조작 재개. 최종 이동 조작 전환은 Omni 후보가 정해진 후 연결하며 정확한 Omni 프로젝트는 미정. 정상 pinch와 오류/비상 중단을 구분한다.
- 현재 upper_target_offline.hpp/InputValidator/RawInputWatchOffline/MinkUdpTarget 검토: 기존 input_disengaged latch는 그대로 보존. 다수 기존 변경사항 확인 후 원본 제어 코드와 배포 파일을 수정하지 않았다.
- arm_cycle_offline.hpp 및 test_arm_cycle_offline.cpp 신규 작성. SDK/UDP 없는 typed-event 프로토타입. 오른팔22..28만 갱신, 0.7rad/s·10deg/s², 복귀 중 속도 연속 제동, 합성 측정 정착 확인 후 대기. 복귀 중 engage 무시, 완료 후 새 idle→active 필요. 재engage는 관절 입력/명령 anchor를 새로 잡아 목표 점프 방지.
- MSVC /std:c++17 /W4 /WX 빌드 및 실행 통과: 3회 반복, anchor, 복귀 중 engage, 속도/가속도, 타관절 보존, fault latch, 입력/피드백/복귀 timeout, NaN, 예상 밖 idle, clock, rebased limit 검사. 초기 재engage 시험에서 수치 잔여 속도로 목표가 변하는 문제를 발견해 정착 완료 시 미소 잔여량 정리 후 재검증했다.
- docs/ARM_CYCLE_OFFLINE.md에 실행 명령과 검증 경계 기록. 이벤트는 신뢰된 합성 입력이며 실기 JSON 검증 어댑터/큐 연결 없음. Unity 손 좌표 재기준화, 복귀 완료 handshake, 복귀 경로 충돌 검사, 실제 LowState 정착 검증이 남아 있다. 관절 offset은 task-space IK 재기준화나 충돌 검증을 대신하지 않는다.
- G1/WSL/DDS 실행·publisher·배포 없음. 현재 START_TWIST2_MINK_UDP의 실기 pinch→damping, R1 및 AI 수동 복귀 동작은 바뀌지 않았다. 다음 작업은 로컬 입력 어댑터와 Unity/Mink handshake 연결 검토이며 실기 동작 완료로 표현하지 않는다.
- 앞선 카메라 시험은 사용자가 '잘 나온다'로 Unity 영상 정상 표시 확인. 이전 'PiP 미확인' 기록을 갱신하는 사용자 확인이며 현재 프로세스 상태를 재조회한 것은 아니다.

## 최신: G1 카메라 실제 수신 확인·Unity 대기 (2026-09-09)

- G1 연결 후 Windows192.168.123.99/WSL eth3 확인. 기존 카메라 브리지 프로세스 없음 확인 후 읽기전용 브리지 시작(exec session77356). 목표 Unity127.0.0.1:5011,20Hz.
- 별도 단발 VideoClient.GetImageSample 읽기: code0,JPEG204428bytes,프레임 형식검사 통과. 이미지 저장/모터명령/모드변경 없음.
- 브리지는 [WAITING] Unity is not listening on TCP5011 상태. 사용자에게 Unity Play 요청. 영상 수신 성공과 Unity PiP 실제표시는 구분하며 PiP는 아직 미확인.
- 브리지를 유지 중이므로 배치 Camera 모드는 기존 프로세스를 재사용한다. 이 상태는 이후 재확인 필요. 팔/Robot 실행 없음.

## 최신: TWIST2 배치에 카메라 수신 연결 (2026-09-09)

- START_TWIST2_MINK_UDP.ps1 Camera 모드 및 All의 네 번째 창 추가. 기존 START_G1_CAMERA_TO_UNITY.bat → WSL VideoClient.GetImageSample → Unity TCP5011 재사용. Camera에는 relay token을 전달하지 않는다.
- Camera 모드는 pgrep로 기존 브리지 유지. start_camera_tcp_bridge_wsl.sh에 flock 추가로 새 브리지의 동시 중복 실행 방지. 기존 프로세스 종료 없음.
- All -Preview 4모드/Camera token 미포함 검사,셸 문법 검사,기존 카메라 프레임 테스트 통과. 실제 All/Robot은 실행하지 않았다.
- 현재 PC G1용192.168.123.x 주소 및 Unity5011 리스너가 없어 실영상 수신은 미확인. 다음 연결 시 배치를 새로 실행하거나 -Mode Camera로 카메라만 추가 후 Unity Play PiP 확인. G1 파일/모터 상태 변경 없음.

## 최신: IK 변경 전후 목표 비교 도구 로컬 구현 (2026-09-08)

- compare_ik_targets.py: 동일입력 파일 해시/모델/초기조건/stage/시간축을 확인하고 오른팔22..28의 자세차이·이동량·속도·가속도·한계여유 및 재검토 시점 출력. 나머지관절 변화도 보고.
- 불균일 시간 간격 차분 사용. 입력/시간축 불일치 자동보간 없음. 큰 목표 변화는 보고하되 불연속/빠른 움직임을 단정하지 않음;PD 재보정 필요성 자동판정 아님.
- test_compare_ik_targets.py 5개 통과 및 CLI 합성 example 실행 성공(22번 변경 감지). logs/test_results/ik_compare_example_20260908/comparison.json.
- docs/IK_TARGET_COMPARISON.md에 trace 형식/실행명령/한계 기록. 실제 두 IK 버전의 같은 손 입력 재생 결과는 아직 생성하지 않았다. 도구는 주어진 trace 비교만 수행하며 입력 생산 경로 자체를 증명하지 않는다.
- 실제 G1/VR/WSL/DDS 실행 및 제어 설정 변경 없음. 다음 IK 수정 시 producer에서 같은 원본 입력·모델·초기조건으로 두 trace를 내보내 사용한다.

## 최신: G1 없이 패킷 간격/이동량12조건 검증 완료 (2026-09-08)

- study_vr_packet_spacing.cpp 추가,MSVC /W4 /WX 실행 통과. 현재 배포 헤더 SHA256 dea4bfcf7f5f4409ff80ad02bf075fe75329cebed67c9f98500626046a6501db 일치.
- 50Hz tick,패킷50Hz/16.7Hz/불규칙20~120ms × 이동량0.05/0.2/1/3rad 총12조건. 세 스케줄 모두 고정 목표 결과 동일. 최대속도 각각0.090912/0.185005/0.415388/0.7rad/s,정착1.14/2.20/4.86/8.38초.
- 속도/가속도 상한,고정 목표 초과방지,타관절 보존,timeout 후고정/재시작금지 확인. 기존 test_vr_rate_limits 해제·방향전환·source_age 만료 검사도 통과.
- docs/VR_PACKET_SPACING_OFFLINE.md 및 logs/test_results/vr_packet_spacing_20260908.json에 조건/수치/한계 기록. 긴3rad는 소프트웨어 시험값이며 물리실행 권고 아님.
- 실제 수정 후 G1 로그는 연결 단절로 미회수. 이번엔 로컬 제한기만 실행했으며 Mink/writer/모터를 포함한 실측 검증이 아니다. 코드설정·G1 변경 없음.

## 최신: 빈 UDP 틱 가속 초기화 수정 G1 반영 완료 (2026-09-08)

- 사용자 '빨리반영' 승인으로 /home/unitree/g1_vr_07_10deg_trial_20260908/upper_target_offline.hpp 한 파일 전송 후 같은 대상 재컴파일 exit0.
- 헤더 로컬/원격 SHA256 dea4bfcf7f5f4409ff80ad02bf075fe75329cebed67c9f98500626046a6501db 일치. 새 ELF SHA256 87191a1e4ecc940997b9983b8e3893cdfebdf75eae05e5dcda5e52695be5ff39.
- 원격 빌드 로그 build_gapfix.log. 기존 source.tar.gz/SHA256SUMS는 최초 배포 이력이며 이번 헤더 수정 이후 현행 해시와 다르다.
- 배치 경로는 이미 같은 폴더이므로 추가 변경 없음. 다음 새 실행부터 수정본 사용. 실행 중인 프로그램을 자동 재시작하지 않았고 물리 실행 없음. 0.7rad/s·10deg/s²,해제/timeout 중단 유지. 실제 개선 여부는 다음 VR 기록으로 확인해야 한다.

## 최신: UDP 빈 틱 속도 초기화 수정 로컬 검증 (2026-09-08)

- UpperTargetOffline 가속 제한 모드에서 마지막 검증 목표를 유지하고 빈 틱에도 가속 상태를 누적. 기본 offline0.08 모드는 기존 빈 틱 대기 유지.
- 목표 재사용 기한은 receipt+0.25-source_age. 수신 timeout/해제/오류 latch 유지. 목표 신선도 만료시 갱신 전 중단.
- 3틱마다 패킷(약16.7Hz)에50Hz갱신 테스트:0.7rad/s 도달,가속0.174533rad/s² 이하,고정 목표 초과방지/타관절 보존/해제 latch 통과. age0.20 패킷 재사용 만료 및 재시작 금지 검사 통과. MSVC /W4 /WX.
- 사용자 시간 제약으로 핵심 수정·SDK-free 검증 우선. G1 헤더 반영·재컴파일 아직 안 함. 다음 대상은 /home/unitree/g1_vr_07_10deg_trial_20260908/upper_target_offline.hpp 한 파일과 같은 실행파일 재빌드,물리실행 없이 배포. 원격 변경 승인 필요.

## 최신: VR 저속 원인 — 빈 UDP 틱의 가속 상태 초기화 (2026-09-08)

- 사용자 저속 보고 후 읽기 전용 회수. 원격 g1_twist2_trial_1787640943683643_8834의 CSV2843행과 run/result 회수. PC vr_slow_8834.csv, vr_slow_8834_run.json, vr_slow_8834_result.json 및 vr_slow_8834_review.json.
- CSV SHA256 67ceaf2af7c185e73f70896c0f6aa0ddaaa0edf29cbdc84ae2226064712f3d0e,run해시도result와일치. input_disengaged 종료.
- udp_ready6.980..56.860초.22번 C++ desired 목표 최고0.0104764rad/s(0.600deg/s),평균절대0.0022218rad/s,목표 변화없는 틱52.85%. 따라서 실측 추종 이전에 명령 목표가 매우 느리다.
- 코드 확인: UpperTargetOffline::Tick packets.empty()에서 velocity.fill(0) 후 waiting. 새 가속 제한이 패킷이 비는 틱마다0으로 초기화된다. dt20ms,가속도0.174533에서 한 틱 속도증가0.00349066rad/s이며 관측 최고는약3배로 이 메커니즘과 부합.
- 원시 Mink 목표/수신 카운트는 CSV에 없어 정확한 수신 틱 이력이나 Mink 단계 속도까지 확정할 수는 없다. 신규 가속 제한 통합의 빈 틱 처리 문제가 핵심 수정 대상이다.
- 이번에는 진단/기록만; 제어 코드·PD·상한·G1 변경/재실행 없음. 다음 수정은 신선도 제한 안의 입력 유지와 제동 상태를 일관되게 처리하는 방식,기존 해제/timeout latch 유지,불규칙/저주기 패킷 회귀시험 추가가 필요하다. 단순 상한 증가로 해결하지 않는다.

## 최신: VR0.7rad/s·10deg/s² G1 반영 및 배치 경로 전환 (2026-09-08)

- 사용자 '반영' 승인으로 새 /home/unitree/g1_vr_07_10deg_trial_20260908 배포·aarch64 빌드 완료. 기존 폴더 보존, 물리 실행 없음.
- 소스 vr_07_10deg_source_20260908.tar.gz SHA256 fc8a02f248adf81e3902da7860f7d0b053d1ab212ead9c1ed05bd827872b9aaf. 원격 아카이브 및21개 파일 해시 모두 일치.
- G1 ELF SHA256 c8433dc45316950943db5897025e0c01c7d7302847c991720a3b5c186f784ad7. 빌드 exit0, 로그 logs/test_results/g1_vr_07_10deg_build_20260908.log 회수.
- START_TWIST2_MINK_UDP.ps1 Robot 경로를 새 폴더로 전환. 배치 진입점 그대로, 파서 및 All -Preview 검사 수행(자식 실행 없음).
- PC Mink live 프로필과 새 C++ UDP 정상 갱신은 목표속도0.7rad/s·가속도10deg/s²=0.174533rad/s². 초기 이동0.08 유지. 해제/입력없음/오류 즉시 중단·freeze 우선. 실제 관절속도·가속도 보장 또는 물리 검증 아님.
- 최신 소스의 run.json/result.json 기록 및 다관절 PD 옵션도 새 빌드에 포함. 해당 기록 기능의 실기 런타임 확인은 남아 있다. PD 자동 왕복 reference는 기존45deg/s·10rad/s²이며 VR값과 별개다.

## 최신: VR 목표0.7rad/s·10deg/s² 로컬 반영 (2026-09-08)

- 직전 배치파일 질문을 이어 VR UDP 경로에 적용. 사용자 단위는 속도rad/s, 가속도deg/s²:10deg/s²=0.1745329252rad/s². PD 자동 왕복의45deg/s·10rad/s² reference는 변경하지 않음.
- 읽은 prototype은 이미 live 속도0.7, 가속도10rad/s²였다. G1_TWIST2_KEYBOARD_RATE=1일 때 가속도만 math.radians(10)으로 변경; 다른 프로필은 현재 값 보존.
- UpperTargetOffline에 선택적 속도/가속도 제한 추가. 기존 기본0.08/가속도제한없음 유지. 새 C++ UDP 모드만 MinkUdpTarget live 옵션으로0.7/0.174533 사용. 초기 두팔 이동0.08 및 PD 준비 경로 유지.
- 이산 제동 여유를 둔 속도 갱신. 고정 목표 초과 방지/방향 전환/가속도·속도/타관절 유지/해제 latch 시험 통과. 갑자기 이동한 목표는 감속 중 지나칠 수 있으며 기존 관절범위 검사 유지. 입력없음은 즉시 freeze,오류·해제는중단 우선으로 정상 갱신 가속도 제한의 예외.
- Python 문법·live 상수 검사,SDK-free MSVC /W4 /WX 새 제한 시험 및 기존 MinkUdpTarget 회귀시험 통과. PC WSL SDK 빌드/링크 exit0: logs/test_results/vr_07_accel10deg_build_20260908.log. 물리 검증 아님.
- START_TWIST2_MINK_UDP.ps1 Check 안내에 로컬 입력값과 기존 G1 경로0.08 잔존을 명시. Robot 경로는 아직 /home/unitree/g1_mink_udp_trial_20260908이며 새 제한 버전 배포·경로 전환 필요. G1 접속/변경/실행 없음. 현재 배치 전체가 새값으로 반영됐다고 해석하지 않는다.

## 최신: 실측 기반 오프라인 모델용 기록 기반 추가 (2026-09-08)

- 목표는 실측 데이터로 모델을 보정하고 별도 세션으로 예측을 검증하는 것. 현재는 provenance/조건/기본 품질 검사 구현 단계이며 식별 모델 완성 아님.
- 로컬 새 C++: handoff 전 run.json에 실제 실행파일/정책 해시,argv,전체 PD,초기 캡처각,reference 계수·시간표 저장. /proc/self/exe는 현재 C++ 프로세스에서 read_symlink 후 해시 계산한다(자식 sha256sum 자신의 exe를 해시하지 않음).
- controller.finish 및 CSV Finish 후 result.json에 종료 사유/왕복 완료/CSV와run 해시/행 수 저장. 강제 종료 또는 저장 실패 때 결과 파일 부재 가능하며 정상 완료로 해석하지 않는다. metadata 파일 I/O는 제어 루프 밖.
- audit_identification_run.py 및 test_identification_audit.py: 해시/유효 writer PD·유한값·시간 역행/중복·건너뜀/표본 간격/phase 존재/조건 누락 검사. 기본 검사 통과는 식별가능성/센서 정확도/물리 안전성 판정이 아님.
- Python 합성 기록 테스트 통과(ResourceWarning 오류 처리 포함). PC WSL SDK 빌드/링크 exit0: logs/test_results/pd_dataset_manifest_build_20260908.log. 실제 metadata 출력은 G1에서 아직 검증하지 않음.
- docs/SYSTEM_IDENTIFICATION_DATA.md에 context.json 양식과 감사 명령,세션 단위 train/validation/test 분리,50Hz 한계 및 이후 모델 보정 조건 기록.
- G1 전송/재실행 없음. 최신 배포 다관절 옵션 버전에는 새 기록 기능이 아직 없다. 다음 배포 시 재포장/빌드 필요. 500Hz 전체 기록·저장부하 검증,조건별 반복 데이터 확보,모델 식별 및 독립 검증은 남음. 기존 중단 CSV는 수동 provenance로 보존하며 자동 run/result를 사후 조작하지 않는다.

## 최신: 다관절 PD 옵션 G1 배포·빌드 완료 (2026-09-08)

- 사용자 '배포' 승인으로 새 /home/unitree/g1_pd_multi_trial_20260908 폴더에만 전송·해제·컴파일. 기존 버전 보존, 물리 프로그램 미실행.
- 소스 logs/test_results/pd_multi_gains_source_20260908.tar.gz SHA256 a8eaa358d85881f27f6f6e1930cd838973a79b9e6e163778fab835da81328710. 원격 아카이브 및21개 manifest 파일 모두 해시 일치.
- 기존 SDK/Torch/ABI1로 G1 aarch64 빌드/링크 exit0. ELF SHA256 1a39d6fb35e7e22dfa53e587c4e5c6845aa38ffe9eb8eb0566ed1ed17f650665. 빌드 로그 회수: logs/test_results/g1_pd_multi_build_20260908.log.
- 새 실행파일에서 --pd-gain 22:48:5 같은 옵션을 반복해22..28 다관절 지정 가능. 미지정 기본값/기존 shoulder 별칭 지원. 값만 바꿀 때 재빌드 불필요. 입력 범위는 검증된 안전 PD 범위가 아니다.
- docs/PD_REACH_TRIAL.md의 경로·배포 상태 갱신. 물리 시험 및 후보 성능 검증은 아직 하지 않았다.

## 최신: 오른팔 다관절 PD 실행 옵션 확장 (2026-09-08)

- pd_gain_options.hpp에서 --pd-gain joint:Kp:Kd 반복 지원. 오른팔22..28만 허용, 미지정 관절은 기본 배열 유지. 기존 --right-shoulder-kp/kd 별칭 유지.
- 같은 관절 중복,22번 별칭과 중복(양방향),번호 범위/형식 오류,비유한값,값 누락,UDP 사용은 거부한다. 실행 중 const 배열, 표시/CSV/토크 제한은 기존 실행 옵션 경로를 그대로 사용한다.
- test_pd_gain_options.cpp에 다관절 적용/나머지 보존 및 잘못된 입력·충돌 검사 추가. MSVC /W4 /WX 통과. PC WSL 대상 빌드/링크 exit0: logs/test_results/pd_multi_gains_build_20260908.log. 기존 Torch 경고 있음.
- docs/PD_REACH_TRIAL.md 예제 갱신. G1 전송/실행 없음. 기존 pd_runtime_gains_source_20260908.tar.gz는 단일22번 옵션 버전이므로 최신 다관절 배포 시 재포장해야 한다.

## 최신: PD 실행 옵션 구현·로컬 빌드 완료 (2026-09-08)

- 사용자 요청에 따라 Kp/Kd마다 재빌드하는 방식을 변경. --pd-reach-trial 뒤 --right-shoulder-kp / --right-shoulder-kd 옵션으로22번만 지정. 생략 시 빌드 기준값(현재40/5), 다른 관절은 원래 배열 그대로.
- pd_gain_options.hpp 파싱은 Policy/Controller 생성 전. 유한값/전체 숫자 소비/중복·누락·알 수 없는 옵션/UDP 사용 거부. 입력 범위 Kp1..100/Kd0.1..20은 소프트웨어 범위로, 실기 검증 범위가 아니다.
- Controller의 const PD 배열로 실행 중 고정. 실제 motor.kp/kd와 토크 제한·예측 모두 같은 배열 사용. 시작 전 전체 오른팔 표시 및 기존 writer CSV는 실제 적용 PD 기록.
- SDK-free test_pd_gain_options.cpp MSVC /W4 /WX 통과. PC WSL SDK 빌드/링크 exit0(logs/test_results/pd_runtime_gains_build_20260908.log); 실행파일 미실행.
- logs/test_results/pd_runtime_gains_source_20260908.tar.gz 소스 패키지 준비, 아카이브 재읽기 검증. 기존40/5 소스·G1 실행파일 보존. G1에 새 옵션 버전은 아직 전송/빌드하지 않았다.
- 다음은 새 /home/unitree/g1_pd_runtime_trial_20260908 폴더에 옵션 버전을 한 번 전송·컴파일하는 단계. 이후 지원 범위 내 PD 변경은 실행 옵션만 바꾸며 재빌드 불필요. 물리 실행 승인은 별도.

## 최신: Kp48/Kd5 별도 소스 패키지 준비·PC 빌드 완료 (2026-09-08)

- logs/test_results/pd_kp48_kd5_source_20260908.tar.gz 준비. SHA256 06d8b9c91a36fab43aa05316e8dc5283f0cf053ace6fbae83e41ee56560df88d.
- 배포했던40/5 패키지와 바이트 비교: twist2_common.hpp의22번 Kp40→48만 다름. Kd 및 다른 관절/속도/가속도/정착/중단/CSV 코드 동일. 공용 원본 헤더와 기존40/5 패키지는 변경하지 않음.
- SHA256SUMS는 LF, tar mtime0으로 이전 CRLF/미래시각 문제 방지. 아카이브 재읽기 해시 검사 통과. pd_kp48_package_check_20260908.json에 기록.
- 별도 PC WSL /home/user/pd-kp48-package-check-20260908 빌드/링크 exit0. 로그 pd_kp48_package_build_20260908.log. 실행파일 실행 없음.
- 다음 승인 대상: G1 새 /home/unitree/g1_pd_kp48_kd5_trial_20260908 폴더에 전송·컴파일만 수행, 기존 폴더 있으면 중단. 물리 실행은 포함하지 않음. 현재 G1 변경/재실행 없음.

## 최신: 오른쪽22번 PD 항 분리 및 Kd5 고정 비교 제안 (2026-09-08)

- review_pd_terms.py로 첫 전진 writer 유효·중복제거84표본 분석. 부호/동일 상태 후보 계산/비유한값 거부 검사 통과. 출력 logs/test_results/g1_pd_kd5_terms_20260908.json.
- 마지막 표본 P=-9.2894Nm, D=+3.5512Nm, FF=0, 합=-5.73825Nm; tau_est=-5.5Nm. D는 이동을 감쇠한다. 중력/관성/마찰 기여는 이 기록만으로 분리하지 않았다.
- writer 명령 생성→write 반환 나이 최고21.93965ms, state 수신→writer cycle 시작 최고1.71942ms. 이는 소프트웨어 내 시각 차이이며 실제 모터 응답 지연 추정값이 아니다.
- 같은 상태에서22번 Kp48/Kd5 대입 시 합=-7.59613Nm. 제한기 반응/실제 궤적/안정성 예측 또는 최적값 판정이 아닌 대수 계산이다.
- logs/test_results/pd_joint22_kp48_kd5_proposal_20260908.json: 기준40/5와 후보48/5만 포함. 다른28관절 Kp 및 전체 Kd 동일 검증. 후보 비교 제안일 뿐 헤더/로봇 PD 실제 변경 없음.
- 다음 실기 비교 후보는 오른쪽 어깨 pitch22번 Kp만48, Kd5 유지. 적용 전 별도 소스/빌드 준비와 원격 변경 승인 필요. 기준 실행은 미완료이므로 정상 완료 후보로 순위화하지 않는다. 속도45도/s·가속도10rad/s²·중단 한계는 그대로.

## 최신: Kp40/Kd5 첫 실기 전진 추종오차 중단 및 CSV 회수 (2026-09-08)

- 사용자 수동 P 실행. 종료 메시지 upper measured tracking error exceeded 0.25 rad. 사용자 현재 안정적·AI 수동 복귀 완료 확인. 재실행/PD 변경/한계 완화 없음.
- 원격 g1_twist2_trial_1787637987923801_4059/policy.csv를 logs/test_results/g1_pd_kd5_1787637987923801_4059.csv로 회수. 537행, SHA256 d7782873b18682de4288fc9805be16b55e733689ec875dc6dcab407d0d12c626.
- 계산 결과 logs/test_results/g1_pd_kd5_stopped_review_20260908.json. pd_settling 7.000..8.020초, 시작대기8.040..9.040초, 첫 전진9.060..10.740초 기록. 복귀/3왕복 완료 없음; 정상 PD 후보 평가에서 제외.
- 전진 표본 최대 오른쪽22번 policy 목표-실측 오차0.249181rad(14.28도), writer 목표-동일 프레임 실측0.232235rad(13.31도). 다음 목표를 검사하는 policy 보호와 이미 송신한 writer 프레임의 오차를 구분해야 한다. 오류를 던진 다음 policy 표본은 기록되지 않아 정확한 초과 순간/관절은 직접 확인 불가.
- 마지막22번 writer q=-0.442901, target=-0.675136, dq=-0.710233rad/s, kp40/kd5, target_dq0. 이때 D항 -Kd*dq=+3.551Nm로 음의 방향 이동을 감쇠한다. 이것만으로 Kd가 원인이라고 확정하거나 최적값을 산정할 수 없다.
- 실측 속도는 목표 속도 제한과 다름: 전진 writer 표본 손목26번 최고1.01243rad/s. 45도/s는 목표 제한이며 실제 속도의 절대 보장이 아님.
- 다음 보정 검토는 동일 궤적에서 PD 영향 및 명령/실측 시간 정렬을 구분하는 것. 중단 한계를 임의로 높이거나 미완료 시험으로 최적 PD를 선정하지 않는다. CSV 존재/회수는 이번에 실제 확인됨.

## 최신: 사용자 준비 확인 후 수동 P 시험 창 열기 (2026-09-08)

- 사용자가 물리3왕복 실행에 '진행', 현재 AI/지지/R1 담당 준비 질문에 '응'으로 확인했다.
- SSH 읽기 점검에서 알려진 g1_twist2/gate7_live/g1_right_arm_jog 제어 프로세스는 검색되지 않았다(조회 bash 자체만 출력). 모든 DDS 송신자 부재를 증명하는 검사는 아니다. 배포 ELF SHA256 338f2d3ead7b9cdc8b446c7e6abd5086a446e2f3a29c9bdbe1b4d5c958395ac0 재확인.
- 사용자에게 보이는 PowerShell 창을 열어 새 폴더의 --pd-reach-trial SSH 실행을 요청했다. 사용자가 로그인·수동 P 입력하도록 안내하며 자동 P 입력은 하지 않았다.
- 현재 도구 확인 범위는 로컬 창 생성까지. 원격 프로그램 시작/P 입력/물리 왕복 완료 여부는 아직 확인하지 않았다. 종료 후 CSV 회수·중단 사유·실측 평가가 다음 항목이다.

## 최신: 기준 PD 실기 직전 검토 (2026-09-08)

- 초기 두팔 목표 이동은 실측 캡처에서 고정 Mink ready로 관절별0.08rad/s, 이후 새 정착 gate를 통과하면 자동3왕복. 초기 경로의 실시간 충돌 판정은 없으므로 이 검토를 초기 충돌 안전성 검증으로 표현하지 않는다.
- CSV 생성/경로 출력, 정착 gate, 기존 중단 경로를 현재 코드에서 재확인. docs/PD_REACH_TRIAL.md의 배포 미완료 문구를 실제 G1 빌드 완료 상태로 수정했다.
- 직전 승인은 전송·컴파일만 해당했다. 물리 시험 실행 전 현재 지지·AI 자세 유지·R1 담당 준비와 구체적 자동3왕복 실행 의사를 확인해야 한다. 아직 프로그램 실행 없음.

## 최신: 승인된 G1 별도 폴더 전송·컴파일 완료 (2026-09-08)

- 사용자 '진행'으로 직전 제안의 전송·컴파일만 승인. /home/unitree/g1_pd_kd5_trial_20260908 부재 확인 후 mkdir, 소스 전송·해제·빌드 수행. 원본 키보드 및 기존 UDP 폴더는 수정하지 않았다.
- aarch64, 기존 /home/unitree/unitree_sdk2-main 및 /home/unitree/.local/lib/python3.8/site-packages/torch, torch.compiled_with_cxx11_abi()=True 확인. 새 패키지 설치 없음.
- source.tar.gz SHA256 7d6a6a3f3c700d479a74f781e950dc0be67c6a1fc2ca79254710017c6ea6b89d 일치. SHA256SUMS의 CRLF는 tr -d '\r' 스트림으로 읽어 20개 파일 모두 OK. 소스 내용 변경 없음.
- PC/G1 날짜 차이로 tar 미래 시각 경고 발생. 새 시험 폴더 파일만 touch하여 빌드 시각 정리; 시스템 시계 변경 없음.
- cmake 빌드/링크 exit0. /home/unitree/g1_pd_kd5_trial_20260908/build/g1_twist2_mink_udp_trial: ARM aarch64 ELF, SHA256 338f2d3ead7b9cdc8b446c7e6abd5086a446e2f3a29c9bdbe1b4d5c958395ac0.
- 빌드 로그 PC 회수: logs/test_results/g1_pd_kd5_build_20260908.log. 실행파일은 실행하지 않았으며 publisher 생성/모드 변경/모터 출력 없음.
- 실측 초기→준비 경로 검토, 새 정착 조건 실측, 물리 왕복 CSV 확보 및 PD 후보 보정은 남아 있다. 이 빌드는 물리 시험 완료 또는 안전성 검증이 아니다.

## 최신: Kd5 PD 시험 소스 패키지 독립 빌드 완료 (2026-09-08)

- 소스 전용 패키지: logs/test_results/pd_kd5_source_20260908_v2.tar.gz. C++ 및 재귀 로컬 헤더, 해당 대상만 있는 CMakeLists.txt, BUILD_ONLY.txt 총20개와 SHA256SUMS 포함. SDK/정책/실행파일은 포함하지 않는다.
- SHA256: 7d6a6a3f3c700d479a74f781e950dc0be67c6a1fc2ca79254710017c6ea6b89d. 아카이브에서 모든 manifest 파일을 재읽어 해시 일치 확인.
- 최초 pd_kd5_source_20260908 폴더는 vendor/json.hpp 상대경로 처리 중 중단된 불완전 산출물이며 배포 대상이 아니다. v2는 vendor 경로를 보존한다.
- v2 소스만 사용한 별도 PC WSL /home/user/pd-kd5-package-check-20260908 빌드/링크 exit0. logs/test_results/pd_package_build_20260908.log. 기존 Torch 및 미사용 함수 경고 있음. 실행파일 미실행.
- 다음 제안은 G1의 새 /home/unitree/g1_pd_kd5_trial_20260908 폴더에만 전송·해제·빌드하는 것. 기존 폴더가 있으면 덮어쓰지 않고 중단한다. 기존 SDK/Torch 위치·ABI 확인 후 빌드하며 패키지 설치나 모터 프로그램 실행은 포함하지 않는다.
- G1 작업은 아직 미승인/미수행. 원본 키보드 경로 및 기존 UDP 시험 경로를 보존한다. 실측 초기 이동 경로 검토·정착 기준 확인·물리 왕복 시험은 별도 남은 작업이다.

## 최신: PD 시험 전 실측 양팔 정착 대기 추가 (2026-09-08)

- pd_ready_settle.hpp 및 새 C++ PD 모드: 준비 목표 완성 후 pd_settling에서 양팔15..28의 목표 오차<=0.10rad·실측 속도<=0.10rad/s가 새 수신 표본 기준1초 연속 유지돼야 왕복 시작. Kp40/Kd5 및 손목20/1, 궤적45도/s·10rad/s²는 그대로다.
- 이 한계는 아직 실기 검증 전 로컬 초기값이다. 하체·허리는 팔 정착 검사에서 제외하며 기존 전신 보호/R1/P/Select/B/p 경로는 유지한다.
- 조건 위반/수신 간격>60ms는 연속 구간 재시작, 중복 수신은 누적하지 않음. 표본 나이>60ms·시계 역행·비유한값·10초 대기 초과는 예외로 기존 damping 경로에 전달. 오류 후 gate는 재사용 불가.
- test_pd_ready_settle.cpp: 연속 대기, 왼팔 속도/오른팔 오차, 하체 제외, 중복/오래된 표본, 간격, timeout, 시계, 비유한값 및 오류 latch 검사 MSVC /W4 /WX 통과.
- PC WSL SDK 빌드/링크 exit0. logs/test_results/pd_settle_build_20260908.log; 기존 Torch 헤더 경고 있음. 명령 가능한 실행파일은 실행하지 않았다.
- 원본 키보드 C++ SHA256 E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F 유지. G1 접속/배포/실행/publisher 생성 없음.
- 남은 항목: 실측 초기→준비 경로 검토, G1용 빌드·배포, 정착 조건 실측 및 기준 PD 왕복 CSV 확보. 정착 gate 추가는 초기 이동 경로의 충돌 검증을 대신하지 않는다.

## 최신: Kd5 PD 시험 대상 빌드 및 시작 안내 확인 (2026-09-08)

- 새 twist2_mink_udp_trial.cpp의 PD 모드는 P 확인 전에 오른팔22..28 Kp/Kd, reference 편도 시간 및 준비 목표 완료 후 자동 시작됨을 표시한다. 실제 정착 확인과 목표 완료를 구분했다.
- 현재 로컬 Kp40/Kd5(어깨·팔꿈치), Kp20/Kd1(손목) 및 편도1.994초 reference로 PC WSL SDK 대상 빌드/링크 exit0. 로그: logs/test_results/pd_kd5_build_20260908.log. 기존 Torch 헤더 경고가 있으며 실행파일은 실행하지 않았다.
- PD 평가4개·시간표5개 테스트 통과. docs/PD_REACH_TRIAL.md를 현재 값·실행 동작·기록 방식으로 정리해 이전2초 기준 혼재를 제거했다.
- 원본 키보드 C++는 보존. G1 접속·배포·실행·publisher 생성 없음. PC 빌드는 G1용 aarch64 배포를 대체하지 않는다.
- 다음 필수 항목: 실측 초기→준비 구간/정착 처리 검토, G1용 별도 시험 빌드·배포, 기준 PD의 동일 왕복 실측 기록. 후보 평가 한계값 및 완료 메타데이터 확보도 남아 있다. 현재 결과는 물리 안전성 검증이 아니다.

## 최신: Kd 5 기준으로 PD 비교 초안 갱신 (2026-09-08)

- 사용자 요청: Kd 5. 재확인한 로컬 twist2_common.hpp는 이미 양팔 어깨·팔꿈치 Kp40/Kd5, 손목 Kp20/Kd1이었다. 해당 값을 보존했으며 하체·허리 값은 변경하지 않았다.
- pd_gain_comparison.py 및 test_pd_gain_comparison.py: 로컬 헤더에서 후보를 생성하고, 동일 궤적·완료 기록·CSV 해시·실제 기록된 전체 관절 PD 일치 여부를 검사하는 오프라인 평가 도구. 이동 구간 시간 가중 RMS 오차, 최대 오차·추정 토크·정지 구간 속도 RMS를 산출한다.
- logs/test_results/pd_gain_plan_joint22_20260908.json을 현재 기준으로 재생성: 오른쪽 22번 관절만 Kp32/40/48 × Kd4/5/6 후보 9개. 다른 관절은 고정. 후보는 실행 설정이 아니며 기준값은 Kp40/Kd5이다.
- 최고45도/s, 최대10rad/s², 편도1.994초의 동일 reference를 PD 비교에 고정. 가속도는 보정 대상이 아니다.
- 오프라인 단위 테스트 4개 통과. 평가 한계값은 아직 null이며, 실측 완료 CSV와 실행 메타데이터 확보 및 평가 한계 설정이 남아 있다. 실제 PD 보정 결과나 로봇 안전성 검증이 아니다.
- 이번에는 G1 전송·컴파일·실행 및 물리 출력 없음. G1의 현재 PD 값은 재확인하지 않았다.

## 최신: 보정 대상은 PD, 속도·가속도는 고정 비교 조건 (2026-09-08)

- 사용자 재확인: 보정 대상은 최대가속도가 아니라 관절별 Kp/Kd.
  최고45도/s·최대10rad/s²와 동일 궤적을 고정하고 PD 후보만 변경해 비교한다.
  추종오차를 줄이려고 후보마다 시간/가속도/경로를 바꾸지 않는다.
- 이번에는 직전 요청의 고정2초 제거만 마무리: choose_timing이 같은 경로/제한에서
  2ms 간격 후보를 검사해 허용되는 첫 시간을 선택. 연속시간 전역최적 증명 아님.
  63후보 후 편도1.994초, 최고44.9575도/s·가속도9.924rad/s².
  이 산출물을 이후 PD 비교의 공통 기준으로 고정. PD 값은 아직 변경하지 않음.
- pd_reach_limits_selected_20260908/report.json 및 reference 갱신.
  Python5개 및 SDK-free MSVC /W4 /WX 왕복 테스트 통과.
  이번 수정 후 전체 SDK 대상 재빌드/G1 배포·실행은 안 함.
- 다음 작업은 PD 후보별 동일 궤적의 기록·평가 구성. 실기 검토/데이터 확보 필요사항은 그대로.

## 최신 사용자 정정: 편도2초는 필수 조건 아님 (2026-09-08)

- 사용자는 편도2초를 꼭 지키려던 것이 아니라 임의의 최대각가속도 기준값을 정하려던 것이라고 정정.
- 최고45도/s와 가속도10rad/s²를 우선 시험할 기준값으로 이해. 10은 최적값/검증된 안전값 아님.
- 이동시간은 속도·가속도와 경로에 따른 결과로 취급하며2초를 맞추기 위해 가속도를 높이지 않는다.
- 이번에는 문서만 정정. 생성기/C++ reference의 기존2초 궤적 및 G1 설정은 변경하지 않음.

## 최신: 반복 궤적 최대 각가속도10rad/s² 확정 (2026-09-08)

- 사용자 요청에 따라 새 반복 시험 기준을 최고45도/s, 최대가속도10rad/s², 편도2초로 명시.
- pd_reach_timing.py MAX_ACCELERATION_RAD_S2=10 및 초과/비유한값 거부 검사 추가.
  생성기는 검사 실패 시 C++ reference 헤더를 출력하지 않는다. reference에 같은 상수 포함.
- 재생성 결과 pd_reach_2s_accel10_20260908/report.json: 최고44.962도/s,
  가속도9.464rad/s², 편도2초 유지. 경로/시간표는 이전과 같고 제한을 명문화한 변경.
- Python4개(10 경계 허용/초과 거부 포함), MSVC /W4 /WX C++왕복시험 통과.
  제한은 시험 목표 궤적 생성/검증에 적용하며 모든 실제 관절가속도나 damping을 보장하지 않음.
- G1배포/실행 없음. live Mink 가속도.32 및 속도.08은 그대로. PD 변경 없음.

## 최신: 최고45도/s 유지하면서 편도2초 시간 배분 (2026-09-08)

- 사용자 최고각속도45도/s 재확인 및 시간배분 변경 승인. 경로는 그대로 유지.
- pd_reach_timing.py: 경로의 max_i|dq_i/du| 적분으로 진행 거리 정의,
  cosine 가감속/등속 진행으로 시간배분. 속도제한만 고려한 하한1.86733초.
  편도2초를 위해 끝점 가감속 각각.13017초. 별도 가속도 상한 없이 계산값 공개.
- 최초 내부44.98도/s 표는 Hermite보간에서45.00586도로 초과하여 채택하지 않음.
  보간 여유를 둔 최종표는 최고44.962도/s, 가속도9.464rad/s².
  결과 logs/test_results/pd_reach_2s_45_final_20260908/report.json 및 reach_return.csv.
  243지정충돌쌍 최소40.30mm/동일 경로/관절범위 샘플검사 통과. 물리검증 아님.
- pd_reach_reference.hpp에 경로계수+시간표/기울기 포함, C++ 동일Hermite보간.
  복귀는 u=1-u가 아니라 시간표 역방향 평가(비대칭 경로이므로 구분 필수).
  3회 시험19초, capture/blend/ready이동 시간 별도. 목표dq0/PD/기존live .08 변경없음.
- MSVC /W4 /WX 및 C++ 3회왕복/구간/다른관절/중단/초기불일치/정확한역경로 확인.
  C++ 최고.784351rad/s, 가속도9.46061. Python시간배분3개 테스트 통과.
  WSL실험C++ 빌드링크 exit0(Torch경고). 로그 pd_reach_2s_build_20260908.log.
  원본SHA E61D8A3C...CC09F 유지. G1 배포/실행 없음.
- 실제 G1의45도/s 추종/토크여유/초기접촉/하체영향/기록타이밍 검증은 남음.
  2초는 목표 궤적 시간이며 실측 완료 보장이 아니다. docs/PD_REACH_TRIAL.md 갱신.

## 최신: 전체 팔 뻗기/복귀 및 목표45도/s 도달 기준 (2026-09-08)

- 사용자 단일관절10도시험 대신 전체팔뻗기 승인. 이후 최고15도/s는 부족하고45도/s
  도달이 필요하다고 명시. 따라서 임시 .32rad/s² 가정을 이번 시험 궤적에서 대체.
- plan_pd_reach_offline.py: 가상 ready에서 어깨높이/팔꿈치20도 도달 task pose로
  Mink80구간 IK. 직선은u=.388 부근 수렴실패, 전방8cm 볼록한 곡선으로 수렴.
  끝점 고정 다항식 근사 및5차 시간함수 적용. 전체 경로 역재생으로 정확한복귀.
- 최종 logs/test_results/pd_reach_45_actual_20260908: 최고44.976도/s, 편도3.402초,
  가속도2.752rad/s², 시작대기포함3회27.412초(초기자세 이동 별도).
  손목전방27.37cm/위32.01cm/안쪽10.10cm. elbow최종19.99도.
  243지정충돌쌍 최소40.30mm, 근사 task오차1.25mm/.373도. 샘플기구학확인만 통과.
- pd_reach_reference.hpp / pd_reach_trial.hpp 추가. 새 --pd-reach-trial이 기존단일어깨
  모드를 대체. 기존 두팔 ready이동 후 이 경로3회, UDP 생성없음, PD/dq0/R1보호유지.
  live Mink .08 및 기존 PD 변경없음. 목표속도 도달이며 실측속도45도/s 확인은 아님.
- C++ SDK-free 전체왕복/다른관절/단계/속도/가속도/중단/초기불일치 테스트 통과.
  최고.784978rad/s, 가속도2.75199. MSVC /W4 /WX, WSL빌드링크 exit0.
  로그 pd_reach_45_build_20260908.log. G1배포/실행 없음.
- docs/PD_REACH_TRIAL.md가 최신시험기준. 오래된 PD_TRIAL_OFFLINE의10도/.32는예비도구.
  남음: 초기실측→ready 경로/접촉/하체정책/실기기록타이밍 검토, 배포, 실제추종,
  PC로그회수 및PD후보비교. 이번에 물리안전성을 검증했다고 표현하지 않는다.

## 최신: C++ 반복 궤적 모드와 명령 구간 기록 로컬 구현 (2026-09-08)

- 새 실험 실행파일에 --pd-right-shoulder-trial 모드 추가. 기존 --udp-right-arm과
  하나만 선택하는 argc/인자 검사를 사용. PD 모드에서는 NativeVrUdp 생성/수신 없음.
  기존 배치 기본은 UDP 그대로. G1 배포/실행 없음.
- pd_joint_trial.hpp: 캡처한 상체 목표 유지, 하체 blend 완료 후 시작대기1초,
  오른팔22 shoulder pitch +10도/끝점대기1초/복귀/대기1초, 3회 반복.
  5차 궤적, 상한45도/s/.32rad/s². 편도1.77453초/최고10.56618도/s.
  시험구간17.64718초 후 planned damping, 전체는 capture/blend 포함 약22.65초.
  시작/끝점 soft joint 범위 사전 검사, 나머지 상체 관절 목표 고정.
- P/R1/Select/B/키p 및 기존 측정 속도·추종오차/토크/시간 보호 유지.
  PD/목표dq=0 유지. PD trial 완료 reason=pd trial completed. AI 자동복귀 없음.
  관절 한계 검사는 충돌 검사 아님. 캡처 자세에서의 몸/팔 접촉 경로 검토 미완료.
- Desired의 trial_phase/cycle을 writer 프레임에 복사. CSV writer_trial_phase/cycle은
  최종 명령과 동일 프레임에 속함. phase 0=비시험,1=시작대기,2=전진,3=끝점대기,
  4=복귀,5=시작점대기. 6=완료는 제어 루프 중단 이벤트이며 평가 명령으로 송신하지 않음.
- 평가기 --reference writer --writer-trial-phase 2 등으로 정책 행 phase와 무관하게
  명령의 시험 구간을 선택. damping은 Kp=0으로 제외.
- SDK-free C++ 왕복/위치·속도·가속도/구간/다른관절보존/범위/중단·시간latch 통과.
  writer 동시성1만회 및 CSV241개 추가컬럼 검사 통과. Python5개 통과.
  MSVC /W4 /WX 통과, WSL C++ 빌드·링크 exit0(Torch 헤더 경고).
  로그 pd_trial_mode_build_20260908.log. 기존 원본 SHA E61D8A3C...CC09F 유지.
- 남음: 충돌경로 검토, 로깅 포함 실기 타이밍/반복 기준 측정, PC회수, PD 후보 비교.
  실제 PD 자동탐색 또는 실기 검증 완료 아님. 다음 배포에는 pd_joint_trial.hpp 추가 필요.

## 최신: writer 명령·상태 쌍 기록 로컬 구현 (2026-09-08)

- writer_frame.hpp 추가. 최종 제한 후 LowCmd q/dq/kp/kd/tau와 해당 write_cycle에서 사용한
  LowState q/dq/tau_est/tick을 같은 고정 크기 프레임으로 보관. 기존 정책 q/target과 구분.
  상태 도착/루프 시작/Write 반환/desired 생성의 steady clock 시각 및 고유 sequence 기록.
- publisher Write 반환 후 프레임 게시. 기기 수신 ACK 또는 후속 측정 응답을 의미하지 않는다.
  snapshot 시점상 상태 수신 시각은 루프 시작보다 늦을 수 있으며 Write 반환 이전이어야 한다.
- CSV에 writer_* 컬럼 추가. 약50Hz 정책 로거가 최신500Hz 프레임을 샘플링한다.
  전체500Hz 기록이 아니며 sequence가 건너뛰거나 중복될 수 있다. phase는 정책 행의 값으로
  프레임과 동일 시점 보장 없음. active VR/idle 구분 및 지연 분석용 전체 기록은 아직 미구현.
- pd_trial_offline.py review --reference writer: 같은 프레임 q/target 오차 사용,
  중복sequence와 오른팔 Kp=0(damping) 제외. 시간순서/유한값 검사. PD 최적 점수는 아님.
- test_writer_frame.cpp: 동시 게시/읽기1만 회 일관성, 초기 무효, CSV239개 추가 컬럼 통과.
  MSVC /W4 /WX 성공. Python 평가/궤적 테스트5개 통과. WSL C++ 빌드·링크 exit0,
  Torch 헤더 경고 있음. 로그 writer_frame_build_20260908.log.
- 기존 키보드 원본 SHA E61D8A3C...CC09F 유지. PD/속도/출력 명령 계산 변경 없음.
  G1 배포/모터 실행 안 함. 배포 시 periodic_csv.hpp와 writer_frame.hpp 모두 포함 필요.
- 남음: active/시험 구간 식별, PC 회수, C++ 반복 궤적 모드, 실기 타이밍 영향 검증,
  충돌 검토/기준 반복시험/PD 후보 비교. 전체 PD 시험 기능 완료로 표현하지 않음.

## 최신: 정책 CSV 주기 저장 로컬 구현 (2026-09-08)

- 새 실험 C++만 수정. periodic_csv.hpp의 별도 기록 스레드에 Sample 복사본을 넘긴다.
  500Hz writer에서 디스크 I/O를 하지 않으며, 50Hz 정책 루프에서 큐에 추가한다.
- AI handoff 전에 고유 디렉터리/CSV를 생성하고 헤더를 flush, 경로를 출력한다.
  경로: 현재 작업 폴더/g1_twist2_trial_<microseconds>_<pid>/policy.csv.
  약250ms 주기 flush 및 Finish에서 남은 큐/flush/close 완료 검사.
  std::ostream flush는 OS 전원손실 내구성 보장이 아님. 디스크 정체 시 주기를 보장하지 않음.
- 큐 상한250개. overflow 또는 기록 실패는 latch되어 다음 Append에서 기존 중단 경로로 전달.
  종료 시 Finish도 실패를 보고한다. 기존 CSV 컬럼/표본 의미는 유지.
- test_periodic_csv.cpp: 주기 저장 중 읽기/최종 drain/생성·쓰기 실패/큐 초과 latch 통과.
  MSVC /W4 /WX 통과, WSL 실험 C++ 빌드·링크 exit0(Torch 헤더 경고 있음).
  로그 logs/test_results/periodic_csv_build_20260908.log.
- 기존 키보드 원본 SHA E61D8A3C...CC09F 동일. PD/속도/R1 보호 변경 없음.
  G1 전송·컴파일·로봇 실행 안 함. 향후 배포 시 새 periodic_csv.hpp도 포함해야 함.
- 남음: 동기화된 최종 송신 목표/active 상태 기록, PC 회수, C++ 반복 시험 모드,
  충돌 검토/기준 실측/PD 탐색. CSV 주기 저장만 완료됐으며 전체 시험 기능은 미완성.

## 최신: PD 반복 시험 오프라인 준비 (2026-09-08)

- 사용자 "진행해보자"에 따라 먼저 로컬 오프라인 궤적·평가 도구 구현.
  최대45도/s 상한, 가속도는 기존 .32rad/s²를 유지한다는 가정으로 진행한다고 안내.
  실제 G1 속도/PD/C++ 및 G1 파일 변경·실행 없음.
- pd_trial_offline.py: 5차 왕복 상대 궤적 생성 및 기존 CSV 관절22..28 기초 오차 평가.
  test_pd_trial_offline.py 4개 통과. pd_quintic_45deg_032_preview.csv 생성.
  10도 편도1.77453초/최고10.56618도/s/가속도.32/왕복3회16.64718초.
  속도 상한45도/s에 실제 도달한 시험으로 표현하지 않는다.
- 기존 desired_target은 writer 제한 전 값, udp_ready는 active/idle 혼합일 수 있음.
  평가기는 이를 명시하며 최종 송신각 추종 점수나 PD 최적값으로 표현하지 않는다.
- docs/PD_TRIAL_OFFLINE.md 사용법/한계/후속 항목 기록.
  남음: CSV 주기 저장·쓰기 확인/회수 및 동기화된 최종 명령 기록, C++ 시험 모드,
  관절 범위·충돌 검사, 실기 기준 측정, PD 후보 탐색. 이번 작업은 그 전체 완료가 아님.

## 최신: 수정 후 사용자 실기 추종 확인 및 해제 종료 로그 (2026-09-08)

- 사용자 "됐다/확인됐어": Quest 손 움직임에 실제 오른팔 추종을 확인한 것으로 대화상 이해.
  후속 제공 콘솔 로그는 preflight 통과, policy_steps=1718, 34초 udp_ready 뒤
  RuntimeError: input_disengaged 종료. 이번 로그에는 invalid_clock 재발 없음.
- 코드상 input_disengaged는 입력 mode가 active가 아니거나 right_arm.active=false일 때 발생.
  의도적 pinch인지 다른 비활성 전환인지는 이 종료 요약만으로 구별 불가.
  status=safety_stop은 현재 코드의 해제 종료 분류이며 자체로 새 하드웨어 fault를 뜻하지 않음.
- 사용자 제공 수치: 오른팔 최대 추종 오차 .085538rad(약4.90도), 어깨 명령 변화 최대
  .375722rad(약21.53도), inference mean/p99/max 2.657127/2.877623/4.836160ms,
  lowcmd 499.722999Hz, interval max6.763904ms, torque limiter ratio0.
- right_shoulder_start_rad=final_rad=.289934는 기존 고정목표 실험용 요약 변수다.
  final 필드는 최종 실측값이 아니므로 미동작 또는 원위치 복귀 증거로 해석하지 않는다.
- CSV 위치는 /home/unitree/g1_mink_udp_trial_20260908/g1_twist2_right_arm_trial_1787645017.csv.
  이번에는 원격 CSV 수집/분석이나 로봇 실행 없음. 근거는 사용자 제공 콘솔과 로컬 소스.
- 종료 로그상 SSH 연결 종료, AI standing 자동 복귀 안 됨. 현재 AI 수동 복귀 여부 미확인.
  현재 조건의 사용자 동작 확인이며 전체 경로 충돌 안전/속도 상향 검증으로 확대하지 않는다.

## 최신: invalid_clock 수정본 G1 배포·빌드 완료 (2026-09-08)

- 사용자 승인에 따라 새 실험 폴더 /home/unitree/g1_mink_udp_trial_20260908에
  mink_udp_target.hpp 및 twist2_mink_udp_trial.cpp 두 파일만 전송. 양쪽 SHA256 일치 확인.
- G1 cmake --build build --target g1_twist2_mink_udp_trial --clean-first -- -j1 성공(exit 0).
  SDK/Torch 헤더 및 unused print_keyboard_help 경고 있음. ARM aarch64 ELF 확인.
  새 실행파일 SHA256 abd1f5e169e965f5d5f0115e52d861e58bc6d5f6c2e8986c68f9173cd81b9404.
- 기존 g1_right_arm_trial 소스와 실행파일 SHA256은 배포 전후 동일. 원본 수정 없음.
- 결과 logs/test_results/g1_mink_udp_clock_deploy_20260908.json.
  초기 source.tar.gz/SHA256SUMS는 이전 패키지 기록이며 이번 두 파일 수정은 위 JSON으로 추적.
- 이번에 제어 프로그램 실행/모터 명령/모드 변경은 하지 않음. 실기 재발 여부 검증은 남음.
  기존 배치/PS1 명령이 같은 경로의 수정된 바이너리를 사용한다. 현재 로봇 자세 상태는 미확인.

## 최신: invalid_clock 시간 순서 경합 로컬 수정 (2026-09-08)

- 사용자 실기 로그: preflight/warmup 통과, 12초 udp_ready 이후 invalid_clock로 damping.
  이번 중단은 직전 사용자의 수동 R1 해제와 별개다. 현재 AI 복귀 상태 미확인.
- 코드상 재현 가능한 원인: 500Hz writer Poll과 주 루프 Receive/Update가 mutex 전에
  clock()을 평가하여 잠금 획득 순서와 타임스탬프 순서가 뒤집힐 수 있다.
  실기 로그에 스레드별 타임스탬프는 없어 해당 사건의 경합 발생 자체는 확정하지 않는다.
- MinkUdpTarget에 주입 가능한 event_clock 추가. live C++는 동일 steady clock을 주입하고
  Receive/Poll/Update 각각 mutex 내부에서 읽는다. 오프라인 명시 시간 API는 유지.
  validator의 역행 검사/250ms timeout/속도/해제 latch를 완화하지 않음.
- MSVC /W4 /WX 빌드 및 표적 테스트 통과. 기존 역순 시간 invalid_clock 재현,
  잠금 내부 clock 사용 시 오래된 호출 인자의 Receive/Poll/Update 정상 처리,
  실제 clock 역행 거부 및 timeout 유지 확인. 기존 속도/초과/해제 검사도 통과.
  결과 logs/test_results/mink_udp_clock_fix_20260908.json.
- WSL의 새 실험 C++ 대상 빌드/링크 exit 0. Torch 헤더 maybe-uninitialized 경고 있음.
  로그 mink_udp_clock_build_20260908.log. 빌드한 실행파일은 실행하지 않음.
- 원본 twist2_right_arm_trial.cpp SHA E61D8A3C...CC09F 유지.
  G1 전송/컴파일/프로그램 실행은 이번 수정에서 수행하지 않음. G1에는 이전 바이너리가 남아 있어
  그대로 재실행하면 문제가 재발할 수 있음. 수정본 배포 및 실기 확인이 남아 있다.

## 최신: Unity 첫 입력 전 Relay 대기 표시 수정 (2026-09-08)

- 사용자 화면: Robot은 udp_ready까지 진행 후 R1 deadman released로 damping.
  Relay에는 non-empty session_id 오류. 두 현상은 별개.
  사용자 후속 확인: 직접 R1을 놓아 중단시켰음. 이번 R1 deadman released는 의도한 중단이며
  컨트롤러 신호 손실 문제로 취급하지 않는다.
- 코드 확인: MinkCommandStream은 첫 Unity 유효 입력 전 session_id=None/age=None,
  inactive idle 상태를 생성하고 live controller가 표시 및 UDP 5008로 전송한다.
  Relay가 이를 세션 순서 검사에서 오류로 표시하던 문제를 수정.
- 최초 세션 전의 검증된 inactive idle/age=None 패킷만 WAIT로 집계하고 전송하지 않는다.
  임의 세션 생성 없음. active의 세션 누락, 기존 세션 후 누락, provenance/순서 검증은 유지.
  첫 정상 전달은 기존 RELAY 메시지로 확인. WAIT는 Unity Play/손 추적 입력 확인 안내.
- gate7_mink_wsl_relay.py 및 해당 테스트 수정. unittest 12개 통과(신규 2개 포함).
  preinput 무송신/실제 세션 이후 전달/세션 소실 거부/active 누락 거부를 mock socket으로 검증.
- 이번에는 G1 연결·프로그램 재실행·모터 출력 없음. C++ 변경 없음.
  실행 중인 Relay에는 수정이 자동 반영되지 않으므로 다음 Relay 시작부터 적용된다.
- 남은 항목: Unity 실제 입력 수신과 정상 Relay 전달 확인. 사용자의 현재 AI 복귀 상태 미확인.
  R1 해제 중단은 사용자 의도와 로그가 일치한다. VR로 실제 팔 추종 성공은 아직 확인되지 않았다.

## 최신: 한 번에 세 창 실행 및 실행정책 우회 (2026-09-08)

- 사용자가 Input 창 하나만 뜬다고 보고. 기존 배치 기본값이 Input이었던 것이 원인.
- START_TWIST2_MINK_UDP.bat 기본을 All로 변경. PS1 All은 Input/Relay/Robot 창을 열고
  GUID 토큰을 Relay/Robot에 자동 공유한다. 모든 자식 PowerShell에도 ExecutionPolicy Bypass 적용.
  시스템 정책은 추가 변경하지 않음. 기존 개별 모드 유지, 창 제목과 NoExit로 오류 확인 가능.
- UDP 5005/5008 점유 시 PID를 표시하고 새 창 실행 중단. 기존 프로세스 자동 종료 없음.
- 배치 All -Preview 실제 호출로 3개 실행 계획/동일 토큰/모든 자식 Bypass 검증 통과.
  배치 Check exit 0, PowerShell 구문 검사 통과. 이번에는 Input/Relay/SSH/Robot 실행 안 함.
- 사용자 실행: 기존 Input 창을 닫고 tools/START_TWIST2_MINK_UDP.bat 실행.
  SSH 로그인 및 P/R1은 수동 유지. Unity Play도 별도 준비. 세 창 오픈은 준비 완료 판정이 아님.
- 남은 항목: 사용자 환경의 실제 세 창 실행/VR 연결 확인, 초기 자세 전 경로 접촉 검증과 실기 확인.
  원본 물리 제어 C++ 및 G1 파일은 이번에 변경하지 않음. 사용 안내 문서 갱신.

## 최신 배치 실행기 추가 (2026-09-08)

- tools/START_TWIST2_MINK_UDP.bat 추가. 기본은 Input, 인자가 있으면 기존PS1에전달.
  powershell.exe -NoProfile -ExecutionPolicy Bypass 사용. 시스템정책변경없음.
- -Mode Check로 실제배치호출 exit0 검증. Input/Relay/Robot은이번에실행안함.

## 최신 사용자 기준 변경: 원본 키보드 기반 별도 Mink UDP 버전 (2026-09-08)

- 사용자 명시요청: 잘되는 g1_right_arm_trial 원본보존, 해당코드에Mink 절대각도입력,
  MuJoCo속도일치, P/R1유지, 보조자중단, 초기팔/다리접촉개선. G1접속·수정허용.
  따라서직전PC전용결정에서이번새요청에따라G1별도배치로전환. 원본은전혀수정하지않음.
- 새소스 twist2_mink_udp_trial.cpp는원본복사에 mink_udp_target.hpp/native_vr_udp 연결.
  하체정책/단일전신송신/P/R1/Select·B/키p/300초기본구조 유지.
  UDP 5014, source192.168.123.99,target192.168.123.164. 기존token/live출처검증재사용.
- raw Mink 오른팔22..28 절대각도를입력, 고정 .08rad/s(원본1배)로초과없이추종.
  기존 VR후보의 .025rad초기정렬/all29 targeterror ready/±10도relative창은사용안함.
  0.25rad 실제q-명령 추종보호는안전상유지했다고사용자에게명시. 제거했다고표현하지않음.
  상체12..28검사,속도1.5/상태/CRC/온도/fault/joint/torque/timeout 등유지.
  원본snapshot age혼용과중복tick 신선도문제는새복사본에서수정.
- capture1초/blend4초후 두팔 [10,±22,0,55,0,0,0]도준비자세로 .08rad/s이동.
  cpp는본래차렷을강제하는것이아니라실측capture였음. 새버전이명시준비자세를추가한다.
  command기준준비완료후udp_ready,그전engage거부. 정책300초에초기팔이동포함.
- MuJoCo prototype에 G1_TWIST2_KEYBOARD_RATE=1일때만 .08rad/s프로필추가.
  기본 .16 및기존가속도 .32rad/s²/jerk유지. QP/trajectory모두 .08사용확인.
  START_TWIST2_MINK_UDP.ps1 Check/Input/Relay/Robot 제공, Input은liveMinkentry/
  hardware-guarded/vanilla, 표시simulation 유지. G1_USE_HARDWARE_INITIAL_STATE=0으로
  오른팔ready의옛환경파일override를배제. 재생/simulation_only를live로위장하지않음.
- 기존simulation_312.py PID41228이5005점유함을확인. 자동종료안함.
  사용자새Input시작전기존MuJoCo창닫기필요. Unity재실행/VR/모터실행안함.
- 오프라인MSVC /W4 /WX: 초기rate/ready/큰입력차이허용/다른축유지/overshoot없음/
  release/latch/timeout/잘못된JSON/earlyengage거부통과. WSL및G1빌드·링크exit0.
- 모델최종ready기존오른팔충돌쌍최소40.38mm, 저장표본시작경로최소28.11mm.
  확장양손-다리조회에중간0반환있어전체경로무접촉검증은미완료.
  초기접촉문제해결/물리안전검증완료로표현하지않는다. 임의시작자세보장없음.
- G1새폴더 /home/unitree/g1_mink_udp_trial_20260908 생성·source전송·해시검증·컴파일만수행.
  packageSHA57b477f18ba4caef2059adab2c35e19d3b914a7dc63360a84b3604dd867633c6.
  새ELF5f30108275149114b30777393a76eba4e825948de57d8b9b481bcc1c8807d3d3.
  원본CPPE61D8A3C...CC09F/ELFa3c1e936...4f60전후일치. 사용자원본명령계속사용가능.
- 상세실행 docs/TWIST2_KEYBOARD_BASED_MINK_UDP.md. 증거logs/test_results/
  mink_udp_target_test_20260908.json,mink_udp_initial_pose_review_20260908.json,
  mink_udp_trial_build_final_20260908.log,g1_mink_udp_build_20260908.log,
  g1_mink_udp_build_check_20260908.json. G1새실험폴더는향후정리대상.
- 남은것: 현재시작자세의접촉경로,새Unity/Mink표시/UDP 실입력/physical검증.
  기존3.12simulation화면을새CPP목표시각화라고해석하지않음.
  EDU속도·가속도상향은사용자요청대로차후검토,이번에하드웨어한계상향없음.

## 최신 PC C++ 실제표본 추론·500Hz 관찰 결과 (2026-09-08)

- 사용자 직접실행 pc_native_20260908_140508 완료. 이번턴 저장로그 로컬분석만 수행.
- accepted10022, CRC0, old_tick530(중복/역행 합산이므로 각각0으로단정못함).
  정책501회, stale skip0, 최대추론 .871798ms, 중앙 .484536ms,20ms초과0.
  500Hz관찰5001회, 상태age최대6.46734ms,20ms초과0, lateness최대2.13734ms.
  관찰주기간격 중앙2ms/최대약4.06ms. 엄밀한매2ms보장은아니다.
- policy.csv 주기간격최대약20.19ms. 목표주기20ms 주위미세지터가있으며,
  이 간격의20ms초과횟수는 상태stale/추론20ms초과와다른지표다.
- publisher_created=false,mode_changed=false,error빈값. source/summary/review는
  logs/test_results/pc_native_20260908_140508에보관.
- 이번관찰구간에서 실측입력C++추론과별도2ms상태점검이동시완료.
  실제native command writer/SDKWrite/네트워크단절시damping전달/VR 결합은미검증.
  G1파일변경/모터출력 없음. 직접실행 선호 유지.

## 최신 실제 LowState C++ 추론 + 500Hz 관찰 스레드 준비 (2026-09-08)

- pc_native_receive_probe.cpp 및 독립 g1_pc_native_receive_probe target 추가.
  ChannelSubscriber<LowState>만생성. command publisher/MotionSwitcher/ReleaseMode 없음.
  기존물리제어C++ 및 PC실행후보 동작은변경하지않는다.
- CRC/전진tick만최신표본으로수용. 실제관절/gyro/rpy를 기존ObservationHistory/Policy로
  추론, 캡처목표 고정 및 가상hybrid target feedback 사용. 모터출력은전혀없다.
  정책20회warmup후 10초관찰. 별도2ms스레드는snapshot age/실행lateness만기록.
  policy.csv,clock_500hz.csv,summary.txt를사용자가지정한새PC폴더에저장.
- PC WSL 컴파일·링크exit0. 무인자실행은DDS초기화전usage/exit1 확인.
  소스에서 command publisher/모드client 부재확인. 실제DDS수신은아직실행안함.
  로그 logs/test_results/pc_native_receive_probe_build_20260908.log.
- 중요: 500Hz스레드는실제writer가아니다. 최종command검사/SDKWrite부하/송신/단절대응을
  측정하지않는다. 고정mimic의읽기전용연구이며실제capture/blend/VR루프와동일하지않다.
- 다음 사용자직접실행: PC ELF g1_pc_native_receive_probe, interface eth3,
  로컬정책경로 및새출력폴더. R1/P불필요,AI유지. G1파일변경없음.

## 최신 PC 합성 추론부하 중 LowState 수신 확인 (2026-09-08)

- 사용자 직접실행 pc_load_20260908_135939 결과를 로컬분석. 원격/DDS/모터실행 없음.
- 10.003초/10045표본, SDK·독립CRC0, 비유한값0, tick역행0, motorfault없음.
  수신중앙값 .949345ms, 최대6.079330ms,20ms초과0.
  중복tick489를제외한 새tick9556개 최대간격6.851110ms,20ms초과0.
- 합성입력 정책800회, 최대추론2.027955ms,20ms초과0, 최대스케줄늦음1.243190ms.
  전체수신구간이정책부하구간에포함됨. 로그/추가분석은 해당폴더의 summary.json,
  fresh_tick_review.json. 수신SHA36297b9f1b9e9da360cf9fe5db401f294f05d399e669fd764461d36601f07aaf.
- NumPy미설치경고는발생했으나 이 도구는torch tensor만사용하고NumPy변환없음.
  추론·출력검사·수신·요약완료, 이번측정실패로해석하지않으며패키지임의설치안함.
- 이는50Hz 합성정책별도프로세스 부하중 읽기전용수신 확인. 실제LowState정책관측/
  같은프로세스 callback/500Hz writer/모터명령전달/단절시행동 검증이아니다.
  다음은PC native실측입력 경로와500Hz동시동작 검증 준비. 사용자가실행하는원칙유지.

## 최신 PC 추론부하+읽기전용 수신 도구 준비 (2026-09-08)

- 사용자 직접실행 흐름 유지. check_pc_receive_under_load.py 추가.
  별도 Torch 프로세스에서 해시검증정책을 합성zero1432입력으로 warmup후
  50Hz·800회 추론. 동시에 기존 읽기전용수신기를10초/12000표본한계로 실행.
  subscriber만사용하며 publisher/모드변경/SSH/모터출력 없음.
- 결과폴더는 PC logs/test_results 아래 새폴더만허용. policy_load.json,
  lowstate.jsonl, summary.json 기록. 수신구간이부하구간안인지 별도검사한다.
- 이 시험은 PC부하간섭 확인이며 실제LowState observation/하체합성/500Hz writer
  결합검증이아니다. 수신간격도편도통신지연으로해석하지않는다.
- --offline-only로 부하경로만 자체점검. 실제수신은 사용자가다음명령으로실행한다.
  기존모터제어코드/실행정책 변경없음.

## 최신 PC 실행으로 전환 / G1 VR 추가파일 정리 완료 (2026-09-08)

- 사용자 요청대로 실행주체를 PC WSL로 전환. G1에 이번VR작업에서 추가한
  g1_vr_native_review_20260908 및 g1_vr_split_candidate_20260908 모두 삭제/부재 확인.
- 이번 후보폴더64파일 전체 PC백업 및 원격SHA 전부일치 검증 후 삭제.
  logs/test_results/retired_split_candidate_20260908에 backup/remote_sha256/verification 보존.
  이전53파일백업도유지. 실제절대경로/심볼릭링크아님 및 /proc cwd/exe 사용부재 확인.
  작업전부터있던 SDK/Torch/정책/g1_right_arm_trial은 삭제하지 않았다.
  원본ELF a3c1e936...4f60 유지. G1에서 프로그램실행/모드변경/모터출력 없음.
- tools/RUN_PC_TWIST2.ps1 및 experiments/twist2_right_arm_manual/run_pc_twist2.sh 추가.
  기본Check는 native실행/DDS없이 경로/정책SHA/PC ELF 확인. Readiness는사용자직접
  P입력하는8초전신시험, Vr는명시token필수. SSH/원격설치 단계없음.
  로그는 PC logs/test_results/pc_twist2_runs에 생성. 제어C++ 알고리즘변경없음.
- PC WSL mirrored설정 및 route eth3/source192.168.123.99 확인. 정책SHA463be037...9015.
  x86_64 ELF SHA6f1f051eb09507678317450ba30b36f835a13970be258fe841a59c55e2df4a09.
  PowerShell 기본Check실행exit0. shell문법/잘못된mode거부도확인.
- 상세명령 docs/TWIST2_PC_RUN.md. VR relay대상은G1IP가아닌PC loopback5013.
  Windows→WSL loopback 실제수신, PC DDS LowState 신선도, 500Hz지연/단절대응은미검증.
  G1에서ready성공한것을 PC물리검증으로해석하지않는다. 다음은PC통신수신검증.
  PC물리시험/Quest실행은이번에하지않았다. 현재AI수동복귀여부도추가확인없음.

## 최신 이전 진단 폴더 정리 완료 (2026-09-08)

- 사용자 요청으로 G1 `/home/unitree/g1_vr_native_review_20260908` 삭제 완료.
  새후보 CMake/ELF RUNPATH 의존성 없음, 관련프로세스 없음 및 삭제직전 /proc cwd/exe
  참조 없음 확인. 실제절대경로 일치/심볼릭링크 아님 확인 후 명시한 폴더만 제거.
- 먼저 전체53파일 PC백업 및 원격 SHA256 전부 일치 검증.
  `logs/test_results/retired_native_review_20260908/g1_vr_native_review_20260908/`.
  같은 상위폴더에 remote_sha256.txt와 verification.json 보관.
- 삭제 후 경로부재 확인. 새후보 ELF40383ff7...62a3 및 원본물리ELFa3c1e936...4f60 유지.
  프로그램 실행/모터출력/모드변경 없음. 과거문서의 이전폴더 "삭제미완료"는 이 기록으로 갱신.
  `/home/unitree/g1_vr_split_candidate_20260908`는 유지하며 추후정리 대상.
- 사용자가 코드열람 요청: 로컬 twist2_vr_native_draft.cpp main(701행)을 앱에 열기 요청.
  현재 준비판정은 split_settle_window.hpp, VR연결은 split_vr_adapter_study.hpp,
  상대목표는 anchored_upper_study.hpp. 원래 물리 twist2_right_arm_trial.cpp와 구분.

## 최신 사용자 직접 실행: vr_ready 진입·계획 종료 확인 (2026-09-08)

- 사용자는 앞으로 본인이 명령으로 실행하기 원함. 실행명령 제공 후 "끝났어" 보고.
  이번턴은 SSH 읽기/기존로그 로컬복사만 수행. 원격변경·출력·재실행 없음.
- 원격 후보 ELF SHA40383ff7d443571642badd930cb1451370072f53330d13ea827458cd17f362a3.
  관련 g1_twist2 프로세스/5013 포트 없음. 현재 AI모드는 조회하지 않았다.
- g1_twist2_right_arm_trial_1787638477.csv:399표본, 최초 vr_ready6.38006944초,
  마지막7.98007251초까지81표본 연속ready. stop reason=planned policy duration completed,
  planned=1. VR active 없음. blend후 오른팔22..28 desired 변화폭 모두0.
- 모든표본 R1 눌림, sampled SDK accepted=1. 최대roll .0242512rad, pitch .1140998rad,
  추론4.986368ms, 표본age1.405088ms. 이 값은 policyCSV 관측이며 전체500Hz/3초damping
  전달 성공의 직접증거는 아니다. 터미널총송신통계는 이번자료에 없음.
- CSV 및 stop.csv 원격/로컬 SHA 일치:
  22cb351fea79a648b57dd812b30cdf0c157db0dae909002f5bbc92baea2e17a8,
  d1cd3b18ccf2fde0e705418aab6651d2787209b87d44bdbdf124207f5d6aed95.
  로컬 logs/test_results/에 저장. 분석 twist2_split_user_trial_audit_20260908.json.
- 사용자 이상움직임 질문에 "딱히없었어". 예상외움직임 없었다는 보고로 기록.
  현재지지안정/AI수동복귀 여부까지 답변했다고 해석하지 않는다.
- 결과: 이번 지지조건에서 split ready 진입과 계획종료 확인. 실제VR 상대정렬/팔이동,
  R1해제·오류 중단시험, 독립보행/지지없는 안전성 검증은 아니다.
- 다음은 현재상태/AI복귀 확인 뒤 실제 LowState 기반 fresh Mink 정렬 및
  사용자 직접 실행용 Quest→G1의 최초engage/작은이동/해제 절차 준비.
  자동 물리 실행 안 함. 두 원격 임시폴더 및 새 CSV 추후삭제 의무 유지.

## 최신 시작 시도: CLI 진입부 거부 / 로컬 수정·검증 완료 (2026-09-08)

- 사용자가 지지/접지/안정/R1 준비 및 구체8초 시험 질문에 "시작"으로 답하여 1회 시작.
  실행전 후보ELF b670e52e...380d2 및 정책463be037...9015 확인, 관련프로세스/5013 없음.
- 후보 --vr-relative-candidate 실행 직후 기존 최상단 --vr-right-arm 전용 검사가 거부.
  `[fatal] native VR draft requires explicit VR invocation; not a keyboard executable`, exit1.
  원인: 후보옵션을 후속파서에만 추가하고 첫 guard를 누락한 구현결함.
  앞선 빌드/adapter시험은 실제 main 진입을 검증하지 못했다. 이는 물리조건 실패가 아니다.
- main 첫 guard에서 종료: P 질문, Policy 구성, Controller/DDS 초기화, publisher 생성,
  ReleaseMode/모터명령 전에 중단. 이번시도는 AI해제/damping 전환을 수행하지 않았다.
  이후 관련프로세스 및5013 없음 확인, SSH 종료. 사용자에게 R1 놓아도 됨 안내.
  현재 AI모드를 새로 조회한 것은 아니며 자동 재시도 없음.
- 로컬 native_vr_invocation.hpp로 첫 guard와 mode선택의 공통검사를 통합.
  후보는 --vr-relative-candidate, 기존진단은 --vr-right-arm만 허용.
  실기 제어/속도/한계/준비 임계값 변경 없음. 기존 물리원본 SHA E61D8A3C...CC09F 유지.
- SDK없는 test_native_vr_invocation.cpp: 옵션교차거부, 명시actuation/기간인자필수,
  잘못된옵션/argc/null 거부 및 양쪽정상옵션 허용 MSVC /W4 /WX exit0.
  WSL 두target 재빌드·링크 exit0. 로컬native/G1바이너리 재실행 없음.
- 패치 `logs/test_results/twist2_invocation_fix_20260908.tar.gz` 파일4개 바이트검증 완료.
  SHA256 `68960570d4d275900e2a07c75f6361acb84047b0f9b2d65c187976059116d75a`.
  cpp/newheader/INVOCATION_FIX_MANIFEST.json/INVOCATION_FIX_SHA256SUMS 포함.
  아직G1미전송. 원격대상은 기존 신규임시폴더 하나로 한정하고 candidate만 재컴파일 제안.
  적용 후 기존 SHA256SUMS의 cpp해시는 과거버전이므로 새 INVOCATION_FIX_SHA256SUMS로 검증.
- 증거: twist2_split_attempt1_terminal_20260908.json,
  twist2_invocation_fix_build_20260908.log, twist2_invocation_fix_check_20260908.json
  (모두 logs/test_results). 시험용패치에는 실행스크립트/정책/SDK/ELF 없음.
- 남은 작업: 이 수정본 반영·재컴파일 승인 및 동일범위1회 재시험 승인/준비 확인.
  현재실기 ready/시간지연/정지 검증은 아직시작하지 못함. 임시폴더 추후삭제 의무 유지.

## 최신 제한 시험 범위 구체화 / 현재 지지·R1 확인 대기 (2026-09-08)

- 사용자 "진행"을 받아 다음 제한 전신 시험을 준비. 아직 원격 실행/출력 없음.
- 대상은 새 split candidate ELF b670e52e...380d2. VR sender/engage 없이
  --policy-seconds 3 --vr-relative-candidate: capture1초 + blend4초 + policy3초,
  계획 종료 damping3초. preflight/오류 damping 시간은 이 8초 active 범위와 별개.
- 실행한다면 AI 자세유지를 해제하고 단일 rt/lowcmd 전신 TWIST2로 전환한다.
  오른팔은 captured 목표 유지하며 상대 VR 이동 시험은 이번 범위에 포함하지 않는다.
  ready 진입/자세/정책·writer 시간/종료 기록을 관찰한다. 재시도·제한완화 없음.
- VR 입력 없는 시험의 UDP는 loopback에만 bind하고 sender를 시작하지 않는 계획.
  실행 직전 ELF/정책 hash, 관련 프로세스/포트 및 현재AI상태 재확인 필요.
- 현재 사람 확인 필요: 지지대 설치, 양발 접지·하중, AI에서 안정, R1 계속 유지와
  Select/B 중단 가능. 과거 "별도 담당 준비" 기록은 현재 상태로 재사용하지 않는다.
  사용자가 혼자라는 후속 정정에 따라 이번에는 Quest 조작 없이 리모컨에 집중한다.
- 종료는 damping이며 자동 AI 복귀하지 않는다. 오류시 damping 지속 가능,
  Ctrl+C도 AI 복귀가 아니다. 지지는 송신 종료 후에도 유지한다.
- 확인 및 해당 구체 범위 승인 전까지 바이너리를 시작하지 않는다.

## 최신 G1 후보 전송·컴파일 완료 / 실행하지 않음 (2026-09-08)

- 사용자가 새 임시폴더 전송·컴파일 질문에 "진행"으로 승인. 이 범위만 수행.
- LAN SSH 연결 확인, 대상폴더 부재 및 실행중 g1_twist2 프로세스 없음 확인 후
  `/home/unitree/g1_vr_split_candidate_20260908` 생성. 기존 작업 되돌림 없음.
- source.tar.gz 전송, archive SHA db190c66...af403 및 SHA256SUMS21항목 모두 OK.
  G1 aarch64 / Torch2.0.0+nv23.05 / ABI1 / 기존 unitree_sdk2-main 확인.
- 후보 target만 CMake configure 및 clean-first -j1 컴파일·링크 성공, SSH exit0.
  ELF `/home/unitree/g1_vr_split_candidate_20260908/build/g1_twist2_vr_split_candidate`
  SHA256 `b670e52e471d8eb2feb297887f63d449159a9d7e62f4e81c799f4159b18380d2`.
- 기존 물리 ELF a3c1e936...74f60, 진단 ELF2af67725...65ef16 전후 동일.
  빌드 후 관련 프로세스 없음. 생성된 바이너리는 --help 포함 실행하지 않았다.
  DDS 초기화/publisher/모드변경/물리출력 없음. 로봇 자세/AI모드는 이번에 조회하지 않았다.
- 기록: `logs/test_results/twist2_g1_split_candidate_build_20260908.log`,
  `logs/test_results/twist2_g1_split_candidate_build_check_20260908.json`.
  stdout 빌드로그이며 SDK/Torch stderr 경고 전체는 포함하지 않는다.
- 다음은 별도 승인·현재 지지/R1 준비 확인 후 VR engage 전 제한된 전신 준비 시험.
  G1 빌드 성공은 split/relative 방식의 물리 검증이 아니다. 실행 승인은 받지 않았다.
- 신규 임시폴더 전체(source/manifest/build 포함)와 기존
  `/home/unitree/g1_vr_native_review_20260908` 추후삭제 미완료 유지.

## 최신 후보 소스 패키지 준비 완료 / 전송 승인 대기 (2026-09-08)

- `logs/test_results/twist2_split_candidate_source_20260908.tar.gz` 생성.
  SHA256 `db190c6692b26a3c8828e4a70ec16024577cdfb6ecfdb1f5b31f57efc44af403`. 파일22개, 169779bytes.
- 검증 소스 해시 대조, quoted include 의존성 완결성, 압축 상대경로/일반파일/
  원본 바이트 일치 검증 통과. 코드 수정 및 기존 작업 되돌림 없음.
- 검증기록 `logs/test_results/twist2_split_candidate_package_check_20260908.json`.
  직전 빌드/오프라인 결과 재사용. G1 빌드·실기 검증은 아직 아니다.
- 상세 범위 `docs/TWIST2_SPLIT_CANDIDATE_PACKAGE.md`:
  신규 `/home/unitree/g1_vr_split_candidate_20260908` 내 전송/압축해제/후보 컴파일 제안.
  기존 원격 진단/물리 원본 불변. 실행·DDS·모드변경·물리출력은 범위 밖.
- 현재 G1 접속/변경 없음. 정확한 원격 변경 승인 대기.
  근거: 본 문서 상단 Absolute G1 mutation rule.
  새폴더(생성할 경우)와 기존 임시폴더 모두 추후삭제 대상 유지.

## 최신 로컬 split/relative native 후보 연결 완료 (2026-09-08)

- 기존 native 진단 target과 분리된 g1_twist2_vr_split_candidate CMake target 추가.
  기본빌드 제외(EXCLUDE_FROM_ALL), TWIST2_SPLIT_CANDIDATE 매크로와 명시적
  --vr-relative-candidate 인자 필요. 기존 --vr-right-arm은 기존 의미 유지.
  아래 과거의 "이식 전" 기록은 당시 상태이며, 이번에 로컬 후보까지만 연결했다.
- 후보 ready: 전신 목표-실측 고정오차 대신 1초 관찰 중 q변화폭 .005rad,
  roll/pitch 변화폭 .01rad, dq .1rad/s, gyro .1rad/s, roll/pitch 절댓값 .15rad 사용.
  이는 관찰로그에서 검토한 연구값이며 물리 안전기준으로 검증되지 않았다.
  발목오차가 하중유지에서 생겼다는 해석은 여전히 가설이다. 보상토크 추가 없음.
- SplitSettleWindow는 deque 대신 고정128표본 배열 사용. 초과 시 거부하며 조용히
  표본을 버리지 않는다. 50Hz의 1초 창을 수용하되 실제500Hz writer 지연은 미측정.
- 후보는 writer 기준 고정을 필수화. 첫 active 직전 최신 완료시도의 active/damping/
  SDK accepted/20ms 신선도와 최신 LowState 검사를 확인하고 오른팔 C0를 고정.
  V0는 첫 active Mink 목표, 이후 C0+(V-V0). 최초 명령은 C0 유지.
  첫 VR-실측 .025rad 정렬, 입력/변환한계 .05margin, ±10도, .08rad/s 유지.
  실측을 곧바로 명령으로 덮어 하중오차를 없애는 방식이 아니다.
- 입력처리/관찰창/추론은 command 잠금 밖. commit 시 command 잠금 아래 최신 frame과
  최초 기준의 오른팔 q/kp/kd/feedforward 및 최초 desired q/feedforward를 재비교한다.
  동일 frame의 새 sequence는 허용, 내용변경은 거부 후 기존 latch 경로로 중단.
  이전 writer_reference_study의 "sequence만 변경돼도 거부" 모델과 이 점이 다르다.
  adapter 잠금 안에서 command 잠금을 취하지 않는다. 다른 관절은 기존 소유구조 유지.
- 정책표본 validate_state 뒤 신선도/damping 결과를 adapter에 전달하고 commit에서 다시
  실제 상태검사. writer의 R1/Select/B/CRC/상태·모드·한계/timeout 검사 유지.
  후보에 한해 SDK Write false면 감사기록 뒤 즉시 latch하여 다음 active 쓰기를 막는다.
  accepted는 모터 ACK가 아니다. SDK 실패에서 damping 전달 성공도 보장할 수 없다.
- 검증: MSVC /W4 /WX 후보 결합시험 및 기존 NativeVrPolicyAdapter 회귀시험 exit0.
  최초기준 필수/정확일치, 동일명령 새sequence 허용, 위치·gain·FF 변경 거부,
  SDK거부/damping/빈기준 거부, 최초명령 점프 거부, 창초과 거부와 기존 속도/
  목표초과 없음/다른축 유지/정렬/JSON/해제·오류·latch·timeout 시험 통과.
  기존진단+새후보 WSL SDK/Torch 컴파일·링크 exit0. SDK/Torch 헤더 경고는 존재.
  증거: logs/test_results/twist2_split_candidate_offline_20260908.json,
  logs/test_results/twist2_split_candidate_build_final_20260908.log.
- 기존 물리원본 twist2_right_arm_trial.cpp SHA E61D8A3C...CC09F 그대로.
  G1 전송/파일변경/실행, DDS 실행/publisher 생성, VR 시험 없음. 로컬 컴파일만 했다.
  원격은 이전2af67725...65ef16 진단버전이며 기존 전송 patch에 이번 변경은 없다.
- 다음 필수 항목: 후보 소스 검토 후 새 전송물 준비 및 승인 범위 안에서 G1 빌드,
  VR engage 전 제한된 전신 settle 시험으로 실제 시간지연/ready/중단 동작 확인.
  그 다음 최초 상대명령 연속성 확인 후 작은 VR 이동. 즉시 무제한조작 가능 판정 아님.
  사용자 AI복귀·안정 확인 상태 유지; 현재 상태를 새로 조회하지 않았다.
  /home/unitree/g1_vr_native_review_20260908 임시폴더 추후삭제는 아직 미완료.

## 최신 Controller 연결 검토 / 표본 신선도 결함 로컬 수정 (2026-09-08)

- validate_state(state)가 전달된 state 대신 내부 snapshot()으로 최신 수신 age를 읽는 결함 확인.
  새로운 callback이 도착하면 이전표본의 오래됨을 가릴 수 있었다. 실제 시험에서 이 결함이
  발현했다는 증거는 없으며 ready timeout 원인으로 단정하지 않는다.
- 로컬 native snapshot이 state_mutex 아래 state와 Clock::time_point received를 함께 복사하도록 수정.
  validate_state의 모든 호출(preflight/warmup/readiness/policy/writer)에 해당received를 필수 전달.
  native_snapshot_freshness.hpp로 미래시각/20ms초과 거부. VR adapter receipt도 동일시각을 사용한다.
  기존20ms 기준을 늘리지 않았다. 실제 원본 twist2_right_arm_trial.cpp는 수정하지 않았다.
- MSVC /W4 /WX test_native_snapshot_freshness 실행exit0: 오래된표본+새callback 반례,
  20ms경계/경계초과/미래시각 검증. WSL SDK/Torch 빌드·링크exit0.
  logs/test_results/twist2_snapshot_freshness_build_20260908.log.
- 로컬 native SHA0FAECDC78F99B46BCC9F805AAD2AF3F81A6D1AB63D2FC6672B501891D5B6CCC1,
  원본물리 CPPSHA E61D8A3C...CC09F 유지. G1원격은2af67725...65ef16 버전 그대로.
  기존 state_stop patch는 이번수정을 포함하지 않는다. 전송전 새패키지 필요.
- 현재 lock검토: writer는 command→adapter(Poll), command→state/desired/stats,
  latch는 command→reason→state. callback은state만 보유. 현재경로의 역순사이클은 찾지 못했다.
  이식시 adapter안에서 command를 얻으면 역순이 생기므로 금지. 최초기준과 후보commit은
  command→adapter→desired 순서로 제한하고, 정책추론/UDP수신/파일I/O는 command잠금 밖에 둬야 한다.
- 외부안전 bool을true상수로 연결하면 안 된다. 실제 validate_state 및 writer 제한/active/damping/
  최신SDK결과를 연결해야 하며, 현재실패반환은기록만하고latch하지않는 기존동작도 별도검토대상이다.
  시험용 deque/임계값을 그대로 실기로 옮기지 않는다. 실제split/relative adapter이식은 아직안했다.
- 로봇명령/원격파일변경/물리시험없음. 사용자AI복귀안정 확인 유지. 원격임시폴더삭제 미완료.

## 최신 writer 기준 고정 연결의 오프라인 검증 (2026-09-08)

- writer_reference_study.hpp 추가. 메모리 writer모델의 최신완료시도 sequence/명령/시간/
  SDK반환/damping을 보존하고 mutex 아래 기준확인과 최초 후보 callback을 직렬화한다.
  sequence변경, 거부된최신시도, damping, Stop, 외부검사실패,20ms초과,비유한값은 기준으로 거부.
  성공 후 재기준화 거부. SDK accepted는 모터수신 ACK가 아니다.
- AnchoredUpperStudy와 SplitVrAdapterStudy에 명시적 BindCommandReference 추가.
  오른팔22..28만 기준에 반영, 최초입력 처리와 같은 writer모델 잠금 안에서 확인한다.
  하체/허리/왼팔 기준은 기존 소유범위 유지. 원래native/실제Controller는 연결하지 않았다.
- C++ 결합시험 확장, MSVC /W4 /WX 빌드 및 저장fixture 실행 exit0.
  기준조회후 writer버전변경 거부/콜백미실행,실패·damping·Stop·지연·외부검사거부,
  최신유효명령과 최초후보 오른팔의 정확한 일치, 다른축 유지,재기준화거부 검증.
  기존 정렬/속도/한계/timeout/해제 시험도 함께 통과.
- 증거 logs/test_results/twist2_writer_reference_study_20260908.json.
  실제SDK lock순서/500Hz부하/실기연결 검증은 아니다. 기존독립시험은 생성자baseline 경로도
  사용하므로 실기 이식 시 명시적 writer기준 고정을 필수로 만드는 설계가 남는다.
- 이번턴 G1원격파일/모드/출력 변경없음. 다음은 실제Controller에 이식하기 전 lock순서와
  모든안전검사 연결의 코드 검토다. 외부검사bool만 true로 두고 실기실행하지 않는다.

## 최신 상대 정렬 C++ 시험용 결합 완료 (2026-09-08)

- anchored_upper_study.hpp 추가. 기존 UpperTargetOffline의 별도 사본으로 JSON 검증,
  입력순서/timeout/배치검증/latch 경로는 유지하고 goal을 C0+(V-V0)로 변환한다.
  첫 active 배치는 모두 검증하되 명령은 그대로 유지, 세션 중 V0는 고정한다.
  입력관절 및 변환후 관절한계(.05margin), ±10도변화, .08rad/s·dt20ms 제한 적용.
- split_vr_adapter_study.hpp가 이 시험용 클래스를 사용하도록 변경. production native와
  원래 UpperTargetOffline/InputValidator는 변경하지 않았다. 실제 인터페이스 의미 변경도 적용 안 함.
- test_split_vr_adapter_study.cpp 확장 후 MSVC /W4 /WX 컴파일·실행 exit0.
  실측offset .03rad 첫명령불변, 이후 .003rad 상대이동/초과없음/속도/다른축유지,
  고정anchor, 변환후관절한계초과시 미갱신 및 latch, 기존JSON/정렬/시작timeout/입력timeout/해제 검증.
  증거 logs/test_results/twist2_relative_cpp_study_20260908.json.
- 앞 단계 절대입력 시험 기록은 당시 이력이며 현재 시험용 adapter는 상대변화량 방식이다.
  C0-실측 하중오차를 없애는 보상은 아니고 위치명령 연속성을 보존하는 가설이다.
  C0는 시험 생성자에 전달한 명령이며 실제 writer 마지막 명령과의 원자적 연결은 아직 없다.
- 실제native/G1 원격 파일/모드 변경·실행 없음. 현재 상대방식/관찰한계가 물리 검증된 것은 아니다.
  다음 실제 이식 전 검토 핵심은 writer 명령 기준 캡처 연결과 기존 외부 안전검사 연결이다.
  원격 임시폴더 추후삭제 미완료 유지.

## 최신 SDK없는 C++ 분리 ready 결합 시험 완료 (2026-09-08)

- split_settle_window.hpp / split_vr_adapter_study.hpp / test_split_vr_adapter_study.cpp 추가.
  기존 native adapter의 로컬 별도 사본에 관찰 창을 연결했다. 실제 native adapter는 수정하지 않았다.
  RawInputWatchOffline/InputValidator/UpperTargetOffline을 그대로 사용한다.
  연구 한계1초/.005rad/.01rad/dq.1/gyro.1/rpy.15는 생성자에 명시하며 물리 안전 기준이 아니다.
- MSVC /W4 /WX SDK없는 빌드 및 저장 simulation 패킷 기반 실행 exit0.
  고정 하중오차 .03rad에서 후보 ready, 외부검사실패 latch, JSON오류 latch,
  초기 engage 거부, 최초정렬불일치, right-only .08rad/s, 해제/입력timeout 및 시작15초timeout 검증.
  증거 logs/test_results/twist2_split_cpp_study_20260908.json.
- 외부검사 bool은 기존 R1/CRC/모드/건강/관절·토크 검사의 연결 지점이며 실제 연결은 하지 않았다.
  SDK/네트워크/publisher 없음. 관찰 창4096표본 상한 초과시 fail, 시간역행/비유한값도 fail한다.
- 이번 결합은 기존 절대 관절 입력과 UpperTargetOffline을 유지한다.
  anchored_alignment_study.py의 C0+(V-V0) 의미 변경은 이식하지 않았다.
  첫입력의 무변화 보장/상대정렬 완료로 오해하지 않는다. 기존 속도 제한은 적용된다.
- 문서 TWIST2_READY_GATE_REVIEW.md 갱신. 실제 native ready/물리 원본/원격 파일 변경 없음.
  추가 로봇 시험 없음. 다음 실제 적용 전에 상대입력 채택 여부와 관찰 한계의 물리 검증 범위를
  결정해야 한다. 현재 시험 통과만으로 실제 출력 승인을 대신하지 않는다.

## 최신 분리 준비 판정기 오프라인 검증 (2026-09-08)

- split_ready_study.py/test_split_ready_study.py 추가, 테스트10개 통과.
  전 관절 고정목표오차 대신 관절각 구간변화/dq/gyro/몸체 자세로 정지 후보를 관찰하고
  최초 VR목표-신선한 오른팔 실측 .025rad 정렬을 별도로 검사한다.
  R1/Select/B/외부검사실패/비유한값/20ms지연/상체 .25rad·1.5rad/s는 latch중단.
- 관찰 한계는 필수 명시 설정이며 물리기본값 아님. 1초,dq.1,gyro.1,rpy.15,rpy변화.01 조건에서
  관절변화 .002/.005/.01rad 민감도 비교:3회차 최초정지후보6.340/6.060/6.060초,
  후보420/434/434표본. 외부공통검사통과/최초입력=실측은 오프라인 가정이며 physical_ready=false.
- CRC/모드/건강/관절·토크한계/VR세션/시작15초·입력timeout은 기존 외부계층 책임으로 남는다.
  기존 실제 adapter와 연결하지 않았고 native ready/중단 조건은 변경하지 않았다.
- docs/TWIST2_READY_GATE_REVIEW.md에 설정·가정·한계 기록.
  로그 twist2_split_ready_tests_20260908.xml, twist2_diag3_split_ready_study_20260908.json.
- 다음은 SDK없는 C++에서 기존 입력/watchdog와 결합해 외부검사 누락/시작timeout/latch 보존 검증.
  G1 명령/원격 파일 변경/재시험 없음. 사용자 AI복귀 안정 확인 유지, 임시폴더 추후삭제 미완료.

## 最新 PC LowState 읽기 전용 수신 확인 (2026-09-08)

- 사용자가 capture_hg_readonly.py 직접실행, pc_lowstate_20260908_135226.jsonl 저장.
  이번턴은 저장로그 오프라인분석만 수행. DDS/모터/원격변경 없음.
- samples6000 제한으로5.986초에서종료, 실제표본구간5.970초. 10초완주 기록 아님.
  SDK 및 독립CRC오류0, 비유한값0, motor fault없음, tick역행0.
- 수신간격중앙값 .950877ms, 최대7.514403ms,20ms초과0.
  tick중복289개는 payload모두달라 단순동일패킷재전송으로단정못함.
  native의 중복tick거부를 적용한 새tick5711개 사이 최대간격도7.514403ms,20ms초과0.
- 최대dq .7153528rad/s, 온도55도. R1버튼0(읽기전용시험에서는필수아님).
  통신관찰결과를 preflight정지조건통과/모터안전성으로해석하지않는다.
- 분석 logs/test_results/pc_lowstate_20260908_135226_review.json.
  원본SHA d64a0fecd02242a878996b246e447662b080f7bab46a500566c98f9720493757.
- PC DDS수신이 가능한것을 실제확인. 절대편도지연/정책동시부하/500Hz송신/단절대응과
  Windows→WSL VR경로는미검증. 10초수신재시험시 --sample-limit 12000 지정필요.

## 最新 gyro 실측 포함 정책 재현 및 ready 분석 완료 (2026-09-08)

- compare_feedback_recorded_offline.py가 CSV의 gyro3축을 .25배로 사용하도록 확장.
  없으면 명시적0가정, 일부만 있거나 비유한 값이면 거부. test_feedback_gyro.py3개 통과.
  이전 코드의 항상0 처리와 달리 이번3회차는 gyro_sources=recorded_policy_state.
- 검증된 TorchScript로 WSL CPU 오프라인 실행 exit0. blend후487표본에서 현재 applied-feedback
  정책 출력 재현 잔차 최대2.44366e-6 action. 최대 기록action1.60072로 관측된 saturation없음.
  공식식 raw-feedback로 바꾼 민감도는 하체목표 최대 .01114984rad(10번),4번 .00086561rad.
  gyro누락 가정을 제거했지만 저장상태/이전action을 공급하는 비교라 폐루프/실제안전 검증은 아니다.
- 기존 ready재분석487표본 통과0.16번과23번 어깨 위치조건은487회 모두 실패.
  body자세/속도 proxy는485표본 통과하지만 실제 균형 승인 기준은 아니다.
- 상체 약1초 중첩437구간에서 각도변화최대 .0028882rad, 속도최대 .0720971rad/s,
  명령변화0, 구간최대목표오차 .031842–.031902rad. 작은 움직임과 고정 오차 구분이 다시 확인됐다.
- 증거 logs/test_results/twist2_diag3_feedback_20260908.json,
  twist2_diag3_ready_components_20260908.json, twist2_diag3_loaded_settle_20260908.json.
  정책입력재현은 양호하며 단순 gyro누락/feedback차이만으로 현재 큰 오차를 설명할 근거는 없다.
- 로봇 명령/원격 파일 변경/물리 재시험 없음. 사용자가 AI복귀·안정 확인한 상태를 유지한다.
  실제 native ready/게인/FF/feedback은 바꾸지 않았다. 다음 설계 초점은 기존 위치추종 ready를
  하중 후 정지 관찰 및 VR최초정렬과 분리하는 것이며 같은 진단시험 반복은 우선하지 않는다.

## 최신 사용자 AI 복귀 및 안정 확인 (2026-09-08)

- 진단3회차 종료 이후 사용자가 직접 AI로 복귀시켰고 다시 안정적이라고 확인했다.
  이는 사용자 확인이며 이번 턴 별도 CheckMode 조회는 하지 않았다.
  아래 진단 직후 AI미복귀/안정 미확인은 당시 이력이다.
- 추가 로봇 명령·물리 재시험 없음. 다음 작업은 회수한 gyro 포함 기록의 오프라인 분석이다.

## 최신 진단 물리3회차 종료 / R1 유지 확인 (2026-09-08)

- 사용자에게 지지·양발접지·R1 유지와 전신 최대15초 진단1회 범위를 안내하고 `응` 확인 후 실행.
  시작 전 CheckMode0/ai, 새 ELF2af67725...65ef16와 정책 해시 일치, 관련프로세스/5013 없음 확인.
  preflight 및 warmup 통과, ReleaseMode 후 전신 출력. VR입력/Quest/relay 실행 없음.
- vr_wait_tracking 후 startup_ready_timeout. mandatory damping3초 완료 안내 뒤 Ctrl+C로 종료.
  정책736표본, lowcmd12172개, 평균500.001191Hz/최대간격4.149088ms,
  handler최대2.114688ms. damping포함 송신 약24.34초이며 총출력15초 이내가 아니다.
  inference최대5.051552ms, roll최대.024851/pitch최대.106661rad.
  계측부하 인과는 분리하지 않았고 전체 실시간 안정성 검증으로 표현하지 않는다.
- 원격 g1_twist2_right_arm_trial_1787638001.csv 및 동일이름.stop.csv 생성 확인/로컬회수.
  logs/test_results에 원래 파일명으로 보존. CSV SHA79c1ac667687639bd85cb65926ccc939971b1c3fa9231a99fd11de04cdef5350,
  stop SHAae6bd9a19dcc8c0caa6892637b4f288c37672da1df7f8e5d64f8ecac9f6eaa4e 양쪽 일치.
- policy514열/stop219열 정상 파싱.736표본에서R1off0, motorstate비0표본0,
  모터전압47.5–49.0V/두온도값최대50. 배터리SOC나 무선품질 판정은 아니다.
  stop reason startup_ready_timeout, remote_buttons1(R1), motorstate비0없음.
  supplied_context0: watchdog에서 최신 수락 상태를 저장한 것. 표본획득시 age .000704ms.
  gyro3축도 실제값 저장 확인. R1 눌림을 이번 표본과 중단snapshot 범위에서 확인했다.
- 종료후 native프로세스/5013 없음 및 SSH 종료. CheckMode0/form0/name빈값, AI복귀 없음.
  지지 유지 안내. 현재 실제 안정상태 사용자 확인이 남아 있다. 자동재시험 없음, 이번1회 승인 사용완료.
- 증거 twist2_diag3_terminal_20260908.json, twist2_diag3_audit_20260908.json,
  twist2_diag3_mode_before_20260908.json / mode_after. 모두 logs/test_results.
  새 원격 CSV2개도 임시폴더 추후 삭제 대상. 아직삭제없음. 원본 제어파일 변경없음.
- 다음은 새gyro가 포함된 기록으로 정책 비교/ready 설계를 오프라인 검토한다.
  VR 팔 조작 성공이 아니며 같은 진단 반복을 자동 진행하지 않는다.

## 최신 G1 재연결 / state-stop 진단 원격 빌드 완료 (2026-09-08)

- 사용자가 재연결 완료를 알림. 192.168.123.164 SSH 접속, 기존 임시 폴더 실경로와
  이전 ELF2d9614eb...8ee9b, 원본 물리 ELF해시 확인. native 실행 프로세스 없음 확인.
- 승인된 임시 소스 전송·컴파일 범위에서 state_stop_patch.tar.gz를
  /home/unitree/g1_vr_native_review_20260908에 전송. archive SHA52826afc...176fa1 및
  STATE_STOP_PATCH_MANIFEST.json의 소스3개 해시 검증 모두 통과.
- G1 cmake --build build --clean-first -- -j1 exit0, 실제 컴파일·링크와 ARM aarch64 ELF 확인.
  새 진단 ELF SHA256 2af67725e0f8c36f6cb11a11c58673edbe6fc7c7b5113c3832d5c4489065ef16.
  로그 logs/test_results/twist2_g1_state_stop_build_20260908.log.
  SDK/Torch 경고와 시계 차이 경고는 보존했고 시계 설정은 변경하지 않았다.
- 기존 물리 ELF a3c1e936...b974f60 / 로컬 원본 물리 C++ E61D8A3C...CC09F 유지.
  제어 바이너리 실행/publisher 생성/모드 전환/물리 출력 없음. SSH 빌드 세션 종료.
  현재 AI 모드나 실제 지지 상태는 이번 빌드 작업에서 조회·확인하지 않았다.
- 새 원격 manifest/패치/headers/build는 기존 임시 폴더 추후 삭제 대상에 포함한다.
  아직 삭제하지 않았다. 패키지 생성 당시 JSON은 미전송 이력이며 최신 상태는 이 항목과
  twist2_g1_state_stop_build_result_20260908.json을 사용한다.
- 실제 telemetry/중단 snapshot 기록과 실시간 부하는 미검증. ready 조건은 그대로라
  이번 빌드 완료가 VR 조작 가능/ready 원인 해결을 뜻하지 않는다. 물리 시험 자동 실행 안 함.

## 현재 다음 연결용 진단 패치 패키지 준비 완료 (2026-09-08)

- logs/test_results/twist2_state_stop_diagnostic_patch_20260908.tar.gz 생성.
  SHA52826afc6ea48dacd217a986bc586a9cc2f4a616fbc9ce55cbe21d816c176fa1.
  native C++/state audit/stop audit와 manifest 총4파일, archive 경로/정규파일/바이트 해시 검증.
  기존 임시 폴더용 증분 패치이며 독립 배포 전체가 아니다. 실행 스크립트/정책/SDK 없음.
- docs/TWIST2_DIAGNOSTIC_PATCH_READY.md에 대상·이전 ELF 해시·검증 후 전송/clean-first 빌드·
  미실행 범위·원격 정리 의무를 기록했다. 패키지 manifest는
  logs/test_results/twist2_state_stop_diagnostic_package_20260908.json.
- G1 전원이 꺼져 있어 SSH/전송/원격 빌드/실행을 시도하지 않았다.
  이 패치는 기록 보강이며 ready 실패 해결/실제 VR 조작 가능 선언이 아니다.
- 다음 장비 연결 시 패키지 일치와 기존 원격 버전을 확인한 뒤 승인 범위에서 빌드 가능.
  추가 물리 시험은 별도이며 이전 1회 승인을 재사용하지 않는다. 임시 원격 폴더 삭제 미완료.

## 현재 최초 중단 상태 snapshot 로컬 구현 완료 (2026-09-08)

- native_stop_audit.hpp 추가. damping 최초 latch 이후 동일한 command/reason 잠금 아래
  상태를 한 번 복사한다. 이후 latch/damping 상태로 덮어쓰지 않는다. latch 안 파일 I/O 없음.
  writer 상태 검증/명령제한 오류는 해당 writer snapshot을 전달하고, policy 예외는 해당 반복의
  snapshot을 전달한다. 제공 표본이 없는 watchdog/계획 종료 등은 최신 수락 상태를 별도 표시한다.
- controller.finish 이후 기존 CSV와 같은 이름의 `.csv.stop.csv`에219열 저장:
  reason/planned/captured/supplied_context/age_at_snapshot_ms, rpy, NativeStateAudit124열,
  q/dq/tau29축. age는 표본 획득 당시이며 latch시점 나이로 오해하지 않는다.
  supplied_context는 해당 반복의 상태이지 모든 오류의 원인이 상태였다는 뜻은 아니다.
- CRC거부 원문/무선 RF상태/전원상실/프로세스 강제 종료는 보존하지 못한다.
  handoff전 예외처럼 이 latch 경로에 진입하지 않은 실패는 snapshot 파일이 없다.
  정상/계획 종료도 첫 latch 문맥을 저장한다. 전원 종료 전에 디스크 기록이 보장되는 구조는 아니다.
- test_native_state_audit.cpp 확장: 첫 상태 보존, 이후 변경/재호출 불변,
  219열 헤더/데이터 일치 검증. MSVC /W4 /WX 빌드·실행 exit0.
  WSL SDK/Torch 로컬 빌드·링크 exit0, logs/test_results/twist2_stop_audit_build_20260908.log.
- 로컬 초안 SHA6507A1B8E2F557A946FAFD7110E9E7A9259095FBA4075A20B5A40657486F3739.
  원본 물리 C++ E61D8A3C...CC09F 유지. ready/FF/게인/feedback 및 중단 조건 변경 없음.
  G1 전송/빌드/실행 없음. 원격은2d9614eb...8ee9b 버전 그대로이며 추후 삭제 의무 유지.
- 실제 오류 발생 시 기록과 기록 추가에 따른 실시간 부하는 아직 미검증.
  전원 꺼진 현재 로컬 진단 준비까지 완료했으며 동일 물리 시험 자동 재실행하지 않는다.

## 현재 LowState 진단124열 로컬 준비 완료 (2026-09-08)

- native_state_audit.hpp 추가, 로컬 twist2_vr_native_draft.cpp의 Sample/CSV에 연결.
  같은 policy LowState의 tick/CRC/mode_pr/mode_machine/버튼비트, gyro3축,
  29모터 vol/temperature[0,1]/motorstate를 기존 CSV 끝에124열 추가했다.
  writer snapshot과 policy snapshot을 구분한다. motor vol은 BMS잔량이 아니며 버튼비트는 RF세기가 아니다.
- test_native_state_audit.cpp MSVC /W4 /WX 컴파일 및 실행 exit0.
  기존 hg_classes_only fixture로 29축 CSV 열/값 일치, signed온도/32bit tick,
  버튼비트 및 복사 후 독립성 확인. WSL SDK/Torch 로컬 빌드·링크 exit0.
  증거 logs/test_results/twist2_state_audit_build_20260908.log 및 state_audit_validation JSON.
- 원본 물리 C++ SHA E61D8A3C...CC09F 유지. 로컬 초안 SHA
  6FE2E506781BBC910477D7891D3D2F5898BB7F4E951032EBF325DDD636364D8E.
  G1에는 전송/빌드/실행 안 함. 원격은 여전히2d9614eb...8ee9b 버전이다.
- 진단은 검증을 통과해 기록되는 policy 표본만 포함한다. 오류를 일으킨 표본/전체500Hz
  기록은 없으며 R1해제·fault 순간이 반드시 CSV에 저장되는 것은 아니다. 오류 snapshot 미구현.
  실제 기록 부하/모터전압 값/gyro 포함 재비교는 새 실기록 전까지 미확인이다.
- ready/게인/FF/정책 feedback/물리 중단 동작 변경 없음. G1 전원 꺼짐 유지.
  임시 원격 폴더 추후 삭제는 미완료. 다음은 필요 시 오류 snapshot 진단과 새 버전 G1 빌드이며
  전원이 꺼진 동안 원격 작업을 시도하지 않는다.

## 현재 하체/공식 정책 경로 검토 및 CPU 비교 (2026-09-08)

- 공식 TWIST2 commit d5c7108e9ef82d1b8770e5b692f27a1294f3aa8a의 config/server/wrapper를
  Windows logs/test_results에 읽기용 저장. 관절0..28 매핑·기본각·Kp/Kd 자동 비교 일치.
  관측 순서/배율/발목dq0/history10도 일치. 공식1432식의1402 주석은 산술 오기.
- 중요한 구조 차이: 공식은 이전 raw policy출력을 feedback하고 전29축 적용,
  현재 C++는 고정/VR상체와 합친 명령을 action으로 환산해 feedback한다. 현재 동작은 변경하지 않았다.
  기록상 상체 feedback 차이 최대 .211045action. 공식ONNX/로컬TorchScript 변환 동등성은 미검증.
- compare_feedback_recorded_offline.py 추가. 검증된 정책으로 WSL CPU 로컬 실행 exit0,
  shape/finite 검사. 두 입력의 previous-action/history만 달리한490표본에서 하체 목표 차이
  최대 .013791rad(10번), 4번 .000914rad. gyro0/저장 action을 공급한 고정상태 비교이며
  실제 폐루프나 발목 오차 단독 원인 입증이 아니다. 정책/ready 수정 근거로 확대하지 않는다.
- 2회차 blend후 하체 q전체범위 최대 .004892rad, dq최대 .073709rad/s.
  4/10번 예측토크는 최대16.555/12.417Nm, 소프트 한계까지 표본여유8.445/12.583Nm.
  실제 토크용량/배터리/지지 안정 여유를 뜻하지 않는다.
- 문서 TWIST2_READY_GATE_REVIEW.md 갱신. 증거 logs/test_results의
  twist2_lower_policy_review_20260908.json 및 twist2_feedback_sensitivity_20260908.json.
  다음은 누락 gyro/전압/건강/입력 진단의 같은 시간축 기록 준비와 hybrid feedback 설계 결정.
  관측 로그 없이 같은 물리 시험을 반복하지 않는다. 원본/native 물리 코드·원격 파일 변경 없음.
  전원 꺼짐/원격 임시 폴더 추후 삭제 의무 유지.

## 현재 하중 후 상체 정지 관찰기 추가 (2026-09-08)

- review_loaded_settle.py/test_review_loaded_settle.py 추가, 테스트7개 통과.
  약1초 중첩 구간의 상체 각도 변화·속도·몸체 자세 변화·명령 변화·목표 오차를 분리 기록한다.
  표본 지연/비유한값/시간 단절/blend 미완료 시 구간을 끊는다. 실제 ready 결정/새 임계값 없음.
- 실기록1회322/2회440구간. 상체 각도 변화 최대 .001354/.004266rad,
  속도 최대 .042854/.047553rad/s, 상체 명령 변화0.
  구간 최대 목표 오차는 각각 약 .03244/.03217rad. 정지 오차와 실제 움직임을 구분했다.
- 지지된 상태에서의 표본 관찰이며 자유 상태 안정/전신 균형 검증이 아니다.
  구간은 중첩되며 독립 시험 횟수로 세지 않는다. 50Hz 사이의 연속 상태도 보장하지 않는다.
- docs/TWIST2_READY_GATE_REVIEW.md 갱신. 증거 logs/test_results의
  twist2_trial1_loaded_settle_20260908.json, twist2_trial2_loaded_settle_20260908.json,
  twist2_loaded_settle_tests_20260908.xml.
- 제어 원본/native ready/FF/게인 변경 없음. G1 전원 꺼짐/원격 임시 폴더 삭제 미완료 유지.
  다음 실제 연결 설계는 하체 안정, 하중 후 상체 관찰, 최초 VR 정렬을 분리해야 하며,
  현재 상체 관찰값만으로 실제 ready 허용 조건을 확정하지 않는다.

## 현재 어깨 FF 감소와 정지 오차 연결 확인 (2026-09-08)

- 2회차 writer 저장값을 capture/early blend/late blend/8–14초 구간으로 비교했다.
  16/23번 FF는 capture +1.4375/-1.4375Nm에서 blend 종료 후0.
  해당 구간 평균 위치오차는 .000093/.000022rad에서 .032142/-.030618rad으로 바뀐다.
  마지막 P 토크 +1.286/-1.225Nm. 하중 보상이 감소하면서 위치 오차로 토크를 만드는 설명과 부합.
  지지·접지 하중 변화까지 분리한 인과 시험은 아니므로 단독 원인 확정으로 과장하지 않는다.
- 현재 코드가 상체를 포함한29축 capture_tau를 (1-alpha)로 줄이는 것을 확인했다.
  Kp40과 ready오차 .025rad 조합은 P성분1Nm까지만 허용하므로 해당 어깨 정지 오차를 차단한다.
  상대 정렬만으로는 기존 상체 ready 실패가 해결되지 않는 이유가 구체화됐다.
- capture_tau 고정 유지/게인 증대/목표를 실측으로 점프시키는 변경은 하지 않았다.
  capture_tau는 순수 중력 보상으로 검증되지 않았다. 실제 힘/균형 개선도 검증되지 않았다.
- docs/TWIST2_READY_GATE_REVIEW.md에 표와 설계 결론 추가.
  증거 logs/test_results/twist2_trial2_load_transfer_20260908.json. 저장값 구간 평균 분석이며
  새 제어 코드 변경/테스트/원격 실행 없음. 기존12개 정렬 시험 결과와 별개의 관측 분석이다.
- 다음 작업은 하중 후 상체 정지 상태의 별도 관찰 진단이다. 실제 ready 출력 변경은 아직 보류.
  G1 전원 꺼짐/임시 원격 폴더 삭제 미완료 상태 유지.

## 현재 상대 정렬 가설 오프라인 검증 (2026-09-08)

- anchored_alignment_study.py 및 test_anchored_alignment_study.py 추가.
  첫 VR값을 신선한 실측과 .025rad 이내 비교하고 최초 명령 C0는 바꾸지 않는다.
  이후 C0+(V-V0)로 입력 변화량만 적용하는 메모리 모델이며 기준은 세션 동안 고정한다.
- 합성/저장 자세 시험12개 통과: 첫 명령 점프 없음, .08rad/s·dt20ms 상한,
  목표 초과 없음, 0..21 유지, 세션·순서·오래된 실측·비유한값·몸체 준비 거부,
  상대/매핑 관절 한계, 결측 freeze/250ms timeout, 해제/오류 후 latch.
  로그: logs/test_results/twist2_anchored_alignment_20260908.xml.
- 저장 CSV 10초 이후 자세에 합성 최초 입력=실측, body_ready=True를 가정한 시험이다.
  실제 입력 정렬/몸체 안정 승인 아님. 절대 관절값 추종에서 상대 변화량으로 의미가 바뀌며
  C0-실측 오차를 보존한다. 힘 변화/상체 오차를 해결했다는 뜻이 아니다.
- docs/TWIST2_READY_GATE_REVIEW.md에 식·가정·검증 범위와 이식 금지를 명시했다.
  JSON/R1/CRC/source age 검증을 대체하지 않는다. 실제 준비 조건은 변경하지 않았다.
- native 초안 SHA53DCE291...DE6CD8 및 원본 물리 CPPSHA E61D8A3C...CC09F 유지.
  G1 전원 꺼짐 상태에서 원격 작업/실행 없음. 임시 원격 폴더 삭제는 여전히 남아 있다.
- 다음 결정 항목은 상대 입력 의미 채택 여부와 몸체 안정 기준/상체 하중 오차 처리다.
  현재 가설만으로 실제 VR 팔 조작 가능 상태라고 결론 내리지 않는다.

## 현재 준비 조건 분리 설계 검토 완료 — 적용 안 함 (2026-09-08)

- docs/TWIST2_READY_GATE_REVIEW.md에 하체 안정 관찰/허리·왼팔 유지/첫 VR 오른팔 정렬/
  공통 중단 조건을 분리한 설계와 다음 구현 순서를 기록했다.
- review_ready_components.py 오프라인 분석기와 테스트3개 추가, 3개 통과.
  이전 policy행 목표를 사용하며 비유한 값·상태 지연·시간 단절은 표본 구간을 끊는다.
  실제 ready 승인값을 생성하지 않으며 publisher/네트워크 없음.
- 저장 실기록 재분석: 1회373/2회490표본에서 기존all29 통과0.
  body 자세/속도 proxy 최장7.36/9.78초 통과하지만 허리·왼팔 추종은 양쪽0.
  오른팔 추종은 1회373, 2회0. 하체 위치 조건만 제거해도 양쪽 모두 통과0이다.
  새 body proxy는 균형 안전 기준이 아니며 전 관절 fault/R1/접촉 하중 등 누락을 명시했다.
- 다음 핵심은 하중 후 실측과 첫 VR 목표의 정렬 상태 설계다. capture 목표 추종과
  첫 VR 목표-실측 정렬을 혼동하지 않는다. rebase 도입 시 연속성/힘 변화/속도 및 latch 검토 필요.
- 제어 코드·G1 파일 변경/실행 없음. 전원 꺼짐 유지, 임시 폴더 삭제 미완료.
  결과 JSON은 logs/test_results/twist2_trial1_ready_components_20260908.json,
  twist2_trial2_ready_components_20260908.json. 기존 변경사항은 유지했다.

## 최신 사용자 확인 — 접지 및 전원 종료 (2026-09-08)

- 진단 당시 Unitree 제공 지지대에 어깨가 묶여 있었고 양발은 지면에 닿아 있었다고 확인했다.
  지지대와 양발 사이의 실제 하중 분담은 미측정이다. 접촉을 정상 체중 부하로 단정하지 않는다.
- 현재 배터리 부족으로 G1 전원을 껐다고 사용자 확인. 원격 연결·물리 재시험을 시도하지 않는다.
  시험 당시 배터리 상태는 확인되지 않았으므로 이번 발목 오차 원인으로 단정하지 않는다.
- 다음 작업은 저장된 로그를 이용한 하체 안정 판정과 최초 VR 팔 정렬 조건의 분리 설계 검토다.
  기존 ready/R1 조건을 임의로 완화하지 않는다. G1 임시 폴더 삭제 의무는 남아 있으며
  전원이 꺼진 현재 삭제 완료로 기록하지 않는다.

## 현재 발목 정지 오차 오프라인 분석 (2026-09-08)

- 새 실기록의 blend 완료 후490표본을 이전 policy행 desired와 비교했다.
  29축 .025rad/.1rad/s 준비조건 통과0. 2/3/4/8/10/16/23축은 위치조건을490회 모두 초과.
  이는 R1 원인 판정이 아니며 순간 속도만의 문제도 아니다.
- writer 기준 4번 목표 평균 .116362rad, 실측 -.290048rad, dq평균 .001116rad/s;
  10번 목표 .074459rad, 실측 -.231438rad, dq평균 -.001119rad/s.
  같은 구간 policy행 tau_est 평균은 각각16.098Nm/12.043Nm.
  writer Kp40, Kd2 및 목표 오차로 계산한 정적 PD값 약16.256Nm/12.236Nm과 유사하다.
  tau_est는 같은 writer 순간값이 아니므로 구간 평균 비교로만 해석한다.
- 추론: 하중을 받으며 토크를 만드는 정지 평형일 가능성이 있다. 단순히 명령 미전달/고장으로
  단정할 근거가 없다. 지지·발 접촉·실제 하중은 CSV만으로 알 수 없어 사용자에게 질문했다.
- 코드의 action→기본각+.5*action 변환과 CSV 하체 desired의 최대 차이는2.15e-8rad.
  SDK 상태와 명령은 같은 인덱스를 사용하고 mode_pr0을 검증한다. 다만 이것만으로 학습 모델의
  관절 순서·훈련 설정과의 외부 일치를 새로 검증한 것은 아니다.
- 현재 all29 위치오차 .025rad ready조건은 정적 PD 하중 오차까지 막는다.
  발목 Kp40에서 .025rad은 정적 P성분1Nm에 해당한다. 이를 곧바로 임계값 완화 근거로 삼지 않는다.
  다음은 실제 접지/지지 조건 확인 후 하체 안정과 VR 최초 팔 정렬 조건을 구분해 설계 검토하는 것.
- 증거 logs/test_results/twist2_writer_trial2_ankle_diagnosis_20260908.json.
  이번 턴은 기존 CSV/코드 검토와 로컬 결과 저장만 수행. 제어 코드/원격 파일 변경·물리 재실행 없음.

## 현재 writer 물리 진단 2회차 종료 (2026-09-08)

- 사용자가 새 진단 진행 및 현재 지지/R1 준비에 `준비` 응답. 혼자 R1 유지 조건으로
  승인한 1회만 실행했다. VR 송신기/relay는 실행하지 않아 engage 입력은 없었다.
- 실행 전 CheckMode code0/form0/nameai, 진단 ELF 2d9614eb...8ee9b 및 정책 해시 일치,
  관련 native 프로세스/5013 점유 없음 확인. eth0, --policy-seconds 10 --vr-right-arm.
  native preflight와 실측 warmup 통과 후 실제 ReleaseMode 및 전신 lowcmd 출력 수행.
- 739 정책 표본, vr_wait_tracking 후 startup_ready_timeout으로 damping latch.
  필수 3초 tail 완료 안내를 확인하고 Ctrl+C로 연속 damping 종료. 재실행하지 않았다.
  lowcmd 12853개, 평균 500.003569Hz, 최대 간격 2.397728ms, writer handler 최대 .430848ms.
  damping 포함 송신은 약25.7초이며 전체 출력이15초 이내였다는 뜻이 아니다.
  최대 roll .022012rad / pitch .095963rad. VR 팔 조작 성공 또는 실제 안전성 검증이 아니다.
- 종료 후 native 프로세스/5013 점유 없음, SSH 종료. CheckMode code0/form0/name빈값.
  AI 자동 복귀 없음. 지지 유지 안내했으며 현재 실제 안정 상태는 사용자 확인이 남아 있다.
- 원격 CSV g1_twist2_right_arm_trial_1787641818.csv를 로컬
  logs/test_results/twist2_writer_trial2_20260908.csv로 복사. 양쪽 SHA256
  8b59b53d5e8000b9fa4815d25687345d1e9189a5c1b57752e1181dec9ceb5082 일치.
- compare_native_writer_csv.py로 실기록 분석: 고유 writer 표본739, SDK거부0,
  표본 내 damping0. 모든 축에서 제한 전/후 목표 차이0(저장 정밀도 범위).
  명령-실측 최대오차 4번 .462393rad, 10번 .353576rad, 16번 .032166rad,
  23번 .030644rad. 기록된 표본에서는 큰 발목 오차를 writer 제한으로 설명할 수 없다.
  50Hz 표본이므로 전체500Hz 제한 개입 부재/로봇 ACK/모터 고장으로 확대 해석하지 않는다.
- 증거: twist2_writer_trial2_terminal_20260908.json, twist2_writer_trial2_comparison_20260908.json,
  twist2_writer_trial2_mode_before_20260908.json 및 mode_after 파일. 모두 logs/test_results 아래.
- 다음은 하체 정책 목표와 지지/접지 상태·좌표/관절 매핑 검토다. ready 기준을 임의 완화하지 않는다.
  이번 1회 승인은 사용 완료. 추가 물리 출력 없음. 원본 소스 수정 없음.
  임시 G1 폴더 추후 삭제 대상에 이번 CSV도 포함한다. 아직 삭제하지 않았다.

## 현재 writer 진단 초안 G1 빌드 완료 — 실행 안 함 (2026-09-08)

- 기존 승인된 임시 폴더 `/home/unitree/g1_vr_native_review_20260908`에
  `writer_audit_patch.tar.gz`를 전송하고 SHA256 검증 후 초안 C++ 한 파일만 갱신했다.
  패치 SHA256: 27073e5d9ca676b210b57a1c2bd4a6575fc17cf921920ce011464f424ccc8e37.
- G1에서 `cmake --build build --clean-first -- -j1` 컴파일·링크 exit 0.
  ARM aarch64 ELF 확인. 새 바이너리 SHA256:
  2d9614eb88ecdfb3115282649aaf3405a840057c43f3d2a13529e03d4c68ee9b.
  원격 소스 SHA256 53dce2913dd9a1aca6f56d2b1b5e9907dea66c80ba8be212bc9ae8c0aede6cd8은 로컬과 일치.
  증거: `logs/test_results/twist2_g1_writer_audit_build_20260908.log`.
- SDK/Torch 경고와 시계 차이 경고는 로그에 보존했다. clean-first 후 실제 컴파일·링크를 확인했으며
  시계 설정은 변경하지 않았다. 기존 물리 바이너리 SHA256 a3c1e936...b974f60 및
  로컬 원본 물리 C++ SHA256 E61D8A3C...CC09F 유지. 다른 작업은 되돌리지 않았다.
- 이번 단계는 빌드만 수행했다. 바이너리 실행, publisher 생성, 모드 전환, 물리 출력은 없다.
  앞 단계 로컬 분석 테스트 2개 통과는 유지되지만 새 실제 writer CSV/실시간 부하 검증은 아직 없다.
- 다음 필수 항목: 새 물리 진단 시험의 명시적 승인과 현재 지지/R1 준비 확인 후,
  제한 전 목표·제한 후 명령·같은 writer 시점 실측을 수집해 ready 미충족 원인을 구분한다.
  이전 1회 물리 승인은 재사용하지 않는다. R1/ready 기준은 완화하지 않았다.
- 추후 삭제 범위는 기존 임시 폴더 전체이며 이번 `writer_audit_patch.tar.gz`와 새 build도 포함한다.
  아직 삭제하지 않았다. 최초 SOURCE_SHA256.json은 이전 소스 기록이므로 현재 버전 명세로 사용하지 않는다.

## 현재 writer 목표 분리 기록 추가 — 로컬 빌드만 (2026-09-08)

- physical1 CSV에는writer 제한후명령/같은writer시점상태가없다. 50Hz정책샘플로
  500Hzwriter의rate/torque제한을정확히복원하지않는다. 기존발목오차만으로모터추종불량을단정하지않는다.
- 별도twist2_vr_native_draft.cpp에WriterAudit 추가. SDK Write호출반환후기존stats_mutex 아래
  최근완료시도sequence/accepted/damping/tick/시각 및29축 desired,target,q,dq,kp,kd,ff 저장.
  policy CSV는해당snapshot/age를복사한다. 새로운policy행desired와혼동하지않는다.
  sequence0은완료시도없음. 50Hz표본이며모든500Hz명령기록/로봇수신확인은아니다.
- SDK bool반환을기록하지만기존제어동작은변경하지않았다. 현재false반환만으로별도latch하는
  기능은없다. 실제송신성공/ACK라고과장하지않는다. 새기록부하의실시간영향은미측정이다.
- compare_native_writer_csv.py 추가:구버전은insufficient_evidence,신규는중복시도제외,
  SDK거부/damping분리후writer기준 policy-state/command-state/limiter delta/PD예측값비교.
  구CSV를추정명령으로채우지않는다. 신규분석테스트2개통과.
- WSL SDK/Torch 컴파일·링크exit0, ELF SHA256
  bafda45343ba9726b0059110a804abd9ff83cf75bf086a48c7c64c48b7bea6e1.
  증거 twist2_writer_audit_build_20260908.log, twist2_physical1_writer_evidence_20260908.json.
  G1임시폴더에는전송하지않았다. 원격실행파일은여전히ef24e203...718dba.
  물리재시험/R1·ready기준변경/AI모드변경없음. 원본물리C++해시E61D8A3C...CC09F 유지.
- 남은것은진단초안의G1빌드및새로운명시적물리시험에서제한후명령기록확보다.
  이전물리1회승인을재사용하지않는다. 임시G1폴더/CSV의추후삭제의무유지.

## 현재 사용자 AI 복귀 / R1 유지 / ready·relay 원인 진단 (2026-09-08)

- 사용자는 혼자 조작하되 R1 유지 방식으로 진행하기로 했다. 이후 직접AI로복귀했다고 알림.
  query_motion_mode.py 읽기전용 조회code0/form0/nameai 확인:
  twist2_user_ai_restored_20260908.json. 새물리시험실행/모드변경은 하지 않았다.
- physical1 CSV를실제gate와같은 이전desired 기준으로재분석(저장소수정밀도범위).
  blend후373샘플중전체29축 q오차<=.025/dq<=.1 만족샘플0.
  2/3/4/7/8/10/16축 q오차는전샘플초과. 특히4번 .400~.427rad,
  10번 .320~.341rad. 단순속도한샘플문제가아니며 gate조건완화하지 않았다.
  desired는writer clamp전목표이므로 이것만으로실제모터고장/송신목표추종실패를단정하지 않는다.
  다음진단은writer가실제로제한한목표와비교하여정책desired/명령/실측을구분하는것이다.
- relay의세션없는합성idle 패킷에서 non-empty session_id 거부재현.
  이전physical1원문은없어서1889개원인확정은아니다. 입력없음/Unity상태가능성과구분한다.
  기존relay동작/거부정책은유지하고rejection_reasons집계및최초사유console기록추가.
  사유길이/종류개수를제한하며원문패킷/비밀은로그에추가하지않는다.
  relay tests10개통과(새main진단시험은mock소켓,거부시송신0검증).
- 진단결과 twist2_ready_relay_diagnosis_20260908.json. 원본물리C++해시유지.
  G1임시폴더/바이너리는이번턴변경없음. R1해제차단/최초정렬/ready조건은유지.
  물리1회승인은이미사용됐으며자동재실행하지않는다. 임시폴더추후삭제의무유지.

## 현재 물리 1회 시험 중단 / 사용자 혼자 조작 방식 재검토 (2026-09-08)

- 사용자1회물리시험 승인 및지지/별도리모컨담당 준비완료 응답 후 실행했다.
  이후 사용자가 실제로 혼자이며 R1유지가 어렵다고 정정했다. 최신조건은 **혼자 조작**이다.
  별도담당 가정으로 재실행하지 않는다. 1회승인은 사용됐으며 자동재시도하지 않는다.
- 실행전 mode0/ai, 모델/ELF 해시 및5013 비점유 확인. 새 seed공급(2015samples/1375updates),
  Windows liveMink hardware-guarded/vanilla idle 확인, relay→G1:5013 구성.
  native P확인→SDK publisher 생성→preflight 통과→실측warmup→ReleaseMode→전신출력 실제 수행.
- native는capture49/blend200/vr_wait_tracking373 총622정책샘플, 마지막elapsed12.440079초.
  vr_ready/vr_active 없음. VR 팔조작 성공 아님. 오른팔desired변화6e-8rad 수준(CSV정밀도).
  별도진단에서 다수하체축/16번축 tracking 기준초과 확인. same-row비교이며
  이전desired/연속시간으로 판정하는 실제gate원인과 정확히 동일하다고 단정하지 않는다.
- 중단원인 RuntimeError: R1 deadman released. 필수3초damping 뒤연속damping 확인 후Ctrl+C.
  nativeexit1/쉘복귀, 관련프로세스및5013수신기없음 확인. lowcmd16787개,
  평균500.002Hz/최대간격4.513ms. 이수에는오류damping구간도 포함되며 총송신15초 주장은 금지.
  최대roll0.018787rad/pitch0.096227rad. 전신정책/인계/중단이 실제수행됐다는 범위만 확인.
- 종료후 CheckMode code0/form0/name빈값: AI복귀없음. 사용자에게지지유지 안내.
  안정적으로지지돼 있는지 질문에 사용자는혼자조작조건을정정했으며 현재안정성답변은미확인.
  AI복귀/새제어실행을 임의로 수행하지 않는다. R1고정/검사제거도 하지 않았다.
- relay는accepted0/rejected1889로종료. 실제관절목표패킷은전달되지않았다.
  거부원문/사유는없어원인미확정. 현재단독조작입력구조와함께실행전연결문제로남긴다.
- CSV /home/unitree/g1_vr_native_review_20260908/g1_twist2_right_arm_trial_1787640493.csv를
  로컬twist2_physical1_20260908.csv로복사, 양쪽SHA256 c881d87593e0c6ea1629766c80db8ad46be3f3c57560d96f2bf80506e8e2d34e 일치.
  터미널원문 twist2_physical1_terminal_20260908.json, 진단 twist2_physical1_audit_20260908.json,
  modebefore/after, relay JSON 보존. 원격CSV도임시폴더와함께추후삭제대상.
- 시험WindowsMink PID8340/34836을명령줄확인후종료, relay/seed정상종료,
  5005/5008/5012/5013 점유없음, SSH종료. Unity유지. 원본물리C++변경없음.

## 현재 실행 전 tick 신선도 수정 / 물리 시험 범위 제안 (2026-09-08)

- 현재 CheckMode0/ai, 정책원본SHA256463be037...e9015 및 G1 초안 해시 확인.
  ps 이름에서twist/trial 없음, root python3/master_service 존재.5013 비점유.
  특정 호스트프로세스 목록만으로 DDS 전체송신자 부재를 입증하지 않았다.
  증거 twist2_preexecution_inventory_20260908.txt / twist2_preexecution_mode_20260908.json.
- native on_state가 동일tick으로 state_received를 갱신하던 문제 수정.
  native_state_tick.hpp에서uint32 증가/wrap만 허용, 중복/역행은 상태/시각 갱신 없이 무시.
  반복이 지속되면 기존20ms 상태watchdog가 만료한다. 초기has_state 갱신도 같은mutex 내부로 이동.
- MSVC /W4/WX 및owner pytest7개, WSL 빌드 통과. 실측6000개 오프라인 적용:
  중복289무시/5711수용, fresh gap최대6.766ms/20ms초과0. 물리writer 검증 아님.
- 승인된 임시source/compile 작업을 이어 같은 G1 임시폴더에 수정2파일만 반영,
  clean-first/-j1 재컴파일 exit0. 새 ELF ef24e2038d1379dd1699071c475ff6166dcd7912600cd4e81101033a12718dba.
  기존 trial ELF a3c1e936...974f60 유지. clock-skew 경고 보존. 제어 바이너리 미실행.
  초기 SOURCE_SHA256.json/source.tar.gz는 최초버전 이력이다. 현재 변경은
  tick_patch.tar.gz(SHA256d8600268...9c6d6) 및로컬현재소스로 식별한다.
  cleanup목록에tick_patch.tar.gz/native_state_tick.hpp 포함. 임시폴더삭제의무 유지.
- 사용자가 지지 및 별도 리모컨 담당 준비 가능 확인. 실제로 배치됐다는 확인과 실행승인은 아직이다.
  docs/TWIST2_FIRST_VR_PHYSICAL_TRIAL.md에1회 policy10초(전체active최대15초),
  전신publisher/ReleaseMode/VR/CSV 생성 및 damping절차를 구체화했다.
  실제 출력은 이 제안에 대한 명시적 승인 전까지 실행하지 않는다.

## 현재 Windows→G1 UDP 진단 수신 확인 (2026-09-08)

- 사용자 진행 지시로 G1 ss -lun 읽기 전용 확인:5013 점유없음.
  로컬 probe_udp_receive_only.py를 검토하고 SSH stdin/python3 -B로 실행했다.
  G1에 스크립트/로그/pycache 파일을 만들지 않았다. SDK/제어 바이너리 import/실행 없음.
- 수신기는192.168.123.164:5013 exclusive bind, source192.168.123.99 및
  twist2.transport_probe.no_command.v1 진단 schema/순번만 검사한다.
  패킷은 schema/sequence/padding만 있으며 관절값/VR 명령이 없다. 수신기 자체는 송신하지 않는다.
- 첫 시도는SSH stdout 파일 반영 지연으로 ready 확인 실패, Windows 송신0/수신0 종료1.
  두 번째는1391bytes 3개 송신 중2개 수신/종료1. 20초 deadline 근처였으나
  마지막 미수신의 원인은 단정하지 않았다. 기존 결과를 삭제하거나 성공으로 덮지 않았다.
- 대기시간60초로 변경하고 readiness→송신을 같은 orchestration에서 즉시 수행한 재시험:
  3/3 수신, sequence/1391bytes/SHA256 모두 송신 원본과 일치, 수신기exit0.
  source192.168.123.99 확인. 이는 단발 진단이며 연속VR 통신/손실률/지연 보장이 아니다.
- 증거 twist2_g1_udp_ports_20260908.txt, twist2_udp_probe_20260908.jsonl(첫 실패),
  twist2_udp_probe_sent_20260908.json(2/3시도), twist2_udp_probe_sent_20260908_retry.json,
  twist2_udp_probe_verified_20260908.json(재시험 및이전2/3 원문).
  터미널 줄바꿈/중복 문자 제어열을 제거한JSON으로 송수신3개 해시를 독립 비교해 통과.
- 수신기with/socket.close 및프로세스exit0으로 종료. G1 제어 실행/모드 변경/모터
  publisher 생성 없음. 기존 임시빌드폴더는 이번 작업에서 변경하지 않았으며 삭제 의무 유지.
- 다음은 native제어 실행 직전의 신선한LowState/초기정렬/단일송신자 및인계·정지 절차 확인이다.
  실제 제어 실행은 이번 진단 승인에 포함되지 않는다.

## 현재 live_mink 로컬 중계 및 native 입력 계약 시험 (2026-09-08 후속)

- 실측seed공급(30초,1790samples/1385updates,exit0) 후 기존 live entrypoint를
  MuJoCo3.11/vanilla/hardware-guarded로 시작했다. Unity display=simulation 유지.
  새 live 생산이며 simulation_only/저장 패킷 재표기 아님. G1 모터 출력 없음.
- 실제 gate7_mink_wsl_relay.py가127.0.0.1:5008→127.0.0.1:5013으로만 전달.
  로컬 수신기 기록935개 모두live_mink, idle826/active108/pinch1.
  사용자 작게 움직이고 pinch 해제 완료 확인. shadow active_updates107/input_disengaged.
- audit_native_relay.cpp 추가: 소켓/SDK 없는 stdin 감사기로 실제 NativeRelay 계약 재사용.
  MSVC/W4/WX 빌드, 위935개 출처/token 통과, 잘못된token 거부 확인. 최대패킷1391bytes.
  C++ tick 재생active107/stopped16, 최대0.069205rad/s, 위반0.
- 시작 구간 relay rejected1130 보고. 이후accepted2000까지 rejected는1130 유지.
  기존 relay는 거부 사유/원문을 보존하지 않아 원인을 확정하지 않았다. 전체 무오류 주장은 금지.
  종료 직전 별도2초 raw입력→메모리sink 검사64개 통과/오류0. 초기 원인 증명은 아니다.
- relay를 종료 요청한 도구가exit1로 끝나 최종transport result JSON은 생성되지 않았다.
  수신기/감사/C++ 재생 결과는 정상 보존. 종료 코드 문제를 정상종료로 표현하지 않는다.
- 증거: twist2_live_relay_20260908_1/result.json 및samples.jsonl,
  twist2_live_native_audit_20260908_1.json, twist2_live_cpp_20260908_1/result.json.
- seed공급/수신기 종료, seed삭제 확인. 시험Mink PID38580/11984 명령줄 확인 후 종료,
  5005/5008/5012/5013 점유없음. Unity 유지. G1 제어 바이너리 미실행.
- 다음은 Windows→G1 실제UDP수신 검증 및native실행 직전 최신상태/정렬/송신자 확인이다.
  이번 검증은 Windows loopback까지이며 G1 네트워크 전달·동작·정지 검증이 아니다.
  원격 임시빌드폴더 삭제 의무 유지.

## 현재 Quest/실측 seed 정렬 시험 완료 (2026-09-08)

- 사용자 VR 가능 및 작게 움직이고 pinch 해제 완료 확인. G1 출력 없는 로컬 시험 수행.
  supply_lowstate_seed_readonly.py30초 공급(3409samples/1415updates, exit0) 중
  MuJoCo3.12 simulation-only/vanilla를 실측 seed session twist2-vr-20260908-1로 초기화.
  초기 seed freshness/configuration 검사 통과 후 UDP 시작. Unity 표시는simulation 유지.
- 로컬 shadow5263packets, active_updates113, input_disengaged 중단, 오류없음.
  기록 twist2_vr_shadow_20260908_092457_66377b9c. 첫 active 오른팔과 초기 seed 차이0,
  전체 기록 비대상0..21축과 초기 seed 차이0. metadata source=validated_lowstate_seed_simulation.
  이 비교는 시작 시 seed 기준이다. engage 순간 실시간 G1 자세 정렬은 검증하지 않았다.
- C++ 메모리 tick 재생 active113/waiting8415/stopped16, 최대rate0.08000000000000229rad/s
  (부동소수점 오차), overshoot/비대상 변경/중단 latch 위반0.
  결과 twist2_cpp_vr_20260908_1/result.json, 정렬 twist2_vr_alignment_20260908_1.json.
  재생은 첫 active Mink 기준이며 native SDK writer/실제 정책/물리 출력 시험이 아니다.
- provenance=simulation_only 유지. relay/native 물리 입구는 여전히 거부하며 재표기하지 않는다.
  live_mink 생산 경로와 실행 직전 실측 정렬은 남은 필수 항목이다.
- 처음 shadow 실행 시 지원하지 않는 --output-dir 인자로 실패하여 즉시 종료했다.
  이후 지원되는 --duration-s240으로 실행해 위 결과를 얻었다. 무관한 프로세스 종료 없음.
- 시험용 Mink PID12168/부모16588의 세션 명령줄 확인 후 두 프로세스만 종료.
  shadow/seed 공급기는 정상종료, seed 삭제 및5005/5008/5012/5013 점유없음 확인.
  Unity는 열어둠. G1 제어 바이너리 미실행. G1 임시빌드폴더는 추후 삭제 의무 유지.

## 현재 승인된 G1 대상 컴파일 / 임시 파일 삭제 의무 (2026-09-08)

- **완료 결과:** G1 configure/compile/link exit0, Built target 확인.
  ELF ARM aarch64, SHA256 cdc8e0ed235e4b19f95044c4be5837d7593e8f00350eef1dc43a665fdea6be9a.
  새 폴더에서 전체 컴파일/링크를 수행했으며 clock-skew 경고도 로그에 보존했다.
  제어 바이너리 미실행, 실제 정책 추론/VR/제어 주기 검증은 아니다.
  생성 파일 목록과 삭제 대기 상태는 logs/test_results/twist2_g1_native_build_20260908.json.

- 사용자가 소스 전송/컴파일을 승인했고, 나중에 삭제하도록 명시했다.
  G1 /home/unitree/g1_vr_native_review_20260908을 mkdir로 새로 생성했다.
  기존 경로면 실패하도록 했으며 기존 trial/SDK/Torch 폴더는 변경하지 않았다.
- 해당 폴더에 source.tar.gz 전송, SHA256
  824adb9ed843e0ac51331ca5f75e5688bbd27a8fa532daf36a31332543f2a8f1 일치 후 해제.
  BUILD_ONLY.sh를 실행하여 전용build 폴더에 configure 및 -j1 compile/link를 진행한다.
  제어 바이너리 실행/모드 변경/모터 publisher 생성은 승인 범위에서 제외한다.
- 삭제할 임시 원격 경로는 위 폴더 전체다. source.tar.gz, BUILD_ONLY.sh,
  SOURCE_SHA256.json, experiments/, references/, build/를 포함한다.
  이후 시험/작업에서 더 이상 필요 없을 때 이 폴더만 삭제하고 부재를 검증해야 한다.
  아직 삭제하지 않았다. 로컬 증거 로그와 원본 프로젝트는 삭제 대상이 아니다.
- G1 시계가 PC 소스 시간보다 뒤여서 tar/make 시간 경고가 발생했다.
  G1 시계는 수정하지 않았다. 원격 빌드 stdout/stderr는 로컬
  logs/test_results/twist2_g1_native_build_20260908.log에 보관한다.

## 현재 G1 내부 환경 확인 / 대상 빌드 묶음 준비 (2026-09-08)

- 사용자가 제공한 유선 SSH 계정으로 호스트 키 검사를 유지해 인증 성공.
  인증 비밀은 프로젝트 파일에 저장하지 않았다. 원격에서는 기존 파일/프로세스/주소만 조회했다.
- 실제 G1 aarch64, Ubuntu20.04.6, glibc2.31, /usr/bin/c++ 확인.
  eth0=192.168.123.164, wlan0=192.168.10.165. WSL x86_64 바이너리는 사용할 수 없다.
- 기존 Torch version.py:2.0.0+nv23.05, CUDA11.4. 기존 trial flags.make의 ABI=1,
  CMake3.16, gcc-ar-9 확인. SDK /home/unitree/unitree_sdk2-main,
  Torch /home/unitree/.local/lib/python3.8/site-packages/torch.
  SDK .git/HEAD는 없어 commit을 확인하지 못했다. Torch/제어 프로그램을 import/실행하지 않았다.
- 기존 trial ELF SHA256 a3c1e9368600d5e344b41d5ec4dc1df0b191d05e460c34b40f58e44c3b974f60.
  readelf로ddsc/ddscxx/torch_cpu/c10 및 해당RUNPATH 확인.
  프로세스 이름 목록에서twist2/trial은 보이지 않았지만 root python3/master_service 등이 있다.
  이 호스트 이름 목록만으로 단일 DDS 송신자 부재를 증명하지 않는다. 프로세스 종료 없음.
- 증거 logs/test_results/twist2_g1_native_inventory_20260908.txt.
- 로컬에 twist2_g1_native_bundle_20260908.tar.gz/.json 생성.
  quoted include를 재귀 수집한 소스/헤더/CMake11개와 SOURCE_SHA256.json, BUILD_ONLY.sh 포함.
  압축 항목 집합/내용SHA256 재검증. archive SHA256
  824adb9ed843e0ac51331ca5f75e5688bbd27a8fa532daf36a31332543f2a8f1.
- 승인 요청 범위: G1 /home/unitree/g1_vr_native_review_20260908 신규 폴더에만
  위 묶음을 전송/해제하고 BUILD_ONLY.sh로cmake configure 및 -j1 compile/link,
  ELF file/hash 확인. 폴더가 이미 있으면 중단하고 덮어쓰지 않는다.
  기존 SDK/Torch/물리 trial 폴더는 수정하지 않는다. sudo/설치/제어 바이너리 실행,
  모드 전환/모터 publisher 생성은 제외. 현재 전송/대상 빌드는 아직 하지 않았다.

## 현재 G1 내부 조회 — SSH 인증 필요 (2026-09-08 09:11 KST)

- 사용자 진행 지시로 기존 접속 단서를 확인했다. Windows known_hosts에
  192.168.123.164가 있고 기존 trial 경로의 사용자unitree로 읽기 전용 조회를 시도했다.
  `ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5
  unitree@192.168.123.164 uname -m`은 Permission denied(publickey,password).
  호스트 키 검사를 해제하지 않았고 비밀번호를 추측하지 않았다. 원격 명령 실행 전 인증 실패다.
- Windows .ssh에는known_hosts만 있고 WSL /home/user/.ssh는 없다.
  PuTTY 저장 세션은 기본 항목뿐이며 사용자/키 경로가 없다. 사용자의 SSH 인증 방법이 필요하다.
- 로컬 inspect_g1_native_readonly.sh 준비, WSL sh -n 문법검사 성공.
  SHA256 01EF2F146A92735DCB32DD2DDF6ECBA6AA1EF3C05A7FA7106DFE8580910BD07C.
  uname/getconf/os-release, 기존 trial ELF의file/hash/readelf, CMakeCache 의존 경로,
  ps 프로세스 이름과ip주소만 조회한다. G1에 복사하지 않고 인증 후 SSH stdin으로 전달할 용도다.
  실제 실행하지 않았다. ps 목록만으로 DDS 단일 송신자 부재를 증명할 수 없다.
- G1 내부 아키텍처/의존성/프로세스 확인과 대상 빌드는 여전히 미완료다.
  G1 파일 변경/제어 실행/빌드/모드 변경/모터 publisher 생성 없음.

## 현재 모드 조회 및 실제 seed 공급 확인 (2026-09-08 후속)

- 사용자 진행 지시로 검토한 query_motion_mode.py를 WSL eth3에서 실행했다.
  CheckMode만 호출하여 result_code0/form=0/name=ai 확인. 모드 변경 없음.
  RPC 조회 트래픽은 발생했으나 모터 명령 publisher/rt/lowcmd 출력은 없다.
  증거 logs/test_results/twist2_motion_mode_20260908_followup.json.
  이 조회는 당시 모드이며 실제 출력 직전 다시 확인해야 한다. 경쟁 송신자 부재 증거는 아니다.
- supply_lowstate_seed_readonly.py도 capture_hg_readonly.SelectInterface를 재사용해
  UP/LOWER_UP192.168.123.99/24 주소로 인터페이스를 선택한다. 고정eth2 제거.
  패킹/인터페이스2tests 및 seed writer/reader16tests 통과.
- 실제30초 state-only seed 공급 exit0: samples1690, updates1402.
  뒤늦게 시작한 Windows observer가765개 갱신 검증, errors0, 최대age69.77ms,
  종료 후 seed 삭제 확인. 양쪽 관찰 시간창이 달라765/1402를 손실률로 해석하지 않는다.
  공급 세션twist2-20260908-followup, 결과 twist2_seed_observed_20260908_followup.json.
  이번 시험은 Windows seed 전달 확인이며 Unity/Mink를 시작하거나 Quest 정렬을 시험하지 않았다.
  69.77ms는 simulation seed age이며 native20ms 상태 기준 통과를 의미하지 않는다.
- 기존 물리 시험 문서에서 실행 위치는 G1 내부
  /home/unitree/g1_right_arm_trial/build/g1_twist2_cpp_right_arm_trial, interface eth0였다.
  현재 G1 환경/아키텍처/SDK·Torch는 원격 조회하지 않았으므로 과거 기록을 현재 검증으로
  재사용하지 않는다. 단일 송신자 현황도 미확인이다. WSL 빌드는 G1 배포 완료가 아니다.
- 다음 실제 필수 작업: G1 실행 환경 및 송신자 읽기 전용 확인, 새 native 초안의 대상 빌드,
  Quest live 초기 정렬. 로봇 파일 생성/프로그램 실행은 이번에 하지 않았다.
  원본 물리 C++ SHA256 E61D8A3C...CC09F 유지, 다른 작업 되돌림 없음.

## 현재 USB 재연결 후 실제 상태 수신 복구 (2026-09-08)

- 사용자 USB 재연결 후 ASIX PnP OK/ProblemCode0, 이더넷4 Up100Mbps,
  Windows192.168.123.99 확인. WSL에서는 G1이 eth3으로 재배정됐고 eth2는 Wi-Fi다.
- capture_hg_readonly.py의 고정eth2를 제거했다. DDS 초기화 전에 ip JSON에서
  UP/LOWER_UP 및192.168.123.99/24가 일치하는 단 하나의 interface를 선택한다.
  없거나 중복이면 거부한다. 기존 읽기 전용 수집 범위 내 수정이며 SDK publisher/모드 호출 없음.
  패킹/인터페이스 재번호·누락·중복·DOWN 검사2tests 통과.
  수집기 SHA256 3F0812013F72B2AA78817711DA0A6D204A4A84C28E3DB45F6FDD9270C5D42C27.
- 기존 승인된 읽기 전용 수집을 WSL에서 재실행(outer timeout25s, 기본10초/6000개 제한).
  약6초에6000개 도달하여 exit0. SDK/독립CRC 오류0, 비유한값0, motor fault 보고없음,
  최대온도45, 최대|dq|0.069813rad/s. 수신간격 중앙0.944ms/최대6.049ms, 20ms초과0.
- duplicate tick289, backward tick0. 샘플마다 새 tick은 아니므로 수신 수를 신선한
  상태 수로 간주하지 않는다. mode_pr/mode_machine=(0,5)는 MotionSwitcher AI 확인이 아니다.
  버튼값0이며 제어 deadman/모드/명령 소유권 준비 완료로 판단하지 않았다.
- 증거 logs/test_results/twist2_hg_readonly_capture_20260908_replug.jsonl 및
  twist2_hg_readonly_review_20260908_replug.json. G1 파일/프로그램 실행, publisher,
  물리 출력, 드라이버/네트워크 설정 변경 없음. 기존 물리 C++ 변경 없음.
- 다음: 실행 호스트/단일 송신자와 모드 확인 및 Quest live 초기 정렬이다.
  supply_lowstate_seed_readonly.py에는 아직 고정eth2가 있으므로 그대로 실행하지 않는다.
  새 수집기의 주소 기반 선택을 적용하고 검증한 후 사용해야 한다. 이번에는 실행하지 않았다.

## 현재 장비 연결 점검 — USB Ethernet 오류 (2026-09-08 09:03 KST)

- 사용자가 G1 전원/유선 연결을 알렸다. Windows/WSL 인터페이스와 PnP를 읽기 전용 확인했다.
- ASIX AX88772A USB2.0 to Fast Ethernet Adapter(이더넷4,
  USB\\VID_0B95&PID_772A\\0001A6)가 Present지만 PnP Error/ProblemCode10,
  ProblemStatus3221225473이다. 드라이버3.18.19.1213, netax88772.inf.
  오류 원인은 아직 특정하지 않았다. 코드만으로 드라이버 손상/케이블 고장을 단정하지 않는다.
- Windows에192.168.123.x 주소 없음. Wi-Fi192.168.133.103만 정상 활성이다.
  WSL eth2 DOWN/주소없음, eth3 Wi-Fi주소 UP. 수집기의 고정eth2로 DDS 수집을 시작하지 않았다.
- 이전 기록의 이더넷3은 상세 확인 결과 PairVPN 가상 어댑터다. G1 USB 어댑터는
  현재 이더넷4 ASIX이며 이름만으로 인터페이스를 선택하지 않는다.
- 다음: 사용자에게 ASIX USB 어댑터를 PC에서 분리 후 다시 연결하도록 안내한다.
  이후 PnP code/물리 링크/IP/WSL 매핑을 재확인한다. 정상화 전 IP 강제 설정이나 DDS 실행 없음.
  장치 재시작/드라이버 설치삭제/네트워크 설정 변경/G1 접속/publisher 생성은 하지 않았다.

## 현재 연결 검토 결과 및 네이티브 입구 수정 (2026-09-08)

- 사용자 `하자`에 따라 대상 환경/Quest 입력/LowState 연결을 검토했다.
  Windows IPv4 목록에 192.168.123.x 없음. 이더넷3 Disconnected,
  활성 이더넷172.30.217.200 확인. G1 전원 상태는 알 수 없으며 로봇 접속은 시도하지 않았다.
- Mink 출력은127.0.0.1:5008. 기존 gate7_mink_wsl_relay.py는 loopback 입력을
  명시된 Linux 주소/5013으로 보내는 재사용 후보다. 새 native 수신기의 bind/source/port와
  실제 주소를 맞춰야 한다. 현재 목적지/방화벽/라우팅을 변경하거나 UDP를 실행하지 않았다.
- 저장 Quest packet은 command_provenance=simulation_only라 기존 relay가 거부한다.
  첫 호환성 시험이 이 이유로 실패했다. 저장 데이터를 live로 재표기하거나 제한을 풀지 않았다.
  별도 기존 합성 live fixture로 relay canonicalization→C++ 검사 호환성을 검증했다.
  실제 Quest live 경로 및 fresh LowState seed는 장비 연결 후 별도 확인해야 한다.
- native_relay_contract.hpp 추가: live_mink 출처, simulation_only 차단, replay-session 차단,
  실행별 relay token 일치를 native_vr_udp.hpp에서 검사한다. G1_VR_RELAY_TOKEN 필수이며
  relay --relay-token과 같은16..128 ASCII 영숫자를 사용한다. IP/token은 암호학적 인증이 아니다.
- native_vr_policy_adapter.hpp의 mutex 보호 Phase를 추가해 기존 vr_wait_or_active 표시를
  vr_wait_tracking / vr_ready / vr_active / stopped로 구분했다. ready 취소도 검증했다.
  표시가 실제 G1 준비를 입증하지 않으며 UI↔native 양방향 ready 동기화는 아직 없다.
- MSVC /W4 /WX 성공, owner 관련 pytest7개 통과. native 출처/token 거부5종,
  relay의 simulation 거부와 합성 live 패킷 전달, ready 취소/active/중단 표시를 확인했다.
  XML: logs/test_results/twist2_native_connection_20260908.xml.
- WSL SDK/Torch 재컴파일·링크 exit0. 빌드 로그:
  logs/test_results/twist2_native_connection_build_20260907.log (자정 전 시작 파일명).
  최신 ELF SHA256 ec356caef23b0adc908ddb1c0c689f35d368a6f8166996b656c27c4b0a413bd6.
  이전 빌드 manifest는 이전 소스의 이력이다. 제어 바이너리 미실행, DDS/publisher 생성 없음.
  원본 twist2_right_arm_trial.cpp SHA256 E61D8A3C...CC09F 유지. 다른 변경을 되돌리지 않았다.
- 다음 우선순위는 장비 연결 후 실제 실행 호스트/아키텍처/SDK·Torch 의존성과 신선한
  LowState 확인이다. G1 내부 실행인지 WSL에서 DDS 송신인지 실행 위치를 확정해야 한다.
  G1 파일/실행 변경은 하지 않았다. Controller 생성 시 publisher가 초기화되므로
  이 바이너리를 읽기 전용 점검기로 실행하면 안 된다. 아직 실제 조작 준비 완료가 아니다.

## 현재 작업 경계 — 사용자 재확인 (2026-09-07)

- Arm SDK weight1.0 시험에서 실제 상체 기울어짐이 발생했다. TWIST2 경로를
  준비 중이며 Arm SDK 문제는 **해결이 아니라 보류**다.
- TWIST2는 Regular를 유지하며 오른팔만 제어하는 구조가 아니다. 최종 구조는
  단일 `rt/lowcmd` 작성자가 하체 정책 출력과 상체 목표를 합치는 것이다.
- 현재 Windows C++ 수신기/후보 계산은 로컬 검증용이다. TWIST2 정책과 실제
  로봇에는 아직 연결하지 않았다. 테스트 통과를 물리 안전성 검증으로 표현하지 않는다.
- 저장 Quest shadow/재생의 초기 기준은 첫 active Mink 가상29축이다.
  최신 C++도 `first_active_mink_simulation_not_g1` 옵션으로 첫 검증된 active를
  캡처한다. 기존 config의 명시적 가상 baseline 옵션도 유지한다.
  어느 경로도 G1 LowState 초기화가 아니다.
- Unity/MuJoCo 화면은 기존 Mink 결과다. 새 C++ 후보를 시각화하는 화면이 아니다.
- UDP5008은 shadow/Gate7 dry-run 등이 공유할 수 없다. 실행 직전 점유 PID와
  명령줄을 확인하고 무관한 프로세스를 종료하지 않는다. 이번 시험 종료 후
  5005/5008/5012에 점유가 없음을 확인했다. 다음 실행 직전 다시 조회한다.
- 로컬 VR 시험은 simulation 표시 모드로 실행한다. 프로젝트 루트 PowerShell:
  `.\START_VR_HAND_TO_MUJOCO.bat --standard-mink --external-feedback`
  시험 전 hardware였던 표시 설정은 위 BAT가 simulation으로 변경했고 종료 후
  JSON으로 재확인했다. 사용자가 Unity Play/engage/움직임/pinch를 수행했다.
- 손목 미측정 진단값은 `wrist_limit_margin_unknown` 플래그로 표현한다.
  관련 소스보다 최신 Assembly-CSharp 빌드/assembly reload 성공 로그를 확인했고,
  이번 Play에서 손목 목표 표시가 정상이라는 사용자 확인을 받았다.
  flag true/false 분기별 별도 화면 비교나 C++ 후보 시각화 검증은 아니다.
- G1/WSL/DDS 실행, publisher 생성, 물리 출력 및 기존 물리 C++ 변경 금지 유지.

## 현재 승인된 WSL SDK 통합 빌드 완료 (2026-09-07 후속)

- 사용자가 Ubuntu WSL SDK/Torch 확인 및 컴파일만 승인했다. 이전 WSL 금지는
  이 범위에서 변경됐다. G1 접속/로봇 파일 변경/제어 바이너리 실행/publisher 생성은 제외다.
- WSL Ubuntu26.04 x86_64에 g++15.2만 있고 CMake/Torch/C++ SDK는 없었다.
  uv로 `/home/user/.venvs/twist2-vr-build`에 Python3.12.14, CMake4.4.3,
  Ninja1.13.2, Torch2.10.0+cpu를 설치했다. sudo 인증이 필요하여 시스템 설치는
  하지 않았고 기존 `.venvs/g1-teleop` 및 Python SDK 환경을 변경하지 않았다.
- 공식 unitree_sdk2를 `/home/user/twist2-vr-build-20260907/unitree_sdk2`에 clone,
  commit9754cd153af3da471b0fe5f3aa535e426fb11db3 확인. Torch C++11 ABI=True.
  native_vr_build/CMakeLists.txt로 configure 및 -j1 compile/link 성공.
  SDK 예제/제어 바이너리를 실행하지 않았다. G1/네트워크 제어 설정 변경도 없다.
- `/home/user/twist2-vr-build-20260907/build/g1_twist2_vr_native_draft`는 x86_64 ELF.
  file/readelf/sha256sum으로만 확인했다. SHA256
  82e5e55b39cd83840b1cc645e4afb6c7db39629cb7e079edbd519c4c9073cf33.
  G1용 바이너리/동일 SDK·Torch 환경 검증이 아니다. WSL x86_64 빌드 완료로 기록한다.
- 전체 빌드 로그를 보존하기 위해 clean build를 다시 수행했다. shell 종료코드 전달
  구문에서 별도 오류가 났지만 compile/link는 완료됐고, 후속 cmake build exit0 및
  최신 ELF 존재를 확인했다. 로그의 경고200건은 SDK/Torch/DDS와 기존 공통헤더1건.
  Torch maybe-uninitialized 등은 런타임 무해함을 확인한 것이 아니다.
- 증거: logs/test_results/twist2_native_wsl_build_20260907.log/.json.
  manifest에 SDK commit, 소스/ELF 해시, 아키텍처, 미실행 범위를 기록했다.
  원본 물리 C++ 해시는 기존 E61D8A3C...CC09F 그대로이며 다른 작업은 되돌리지 않았다.
- 다음 실제 연결 선행 조건: G1 대상 아키텍처/SDK/Torch 빌드, Windows 입력 목적지와
  실제 신선한 상태 연결, 명령 송신자/모드/인계 실패 및 damping 동작 확인.
  위 환경 변경 및 실행은 이번 컴파일 승인에 포함하지 않는다.

## 이전 네이티브 writer 충돌 수정 / Linux 빌드 대기 (2026-09-07 후속)

- 사용자는 G1 바로 조작에 필요한 후속 작업을 요청했다. 별도 네이티브 초안의
  배포 전 문제를 우선 수정했다. 기존 물리 원본은 변경하지 않았다.
- native_command_limits.hpp: 유한수/양의 gain 검사 후 rate/joint/torque 교집합만
  허용한다. twist2_vr_native_draft.cpp의 순차 clamp를 이 함수로 대체했다.
  목표는 전체 계산 완료 뒤 commit하며 한 축 실패 시 전체35슬롯을 damping으로
  덮어쓰고 이전 목표를 보존한다. 일부 축만 active인 실패 frame이 나가지 않도록 했다.
- stop latch와 최종 frame 결정/SDK Write에 같은 recursive mutex를 적용했다.
  이미 진행 중인 Write 취소가 아니며, SDK Write가 블로킹할 때의 지연은 미측정이다.
- ReleaseMode 예외/실패는 UNKNOWN/ABORT로 명시하며 active/VR loop 진입을
  하지 않는다. 자동 재시도나 경쟁 damping publisher 생성은 없다. 실제 로봇 모드
  복구나 안전 정지의 보장은 아니므로 현장 인계 실패 절차는 아직 확인이 필요하다.
- MSVC /W4 /WX로 공통 제한 함수를 빌드했다. 충돌2종/정상 제한/잘못된 gain
  검증 및 owner 관련 pytest6개 통과. 전체 Linux SDK 초안 빌드는 미실행이다.
  기존 원본 SHA256 E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F 유지.
- Windows PATH에서 cmake/clang++/docker를 찾지 못했다. 과거 WSL inventory에는
  Python SDK만 확인돼 있어 현재 C++ SDK/Torch 환경 확인이 먼저 필요하다.
  사용자 지정 WSL 실행 금지가 유지되므로 WSL 환경 확인/컴파일만 허용할지 요청한다.
  G1 접속, 로봇 파일 변경, DDS/publisher 생성, 바이너리 실행은 이 빌드 범위에 포함하지 않는다.

## 이전 우선순위 변경: 네이티브 VR 통합 초안 (2026-09-07 후속)

- 사용자가 작은 오프라인 작업의 반복을 지적하고 필요한 작업부터 요청했다.
  기존 물리 C++를 직접 검토해 SDK 송수신/네이티브 정책/ReleaseMode/damping이
  이미 있음을 확인했다. Windows harness 확대 대신 기존 네이티브 경로에 VR을
  붙이는 작업으로 우선순위를 변경했다. 상세는 docs/TWIST2_NATIVE_VR_REVIEW.md.
- 원본 해시를 확인한 뒤 별도 twist2_vr_native_draft.cpp를 만들었다. 기존 Controller/
  SDK writer/정책 경로를 재사용하고 키보드 입력을 native_vr_udp.hpp와
  native_vr_policy_adapter.hpp로 대체했다. 입력 어댑터는 mutex로 Receive/Update/
  writer Poll을 직렬화하며 JSON 검증/ready/초기 정렬/0.08rad/s를 연결한다.
  실제 전달은 단일 기존 SDK publisher/Write site다. 실제 실행은 하지 않았다.
- pinch는 계획된 damping, 오류/timeout은 기존 오류 damping에 연결했다.
  자동 AI 복귀는 없다. 새 native_vr_build/CMakeLists.txt를 추가했고 기존 CMake는
  보존했다. 환경변수로 bind/source IPv4와 port를 명시해야 하며 값은 설정하지 않았다.
- 검증: 입력 어댑터 MSVC C++17 /W4 /WX 빌드 성공, owner 관련 pytest6개 통과.
  early engage/정렬 오류/22번만 갱신/다른 축 보존/pinch/독립 watchdog timeout 확인.
  네이티브 초안의 publisher 생성과 Write site가 각각1개임을 소스로 확인했다.
  Linux SDK/Torch/UDP 통합 빌드는 아직 수행하지 않았다. 초안은 실행 준비 완료가 아니다.
- 먼저 처리할 실제 잔여: 대상 Linux SDK 빌드, 기존 handoff 실패 처리와 rate/torque
  clamp 충돌 검토, Windows 입력 목적지 연결 및 장비에서 모드/송신자/초기 상태 확인.
  기존 Controller 생성자부터 publisher가 만들어지므로 바이너리 실행은 단순 검토가 아니다.
- 원본 twist2_right_arm_trial.cpp SHA256은
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F 유지.
  기존 작업을 되돌리지 않았다. G1/WSL/DDS 실행, 실제 publisher 생성/물리 출력 없음.

## 이전 초기 torque fade 연결 (2026-09-07 후속)

- 변경사항과 현재 owner/writer 코드를 먼저 확인했다. OfflineOwner(true,true)에
  torque fade를 opt-in으로 연결했다. 첫 writer 생성 때 최신 검증 상태의 29축 토크를
  한 번 캡처하고 기존 OfflineTorqueFade로 축별 토크 한도의50%에 제한한다.
  writer tick 시점의 경과 시간으로1초 동안 선형 감소하여0이 된다. 이후 측정 토크로
  재캡처하지 않는다. 1초와50%는 오프라인 실험값이며 물리 승인 기준이 아니다.
- feedforward는 Tick의 로컬 desired 복사본에만 적용한다. 정책 created_at을
  갱신하지 않으므로 fade가 오래된 정책을 연장하지 않는다. Stop은 캡처를 제거하고
  기존 writer 중단 진단의 feedforward0으로 전환한다. 실제 damping 송신은 없다.
- test_owner_torque_fade.cpp 5개 시나리오: 양/음 큰 측정값의 clamp/단조 감소/0끝점,
  후속 측정 변경에도 캡처 유지, 외부 Stop, CRC 오류, 정책 만료, opt-out0 확인.
  초기 검사의 하체 위치 동등성 실패는 blend의1.49e-8rad 반올림 차이였다.
  하체는1e-7rad 오차 검사, 비대상 상체는 정확한 동등성을 유지한다.
- VERIFY_OFFLINE.ps1 / backend/tests/test_offline_owner.py에 연결했다.
  최종 MSVC /W4 /WX 빌드 및37 passed / 50 subtests passed,
  watchdog/writer와 저장 Quest1001packet 재생 통과(violations=[]).
  기존 물리 C++ SHA256 검사도 통과했다.
- owner_policy_stdio와 CPU runner의 --torque-fade는 --tracking-fixture를 포함하고
  합성 상태에 축별 +/-0.5Nm를 넣는다. 합성 지연 모델은 토크 물리 효과를 모델링하지 않는다.
  logs/test_results/twist2_torque_fade_cpu_20260907.json: 498 cycle accepted,
  history407, frame1843, 5.669초 후 policy_deadline, exit1/release_verified=false.
  최대 전달 간격4.3155ms, 최대 lock 대기1.3692ms. 마지막 요청~Finish12.5297ms,
  worker 전체1.6211ms. 지연의 정확한 원인은 미확정이며 재실행으로 실패를 덮지 않았다.
- 저장 로그에서 최초 관측 feedforward +/-0.4963394Nm(시각2.0164862),
  3.0129076에0, 이후0 유지 및 전구간 부호/절댓값 단조 감소를 확인했다.
  중단 후 모든 기록의 frame/history는 고정됐다. fade 검증은 통과했지만
  이번 실제 CPU 시험은 ready/engage/해제 전구간에 도달하지 못했다.
- 남은 항목: 반복된 정책 지연 구간의 분리 계측, damping/모드 인계의 요청·확인·실패
  계약, 실제 SDK 상태/송신 어댑터 및 G1 동역학 검증. 물리 C++ 변경이나
  G1/WSL/DDS/VR 실행, publisher 생성은 하지 않았다. Arm SDK 문제는 계속 보류다.

## 이전 실제 CPU + 합성 추종 ready/engage/해제 시험 (2026-09-07 후속)

- 현재 변경사항과 handoff/실행 코드를 확인한 뒤 offline_lag_fixture.hpp를 추가했다.
  시정수0.2초의 1차 지연 응답을 expm1로 계산하고 속도0.08rad/s로 제한한다.
  유한수 및 0<dt<=20ms를 검사한다. 질량/접촉/균형/모터 동역학이 없는 합성 모델이다.
  test_owner_startup.cpp에 양방향 수렴/속도/초과 목표 및 잘못된 dt 검증을 추가했다.
- owner_policy_stdio.cpp의 tracking_fixture opt-in은 독립 tick에서 마지막으로
  memory sink가 수락한 목표를 따라 합성29축 q/dq를 갱신한다. 기존 고정 상태는 유지.
  ready 후 첫 engage는 기준 자세이고, 이후22번 목표에만 +0.02rad를 준다.
  release op는 현재 fixture packet의 다음 sequence와 pinch_disengaged를 사용한다.
- run_owner_continuous_cpu.py --tracking-fixture는 autonomous/dispatch/startup을
  포함한다. 최대1200cycle 중 active 목표 갱신20회 후 해제하고30ms 뒤 상태를 확인한다.
  목표 증가/합성 측정 움직임/비대상 상체 목표 유지/해제 후 count/history 정지가
  모두 확인돼야 성공한다. 이 VR 입력은 합성 시험 입력이며 새 Quest 실측이 아니다.
- 실제 CPU 시험 logs/test_results/twist2_tracking_cpu_20260907.json:
  544 cycle accepted, 6.321초, frame2063, exit0, release_verified=true.
  시계 시작1.0 기준 phase 시각: blending2.0118601, verifying_tracking6.0166407,
  awaiting_alignment7.0193067, active7.0265032, input_disengaged7.2895835.
  전달 간격2.1601~3.7345ms, 최대 lock 대기1.1259ms.
  22번 목표 증가0.01999999955rad, 합성 측정 증가0.00886131544rad,
  다른 상체12..21/23..28 목표 변화0. 하체 합성 측정 최대 변화0.1849435121rad.
- logs/test_results/twist2_tracking_audit_20260907.json: 저장된 전체 목표에서
  비대상 상체 유지, 22번 목표 단조 증가/0.02rad 초과 없음 확인. 첫 해제부터
  이후 모든 로그의 desired 제거 및 frame/history 고정, background tick 지속 확인.
  이는 로그에 기록된 목표 검사이며 실제 모터 정지/물리 damping 검증이 아니다.
- 검증: MSVC /W4 /WX 빌드, VERIFY_OFFLINE.ps1의36 passed / 50 subtests passed,
  watchdog/writer 및 저장 Quest1001packet 재생 통과(violations=[]). 기존 물리 C++
  SHA256 검사 통과. 다른 작업을 되돌리지 않았고 G1/WSL/DDS/VR/publisher 미실행.
- 남은 핵심: 초기 torque fade와 중단/모드 인계 계약, 실제 SDK 상태/송신 어댑터,
  로봇 동역학/충돌/균형과 실제 입력을 결합한 검증. 이번 결과만으로 실제 G1 조작
  가능이나 안전성을 주장하지 않는다. Arm SDK 기울어짐 문제는 계속 보류다.

## 이전 독립 C++ tick 및 고해상도 타이머 (2026-09-07 후속)

- 현재 변경사항을 확인한 뒤 owner_policy_stdio.cpp에 autonomous_tick opt-in을
  추가했다. std::thread가 합성 LowState 생성과 memory dispatch를 수행하며, main의
  상태/VR/정책/관측 접근과 동일 mutex로 직렬화한다. JSON 직렬화와 stdout 쓰기는
  잠금 밖에서 수행한다. EOF/예외 시 스레드를 join한 뒤 참조 상태를 파괴한다.
  중복 init은 거부한다. 실제 로봇 cache의 receipt를 새롭게 꾸미는 구현이 아니다.
- run_owner_continuous_cpu.py --autonomous-tick은 --dispatch를 포함하며 Python이
  state/tick을 보내지 않는다. status는 조회만 하고 외부 tick도 중복 writer를 실행하지
  않는다. 응답이 생략한 중간 frame까지 포함한 전달 간격은 C++ sink에서 직접 집계한다.
  background tick 수/최대 간격, owner lock 최대 대기 시간도 기록한다.
- 초기 sleep_for(2ms) 시험 logs/test_results/twist2_autonomous_cpu_20260907.json:
  2/100 cycle accepted, frame0, 최대 tick 간격15.164ms, lock 대기0.0008ms에서
  dispatch_deadline 중단(exit 1). 실패 로그를 유지했다.
- 그 후 Windows CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 상대 2ms 타이머로 변경.
  timeBeginPeriod 같은 전역 설정 변경은 없고 6ms 제한도 유지한다. 타이머 생성/대기
  실패는 owner 중단으로 처리한다. 고정 500Hz 보장은 아니며 callback 처리 시간과
  스케줄링 지연이 간격에 더해진다. timer는 Windows 로컬 실험 전용이다.
- 실제 CPU 재검증(고정 합성 상태, 실제 통신 없음):
  - logs/test_results/twist2_autonomous_highres_cpu_20260907.json: 100/100 accepted,
    frame483, 1.238초, 전달 간격2.1602~4.0317ms, 최대 lock 대기1.386ms, reason 없음,
    exit 0. 기본 경로의 settle/정렬은 합성 fixture이며 물리 arming 검증이 아니다.
  - logs/test_results/twist2_autonomous_highres_startup_20260907.json: 600/600 accepted,
    frame2266, 6.785초, 전달 간격2.1478~4.4110ms, 최대 lock 대기0.2912ms,
    reason 없음. 고정 상태 때문에 verifying_tracking까지만 도달하여 exit 1.
    ready/active 전구간 통과로 기록하지 않는다.
- test_offline_owner.py에 stdin 요청을 60ms 보내지 않는 검증 추가. C++가 자체적으로
  policy_deadline을 감지하고 뒤늦은 Finish를 거부하며 history/frame0 유지, EOF 후
  정상 종료를 확인했다. 이 시험은 독립 중단 경로의 검증이지 실제 로봇 안전성 검증이 아니다.
- 최종 VERIFY_OFFLINE.ps1: MSVC C++17 /W4 /WX 빌드, 36 passed / 50 subtests passed,
  watchdog/writer 진단과 저장 Quest 1001 packet 재생 통과(violations=[]).
  물리 C++의 기준 SHA256 검사도 통과했다.
- 남은 항목: 실제 모델과 추종 동역학을 함께 연결한 ready/engage 검증, 실제 SDK의
  별도 상태 수신 및 송신 실패/블로킹 처리, torque fade와 damping/모드 인계.
  이번 두 짧은 고해상도 시험으로 Windows/Linux 실시간 보장을 주장하지 않는다.
  기존 물리 C++ 변경, G1/WSL/DDS/VR 실행 및 publisher 생성은 하지 않았다.

## 이전 실제 CPU와 메모리 dispatch 통합 (2026-09-07 후속)

- 기존 변경사항을 확인한 뒤 owner_policy_stdio.cpp와 run_owner_continuous_cpu.py를
  수정했다. init dispatch=true / CLI --dispatch opt-in으로 첫 writer 생성 때
  OfflineDispatch를 시작하고 이후 tick을 Pump에 연결했다. 기존 경로는 기본값 유지.
  각 응답/로그에 dispatch count/time/state sequence와 handoff_required를 기록한다.
  중단 후 tick 2회로 전달 수 고정과 인계 필요 상태를 검증한다.
- MSVC /W4 /WX 빌드 및 VERIFY_OFFLINE.ps1 통과: 35 passed / 50 subtests passed,
  저장 Quest 1001 packet 재생 violations=[]. 기존 물리 C++ SHA256 검사 통과.
- 실제 CPU 모델 시험을 각각 한 번 실행했다. 모두 Windows local pipe와 고정 합성
  LowState만 사용했고 실제 DDS/publisher/G1/VR는 실행하지 않았다.
  - logs/test_results/twist2_dispatch_cpu_20260907.json: 요청100 중12 cycle accepted,
    frame44개. 전달 간격2.482~5.138ms, 다음 tick 공백6.4737ms에서 dispatch_deadline.
    지연 cycle의 worker 전체0.8624ms, C++ 요청~Finish4.0034ms. 종료코드1.
  - logs/test_results/twist2_dispatch_startup_cpu_20260907.json: 요청600 중581 accepted,
    history490, frame1953개. 전달 간격2.334~4.638ms, tick 공백8.9798ms에서 중단.
    verifying_tracking까지만 도달했고 ready/active 없음. worker 전체1.7687ms,
    C++ 요청~Finish11.3046ms이며 먼저 발생한 dispatch_deadline을 보존했다. 종료코드1.
- 두 로그 모두 실패 이후 Finish와 추가 tick 2회에도 전달 수 및 history가 유지됐다.
  전구간 성공이나 실시간성 통과로 기록하지 않는다. 전달된 frame 간격과 실패를
  유발한 호출 공백은 서로 다른 지표다. frame 시간은 C++ op 진입 시각이며 실제
  DDS 송신 완료 시각이 아니다. CPU inference만으로 관측된 전체 지연을 설명할 수
  없지만 OS 스케줄링/파이프/관측 구성 중 어느 부분인지 아직 분리 측정하지 않았다.
- 다음 핵심은 Python stdin 요청에 의존하는 tick을 독립 C++ 주기로 분리하고,
  단일 owner 상태 접근을 직렬화한 상태에서 지연/중단을 재검증하는 것이다.
  6ms 제한을 완화하지 않았다. G1 동역학, 실제 SDK/500Hz 송신, torque fade,
  damping/모드 인계와 독점 송신자 확인은 여전히 남아 있다.

## 이전 메모리 전송 경계 (2026-09-07 후속)

- 현재 변경사항과 owner/writer/검증 스크립트를 읽은 뒤 추가했다. 기존 물리 C++나
  다른 작업은 변경·복구하지 않았다. 새 offline_dispatch.hpp는 OfflineOwner.Tick의
  성공 결과만 35슬롯 진단 snapshot으로 OfflineMemorySink에 동기 전달한다.
  snapshot에는 증가하는 frame sequence, 최신 state sequence, 작성 시간이 있다.
  이는 LowCmd가 아니며 SDK 직렬화/CRC/네트워크/실제 publisher는 없다.
- Pump는 호출자가 주는 단조 시계로 최소 2ms 간격, 최대 6ms 공백을 검사한다.
  이른 호출은 생략, 늦은 호출은 dispatch_deadline으로 중단한다. 몰아서 catch-up하거나
  저장 snapshot을 재전송하지 않는다. 6ms는 오프라인 실험값이며 실제 주기 보장이 아니다.
  아직 독립 timer/thread나 실제 CPU runner에 연결하지 않았다.
- owner 중단, 시계 역행, sink 거부 시 후속 전달을 latch한다. HandoffRequired는
  실제 인계가 필요하다는 진단일 뿐 damping 송신/모드 복귀 완료를 뜻하지 않는다.
  sink 거부 전에 writer 계산은 진행될 수 있으므로 전달 성공과 계산 성공을 구분한다.
  메모리 sink의 마지막 snapshot은 감사용으로 남고 재전송되지 않는다.
- test_offline_dispatch.cpp 6개 시나리오: 정상/이른 호출/6ms 경계와 중복 방지,
  7ms 지연, pinch 해제, sink 거부, 역행 시계, CRC 오류. 각 중단 후 추가 전달 없음,
  desired 제거와 마지막 writer 목표 보존을 확인했다. 상체 값과 frame/state binding도 검사.
  backend/tests/test_offline_owner.py 및 VERIFY_OFFLINE.ps1에 연결했다.
- 검증: MSVC C++17 /W4 /WX 빌드 성공. 35 passed / 50 subtests passed,
  watchdog/writer 진단 및 저장 Quest 1001 packet 재생 통과(violations=[]).
  물리 C++ SHA256 기준 검사를 통과했다. G1/WSL/DDS/VR/publisher 미실행.
- 남은 핵심: 실제 CPU runner와 dispatch 통합 및 주기 지연 측정, 독립 scheduler,
  SDK 전송의 실패/블로킹/경쟁 송신자 처리, 초기 torque fade, 실제 damping과 모드
  인계 확인. 단일 프로세스의 메모리 검증은 시스템 전체 송신자 독점 보장이 아니다.
  실제 G1 동역학 및 과거 12.89ms CPU 지연 원인도 미검증 상태다.

## 이전 ready 대기 제한 및 추종 fixture (2026-09-07 후속)

- 먼저 현재 변경사항과 handoff/owner/test 코드를 확인했다. 다른 작업을 되돌리지 않았다.
- offline_owner.hpp: startup_blend opt-in에 첫 유효 상태부터 active 진입까지
  15초 제한 추가. settle/blend/tracking/ready 후 engage 대기 모두 포함하며,
  ready 취소나 재시도로 기한을 연장하지 않는다. ReceiveState/ReceiveVR/
  BeginPolicy/Finish/Tick에서 검사하고 startup_ready_timeout으로 latch한다.
  desired/관측/대기 정책을 제거하고 writer의 마지막 목표와 history를 보존한다.
  기본 startup_blend=false 동작에는 이 기한을 적용하지 않는다.
- test_owner_startup.cpp: 8개에서 12개 시나리오로 확장. writer 목표에 대한
  시정수 0.2초, 속도 상한 0.08 rad/s의 1차 지연 합성 관절을 사용했다.
  0번 관절의 0.1 rad 목표를 실제 fixture 상태가 0.07 rad 넘게 추종한 뒤
  ready/engage에 진입하고 상체 목표가 보존됨을 검증했다.
  고정 상태의 추종 실패, settle 속도 조건 미충족, ready 후 engage 미입력은
  정확히 첫 상태+15초에서 중단되며 이후 Finish/Tick도 갱신하지 않는다.
- VERIFY_OFFLINE.ps1 완료: MSVC /W4 /WX 빌드, 34 passed / 50 subtests passed,
  watchdog/writer 진단 통과. 저장 Quest 1001 packet 재생 violations=[].
  물리 C++의 기존 SHA256 검사도 통과했다. 실제 CPU 전구간 시험은 이번에
  재실행하지 않았고 이전 고정 상태의 active 미도달 결과를 그대로 유지한다.
- 한계: 위 fixture는 합성 정책의 제어 흐름 검증이며 G1/MuJoCo 동역학이 아니다.
  첫 상태 이전에는 writer가 없고 이 기한도 시작하지 않는다. 실제 시간 보장은
  독립 scheduler 연결이 필요하다. 15초는 오프라인 실험값이며 물리 승인값이 아니다.
- 다음 핵심 작업: 실제 배포 대상과 분리된 scheduler/전송 어댑터 계약,
  초기 torque fade 및 해제/오류 시 damping·모드 인계. 실제 G1 동역학 검증과
  과거 CPU 12.89ms 지연 원인 확인도 남았다. G1/WSL/DDS/VR/publisher 미실행.

## 이전 측정 상태 기반 ready 조건 (2026-09-07 후속)

- 변경 전 OfflineOwner(true)는 4초 blend 경과만으로 awaiting_alignment가 됐다.
  이제 verifying_tracking 단계를 거쳐 29축 모두 측정 q와 desired/직전 writer 목표의
  오차 <=0.025 rad, |dq|<=0.1 rad/s를 상태 receipt 기준 1초 연속 만족해야 한다.
  조건 이탈은 dwell을 초기화하고 engage 전 ready를 취소한다. 이 값은 오프라인
  실험 기준이며 실제 G1 승인 기준이나 기존 seed 속도 기준의 변경이 아니다.
- ReceiveVR도 상태 freshness를 검사한다. ready 후 상태가 만료되면 engage를
  거부하고 기존 stop latch로 desired를 제거한다. active 단계의 기존 중단 조건은
  유지하며 이번 ready 기준을 active의 새 속도 제한으로 적용하지 않는다.
- 변경 파일: offline_owner.hpp, test_owner_startup.cpp. 기존 변경사항을 먼저 확인했고
  다른 작업은 되돌리지 않았다. startup 8개 시나리오: 조기 engage, 정렬 성공/실패,
  blend 중 timeout, 목표 미추종, 속도 이탈에 의한 dwell 초기화, ready 취소, ready 만료.
- VERIFY_OFFLINE.ps1: MSVC /W4 /WX 빌드 성공, 34 passed / 50 subtests passed.
  저장 Quest 1001 packet 재생 violations=[]; 최대 속도 0.08000000000000229 rad/s.
  물리 twist2_right_arm_trial.cpp SHA256은
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F 그대로다.
- 실제 CPU 모델 + 고정 합성 LowState 시험:
  logs/test_results/twist2_measured_ready_cpu_20260907.json.
  600 cycle accepted, 6.764초, reason 없음. settling/blending/verifying_tracking까지만
  도달했고 ready/active는 발생하지 않았다. runner exit 1은 active 미도달에 따른 것으로
  이번 전구간 시험을 성공으로 기록하지 않는다. 고정 상태에는 로봇 동역학이 없다.
  과거 ready 조건으로 통과한 CPU 로그는 현재 조건의 통과 증거가 아니다.
- 남은 핵심: 측정 상태가 목표를 따라오는 동역학/실장 검증, ready 대기 기한 설계,
  실제 독립 scheduler와 SDK 단일 full-body 송신자 통합, 초기 torque fade,
  해제/오류 시 실제 damping 및 모드 인계. 과거 12.89ms deadline 초과 원인도 미해결.
  G1/VR 미사용 상태이며 WSL/DDS/publisher/물리 출력은 실행하지 않았다.

## 이전 실제CPU 초기blend 전구간시험 (2026-09-07)

- owner_policy_stdio init에startup_blend opt-in 연결. 해당모드에서는
  합성zero action으로settle을미리건너뛰지않고실제모델을처음부터호출한다.
  VR은awaiting_alignment/active에서만합성정렬packet을주입한다.
  run_owner_continuous_cpu.py --startup-blend는600cycle을요청한다.
  C++ clock_base=1,관측/IPC/스케줄링을포함한실제기한검사유지.
- 1차 logs/test_results/twist2_startup_cpu_20260907.json:
  settling→blending→awaiting_alignment→active 도달했으나469cycle후
  policy_deadline/exit1. 실패요청Finish12.8921ms,먼저Tick에서중단,
  history378에서유지. 이실패를지우거나임계값을완화하지않았다.
- 모델/worker total/GC timing을cycle로그에추가한재시험:
  logs/test_results/twist2_startup_cpu_timing_20260907.json.
  600/600accepted,7.0513284초,history509commits(안정화중discard),exit0.
  요청최대7.6752ms,worker최대2.4088ms,model최대2.1793ms,GCevent0.
  초기blend와실제CPUhistory연결은확인됐지만1차지연의원인은미확정이다.
  재시험통과를간헐지연해결/실시간보장으로해석하지않는다.
- MSVC /W4 /WX빌드통과,owner회귀2tests통과.
  고정합성state/준비후합성정렬packet이며실제G1 동역학이나Quest재시험아님.
  물리C++SHA256불변 E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.
- 다음:실측tracking을반영한ready조건,初期torque fade/모드인계의미검토,
  latency tail을진단할단계별timestamp와중단원인보존강화.
  실제500Hz/SDK송신은여전히미연결. 장비불가조건유지,
  WSL/DDS/VR/G1/publisher/물리출력실행없음.

## 이전 초기blend와VR단계분리 (2026-09-07)

- OfflineOwner(true) opt-in 경로 추가. 기존default false/기존시험동작유지.
  MeasuredCompositionOffline→Guarded→Native에prealignment 옵션전달하여
  안정화baseline이확정된후VR없이도검증된상체고정후보를만들수있게했다.
- 단계settling→blending→awaiting_alignment→active,오류시stopped latch.
  기존1초settle후4초smoothstep 전환. 하체0..11의mimic은captured→default,
  desired는captured→정책하체목표로blend. 상체12..28은정확히유지한다.
  ready전active VR수신은engage_before_ready로중단. ready후첫목표는
  기존실측오차검사(.025rad)를통과해야active가된다.
- VR전writer진단생성및blend된desired 기준history commit 연결.
  이는zero feedforward 진단경로다. 실측torque fade/모드인계가없으므로
  물리초기화경로로사용할수없다. phase ready는blend시간완료이지
  실제lower-body tracking완료/동역학안정판정이아니다.
- test_owner_startup.cpp 4경우:VR없는전환/초기jump없음/단조목표/상체유지,
  earlyengage거부,ready후aligned 허용/mismatch거부,blend중무수신중단.
  합성고정상태/고정policy action사용. 실제CPU모델blend운전은아직미검증.
- VERIFY_OFFLINE 전체34passed/50subtests,writer/watchdog/Quest재생통과.
  마지막무수신case추가후startup재빌드및owner2tests통과.
  MSVC /W4 /WX. 첫빌드의멤버변수shadow경고는이름분리로수정.
- 다음:opt-in startup경로를CPU stdio실행기에연결해실제모델로blend전구간
  관측/history/기한을검증하고,별도로ready의실측tracking조건을검토한다.
  현재기존CPU runner는default false경로를사용한다.
  장비불가조건유지:WSL/DDS/VR/G1/publisher/물리출력실행없음.
  기존물리C++변경없음.

## 이전 연속CPU주기와wallclock 검증 (2026-09-07)

- owner_policy_stdio.cpp에begin 및wall_clock opt-in 추가.
  wallclock은C++steady_clock으로초기실제정책요청직전에시작하여
  관측JSON전달/Python스케줄링/worker IPC/Finish dispatch까지기한검사에포함.
  기존결정적eventclock은유지한다. SDK/로봇/동역학없는고정합성state다.
- run_owner_continuous_cpu.py 신규:실제모델100cycle 요청,계산중에도
  state/tick event처리,결과반영후다음관측/history로추론한다.
  첫실행은writer활성화후2ms이전Tick호출로writer_clock중단(1cycle).
  원본실패logs/test_results/twist2_owner_continuous_20260907.json 보존.
  runner에서첫Finish뒤tick기준시간을재설정하여수정. 임계값완화없음.
- 수정후logs/test_results/twist2_owner_continuous_retry_20260907.json:
  100/100accepted,historycommits100,1.2090399초,중단원인/오류없음.
  C++요청→Finish3.1198~5.1852ms,평균3.672367ms(10ms제한내).
  writer399ticks,간격2.3012~5.4302ms. 실제500Hz충족증거는아니다.
  연속고정합성state이므로실제관절동역학/실측tracking검증도아니다.
- 기존CPU3시나리오(normal/pinch/late)재실행모두통과.
  owner13경우회귀1test통과,MSVC /W4 /WX빌드통과. 물리C++불변.
- 초기blend검토:현재새owner는VR정렬후에만candidate/writer를만든다.
  기존OfflineBlendAlpha/OfflineBlendDesired만삽입하면VR전서기제어가
  없거나상체목표가전환중변하는문제가있어이번에적용하지않았다.
  다음은settle→VR없는초기blend→ready→VR정렬을명시적단계로분리하고
  기존합성blend검증과history commit기준을연결하는것이다.
- 장비불가조건유지:Windows local pipe/CPU만실행.
  WSL/DDS/VR/G1/publisher/물리출력없음. 실제송신/모드인계는미완료다.

## 이전 실제CPU정책→owner 로컬연결 (2026-09-07)

- owner_policy_stdio.cpp 신규:합성native state/settle 및저장Quest packet schema로
  owner관측생성→local stdin/stdout event API(init/state/vr/tick/finish).
  SDK/네트워크없음. 파일fixturehg_classes_only.hpp로만합성상태구성.
- run_owner_cpu_offline.py:기존hash검증CPU worker10회warmup후
  owner1432관측을실제모델에전달,worker request_id검증,대응owner token으로Finish.
  worker infer는Python별도thread에서수행하고owner상태/VR event를주입한다.
  정상/계산중pinch/인위적13ms지연의3경우통과.
- 초기측정worker왕복1.78~2.95ms. sourcehash기록추가후재실행은1.47~1.61ms.
  logs/test_results/twist2_owner_cpu_verified_20260907.json:
  capture/exe/model SHA256 포함. 모델hash463be0376c2c1f551b996d0bf9ab97833854f2cc098b9d4fea735f17ec2e9015.
  정상commits1/writer tick성공,pinch와deadline은commits0/desired null/늦은결과거부.
- simulation clock는測定worker turnaround와주입event시간중큰값을Finish에반영한다.
  owner IPC 전체latency를실시간deadline에포함한시험이아니며
  실제worker계산종료이전에VR event가도착했다는wallclock보장도아니다.
  threaded inference+결정적event ordering 검증이며실시간스케줄러검증과구분한다.
- MSVC /W4 /WX빌드통과. owner+workerclient 회귀6passed/14subtests.
  VERIFY_OFFLINE.ps1에새stdio harness빌드추가.
  실행:py -3.11 experiments/twist2_right_arm_manual/run_owner_cpu_offline.py
  --output <새결과JSON경로>. 기존파일overwrite하지않는다.
- 제약:한정상policy cycle만검사,settle은합성zero action,실제모델은settle후호출.
  초기blend/연속CPUhistory/동역학/실제state 수신스레드/SDK송신은미연결.
  numpy미설치및torch.jit.load deprecation warning은기존환경에서발생했으나
  이번추론은성공했다. 장비실행/WSL/DDS/VR/publisher없음,물리C++불변.
- 다음:연속cycle에서history/초기blend를연결하고wallclock deadline을포함한
  상태/VR/CPU 통합부하·지연시험. 실제G1출력준비완료로표현하지않는다.

## 이전 독립VR검증과관측history통합 (2026-09-07)

- offline_owner.hpp에RawInputWatchOffline 연결. ReceiveVR에서즉시검증,
  정상active FIFO64보존,BeginPolicy에서Drain한다. 정책중pinch/JSON오류/
  queueoverflow는Stop으로pending/desired/history를폐기한다.
  Begin/Finish/Tick에서도VRtimeout검사. 기존batch API는동일경로로전달.
- OfflineObservationHistory를owner에연결:BeginPolicy에서요청시점
  q/dq/gyro/rpy와PreparedUpper로1432차원관측을고정한다.
  NativeCompositionOffline.PreparedUpper는검증중인임시상체목표의읽기전용접근.
  관측은새state수신으로변경되지않는다. 정상candidate채택후만Commit,
  settle/VR미정렬은Discard,Stop은관측폐기/history정지.
- test_offline_owner 13경우:기존10경우+pending pinch/parse_error/FIFOoverflow,
  관측생성/수신후관측불변/성공commit/실패시commit금지확인.
  VERIFY_OFFLINE재빌드와실행exit0:33passed/50subtests,
  writer/watchdog C++ 및Quest1001packets재생violations없음.
- 실제CPU worker 프로세스와이owner의IPC는아직미연결.
  관측생성/정책응답인터페이스만준비했으며정책action은합성fixture다.
  history는합성목표기준이고초기blend/실제하체정책동역학과연결되지않았다.
  독립VR검증은event API이며실제수신thread/스케줄러는아니다.
- 다음:새owner관측→검증된CPU모델→token결과→Finish를로컬stdio로연결하고
  응답지연중상태/VR이벤트를계속처리하는통합재생을검증한다.
  장비불가조건유지:WSL/DDS/VR/G1/publisher실행없음. 물리C++해시불변.

## 이전 수신 cache와정책요청분리 (2026-09-07)

- offline_owner.hpp ReceiveState와BeginPolicy 분리. ReceiveState는
  CRC/native decode/receipt연속성/상태health를검사후최신cache만교체한다.
  정책진행중에도수신가능하며request_state_sequence는요청시점값을유지한다.
  기존Begin은ReceiveState+BeginPolicy 호환wrapper다.
- Tick은최신수신cache의freshness와writer health를검사한다.
  Finish는기존요청token/10ms기한과요청당시composition snapshot검증을유지.
  새상태를받았다는이유로오래된요청을fresh로바꾸지않는다.
- guarded_composition_offline.hpp health검사를CheckOfflineStateHealth로추출해
  policy prepare와cache 수신이같은CRC/mode/deadman/IMU/관절/속도/temp/fault
  조건을사용한다. 실제runtime seed의0.1rad/s기준은변경없음.
- owner기존7경우에3경우추가:정책중정상상태수신/요청seq불변후Finish허용,
  정책중CRC오류/정책중deadman해제후Finish거부.
  VERIFY_OFFLINE전체33passed/50subtests,writer/watchdog/Quest replay통과.
  health추출영향검증을위해guarded composition도재빌드후2passed/29subtests.
- 이cache는단일thread event model이다. mutex/실제수신thread/CPU worker IPC와
  observation/history/blend는새owner에아직연결하지않았다.
  실제송신/배포가능owner로해석하지않는다. VR도정책요청시batch입력이며
  독립VR수신중단경로는다음통합대상이다.
- 다음:실제CPU worker 결과를명시적request token과결합하고
  관측/history/초기blend 및독립VR검증을오프라인owner에통합한다.
  장비불가조건유지:WSL/DDS/VR/G1/물리출력실행없음,물리C++불변.

## 이전 메모리 전용 owner 통합 (2026-09-07)

- offline_owner.hpp 신규:NativeCompositionOffline와OfflineWriterStudy를
  단일thread event API Begin/Finish/Tick으로연결. SDK/소켓/송신없음.
  Begin은검증된native fixture 상태와VR을준비하고명시적request token발급.
  Finish는동일token/10ms deadline을검사후하체policy+상체후보를writer desired로전달.
  Tick은새패킷없이상태20ms/정책10ms만료검사후writer진단을갱신한다.
- 모든Stop은원인latch,pending/desired폐기,composition.Abort,writer.Stop을함께적용.
  중복/다른token/늦은결과로재개하지않는다. 이전target은보존하되damping은진단값이다.
- test_offline_owner.cpp:합성native state1초settle→저장Quest schema의목표를
  합성measured에정렬→합성policy하체적용→writer확인.
  무수신/중복응답/CRC/timeout후응답/pinch/Finish deadline/Tick deadline
  7경우에서정확한중단이유/desired폐기/target불변확인.
  실제Quest 전체재생이나실측연속state/policy추론실행검증은아니다.
- VERIFY_OFFLINE.ps1에owner빌드/test추가. 전체33passed/50subtests 및
  watchdog/writer C++/1001Quest replay통과. 후속Tick deadline추가후
  owner재빌드와7경우회귀1test추가실행통과. MSVC /W4 /WX.
- 현재제약:한policy요청진행중새Begin은overlap중단한다.
  독립상태수신cache/실제timer/thread/SDK직렬화/배포ABI/물리송신은없다.
  초기blend/실제정책history는이새owner에아직연결하지않았다.
  최초VR전에writer가없으며실제서기제어로사용할수없다.
  zero feedforward 진단경로이며물리출력준비완료로해석하지않는다.
- 다음:상태수신과policy요청을분리한cache/시퀀스binding을오프라인구현하고
  실제CPU정책/초기blend/history와통합. 사용자퇴근으로장비실행금지유지.
  기존물리C++/G1/WSL/DDS/VR실행변경없음.

## 이전 다음날 실행 준비 (2026-09-07)

- 퇴근후장비불가조건유지:Windows 로컬코드/저장로그만사용.
  WSL/DDS/VR/로봇실행없음. 실제구동준비완료로표현하지않는다.
- offline_state_continuity.hpp Poll(now) 추가:무수신20ms초과와
  fresh receipt에도tick진행이없을때중단원인latch.
  NativeCompositionOffline.Poll은그원인을guard.Abort로전달해후보폐기.
  독립timer/thread는생성하지않으며실제owner가주기호출해야한다.
  최초수신전대기는타임아웃하지않는다. 별도startup deadline은남은항목.
- test_state_watchdog.cpp:무수신/재수신후latch/frozen tick/adapter invalid-clock
  MSVC /W4 /WX 빌드및실행통과.
- VERIFY_OFFLINE.ps1 신규:물리source hash확인→3C++빌드→watchdog/writer
  →32pytest/50subtests→저장Quest1001packets재생. 실제실행exit0.
  writer500ticks*29checks/12fault+latch/충돌반례/fade 포함.
  replay violations=[],pinch stop,input_disengaged,0.08rad/s제한유지.
- docs/TWIST2_NEXT_DAY_RUNBOOK.md:내일로컬검증명령,포트점유확인,
  fresh seed simulation 시작절차,정리방법,미완료연결표작성.
  실제500Hz송신/SDK직렬화/단일owner/중단후인계는미연결.
  실제출력명령이나잠금해제코드를만들지않았다. 기존물리C++불변.
- 다음핵심작업은상태/VR/정책/writer를하나의실행owner에묶고
  watchdog호출과명령만료를통합검증하는것이다. 현재문서와검증스크립트는
  장비연결후사전검사를빠르게시작하기위한준비이며실제팔구동보장이아니다.

## 이전 퇴근 후 오프라인 검증 (2026-09-07)

- 사용자 VR/G1 사용불가 조건에 따라 저장로그/Windows 로컬만 사용.
  VR/WSL/DDS/SDK/로봇실행없음. 기존변경을보존했다.
- MSVC /W4 /WX로 test_upper_target_offline.cpp 재빌드후실제Quest pinch
  로그1001packets를기존replay_cpp_input_tick.py로재생.
  logs/test_results/twist2_pinch_cpp_offline_20260907/result.json,ticks.jsonl.
  20ms tick:active73,waiting1533,stopped16,stop=input_disengaged,
  maxrate0.08000000000000229rad/s(부동소수오차),violations=[]:
  overshoot/0..21변경/inactive갱신/stop latch 위반없음.
  종료후약0.3초합성tick 추가. 오류후유지는별도회귀tests로검증.
- 이재생은저장JSON을현재pure serializer로재직렬화한memory-only검증이다.
  rawbytes동일재생이나live C++/정책/실제제어검증은아니다.
  기준은first-active Mink이며이전검증에서실측seed와오차0을확인했다.
- compare_seed_windows_offline.py 신규,저장30초30143samples 분석.
  0.2/0.5/1초창,100ms간격,관절별p99/초과비율/q범위 비교.
  탐색용peak0.2,p99 0.1,초과비율1%,q범위0.005/0.01rad.
  runtime권장값아님,seed/control 임계값은변경하지않았다.
  독립CRC/finite/fault 검사후분석,20ms초과gap과역행창거부.
- 1초/q범위0.01후보:290창중290통과,모든sample<=0.1조건279통과.
  q범위0.005후보:279통과(속도초과창4개추가허용하나드리프트창도거부).
  창은서로겹쳐독립시험횟수로해석하지않는다. 짧은한기록으로기준채택불가.
  결과logs/test_results/twist2_seed_window_comparison_20260907.json.
- 회귀22passed/50subtests:window spike/drift/gap/nonfinite,
  C++목표수렴/반전/idle/timeout/오류/해제/latch 포함.
  logs/test_results/twist2_offline_evening_latest.xml.
- 남은오프라인:초기화후보기준을지속움직임/느린drift/단발spike/누락의
  더넓은합성반례로비교. 실제기준채택과실측연속감시는장비복귀후별도검증.
  기존물리C++는변경하지않았다. 물리안전성검증이라고표현하지않는다.

## 이전 속도 초과 전후 기록 확보 (2026-09-07)

- capture_hg_readonly.py에 seconds(최대30)/sample-limit(최대36000) 옵션 추가.
  기존기본10초/6000개유지. 읽기전용원본전체기록으로초과후도보존하며
  seed writer/제어기와분리되어있다. seed검사임계값변경없음.
- 새30초읽기전용실행exit0:30143samples,span29.989756677초.
  logs/test_results/twist2_velocity_window_capture_20260907.jsonl.
  SDK/독립CRC오류0,motorfault없음,20ms초과gap없음,maxgap15.437296ms.
- joint2 maxabsdq0.126848042,p99 0.041139904rad/s.
  0.1초과7samples(0.02322%),4연속구간,최장관측span1.874359ms.
  joint2전체30초q범위0.004298798rad,순변화0.000241054rad.
  joint21 maxabsdq0.055223312rad/s,이전joint21초과는미재현.
- review_seed_velocity.py TriggerWindow 추가:첫초과sequence9648,
  전후범위8647..10652,pre0.999392814s/post0.999541977s,
  해당구간maxgap6.04999ms. 원본샘플은capture파일에보존한다.
  logs/test_results/twist2_velocity_window_review_20260907.json.
  관측span은샘플간시간이며실제초과지속시간의정밀측정으로해석하지않는다.
- 분석/기록형식회귀6passed. 물리C++해시불변.
  publisher/모드변경/물리출력/G1파일변경없음. 다른변경보존.
- 판단:짧은초과가낮은q순변화와함께관측되어단일샘플seed거부기준의
  민감도를검토할근거가생겼다. 외력/자세유지/추정노이즈중원인은미확정.
  다음은저장기록에서시간창기반초기화후보기준을오프라인비교한다.
  실제제어중단조건과분리하며현재runtime임계값완화는하지않았다.
  이전Quest→C++오프라인재생검증은여전히남아있다.

## 이전 seed 속도 시계열 검토 (2026-09-07)

- 사용자 설명 반영: 외력/Regular 자세유지로 관절속도가 발생할 수 있다.
  단일샘플0.1rad/s 초과는현행검사거부이며로봇이상/위험의증명이아니다.
  다만이번관측만으로외력/Regular가이전초과의원인이라고확정하지않는다.
- 기존검토한capture_hg_readonly.py로읽기전용추가수신,exit0.
  logs/test_results/twist2_velocity_capture_20260907.jsonl.
  6000sample cap으로5.943019056초 구간(10초전체아님),CRC오류0,
  최대수신간격5.773651ms,모드bytes0/5,모터fault없음,최대온도55.
- review_seed_velocity.py 신규:29축 abs dq최대/p99/초과비율,
  연속초과샘플구간길이,q범위/순변화.20ms초과gap은구간분리.
  보간하지않으므로single spike의관측span0은실제지속0을뜻하지않는다.
  CRC/nonfinite 검증후분석,seed나제어기임계값변경없음.
- 분석:이번구간전체maxabsdq0.088357292rad/s(joint3),0.1초과없음.
  joint21 max0.042951465,p99 0.024543693rad/s,
  q범위0.0000719051rad.이전-0.153398082초과는이번에재현되지않았다.
  logs/test_results/twist2_velocity_review_20260907.json.
- 시계열run/gap/경계값/불량데이터 회귀4passed.
  물리C++SHA256불변 E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.
  publisher/모드변경/물리출력/G1파일변경없음,다른작업보존.
- 기준검토:seed 초기화가능 여부와실제제어중단 기준은분리한다.
  향후초기화는시간창의q변화/속도분포/초과지속을함께검토하되
  임계값은현재짧은정상구간으로정하지않는다. CRC/finite/fault는별도검증.
  다음:초과직전·직후기록을확보하도록진단기록을준비하고재현될때분석.
  Quest→C++오프라인재생검증도남아있으며이번시계열분석으로대체하지않는다.

## 이전 Quest pinch 중단 확인 (2026-09-07)

- 새seed session twist2-seed-pinch-20260907로 simulation 시작.
  사용자 작은움직임→pinch완료 확인. 로그:
  logs/test_results/twist2_vr_shadow_20260907_175950_1b96b661.
- Python shadow1001datagrams,76active_updates,invalid0,transporterror없음.
  마지막입력 pinch_disengaged→후보stopped/input_disengaged 확인.
  첫active와초기seed29축오차0,오른팔외0..21변화0rad.
  오른팔최대움직임0.08967699785797967rad(약5.14도),범위제한중단아님.
  review.json 저장. 중단패킷에서수신기가종료하므로장시간중단유지는
  이번live로그로검증한것이아니며오프라인latched중단테스트와구분한다.
- 별도실패:초기화후공급기가joint21 dq=-0.153398082rad/s로
  0.1제한초과 ValueError/exit1. seed삭제확인. 전체공급시험은실패다.
  simulation은검증된초기seed를적용한뒤독립실행하므로공급기중단으로
  멈추지않는다. 실제로봇상태연속감시/실제출력interlock은미구현이다.
- 시험후shadow정상종료,Mink PID50324명령줄확인후종료.
  Unity그대로유지. 물리출력/publisher/G1파일변경없음.
- 다음:기록한새seed Quest패킷을C++0.08rad/s 목표갱신경로로오프라인재생,
  pinch이후갱신중단/나머지축유지검증. 별도로joint21속도초과원인을
  읽기전용시계열로확인해야한다. 임계값완화로숨기지않는다.

## 이전 Quest 첫engage seed 정렬 확인 (2026-09-07)

- 사용자 G1 정지 확인 후 새30초 읽기전용공급 실행:
  session twist2-seed-quest-retry-20260907, samples3941,updates1439,exit0.
  종료후seed삭제 확인. 이전 오류 임계값 변경없음.
- seed 환경변수를 지정해 사용자가 정한 BAT --standard-mink --external-feedback
  실행. simulation 표시/isolated MuJoCo3.12 실제 패킷 metadata 확인.
  5005/5012 PID45084,로컬shadow5008 PID22152. 시작 전포트미점유확인.
- 사용자 engage→움직임→pinch완료 확인. shadow로그:
  logs/test_results/twist2_vr_shadow_20260907_175712_ac57ef7a.
  1191datagrams,191active_updates,invalid_before_baseline0.
- alignment_review.json: 첫active29축과실제사용한initial seed의최대오차0rad,
  기록 전체의오른팔외0..21축변화0rad. 초기세션metadata로출처확인.
  이것은 시작 seed와의정렬이며engage시점의새LowState 동시추종검사가아니다.
- shadow는joint22의초기대비-0.175902883rad변화로±10도범위를넘어
  start_relative_limit로먼저중단. 사용자는pinch완료했으나shadow가이미종료해
  이번로그는pinch중단을검증하지못했다. Python shadow 시험이며새C++실행아님.
- 시험후이번Mink PID45084 명령줄확인후종료. shadow는자체정상종료.
  Unity프로세스는그대로유지. 물리출력/publisher/모드변경없음.
- 다음: 새seed/새세션에서더작은손움직임으로pinch중단을별도확인하고,
  새C++목표갱신경로와연결한기록검증을진행. 이번결과는물리안전성검증아님.

## 이전 Quest seed 초기화 거부 (2026-09-07)

- 사용자 Quest 시험 가능 확인 후5005/5008/5012 미점유확인.
  5008 로컬shadow만 시작(logs/test_results/twist2_vr_shadow_20260907_175453_10cd5c96).
- 새30초 읽기전용 공급(session twist2-seed-quest-20260907)은
  seed_position_or_velocity ValueError로 exit1. 원래 오류는 finite q/dq 또는
  abs dq>0.1을 함께 표시하므로 어느 관절/값인지는 이번 로그로 확정불가.
  실패 seed 삭제 확인. 과거seed 대체/제한완화/자동재시험없음.
- simulation/Unity Play는 시작하지 않았다. 로컬shadow는 패킷0상태에서
  이번에 생성한 Python PID47240의 명령줄 확인 후 종료.5008 해제확인.
  강제종료여서 shadow 최종result는 없을 수 있으며 정상완료로 간주하지 않는다.
- loader 진단을 nonfinite 또는 joint/dq/limit 표시로 세분화했다.
  검사 임계값은 동일. 관련16tests passed. 물리C++해시불변.
- live controller metadata에 초기seed q29/수신시각을 기록하도록 추가했다.
  실제Quest 출력과초기seed 비교용이며 이번 실행에서는아직출력되지 않았다.
- 다음: 로봇이 현재 정지해 있는지 사용자 확인 후 새 공급 재시험.
  fresh seed 통과 후 simulation 시작→실제Quest engage/움직임/해제 기록.
  물리출력/publisher/G1파일변경없음.

## 이전 production simulation seed 연결 (2026-09-07)

- START_VR_HAND_TO_MUJOCO.bat는 G1_MINK_INITIAL_SEED/SESSION 환경변수 중
  하나라도 있으면 --seed-from-environment를 MuJoCo3.12 진입점으로 전달한다.
  다른 엔진/하드웨어 표시 경로에서는 거부. 환경값을 CMD 명령에 삽입하지 않고
  Python에서 읽어 argv로 전달하며 seed/session 한쪽 누락도 엔진 import 전 거부.
  기존 환경변수 없는 실행은 유지. 실제 BAT/Unity 실행은 이번에 하지 않았다.
- run_mink_g1_simulation_312.py에 직접 seed/session 및
  --initial-state-check-only REPORT 옵션을 전달하도록 연결.
  controller의 check-only는 실제 모델/task/planner/trajectory를 준비하고
  fresh seed/충돌 검증 후 보고서 저장 및 return. 소켓/뷰어는 열지 않는다.
- 실제 isolated3.12 진입점 검사 통과:
  logs/test_results/twist2_seed_entry_check_20260907.json.
  seed_age_s=0.041203975677490234,clearance_m=0.02821232034905769,
  engine3.12.0,session=twist2-seed-entry-20260907,sockets_opened=false.
  기존 읽기 전용30초 공급기 정상 종료:samples7861,updates1447.
- seed 전달/누락거부/기존엔진·provenance/seed 검사27 passed(3.21s).
  logs/test_results/twist2_seed_entry_latest.xml.
  실제 Quest engage/화면/새C++ 정렬은 미검증,물리출력/G1파일변경없음.
- 다음 VR 시험에서 새 공급기와 동일한 세션/절대경로를 설정하고 실행:
  $env:G1_MINK_INITIAL_SEED = '<새 공급기가 갱신 중인 seed.json 절대경로>'
  $env:G1_MINK_INITIAL_SESSION = '<동일 session>'
  .\START_VR_HAND_TO_MUJOCO.bat --standard-mink --external-feedback
  시작직전5008등 점유확인,현재 seed250ms 조건 유지,이전로그 재사용금지.
  시험후 위 두 환경변수 제거. 실제 첫engage 목표와동일세션 실측 비교가 남았다.

## 이전 fresh seed Mink 모델 검사 (2026-09-07)

- 신규 audit_fresh_seed_mink.py: 화면/소켓/SDK 없이 파일을 읽어 모델 검사.
  로컬 XML을 임시폴더에 생성하고 operational limits를 적용한 뒤
  mink-default BuildPlanner + StandardMinkPlanner(horizon1)를 준비한다.
  새 seed를 기다려 ReadSeed의session/CRC/health/250ms검사를 거친다.
- 사용자의 진행 지시에 따라 기존30초 읽기 전용 공급을 새 세션
  twist2-seed-mink-20260907로 실행. 공급기 exit0,samples7643,updates1446.
  로그: logs/test_results/twist2_seed_mink_audit_20260907.json.
- fresh seed29축 적용 오차0, 그 외qpos는변경없음.
  CheckConfiguration=true, 검사한 collision pair 최소거리0.02821230965647659m.
  현재 wrist-yaw FK를 그대로 목표로 준 합성hold: valid=true,
  status=standard_mink_following,29축 최대변화0rad.
  검사완료 age=0.022821426391601562s,250ms이내. audit exit0.
- 이는 모델 초기화/검사한 충돌쌍/합성 유지 목표의 검사다.
  production live launcher 전체setup/Unity 표시/Quest 첫engage는 실행하지 않았다.
  BuildPlanner helper의 collision QP 설정과 live reserve 설정 차이가 있어
  전체 live 경로와 동일한 실행을 검증한 것으로 표현하지 않는다.
  실제freebase pose는여전히미측정. G1전신 안전거리 검증이 아니다.
- seed+standard Mink 회귀34 passed(16.81s),
  logs/test_results/twist2_seed_mink_latest.xml. 물리C++ SHA256불변
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.
  VR/publisher/모드변경/물리출력/G1파일변경없음. 다른 작업 보존.
- 다음: production simulation launcher에서 fresh seed 옵션을 연결하고
  실제Quest 첫engage 출력과동일세션실측값의정렬을검증한다.
  이때5008점유재확인,새seed공급중실행,오래된로그q재사용금지.

## 이전 읽기 전용 seed 재시험 결과 (2026-09-07)

- 사용자의 진행 지시에 따라 수정한 공유 읽기로 기존 승인 범위의 30초
  WSL Domain0/eth2 rt/lowstate 공급과 Windows35초 observer를 동시 실행했다.
  새 session=twist2-seed-shared-20260907,
  폴더=logs/test_results/twist2_seed_live_shared_20260907.
  VR/publisher/모드 변경/G1 파일 변경/물리 출력 없음.
- 공급기 정상 exit0: samples=8015, updates=1446.
- observer 정상 exit0: validated_updates=1281, errors=[],
  maximum_age_s=0.03838038444519043 (38.38ms,250ms 제한 이내).
  로그: logs/test_results/twist2_seed_live_shared_observer_20260907.json.
  관측한 각 seed에 session/CRC/29관절/health/수신시각 검증을 적용했다.
  20ms sleep+검증 시간 때문에 모든1446개를 관측한 것은 아니다.
  전체 갱신 간격과 모든 샘플의 무손실 수신을 증명한 결과는 아니다.
- observer seed_present_at_end=true: 공급기 초기화 시간 차이로
  observer가 공급기보다 먼저 종료했다. 이 필드를 수정하거나 숨기지 않았다.
  공급기 exit0 뒤 별도 Windows Test-Path=False 및 전용폴더 empty로
  seed와 임시파일 삭제를 확인했다. 현재 observer 자체는 공급기 종료와
  동기화하지 않으므로 다음 orchestration에서 종료 후 확인을 별도로 유지한다.
- 코드 변경 없이 실제 읽기 전용 재시험과 기록만 진행했다.
  물리C++ SHA256 불변:
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.
- 다음: fresh seed를 공급하는 동안 Mink29축 초기화/모델 충돌 및
  첫 engage 목표 정렬을 simulation 경로에서 검증한다.
  이번 로그의 first.q는 과거 관측값이므로 새 runtime seed로 재사용하지 않는다.
  freebase 실측/실제제어 arming/VR→단일 rt/lowcmd 송신자 연결은 미완료다.

## 이전 seed 파일 공유 오류 수정 (2026-09-07)

- 기존 변경사항과 공급기/검증기/loader를 읽고 다른 작업을 보존했다.
  G1/DDS/VR/publisher 실행 없음. WSL은 로봇과 무관한 합성 파일 교체만 실행했다.
- probe_seed_file_sharing.py: 새 전용 진단 폴더에서 WSL이 약50Hz로
  6KB 합성 JSON을 임시파일/fsync/replace하고 Windows가 약1ms 간격으로 읽는다.
  SDK import/소켓/로봇 접속 없음. 합성 파일은 runtime seed schema가 아니다.
- 수정 전: Windows 134회 읽기/8개 갱신 관측 후 PermissionError 1회,
  WSL os.replace도 PermissionError로 exit1. 원래 오류를 로봇 없이 재현했다.
  로그: logs/test_results/twist2_seed_sharing_before.json.
- g1_lowstate_seed.py의 ReadSeedBytes는 Windows CreateFileW에서
  FILE_SHARE_READ|WRITE|DELETE를 명시한다. 열린 이전 파일의 내용은 유지하면서
  WSL 교체를 허용한다. 읽기 크기는16385bytes로 제한하고 기존16384 제한을 유지.
  재시도나 오류 무시, timestamp 갱신/CRC/health 완화는 하지 않았다.
- 수정 후 동일조건: 500개 갱신 전부 관측, 6924회 읽기, 오류0, WSL exit0.
  로그: logs/test_results/twist2_seed_sharing_after.json.
  기존 Python 기본 open의 교체 공유 충돌을 원인으로 뒷받침한다.
- 회귀: 열린 파일 삭제 공유/이전 내용 유지/handle 종료, 미존재/크기 제한 및
  기존seed/observer/writer 검증 총19 passed.
  logs/test_results/twist2_seed_sharing_latest.xml.
  Windows os.replace 자체는 대상이 열린 동안 WinError5가 나므로 Windows 단위
  테스트는 unlink→replace로 DELETE 공유를 검증한다. WSL atomic 교체 검증은
  별도 probe 결과다. Windows writer 동시교체 지원으로 해석하지 않는다.
- 남은 항목: 실제 읽기 전용 LowState 공급과 Windows observer 재시험,
  이후 fresh seed 기반 Mink 초기화/충돌/첫 engage 정렬 검증.
  이번 합성파일 시험은 실제 로봇 안전성/VR→G1 연결 완료 검증이 아니다.

## 이전 승인한 seed 공급 시험 결과 (2026-09-07)

- 사용자가 승인한 WSL Domain0/eth2 rt/lowstate 읽기 전용 30초 공급기와
  Windows 35초 파일 observer를 동시에 실행했다. VR/publisher/모드 변경 없음.
- 공급기 exit 0: samples=7939, updates=1448. 종료 후 전용 폴더
  logs/test_results/twist2_seed_live_20260907가 비어 있어 seed와 임시파일 삭제 확인.
- Windows observer는 시작 약 6.8초 이내 seed.json read_bytes/open에서
  PermissionError [Errno 13]으로 exit 1. 결과 JSON 생성 전에 중단됐다.
  따라서 Windows 유효 seed 개수/최대 age/연속 갱신은 미검증이며 시험 실패다.
  WSL 교체와 Windows 읽기의 공유/권한 문제 가능성이 있으나 원인은 확정하지 않았다.
- observer가 FileNotFoundError 이외 OSError도 오류 목록에 보존하고 끝까지
  보고서를 작성한 뒤 exit 1 하도록 수정했다. 오류를 성공으로 무시하지 않는다.
  PermissionError 회귀 테스트 및 기존 seed/writer 테스트 총 17 passed.
  XML: logs/test_results/twist2_seed_supply_latest.xml.
- 물리 C++ SHA256 확인: E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.
  다른 작업 변경은 보존했다. 공급기 추가 실행은 하지 않았다.
- 남은 순서: WSL→Windows 파일 교체/접근 오류를 로봇 없는 재현으로 진단하고
  해결한 뒤 같은 읽기 전용 공급 시험을 새 폴더에서 재검증한다.
  그 후 현재 LowState seed 기반 Mink 초기화/충돌/첫 engage 정렬을 검증한다.
  실제 VR→G1 단일 송신자 연결과 물리 안전 검증은 아직 완료되지 않았다.
## 이전 LowState→atomic seed 공급기 준비 (2026-09-07)

- 현재 인계/capture/seed loader를 검토하고 로컬 코드를 작성했다.
  신규 WSL/DDS/로봇 실행/VR 시작/publisher/물리 출력 없음.
- 신규 lowstate_seed_writer.py: 세션별 새 폴더의 seed 경로를 소유한다.
  임시파일에 기록/fsync→기존 ReadSeed 검증→os.replace 순서로 교체한다.
  잘못된CRC/health/age/receipt 또는교체실패 시이전seed와임시파일을제거한다.
  기존다른파일을 인수하지 않으며 timestamp는새수신값일때만전진한다.
- 신규 supply_lowstate_seed_readonly.py: 승인 후 Domain0/eth2/rt/lowstate만
  최대30초 구독한다. 새run폴더를exclusive생성,약50Hz로 SDK CRC-packed seed를 갱신.
  msg수신 직후Unix wall-clock을부여하고CRC는수신마다검사한다.
  timeout/오류/종료시seed삭제. 강제종료로남아도consumer250ms만료로거부한다.
  외부45초timeout으로시작정체도제한할계획이다.
- 신규 observe_seed_file_offline.py: Windows에서35초동안seed파일만읽어
  동일session/CRC/health/250ms유효시간과종료후삭제여부를기록한다.
  WSL↔Windows wall-clock/DrvFs파일교체의실제동작은아직미검증이다.
- backend/tests/test_lowstate_seed_writer.py의6tests:
  교체/수신중단뒤만료/삭제,CRC/stale/receipt/replace오류시정리,
  다른소유파일보존 통과. 기존seed loader10개포함 **16 passed**.
  logs/test_results/twist2_seed_supply_latest.xml.
  합성시계+저장bytes fixture만사용했으며runtime seed파일은작성하지않았다.
- 기존물리C++ SHA256불변:
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.
- 다음승인요청:30초읽기전용DDS seed공급과Windows 파일검증만실행.
  session=twist2-seed-check-20260907,새폴더=logs/test_results/twist2_seed_live_20260907.
  Unity/Mink 실행이나모터명령/모드변경은포함하지않는다.
  실제제어arming/세션별VR프레임/전체base pose동기화는계속미완료다.

## 이전 Mink29축 LowState seed 초기화 경로 (2026-09-07)

- 현재 변경사항/인계/기본 초기화 함수를 확인하고 기존 변경분을 보존했다.
  기존 물리 C++/G1/WSL/DDS/publisher 실행·변경 없음. VR 프로세스도 시작하지 않았다.
- 신규 MuJoCo_G1_Controller/scripts/g1_lowstate_seed.py:
  schema g1.mink.lowstate_seed.v1,명시적session ID,29관절 이름 순서,
  received_at_unix_s의0..250ms age,reviewed SDK CRC-packed2092bytes를 검증한다.
  CRC 독립검사,mode0/5,finite q/dq/IMU,abs dq<=0.1,roll/pitch<=0.15,
  온도<=75/motorfault0 조건을 확인한다. 부정확한 관절값을 clamp해서 숨기지 않는다.
  이것은 시뮬레이션 초기 seed 검사이며 R1/실제제어arming 판정이 아니다.
- 기존 run_mink_g1_right_arm_virtual_center_live.py에 opt-in
  --initial-lowstate-seed PATH / --initial-lowstate-session ID를 추가했다.
  두 옵션은 함께 필요하며 없으면 기존 기본자세로 시작한다.
  model joint qpos 주소로29축을 모두 적용하고 태스크/목표 프레임을 그 자세에서
  초기화한다. 소켓 생성 전 age를 재검사하고 기존 planner의 CheckConfiguration
  충돌/범위 검사를 통과해야 한다. loader실패 시기본자세로 fallback하지 않는다.
- 적용은 joint29축에 한정된다. free-base 위치/방향은 model 초기값을 유지하며
  metadata base_pose_measured=false다. 실제 월드 프레임 정렬까지 완료된 것이 아니다.
  session은 seed와명시적실행값을 대조하며 아직Unity/수신기세션전달 전체계약은 미연결이다.
- 신규 backend/tests/test_lowstate_mink_seed.py:
  실제 저장 q를 테스트 시계로만 seed fixture화하여29축exact 적용/다른qpos유지/
  입력불변,stale/future/session/order/CRC/length/schema/representation 거부,
  관절범위오류의atomic거부10tests 통과. 오래된상태를live로 승인하거나runtime에 쓰지 않았다.
- 기존standard Mink24tests 포함 **34 passed**.
  XML logs/test_results/twist2_mink_seed_latest.xml.
  최종계약재검사10passed: logs/test_results/twist2_mink_seed_contract_latest.xml.
  syntax/diff 검사 통과. 새로운옵션으로 전체GUI시작/VR사용자확인은 아직이다.
- 다음 필수 연결: 명시적동일세션의최신LowState→seed파일을atomic갱신하는
  읽기전용공급기,플랫폼간wall-clock timestamp 확인,simulation launcher인자전달.
  현capture로그는wallclock/session envelope가없으므로live seed로바로사용할수없다.
  seed유효시간은완화하지않는다. 소켓전검사이후live첫engage freshness/일치 여부는
  C++정렬gate와동일세션상태로다시검증해야한다.
- 기존공유초기화파일/G1_USE_HARDWARE_INITIAL_STATE/BAT는변경하지않았다.
  실물초기화·single rt/lowcmd owner·물리안전성은계속미검증이다.
- 기존물리C++ SHA256:
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.

## 이전 저장 실측 자세↔VR 최초목표 정렬 검사 (2026-09-07)

- 현재 변경사항/인계와 MeasuredComposition의 기존 initial_arm_error0.025rad
  조건을 읽고 유지했다. 새로운 WSL/DDS/로봇 실행이나 물리 C++ 변경 없음.
- 신규 audit_saved_alignment.cpp는 실제 CRC-packed 상태에서1초 정지구간을
  확인한 뒤(1011samples) 저장Quest 첫 active 목표를 pose-only 검사에 전달한다.
  다른 시각에 수집한 세션이므로 packet receipt를 비교시각으로 재지정했다.
  따라서 동시수집 live 정렬 시험이 아니며 health/R1 arming 시험도 아니다.
- 결과 initial_arm_mismatch, 후보null. 오른팔7축 중6축이0.025rad를 초과했다.
| 관절 | 실측 rad | 저장 VR rad | 차이 ° | 허용 |
|---|---:|---:|---:|---|
| 22 right_shoulder_pitch | 0.16053 | 0.17453 | 0.80 | 통과 |
| 23 right_shoulder_roll | -0.05057 | -0.38397 | -19.10 | 초과 |
| 24 right_shoulder_yaw | -0.06134 | 0.00000 | 3.51 | 초과 |
| 25 right_elbow | 1.39617 | 0.95993 | -24.99 | 초과 |
| 26 right_wrist_roll | -0.10733 | 0.00000 | 6.15 | 초과 |
| 27 right_wrist_pitch | 0.28316 | 0.00000 | -16.22 | 초과 |
| 28 right_wrist_yaw | -0.07005 | 0.00000 | 4.01 | 초과 |

- 양성 대조군으로 동일 실측q를 목표로 만든 합성packet은 정렬 검사를 통과했다.
  합성packet은 테스트 안에서만 사용했고 runtime 파일/Unity/VR에 보내지 않았다.
  로봇을 기존 VR 기본자세로 이동하거나 관절 offset을 더하지 않았다.
- 공통 Mink 코드 g1_right_arm_common.py의 DEFAULT_RIGHT_ARM_READY_DEGREES는
  [10,-22,0,55,0,0,0]이며 저장VR 첫 목표와 일치한다.
  G1_USE_HARDWARE_INITIAL_STATE=1이면 별도 right_arm_q_rad를 읽는 기존 경로가
  있지만 freshness/동일세션/CRC를 이 loader가 확인하지 않으며7축만 초기화한다.
  이번에 환경변수/공용초기화파일/기존 hardware-sync launcher는 변경·실행하지 않았다.
- 다음 구현 대상: 최신 LowState와 동일세션에 묶인 Mink 초기 자세/기준 프레임
  동기화. 필요하면 full29축 기구학 자세까지 반영하고 collision/첫 goal 정렬을
  다시 검사해야 한다. 오래된 저장 snapshot을 현재 로봇 상태로 재사용하면 안 된다.
- MSVC C++17 /W4 /WX 빌드와 실제 mismatch 거부/합성 matched 허용2경로 통과.
  증거 logs/test_results/twist2_saved_alignment_review.json(입력hash/관절별오차 포함).
  pose-only 정지구간 검사 통과를 제어 초기화/물리안전성 통과로 해석하지 않는다.

## 이전 실제 tick 중복 분석·연속성 어댑터 수정 (2026-09-07)

- 저장된 실제6000sample을 Windows에서만 재생했다. 신규 WSL/DDS/로봇 접속/
  publisher/물리 출력 없음. 현재 변경사항과 인계 및 기존 어댑터를 읽고 수정했다.
- 같은tick291쌍 전부 IMU/motor/CRC 영역이 달랐고 header/remote/reserve는
  같았다. 전체bytes 동일쌍0,중복쌍receipt 간격0.329115~5.589701ms.
  따라서 tick을 패킷별 unique sequence로 해석한 기존 규칙이 관측자료와 맞지 않는다.
  실제 firmware의 tick 단위/갱신 구현까지 확인한 것은 아니다.
- 신규 offline_state_continuity.hpp: local receipt 단조 증가/20ms freshness와
  receipt gap을 유지한다. 동일robot tick은 허용하되 마지막tick 전진 이후20ms
  초과 시robot_tick_stalled. 역행/reset은 거부, uint32 rollover는 허용한다.
  중단은 latch되고 나중 전진으로 자동 복구되지 않는다. tick의 정상 주기 가정은 없다.
  이 검사는 Check 호출 시 동작하며 독립 타이머가 아니다.
- native_composition_offline.hpp는 이 검사를 사용한다. local sequence는
  유효상태마다 증가하므로 반복robot_tick을 local sequence로 대체하지 않는다.
  CRC/health/pose/alignment/deadman 조건은 완화하지 않았다.
- decoder에 hg_sdk_crc_le2092_b95a5304를 별도 profile로 추가했다.
  설치SDK CRC source 해시/패킹을 확인한 representation이며 native G1 ABI/
  CDR원본으로 명명하지 않는다. 기존native fixture profile도 유지한다.
- 신규 test_real_state_continuity.cpp:
  수집metadata CRC source/representation 확인→6000CRC/receipt/tick 연속성 통과,
  duplicate291허용, 합성stall/receipt재사용/stale/latch 검사 통과.
  실제 첫sample은 원본buttons0 상태로 native composition에 전달하여
  operator_stop/nullcandidate를 확인했다. R1값을 조작하지 않았다.
- 기존 native composition 테스트는 짧은중복 허용→지속정체중단으로 갱신했고
  capture/정책하체/캡처상체/health7종/rollover/역행/Finish만료까지 통과.
  MSVC C++17 /W4 /WX 빌드 통과. 회귀 **14 passed /110 subtests passed**.
- 증거:
  logs/test_results/twist2_real_state_continuity_latest.txt,
  logs/test_results/twist2_real_state_continuity_review.json,
  logs/test_results/twist2_native_composition_tick_latest.txt,
  logs/test_results/twist2_state_continuity_regression_latest.xml.
- 다음은 실측 캡처 자세와 VR 최초목표의 정렬 준비다. 현재 자료는 R1 off이며
  실제 제어초기화가 성공한 자료가 아니다. 실제single lowcmd owner/모드전환/
  비VR 물리시험/VR 물리시험은 여전히 미실행·미승인이다.
  코드의20ms 부동소수 경계 비교 문제는 이번 변경으로 별도 보정하지 않았다.
- 기존 물리 C++ SHA256 불변:
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.

## 이전 승인된 실제 LowState 수집 결과 (2026-09-07)

- 사용자 승인 후 검토된 수집기 source SHA256 d56b65fd…586d966을 재확인하고
  승인한 WSL timeout20s/eth2/rt/lowstate 구독 명령을1회 실행했다.
  publisher/모드 변경/SSH/G1 파일작업/기존 물리 C++ 변경은 없었다.
- 수집기는 정상 종료했다. 10초 전에6000sample 상한에 도달하여 실행 구간
  5.986866초, 첫~마지막receipt5.976110초를 기록했다. 10초 전체 수집으로 표현하지 않는다.
- 실제 파일: logs/test_results/twist2_hg_readonly_capture_20260907.jsonl
  SHA256 bf0ce906938c71f9870fbe6801f0fcf022d6b36632c57478c5d4a987c002feee.
  내용은 SDK CRC-packed2092bytes이며 DDS/CDR 원본 또는 G1 C++ ABI 증명이 아니다.
- 신규 review_hg_capture_offline.py는 Windows 파일만 읽는다.
  SDK CRC6000/6000 통과, 독립 table CRC6000/6000 통과.
  첫 sample은 별도 bitwise CRC와도 대조했다. q/dq/rpy nonfinite0,
  mode_pr/mode_machine 전구간0/5,29축 motor fault0,최고온도46도.
  최대abs dq0.0788515rad/s,최대abs roll0.0450964/pitch0.0260590rad.
  수신gap 중앙0.954377ms/최대5.966110ms,20ms초과0.
- **중요한 실제 입력 차이:** robot_tick 중복291쌍/역행0.
  중복쌍 중 전체packed bytes가 완전히 같은 쌍은0개다. 단순 동일패킷 재전송으로
  간주하지 않는다. tick 범위212748→218728이며 증가량0..6.
  현재 NativeCompositionOffline은 중복tick을 fault로 처리하므로 이 입력을
  그대로 정상 초기화 통과시킬 수 없다. 아직 조건을 완화하거나 필터링하지 않았다.
- remote buttons는 전구간0으로 R1 deadman 미입력이다. 읽기전용 수집에는
  문제없지만 현재 제어 초기화 조건은 충족하지 않는다. 사용자에게 R1을
  조작하도록 요청하거나 실제 제어를 시작하지 않았다.
- 요약: logs/test_results/twist2_hg_readonly_review_20260907.json.
  최대관절q범위는 index24에서약0.0001558rad였다. 실제 상태의 정지 경향은
  관측했지만 초기화/자세정렬/물리안전성 통과로 선언하지 않는다.
- 다음은 저장된 실제 자료로 tick 중복의 변경 필드를 분석하고,
  local receipt/sequence와 robot tick의 역할을 분리하는 검토다.
  추가 DDS수집이나 publisher 실행 없이 우선 오프라인으로 진행 가능하다.
- 기존 물리 C++ SHA256:
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.

## 이전 유선 연결 확인·LowState10초 수집 준비 (2026-09-07)

- 사용자 전원/유선 연결 알림 후 승인된 읽기 전용 SDK/인터페이스 점검을 재실행했다.
  eth2 UP/LOWER_UP,192.168.123.99/24 확인. SDK 버전/source hashes는 이전과 동일.
  아직 DDS 초기화/로봇 데이터 수신/명령 출력은 하지 않았다.
- WSL 공유파일 경로로 설치 SDK crc.py/LowState_/channel.py 소스를 읽었다.
  SDK CRC 패킹은2092bytes이며 native fixture offset과 대응한다.
  이것은 SDK가 재구성한 CRC용 bytes이며 수신 DDS/CDR 원본이나 G1 C++ ABI 증명은 아니다.
- 신규 capture_hg_readonly.py는 승인 후에만 SDK import/Domain0 eth2
  rt/lowstate subscriber를 만든다. publisher/모드 전환/LowCmd/SSH/G1 파일작업 없음.
  최대10초/6000sample,Read0.1초 timeout. Windows logs/test_results 아래
  새 파일만 exclusive 생성한다. 각 sample에 local monotonic receipt/robot tick/
  SDK CRC 검사결과/CRC용 packed_hex를 저장한다. bad CRC도 진단용으로 보존한다.
  outer timeout20초로 프로세스 기동/초기화 정체를 제한할 계획이다.
- test_capture_hg_pack.py는 설치 SDK에서 패킹 메서드 AST만 추출해
  표준 struct.pack으로 비교했다(SDK import/DDS 실행 없음).
  합성3tick fixture의2092bytes/CRC offset/전체bytes exact 비교1test 통과.
  XML logs/test_results/twist2_hg_capture_pack_latest.xml.
- 수집 source SHA256: d56b65fdf92bf6b8ce08694ac04f4a6aa6230c6ada2e9bab01649a26f586d966
- 구체적 승인 대상 명령:
  wsl -d Ubuntu -- timeout --signal=TERM --kill-after=2s 20s /home/user/.venvs/g1-teleop/bin/python -B /mnt/c/Users/user/Desktop/G1_Teleop_Project/experiments/twist2_right_arm_manual/capture_hg_readonly.py --output /mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/test_results/twist2_hg_readonly_capture_20260907.jsonl
- DDS discovery/상태 수신 네트워크 트래픽은 발생한다. 로봇에 명령을 보내는
  publisher는 만들지 않는다. WSL에서만 실행하며 G1 파일 생성/프로그램 실행 없음.
  설치/네트워크 설정/기존 물리 C++ 변경은 하지 않는다.
- 현재 승인 대기. 이 수집으로 state reception/CRC/간격/건강 상태를 확인한
  뒤에야 실측 초기화 가능 여부를 판단한다. 실제 움직임 승인이 아니다.

## 이전 승인된 WSL SDK 점검 결과 (2026-09-07)

- 사용자가 직전 제시한 WSL 읽기 전용 SDK/인터페이스 점검을 승인하여 그 명령만 실행했다.
  실행 전 source SHA256이 승인자료의084bb02d…99b08f5와 같은지 확인했다.
- Ubuntu /home/user/.venvs/g1-teleop/bin/python -B 실행 성공.
  metadata 기준 unitree_sdk2py1.0.1,cyclonedds0.10.2.
  Python hg LowState/MotorState/IMUState 및 CRC/channel source의 위치/해시 확인.
  /home/user/unitree_sdk2_python 아래 파일이며 실제 SDK import는 하지 않았다.
- 확인한 정확한 경로에서 C++ hg header는 나오지 않았다. 다른 위치에도 없다고
  결론내리지 않는다. Python package 버전은 G1 자체 배포 ABI 일치 증거가 아니다.
- 네트워크: eth2 DOWN/주소없음, eth0/1/3도DOWN. eth4 UP 192.168.133.103/24.
  기존 launcher가 찾는192.168.123.99 주소는 없다. 현재 기존 설정으로는
  수집기 시작 조건을 만족하지 못한다. 케이블/로봇 전원/Windows NIC 원인은 미확인.
- DDS 초기화/G1 접속/publisher 생성/네트워크 설정 변경/기존 물리 C++ 변경 없음.
  이번 승인은 SDK 점검에 한정되며 DDS 수집이나 물리 실행 승인으로 확대하지 않는다.
- 결과 요약과 확인 source hashes:
  logs/test_results/twist2_sdk_inventory_approved_20260907.json.
  전체 stdout은 이번 도구 실행 기록에 있다.
- 다음: G1 연결 상태를 준비하고 로컬 인터페이스를 재확인해야 한다.
  실제 LowState 수집은 해당 코드/범위 검토 및 별도 승인 후 진행한다.

## 이전 WSL SDK 읽기 전용 점검 준비 — 실행 승인 대기 (2026-09-07)

- 현재 인계/변경사항 및 기존 start_read_only_wsl.sh/read_only_lowstate_entry.py를 검토했다.
  기존 수집은 요약 JSON/forward 경로로 native ABI/원본 CRC 확인에 부족하다.
  VIEW_G1_LIVE_MUJOCO.bat에는 pkill 경로도 있어 이번 확인에 사용하지 않는다.
- 신규 inspect_wsl_sdk_readonly.py는 표준라이브러리만 사용한다. 설치 distribution
  metadata와 알려진 정확한 SDK source 경로의 크기/SHA256, ip -j address show를 출력한다.
  editable 설치는 direct_url.json의 local file 경로만 추가한다. recursive 탐색,
  SDK import, DDS 초기화, G1 접속/파일 변경, 송신자/모드 제어가 없다.
- Windows에서 Inspect helper의 exact path/hash/미존재2테스트 통과.
  실제 WSL 실행/경로 존재/SDK 상태는 아직 확인하지 않았다.
  XML: logs/test_results/twist2_sdk_inventory_tests_latest.xml.
  source SHA256: 084bb02d68b020f569e61cd3ebd74e651b5c1e5eff44c85df8175596099b08f5
- 승인 요청 범위는 다음 한 번의 WSL Ubuntu 로컬 점검뿐이다:
  wsl -d Ubuntu -- /home/user/.venvs/g1-teleop/bin/python -B /mnt/c/Users/user/Desktop/G1_Teleop_Project/experiments/twist2_right_arm_manual/inspect_wsl_sdk_readonly.py
  -B는 Python bytecode 쓰기를 막는다. 출력은 stdout이며 Windows 쪽 로그로 보관 가능.
  WSL 배포명/venv 경로는 기존 launcher에서 읽은 값이고 실제 존재는 실행 전 미확인이다.
- 이 승인은 DDS 수집/로봇 실행/컴파일/설치/물리 제어 승인과 별개다.
  정확한 SDK 형식과 경로를 확인한 후 별도의 read-only LowState 수집 코드를
  준비하고 검토해야 한다. 임의 native2092byte ABI 일치를 가정하지 않는다.
- 실제 G1 초기화/단일 송신자 배포/물리 안전성은 계속 미완료다.
  기존 물리 C++는 수정하지 않았다.

## 이전 native LowState→초기화→전신 후보 연결 (2026-09-07)

- 현재 변경사항/인계/native decoder/초기화 코드를 검토했다. 기존 물리 C++와
  다른 작업은 유지했고 G1/WSL/DDS/UDP/publisher/물리 출력 실행 없음.
- 신규 `native_composition_offline.hpp`는 native bytes를 DecodeOfflineHgNative에
  통과시켜 실제 입력 형태의 sample/health를 GuardedComposition Prepare에 전달한다.
  JSON/Mink를 measured state로 대체하지 않는다. Finish가 유효 policy를 받은
  뒤에만 후보를 노출한다. 초기 정지1초→VR 첫 목표 정렬→정책 하체와 캡처 상체
  결합까지 기존 개별 단계를 연결했다.
- CRC/ABI profile/health/age 외에 receipt 증가와 robot tick 연속성을 검사한다.
  tick duplicate/backward/reset은 latch중단, uint32 max→0 rollover는 serial
  arithmetic으로 허용한다. tick 단위/최대 허용 jump는 배포 확인 전 미검증이다.
- profile은 여전히 `hg_native_le2092_9754cd15`라는 Windows native fixture
  layout이다. 실제 G1 배포 ABI 확인도 DDS/CDR 디코딩도 아니다.
- `test_native_composition.cpp`: pinned SDK class accessor로 만든 합성 LowState
  bytes→CRC→1초 settle→VR align→policy legs/캡처 upper를 검증했다.
  waist12를 모델 default와 다른0.1rad로 설정해 실측 입력 역할의 capture를
  사용하는지 확인했다. Prepare 중 후보null, 정상Finish 후0번 정책 반영/
  12..28 캡처 유지,중복tick 후후보제거/재개금지 통과.
  CRC/profile/stale/R1/mode/motor fault/tilt7종 거부, rollover/backward,
  Finish state 만료도 통과했다.
- 초기 시험은 strict20ms 간격 경계에서 실패했다. fixture cadence를10ms로
  하여 경계 반올림을 피했다. strict age/receipt gap20ms 비교의 부동소수 경계
  처리는 변경하지 않았으므로 정확히20ms cadence에 대한 허용을 주장하지 않는다.
- MSVC C++17 /W4 /WX 및 관련 회귀 **14 passed /110 subtests passed**.
  증거: `logs/test_results/twist2_native_composition_latest.txt`,
  `logs/test_results/twist2_native_composition_regression_latest.xml`.
- 로컬 기존 상태 자료도 확인:
  `logs/runtime/g1_hardware_lowstate.json`은2026-09-07 14:42:30 저장된
  read_only_lowstate 상태 요약으로 당시 mode_pr0/mode_machine5와29축q/dq가 있다.
  native bytes/CRC/시간 연속 sample이 없어 이번 native 초기화 입력으로 사용할 수 없다.
  내부 last_packet_age_s는 저장 당시 값이며 현재 fresh 상태로 해석하면 안 된다.
  `logs/review/20260903/saved_lowstate_review_fixture.json`은29축0값 fixture다.
- 실물 전환에 필요한 다음 입력: 배포 SDK/native layout 확인과 최신 연속
  LowState 원본 및 local receipt 시각. 현재 로컬 자료만으로 실측 초기화
  완료를 선언할 수 없다. G1/WSL/DDS 실행 금지는 유지한다.
- 단일 송신자 연결은 아직 후보 계산 단계다. 0..11 정책/12..21 캡처/
  22..28 VR 소유권을 구성할 수 있지만 실제 lowcmd writer/모드 handoff/
  종료 lifecycle과 배포 ABI는 미연결이다. native 후보 연결 통과는 물리 안전성 검증이 아니다.
- 기존 물리 C++ SHA256 불변:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.

## 이전 worker 응답 제한시간·실물 전환 우선순위 (2026-09-07)

- 사용자 요청에 따라 실물 연결의 필수 장애 처리부터 진행했다.
  현재 변경사항/인계/worker를 읽고 기존 물리 C++와 다른 작업은 유지했다.
  G1/WSL/DDS/UDP/publisher/물리 출력 실행 없음.
- 신규 `policy_worker_client_offline.py`: 자신이 만든 로컬 worker에만 접근하는
  단일 요청 client다. daemon I/O thread가 pipe write/read를 수행하며 부모는
  초기 ready10초/요청응답30ms deadline으로 대기한다. 최대응답65536bytes,
  newline/UTF8 JSON/중복key/NaN/응답ID/finite29축[-2,2]를 검증한다.
  오류는 latch되며 worker를 종료하고 늦은 결과로 재개하지 않는다.
- `policy_cpu_worker_offline.py`는 request_id를 응답에 되돌린다.
  기존 list 입력은 출력 동등성 비교용으로 유지한다. 실제 client는 ID 포함 dict를 사용한다.
- `run_event_clock_offline.py`는 새 client를 사용하고 오류를 worker_failure
  이벤트로 C++ Stop에 전달한다. 무응답을 무기한 readline으로 기다리던 경로를 제거했다.
  모의 큐에서는 elapsed 이후 Stop 이벤트이며 live 비동기 제어 구현은 아니다.
- deadline은 OS 실행 상한 보장이 아니다. timeout 감지 후 소유 worker
  terminate/wait/kill 및 thread join의 정리 시간이 추가된다(각1초 제한).
  시험에서 오류 호출은 정리 포함1초 미만이고 프로세스/thread 종료를 확인했다.
  현재 메모리 재생의 C++ stdin 응답 자체에 대한 장애 처리는 별도다.
- 신규 client 테스트5개/내부14case: 응답timeout/EOF/깨진JSON/ID불일치/
  boolean action/oversized, 시작timeout,NaN/중복key,정상ID응답,
  장애6종→C++ pending Stop→늦은Finish·재engage 후 history/target 불변.
  합성 worker는 모두 로컬 테스트 프로세스이며 무관한 PID를 종료하지 않았다.
- 전체 관련 회귀 **28 passed /124 subtests passed**.
  직접 정책과 worker 출력 exact8입력 비교도 unittest1개 통과.
- 실제CPU/저장Quest 정상 재생 통과: inference1800/history385/writer3921,
  최대왕복4.9294ms, 해제36.591642초, 늦은completion1개 폐기.
  fixed_inference_ms=null. warm-up10회는 모의 시계 밖이며 실시간/물리 안전성 보장은 아니다.
- 증거:
  `logs/test_results/twist2_worker_deadline_regression_latest.xml`,
  `logs/test_results/twist2_worker_deadline_20260907/result.json` 및 timing/trace,
  `logs/test_results/twist2_worker_deadline_equivalence_latest.txt`.
  물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.

### 실물 VR까지의 필수 순서 — 부가 오프라인 시험보다 우선

| 단계 | 현재 상태 | 통과에 필요한 증거 |
|---|---|---|
| 입력/정책/목표/중단 로컬 준비 | 합성·저장파일 재생 통과 | 위 테스트·trace; 실제 로봇 안전성과 구분 |
| 실제 LowState 초기화 | 미완료 | 실제 배포 SDK/LowState 형식 확인, fresh CRC/모드/관절/속도/IMU 상태와 정지구간 캡처, VR 첫 목표 정렬 |
| 단일 full-body owner 연결 | 미완료 | 기존 물리 C++를 유지한 별도 검토 가능한 연결안, 0..11 정책·12..21 할당·22..28 VR 통합, 송신자1개와 fail-stop |
| 제한된 실물 비VR 시험 | 미승인/미실행 | 실행 파일·대상·모드 전환·중단/종료 동작을 사전에 특정하고 승인 후 확인 |
| 최초 실물 VR 시험 | 미승인/미실행 | 앞 단계 통과, 작은 목표 범위·0.08rad/s·해제/오류 중단 확인 |

- 다음 작업은 실제 LowState 입력과 단일 owner의 연결 준비다. 동일한 정상
  오프라인 검사를 반복하는 것으로 실제 초기화/물리 시험을 대체하지 않는다.
- 기존 physical writer의 순차 clamp 충돌 반례는 아직 물리 원본에 수정되지 않았다.
  새 owner 연결 때 해결/검토해야 하며 Arm SDK 사고 원인으로 단정하지 않는다.
- 현재 금지된 G1/WSL/DDS/publisher 실행은 별도 구체적 범위의 승인이 필요하다.
  기존 Arm SDK 기울어짐은 해결이 아닌 보류이며 새 C++의 Unity 시각화도 별개다.

## 이전 CPU 지연 분리 측정·정책 worker 격리 (2026-09-07)

- 인계/현재 변경사항/측정 코드를 읽고 로컬 파일 재생만 수행했다.
  기존 물리 C++/G1/WSL/DDS/UDP/publisher/물리 출력은 변경·실행하지 않았다.
- `run_event_clock_offline.py`에 tensor/model/output 시간, 호출 thread CPU 시간,
  GC callback의 시작/종료·generation을 기록했다. 성공/실패 모두
  `normal_timing.json`에 매 추론 구간을 저장한다.
- 직접 실행 실패를 재현했다: total40.9698ms, tensor0.0506ms,
  model40.8806ms, output0.0386ms. 이 model 구간에 generation2 GC가
  40.5913ms 실행됐다. 따라서 이번 재현에서 GC가 지연 대부분을 차지했다.
  이전52.03ms 건은 당시 세부 계측이 없어 동일 원인으로 단정하지 않는다.
  thread_time 값은 Windows의 거친 해상도로0/46.875ms 등이 나와 세부 분해에 사용하지 않는다.
- 신규 `policy_cpu_worker_offline.py`: 해시 검증한 동일 bytes 모델을
  별도 로컬 Python 프로세스에서 CPU 실행한다. stdin/stdout JSON만 사용,
  소켓/SDK 없음. 부모는 이 모드에서 torch/model을 로드하지 않는다.
  GC를 끄거나 임계값을 바꾸지 않고 policy heap과 replay/log heap을 분리했다.
- `--raw-input --isolated-policy`는 JSON 인코딩/pipe 왕복/worker 실행/
  응답 decode까지 포함한 실제 경과시간을 모의 Finish 시각에 더한다.
  worker 내부 세부시간도 별도 기록한다. 고정 완료시간 옵션은 사용하지 않았다.
  기존 직접 실행/고정시간 옵션은 비교용으로 남아 있다.
- 초기 model 로드/warm-up10회는 모의 시계 밖이다. 부모 event processing/
  전체 OS scheduler의 모든 지연을 모의 시계에 더하는 구조는 아니다.
  실제 asynchronous robot control이나 실시간성을 입증한 것은 아니다.
- 분리 실행2회 정상 종료:
  - 첫 실행1800 inference/history386/writer3921, 최대왕복1.8442ms,
    중앙값0.7393ms, worker 내부 최대0.9748ms. 측정 window에서 부모/worker
    generation2 GC event는0개였다.
  - worker 정리 경로 보강 후 최종v2도1800 inference/writer3921,
    최대왕복2.0556ms. history385/해제 뒤 completion1개 폐기.
    마지막 Finish와 raw release의 측정시간 순서에 따른 차이이며 재개 없음.
  - 두 실행 모두 raw release36.591642초에 input_disengaged.
  30ms state freshness 기준은 그대로다. 최대치의 장기 상한을 보장하지 않는다.
- 신규 `test_policy_worker_offline.py`는 합성1432차원8입력에 대해
  직접 실행과 worker의 clip 후29축 출력을 exact 비교해 통과했다.
  별도 unittest1개/내부8case이며 관련 pytest는 **23 passed /110 subtests passed**.
  syntax/diff check 및 worker 정상 종료 확인. 물리 C++ SHA256 불변:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 증거:
  `logs/test_results/twist2_timing_split_20260907/failure.json` 및 timing,
  `logs/test_results/twist2_timing_isolated_20260907/result.json`,
  `logs/test_results/twist2_timing_isolated_20260907_v2/result.json` 및 timing/trace,
  `logs/test_results/twist2_policy_worker_equivalence_latest.txt`,
  `logs/test_results/twist2_cpu_isolation_regression_latest.xml`.
- 남은 다음 단계: worker 응답 누락/비정상 종료/잘못된 응답에 대한 제한시간과
  stop 전파를 파일·합성 worker로 검증한다. 현재 readline은 응답을 동기 대기하며
  worker hang에 대한 응답 deadline은 없다. 정상 종료/예외 정리의5초 대기는 별도다.
  실제 LowState/배포 ABI/동역학/물리 안전성 및 live 동시성은 계속 미검증이다.

## 이전 raw 입력 감시와 pending 추론 중단 (2026-09-07)

- 현재 변경사항과 인계/validator/queue/event harness를 읽고 기존 작업을 유지했다.
  물리 C++/G1/WSL/DDS/publisher/UDP 실행·수정 없음.
- 신규 `raw_input_watch_offline.hpp`: 단일 이벤트 소유자가 raw 도착 시
  InputValidator로 즉시 검증한다. 유효 active만64개 FIFO에 보관하고 Prepare가
  한 번 drain한다. 완전히 검증된 pre-engage inactive는 대기하며 보관하지 않는다.
  bootstrap validator는 drain과 무관하게 session/sequence를 유지한다.
- payload16384bytes/queue64 제한, 전체 스키마/해제/중복sequence/250ms
  receiver timeout을 검사한다. 오류 시 FIFO를 지우고 latch한다.
  timeout은 이벤트에서 Poll하므로 별도 실시간 timer/독립 thread 구현은 아니다.
- `test_event_clock_loop.cpp`의 선택적 raw_input 모드:
  packet/poll을 추론 pending 동안 처리하고 guard/history/writer/desired를
  함께 중단한다. raw 모드 build에 외부 packet batch를 섞으면 거부한다.
  기존 batch 모드는 유지한다. Finish/다른 이벤트 앞에서도 timeout을 확인한다.
- `run_event_clock_offline.py --raw-input`은 외부 stop tick 주입을 제거하고
  raw packet을 동일시각 writer/finish보다 먼저 처리한다.
  동일시각 packet 간에는 원본 FIFO 순서를 유지한다.
- 신규 `test_raw_event_clock.py` **9종 통과**: 해제=완료 시각 및 재engage,
  pending malformed JSON, drain 뒤 duplicate,250ms 경계와 timeout,
  oversized, pending65번째 queue overflow, FIFO 중간 역순sequence,
  engage 전 idle 장기대기, 유효 batch drain1회.
  합성 zero-action 정책 입력이며 실제CPU 정책 시험과 구분한다.
  중단 최초 및 늦은 Finish/재engage 이후 history/previous/target/write 불변,
  desired 제거/pending 취소/FIFO 제거를 검사했다.
- **실측 duration 재생은 통과하지 못했다.** warm-up1회로2회 시도했으나
  active 이전 state_expired_during_inference로 중단됐다. warm-up10회 후에도
  동일하게 실패했으며 v3 failure.json에 최대52.0336ms window가 기록돼 있다.
  window는 tensor 생성/model/clamp/list 변환을 포함한다. 지연 원인은 미진단이다.
  30ms state freshness 제한을 완화하지 않았다. 첫2회는 콘솔 오류만 남고
  v3부터 failure.json으로 trace를 저장하도록 개선했다.
- 입력 스케줄 검증을 분리하기 위해 `--fixed-inference-ms 1` 옵션을 추가했다.
  실제 CPU action은 계산하되 완료 시각만 명시적1ms 모의 값으로 사용한다.
  이 모드 **정상 재생 통과**: inference1800/history386/writer3921,
  raw 해제 도착36.591642초에서 input_disengaged 중단.
  다음 policy tick36.6105804초를 기다리지 않는다. 실제 물리 지연 측정이 아니다.
  이 실행의 실제 측정 최대40.8206ms도 별도 보고하며 실시간 통과로 해석하지 않는다.
- 상태는 정책 frozen virtual baseline/writer previous-target zero-velocity
  fixture로 유지한다. G1 LowState/동역학/로봇 안전성 검증이 아니다.
- C++17 /W4 /WX 빌드 통과. 관련 회귀 **23 passed /110 subtests passed**.
  증거:
  `logs/test_results/twist2_raw_event_regression_latest.xml`,
  `logs/test_results/twist2_raw_event_clock_20260907_v3/failure.json`,
  `logs/test_results/twist2_raw_event_clock_fixed_20260907/result.json` 및 trace.
- 물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 다음: 로컬 CPU 측정 window의 지연 구간을 tensor 준비/model/후처리로
  분리해 원인을 조사하고, 실측 시계에서 정상 종료까지 가능한지 확인한다.
  raw 입력 로직의 결정적 시험은 완료했지만 이번 실측 시간 전체 재생은 실패다.
  실제 로봇 실행 및 LowState/배포 ABI/동역학 검증은 미완료다.

## 이전 단일 이벤트 시계 통합 검증 (2026-09-07)

- 현재 변경사항과 인계/GuardedComposition/ObservationHistory/writer를 확인했다.
  기존 물리 C++/다른 작업은 변경하지 않았다. G1/WSL/DDS/UDP/publisher 실행 없음.
- 신규 `test_event_clock_loop.cpp`, `run_event_clock_offline.py`:
  raw Quest 파일을 기존 Replay로 검증하고 Prepare→실제 CPU 추론→Finish→
  desired/history→2ms writer를 하나의 모의 이벤트 시계에서 실행한다.
  source tick은 기록된 약50Hz cadence, writer는 첫 candidate 후2ms 간격이다.
  Python heap 순서는 같은 시각 stop→writer→finish→packet→build다.
- Prepare 시각을 Finish 시각으로 재사용하던 방식과 달리 실제 측정 inference
  duration을 더한 완료 시각을 Finish에 전달한다. 정책 created_at은 완료 시각이며
  inference 중 snapshot30ms age 만료를 GuardedComposition에서 검사한다.
  단일 추론만 pending으로 허용하고 그동안 build는 건너뛰며 packet은 다음 build까지 보관한다.
- writer 실패가 guard.Abort/history.Stop/desired 제거로 전파된다. stop은
  pending observation과 준비 중인 upper를 취소한다. 이후 finish는 폐기되며
  target/history/previous_action은 유지된다. 정상 history feedback은 writer의
  rate-clipped q가 아니라 기존 규약대로 성공 Finish의 blend desired다.
- 모델은 검증된 같은 bytes TorchScript를 CPU로 실행한다. 초기 warm-up1회는
  모의 작업 밖에서 수행했고 cold-start/실시간성 검증으로 표현하지 않는다.
  이번 정상 최대 inference9.5081ms. NumPy 미설치/jit.load deprecated 경고가
  있으나 tensor-only 실행은 성공했다.
- 4종 통과:
  - 정상: inference1800/history386/writer3931, input_disengaged.
  - 40ms 지연 Finish: history13/writer152 후 state_expired_during_inference.
    해당 Finish는 후보/history에 commit하지 않았다.
  - 추론 pending 중 writer state age30ms 주입: history13/writer132에서
    state_timeout; 이후 완료 결과1개 폐기.
  - 마지막 추론40ms 지연 중 해제: history385/writer3931, 결과1개 폐기.
- 매 이벤트 history1270개/previous_action29개/commit count를 독립 비교했다.
  성공 writer의 rate/overshoot/12..21 유지, stop 최초·이후 target 불변과
  desired 제거/pending 취소도 확인했다.
- 해제는 raw 파일의 검증된 stop tick36.6105804초를 외부 stop 이벤트로 주입한다.
  이 이벤트에서 즉시 메모리 latch되며 그 뒤 writer 갱신은 없다.
  raw packet을 추론 중 별도 validator로 처리한 시험이나 실제 pinch 지연 실측은 아니다.
- 상태 경계: 정책 state는 frozen virtual baseline, writer state는 직전 target/
  zero velocity fixture다. history 연결과 stop 전파는 통합됐지만 두 단계가
  동일한 실제 LowState를 사용하거나 writer 위치가 다음 policy q 관측으로
  돌아가는 동역학 closed-loop는 아니다. 실로봇 안전성은 계속 미검증이다.
- C++17 /W4 /WX 빌드 통과. 기존 writer 단독 검사와 관련 pytest
  **14 passed /110 subtests passed**, skip0.
  결과: `logs/test_results/twist2_event_clock_20260907/result.json` 및4종 trace,
  `logs/test_results/twist2_event_clock_regression_latest.xml`.
- 물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 남은 다음 단계: 추론 pending 동안 raw 입력의 해제/오류/timeout을 별도
  검증해서 stop으로 전달하는 로컬 경로. 현재 외부 stop tick 주입을 대체하고
  packet FIFO/재참여/중복 sequence와 동시 완료 우선순위를 검증한다.
  실제 LowState/배포 ABI/동역학/콜드 스타트/실시간성/물리 실행은 미완료다.

## 이전 정책 trace→500Hz 다중 주기 재생 (2026-09-07)

- 현재 변경사항과 CHAT_HANDOFF/정책 history/writer 코드를 확인한 뒤 진행했다.
  다른 작업과 물리 C++는 변경하지 않았다. G1/WSL/DDS/UDP/publisher 실행 없음.
- 신규 `test_writer_trace_loop.cpp`는 stdin/stdout 전용 C++ probe다.
  `replay_writer_policy_trace.py`가 실제 CPU 정책/blend trace를 읽고 기록된
  inference_ms를 단일 worker 결과 도착 지연으로 반영하여 2ms writer를 호출한다.
  같은 시각에는 stop을 completion보다 먼저 처리하고 중단 후 completion은 폐기한다.
- CPU 정책 원본 재생을 새로 실행했다: 정상 1800 inference/386 commit/active240,
  tilt/blend_gate 포함 3종 통과. 첫 CPU 추론 36.1463ms, 중앙값 0.45805ms.
  전체 시작 구간을 포함한 실시간성 보장은 아니다. writer 재생은 첫 유효
  candidate 이후 구간만 사용하므로 초기 warm-up 지연은 포함하지 않는다.
- 입력은 alpha=1인 완료된 blend만 허용하며 feedforward=0 합성 fixture다.
  writer state는 직전 target q/zero dq로 매 tick 갱신한 이상화된 입력이다.
  정책 관측은 원본 frozen virtual baseline을 그대로 사용한다. writer 결과가
  정책 관측/history로 돌아가지 않는 open-loop trace 재생이며 동역학 모델이 아니다.
- 4종 통과:
  - 기록 inference 지연: 3931 writer tick, input_disengaged 중단.
  - 100ms까지 결과 도착 정체 주입: 223 tick 뒤 command_timeout, 이후 결과366개 폐기.
  - state receipt 갱신 중단: 209 tick 뒤 state_timeout, 이후 결과365개 폐기.
  - 마지막 candidate 40ms 추가 지연: 해제 후 결과1개 폐기, 재개 없음.
- 해제는 source의 검증된 stop tick 36.6105804초를 사용한다.
  writer 중단 36.6121153초, 전달 지연1.5349ms(모의 시계).
  실제 pinch/UDP 수신부터의 지연 또는 Windows 스케줄러 실측이 아니다.
- 성공 tick마다 rate/overshoot/waist·왼팔12..21 유지, 실패 첫 tick의 전체
  commit 취소, 이후 target 불변/damping 진단을 독립 비교했다.
  하체0..11은 정책대로 변경되므로 이 full-body writer에서 유지 대상이 아니다.
  최대 step 0.00400000066rad는 float 반올림을 포함한 하체2rad/s×2ms다.
  VR0.08rad/s와 writer 상체0.8rad/s는 별도 상한이다.
- 첫 release_pending 시험은 마지막 candidate가 해제20.24ms 전이어서 20ms
  주입 구간에 포함되지 않아 검사 실패했다. 30ms 선택 구간으로 수정하여
  실제 지연 completion이 존재하는 것을 확인했다. 최종 결과는 v3다.
- C++17 /W4 /WX 빌드 및 writer 단독 테스트 통과.
  pytest **14 passed /110 subtests passed**, skip0.
- 증거:
  `logs/test_results/twist2_writer_policy_source_20260907/result.json`,
  `logs/test_results/twist2_writer_multirate_20260907_v3/result.json` 및 4종 trace,
  `logs/test_results/twist2_multirate_regression_latest.xml`.
  입력 normal trace SHA256:
  `9e231b7eae74bfb9e8d2989b98747df1db234467770df0f11f6ce30317ed301b`.
  물리 C++ SHA256은 이전 기록 E61D8A3C…CC09F와 동일하다.
- 남은 다음 단계: Prepare→실제 추론 완료→Finish→writer를 하나의 모의
  이벤트 시계로 연결하여 stale 추론 폐기와 history commit 순서를 검증한다.
  현재는 precomputed 후보 전달 시험이므로 upstream freshness 검증의
  실제 추론 지연 반영 및 writer 중단의 upstream 전파는 아직 통합되지 않았다.
  실제 LowState/배포 ABI/동역학/물리 안전성은 계속 미검증이다.

## 이전 500Hz writer 계산 오프라인 검토 (2026-09-07)

- 기존 변경사항을 먼저 확인하고 물리 C++의 rate → joint → torque → joint
  순서를 검토했다. 기존 물리 C++와 reference 원본은 변경하지 않았다.
- 새 `offline_writer_study.hpp`는 소켓/SDK/LowCmd 직렬화 없는 메모리 진단이다.
  2ms당 하체 2.0rad/s, 상체 0.8rad/s writer 상한을 사용한다.
  VR 목표의 0.08rad/s 제한과는 별도 단계다. kp/kd/torque 상수는 로컬
  reference와 drift-test로 대조했다.
- 합성 입력으로 기존 순서의 충돌 2개를 재현했다. 관절27에서 last=desired=0,
  measured q=0.2/dq=0/ff=0이면 torque clamp가 목표를 0.075rad까지 옮겨
  0.0016rad writer 변화량을 넘는다. 같은 관절이 soft upper bound에 있고
  dq=1.5/ff=-2.5이면 최종 joint clamp 뒤 예측 torque=-4Nm로 2.5Nm를 넘는다.
  이는 소스 수식의 합성 반례이며 Arm SDK 기울어짐의 원인 진단이 아니다.
- 새 모델은 rate/joint/torque 구간의 교집합으로 제한한다. 교집합이 없으면
  전체 target commit 취소 후 damping 진단으로 latch한다. 따라서 충돌 시
  기존 물리 계산과 의도적으로 다르며 실제 controller에 적용된 수정이 아니다.
- health/20ms state watchdog, 60ms command watchdog(250ms grace), R1/비상정지,
  gains, capture torque clamp/fade, 중단 후 재개 금지와 35슬롯 damping을 검증했다.
  damping 진단의 predicted_torque=0은 미계산 placeholder다. 실제 토크가
  0이라는 의미가 아니다. damping 지속시간/종료 lifecycle은 아직 모델링하지 않았다.
- 모델 추가 규칙: 호출 간격 최소2ms, 긴 간격에도 고정2ms 변화량만 허용,
  desired 생성시각은 activation 이후여야 한다. 실제 scheduler/clock 측정은 아니다.
- `test_offline_writer_study.cpp`: 500tick×29축 정상 reference 일치/변화율/
  overshoot/gain/예측torque, 오른팔만 목표 변경 시 0..21 유지, 오류12종
  atomic 취소/latch, 충돌2종, watchdog/grace/명시 stop/누락desired,
  torque fade101단계 및 잘못된 alpha 거부 통과.
- MSVC C++17 /W4 /WX 빌드 통과. 관련 pytest **14 passed /110 subtests passed**.
  로그: `logs/test_results/twist2_writer_study_latest.txt`,
  `logs/test_results/twist2_writer_regression_latest.xml`.
- 물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
  G1/WSL/DDS/publisher/물리 출력은 실행하지 않았다.
- 다음: 저장 Quest→CPU 정책→blend의 desired를 이 모델에 연결하여
  50Hz/500Hz 다중 주기와 추론 지연·해제 전파를 파일 재생으로 검증한다.
  현재 writer 테스트는 합성 입력 단독이며 그 전체 경로 연결은 아직이다.
  실제 LowState/배포 ABI/동역학/실시간성 및 로봇 안전성은 미검증이다.

## 현재 upper 사전 준비·blend 순서 연결 (2026-09-07)

- 현재 변경사항과 physical mimic_target→infer→hybrid_target→Desired blend→history
  commit 순서를 확인했다. 기존 물리 C++/reference 원본은 수정하지 않았다.
- `GuardedCompositionOffline`에 Prepare/Finish/Abort를 추가했다. Prepare는 health/
  snapshot/VR 전체 배치를 먼저 검증하고 복사된 상태에서 현재 upper를 준비한다.
  외부 Candidate는 null이며 Finish가 정책을 검증한 뒤에만 staged 상태를 commit한다.
  기존 Tick은 Prepare+Finish wrapper로 유지했다. 동일 tick에서 upper를 두 번
  갱신하지 않는다. validation 순서는 기존 policy-first에서 state/VR-first로 바뀌었다.
- Finish는 prepared 시각 이전 policy, stale policy/state, sequence 불일치/잘못된
  action을 거부한다. 추론 중 상태 age 만료·중복 Prepare·명시적 Abort도 latch 중단.
  실패 시 임시 upper/캡처 상태를 확정하지 않고 후보 null, 자동 재개 없음.
- `offline_blend.hpp`: capture1초/blend4초 smoothstep alpha, 하체 mimic의
  (1-alpha)*capture+alpha*default, 현재 upper mimic, 최종 위치
  (1-alpha)*capture+alpha*hybrid를 기존 float 순서대로 계산한다.
  일반 helper는 시간/alpha/finite 입력을 검사하고 duration은 호출자가 정한다.
- `test_policy_history_loop.cpp`: Prepare의 현재 upper로 관측을 만든 뒤 실제CPU
  정책을 실행하고 Finish→blend 위치→history feedback 순서로 바꿨다.
  이전 tick upper mimic 지연을 제거했다. history feedback은 blend 후 float 위치다.
  raw upper 후보는 이전 Quest 로그와 정확히 일치하고 최종 위치는 그 float 변환과 일치.
- blend 변화율과 VR 갱신이 겹치면 최종 위치 변화율이 증가할 수 있으므로
  이 오프라인 harness는 alpha<1에서 active VR이면 vr_before_blend_complete로
  중단한다. 이 규칙은 아직 실제 receiver/물리 controller에 적용하지 않았다.
- native `test_preinfer_blend.cpp`:601시점 alpha/mimic/위치 수식 비교 및
  Prepare→Finish 정상/추론지연/중복/잘못된policy/Abort/과거policy6종 통과.
  MSVC C++17 /W4 /WX로 신규harness 및 바뀐header 의존 실행파일4개 빌드 통과.
- 관련 회귀 **14 passed /107 subtests passed**, skip0.
  XML: `logs/test_results/twist2_preinfer_blend_regression_latest.xml`.
  기존6종 guarded replay도 모두 통과:
  `logs/test_results/twist2_guarded_after_prepare_20260907/result.json`.
- 실제CPU/Quest replay3종 통과:
  `logs/test_results/twist2_preinfer_blend_20260907_v2/result.json` 및 trace.
  정상1800 inference/active240/commit386, pinch에서 inference/commit 없음.
  tilt는active/commit1 후 사전 차단, blend_gate는active/commit0 사전 차단.
  초기v1결과도 보존했다. model 관측/feedback history의 매-frame 대조 유지.
- 남은 차이: first active 전 Candidate=null인 offline gating은 유지되어
  VR 이전에 실물 하체 takeover/blend 명령을 계속 송신하는 경로는 아직 없다.
  이번601시점 검사는 blend 수식 검사이며 실제 takeover/dynamics 검증이 아니다.
  feedforward torque fade, gains/500Hz writer rate·watchdog·damping, 실제 applied
  feedback, 실제 state/robot tick/배포 SDK 대조와 전신 경로·충돌은 남아 있다.
  state/health는 합성, policy시각은 기록 tick 기반 가상시각이고 실제 추론 지연과
  watchdog을 함께 돌린 실시간 시험은 아니다. 물리 제어 전체 동등성 주장 안 함.
- G1/WSL/DDS/publisher/물리 출력 없음. 물리 C++ SHA256 유지:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
  Arm SDK 문제 보류 및 기존 Mink 화면/가상 baseline/물리 안전성 미검증 경계 유지.

## 관측 history·승인 후보 feedback CPU 반복 연결 (2026-09-07)

- 현재 reference ObservationHistory/target_as_action 및 물리 C++의 mimic/Desired/
  commit 순서를 확인했다. 물리 C++와 reference 원본은 수정하지 않았다.
- `offline_observation_history.hpp`: mimic35 + gyro3*.25 + roll/pitch2 + q-default29
  + dq29*.05(ankle4/5/10/11은0) + previous action29 = current127;
  current127 + history10*127 + mimic35 = observation1432를 만든다.
  policy 관측만[-100,100] clamp하고 history에는 원래 current를 저장하는 reference
  규칙을 유지한다. feedback은 승인 위치를 float로 변환한 뒤
  (q-default)/.5를[-2,2] 제한한 값이다. 원시 정책 action을 그대로 넣지 않는다.
- Build/Commit/Discard/Stop 단계를 분리했다. 후보 없음은 Discard, 오류/해제는 Stop;
  finite/phase 검증 후 원자적으로 commit하여 실패 시 history가 바뀌지 않는다.
  Stop 이후 Build 거부, 새 인스턴스 이외 자동 reset/resume 없음.
- `prepare_observation_reference.py`는 현재 reference의 원래 관측 코드를 추출하고
  가짜 Policy로 관측만 캡처한다(DDS/Torch 실행 없음). source hash도 보존한다.
  native `test_observation_history.cpp`에서200개의 다른 입력 frame을 정확히 비교:
  current/관측 순서, ankle mask, observation clipping,10-frame rollover, candidate
  feedback 모두 일치. Discard/invalid Commit/Stop도 확인했다.
- `test_policy_history_loop.cpp`와 `run_policy_history_offline.py`: 실제 검증된 정책
  CPU 추론→C++ guarded 합성→후보 feedback→다음 관측의 반복 경로 추가.
  저장152430 Quest의 원문/tick을 사용하고 상태는 가상 baseline에 고정한다.
  health/CRC는 합성 assertion, state/policy 시각은 기록 tick 기준 가상시각이다.
  실제 추론 지연이 watchdog에 전달되는 실시간 시험이나 robot dynamics가 아니다.
- 정상: 추론1801회, active240회, 승인 후보/history commit386회, input_disengaged 종료.
  386회 모두 raw policy action과 후보 feedback이 달랐고 다음 관측의 previous_action과
  history 내용을 매회 정확히 검사했다. 상체12..28은 기존 Quest 후보와 정확히 일치.
  입력 없는 waiting tick도 유효 후보가 있으면 하체 정책 합성과 commit을 수행한다.
- tilt 주입: 추론1416회, active/commit1회 후 attitude_limit, 중단 tick commit 없음.
  출력 trace/결과: `logs/test_results/twist2_policy_history_20260907_v1/`.
  정상 첫/max 추론30.1117ms, 중앙0.351ms(tensor 생성 포함),50Hz 보장은 아니다.
- MSVC C++17 /W4 /WX native2종 빌드/시험 통과. 관련 회귀
  **14 passed /107 subtests passed**, skip0.
  XML `logs/test_results/twist2_history_regression_latest.xml`.
- 중요 차이: 현재 harness의 mimic은 default legs + 이전 승인 upper다.
  물리 C++는 inference 전에 현재 upper_target과 blend alpha로 mimic을 만든다.
  따라서 관측 알고리즘/history는 reference와 대조했지만 물리 제어 전체 실행 순서와
  동등하다고 주장하지 않는다. blend/500Hz writer가 없으므로 feedback은 메모리 승인
  후보이며 실제 송신/모터 적용값이 아니다. actual observation/pre-inference upper
  준비·blend·writer 적용 feedback·전신 동역학/충돌 검증은 남아 있다.
- G1/WSL/DDS/publisher/물리 출력 없음. 물리 C++ SHA256 유지:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
  Arm SDK 기울어짐은 보류, 실제 LowState/배포 SDK 대조와 물리 안전성 검증 미완료.

## 공식 hg 정의 확보·native decoder 및 CPU 환경 준비 (2026-09-07)

- 프로젝트/PC 기존 자료와 현재 변경사항을 먼저 확인했다. G1/WSL에 접속하지 않았다.
- 공식 Unitree SDK commit `9754cd153af3da471b0fe5f3aa535e426fb11db3`의
  hg LowState/MotorState/IMUState 정의와 LICENSE를 읽기 전용 reference로 보관했다.
  `experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/manifest.json`에
  원본 URL/SHA256과 deployed_robot_match_verified=false를 기록했다.
  출처: https://github.com/unitreerobotics/unitree_sdk2/tree/9754cd153af3da471b0fe5f3aa535e426fb11db3/include/unitree/idl/hg
- `prepare_hg_class_fixture.py`: 원문 해시 확인 후 공식 class 선언만 시험용으로
  추출한다. DDS traits/header/runtime는 포함하지 않는다. MSVC에서 LowState2092,
  MotorState56, IMUState56바이트 및 trailing CRC offset2088을 확인했다.
- `offline_hg_native_decoder.hpp`: 명시적 `hg_native_le2092_9754cd15` profile만
  받는 native little-endian 메모리 decoder다. DDS/CDR wire decoder가 아니다.
  길이/receipt/CRC/사용하는 float finite 검사를 먼저 수행하고 q/dq/torque/온도/
  fault/IMU/mode/remote/tick을 읽는다. motor 두 온도 중 큰 값을 사용한다.
  CRC는35 motor 전체를 포함하고 제어용 snapshot은0..28만 추출한다.
  robot_tick은 추출만 하며 재전송/재시작/wrap 검사는 실제 수신 어댑터에 남아 있다.
- `test_hg_native_decoder.cpp`: 공식 클래스 accessor로 채운 합성 memory와
  decoder 값을 대조했다.2092개 byte 각각1bit 변조를 모두 CRC 오류로 거부;
  잘못된 크기/profile, valid CRC의 NaN, emergency 버튼도 확인했다.
  MSVC C++17 /W4 /WX 빌드 통과. 실제 로봇 raw 데이터와 ABI 일치 시험은 아니다.
- 관련 Python 회귀 **14 passed /107 subtests passed**, skip0.
  XML: `logs/test_results/twist2_sdk_cpu_preparation_latest.xml`.
- `run_policy_cpu_offline.py`: 고정 hash 검증한 동일 bytes를 CPU TorchScript에
  로드하고 synthetic1432 관측2종을 각각10회 추론하는 시험을 준비했다.
  [1,29] float32/finite/clip/repeatability/latency 기록용이며 history feedback이나
  실제 LowState 관측, 정책-로봇 폐루프 시험이 아니다.
- CPU Torch 설치는 `logs/diagnostics/twist2_cpu_venv`에 격리한다. 전역Python은
  변경하지 않는다. 공식 wheel 전체 다운로드가 멈춰 시험 소유 pip만 종료했고,
  range 다운로드 후 공식 index SHA256 대조를 완료했다. Torch2.14.0+cpu 설치 및
  pip check 통과. wheel SHA256:
  `8e2c47c6556c7d5a85848634372bb2252907d411e9cad669c99406856d536eb5`.
  설치 출처: https://pytorch.org/get-started/locally/ 및 공식CPU wheel index.
  설치 manifest/requirements: `logs/test_results/twist2_cpu_install_20260907.json`,
  `logs/test_results/twist2_cpu_requirements_20260907.txt`.
- 실제 정책 hash 확인 후 CPU 추론 완료: zero1432 및 synthetic home(empty history)
  각각10회, [1,29] finite float32/정확한 반복 일치/clip 통과. zero raw최대2.91649는
  기존 adapter가2로 제한했다. 첫 추론29.7351ms, zero warm최대6.1115ms,
  synthetic home최대0.3112ms.20회 국소 측정이며50Hz/실시간 보장은 아니다.
  결과: `logs/test_results/twist2_cpu_policy_smoke_20260907.json`.
  NumPy 미설치 및 torch.jit.load deprecation 경고가 있었으나 현재 tensor-only
  시험과 pip check는 통과했다. 기존 TorchScript artifact를 변경하지 않았다.
- CPU 재현(새 output 경로 사용):
  `.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_policy_cpu_offline.py --output logs/test_results/cpu_policy_new.json`
- 남은 경계: 배포 SDK/ABI와의 대조 및 실제 raw CRC 표본, robot tick/receipt
  adapter, 상태 provenance, 실제 관측 history/적용 action feedback, 전신 경로/
  충돌/blend/torque/gain/단일500Hz writer/damping 연결. SDK 정의를 얻은 것만으로
  실제 LowState 초기화나 로봇 안전성 검증이 완료된 것은 아니다.
- 기존 물리 C++ SHA256 유지:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
  G1/WSL/DDS/publisher 실행 없음. Arm SDK 기울어짐 보류, 기존 Mink 화면 경계 유지.

## CRC 코어·정책 파일/출력 어댑터 준비 (2026-09-07)

- 프로젝트 파일 목록과 reference를 확인했다. 로컬 정책
  `references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt` SHA256은
  reference 고정값 `463be0376c2c1f551b996d0bf9ab97833854f2cc098b9d4fea735f17ec2e9015`와 일치.
  프로젝트에 hg LowState/MotorState/IMUState SDK 정의는 발견하지 못했다.
  발견된 unitree_mujoco motor_crc 예제는 Go LowCmd용이므로 G1 LowState layout으로
  사용하지 않았다. 확인한 py3.11에는 torch/unitree_sdk2py 모듈 없음.
- `offline_word_crc.hpp`와 stdin 시험 harness 추가. little-endian uint32 word
  입력에 reference와 같은 initial FFFFFFFF/polynomial04c11db7/MSB32회 처리를
  구현했다. 빈 입력/4바이트 정렬 위반을 거부한다. 독립 Python 다항식 long
  division으로 random/bitflip 벡터를 비교했다. bitflip은 벡터 비교이며 실제
  LowState 패킷 CRC 판정 시험이 아니다.
- 중요: CRC 코어는 DDS/CDR decoder가 아니다. 원본 memory layout/길이/endianness/
  CRC field 위치가 확정된 데이터의 CRC 계산만 제공한다. 실제 raw 상태에서
  필드를 읽는 decoder나 CRC 검증 후 health를 채우는 연결은 미완료다.
- `offline_policy_adapter.py` 추가: 고정 SHA256 검증 후 동일 bytes를 반환하여
  향후 loader가 경로를 다시 열 필요가 없도록 했다. array 어댑터는 raw [1,29]
  finite float32 출력, 시간/uint64 metadata를 검사하고 Policy::infer와 동일하게
  [-2,2] clip한다. bool/string/shape/NaN/Inf/float32 overflow/time 오류를 거부한다.
  이 함수는 배열을 검증할 뿐 해당 정책이 계산했다는 출처를 증명하지 않는다.
  repeated-sequence와 state binding 검사는 기존 C++ wrapper 책임이다.
- 새 `test_offline_input_adapters.py`: **3 passed /65 subtests passed**, skip0.
  MSVC C++17 /W4 /WX CRC harness 빌드 통과.
  XML: `logs/test_results/twist2_input_adapters_latest.xml`.
- 재현(프로젝트 루트; CRC harness 빌드 후):
  `py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_offline_input_adapters.py`
- 남은 필수 자료: 실제 배포와 일치하는 hg LowState SDK 타입 정의 및 byte layout,
  CRC를 포함한 기존 raw LowState 표본, 로컬 Torch 실행 환경. 따라서 LowState
  decoder와 실제 inference 연결은 이번에 완료하지 못했다. 임의 offset/Go 타입으로
  대체하거나 assertion을 실제 CRC 확인으로 승격하지 않았다. 정책 파일은 검증했지만
  로드/추론하지 않았다. SDK/패키지 설치·G1/WSL/DDS/publisher 실행 없음.
- 기존 물리 C++를 수정하지 않았다. Arm SDK 기울어짐은 보류이며 실제 LowState
  초기화·전신 동역학·단일 writer 연결 및 물리 안전성은 계속 미검증이다.

## 저장 Quest → guarded 합성 경로 연결 검증 (2026-09-07)

- 현재 코드/로그/변경사항을 확인한 뒤 별도 stdin C++ harness
  `test_guarded_replay.cpp`와 `replay_guarded_quest_fixture.py`를 추가했다.
  기존 receiver/물리 C++/검증 모듈의 동작 코드는 변경하지 않았다.
- 152430 Quest 원문 로그를 기존 exact replay로 먼저 검증한 뒤 수신 byte와
  receipt/tick 순서를 guarded composition에 전달했다. 상태는 첫 가상 baseline에
  고정된 합성 q/dq, 정책은 합성 sine action, health/CRC는 명시적 fixture다.
  실제 LowState/정책 inference/CRC 계산이나 로봇 동역학 모사가 아니다.
- 정상 경로 active240회에서 기존 로그의 상체12..28 후보와 정확히 일치했다.
  하체12축 정책 변환·관절 clamp·motor 순서, 허리/왼팔 유지, 오른팔0.08rad/s
  및 오버슈트 방지, pinch 중단을 확인했다. 기록된 tick 간격 최대22.3774ms;
  합성 snapshot 연속성 임계값은30ms, settling1초로 명시했다. 물리 설정값 아님.
- 오류 주입5종도 통과: 첫 active 이후 입력 단절→receiver_timeout,
  tilt→attitude_limit, 정책 지연→policy_time, 상태 지연→stale_or_invalid_state_time,
  초기 q22 차이+.05rad→initial_arm_mismatch(active0). 이후 남은 tick을 계속
  재생해 중단 사유 고정/후보 null 및 자동 재개 없음을 확인했다.
- 총6개 end-to-end 시나리오 통과. MSVC C++17 /W4 /WX 빌드 통과.
  관련 회귀 **11 passed /42 subtests passed**, skip0.
  XML `logs/test_results/twist2_guarded_quest_regression_latest.xml`.
  최종6개 trace와 결과: `logs/test_results/twist2_guarded_quest_fixture_20260907_v2/`.
  trace 각 행에 synthetic fixture 출처 및 hardware_output_authorized=false 표시.
  초기 v1 결과도 보존했다. 원문 SHA256:
  `d2d824d6f13b37e845826b2b3b4557c30b3da1837d78edb3cbd8fcda3622d65c`.
- 재현(프로젝트 루트, output은 존재하지 않는 새 경로):
  `py -3.11 experiments/twist2_right_arm_manual/replay_guarded_quest_fixture.py --output logs/test_results/guarded_quest_new_run`
- 남은 주요 경계: 합성 state/policy를 실제 검증 가능한 입력으로 교체하는
  decoder/CRC·policy artifact/inference 어댑터, 전신 동역학·충돌, blend/torque/gain,
  500Hz 단일 writer/damping 연결. 현재 실물 실행을 위한 검증은 완료되지 않았다.
  수신기 실시간 연결도 아직 없고 오프라인 harness 연결만 완료했다.
- 소켓/G1/WSL/DDS/publisher/물리 출력 없음. 기존 물리 C++ SHA256 유지:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
  Arm SDK 기울어짐 보류/기존 Mink 화면/가상 baseline 경계 유지.

## 상태 health·정책 action 어댑터 오프라인 검증 (2026-09-07)

- 현재 코드/변경사항, 물리 C++ validate_state 및 reference Policy::infer와
  hybrid_target를 읽었다. 물리/reference 원본은 수정하지 않았다.
- `guarded_composition_offline.hpp` 추가: 기존 위치 합성 초안을 감싸며
  CRC 검증 여부, mode_pr0/mode_machine5, deadman/비상정지, finite RPY 및
  roll/pitch 한계, 전축 q/dq/torque/temperature finite, 속도/관절 soft limit,
  온도/motor fault를 검사한다. CRC는 adapter가 전달하는 assertion이며 원본 DDS
  바이트 CRC 계산이나 실제 출처 인증을 구현한 것이 아니다. 기본값은 거부 상태다.
- policy sample은 Policy::infer 이후의 clipped[-2,2] motor순서29축 action이다.
  raw tensor/절대 위치 입력이 아니다. 전축 finite/범위, 생성 시각/최대 age,
  sequence 증가와 현재 state_sequence 일치를 요구한다. 정책 누락/재사용/미래/
  오래된 입력은 latch 중단. 동일 state의 정책 결과를 전달하는 동기 초안이다.
- 하체는 reference와 동일 float 연산 default+0.5*action 후 soft-limit clamp.
  policy의 상체 action은 합성에 사용하지 않는다(형식/finite 검사는 수행).
  최종29축 후보 한계도 검사하며 상체 한계 초과 시 clamp 대신 중단하여
  캡처 유지/속도 제한을 몰래 바꾸지 않는다. Candidate=null 이후 자동 재개 없음.
- `offline_twist2_constants.hpp`는 reference의 default/lower/upper/scale/action
  limit/margin 스냅샷이다. 테스트가 현재 reference와 값을 대조하여 drift를 검출한다.
  SDK/Torch header를 포함하거나 실행하지 않는다.
- 새 native harness `test_guarded_composition.cpp`와 Python 회귀 추가.
  MSVC C++17 /W4 /WX 빌드 통과. 관련 신규/기존 초기화 tests:
  **11 passed /42 subtests passed**, skip0. NaN/Inf, tilt, q/dq, fault/temperature,
  deadman/CRC/mode, policy time/seq/state 불일치 및 최종 후보 한계 초과 후
  다음 정상 입력에서도 후보가 null인 것을 검증했다.
  XML: `logs/test_results/twist2_guarded_composition_latest.xml`.
- OfflineHealthLimits(policy_age/roll/pitch/velocity/temperature)는 호출자가
  양수로 명시한다. 시험값 .01s/.15rad/.15rad/1.5rad/s/75도는 합성 fixture용,
  실제 preflight/runtime 승인을 의미하지 않는다. 물리의 단계별 임계값 전환 미구현.
- 남은 항목: raw LowState CRC와 snapshot 출처 검증/실제 decoder, 정책 artifact
  identity 및 실제 inference 결과 연결, 초기 leg home/전신 경로·충돌 검사,
  blend/torque/gain/500Hz writer와 damping 전환. assertion만으로 실물 연결 불가.
  신규 wrapper는 아직 Windows 수신기에도 연결하지 않았다.
- 소켓/G1/WSL/DDS/publisher/물리 출력 없음. 기존 물리 C++ SHA256 유지:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
  실제 LowState 초기화 완료나 로봇 안전성 검증이 아니다. Arm SDK 문제는 보류다.

## 상태 snapshot 기반 초기화·합성 초안 (2026-09-07)

- 현재 변경사항과 물리 C++의 capture/upper_target/hybrid_target/Desired 경로를
  검토했다. 기존 `hybrid_target`은 raw action에 default+scale을 적용하고 전축
  clamp한다. 새 인터페이스는 이미 변환된 motor순서 하체12축 절대 rad를 받는다.
  raw policy tensor를 이 인터페이스에 직접 넣으면 안 된다.
- 별도 `measured_composition_offline.hpp`와 stdin harness
  `test_measured_composition.cpp`, `test_cpp_measured_composition.py`를 추가했다.
  실제 LowState subscriber가 아니라 q29/dq29/sequence/receipt snapshot을 받는
  순수 메모리 초안이다. 이번 입력은 전부 합성 fixture이며 실제 G1 측정이 아니다.
- 연속 fresh snapshot의 속도/누적 자세변화가 설정된 정지 조건을 만족해야
  마지막 snapshot을 baseline으로 캡처한다. 캡처 전에는 후보 null이다.
  캡처 이후 첫 유효 active VR 목표와 현재 오른팔 q의 차이를 검사하며
  불일치 시 중단, 자동 rebase/re-engage 없음. settling 중 VR payload는 저장하거나
  적용하지 않는다(크기/receipt/batch envelope만 검사). 캡처 후 새 active가 필요하다.
- 입력 상태 누락/오래됨/미래 시각/sequence 반복·역행/수신 간격 단절,
  상체 추종 오차, VR 해제/오류/timeout/범위 초과는 latch 중단 및 후보 null.
  같은 batch의 후속 release/오류도 후보를 반환하지 않는다.
  VR packet 누락 시 오른팔을 동결하되 watchdog 만료 전 하체 합성은 가능하다.
- 후보 소유권:0..11 전달된 정책 위치,12..21 캡처값,22..28 기존0.08rad/s
  UpperTargetOffline. 중단 시 null은 송신 중단/서기/댐핑 명령 자체가 아니다.
  실제 단일 writer와 기존 damping/watchdog 연결은 아직 구현하지 않았다.
- 모든 정지/신선도/일치/추종 임계값은 생성자가 명시적으로 받는다. 테스트값
  state_age=.021s, settle=.039s, velocity=.1rad/s, drift=.01rad,
  alignment=.025rad, tracking=.25rad, arm delta=.17rad는 합성 시험값이며
  물리 승인값 또는 기존 preflight의 대체값이 아니다.
- MSVC C++17 /W4 /WX 빌드 통과. 새9 tests와 기존 메모리 회귀 포함
  **60 passed /236 subtests passed**, skip0.
  `logs/test_results/twist2_composition_offline_latest.xml`.
  이번 시험은 소켓을 열지 않았다. 기존 loopback/Quest 결과는 이전 단계 근거다.
- 남은 항목: 실제 snapshot의 CRC/모드/IMU/온도/전축 한계 검증 및 출처 보장,
  정책 위치의 freshness/한계/변환 어댑터, 전신 경로 검사, blend/torque/gain 및
  기존 단일 writer의 중단 처리 연결. 이번 클래스는 위치 후보만 만들며 이러한
  검사를 대신하지 않는다. 실제 LowState 초기화 완료로 해석하지 않는다.
- G1/WSL/DDS/publisher 실행 없음. 기존 물리 C++ SHA256 유지:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
  Arm SDK 기울어짐은 보류. Unity 화면은 기존 Mink이며 물리 안전성 검증 아님.

## 새 형식 실제 Quest 로그 재생 통과 (2026-09-07 15:24)

- 사용자 VR 준비 확인 후 지정 BAT를 `--standard-mink --external-feedback`로
  실행했다. camera/WSL/Regular-return 경로는 실행하지 않았다. simulation 표시 확인.
  실행 전5005/5008/5012 점유 없음을 확인하고 기존 Unity를 유지했다.
- 새 Windows C++ PID5204가127.0.0.1:5008에서 수신했다. config는 첫 active
  Mink 가상29축 baseline, 시작 대비10도, queue64, 최대180초였다.
  사용자가 engage→손 움직임→pinch 해제 완료를 확인했다.
- 기록1127 datagrams, active tick240회. 첫 active28.7476927초,
  마지막 active36.5702399초,36.6122555초 `input_disengaged` 종료. queue peak2.
- 실제 수신 원문/receipt/tick을 `replay_cpp_receiver_log.py`로 오프라인 재생했다.
  후보/검증 목표/baseline/mode/reason의 정확한 일치,0.08rad/s 제한,
  목표 오버슈트 없음,0..21축 고정, inactive 및 해제 시 후보 유지 검사를 통과했다.
  최대 한 번 갱신0.0013840124019711547rad. 이는 이번 캡처에 대한 로컬 검증이다.
- 로그/config/stdout/stderr 및 SHA256 포함 결과:
  `logs/test_results/twist2_cpp_quest_raw_20260907_152430/result.json`.
  재현 명령(프로젝트 루트):
  `py -3.11 experiments/twist2_right_arm_manual/replay_cpp_receiver_log.py logs/test_results/twist2_cpp_quest_raw_20260907_152430/ticks.jsonl`
- 이번에는 기능 코드 수정 없이 현재 빌드로 실험/재생을 수행했다. 직전 회귀시험
  61 tests/231 subtests 통과 기록은 이전 단계 근거이며 이번에 재실행하지 않았다.
- 수신기는 해제로 자동 종료했다. 이번 BAT로 시작한 Mink PID43440의 정확한
  command line을 확인하고 해당 프로세스만 종료했다. 이후5005/5008/5012 점유 없음.
  Unity/Meta Link는 유지했다. G1/WSL/DDS/publisher/물리 출력 실행 없음.
  기존 물리 C++ SHA256 `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F` 유지.
- 다음 작업: 실제 LowState를 기준으로 시작할 초기화/일치 검사와 단일 writer에
  합칠 인터페이스를 Windows 메모리 전용으로 먼저 구현·검증한다. 실제 LowState
  연결, TWIST2 정책 통합, 전신 경로 검증, C++ 후보 시각화는 아직 남아 있다.
  이번 baseline은 가상 Mink이고 화면도 기존 Mink다. Arm SDK 기울어짐은 보류,
  실제 로봇 안전성/실행 승인은 이번 시험으로 확보되지 않는다.

## C++ 원문 기록 및 정확한 오프라인 재생 (2026-09-07)

- 작업 전 현재 변경사항/코드/이전 Quest 로그 상태를 확인했다. 다른 변경을 되돌리지 않았다.
- `receive_target_shadow.cpp`: 새 `g1.twist2.receive_replay.v1` 로그에 수신 순서,
  receipt 시각, 원문 전체 hex, enqueue 결과/중단 사유를 기록한다. UDP 수신 버퍼는
  65536바이트로 원문을 보존하되 허용 입력 크기는 기존16384바이트를 유지한다.
  tick에는 배치 전체 검증에 성공한 최신7축 `validated_goal`을 기록하며
  waiting/stopped에는 null이다. 출력은 Windows 로컬 파일뿐이다.
- `upper_target_offline.hpp`/`queued_input_offline.hpp`에 tick 목표 조회를 추가하고
  `test_queued_input.cpp`에 hex 입력 재생을 추가했다. 갱신/중단 규칙은 유지했다.
- 잘못된 UTF-8 시험에서 parser 예외문에 원시 바이트가 포함되어 최종 JSON 기록이
  실패하는 결함을 발견했다. `validate_input.hpp`에서 parse_error를 고정 ASCII
  사유로 latch하도록 수정했다. 원문은 별도 hex에 그대로 보존한다.
- `replay_cpp_receiver_log.py`: 원문/receipt/tick 순서를 메모리 전용 C++ queue에
  재생하여 q/baseline/검증목표/mode/reason/queue peak를 정확히 비교한다.
  별도로0.08rad/s, 최대20ms step, 목표 오버슈트,0..21축 고정 및 inactive 유지 검사.
  누락 패킷/변조 목표·후보/불완전 로그/구형 로그는 거부한다. duration 이외의
  외부 transport 오류는 재현했다고 처리하지 않는다. 암호학적 로그 인증은 아니다.
- MSVC C++17 `/W4 /WX`로 receiver/queue/validator/upper harness 빌드 통과.
  기존7개 관련 테스트 파일: **61 passed /231 subtests passed**, skip0.
  loopback에서 근접 목표 exact snap, 방향 반전, first-active baseline, 해제,
  timeout, invalid UTF-8/NUL/빈 입력, oversize, queue overflow의 원문 재생을 검증했다.
  XML: `logs/test_results/twist2_cpp_raw_replay_regression_latest.xml`.
  보존 합성 수신 로그/재생 보고서: `logs/test_results/cpp_raw_replay_dw9v_jyy/`.
  재생 명령(프로젝트 루트, 소켓 없이 실행):
  `py -3.11 experiments/twist2_right_arm_manual/replay_cpp_receiver_log.py logs/test_results/cpp_raw_replay_dw9v_jyy/ticks.jsonl`
- 이번에는 임시 loopback 포트의 합성 입력만 사용했고 VR/G1/WSL/DDS/publisher를
  실행하지 않았다. 종료 후5005/5008/5012 점유 없음. 기존 물리 C++ SHA256 유지:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 남은 항목: 새 기록 형식으로 실제 Quest 세션을 수집해 동일 재생 검증 적용.
  이전150530 세션은 raw 목표가 없어 그 세션의 오버슈트를 소급 검증할 수 없다.
  실제 LowState 초기화, TWIST2 정책/단일 writer 통합, 전신 경로 검증과 C++ 후보
  시각화는 미구현/미검증이다. Arm SDK 기울어짐은 보류이며 물리 안전성 검증 아님.

## 실제 Quest → Windows C++ 첫 active baseline 시험 (2026-09-07)

- 사용자 준비 확인 후 로컬 VR 시험을 수행했다. 첫 C++ 실행150316은 이전
  세션의 pinch_disengaged 패킷을 받아 baseline 없이 중단(active0)했다.
  동일 시점 진단 패킷은 이전 세션/age45.469초/active=false/state=idle였다.
  실패 기록과 관찰 패킷은 `twist2_cpp_quest_20260907_150316/`에 보존했다.
- 코드 수정: InputValidator의 선택적 검증된29축 출력과 QueuedInputOffline의
  첫 active 가상 baseline 옵션 추가. 캡처 전 q/baseline은 null이며 가짜0축
  후보를 내지 않는다. 유효한 첫 active의29축과 관절 한계를 확인한 후 캡처한다.
  같은 배치의 후속 패킷도 모두 검사하고, 오류/해제 시 후보를 변경하지 않는다.
- 첫 active 캡처 전에는 형식이 정상인 이전 inactive(pinch/tracking/workspace)
  상태도 기다린다. 잘못된 형식/수신 시각/overflow는 캡처 전에도 latch 중단.
  active 이후에는 기존 해제/timeout/error 중단을 유지하며 자동 재캡처하지 않는다.
  이 대기 옵션은 새 baseline bootstrap에만 사용하고 기존 validator 기본값은 유지한다.
- 재시험150530: C++가2079개 Mink datagram을 수신했다. 첫 active61.782초,
  마지막 active66.671초,66.693초 input_disengaged 종료, active tick152회.
  최대 한 번 갱신0.0016000000000000458rad(부동소수 오차 포함),
  최대 실제 시각 기준 속도0.0798901510rad/s, baseline 대비 최대0.113435rad.
  비대상22축 불변, baseline 재설정 없음, 비활성/종료 시 후보 유지 위반0.
- tick 중앙값20.1308ms/전체 최대79.1033ms, active 구간 최대20.9788ms.
  Windows 실시간50Hz 보장은 아니다. 실제 수신기 로그에는 원시 목표가 없어
  이 세션의 목표 오버슈트는 직접 대조하지 못했다. 오버슈트는 오프라인 시험
  근거로만 설명한다. 실행파일 SHA256과 집계:
  `logs/test_results/twist2_cpp_quest_20260907_150530/result.json`.
  동일 폴더에 config/ticks/stdout/stderr를 보존했다.
- Unity: 최신 Assembly-CSharp 컴파일(Tundra build success)과 assembly reload
  로그를 확인했다. 사용자는 engage→움직임→pinch 완료 및 손목 목표 표시 정상
  확인을 제공했다. 화면은 기존 Mink 결과이며 C++ 후보 화면은 아니다.
- 테스트: 새 bootstrap 메모리/loopback 시험과 기존 전체 관련 회귀시험
  **59 passed /230 subtests passed**, skip0. MSVC C++17 /W4 /WX 빌드 통과.
  XML: `logs/test_results/twist2_cpp_quest_regression_latest.xml`.
- 정리: C++는 해제로 스스로 종료했다. 이번에 시작한 simulation Mink
  PID32748의 정확한 command line을 확인하고 그 프로세스만 종료했다.
  종료 후5005/5008/5012 점유 없음. Unity/무관한 프로세스는 종료하지 않았다.
  G1/WSL/DDS 실행/파일 변경, publisher 생성, 물리 출력 및 물리 C++ 수정 없음.
  물리 C++ SHA256은 `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 남은 항목: 수신 원문/검증 목표 로그를 통한 실제 세션 재생과 오버슈트 대조,
  장시간 부하/OS UDP 유실, Unicode session 공백 계약 차이,
  실제 LowState baseline/정책 합성/전신 충돌/추적 오차/물리 종료 정책.
  Arm SDK 기울어짐 문제는 계속 보류이며 물리 안전성 검증 완료가 아니다.

## C++/Python 입력 필드 계약 비교 및 누락 보완 (2026-09-07)

- 검토: 최신 C++/Python 파서와 저장 Quest shadow/144501 loopback 결과,
  Arm SDK 기울어짐 보고서, Unity flag/launcher 소스를 읽었다. 이번에는
  포트 점유만 조회했고 프로세스 종료/수신기/VR 실행은 하지 않았다.
- 비교 시험을 먼저 실행해 C++에서 timestamp, workspace/collision bool,
  충돌 진단 이름 배열, idle 메타데이터의 형식 누락을 재현했다. 수정 전 결과:
  `logs/test_results/twist2_cpp_contract_before.xml`(예상 실패 기록).
- 코드 수정: `validate_input.hpp`에 위 필드 검증, mode/state/active 조합 검사,
  idle에서도 제공된 session/age/clearance 검사 추가. ASCII session 앞뒤 공백은
  Python처럼 정규화한다. 정수 sequence의 -0은0과 동일하게 처리한다.
  CheckTimeout 단독 호출도 비유한/음수/역행 시계를 latch 거부한다.
  timestamp는 형식만 검사하며 wall time을 로컬 단조 시계와 비교하지 않는다.
- 테스트: `test_cpp_input_contract.py` 추가. 순수 Python parse 함수와 첫 입력
  수용/대기/중단을 비교하며 freshness/clearance/active 조건은 TWIST2 기준으로
  판정한다. Arm SDK controller나 Regular 복귀 로직은 생성/실행/이식하지 않는다.
  신규 필드 오류 후 후보29축 유지·재연동 차단과40가지 mode/state/active 조합,
  기존 저장 Quest 재생을 포함해 **46 passed /214 subtests passed**, skip0.
  `logs/test_results/twist2_cpp_contract_regression_latest.xml`에 기록했다.
- MSVC C++17 /W4 /WX로 validator/목표/큐 harness 및 두 Windows 수신기 빌드
  성공. 이번 실행은 stdin/stdout harness만이며 소켓/G1/WSL/DDS 실행 없음.
  새 빌드의 실제 loopback/Quest 시험은 이번에 반복하지 않았다. 144501 기록은
  앞 단계 실행파일의 결과이며 이번 헤더 변경 후 runtime 검증으로 인용하지 않는다.
- 동등성 범위: 숫자 문자열/bool의 숫자 변환, 중복 JSON 키, raw NaN/Infinity,
  uint64 초과 sequence는 Python이 허용할 수 있어도 C++는 계속 거부한다.
  이 의도적 차이는 테스트로 고정했다. Unicode 공백 session의 Python strip과
  C++ ASCII trim 차이는 남아 있어 **모든 입력의 완전 동등성 완료가 아니다**.
- 물리 `twist2_right_arm_trial.cpp` SHA256은 앞 단계와 동일하다.
  남은 항목: 새 수신기의 실제 Quest 입력, Unity flag 재컴파일/화면, 실측
  baseline/정책 합성/전신 충돌/추적 오차/물리 종료 검증. 현재 후보 검증 결과를
  실제 로봇 안전성이나 Arm SDK 문제 해결로 해석하지 않는다.

## Windows C++ 수신 큐와 실제 로컬 tick 연결 (2026-09-07)

- 검토: 현재 변경사항과 앞 단계의 batch Tick API, 기존 receive-only probe를
  확인했다. 기존 수정/미추적 작업을 되돌리지 않았다. 새 실행파일로 분리해
  기존 `receive_only.cpp` 및 물리 `twist2_right_arm_trial.cpp`는 변경하지 않았다.
- 코드 수정: `queued_input_offline.hpp`의 단일 소유자 큐와
  `receive_target_shadow.cpp` 추가. Windows127.0.0.1만 수신하고 후보29축은
  새 로컬 JSONL에만 기록한다. 송신/SDK/DDS/정책/물리 제어기 연결 없음.
  명시한 가상 baseline29축/시작범위/큐 용량을 config로 받는다.
- 큐는1..64개, 각 payload는최대16,384bytes. FIFO 순서를 유지하며 tick마다
  전체 배치를 검사한 뒤 최대1회 갱신한다. overflow/과대 datagram은 큐를
  비우고 latch stop한다. 오래된 패킷을 버린 뒤 계속하는 경로는 없다.
  receive/event/timer/log 오류, duration 종료도 후보 갱신을 중단한다.
  수신/큐/tick/로그를 같은 스레드가 소유하므로 공유 큐의 경쟁 상태는 없다.
  이 클래스는 다른 스레드에서 동시에 호출하면 안 된다.
- 실제 스케줄링: 첫 select 대기 실험의 tick 중앙값30.169ms를 확인하고
  프로세스 전용 high-resolution waitable timer + Winsock event로 교체했다.
  목표 주기는20ms, 지연 뒤 catch-up 연속 갱신은 하지 않는다. 시스템 전역
  타이머/전원/드라이버 설정은 변경하지 않았다. 로그는 CREATE_NEW로 생성해
  기존 파일을 원자적으로 덮어쓰기 거부하며, 오류 시 stderr로 중단을 알린다.
- 테스트: 새 큐 harness와 수신기를 Windows MSVC C++17 /W4 /WX로 빌드.
  새 큐8개+새 실제 loopback7개+기존29개, **44 passed / 91 subtests passed**,
  skip0. `logs/test_results/twist2_cpp_queued_shadow_latest.xml`에 기록했다.
  용량 경계/재사용/overflow latch, 중간 해제/오류, payload 크기 경계,
  잘못된 receipt, age/timeout, 외부 오류 latch를 메모리에서 검사했다.
  실제 loopback으로 idle→active→해제, 무입력/active 후 침묵, 잘못된 JSON/
  빈/오래된/과대 datagram, 작은 큐 burst overflow, 포트 점유, 기존 로그 보호,
  잘못된 config를 검사했다. 수신기는 sender로 응답 datagram을 보내지 않았다.
- 별도 약1.2초 합성 연속입력 시험:61개 송신/61개 수신, active tick55,
  큐 peak2, `input_disengaged` 종료. tick 중앙값20.08555ms/최대20.4459ms,
  최대 관찰 후보 속도0.0797734434rad/s. 비대상22축 불변, 오버슈트 없음,
  비활성/종료 시 후보 유지 확인. 최신 기록:
  `logs/test_results/twist2_cpp_receive_stream_20260907_144501/`
  (`config.json`, `ticks.jsonl`, `result.json`, 실행파일 SHA256 포함).
  앞선 select 기록144315는 비교용이며 현재 구현의 결과가 아니다.
- 이번 소켓 실행은 테스트가 확보한 Windows loopback 임시 포트의 합성 입력만
  사용했다. Quest/Unity/G1/WSL/DDS 및 publisher/물리 출력은 실행하지 않았다.
  물리 C++ 전후 SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 남은 항목: 실제 Quest 입력의 새 수신기 호환 확인, 전체 Python 입력 계약
  동등성, 실측 baseline/정책 합성/전신 충돌/추적오차/물리 종료 정책.
  큐 제한은 애플리케이션 큐에만 적용되며 OS UDP buffer overflow/네트워크
  유실 검출을 보장하지 않는다. receipt는 recv 직후 시각으로 kernel 대기
  지연은 측정하지 않는다. Windows의 실시간20ms 보장이나 장시간 부하 시험,
  실제 디스크 장애 재현은 미검증이다. 물리 출력 준비 완료로 해석하지 않는다.
  새 실행기 config/빌드/시험 예시는 실험 README에 기록했다.

## C++ 수신 배치 → 가상 정책 tick 연결 (2026-09-07)

- 검토: 앞 단계의 새 패킷별 갱신 API는 수신→tick 대기 시간을 입력 age에
  포함하지 않았고, 여러 패킷이 한 tick에 들어올 때의 처리 규칙이 없었다.
  기존 변경사항을 유지하고 이번 변경도 실험 폴더와 문서에 한정했다.
- 코드 수정: `ReceivedInput{payload, received_at}`와
  `UpperTargetOffline::Tick(packets, now)` 추가. 같은 단조 시계의 수신 시각과
  tick 시각을 구분한다. `InputValidator`는 source age + (tick - receipt)를
  0.25초와 비교하며 timeout 기준에는 실제 receipt를 저장한다.
  미래/비유한/음수/역순 receipt는 거부한다. 기존 즉시 수신 Step API는 유지.
- 한 tick의 모든 패킷을 순서대로 검사한 뒤 최신 목표로 딱 한 번 갱신한다.
  배치 중간의 해제/오류/관절 범위 위반을 최신 정상 패킷이 가리지 못하며,
  실패한 배치는 관절 후보를 전혀 변경하지 않는다. 무패킷 tick은 유지한다.
  이전에 처리한 수신 이후 tick 자체가0.25초 넘게 지연되면, 새 배치가 있어도
  timeout을 latch한다. 쌓인 패킷으로 오래 멈춘 tick을 자동 재개하지 않는다.
- `replay_cpp_input_tick.py` 추가: 저장 shadow JSONL을 실제 소켓 없이
  0.02초 간격의 가상 tick으로 묶어 C++ stdin harness에 공급한다. 옛 Infinity
  진단값은 현재 `_send_state` 순수 함수만 AST로 추출해 fake sink에 직렬화한다.
  제어기 모듈 전체는 import/실행하지 않는다. 원본 capture는 수정하지 않는다.
  baseline은 첫 active Mink 가상 자세, 시작 대비 범위는10deg다.
- 테스트: MSVC C++17 /W4 /WX로 목표 harness, validator harness 및 기존
  receive-only probe 빌드 성공(probe 실행 없음). **29 passed / 70 subtests
  passed**, skip0. XML: `logs/test_results/twist2_cpp_input_tick_latest.xml`.
  배치당1회, 중간 해제/오류, age 합산과 경계, receipt 기준 timeout, 잘못된
  수신 시각, tick 정체, 같은 시각의 순서 있는 패킷을 검증했다.
- 저장 Quest `140851_282afca4`의476개 패킷을 재생한 결과: 가상 tick781개,
  active115 / waiting650 / stopped16, 종료 `input_disengaged`.
  최대 관찰 갱신 속도0.07999999999999952rad/s. 오버슈트/비대상 변경/비활성
  갱신/중단 latch 위반0. 결과와 tick별 후보:
  `logs/test_results/twist2_cpp_tick_replay_20260907_01/{result.json,ticks.jsonl}`.
  보고서에 입력과 실행파일 SHA256을 기록했다. 이 재생은 가상 시간을 쓰며
  실제50Hz 스케줄링 성능이나 물리 응답을 측정한 것이 아니다.
- 기존 물리 C++ SHA256은 앞 단계와 동일. G1/WSL/DDS 실행, publisher 생성,
  실제 소켓 실행/송수신 및 물리 출력 없음.
- 남은 항목: 실제 receive-only transport와 이 tick API 연결, 수신 큐의
  용량/overflow 처리 및 동시성 검토, 실측 baseline과 실제 정책 합성,
  전체 Python 입력 계약 동등성, 전신 충돌/추적 오차/물리 종료 정책.
  source age 합산은 기록된 age와 로컬 큐 지연 대상이며 측정되지 않은
  송신→수신 네트워크 지연을 알아내는 기능이 아니다. 물리 출력 준비 완료 아님.

## C++ 오른팔 목표 갱신 오프라인 검증 (2026-09-07)

- 검토: 작업 전 git status의 다수 수정/미추적 파일을 확인했다. 기존 변경을
  되돌리지 않았다. 현재 입력 validator, Python VRInputStudy, 수신 probe와
  물리 C++의 keyboard_applied/upper_target 합성 지점을 읽었다.
- 코드 수정: 실험 폴더에 `upper_target_offline.hpp`를 추가했다. 명시한 29축
  baseline을 보존하고 검증된 오른팔22..28만 절대 rad 목표로 갱신한다.
  속도 상한0.08rad/s, dt 상한0.02초(한 번 최대0.0016rad), 마지막 단계는
  목표를 정확히 대입해 오버슈트를 막는다. 7축 관절 한계와 시작 대비 범위를
  모두 검사한 뒤 후보 전체를 commit한다. 모델 한계는 Python 계약과 동일하며
  테스트가 각 축의 양쪽 경계 및 경계 밖 값을 대조한다.
- `validate_input.hpp`는 완전히 검증된 active 패킷에만 선택적 7축 출력 인자를
  채운다. 기존 2인자 호출과 receive-only 동작은 유지한다. 새 모듈은 idle 전
  timeout 없이 대기하며, 새 패킷이 없는 tick은 후보를 즉시 유지한다.
  engage 후 수신 공백>0.25초, 해제, 입력/관절/시각 오류는 latch stop한다.
  오류 tick 및 이후 정상 입력에서도 후보가 바뀌지 않는다. 자동 재연동 없음.
- 테스트: `test_upper_target_offline.cpp` stdin/stdout harness와
  `test_cpp_upper_target.py` 추가. Windows MSVC C++17 /W4 /WX로 새 harness 및
  기존 validator harness 빌드 성공. 새8개+기존 validator5개+Python offline6개,
  **19 passed / 51 subtests passed**. 저장 Quest 패킷 serializer 호환 시험도
  포함됐다. XML: `logs/test_results/twist2_cpp_upper_target_latest.xml`.
  양/음/0/작은 목표 수렴, 방향 반전, 짧거나 긴 dt, 비대상22축 정확한 유지,
  14개 모델 경계, 마지막 축 오류의 원자성, 해제/timeout/잘못된 시각 이후
  latch, 비영점 baseline의 목표·dt 변화500회 시험을 수행했다.
- 기존 물리 `twist2_right_arm_trial.cpp` 변경 없음. 전후 SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
  G1/WSL/DDS 실행, publisher 생성, 소켓 실행/전송 및 물리 출력 없음.
- 남은 항목: 실제 수신기와 정책 tick 연결, 실측 baseline 초기화, 큐에 대기한
  패킷의 receipt/source age 합산, 전체 Python 계약 동등성, 전신 충돌·추적 오차
  검증 및 실제 종료 정책은 미완료다. API는 호출 시각에 새로 받은 패킷을
  가정한다. baseline/시작범위는 caller가 명시하며 실물 승인값이 아니다.
  후보 갱신 중단은 로봇 damping/정지 실행을 뜻하지 않는다. 물리 제어기에
  연결하거나 출력 준비가 완료된 것으로 해석하지 않는다.
  재현 빌드/시험 명령은 실험 README의 C++ 메모리 전용 목표 갱신 절 참조.

## C++ idle 대기 및 strict JSON 호환 수정

- 검토: 저장 Quest shadow 140851_282afca4의 진단 필드에 Infinity 존재.
  제어값이 아닌 미측정 손목 여유각이었다.
- 코드 수정: _send_state에서 해당 진단값만 0 + wrist_limit_margin_unknown=true로
  직렬화한다. Unity는 플래그가 true이면 기존 Infinity 진단 의미를 복원한다.
  유한값/기존 플래그 없는 패킷 해석은 유지. allow_nan=False로 나머지
  비유한 값은 전송 전 거부한다. 원본 packet dict는 변경하지 않는다.
  C++는 첫 engage 전 idle을 waiting으로 처리하며 timeout은 engage 후 적용.
  engage 후 해제/오류 latch는 유지된다.
- 테스트: MSVC 빌드, 저장 Quest 패킷을 새 serializer로 변환하여 C++ harness에서
  waiting -> 100회 이상 active -> 마지막 해제 중단 확인. 실제 로봇/소켓 전송 없음.
  기존 raw loopback 테스트는 별도 수행. 전체 결과는
  logs/test_results/twist2_cpp_compatibility_latest.xml에 기록.
- 남은 항목: Unity Editor 재컴파일/VR 화면은 미검증. C++ 관절 한계/속도/
  정책 tick은 아직 연결하지 않았다. 원본 옛 Infinity 패킷은 그대로는 거부된다.
  G1/WSL/DDS 실행 및 물리 제어 코드 변경 없음.

## C++ 입력 검증 기초

- 코드 수정: receive_only --validate 선택 기능과 validate_input.hpp 추가.
  schema/source, 세션/순서, age0.25초, 29축 이름/수치 및 오른팔 중복 값,
  active/clearance 검사. 오류/해제/수신 지연은 latch 중단한다.
  기본 raw 수신 모드는 유지. 출력/SDK/정책 연결 없음.
- 의존성: nlohmann/json3.12.0 MIT 단일 헤더. 공식 릴리스 SHA256 일치.
- 테스트: Windows MSVC 두 실행파일 빌드. Python이 C++ stdin harness에
  합성 패킷/시각을 공급하여 순서/세션/age/형식/해제/latch 검증.
- 남은 항목: Python 계약 전체 동등성 및 실제 패킷 호환은 아직 미완료.
  Mink 진단 필드 Infinity는 strict JSON에서 거부되므로 송신 형식 정리가 필요.
  idle 시작도 현재 validate 모드에서는 중단된다. 바로 VR 실행용이 아니다.
  관절 한계/속도/전신 충돌과 정책 tick은 연결하지 않았다.
  G1/WSL/DDS 접근 및 기존 물리 C++ 변경 없음.

## TWIST2 Windows C++ 수신 전용 transport probe

- 검토: 실제 Quest shadow 140851_282afca4에서 active_updates116,
  input_disengaged 종료, transport_error 없음. 로컬 입력/해제 확인 완료.
- 코드 수정: experiments/twist2_right_arm_manual/receive_only.cpp 추가.
  Windows Winsock loopback만 bind, SDK/policy/송신 없음. 원문 datagram을
  4-byte network-order 길이 + payload 형식으로 로컬 파일에 저장한다.
  JSON 의미 검증/관절 적용은 하지 않는다. 잘못된 JSON도 원문 보존한다.
  기존 물리 C++ 및 G1 파일은 변경하지 않았다.
- 테스트: VS18 MSVC /W4 빌드 성공. C++ 실제 loopback 수신 원문 일치,
  빈 datagram, 비정상 JSON 보존, 기존 파일 덮어쓰기 거부 확인.
  Python shadow 포함 11 tests 및 11 subtests 통과.
- 남은 항목: C++ JSON 계약 검증, 정책 tick 입력 통합, 실측 초기화,
  전신 충돌/종료 정책. 이 probe는 TWIST2 제어기에 연결된 것이 아니다.
  WSL/G1/DDS runtime은 실행하지 않았다. 빌드 산출물은 logs/test_results 아래.

## TWIST2 shadow 실입력 후 시계 오류 수정

- 검토: twist2_vr_shadow_20260907_140321_90462cae/result.json에서
  523 packets, active_updates=1, non_increasing_clock 중단 확인.
  engage는 수신됐지만 pinch 종료까지 검증된 것은 아니다.
- 코드 수정: receive_vr_shadow.py의 경과/수신 시계를 모두 perf_counter로
  통일했다. Windows Python3.11 monotonic의 동일 tick 반환 가능성을 피한다.
  입력 검증 및 속도 제한은 그대로 유지한다.
- 테스트: 관련 pytest 10개 및 subtest 11개 통과.
- 남은 항목: 실제 Quest 재시험. G1 접근/출력 없음.

## TWIST2 shadow 손목 표시 설정 수정

- 검토: 표시 JSON이 hardware로 남아 있었으며 Unity 로그에서 tracked=True,
  engage_state=waiting-position을 확인했다. 손 추적 자체가 없었던 것은 아니다.
- 코드 수정: shadow BAT 시작 시 기존 SET_UNITY_DISPLAY_MODE.ps1로 simulation을
  선택하고 실패 시 중단한다. Unity Play 재시작 안내를 추가했다.
- 테스트: 로컬 설정 스크립트 실행 및 simulation JSON 확인. VR 화면 재확인은 필요하다.
- 남은 항목: Mink 실행 후 Play 재시작으로 손목 표시와 engage 확인.
  G1/WSL/DDS 및 물리 출력 설정은 변경하지 않았다.

## TWIST2 로컬 수신 전용 VR shadow

- 코드 수정: 실험 폴더 receive_vr_shadow.py, test_receive_vr_shadow.py 및
  tools/START_TWIST2_VR_INPUT_SHADOW.bat 추가. loopback UDP5008 수신만 하며
  송신/SDK/DDS/WSL/C++ 제어기 호출은 없다. 기존 실행기는 변경하지 않았다.
- 실행: shadow BAT 후 START_VR_HAND_TO_MUJOCO.bat --standard-mink
  --external-feedback. 기본 Regular 복귀 수신기와 동시 사용하지 않는다.
- baseline은 첫 정상 active Mink 가상 자세이며 실측 G1이 아니다. 로컬 후보
  10deg/0.08rad/s/0.25초 조건,180초 상한. 중단 시 재시작 필요. 화면은 기존
  Mink 결과이며 후보는 logs/test_results/twist2_vr_shadow_* 아래에만 저장한다.
- 검토/테스트: loopback 실제 datagram으로 baseline/목표갱신/pinch/수신침묵/
  포트점유/무입력 검증. 기존 입력 테스트 포함10개 및 subtest11개 통과.
  pytest XML: logs/test_results/twist2_vr_shadow_tests_latest.xml.
- 남은 항목: 실제 Quest 세션 검증, C++ receive-only shadow 및 정책 tick 통합,
  실측 피드백/전신 충돌/종료 정책 검토. 물리 출력 준비 완료가 아니며
  G1 접근/배포/실행은 하지 않았다. Arm SDK 허리 문제는 계속 보류다.

## TWIST2 경로 선택 및 VR 입력부 오프라인 준비

- 결정: 사용자가 "twist2로 하자 일단"이라고 선택했다. Arm SDK 허리 문제는
  해결된 것이 아니라 보류한다. G1 변경/배포/실행 승인은 포함하지 않는다.
- 검토: 기존 experiments/twist2_right_arm_manual C++/README와 어깨 한 축
  물리 기록을 기준으로 삼았다. 원본 단일 lowcmd writer, 정책/게인/종료 유지.
- 코드 수정: 같은 실험 폴더에 vr_input_offline.py 및 test_vr_input_offline.py
  추가. strict Mink parser 재사용, 오른팔22..28만 absolute rad 목표를 받아
  0.08rad/s 갱신. 나머지 캡처 값 불변, 최대 dt0.02초. 명시 session/sequence,
  시작범위/관절범위/입력 age 검사, timeout/invalid/disengage 후 latch stop.
  이 출력은 offline upper_target dict이며 DDS 메시지가 아니다.
- 테스트: direct unittest6개 통과. 속도/부호/비대상 불변/수렴/중복/세션 변경/
  stale/잘못된 시각/큰 목표 점프/재연동 차단 확인. C++/정책은 실행하지 않았다.
- 문서: TWIST2_INTEGRATION의 참고용이라는 오래된 설명과 허리/왼팔 소유권
  표기를 현행 실험본 기준으로 수정했다. Regular 반환 의미는 이 경로에 없다.
- 남은 항목: 수신 전용 socket/shadow, C++ 입력 연결과 전체 빌드 검증,
  실제 LowState/충돌/측정 오차 연계, 배포 및 제한 물리 시험의 별도 승인.
  이번 작업으로 Unity->G1 VR 조작이 완성된 것은 아니다. offline stop은
  후보 갱신 중단이며 실제 damping/정지 동작을 수행하지 않는다.

## 허리 기울어짐 문의용 근거 보고서

- docs/G1_ARM_SDK_WAIST_INCIDENT.md에 기존0.6/0.8/1.0 HOLD 로그 비교,
  명령 구성, 시간 흐름, 미확정 해석, 공식 지원 질문을 정리했다. 발송은 하지 않았다.
- sampled_command가 있는 행만 재집계했다(36/36/32표본). 세 실행 모두 팔
  목표 변화0deg, 허리 mode/kp/kd0. weight1.0의 허리 roll/pitch 변화 폭은
  5.186992/5.048893deg이며 weight 감소 전 HOLD부터 변화가 있었다.
  READY/종료 포함 집계와 표본 범위가 다르므로 과거 수치를 덮어쓰지 않는다.
- 최종 LowState age3.1116초, external_authority_handoff_confirmed=false를
  명시했다. zero25 write 성공을 종료 후 실시간 균형 회복 확인으로 해석하지 않는다.
- 검토/테스트: 원본 JSON 파싱과 재집계. 코드 수정 없음, 문서만 추가/갱신.
  새 G1/WSL/DDS 실행 없음. 남은 항목은 firmware 적합성과 물리 시험조건 확인이다.

## 오프라인 허리 감시에 IMU 기울기 추가

- 검토: 기존 테스트가 허리 관절 이상/통신 지연 및 fake release를 이미
  검사하고 있어 중복 세션 구현은 하지 않았다. 빠진 IMU 입력을 보완했다.
- 코드 수정: waist_guard_offline.py의 WaistGuardStudy에 선택적
  initial_imu_rpy/tilt_deg와 Evaluate의 imu_rpy 입력을 추가했다.
  baseline과 한계를 함께 명시해야 하며 단위는 baseline/sample rad,
  한계 deg다. 같은 LowState 표본의 age를 사용한다는 입력 계약이다.
  IMU 감시가 활성화되면 누락/비정상 IMU를 invalid_state로 latch한다.
  시작 roll/pitch 대비 축별 최단 각도 변화량을 검사하고 yaw 회전은
  기울기로 판정하지 않는다. 정상값 복귀로 기준점/중단 상태를 초기화하지 않는다.
  IMU 인자를 사용하지 않는 기존 로그 분석 경로의 동작은 유지한다.
- 테스트: 허리 관절각 불변 상태의 양방향 roll/pitch, 경계값, yaw 회전,
  각도 wrap, 누락/NaN/Inf, stale state, 명시 설정 검증을 추가했다.
  IMU 이상 -> fake release -> zero25 -> 재연동 차단을 테스트했다.
  관련4개 테스트 파일에서89개 및 subtest19개 통과, 변경2개 파일 메모리
  compile 통과. 실제 SDK/publisher/WSL/G1 실행은 없었다.
- 남은 항목: 축별 IMU 변화량은 균형 안정성 증명이 아니며 절대 초기 기울기,
  IMU 각속도/토크 감시나 fault release의 물리 적합성 검증을 대체하지 않는다.
  테스트의2deg, kp60/kd1.5 등은 가짜 입력 전용이다. 물리 프로파일의 미결정
  값과 잠금은 바꾸지 않았다. 현재 physical runner는 이 오프라인 guard를
  사용하지 않는다. firmware 제어권 해석과 실제 시험조건 확정은 여전히 필요하다.

## 기존 상체 A/B 및 static_stand의 허리 유지 방식

- 검토: references/lower_body/g1_upper_body_ab_test.py 전체와
  twist2_deploy/cpp_g1_twist2/twist2_static_stand.cpp의 초기화/명령 생성,
  twist2_common.hpp의 게인 및 hybrid_target을 로컬에서 확인했다.
- A/B 코드는 rt/arm_sdk에서 free/hold/offset을 제공한다. hold는 q_initial을
  한 번 저장하고 허리12..14에 mode1, kp60/kd1.5(기본값), dq/tau0을 보낸다.
  offset은 시작 pitch에 편차를 더한다. free는 허리 명령 필드를 설정하지
  않는 구현일 뿐, firmware가 Regular 허리 제어를 유지한다는 증거가 아니다.
  현재 경로의 허리 최신 실측 q/zero gain과도 payload가 완전히 같지는 않다.
- A/B 실행 위험: publisher가 사용자 Enter 확인보다 먼저 생성되고, 시작각
  캡처도 확인 전에 수행된다. 확인 대기가 길면 시작각이 오래될 수 있다.
  new_state가 없어도 이전 state로 계속 실행하며 freshness watchdog,
  최대 실행 시간, IMU/허리 편차 자동 중단이 없다. weight는3초에1까지 올라간다.
  finally에서2초 release를 시도하지만 Write 예외 시 잔여 release를 보장하지
  않는다. CSV를 생성하므로 읽기 전용 진단 도구로 실행하면 안 된다.
- static_stand는 MotionSwitcher ReleaseMode 후 rt/lowcmd 전신 명령을
  약500Hz로 보낸다. 하체0..11은 TWIST2 정책, 허리12..14는 캡처 목표를
  유지한다. 로컬 kKp/kKd의 허리 값은150/4이며 write_cycle에서 속도/관절/
  예측 토크 제한을 거친다. 종료는 damping이고 Regular 유지 구조가 아니다.
  이 숫자는 현재 arm_sdk용 권장값이 아니며 기존 게인은 임의 설정이었다는
  사용자 설명을 유지한다.
- 결정: 재사용 후보는 A/B의 시작 허리각 고정 및 별도 허리 PD 구성이다.
  원본 스크립트를 그대로 실행하거나 static_stand 게인을 이식하지 않는다.
  기존 offline HOLD 후보가 이미 이 구조를 표현하므로 중복 구현하지 않는다.
  물리 후보는 fresh capture, 제한 시간/weight, 허리/IMU 감시, fault release를
  갖춰야 하며 mode/게인/중단값 확정과 정확한 실행 승인은 여전히 별도다.
- 코드 수정: 없음. 문서만 갱신, 원본/물리 config/실행 잠금 유지.
- 테스트: 이번은 source inspection이며 로봇/WSL/SDK 프로그램 실행 없음.
  위 A/B 방식의 성공을 입증할 upper-body/waist 이름 CSV는 로컬 references
  검색에서 찾지 못했다. 코드 존재를 실제 검증 완료로 취급하지 않는다.
- 남은 항목: 오른팔만 SDK에 위임하고 나머지 Regular 유지가 지원되는지와,
  허리 HOLD 후보의 현재 firmware 적합성은 이 송신 코드로 확정할 수 없다.

## 허리 명령 필드 재대조와 검증 범위 (2026-09-07)

- 검토: 사용자가 실행한 find 결과에서는 tracker 캐시와 SDK CMake 버전만
  발견되었으며 제어 펌웨어 버전은 확인되지 않았다. 이번 작업은 로컬 소스와
  공식 Python arm7 소스 조회만 수행했다. G1 접속/WSL 실행은 하지 않았다.
- 현재 경로: Gate7 session의 결정 -> gate7_mink_arm_sdk_offline.py의
  build_measured_hold_frame 호출 -> gate6_arm_sdk_hold.py의 _apply_frame.
  Gate6 HOLD, Gate7 acquire/release도 같은 frame builder를 사용한다.
- arm_sdk_hold_contract.py는 모든 실측 q를 payload에 복사한 후 팔15..28만
  mode=1 및 PD 게인을 설정한다. 허리12..14는 최신 실측 q, mode=0,
  kp=kd=dq=tau=0이다. _apply_frame은 이를 그대로 SDK 메시지에 복사한다.
  따라서 허리 각도 필드가 있다는 사실은 허리 HOLD 명령이 있다는 뜻이 아니다.
- 공식 Python arm7은 arm_joints에 허리12..14를 포함하고 kp=60, kd=1.5,
  dq=tau=0과 시간에 따라 변하는 q 목표를 보낸다. 시작 실측각 고정 HOLD
  예제가 아니라 영점/팔 들기 동작 예제다. motor.mode는 명시 설정하지 않는다.
  slot29.q는 하나이며 첫 단계에서1, 종료 단계에서0으로 감소한다.
  https://github.com/unitreerobotics/unitree_sdk2_python/blob/master/example/g1/high_level/g1_arm7_sdk_dds_example.py
- 해석: PD 항 kp*(q_target-q_measured)+kd*(dq_target-dq_measured)에서
  현재 허리 게인은 모두0이다. 게인만 올리고 q_target을 매번 실측각으로
  덮어써도 고정 자세로 돌아오는 위치 오차 항은 생기지 않는다. 고정 HOLD
  후보라면 시작 시점 기준각과 게인/해제 정책을 함께 정의해야 한다.
  이 식은 명령의 PD 항 설명이며 firmware 내부 혼합/보상 토크 규격은 아니다.
- 코드 수정: 없음. 현재 물리 게인, 실행 잠금, 제어 경로 유지. 문서만 갱신.
- 테스트: py -3.11 -B hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py
  실행, 7개 통과. 가짜 메시지 복사 및 payload/weight/제한 검증이며 SDK/DDS
  publisher나 실제 로봇 응답을 시험하지 않는다.
- 남은 항목: zero gain이 Regular 허리 제어 유지라는 과거 해석은 근거가 없다.
  기울어짐 원인은 아직 가설이다. 공식 예제와의 차이만으로60/1.5 등 게인을
  물리에 적용하지 않는다. 허리/왼팔 Regular 소유권 유지와 양팔/허리 SDK HOLD는
  다른 설계이며 현재 firmware의 지원 범위 확인이 필요하다.

## 공식 근거 추가 조사와 물리 시험 미결정 사항

- 검토: 공식 Motion wiki는 motion control 하체와 Arm SDK 양팔 명령의
  혼합을 설명하고 weight 점진 전환을 권고하지만 대규모 검증이 아니라고
  경고한다. 설명 예시는 1DoF waist 모드이며 현재3DoF Regular에 대한
  firmware별 허리 소유권 명세로 취급하지 않는다.
  https://github.com/unitreerobotics/xr_teleoperate/wiki/Motion
- 공식 ROS2 arm 예제 SendPositionCommand는 허리 kp/kd를 기본60/1.5의
  4배인240/6으로 설정한다. StopControl은 다시60/1.5를 사용한다.
  G1ARM7 분기는17축이며 파일 기본 빌드 선택은G1ARM5다. 이 실행 예제를
  복사하지 않았다. 앞서 본 SDK60/1.5, XR300/3과 달라 공통 물리 게인
  규격이라고 해석할 수 없다.
  https://github.com/unitreerobotics/unitree_ros2/blob/master/example/src/src/g1/high_level/g1_arm_sdk_dds_example.cpp
- 공식 low-level 예제의 motor.mode 1/0은 Enable/Disable로 설명되지만
  rt/lowcmd 경로의 의미를 rt/arm_sdk firmware의 허리 처리에 그대로
  대입하지 않는다. mode_pr, mode_machine과도 구분한다.
- 접근 한계: support.unitree.com의 arm_control_routine 및
  sport_services_interface는 이번 조회에서 timeout, 검색에서도 해당 명세를
  확보하지 못했다. 사용자 GitHub 이슈 응답은 제조사 확정 명세로 사용하지 않는다.
- 코드 수정/테스트: 이 항목은 문서만 갱신. 실제 출력/게인/config 변경 없음.
- 제조사 확인에 필요한 구체 질문(아직 발송하지 않음):
  1. 현재3DoF 허리 G1의 Regular에서 slot29 weight는12..28 전체에 적용되는가?
  2. 오른팔22..28만 SDK에 맡기고 왼팔/허리는 Regular에 남기는 지원 방식이 있는가?
  3. rt/arm_sdk에서 허리 motor.mode=0, kp=kd=0은 무시/해제/제로토크 중 무엇인가?
  4. 허리 HOLD가 필요하다면 해당 firmware의 권장 mode/게인/해제 절차는 무엇인가?
  함께 전달할 근거: 정지 목표 HOLD weight1.0에서 실제 기울어짐, 기존 허리
  mode/gain0, mode_pr0/mode_machine5, baseline과 물리 로그. firmware 버전은
  아직 확보하지 않았으며 요청 없이 G1 내부에 접속/변경하지 않는다.
- 결정: 공개 송신 예제만으로 허리 HOLD 물리 시험값을 확정하지 않는다.
  기존 실패 경로 재실행은 보류한다. 더 많은 대수 테스트가 이 명세 공백을
  해소하지는 않으므로 준비 완료나 다음 단계 물리 실행 가능으로 표현하지 않는다.

## 양팔/허리 HOLD 시험 초안 (실행 불가)

- 검토: 최신 baseline은 일정했지만 이전 baseline pitch 속도는8.87deg/s까지
  관측되었다. 그 때문에 탐색값5deg/s를 물리 중단 기준으로 확정하지 않았다.
- 코드 수정: config/g1_waist_hold_trial_draft.json 추가. 현재값을 읽어17축
  고정 목표를 캡처하는 정책, VR/저장자세 명령/자동 재보정/다리 명령 변경 금지를
  명시했다. 제안 일정은 weight0.2, 250Hz, 3+3+3초, zero25이나 승인값은 아니다.
  mode/kp/kd, 허리각/속도/IMU/토크 제한과 fault release는 null(미결정)이다.
  physical_runner=null, hardware_output_authorized=false이며 물리 실행기가 없다.
- 테스트: 기존 Gate6 loader가 이 draft schema를 거부함을 추가 검증했다.
  기존 Gate6 설정 잠금과 미결정 필드/대상17축도 확인. 관련 pytest94개와
  subtest4개 통과. 기존 물리 제어/게인/실행기는 변경하지 않았다.
- 남은 항목: 실행 준비 완료가 아니다. firmware mode 해석, 검증할 게인과
  감시/중단/해제 조건을 먼저 정하고 해당 프로파일의 live guard/실행기 검증과
  명시적 물리 승인을 별도로 받아야 한다. 숫자를 비운 것은 사용자에게 임의
  게인 선택을 요청한다는 뜻이 아니라 근거가 아직 확보되지 않았다는 뜻이다.

## 허리 baseline 실제 기록 확인 (13:16 / 13:17)

- 검토: logs/read_only_baselines/waist_20260907_131618_983779와
  waist_20260907_131702_260380 모두 completed=true, 각442표본/약15.03초,
  publisher_created=false, hardware_authorized=false, mode pair=(0,5).
- 최신 기록: yaw/roll/pitch 각도 변화 폭 0.00691/0.01262/0.01516deg,
  속도 절댓값 p95 1.277/0.724/0.324deg/s, 최대 2.063/0.947/0.610deg/s.
  최대 표본 간격35.35ms, 최대 관측 LowState age5.23ms. 이 표본에서
  수신 장애 증거는 없지만 모든 DDS 패킷의 무손실이나 firmware 승인 증거는 아니다.
- 앞선 기록: pitch 변화 폭0.55185deg, 속도 p95 6.521/최대8.874deg/s.
  두 기록 시작 자세도 달라 두 구간을 하나의 중립 기준으로 합치지 않는다.
  5deg/s는 앞선 baseline에서도 넘으므로 탐색용 감시값을 그대로 물리에 적용하지
  않는다. 원인을 센서 잡음/외력/제어로 단정하지 않았다.
- 검증: 최신 samples.jsonl을 오프라인 재집계하여 저장 요약과 일치 확인,
  sequence 엄격 증가 확인. 코드 변경/새 WSL/DDS 실행/물리 명령 없음.
- 남은 항목: 최신 구간의 관절각은 거의 일정하지만 전신 균형/IMU/Regular 여부와
  물리 HOLD 안전 승인으로 해석하지 않는다. 물리 시험은 새 현재값에서 시작해야
  하며 이 저장값을 곧바로 목표 명령으로 사용하지 않는다. 허리 HOLD 후보의
  게인/mode/중단 및 해제 조건은 별도 검토가 필요하다.

## Arm SDK 제어 범위 공식 소스 대조 (2026-09-07)

- 검토: 오른팔 목표 갱신과 오른팔만의 제어권 획득은 구분한다. 아래 공개
  송신 예제에서 오른팔만 선택하는 별도 weight/소유권 mask는 확인되지 않았다.
  이는 모든 firmware/API에서 불가능하다는 증거는 아니다.
- 공식 SDK C++/Python arm7 예제: arm_joints는 양팔14축과 허리3축의17개이며
  weight는 motor_cmd[29].q 하나이다. 허리에도 q/dq/kp/kd/tau를 설정한다.
  두 예제는 관절 motor mode를 명시 설정하지 않으므로 mode=1 필수라는
  결론을 이 코드에서 도출하면 안 된다. 기본 kp60/kd1.5는 물리 권장값으로
  채택하지 않았다.
  https://github.com/unitreerobotics/unitree_sdk2/blob/main/example/g1/high_level/g1_arm7_sdk_dds_example.cpp
  https://github.com/unitreerobotics/unitree_sdk2_python/blob/master/example/g1/high_level/g1_arm7_sdk_dds_example.py
- 공식 XR G1_29_ArmController: motion_mode에서 rt/arm_sdk를 선택한다.
  초기화시 전 관절 payload에 시작 실측각과 mode/gain을 설정하며, 이후14개
  팔 목표를 갱신한다. 허리에는 시작각과 kp_high300/kd_high3이 남는다.
  이는 현재의 허리 mode/gain0과 다르다. 이 값을 그대로 복사하지 않는다.
  다리 payload에도 값이 들어간다고 firmware가 다리를 이 토픽으로 제어한다고
  단정할 수 없다. 공개 송신 코드와 로봇 내부 수신/혼합 로직은 별개다.
  https://github.com/unitreerobotics/xr_teleoperate/blob/main/teleop/robot_control/robot_arm.py
- 로컬 도구: g1_inspect_arm_sdk.py는 입력 토픽 관측일 뿐 firmware 승인/실제
  소유권을 보여주지 않는다. g1_check_arm_mode.py의 mode_machine 2/9 해석도
  현재 로봇(관측5)의 제어권 판정 근거로 재사용하지 않는다. 두 파일 모두 미실행.
- 참고 이슈173은 사용자 경험/질문이며 공식 해결책으로 취급하지 않았다.
  공개 페이지에서 해당 질문에 대한 제조사 답변은 확인하지 못했다.
  https://github.com/unitreerobotics/unitree_sdk2_python/issues/173
- 코드 수정/테스트: 문서만 갱신. 물리/WSL 실행, 게인 변경, firmware 검사 없음.
- 남은 항목: 현재 firmware에서 slot29의 허리/좌우팔 적용 범위, mode=0과
  zero gain 처리, 오른팔 단독 위임 가능 여부를 확인해야 한다. 단일 팔 목표+
  왼팔/허리 명시적 HOLD는 조사할 대안이지만 Regular 소유권 유지와는 다르다.
  연속 baseline을 먼저 확보하고, 실제 시험은 별도 조건 검토/승인 후에만 한다.

## 허리 연속 baseline 기록 실행기 준비

- 검토: 기본 read-only BAT의 마지막 상태 저장만으로는 시간 구간 분석이
  불가능하여 포트 전달 없이 rt/lowstate를 기록하는 전용 경로를 추가했다.
- 코드 수정: waist_baseline_read_only.py와
  tools/RECORD_G1_WAIST_BASELINE_READ_ONLY.bat 추가. PC WSL의 기존 SDK를
  사용하며 G1 파일/모드 변경, DDS publisher, 모터 명령, UDP 전달은 없다.
  첫 신선한 상태를 최대 10초 기다리고 이후 15초간 최대 30Hz로 29축 q/dq를
  기록한다. 시작 후 LowState 지연 0.25초 초과 시 불완료로 종료한다.
- 결과: logs/read_only_baselines/waist_<timestamp>/samples.jsonl 및 summary.json.
  허리 3축 초기/최종각, 변화 폭, 초기값 대비 최대편차, 속도 절댓값 p95/최대,
  표본 간 최대 간격과 관측 age, mode pair를 기록한다. 실패 시에도 summary를
  저장하며 completed=false이다. 결과는 안전 승인이나 MotionSwitcher 확인이 아니다.
- 테스트: 신규 6개 포함 관련 pytest 84개와 subtest 4개 통과.
  신규 모듈 import는 SDK를 로드하지 않으며 Capture는 가짜 시계/상태로 검증했다.
- 남은 항목: 새 실행기의 실제 WSL/G1 기록은 아직 실행하지 않았다.
  사용자 실행 후 연속 로그를 확인한다. 허리 HOLD 물리 후보는 여전히 미적용이며
  이번 변경으로 물리 실행을 허가하지 않는다.

## 재충전 후 읽기 전용 수신 확인 (13:10:34)

- 사용자 START_G1_READ_ONLY.bat 실행/종료 후 로컬
  logs/runtime/g1_hardware_lowstate.json 확인. received_packets=16556,
  eth2, mode_pr=0, mode_machine=5, fault.active=false, phase=OFFLINE.
  command_output_enabled=false, publisher_present=false. OFFLINE은 종료 상태다.
- 마지막 허리 yaw/roll/pitch: 0.061/0.326/-1.634 deg.
  마지막 각속도: 1.179/-0.504/4.280 deg/s. base velocity 크기 0.0129 m/s.
  이는 단일 종료 시점 표본이며 전체 구간의 안정성 판정이 아니다.
- 한계: 기본 BAT는 --record-jsonl을 지정하지 않아 연속 허리 기록이 없다.
  15초간 흔들림을 평가할 수 있다고 안내한 것은 부정확했다. 이번 결과는
  수신 확인과 종료 시점 값 확인에만 사용한다. MotionSwitcher ai 확인도
  이 LowState의 mode_pr/mode_machine만으로 대체하지 않는다.
- 코드 수정/실행: 없음. 로컬 저장 파일만 분석했으며 새 물리 출력/WSL 실행 없음.
  다음 물리 시험 전에 연속 baseline 기록과 허리 HOLD 프로파일/중단 조건을
  준비해야 한다. 기존 1.0 실패 경로 재실행 보류는 유지한다.

## 충전 중 후속 검증: 허리 3축 PD 부호

- 검토: 기존 후보는 roll 한 방향의 PD 계산만 확인했으므로 yaw/roll/pitch와
  반대 방향, 속도만 있는 상태, 복귀 중 상태를 추가 검증했다.
- 코드 수정: test_waist_hold_offline.py에 3축 x 7상태 x 3weight의 63개
  pytest 사례를 추가했다. 비영점 초기 자세에서 각 축 독립성, 복원/감쇠 부호,
  고정 기준, 최대 절댓값 집계와 offline 표기를 확인한다. 실제 코드는 불변이다.
- 테스트: 관련 pytest 92개와 subtest 4개 통과. 기존
  TEST_G1_WAIST_HOLD_OFFLINE.bat에 포함된다.
- 남은 항목: kp=60/kd=1.5는 계산 검사용 입력이지 물리 권장값이 아니다.
  unblended_pd_algebra_nm는 weight=0에서도 남는 수학 항이며 실제 모터 토크가
  아니다. 축간 기계적 결합, 중력, firmware blending과 균형은 이 검사로 평가하지
  않았다. 1.0 물리 재시험 보류와 기존 출력 잠금은 유지한다.
- 다음 판단: 단순 계산 테스트를 더 늘려도 firmware 제어권 문제는 해결되지 않는다.
  원인 확인에는 승인된 제한 시험과 실제 상태 관측이 필요하며, 충전 중에는
  실제 출력 없이 명령/상태 기록과 시험 조건만 준비한다.

## 충전 중 후속 검토: 허리 명령 소스와 기록 대조

- 검토: arm_sdk_hold_contract.py는 최신 실측 q를 허리 12..14의 payload에
  복사하지만 mode/kp/kd/dq/tau는 모두 0이다. 이는 시작 자세를 유지하는 PD
  HOLD 명령과 다르다. references/lower_body/g1_upper_body_ab_test.py의
  --waist-mode hold는 q_initial을 고정 목표로 사용하고 mode=1, 기본 kp=60,
  kd=1.5를 넣는다. 이 기본 게인은 현재 로봇에 검증된 설정이 아니다.
- 저장 기록: gate6_hold_20260907_115747_b771ceae의 명령 표본 36개,
  115826_a9a710e8의 36개, 115904_a84b17e7의 32개, 총 104개 모두
  waist_mode=[0,0,0], waist_kp/kd/dq/tau=[0,0,0]임을 재확인했다.
  상태 이벤트 전체가 아니라 sampled_command가 존재하는 표본 수이다.
- 코드 수정: validate_command_frame의 설명만 수정했다. payload 검사는
  firmware 허리 제어권 유지나 상체 무영향을 보장하지 않음을 명시했다.
  검증 조건, 게인, 송신 경로, 물리 설정은 변경하지 않았다.
- 테스트: 관련 오프라인 pytest 29개와 subtest 4개 통과.
- 남은 항목: weight 변경과 허리 지지의 관계는 유력한 조사 대상이지만
  원인 확정은 아니다. 기존 hold 코드를 그대로 실행하지 않는다. 별도 승인된
  시험 전에 허리 mode 해석, 검증할 게인, 중단/해제 시 균형 영향을 검토해야 한다.
  이번 단계는 로컬 소스/저장 파일만 읽었으며 WSL/G1에는 접속하지 않았다.

## 충전 중 후속 검증: 해제 도중 부분 송신 실패

- 검토: 기존 허리 감시 후보 테스트에 램프 중간 실패와 zero tail 부분 실패가
  빠져 있어 보완했다. 실제 제어 경로와 설정은 변경하지 않았다.
- 코드 수정: test_waist_guard_offline.py에 가짜 시계/송신 콜백 기반 4개
  subtest를 추가했다. 램프 중간, zero tail 첫 번째/13번째/25번째 실패를 주입한다.
- 테스트: 관련 pytest 29개와 subtest 4개 통과. 램프 실패 후 별도 zero tail을
  시도하고, tail 일부 실패는 output_state_unknown=true로 기록함을 확인했다.
  마지막 성공 송신 시각/weight, 단조 감소, 허리 기준 유지, 오류 latch도 확인했다.
  모든 경우 external_authority_handoff_confirmed=false를 유지한다.
- 남은 항목: 실제 통신 수신 여부와 firmware 제어권 회수, 균형 회복은 미검증이다.
  허리 HOLD 후보/감시 임계값은 물리 경로에 미적용이며 1.0 재시험 보류를 유지한다.
- 재검증: 기존 tools/TEST_G1_WAIST_HOLD_OFFLINE.bat에 새 테스트가 자동 포함된다.
  G1/VR/WSL, DDS publisher, 로봇 명령은 사용하지 않았다.

## 충전 중 오프라인 허리 감시/해제 검증

- 코드: waist_guard_offline.py에 시작 허리각 기준 각도/속도/상태 신선도
  감시 후보 추가. 첫 오류를 latch하며 정상값 복귀로 자동 재연동/기준변경하지 않음.
  기존 물리 경로와 분리된 study이며 실제 게이트에는 적용하지 않았다.
- 저장 로그 비교: 각도1/2/3deg,속도5/10/20deg/s,신선도0.25s의9개
  탐색용 조합. 0.6/0.8 로그는 모두미감지,1.0은모두HOLD구간에서감지.
  READY 이후약3.50~4.25초의첫표본. 물리 정지 지연/균형 회복 예측이 아니다.
  4Hz표본/3회시험에 한정되므로 이 조합을 실제임계값으로 확정하지 않는다.
- 합성 테스트: 각도초과/속도초과/stale/NaN/잘못된길이/음수age 및 latch,
  READY/명령표본누락 거부. 기존 execute_release_sequence를 가짜시계와
  기록콜백으로 실행해 단조weight감소,25zero,허리고정목표 유지 확인.
  첫송신실패시zero시도 및 전체송신실패시output_unknown 확인.
- 테스트: 신규 후보+기존release/Gate6hold/fault/interrupt28개 통과.
- 직접 실행: tools/TEST_G1_WAIST_HOLD_OFFLINE.bat. VR/G1/WSL 필요 없음.
  출력: logs/test_results/g1_waist_guard_offline.json. 실제 제어 출력 없음.
- 남은 항목: 허리HOLD후보와 guard의 실제 동역학/firmware 소유권 검증,
  감시 발동시 해제의 균형 영향 확인. 기존 실패1.0 물리 재실행 보류 유지.

## 시작 실측 허리 HOLD 후보의 오프라인 검증

- 사용자 확인: 1.0에서 실제 기울었고 종료 후 안정 자세로 돌아옴.
- 검토: 공식 C++ arm7의17축에 허리12..14 포함, kp60/kd1.5 설정.
  단, 공식 예제는 허리를0으로 보간하며 motor mode를 명시 설정하지 않는다.
  로컬 g1_upper_body_ab_test.py hold는 시작 q를 저장하여 유지하고 mode1을
  설정한다. 따라서 후보는 그 hold 방식을 참고하며 공식 예제와 완전히 같지 않다.
  https://github.com/unitreerobotics/unitree_sdk2/blob/main/example/g1/high_level/g1_arm7_sdk_dds_example.cpp
- 코드 수정: waist_hold_offline.py와 오프라인 테스트 추가.
  입력: 실측29축/팔목표14축/시작허리3축/명시적 kp,kd,mode,weight.
  출력: offline_only dict. SDK/socket/publisher/실행기 연결 없음.
  시작허리 q를 고정하고 허리 mode/kp/kd만 후보값으로 바꿈.
  기존 물리 validator는 양팔 외 게인을 금지하므로 후보를 계속 거부한다.
  기존 Gate6/Gate7 명령 생성, 게인, 잠금 설정은 변경하지 않음.
- 테스트: 후보/기존hold/Gate6/Gate7 core34개 통과.
  모드0/1,weight0/.6/.8/1/.4/0,허리drift+-0.1rad에서 고정 목표 및
  허리 외 필드 불변 확인. 잘못된 입력/READY누락 거부, 실제 출력 계약 거부 확인.
- 로그 분석: 실패1.0 events32표본에 예제비교용60/1.5,mode1 적용.
  kp*(q_initial-q_measured)-kd*dq의 절대최대 yaw/roll/pitch는
  0.2112/5.4454/5.2811Nm. 이 수치는 weight합성 전 PD항의 대수 계산이다.
  실제 모터 토크 예측/폐루프 시뮬레이션/안정성 검증으로 해석하지 않는다.
  결과: logs/test_results/g1_waist_hold_study_weight10.json.
- 남은 항목: firmware mode/weight/허리제어권 의미, 게인 적합성,
  허리각/속도 감시와 오류시 해제 설계, 동역학 및 별도 제한물리 검증.
  후보를 기존 물리 실행기에 연결하지 않는다. 기존1.0 재시험도 보류 유지.

## 반복 HOLD 결과: weight1.0에서 고정 목표인데도 허리 기울어짐 재현

- 사용자 3단계 실행 완료 후 로컬 결과만 분석. 추가 WSL/DDS/출력 실행 없음.
- 0.6: gate6_hold_20260907_115747_b771ceae, 정상 종료2275프레임,
  zero25/25. 38표본 허리 yaw/roll/pitch 범위0.01765/0.18599/0.11387deg,
  최대 양팔 추종오차0.45319deg, 팔 명령 목표 변화0deg.
- 0.8: gate6_hold_20260907_115826_a9a710e8, 정상 종료2275프레임,
  zero25/25. 38표본 허리 범위0.02225/0.19080/0.18479deg,
  최대 양팔 추종오차0.75325deg, 팔 명령 목표 변화0deg.
- 1.0: gate6_hold_20260907_115904_a84b17e7, FAULT,2052프레임,
  runtime base speed0.157m/s >0.150m/s. 오류는 해제 구간에서 발생.
  34표본 허리 범위0.16804/5.19570/5.04889deg,
  최대 양팔 추종오차1.32317deg, 팔 명령 목표 변화0deg.
  HOLD weight1.0 구간에서 이미 roll약0.49->5.41deg,
  pitch약-2.13->-6.49deg로 변했다. 해제에서 pitch약-7.08deg까지 기록.
  따라서 오류가 해제 중이라는 이유로 해제에서 처음 기울었다고 해석하면 안 됨.
- 모든 단계의 sampled waist kp/kd는0. 1.0 고정 팔 목표에서도 큰 변화가
  재현되어 VR/IK 목표 이동이 이 현상의 필수 조건은 아님을 확인했다.
  허리 유지 부재/수신측 제어권 해석 가설을 지지하지만 펌웨어 내부 인과 확정은 아님.
- 3개 실행 config는 모두false로 재잠금 확인. 1.0 오류 후에도 소프트웨어
  ramp release 및zero25/25 완료. 외부 펌웨어 handoff확인은false.
  약4Hz 진단이라 표본 사이 피크/실제 균형 회복을 보장하지 않는다.
- 1.0 및 VR 물리 재시험 보류를 사용자에게 알림. 0.6/0.8 무이상도
  임의 팔 이동이나 장시간 운용의 안전 보장은 아님. 실제 소리/기울어짐 및
  종료 후 자세 안정 여부는 사용자에게 확인 필요. 기존 실행기 재실행하지 말 것.

## 0.6/0.8/1.0 고정 HOLD 단일 단계 실행기 준비

- 사용자: 0.4 시험도 기울어짐/이상 소리 없음. 이후3단계를 바로 선택해서
  시험할 수 있게 준비 요청. 이번 작업은 로컬 준비/오프라인 테스트만 수행.
- tools/START_G1_GATE6_WEIGHT_HOLD.bat -> gate6_weight_hold_trial.py.
  1=0.6,2=0.8,3=1.0 선택 후, 해당1회 출력과 현장 조건을 Y로 명시 확인.
  자동 다음 단계 없음. 이전 단계 로그/육안 확인 전 높은 단계를 선택하지 않는다.
- 기본 g1_gate6_hold.json(weight0.4,잠금false)은 수정하지 않는다.
  각 실행마다 logs/physical_tests/gate6_hold_<time>_<id>/에 config/mode/precheck/
  status/events 및 console logs 저장. 선택weight 외 설정은 기본값 재사용,
  고정 게인/시간/주기 변형은 실행 전 차단. Y 확인 후에도 새 토큰 기반
  실측 검사와 기존 Gate6 entry guard를 통과해야 publisher 생성 가능.
- WSL/Windows의 알려진 제어 프로세스를 확인한다. 이는 다른 PC나 임의 이름의
  모든 publisher를 탐지하는 보장이 아니므로 현장 단독 제어 확인 필요.
  준비 forwarder는15초 timeout으로 종료, 이후 고정 HOLD 수행.
- 시험용 config만 출력 직전에 잠시 승인하고 finally에서 다시 잠금.
  강제 창 종료/전원 단절은 finally 및 로그 저장을 보장하지 않으므로 피한다.
  Ctrl+C는 자식 종료/해제를 기다리며 강제 kill하지 않는다. 원격 비상정지 준비 필수.
- 테스트: mocked 단계 선택/취소/설정변경 차단/precheck실패/출력실패 후재잠금,
  기존 Gate6 hold/fault/interrupt 포함20개 통과. WSL/G1 실행 안 함.
  신규 실행기의 실제 통신/실시간 주기는 다음 승인 시험에서 확인 필요.

## weight0.4 고정 HOLD 물리1회 완료 (11:49)

- 사용자 준비 완료 확인 후 최신 CheckMode/실측 검사 수행.
  DIRECT_TELEOP_READY, clearance27.69mm,100packets,
  arm span0.0062deg,velocity_p951.318deg/s. 모드 변경 없음.
- weight0.4/3초 인수/3초 고정 유지/3초 해제 시험1회 정상 종료.
  logs/runtime/g1_gate6_hold_weight04.json 및 .jsonl에 결과 보존.
  기존0.2 로그와 분리했으며, 종료 직후 Gate6 물리 잠금false 복구.
- 38표본에서 허리 yaw/roll/pitch 범위0.01765/0.10102/0.05322deg.
  양팔 명령 목표 변화0deg, 최대 양팔 추종 오차0.16205deg.
  큰 허리 기울어짐은 해당 표본에서 관찰되지 않았으나4Hz 표본 한계 있음.
  사용자도 기울어짐/이상 소리 없음을 확인. 펌웨어 제어권 복귀는 별도 미확인.
- 추가 물리 시험 및1.0 자동 전환 없음. 다음 단계는 관찰 결과 검토 후
  별도 승인할 것. G1 내부 파일/서비스 변경 없음.

## weight0.4 고정 HOLD 준비 (물리 미실행)

- 사용자: weight0.2 시험에서 기울어짐/이상 소리 없었다고 확인.
- config/g1_gate6_hold.json 최대 weight만0.2에서0.4로 변경, 잠금false 유지.
  고정 팔 목표/게인/3초 인수/3초 유지/3초 해제/25 zero프레임은 그대로.
  같은3초 램프이므로 weight 상승/하강률도0.0667/s에서0.1333/s가 된다.
  따라서 다음 결과는 최대weight만이 아니라 이 램프 조건을 함께 명시한다.
- 오프라인 비교 테스트: 0.2/0.4의 2276시점 명령에서 weight 슬롯 외의
  q/mode/kp/kd/dq/tau가 동일하고9초 이후weight0임을 확인한다.
  Gate6 hold/fault/interrupt 테스트14개 통과.
- 다음 물리 실행은 weight0.4 고정 HOLD1회에 대한 승인과 현장 준비 확인 후.
  이번 준비 단계에서 WSL/DDS/G1 실행 없음. 기존0.2 결과 로그는 그대로 보존.

## 고정 목표 Gate6 HOLD 물리 1회 완료 (11:44)

- 사용자 승인 및 지상 Regular/주변 비움/비상정지 준비 확인 후 실행.
  최초 실행은 start_gate6_hold_wsl.sh CRLF로 Python 시작 전 차단됨.
  로컬 해당 sh만 LF 정규화하고 새 토큰 실측 검사 후 실제 출력1회 수행.
- 최신 precheck: DIRECT_TELEOP_READY, clearance27.79mm,
  101 packets, right-arm span0.0082deg, velocity_p951.230deg/s.
  MotionSwitcher CheckMode만 호출했고 form0/nameai. 모드 변경 없음.
- 승인 범위 그대로 weight0.2, 인수3/유지3/해제3초, 고정 양팔 목표.
  2275프레임 송신, zero25/25, release_fault없음, weight0으로 종료.
  외부 펌웨어 제어권 복귀 확인은 false이며 소프트웨어 송신 완료와 구분한다.
  config/g1_gate6_hold.json은 종료 직후 false로 복구. Gate7도 잠금 유지.
- logs/runtime/g1_gate6_arm_sdk_hold.jsonl 최신 종료 전12초의38표본:
  허리 yaw/roll/pitch 범위0.0054/0.0131/0.0366deg.
  표본 팔 목표 변화0deg, 최대 양팔 추종 오차0.09682deg.
  약4Hz 표본이므로 사이의 순간 최대값을 보장하지 않는다.
- 결론: 이번 weight0.2 고정 목표 조건에서는 이전의 큰 허리 변화가 재현되지
  않았다. weight1.0 또는 팔 이동 조건의 문제 해결을 의미하지 않는다.
  사용자도 기울어짐/이상 소리 없음을 확인했다. 추가 물리 실행 자동 진행하지 않는다.
- 준비용 읽기 전용 forwarder도 제한 시간 후 종료됨. G1 내부 파일 변경 없음.

## 고정 목표 HOLD의 허리 진단 준비

- 검토: Gate6는 시작 실측 양팔 q를 고정하고 weight만 상승/유지/해제한다.
  현재 config/g1_gate6_hold.json은 잠금 상태, weight0.2,
  상승3초/유지3초/하강3초/zero25프레임/250Hz이다. 이 값을 바꾸지 않았다.
- 코드 수정: gate6_arm_sdk_hold.py의 기존 상태 로그에 전신 실측 q/dq,
  LowState 수신 Unix ns, 표본 명령 q/weight와 허리 mode/kp/kd/dq/tau 추가.
  기존 약4Hz 상태 보고 주기는 유지한다. sampled_command는 실제 구성한
  송신 프레임이며 firmware acknowledgement는 false. BLOCKED/최종 상태처럼
  해당 프레임이 없는 보고는 null로 남긴다. fault-release 내부 매 프레임
  진단은 추가하지 않았으며 기존 해제 증거/오류 처리는 유지한다.
- 테스트: Gate6 hold/fault/interrupt, Gate7 core/finalizer에서
  36 passed + 5 subtests. 허리 실측만0.1rad 변한 입력에서도 양팔 목표는
  그대로이며 변한 실측/허리0게인이 별도 기록됨을 확인했다.
- 결과 경로: logs/runtime/g1_gate6_arm_sdk_hold.jsonl의 details에
  schedule_phase, last_successful_write_unix_ns, sampled_command,
  measured_all_q_rad, lowstate_received_unix_ns. 상태 요약은 같은 이름의 json.
- 남은 항목/다음 시험: 별도 물리 승인 후, VR 입력 없이 위 고정 목표 HOLD에서
  허리 변화가 인수/유지/해제 중 언제 나타나는지 확인한다. weight0.2의 무이상은
  weight1.0의 안전성 증거가 아니다. 반대로 고정 목표에서 기울어지면 손 목표
  이동은 필수 조건이 아니지만 허리 제어권 원인을 단독으로 확정하지는 않는다.
  PREPARE_G1_GATE6_HOLD.bat는 읽기 전용 준비이며 물리 HOLD를 시작하지 않는다.
  이번 작업에서 G1/WSL/DDS 실행 및 물리 승인 변경은 없었다.

## 허리 변화와 명령 단계의 시간축 기록 보완

- 검토: 기존 결과의 마지막 송신 시각만으로는 취득/팔 이동/해제 구분이 어렵다.
- 코드 수정: gate7_live_arm_sdk.py에 CommandDiagnosticTrace 추가.
  ACQUIRE/CONTROL/RELEASE/ZERO_WEIGHT 단계별 SDK Write 반환 시각(Unix ns,
  monotonic), weight, 명령29관절 q, 허리 mode/kp/kd/dq/tau,
  전신 실측 q와 snapshot age를 결과 JSON의 command_diagnostic_trace에 기록.
  실측은 명령 적용 후 응답이 아니라 해당 시점에서 이용 가능한 LowState이다.
  기존 전신 로그의 몸체 자세와는 Unix 시각으로 비교한다. 이 기록 자체에는
  몸체 IMU/odom이 없고 펌웨어 수신 확인도 아니다.
- 기본20Hz 표본 및 단계 전환 즉시 기록, 최대10000개. 제어 중 디스크 쓰기
  없이 메모리에 보관하고 해제 처리 후 기존 결과 JSON에 저장한다.
  표본 한도 초과/기록 오류 수를 남기며 기록 오류는 해제 송신을 중단하지 않는다.
  강제 프로세스 종료나 전원 단절 시 메모리 기록은 유실될 수 있다.
- 테스트: core/hold/profile/entry/finalizer/release 6개 파일,
  50 passed + 8 subtests. 최종 해제 실행 테스트에도 실제 진단 클래스를 넣어
  정상 해제 기록과 기존 송신 실패 시 동작을 확인. SDK/WSL/물리 실행 없음.
- 남은 항목: 실시간 주기 영향과 실제 기기 명령 해석 미검증. 물리 잠금 유지.
  다음 시험 설계는 팔 목표 고정 인수와 팔 목표 이동을 분리한다.
  IK/PD/허리 제어/속도/승인 설정은 이번 수정에서 변경하지 않았다.

## 허리 제어권 자체 조사로 전환

- 의미 정정: 담당자가 일시 부재한 것이 아니라, 이 부분을 담당한 사람이 없다.
  외부 담당자의 답변을 기다리는 단계는 두지 않는다.
- 사용자: 확인할 담당자가 없으므로 자체 조사한다. 아래 과거 기록의 담당자
  확인은 진행 조건에서 제외한다. 물리 출력 잠금과 G1 변경 금지는 유지한다.
- 검토: 공식 C++ arm7 예제도 arm_joints에 허리12..14를 포함한17축을 넣고
  q/dq/kp/kd/tau를 설정한다. 예제에는 motor mode를 명시적으로 설정하는
  코드가 없다. 따라서 현재 검증기의 mode0="disabled" 표현은 메시지 필드
  검사일 뿐 rt/arm_sdk 수신 측의 허리 제어권 보장으로 볼 수 없다.
  https://github.com/unitreerobotics/unitree_sdk2/blob/main/example/g1/high_level/g1_arm7_sdk_dds_example.cpp
- 공식 저장소 issue173에는 Arm SDK 사용 중 상체 흔들림과 허리 명령 추가
  경험이 보고되어 있다. 사용자 보고이며, 정지 중인 우리 시험과 조건이
  다르고 펌웨어 계약이나 해결책의 공식 확인은 아니다. 게인 이식 근거로 쓰지 않는다.
  https://github.com/unitreerobotics/unitree_sdk2_python/issues/173
- 코드 수정: 없음. IK/PD/weight/허리 명령 변경 없음. 인계 문서만 갱신.
- 테스트: 이번 배치는 공식 소스와 로컬 메시지 구성 비교만 수행했다.
  WSL/DDS/물리 시험 미실행. 기존 메시지 복사 테스트는 펌웨어 검증이 아니다.
- 남은 항목: (1) 취득/ACTIVE/해제 단계의 정확한 시각과 송신한 허리 필드,
  실측 허리/팔/몸체 자세를 동일 시간축으로 남길 로컬 진단 보완,
  (2) 팔 목표 고정 상태의 제어권 인수와 팔 이동 영향을 분리하는 시험 설계,
  (3) 허리 유지 계약의 오프라인 검증 후 별도 승인된 제한 시험.
  현재 가설은 허리 유지 부재, 균형 제어 반응, 명령 해석 차이이며 아직 확정 아님.
  소스/오프라인 시뮬레이션만으로 기기 내부의 제어권 해석을 증명할 수 없다.

## 기존 허리 유지 코드의 근거 범위 확인

- references/lower_body/g1_upper_body_ab_test.py 전체 루프 확인:
  free는 팔15..28만 설정, hold는 허리12..14를 추가하고 시작 q를 유지,
  offset은 허리 pitch 시작 q에 offset을 더한다. 허리 기본값 kp60/kd1.5는
  argparse 기본값일 뿐 현장 검증값으로 인정하지 않는다. CLI로 변경 가능.
  weight3초 상승/목표5초 보간/50Hz/시간 무제한/Ctrl+C 후2초 해제 구조.
- static_stand의 common.hpp는 허리 kp150/kd4; hybrid_target은 upper_target을
  복사하고 하체 정책 출력만 덮어쓴다. write_cycle에서 허리도 q/kp/kd 적용.
  이는 rt/lowcmd 전체 제어 경로이며 Arm SDK 경로로 게인을 그대로 이식할 근거 아님.
- docs/references/config 검색 및 logs/references 파일명 검색에서
  waist_free/hold A/B 결과 파일은 발견되지 않았다. 9/1 인계에도 코드 읽기만
  수행했다고 기록됨. G1 내부 파일을 조회하거나 실행하지 않았다.
- 결론: 허리 유지 구현의 참고점은 확보했지만 해당 기기의 검증된 Arm SDK
  waist 계약/게인은 미확인. 담당자에게 hold 사용 여부, 실행 인자, 결과 로그,
  waist mode0에서 기존 AI 제어 유지 여부의 근거를 확인해야 한다.
  물리 출력 잠금 유지. 제어 코드/PD 변경 없음.

## 상체 기울어짐 조사: 물리 재시험 보류

- 사용자는 11:24 시험에서 손을 움직일 때 상체가 기울었다고 보고했다.
  first_live hardware_output_authorized=false로 로컬 시험을 잠갔다.
  반복 Y/N 운용 합의와 별개로 이상 동작 원인 확인 전 물리 재시험 보류.
- 중요 정정: 결과 파일명 112408은 동작 시작 시각이 아니다. 결과의 마지막
  송신 시각은 11:24:33.409820. 앞서 11:24:08~17의 거의 정지한 로그를
  근거로 허리 변화가 없다고 설명한 것은 잘못된 시간 구간 선택이었다.
- 저장 전신 로그 g1_live_state_20260907_112323.jsonl에서
  11:24:18.41~35.41 구간 허리 roll/pitch 범위는6.57/4.53도.
  11:24:30 roll1.18/pitch-2.49, 31초3.00/-3.60,
  32초5.04/-6.65, 33초0.86/-2.36도. 취득/제어/해제 시각을
  정확히 구분하는 매 프레임 명령 로그는 없어 인과관계 확정 불가.
- 메시지 구성/복사: 15..28 팔,29 weight. 0..14 q는 매번 실측이며
  mode/kp/kd/dq/tau=0. _apply_frame는 인덱스 그대로35슬롯 복사한다.
  SDK 모양의 가짜 메시지에 기존 비정상 필드를 채운 뒤0/.5/1/0 weight로
  복사 검증7테스트 통과. 실제 DDS 캡처나 펌웨어 해석 검증은 아니다.
- 공식 Python arm7 예제는 양팔14축+허리12/13/14를 arm_joints에 포함하고
  게인을 설정한다. 따라서 현재 non-arm mode/gain0을 '기존 제어기가 허리를
  계속 지탱한다'는 보장으로 해석할 수 없다. gain0이면 반드시 풀린다는
  결론도 아직 확정하지 않는다. 해당 G1 펌웨어의 소유권 의미 확인 필요.
  https://github.com/unitreerobotics/unitree_sdk2_python/blob/master/example/g1/high_level/g1_arm7_sdk_dds_example.py
- references/lower_body/g1_upper_body_ab_test.py는 free/hold/offset으로
  허리 소유권을 비교하는 기존 코드. 읽기만 했으며 실행/게인 이식 안 함.
- 다음: 허리 제어 주체와 mode0/weight 의미를 기존 담당자와 확인하고,
  확인된 계약으로 오프라인 검증 후 별도 물리 승인. PD/IK/허리 제어 변경 없음.
  G1 파일/서비스/네트워크/DDS 실행 없음. 읽기 전용 프리뷰는 사용 가능.

## 실측 프리뷰와 물리 제어 수명 분리

- 사용자: 읽기 전용 경로에서 state/손목 표식 모두 표시 확인.
- STANDARD_MINK은 --external-unity-state로 기존 독립 프리뷰를 사용한다.
  먼저 START_G1_VR_PREVIEW_READ_ONLY 실행 후 실측을 확인하고, 프리뷰는
  유지한 채 Unity Play만 중지한 뒤 STANDARD_MINK 실행/Y/N/READY/Play.
- 실행기는 5009 소유 프로세스가 live_lowstate_mujoco인지 확인하며,
  없으면 물리 실행 전에 차단. 이것은 실측 신선도 보장이 아닌 준비 확인이다.
  어댑터는 직접 LowState 안전 수신/검사를 유지하고 Unity5010 전송만 끈다.
  Gate7 종료/실패 시 독립 프리뷰/카메라는 중단하지 않는다.
- 테스트: core12/entry8 통과. 외부 프리뷰 콜백의 stale 차단과 옵션 전달 확인.
  실제 물리 종료 후 화면 갱신 유지는 미검증. G1/WSL 실행 없음.
  물리 속도/범위/시간 및 충돌 설정 변경 없음.

## 실측 VR 프리뷰 단독 확인 경로

- 최신 물리 시도는 initial arm velocity 5.63deg/s > 5.0 기준으로 중단.
  기준 완화 안 함. 사용자와 합의하여 표시 확인을 물리 실행과 분리.
- tools/START_G1_VR_PREVIEW_READ_ONLY.bat 추가. 기존 VIEW_G1_LIVE_MUJOCO와
  START_G1_CAMERA_TO_UNITY만 호출. IK/모터 publisher/Gate7 시작 없음.
  기존 5008 릴레이/5013 어댑터 및 일부 알려진 물리 프로세스가 있으면 차단.
  이 검사는 모든 외부 제어기를 탐지하는 보장은 아님. 기존 물리 창 정상 종료 필요.
- 사용: Unity Play 중지 -> 위 BAT -> 실측 수신 후 Unity Play.
  실제 상태 lost 해제와 손목 표식 확인. 카메라 창은 종료 시 별도 닫기.
  임계 속도/settle 검사는 이 읽기 전용 경로에 적용하지 않는다.
- 테스트: launcher/display 2개, Unity state bridge 8개 통과.
  소스 경로/임시 display 설정/패킷 테스트만 실행. WSL/로봇/VR 미실행.
  표식 복구 결과는 아직 미확인. 사용자 시험 후 표시 조건 추가 분석.

## 10:49 guarded wait 콜백 누락 수정

- 카메라 표시는 사용자 확인. adapter_104854 로그는 guarded_wait_for_active의
  2인수/3인수 불일치 TypeError로 대기 프리뷰 전송 전에 종료.
- gate7_live_arm_sdk_entry의 래퍼도 on_wait를 받아 원래 wait에 전달하고,
  두 번째 ACTIVE 확인 대기에도 실행한다. ACTIVE 연속성 검사는 유지.
- 테스트: entrypoint 8개, core 10개 통과. 실제 래퍼 함수 AST를 실행하여
  콜백 전달/seed/observe/콜백 실패 차단 검증. 로봇/WSL 미실행.
  실제 Unity 표식 복구는 아직 미확인. 이전 core-only 검증 누락 보완.

## Engage 대기 실측 프리뷰 및 카메라 연결

- 10:45 로그: LowState settled/UDP5013 성공 후 ACTIVE 대기. 종전 코드는
  publisher 생성 후에야 Unity5010 전송을 시작해 hardware 표시의 준비 순서가
  맞지 않았다. 모터 publisher를 먼저 만들지 않고 실측 프리뷰를 먼저 보낸다.
- WaitForFirstActiveMink에 선택적 on_wait 콜백 추가. 대기 중 LowState
  freshness/mode 검사 후 5010 실측 전송. 누락/stale/mode 변화는 차단.
  활성 이후에도 같은 Unity 세션/소켓을 사용. 기존 publisher 사전 검사 유지.
- LIVE_HARDWARE의 Unity/Mink 실행에 --camera 추가. 기존 읽기 전용 카메라
  브리지 사용. 사용자에게 기존 Play/대기 어댑터 종료 요청; 자동 실행 안 함.
- 테스트: gate7_live_arm_sdk 10개 통과(대기 콜백/실패 차단 포함).
  실제 VR 손목 표시/카메라 복구는 미검증. 모터/WSL 실행 없음.

## 반복 시험 승인 방식 및 SettleConfig 수정

- 사용자 요청: 같은 제한의 시험은 파일 재잠금/채팅 승인 대신 매 실행 Y/N.
  STANDARD_MINK wrapper의 자동 재잠금을 제거했다. first_live hardware=true,
  algorithm=false 유지. 0.08rad/s/3도/20초 및 사전 검사/종료 출력 해제 유지.
  일반/visible 프로필 변경 없음. 다른 first-live wrapper는 기존 재잠금 유지.
- 10:38 실행은 SettleConfig.hold 누락으로 LowState 최초 수신 후 종료.
  결과 103902.json: publisher_created=false, published_frames=0.
  collect_settled_snapshot의 freshness 검사에 필요한 hold.lowstate_timeout_s를
  hardware_config로 전달하도록 수정. 검사 생략/timeout 완화 없음.
- Unity hardware 표식은 수신 상태 및 engagement frame을 요구하므로 어댑터
  조기 종료를 먼저 해결해야 한다. 가상손목 표시 복구는 아직 VR에서 미확인.
  Unity 표시 조건을 우회하거나 시뮬레이션 상태로 대체하지 않았다.
- 테스트: first-live 6개 및 Jog 20개 통과. SettleConfig 실제 AST 생성식의
  timeout 전달, 실행기 Y/N 순서 회귀 검사 추가. 물리/WSL 실행 없음.

## 10:36 모드 조회 실행 실패: CRLF 수정

- 검토: launcher_20260907_103608_011531 로그의 STEP2에서 bash
  set pipefail 오류. query_motion_mode_wsl.sh 24줄 전부 CRLF 확인.
  후속 start_gate7_live_arm_sdk_wsl.sh도 29줄 전부 CRLF였다.
- 코드 수정: 위 두 Windows 로컬 파일만 LF/UTF-8 BOM 없음으로 정규화.
  명령 내용/설정값 변경 없음. 기존 *.sh text eol=lf 규칙 유지.
- 테스트: 변환 후 CR 없음 및 줄바꿈 외 내용 보존 확인.
  start_read_only_wsl.sh는 이미 LF. 물리 출력 잠금 false 확인.
  WSL/스크립트/DDS 실행 검증은 하지 않았다.
- 남은 항목: 새 승인 후 다음 실행 결과 확인. 현재 실패는 모드 조회
  이전 shell 초기화 실패이며 G1 모드 이상을 뜻하지 않는다.

## Standard Mink 실행기 콘솔 로그 보완

- 검토: 10:31:21 validate-only 로그는 authorized=true/published_frames=0.
  이후 오류 콘솔은 저장되지 않아 최초 종료 원인은 확정할 수 없다.
  현재 first_live_hardware_output=false 확인. 재승인/재실행하지 않았다.
- 코드 수정: STANDARD_MINK BAT가 run_logged_standard_mink.py를 통해
  자기 --logged 경로를 실행. 부모 실행기의 stdout/stderr를 화면과
  logs/test_results/g1_gate7_standard_mink_launcher_<timestamp>.log에 동시 기록.
  stdin은 콘솔 상속, 줄바꿈 없는 CHOICE 안내도 즉시 전달한다.
  별도 창 프로세스 출력은 이 로그에 포함되지 않는다(기존 adapter 로그 별도).
- 테스트: --self-test로 stdout/stderr/자동 N 선택 안내/종료코드2 저장 확인.
  결과 g1_gate7_logging_self_test_20260907_103355_214332.log.
  실제 키보드 Y/N 및 물리 실행은 미검증. G1/WSL/DDS 실행 없음.
- 남은 항목: 새 승인을 받은 다음 실행에서 첫 실패 원인 확보.
  창 강제 종료 시 로그 꼬리 및 자동 재잠금 보장 불가. 출력 잠금 유지.

## 첫 standard Mink 물리 시험 1회 승인

- 사용자가 지상 Regular/주변 비움/조종기 준비 조건의 0.08rad/s,
  3도/20초 standard Mink 물리 시험 1회를 명시 승인했다.
- first_live_hardware_output만 true로 일시 해제. 알고리즘 config는 false 유지.
  STANDARD_MINK BAT에 성공/실패 반환 후 하드웨어 설정 재잠금을 추가했다.
  창 강제 종료 등으로 반환 경로가 생략되면 자동 재잠금은 보장되지 않는다.
- 에이전트는 WSL/DDS/물리 실행을 하지 않았다. 사용자가 BAT 실행 및 현장
  확인을 진행한다. 시험 결과는 아직 없음. 재시험은 새 승인 필요.

## 제한된 물리 시험 준비: 첫 시험 속도 0.08 rad/s

- 검토: 사용자가 VR 기능 확인 및 G1 실측 MuJoCo/Unity 자세 일치를 확인했다.
  posture 기준 개선 실험은 보류. 이번 승인은 로컬 설정 및 오프라인 검증만이다.
- 코드 수정: first_live_mink_arm_sdk의 근위/손목 속도 상한을 모두
  4.583662361046586 deg/s (=0.08 rad/s)로 변경. 해당 회귀 테스트와
  FIRST_LIVE_TRIAL 안내 문구 갱신. STANDARD_MINK 실행기도 같은 프로필 참조.
  3도/20초/weight1, 가속도/jerk/충돌/IK 비용 유지. 두 출력 잠금 false 유지.
  일반 및 visible-motion 프로필은 변경하지 않았다.
- 테스트: first_live_profile 4개, ruckig_joint_motion_limiter 3개 통과.
  validate-only 통과: logs/test_results/g1_gate7_live_hardware_20260907_101255.json.
  WSL/G1/DDS/publisher/명령 실행 없음.
- 남은 항목: 이 정확한 프로필의 물리 시험은 별도 명시 승인 후 진행.
  오프라인 검증은 실제 추종 성능이나 물리 안전성 검증을 대체하지 않는다.

## Posture 기준 자세 분리 실험

- 검토: 동일 4cm 전진 후 자세에서 local X 35도 회전을 10초간 부드럽게
  증가시키고 10초 유지. 회전 전용 및 위치 [+.03,-.02,+.02]m 동시 이동의
  두 조건, 기준 자세 4종으로 8결과 비교. direct Mink next_q 사용,
  Ruckig 제외. 이전 step 입력 시험과 누적 이동량을 직접 비교하지 않는다.
- 기준: 전진 전 고정 / 전진 후 고정 / 매 단계 현재 q / posture 비용 0.
  마지막은 진단용 제거 조건이며 나머지는 비용 크기를 유지했다.
- 결과: 회전 전용 근위4축 누적 이동 합은 21.68/24.39/4.59/3.53도.
  shoulder yaw 최종 변화는 -16.46/-16.76/-1.07/-0.27도.
  현재 q 기준은 전진 전 고정 대비 누적 이동 약79% 감소.
  위치+회전 근위 누적 이동은 26.12/29.07/17.66/17.05도.
  모든 조건 최종 위치오차 0.60mm 이하, 회전오차 0.03도 이하.
- 해석: 이 조건에서는 고정 posture 기준의 복원 목적이 큰 근위 움직임에
  기여한다. 전진 후 자세로 고정 기준을 옮기는 것만으로는 해결되지 않았다.
  현재 q 기준은 장기 기준 자세 복원이 아닌 국소 변화 억제로 의미가 달라진다.
  posture 제거와 함께 장기 자세 드리프트/특이점/충돌 근처 검증이 필요하다.
- 코드 수정: 제어 코드 및 live/물리 설정 변경 없음. 진단 프로세스 내에서만
  조건 변경. G1/WSL/DDS/소켓 실행 없음. 결과 기록만 추가했다.
- 테스트: 8결과 완전성/유한값, 거부0, 샘플 clearance>=5mm,
  최대 관절속도<=.160001rad/s 확인. 샘플 최소 clearance는35.28mm.
  결과: logs/test_results/posture_reference_20260907.jsonl.
- 남은 항목: 여러 전진 자세와 회전축, 왕복 회전 및 충돌 근처에서 같은
  비교를 반복하고 Ruckig 포함 경로를 별도 검증. 아직 live 후보로 채택하지 않음.

## Posture / damping 분리 실험

- 검토: 동일 4cm 전진 A자세, 같은 posture 기준(전진 전 initial),
  direct Mink next_q 1200회/목표, Ruckig 제외. 기존/손목posture .004/
  근위damping 1.0/둘다/근위고정 참고 5조건 x 회전/위치+회전 2목표.
  기존 손목posture .04 및 근위damping .25의 대조 실험값이며 최적값 아님.
- 결과: 회전 목표의 근위4축 누적이동 합은 순서대로
  71.47/85.20/51.20/65.61/0도. 최종 shoulder yaw 변화는
  -16.46/-1.61/-16.45/-3.96/0도. 최종오차는 모두 1mm/.1도 이내.
  손목posture 감소는 최종 어깨변화를 줄이나 누적이동은 증가했다.
  damping 증가는 누적이동 감소, 최종자세는 거의 동일했다.
- 위치+회전 목표는 원래 손위치에서 [+.03,-.02,+.02]m 추가 이동.
  자유 네 조건 위치오차 .29~.63mm; 근위고정 참고는 40.04mm.
  팔 보정 능력은 두 목표에 한해 유지되었으나 전체 작업공간 증명은 아니다.
- 검증: 10결과 완전성, 샘플 clearance>=5mm/속도<=.160001rad/s,
  거부0 확인. 결과 logs/test_results/posture_damping_20260907.jsonl.
  step입력이므로 이전 ramp 시험의 누적이동과 직접 비교 금지.
- 코드 수정: 없음. 어떤 비용도 live/물리 설정에 채택하지 않았다.
  다음은 자세 기준 유지 비용이 회전 도중 만드는 복원 동작을 따로 조사하고,
  ramp 입력/다른 자세에서 검증해야 한다. 비용만 올리면 해결된다는 결론 아님.

## 4cm 전진 후 손목 회전: 근위 고정 진단

- 검토: 같은 A 전진 1200단계 후 q에서 동일 local X 35도 목표를 설정.
  격리 MuJoCo3.12, 기존 standard Mink 비용/관절/속도/충돌 제한 유지.
  Ruckig를 제외한 진단 IK, 1200번 Plan의 next_q 적용. 35도 step 입력이므로
  이전 10초 ramp 시험의 누적 이동량과 직접 비교하지 않는다.
- 결과: 자유7축 위치 .596mm/회전 .020도, shoulder yaw 최종 변화 -16.459도.
  근위4축 고정 위치 .904mm/회전 .039도, 손목 roll 변화 +34.963도,
  근위 최종 변화는 수치오차 수준(<1e-10도). 두 조건 거부0,
  최종 clearance 각각35.281/40.557mm.
  보조 고정+위치cost0도 .904mm/.039도로 유사했다(진단 프로세스만).
- 해석: 이 자세/회전에서는 1mm/0.1도 이내 해가 손목만으로 가능하다.
  큰 근위 동작은 필수라고 볼 수 없으며 비용/해 선택 영향을 우선 조사한다.
  모든 자세에서 근위 고정이 가능하거나 cost만이 유일 원인이라는 증명은 아니다.
- 코드 수정: 없음. 실제 제어에 고정/비용 변경 적용 안 함. 소켓/SDK/G1 없음.
  현재 위치cost8/회전2/posture.04, 근위damping.25/손목.015, gain.35 확인.
- 다음: posture 기준/관절별 posture 비용과 damping 영향을 따로 비교하되,
  손목만으로 불가능한 목표에서 근위 관절 보정 능력을 유지해야 한다.

## 앞으로 둔 손의 회전 전용 비교

- VIEW_TRAJECTORY_AB 기본 case9/40초: 0~5초 4cm 전진, 20초까지 정지,
  20~30초 손목 local X 35도 회전, 40초까지 유지. 위치 목표는 5초 이후 고정.
- 8cm 조건은 회전 시작 시 미수렴이라 4cm로 교체했다. 4cm 조건은 A/B 모두
  회전 시작 위치5mm/자세2도 기준 통과. 2400단계 계산 완료, 거부0.
- 회전 구간 누적 움직임 SP/SR/SY/elbow: A 4.01/3.75/16.46/9.25도,
  B 6.16/3.75/16.63/14.04도. 종단속도 변경만으로 근위 관절 동작은 줄지 않았다.
  최종 위치오차 둘 다 .60mm, 회전 .02도. B 개선으로 채택하지 않는다.
- 관련 pytest8개 통과. HUD에 회전 구간 누적관절이동과 시작수렴여부 표시.
  물리/live 변경 없음. 결과 logs/experiments/trajectory_ab/latest.json.

## 오프라인 trajectory A/B 구현

- 코드 수정: 별도 compare_mink_trajectory.py에 정지형 A/종단속도 후보 B.
  기존 viewer에 --trajectory-ab 옵션, VIEW_TRAJECTORY_AB.bat 추가.
  live 코드/속도/안전설정 그대로. F8은 동일 시간에서 A/B 전환한다.
- 테스트: 선택 pytest 10 passed. B 최초 계수 .5는 정지 실패로 폐기;
  .1은 정지/bounds 통과했지만 단순 이동 목표 정상속도 .03944rad/s로
  A .04152rad/s보다 느렸다. B를 개선 성공으로 판단하거나 live에 적용하지 않는다.
- 전체 synthetic 10동작 각각 1200단계/20초 계산 및 snapshot 렌더 확인.
  전 동작 성공 판정은 아님: toward-body 양쪽 충돌 HOLD/약105mm 잔차,
  wrist-Z A invalid_velocity 거부가 남는다. 기준 검사 우회 안 함.
  결과 logs/experiments/trajectory_ab/latest.json; 수동 viewer 키 조작 미검증.
- 남은 항목: synthetic 10동작 비교이며 실제 Quest 캡처 비교는 아직 아님.
  자세한 사용/한계는 docs/TRAJECTORY_AB.md. 물리 출력/WSL/DDS 없음.

## 향후 trajectory A/B 기준 보존

- 현재 Mink/Ruckig 관련 6소스 + 09:35 캡처 + Unity CSV를
  logs/experiments/trajectory_ab/baseline_20260907에 복사, 8파일 SHA256 일치 확인.
  독립 실행 패키지가 아니라 비교용 부분 스냅샷이다. 모델/의존성은 포함 안 함.
- A=현재 정지형 Ruckig, B=향후 통과형 후보(미구현), C=추가 Ruckig 없는
  프로젝트 standard Mink 진단 기준. upstream 원본과 같다고 부르지 않는다.
- 같은 입력/초기 자세/제한/비용/dt로 비교하고 시각 전환도 같은 재생 시점을
  유지한다. README에 지표/범위 기록. 이번에 live 코드/물리 설정 변경 없음.
- 후보 구현, A/B 시각 전환 기능과 검증은 아직 남아 있다.

## 추종 감속 원인 재현: 가까운 중간 목표의 정지 조건

- 검토: 09:35 캡처 활성 1916패킷의 trajectory_velocity P95는 모든 축에서
  0.041520372 rad/s. sequence 차이는 모두 1. 송신 timestamp 간격 중앙값
  33.84ms는 출력 패킷 간격이며 제어 loop 주기라고 단정할 수 없다.
- 원인 근거: StandardMinkPlanner horizon=3, DT=1/60, 최대속도 0.16rad/s에서
  단조 최대속도 방향 중간 목표는 현재 q 앞 0.008rad이다. Ruckig limiter는
  target_velocity/acceleration=0이므로 가까운 목표마다 정지 가능하도록 계산한다.
- 테스트: 기존 RuckigJointMotionLimiter를 7축, v=.16/a=.32/j=1.28,
  dt=1/60, 600회 실행. 매번 current+0.008 목표는 정상상태 속도
  0.041520372059rad/s (약 2.38도/s). 같은 제한의 고정 2rad 목표는
  최대 0.16rad/s 도달. 충돌/렌더/네트워크 없이 로그 속도를 재현했다.
- 코드 수정: 없음. 물리/시뮬레이션 설정 변경 없음. 이 시험은 매핑/모든 오차의
  원인을 입증하지 않는다. 느린 실제 loop 영향도 별도 미검증으로 남긴다.
- 다음: 가까운 waypoint를 매번 정지점으로 취급하지 않는 연결 방식을 오프라인
  비교해야 한다. 무조건 horizon/속도 증가나 충돌 검사 생략으로 해결하지 않는다.

## Quest 재시험 09:35 세션 결과

- 검토/분석: live_quest_trace.csv 2755샘플 중 활성/추적/수신 유효 2254.
  평균 위치 오차 4.79cm, P95 12.15cm, 최대 12.69cm.
  회전 평균 23.21도, P95 83.03도, 최대 95.98도. collision_limited=0.
  time_s 23~28 구간 끝 1.79mm/0.24도, 28~33 끝 2.44mm/0.26도.
  이후 회전 동작 구간 오차 증가 뒤 마지막 활성 샘플 1.90mm/2.44도로 감소.
  같은 입력의 A/B가 아니므로 이전 대비 개선율로 해석하지 않는다.
- 복귀: g1_gate7_live_dry_run_20260907_093449.json passed=true,
  피드백 5033프레임, 수신 status accepted=5033/rejected=0.
  event time_s 92.95 intentional_pinch_return -> 94.86 regular_return_complete.
  SDK/DDS/물리 출력 false. 실제 G1 복귀 검증이 아닌 시뮬레이션 결과다.
- 코드 수정: 없음. 카메라 표시 성공 여부는 이번 로컬 결과로 확정 불가.
- 남은 항목: 정지 후 수렴은 확인되지만 동작 중 특히 회전 추종 지연은 남음.
  속도/고정 DT/실제 계산 주기의 영향 분리 필요. G1 물리 출력으로 확대하지 않음.

## 시뮬레이션 복귀/선택 카메라 실행 구성

- 검토: 기본 BAT에 5012 수신만 있고 복귀 계산 dry-run이 없었다.
  기존 dry-run을 재사용하며 물리 adapter는 실행하지 않는다.
- 코드 수정: 기본 simulation/virtual-center 실행은 5008이 비었는지 확인하고
  Gate7 dry-run을 validate-only 후 시작한다. 기존 recording/dry-run wrapper는
  --external-feedback을 넘겨 중복 시작을 막는다. --hardware-display에는
  자동 dry-run을 추가하지 않았다. 카메라는 --camera 명시 시에만 확인/실행.
  camera WSL starter도 CRLF를 LF로 정규화했다. G1 내부 변경 없음.
- 테스트: launcher 선택/기존 dry-run/localhost UDP E2E 27 passed.
  logs/test_results/simulation_return_launcher_20260907.xml.
  localhost 임시 포트만 사용, G1/WSL/SDK 실행 없음. 실제 VR 복귀/PiP 재검증 필요.
- 사용: 기본 START_VR_HAND_TO_MUJOCO.bat은 복귀 포함 시뮬레이션.
  같은 BAT에 --camera를 붙이면 읽기 전용 카메라를 추가한다.
  로그 보존은 tools/START_G1_GATE7_VR_RECORDING.bat --camera 사용.
  이전 MuJoCo/dry-run/하드웨어 mirror를 종료하고 Unity Stop 후 실행한다.
  종료 시 Regular Return 창 Ctrl+C 및 카메라 창 종료가 각각 필요하다.
- 추종 추가 분석: 이전 1845 활성 샘플에서 0.5초 이상 간격의 관절 변위로
  계산한 최대 속도는 축별 약 2.46~2.48도/s였다. 설정 상한 0.16rad/s
  (9.17도/s)와 다르다. 고정 DT 적분과 느린 실제 loop가 원인일 가능성은
  있으나 활성 cycle 로그가 없어 확정하지 않는다. 제한/게인/DT 변경 없음.
  다음 기록은 단순 한 방향 이동 후 손을 정지해 수렴 여부를 확인해야 한다.

## Quest 실사용 추종 분석 (09:21:42 세션)

- 검토: Unity_G1_VR/Logs/live_quest_trace.csv 2405행 및
  rotation_trace_20260907_002142_196_6551682ae9b349e8920ddf4640c646ba.jsonl.
  세션 2c3e1b984da04c8b9fc20355498a52ad. CSV는 다음 실행에서 덮어써진다.
- 코드 수정: 없음. 물리 출력/네트워크/속도/IK/충돌 설정 변경 없음.
- 테스트/분석: tracked + command_valid + backend_recent인 1845샘플,
  time_s 16.520119~67.829758의 한 활성 구간. 위치 오차 평균 8.42cm,
  P95 13.06cm, 최대 16.82cm. 회전 오차 평균 37.32도, P95 81.94도,
  최대 157.59도. collision_limited 589/1845 (31.92%), workspace_limited 0.
  제한 표시 없는 1256샘플도 위치 평균 8.13cm/회전 평균 33.92도.
  sender_delta와 backend_target_delta 차이 norm P95 2.35mm, 최대 15.61mm.
  비동기 샘플이므로 이것을 네트워크 지연이나 패킷 손실률로 해석하지 않는다.
  활성 engagement_revision은 모두 1, anatomical_used는 모두 True.
  기존 rotation analyzer는 2405샘플/81이벤트를 기록했으며 이벤트는 회전
  변화 또는 상태 전환 표시이지 오류 개수가 아니다. 결과:
  logs/test_results/quest_rotation_20260907_092142.analysis.json.
- 남은 항목: 이번 것은 MuJoCo 추종이며 실제 G1 추종 결과가 아니다.
  입력 위치 전달 불일치보다는 수신 목표 이후 추종 오차가 크지만,
  속도 제한/목표 도달 가능성/회전 매핑/충돌 제약 중 원인 분리는 미완료.
  평균은 시간 가중이 아닌 샘플 평균. 최종 inactive 오차 0은 성공 증거 아님.
  status의 pinch_disengaged와 feedback accepted=0 확인: 복귀 피드백 미수신.
  기본 3.12 BAT는 카메라 시작을 건너뛰며 Gate7 dry-run을 시작하지 않으므로
  카메라/Regular 복귀 안내 문구와 실제 단독 실행 구성이 불일치한다.

## R20 전체 저장 궤적 비교

- 검토: 저장 캡처의 segment 2 전체 1756단계(입력 1036, HOLD 360,
  RETURN 360)를 기존 r20_paced_reference_20260907 기준과 비교했다.
  격리 MuJoCo 3.12, horizon=3, 각 조건 3회, warmup=30,
  cache/broadphase/constraint-cache 모두 꺼진 planner-only 조건이다.
- 코드 수정: 없음. 비교군은 별도 Python 프로세스 메모리에서 EvaluateStep의
  새 API 호출 한 곳만 기존 CheckConfiguration + 유효 시 GetClearance로
  교체했다. 저장 소스/운영 설정/원본 캡처는 바꾸지 않았다.
- 테스트: 두 조건 모두 3회 관절값/preview qpos 최대 차이 0,
  accepted lookahead step 수 불일치 0. 평균 계산 시간은 기존 중복 계산
  11.329/11.338/11.308ms, 새 방식 8.024/8.049/8.169ms로 약 29% 감소.
  16.667ms 초과는 기존 2/0/2회, 새 방식 0/1/0회다. 양쪽 보고서는
  DEADLINE_MISSES이며 전체 성공으로 표시하지 않는다.
  결과: logs/test_results/r20_single_clearance_full_20260907.json,
  logs/test_results/r20_double_clearance_control_20260907.json.
- 남은 항목: 하나의 저장 segment와 동일 모델에 대한 결과다. 모든 충돌 상태의
  동등성, 실시간 paced/GPU/VR/물리 동작은 검증하지 않았다. 순차 비교라
  시스템 부하/발열 영향을 완전히 분리하지 못한다. 로봇 이동 속도가 빨라진
  것이 아니라 오프라인 후보 계산 비용이 감소한 것이다. R20 partial 유지.
  검토 coverage 변경 없음. G1/WSL/DDS/네트워크/출력 잠금 변경 없음.

## R20 중복 거리 계산 제거

- 검토: 후보 EvaluateStep의 CheckConfiguration 다음 GetClearance 재계산.
- 코드 수정: CheckConfigurationWithClearance(q)는 (valid, distance_m)를 반환하며
  FK 전 거부는 (False, None). 기존 CheckConfiguration은 bool 반환을 유지한다.
  후보 비교기의 중간 경로 루프만 새 반환값을 사용하고 renderer benchmark의
  검사 카운터도 같은 API를 감싼다. 캐시/임계값/4개 경로 샘플/IK 비용 변경 없음.
- 테스트: 3.11 선택 4파일 87 passed / 10 subtests / GPU smoke 2 skipped.
  격리 3.12 후보 비교 2파일 47 passed / GPU smoke 2 skipped (중복 포함).
  결과 r20_single_clearance_20260907.xml 및 r20_single_clearance_312_20260907.xml.
  합성 12프레임 전후 관절/decision 동일성, 같은 q 재검사 시 재계산,
  invalid q의 FK 전 거부 확인. 이전과 같은 12프레임 측정에서 거리 호출
  336 -> 192 (연속 동일 q 180 -> 36), 모두 accepted. 호출 수 감소이지
  전체 runtime 또는 실제 추종 속도 개선을 의미하지 않는다.
- 남은 항목: 전체 캡처 paced replay deadline 재측정/실제 GPU/VR 검증.
  사용자 CheckConfiguration monkeypatch를 쓰는 후보 테스트/계측은 새 API로
  옮겼다. bool 공개 호출은 유지하지만 새 API 호출을 옛 메서드 spy가 가로채지는 않는다.
  운영 live의 호출 수 최적화를 적용한 것은 아니다. G1/WSL/DDS/출력 잠금 변경 없음.

## R41 저장 캡처 호환성 확인

- 검토: logs/captures 직하 *.jsonl 12개를 전체 패킷 파싱 후 실제
  _decode_capture 로더로 다시 확인했다. 원본 파일 수정/변환 없음.
- 코드 수정: 없음. 저장 파일의 누락된 거리값을 보충하지 않았다.
- 테스트: 데이터 있는 11파일 129938패킷(활성 11184) 파싱 오류 0, 로더 통과.
  20260904_163754는 manifest만 있어 로더 거부; 당시 result에도 accepted=0,
  passed=false가 기록되어 있다. R41 변경으로 새로 생긴 실패가 아니다.
  선택 pytest 28 passed / 35 subtests. 파일별 SHA256/건수는
  logs/test_results/r41_capture_inventory_20260907.csv,
  회귀 결과는 r41_capture_compatibility_20260907.xml.
- 남은 항목: 이 검사는 캡처 해독 호환성이다. 모든 목표의 IK 재계산/시각 재생,
  현재 모델과의 물리 동등성, runtime/실제 G1 안전 검증은 수행하지 않았다.
  다른 폴더의 캡처나 외부 파일까지 검사한 것은 아니다. G1/WSL/DDS/송신 없음.

## R41 공용 ACTIVE 충돌 거리 계약 보완

- 검토: core parser가 active의 누락/null clearance를 허용하고 controller는
  collision_limited=false일 때 계속 추종할 수 있었다. 기존 R41 범위다.
- 코드 수정: active는 유한 JSON 숫자 거리 필수. bool/문자열은 거리 필드에서
  거부한다. direct active sample의 None/비유한/잘못된 타입도 incomplete HOLD.
  inactive 누락/null 및 pinch Regular 복귀 우선순위는 유지한다.
  음수/0 거리의 파싱은 허용하되 기존 안전거리 제한으로 판단한다.
- 테스트: 최초 타입 회귀에서 bool/숫자문자열 통과 2건 확인 후 수정.
  선택 71 tests / 26 subtests 통과. mock relay 송신 전 거부, 거부한 sequence를
  정상 패킷으로 다시 사용 가능, inactive pinch 전달 확인. 실제 소켓 사용 없음.
  결과 logs/test_results/r41_core_clearance_20260907.xml; PROTOCOL 갱신.
- 남은 항목: 모든 과거 캡처 호환성/실제 SDK/물리 검증 미완료.
  거리 없는 과거 ACTIVE 캡처는 더 이상 공용 파서를 통과하지 않으며 임의의
  안전거리를 보충하지 않는다. 가드 없는 직접 main은 이전 배치대로 차단 유지.
  게인/속도/IK/거리 임계값/잠금 변경 없음. G1/WSL/DDS 실행 없음.

## Gate7 가드 없는 직접 실행 차단 (R2/R33/R41)

- 검토: core main 직접 실행 시 supported entry의 최종 충돌/acquisition/
  provenance/health 가드가 설치되지 않은 채 SDK 초기화로 진행할 수 있었다.
- 코드 수정: validate-only 반환 뒤 설치 완료 marker를 엄격한 True로 확인.
  없으면 PermissionError/exit 2와 공식 entry 사용 안내를 기록한다.
  direct pre-publisher-check-only도 차단한다. 공식 WSL starter는 이미 entry를
  사용하며 승인/설정 잠금은 그대로다. 게인/속도/관절 번호/IK 변경 없음.
- 테스트: actual main을 임시 로컬 결과 경로와 SDK-import/socket 차단 mock으로
  실행. direct runtime 거부, validate-only 허용, marker 후 승인 검사 유지 확인.
  9파일 선택 회귀검증 64 passed / 8 subtests / 1 deselected.
  제외한 항목은 실제 localhost UDP를 사용하는 기존 idle-to-active 수신 시험.
  결과 logs/test_results/gate7_guarded_entry_regression_20260907.xml.
- 남은 항목: 물리 검증/전체 프로세스 통합은 미완료. 이는 core parser 자체의
  모든 검증을 통합한 수정이 아니라 지원되지 않는 직접 runtime을 닫은 수정이다.
  Python marker는 악의적인 코드 변경에 대한 보안 경계가 아니다.
  G1/WSL/DDS/네트워크 및 관리자 설정은 실행/변경하지 않았다.

## Gate7 실제 종료 블록 오프라인 실행 검증

- 검토: 기존 R1 finalizer 문자열/AST 연결 검사만으로는 result 갱신 동작을
  증명하지 못했다. gate7_live_arm_sdk.py의 finally 본문을 직접 추출하여 실행한다.
- 코드 수정: test_gate7_release_finalization.py에 실행 테스트 5개 추가.
  release contract는 실제 함수, frame/CRC/publisher/snapshot/clock/socket/path는
  fake다. 운영 제어 코드와 설정 변경 없음. 테스트 내 fake publisher만 사용했다.
- 테스트: 관련 7파일 50 passed / 5 subtests. 결과
  logs/test_results/gate7_extracted_finalizer_20260907.xml.
  정상 해제, 이전 fault 보존, ramp 실패 후 zero tail, 전체/zero-tail 송신 실패,
  snapshot 부재, prerequisites 부재, release 예외, publisher 없는 종료 확인.
  config 전달, zero target 구성, 소켓 close 및 저장 JSON도 검증했다.
- 남은 항목: 전체 main/acquisition 루프와 실제 SDK Write 반환 의미, 물리
  제어권 회수는 검증하지 않았다. AST finalizer 실행은 end-to-end 시험이 아니다.
  G1/Quest/WSL/DDS 실행 없음. Gate6/7 잠금 8개 false 확인.

## HOLD・해제 오프라인 회귀검증

- 검토: shared release, Gate6 fault release, Gate7 finalizer/acquisition,
  final collision guard, LowState health, dry-run state-machine 7개 테스트 파일.
  pinch는 REGULAR_RETURN 요청이며 종료 시 zero-weight release와 다른 경로다.
- 코드 수정: 제어 코드 없음. test_arm_sdk_release_contract.py에 전체 송신 실패와
  ramp 첫 송신 후 LowState 상실을 모사하는 2개 테스트 추가. 기존 R1 검증 보강.
- 테스트: 45 passed. 결과 logs/test_results/hold_release_regression_20260907.xml.
  정상 ramp/zero tail, ramp 실패 뒤 zero 시도, partial/전체 실패 unknown 상태,
  acquisition stale/session 변경, 오래된 LowState 명령 거부, pinch 복귀와
  추적 손실 10초 HOLD 후 복귀를 오프라인으로 확인했다.
  finalizer 통합 검사는 AST 기반; 실제 SDK Write/firmware 제어권 회수 증거가 아니다.
- 남은 항목: 실제 SDK/WSL 연결, runtime base 필드와 중단 시 실제 제어권 반환.
  Gate6/7 authorization 8개 false 확인. G1/WSL/DDS 실행 없음.

## 물리 시험 이후 변경 비교 및 최소 재검증 범위

- 검토: Gate7 실제 움직임 기록 g1_gate7_live_hardware_20260902_173416.json은
  published_frames=1459, release_zero_frames=25, 실측 최대 약 8.91deg지만
  10.08deg 요청의 10deg 제한 초과로 passed=false다. 정상 추종 전체 통과가 아니다.
  9월 4일 TWIST2 시험은 rt/lowcmd 어깨 pitch 부호/응답 시험으로 별도 경로다.
- 비교 기준: 시험 당시 코드 해시는 위 결과에 없어 정확한 버전 동일성은 입증 불가.
  시험 후 첫 저장 스냅샷 bf0b863(9월 3일)과 현재 작업 트리를 비교했다.
  config 및 arm_sdk_hold_contract/arm_sdk_teleop_contract 차이는 없었다.
  오른팔 22..28, 왼팔 measured_hold, 하체/허리 명령 비활성 계약은 유지된다.
  다만 종료 release contract와 supported entry의 acquisition/LowState/
  runtime base/provenance/final command collision 검증은 추가/변경됐다.
  따라서 PD 기본 수치 불변을 실행 전체 동작 불변으로 해석하지 않는다.
- 코드 수정: 없음. Gate7 authorization false 유지. G1/WSL/DDS 실행 없음.
- 테스트: 로컬 로그/문서/소스/git diff 검사만 수행; 이번 물리 시험 없음.
- 남은 항목: 7축 부호 시험 전체 반복을 기본 요구하지 않는다. 먼저 현재 SDK의
  실측/odom 필드 및 provenance를 읽기 전용으로 확인해야 한다(R40/R50).
  그 후 정확한 별도 승인 아래 변경된 HOLD/acquire/release 경로를 제한적으로
  재검증하고, 통과 후 작은 VR 명령 시험으로 진행한다. 실제 remote/deadman/CRC
  호환성과 R24 물리 엔진 경계는 미검증이며 승인만으로 해결되는 항목이 아니다.

## R20 충돌 거리 중복 계산 확인

- 검토: EvaluateStep의 CheckConfiguration 뒤 GetClearance 중복 확인.
  기존 R20 범위이며 새 finding 번호는 만들지 않았다.
- 코드 수정: 없음. 전역 캐시 대신 한 검사에서 bool/거리를 함께 반환하는
  방식을 다음 수정 후보로 기록. 모델 변경과 공개 bool API 호환성에 주의한다.
- 테스트: 오프라인 합성 12프레임, 거리 호출 336회 중 연속 동일 q 180회.
  MuJoCo 3.11.0, 모두 accepted; 관련 pytest 26 passed.
- 남은 항목: 구현과 전후 궤적/실패 경로/3.12 전체 재생 검증은 아직 하지 않음.
  기본 vanilla/물리 경로 변경, G1/WSL/DDS 실행 없음. REVIEW_LATEST 참고.

## 설정 중복 및 동적 참조 점검

- 검토: 338개 색인 범위 내용 해시/설정명 참조 확인. 동일 내용의 Gate7
  first-live/visible-motion Mink 설정은 실행기에서 별도 선택되므로 보존.
  teleimager_real_d435i.yaml은 verify_camera_simulation의 동적 경로 참조 확인.
- 코드 수정: 없음. CLEANUP_20260903.md에 보존 근거 추가; 삭제/이동 없음.
- 테스트: 정적 참조 확인 및 ledger/index --check 통과.
  현재 색인 338개, full_text_review 338개, static_only 0개. 정확성 보증과는 별개다.
- 남은 항목: probe 삭제 결정, 정책 차단된 캐시 정리. 추가 삭제 확정 후보 없음.
  실제 G1/WSL/DDS/카메라 실행은 하지 않았다.

## 미사용 후보 참조 점검

- 검토: 338파일 범위 Python stem 참조 조사와 수동 후보 본문 확인.
  무참조 관리 도구 reconcile은 사용 중. probe_joint_motion은 과거 수동 확인
  종료 이력과 현재 호출 부재를 확인하여 삭제 후보로 기록했으나 미삭제.
- 코드 수정: test_g1_right_arm_jog의 unittest.main 뒤 효과 없는 표현식 2줄 제거.
- 테스트: 20 passed / 3 subtests. 제어/하드웨어 변경 없음.
- 남은 항목: probe 삭제 결정 및 동적/외부 사용 여부. 참조 문자열 조사로
  모든 코드의 미사용 여부를 증명한 것은 아니다. CLEANUP_20260903.md 참고.

## 캐시 삭제 승인 및 도구 차단

- 사용자가 지정된 캐시 9폴더 삭제 승인. 프로젝트 내부 절대 경로 및
  reparse point 부재 확인. 파일 수 338개 확인.
- 삭제 명령이 도구 정책으로 실행 전 차단됨. 삭제 완료 아님; 우회 없음.
- 소스/로그/G1 변경 없음. 승인된 정리 작업은 미완료 상태.

## 정리 후보 점검 (2026-09-07)

- 검토: 루트/tools 실행기 목록, 공용 import와 엔진 경로, 캐시 목록 확인.
  prototype 모듈과 logs 내부 3.12 엔진은 사용 중. 이름만으로 삭제하지 않는다.
- 코드 수정: 없음. 삭제/이동 없음. CLEANUP_20260903.md 상단에 현재 후보 기록.
- 테스트: 정적 참조/목록 점검만 수행. 캐시 후보 9폴더/338파일/약 4.53MiB.
- 남은 항목: 후보 삭제 승인 대기. 전체 소스 미사용 검증 완료 아님.
  증거 로그/캡처/보류 실험 및 G1 내부는 보존한다.

## R20 후보 계산 프로파일 (2026-09-07)

- 검토: 같은 1756스텝 후보 benchmark에 cProfile 적용. 격리 3.12,
  broadphase/constraint-cache 활성화, 30 warmup 포함. 렌더는 미포함.
- 코드 수정: 없음. 비용/충돌 pair/안전거리/주기 유지.
- 테스트: 기준 actual/preview 오차 0, step mismatch 0.
  EvaluateLookahead 누적 15.437s, CheckConfiguration 6.031s,
  solve_ik 5.155s(build_ik 4.410s 포함), CenterRedundancy 2.503s.
  mj_geomDistance 전체 2432556호출/자체 3.231s, daqp_solve_problem 누적 .635s.
  누적 시간은 서로 중첩되므로 합산 금지. 초기 로드/디코딩도 profile에 포함.
  보고서는 DEADLINE_MISSES지만 프로파일러 오버헤드가 있어 성능 승인 자료 아님.
  logs/test_results/r20_candidate_profile_20260907.json 및 .prof.
- 남은 항목: 특정 지연 프레임 원인이나 GPU 지연을 증명하지 않는다.
  다음은 검사 제거가 아닌 동일 상태 중복 계산 재사용 가능성 검토.
  기본 vanilla live와 다른 후보 경로이므로 최적화를 바로 이식하지 않는다.

## R20 후보 재생 3회 반복 (2026-09-07)

- 검토: 같은 격리 3.12/입력/기준으로 1756스텝씩 3회 재생.
- 코드 수정: 없음. 비용/속도/주기/통과 기준 변경 없음.
- 테스트: 전 회차 actual/preview 궤적 일치, 표시 qpos mismatch 0.
  release deadline 초과 6/1/0회. 1회차 frame 13,100,146,148,978,1285;
  2회차 1188; 반복되는 동일 프레임 없음. 계산 work P95 11.799/10.795/10.599ms.
  표시 1755/1756/1462프레임, age P95 6.136/5.815/6.780ms.
  3회차는 표시 age deadline 초과 57회로 계산 통과만으로 전체 통과 아님.
  최종 DEADLINE_MISSES; logs/test_results/r20_paced_render_repeat3_20260907.json.
- 남은 항목: 간헐 지연 원인 미확정. 특정 자세의 결정적 실패 증거는 없으나
  OS/GPU 원인으로 단정하지 않는다. 후보 경로의 실시간 성능 미달은 유지.
  반복 측정만 늘려 PASS를 고르지 말고, 후속 작업은 구간별 프로파일링 또는
  다른 미해결 source finding으로 이동. 기본 vanilla/VR/G1 검증 아님.

## R20 렌더 지연 분리 시험 (2026-09-07)

- 검토: 동일 격리 3.12에서 단독 render, 제한 스레드 full replay,
  기본 환경 full replay를 순차 실행했다. 전체 입력은 이전과 동일 1756스텝.
- 코드 수정: 없음. OPENBLAS_NUM_THREADS/OMP_NUM_THREADS/MKL_NUM_THREADS=1은
  단일 비교 프로세스에서만 적용. 기본 재시험 환경은 세 변수 모두 미설정 확인.
- 테스트: 실제 renderer 3.12 smoke 2 passed, 표시 age P95 7.721ms.
  제한 스레드: 1756/1756 표시, age P95 6.830ms, release deadline 초과 3회.
  기본 재시험: 1756/1756 표시, age P95 5.936ms, deadline 초과 1회.
  두 전체 재생 모두 궤적/표시 관절값 오차 0, 최종 DEADLINE_MISSES.
  앞선 130ms P95는 재현되지 않았으므로 thread 경합 원인으로 확정하지 않는다.
  결과 logs/test_results/r20_render_312_isolation.json 및 .xml,
  r20_paced_render_singlethread_20260907.json,
  r20_paced_render_default_repeat_20260907.json.
- 남은 항목: 부하/스케줄링 원인 미확정, 드문 deadline 초과 측정 필요.
  이 결과만으로 런처 환경/제어 주기 변경하지 말 것. 기본 vanilla 및 장치 검증 아님.

## R20 전체 후보 IK/렌더 재생 (2026-09-07)

- 검토: 과거 3.12 보고서와 캡처/엔진은 같지만 XML 해시가 달라 재사용 거부.
  현재 모델로 segment 2, limit_avoidance, horizon 3 기준을 다시 생성했다.
- 코드 수정: 없음. 격리 MuJoCo 3.12, 현재 비용/속도 유지. 기본 vanilla
  live 경로가 아니라 후보 진단 경로임을 구분한다.
- 테스트: 실제 기록 522패킷에 hold/return을 더한 1756스텝, 별도 renderer,
  640x480, 1회. actual/preview qpos 오차 0, accepted step mismatch 0.
  계산 work P95 12.713ms; release-to-finish 16.667ms 초과 1회(16.845ms).
  renderer 549프레임, 중간 표시 1207스텝 생략, qpos mismatch 0.
  source-age-finish P95 130.094ms, 최대 244.935ms; 최종 DEADLINE_MISSES.
  화면 PNG 확인. 실행 완료를 성능 통과로 해석하지 않는다.
  logs/test_results/r20_paced_reference_20260907.json 및 대응 trace,
  logs/test_results/r20_paced_render_20260907.json 및 r1_s*.png.
- 남은 항목: 렌더 지연 원인 분리/재측정. 1회 결과이고 스케줄링/GPU 원인
  확정 아님. 기본 vanilla 성능, VR/물리 검증 아님. G1/WSL/DDS 실행 없음.

## R20 실제 렌더 프로세스 검증 (2026-09-07)

- 검토: 실제 Windows spawn 시험에서 startup 실패 뒤 Close의 poll이
  BrokenPipeError를 발생시켜 원래 오류를 가렸다. 기존 렌더 오류 처리 범위.
- 코드 수정: offline_render_worker.Close에서 poll도 EOF/OSError 보호 범위에
  포함하여 join/종료 처리를 계속한다. IK/물리 경로 변경 없음.
- 테스트: 명시적 G1_TEST_REAL_RENDERER=1로 실제 GPU/프로세스 검사 포함
  187 passed. 정상 60프레임, qpos mismatch 0, skip 0, 변화 59프레임.
  startup 오류 뒤 자식 프로세스 잔류 없음. 화면 PNG 직접 확인.
  결과: logs/test_results/r20_real_render_process.xml,
  logs/test_results/r20_render_smoke/result.json 및 frame_s*.png.
  보관 JSON의 screenshots는 원래 pytest 임시 경로이며 PNG는 같은 보관 폴더에 복사했다.
- 남은 항목: 30ms 간격 합성 관절 입력/640x480의 짧은 렌더 시험이다.
  전체 IK/60Hz 실시간 성능, VR, WSL/DDS/G1 검증을 의미하지 않는다.

## R20 렌더 재생 실패 경계 (2026-09-07)

- 검토: 렌더 루프 내부에는 예외 보고가 있었으나 모델 준비/로드와 종료 오류는
  최종 결과 없이 끝날 수 있었다. 기존 R20 범위.
- 코드 수정: CLI 경계에서 예상 오류를 ERROR/종료 1로 저장하고 조치 안내.
  잘못된 구간 명시 검사. 종료 실패 시 동일 renderer.Close 중복 호출 방지.
  실패 최종 보고서는 간단한 오류 기록이며 부분 이미지/중간 결과는 완료 증거가 아니다.
- 테스트: 185 passed; load/startup/run/close 실패 주입 및 임시 XML 정리 확인.
  실제 missing-reference CLI 종료 1 및 ERROR 저장, Python compile 통과.
  logs/test_results/r20_render_failure_boundary.xml,
  logs/test_results/r20_render_missing_reference.json.
- 남은 항목: 실제 GPU/별도 worker 전체 재생 성능 통합 검증 및 다른 진단 CLI.
  이번 자원 정리 검사는 mock renderer 기준이다. IK/물리/WSL/DDS 변경 없음.

## R20 후보 벤치마크 실패 처리 (2026-09-07)

- 검토: benchmark_mink_candidate 기준/구간/계산 예외가 보고서 없이 종료했다.
  기존 R20의 진단 결과 계약 범위를 보완했다.
- 코드 수정: RunReport 호출 경계에서 예상 예외를 FAIL/종료 1로 저장.
  요청 구간 부족을 명시적으로 검사하고 저장 실패 시 stale 경고 출력.
  기존 시간/궤적 판정, 후보 알고리즘, IK 및 물리 경로는 변경하지 않았다.
- 테스트: 183 passed. 실제 missing-reference CLI 종료 1 및 FAIL 저장.
  logs/test_results/r20_candidate_failure_boundary.xml,
  logs/test_results/r20_candidate_missing_reference.json.
- 남은 항목: 전체 성능 측정을 재실행한 것은 아니다. 다른 R20 진단 CLI와
  렌더 통합 검증은 남아 있다. 장치/WSL/DDS/G1 실행 없음.

## R20 복귀 진단 실패 처리 (2026-09-07)

- 검토: 두 번째 연동 구간 직접 참조 및 기준 파일/모델/계산 예외는
  FAIL 보고서를 남기지 않았다. 기존 R20 범위를 보완했다.
- 코드 수정: RunInspection CLI 경계에서 예상 예외를 FAIL/종료 1로 보고.
  두 번째 구간 부족을 명시적으로 검사. 저장 실패 시 이전 결과 사용 금지
  안내. 정상 입력의 계산/판정과 IK/물리 경로는 변경하지 않았다.
- 테스트: 178 passed / 4 subtests; 실제 누락 기준 파일 CLI 종료 1 및 FAIL.
  결과: logs/test_results/r20_return_failure_boundary.xml,
  logs/test_results/r20_return_missing_reference.json.
- 남은 항목: 다른 R20 CLI의 통합/예외 검증. 이번에는 전체 복귀 렌더 실행이
  아니라 단위/계약 및 오류 CLI 검증이다. WSL/DDS/G1 실행 없음.

## R20 도달 진단 계산 예외 보고

- 검토: decode/FK 불일치는 FAIL을 저장했지만 모델/계산 예외는 이전 보고서를
  남긴 채 종료할 수 있었다. 기존 R20 범위이며 새 finding은 만들지 않았다.
- 코드 수정: RunDiagnosis 호출 경계에서 예상되는 모델/계산/입출력 예외를
  FAIL 보고서와 종료 코드 1로 변환한다. 보고서 저장 실패 시 저장 성공을
  출력하지 않고 이전 보고서를 사용하지 말라는 안내와 원래 오류를 출력한다.
  정상 계산, REVIEW_REQUIRED/3 판정, IK 및 물리 경로 변경 없음.
- 테스트: 172 passed / 2 subtests. 모델 격리 AST 검사를 새 함수 위치로 갱신.
  실제 누락 캡처 CLI도 종료 1 및 FAIL 파일 생성 확인.
  logs/test_results/r20_diagnostic_failure_boundary.xml 및
  r20_missing_capture_failure.json. 장치/WSL/DDS 실행 없음.
- 남은 항목: 다른 R20 진단 CLI의 오류 처리/통합 검증. 저장 권한이 없으면
  기존 파일을 무효화할 수 없으므로 종료 코드와 콘솔 경고를 확인해야 한다.


## R24 로컬 기본 엔진 거리 회귀 대응

- 검토: 설치된 MuJoCo 3.11에서 wrist-roll 거리 회귀 실패 재현.
  -133.2 mm 비정상 거리값이며 실제 침투 판정 근거는 아니다.
- 코드 수정: START_VR_HAND_TO_MUJOCO 로컬 공통 루프 기본 엔진만
  격리 3.12로 연결. --mujoco311 진단 선택 추가. 물리/이전 prototype은 유지.
  IK 비용, gain, 속도, 충돌 거리 설정 변경 없음.
- 테스트: 3.11 회귀 1 failed/4 passed/2 subtests;
  r24_isolated_engine_recheck.xml: 38 passed/3 subtests;
  r24_local_default_selection.xml: 38 passed. 각 묶음은 중복 포함.
  결과는 logs/test_results 아래. Unity/WSL/DDS/G1 실행 없음.
- 남은 항목: VR 착용 확인, R24 다른 회귀 및 물리/전역 엔진 검증.
  아래 과거의 '3.12는 전용 BAT만' 설명보다 이 항목이 우선한다.

## R20 실제 캡처 도달 진단 및 실패 저장

- 검토: 실제 캡처 CLI 실행. decode/FK 불일치가 보고서 없이 끝나는 문제를 R20으로 처리.
- 코드 수정: decode 오류/활성 구간 없음/FK 불일치는 FAIL JSON과 조치 문구,
  exit 1. 정상 분석은 REVIEW_REQUIRED/exit 3 유지. 렌더 진단의 RunReplay
  반환 전달 구조에 맞춰 기존 exit 테스트 수정. 제어 코드 변경 없음.
- 테스트: 99 passed, 2 subtests passed; Python 3개 compile 통과.
  g1_mink_capture_20260904_164644.jsonl의 1개 구간/1523 active packets 분석,
  subprocess returncode 3 확인. 상한 밖 패킷 0은 도달 가능 승인 아님.
  결과 logs/test_results/r20_recorded_reach_actual.json 및 r20_reach_failure_report.xml.
- 남은 항목: 다른 diagnostic 전체 CLI, 모델 로드/solver/출력 저장 오류 등
  기타 예외 처리. R20 전체 완료 아님. G1/WSL/DDS/VR 실행 없음.
  delta/ledger/CODE_INDEX 갱신.

## R63 TeleImager 머리 스트림 일치 검사

- 검토: 두 YAML은 현재 JSON profile과 640x480/30fps로 일치하지만 drift 검사가 없었음.
- 코드 수정: camera_factory에 순수 설정 비교 추가. 기존 verify_camera_simulation에
  --config-only 추가; YAML safe_load와 실패 보고서/exit 1. 기존 렌더 모드 유지.
  profile을 기준으로 head shape/fps/binocular/type만 검사하며 자동 변경하지 않는다.
- 테스트: 97 passed, 96 subtests passed; Python 3개 compile 통과.
  실제 config-only CLI PASS. 실패 YAML/불일치 보고서 확인. 카메라/WSL/DDS/G1 실행 없음.
  Windows Python 3.11에 PyYAML 6.0.3 설치; WSL/G1 환경 변경 없음.
  결과 logs/test_results/r63_camera_profile_alignment.xml 및 logs/camera/camera_config_validation.json.
- 남은 항목: TeleImager 전체 구성, runtime.head_camera_fps 역할과 실제 프레임 속도 검증.
  R63 전체 완료 아님. delta/ledger/index 갱신 (338/338).

## R63 TCP 카메라 기본 주기 중복 제거

- 검토: TCP bridge/replay/WSL starter에 20fps가 중복. camera_profile의 30fps는
  별도 source adapter 설정이며 무조건 동일하게 변경할 값은 아니다.
- 코드 수정: replay는 bridge.DEFAULT_FPS import, starter의 --fps 20 제거.
  실제 기본값 20.0 및 CLI override 유지. 카메라 설정 위치를 CAMERA_SIMULATION_GUIDE에 설명.
- 테스트: 17 passed, 16 subtests passed; Python 2개 compile 통과.
  기본 20/override 15/런처 중복 없음 검사. WSL starter 실행하지 않음.
  결과 logs/test_results/r63_camera_rate_owner.xml. SDK/DDS/카메라 접속 없음.
- 남은 항목: TeleImager/source adapter와 runtime config 전체 설정 관계,
  실제 카메라/Unity 전달 속도 확인. R63 전체 완료가 아닌 TCP 범위 정리.
  review delta/ledger/CODE_INDEX 갱신.

## R53 적용 후 관절 제한과 엔진 확인

- 검토: operational joint limits는 XML 로드 뒤 적용되므로 XML 해시에 없다.
- 코드 수정: 적용 후 jnt_type/jnt_limited/jnt_range를 해시하고 MuJoCo 버전을
  prototype/공통 live 패킷과 replay 모델 metadata에 추가. 새 필드가 다른
  기록은 재생 전에 거부, 과거 기록은 joint limits/engine unverified 표시.
  실제 관절 제한값과 IK/속도/출력 잠금은 변경하지 않았다.
- 테스트: 99 passed, 17 subtests passed; Python 7개 compile 통과.
  limits 변경, engine 불일치, legacy, 잘못된 필드, 적용 후 기록 순서 확인.
  테스트는 실제 모델과 main 일부 문장 추출/대역을 사용하며 장비 실행은 없음.
  결과 logs/test_results/r53_runtime_identity.xml.
- 남은 항목: 충돌 mask 등 다른 모델 변경, solver/cost/velocity 설정과
  다른 replay 경로. 버전 문자열 일치는 동일 바이너리/동역학 보장이 아니다.
  R53 partial 유지. delta/ledger/CODE_INDEX 갱신 (338/338).

## R53 명시적 외부 자산 해시

- 검토: XML hash는 mesh/texture 파일 내용 변경을 검출하지 못했다.
- 코드 수정: 생성된 flat MJCF의 mesh/hfield/texture 명시적 file 속성들을
  해시로 묶어 model_assets_sha256에 기록. 로드 전후 해시가 다르면 중단한다.
  include 등 지원하지 않는 파일 의존성은 누락시키지 않고 거부한다.
  decoder는 선택적 자산 해시 형식을 검사하고 replay는 불일치를 거부한다.
  과거 XML-only 기록은 assets unverified 표시. IK/속도/출력 설정 변경 없음.
- 테스트: 93 passed, 9 subtests passed; Python 5개 compile 통과.
  내용 변경/누락 파일/미지원 include/로드 전후 변경/불일치/legacy 확인.
  logs/test_results/r53_assets.xml. 전체 실사용 캡처나 장비 런타임 검증 아님.
- 남은 항목: runtime 모델 설정, 엔진 차이, 다른 replay 경로.
  전후 해시는 동시 파일 교체에 대한 원자적 snapshot 보장이 아니다.
  현재 지원은 명시적 자산 파일이며 일반 MJCF/plugin 의존성 추적기가 아니다.
  R53 부분 수정 유지. ledger/index 갱신, bounded coverage 338/338 유지.
- 경로 해석 참고: https://mujoco.readthedocs.io/en/3.0.1/XMLreference.html
  compiler meshdir/texturedir/assetdir/strippath 규칙.

## R53 prototype 송신 XML 메타데이터

- 검토: prototype main은 격리 모델을 사용하지만 패킷에 모델 해시가 없었다.
- 코드 수정: 실제 로드 모델과 metadata를 함께 받고 송신 직전 패킷에 추가.
  기존 _state_packet API, 관절값, IK, 속도, 출력 설정은 유지한다.
- 테스트: model isolation + standard live 81 passed; Python 2개 compile 통과.
  기존 AST 로더 테스트 대역에 새 함수를 등록했다. 실제 생성 모델과 패킷을
  사용하되 main의 해당 문장만 추출 실행하고 송신은 대역으로 검사했다.
  전체 prototype main/Unity/WSL/DDS/G1 실행은 하지 않았다.
  결과 logs/test_results/r53_prototype_metadata.xml.
- 남은 항목: 외부 자산 bytes, runtime 설정 binding과 다른 재생 경로.
  R53은 부분 수정. source_checks delta 및 ledger/CODE_INDEX 갱신.

## R53 재생 XML 일치 검사

- 검토: capture decoder는 모델 해시를 보존하지만 MuJoCo replay가 모델과
  대조하지 않음. 기존 R53 범위에서 처리.
- 코드 수정: LoadModel의 기존 3개 반환값 유지, include_metadata 선택 시
  실제 생성 XML 메타데이터 추가 반환. replay는 재생 구간의 기록 해시가
  다르면 pose 적용/뷰어 시작 전에 거부. legacy/mixed 기록은 UNVERIFIED 경고.
  장면 표시 옵션이 달라도 XML이 달라질 수 있으므로 일치 옵션이 필요하다.
- 테스트: model isolation 56 passed; 변경 Python 3개 compile 통과.
  일치/불일치/legacy/mixed main 검증은 합성 decoder 입력과 실제 모델을 사용.
  결과 logs/test_results/r53_replay_model_identity.xml. 뷰어/장비 실행 없음.
- 남은 항목: 외부 asset bytes, runtime 설정, prototype 송신 메타데이터 및
  다른 재생 경로. R53 부분 수정 유지. XML MATCH ONLY는 완전한 모델 동등성 아님.
  source_checks delta, canonical ledger, CODE_INDEX 갱신; scoped coverage 338/338 유지.

## 기본 Mink 회귀 확인

- 검토: 새 IK 개선 대신 기본 경로 안정화 진행. 일반 QP, 입력 상태 전이,
  피드백 수신, 기존 공개 심볼, 궤적 제한과 비용 계약 테스트를 선택했다.
- 코드 수정: 없음. 선택한 검사에서 실패가 없었으며 비용이나 안전 제한을
  더 조정하지 않았다.
- 테스트: 7개 테스트 파일에서 50 passed, 11 subtests passed (11.22s).
  결과: logs/test_results/mink_baseline_regression.xml.
  피드백 수신 테스트는 Windows localhost의 임시 UDP 포트만 사용했다.
  Unity, G1, WSL, DDS, 물리 출력은 실행하지 않았다.
- 남은 항목: 아래 VR 확인은 자동 검사로 대체되지 않는다. 일반 QP와 이후
  경로 검사/궤적 제한을 구분해 실패 지점을 판단해야 한다.

### 다음 사용자 확인

START_VR_HAND_TO_MUJOCO.bat 로컬 기본 경로에서 같은 세션으로 확인한다.
물리 런처는 사용하지 않는다.

1. engage 후 손을 고정하고, 회전 없이 작은 위치 이동 후 멈춘다.
2. 위치를 최대한 유지하며 손목을 회전하고 멈춘다.
3. 위치와 회전을 함께 천천히 바꾼다.
4. 엄지-검지 pinch 해제와 재engage 후 목표가 튀는지 확인한다.

빠르게 움직이는 동안의 지연과, 손을 멈춘 뒤에도 남는 오차를 구분한다.
어색함/정지가 보인 동작과 시각을 기록해 해당 로그 구간을 확인한다.
이번 통과 결과를 모든 자세의 도달/충돌 회피 성공으로 해석하지 않는다.

## 로컬 Mink 6D 기준선 선택

- 검토: 공통 루프의 StandardMinkPlanner는 일반 6D QP와 기존 안전 검사를
  사용한다. upstream 예제를 그대로 실행하는 방식은 아니다.
- 코드 수정: START_VR_HAND_TO_MUJOCO.bat 로컬 기본을 vanilla로 변경.
  --hierarchical로 비교 가능. 시각 비교 도구도 Mink 6D부터 표시한다.
  hardware-display 및 Python 직접 실행 기본은 hierarchical 유지.
  비용/속도/충돌 프로파일/물리 출력 잠금은 변경하지 않았다.
- 테스트: standard live + visual comparison 29 passed; 수정 Python compile 통과.
  BAT 선택 테스트는 변수 선언부만 실행하며 런타임을 시작하지 않았다.
- 남은 항목: VR 체감 확인. 이번 작업에서 Unity/WSL/DDS/G1을 실행하지 않았다.

## IK 비교 velocity reject 종료 수정

- 사용자 latest.json: inspection sweep / Standard Mink returned invalid velocity.
- 재현: 약 10.2667s에서 cap excess 3.93e-5 rad/s. 이전 짧은 smoke로 놓침.
- 비교 도구만 invalid velocity를 적분하지 않고 이전 q 유지; rejected/status 표시.
  검사 허용오차/IK 비용/속도/충돌 제한은 변경하지 않음.
- 단위 테스트 5 passed. 복합 4종 각1200프레임 완주, inspection sweep만 1 reject.
  결과 logs/ik_visual_comparison/composite_regression.json. 짧은 viewer 재실행도 통과.
- reject가 있는 경로는 순수 direct QP 성공으로 해석하지 않는다. 물리 실행 없음.

## IK 시각 비교 복합 동작

- 기본 시작을 3D 8자로 변경. 뻗기+회전, 점검 스캔, 고정 위치 다축 회전 추가.
- 두 IK에 동일한 wrist-yaw 목표 입력; 기존 고정 dt/비용/속도/충돌 제한 유지.
- HUD에 근위 4축/손목 3축 누적 절대 관절 이동량 표시. 우월성 지표로 단정하지 않음.
- 합성 목표이며 사람 동작 기록이 아님. 전체 경로 실기 검증/도달 보장 없음.

## IK 비교 사전 계산 재생 / 사용자 배속

- 이전 40/100 deg/s 및 8초 주기 변경 취소. BuildPlanner 기본 시그니처 복원.
- 각 동작을 고정 dt로 20초 계산해 메모리에 보관; 표시만 wall-time 배속 적용.
- BAT에서 0.1~16배 입력(기본4), F11로 .25/.5/1/2/4/8 순환.
- F10 캐시 재생 시작, F9 다음 동작은 처음에만 계산. 끝에서는 정지.
- pytest 3 passed: 원래 속도 caps, 재생 중 Step 미호출, 캐시/직접 계산 q 동일성.
- 실제 G1/VR 실행 없음. 기본 길이의 전체 6개 동작 성능 검증은 별도.

## IK 비교 뷰어 2배 재생

- 사용자 요청으로 viewer 기본 playback-speed=2. 고정 dt Step을 표시당 두 번 수행.
- IK/관절 제한/실제 G1 경로는 불변. headless 프레임 수 불변.
- 1~4배 CLI 선택 가능. 계산 처리량에 따라 실제 배속은 낮아질 수 있음.

## IK 비교 뷰어 단축키 충돌 수정

- F8 비교 전환 / F9 다음 동작 / F10 재시작 / F12 일시정지.
- 기존 1/2/N/R/Space 처리 제거; Esc 종료 오안내 제거. BAT/HUD/설명서 동기화.
- test_ik_visual_comparison.py 2 passed. 실제 키보드 입력은 사용자 재확인 필요.
- IK/속도/충돌 설정 변경 없음.

## R53 송신 모델 정보 캡처

- 검토: recorder에서 별도 생성한 모델은 송신 모델의 증거가 될 수 없음.
- 코드 수정: virtual-center/vanilla 선택 진입점이 실제 loader metadata를 패킷에 추가.
  recorder는 기존 base64 원문 저장을 유지. decoder는 hash 형식과 세션 내 불변성 검사.
  과거 metadata 없는 캡처는 읽기 허용; 과거 모델 동일성은 보장하지 않는다.
- 테스트: r53_capture_identity_20260906.xml 71 passed/15 subtests; 필터 제외 1건은
  r53_capture_identity_remaining_20260906.xml에서 별도 검사. 소켓/뷰어 대역 송신 및 합성 캡처.
- 남은 항목: 재생 모델과의 자동 대조, 외부 asset bytes, prototype 직접 송신 경로.
  XML hash는 runtime limit/asset bytes를 포함하지 않는다. G1/VR 미실행.

## R53 Jog 모델 provenance 연결

- 검토: 허가가 공유 XML을 해시하지만 검사기는 임시 XML을 로드하는 불일치.
- 코드 수정: CollisionPathValidator.model_metadata를 허가 생성/실행 검증에 전달.
  model_binding 필드 추가; 구형 허가는 재생성 필요. 모델 생성/제한 소스도 해시에 포함.
  entry의 write_json 교체는 finally에서 복원. 제어 수치/물리 출력 잠금 변경 없음.
- 테스트: r53_jog_model_20260906.xml 57 passed, r53_jog_entry_20260906.xml 18 passed.
  공유 XML 부재/모델 불일치/구형 허가 거부 확인. Python compile 통과.
- 남은 항목: 외부 mesh/texture bytes와 캡처 당시 모델 binding, 실제 G1 검증.
  이 결과는 물리 실행 승인이 아니다. publisher/WSL/G1 미실행.

## R53 live 모델 로드 격리

- 검토: prototype/virtual-center main의 공유 XML 생성과 로드 확인.
- 코드 수정: LoadMinkModel 사용. 기존 생성 helper의 공개 호출은 유지.
  라이브 실행은 공유 XML을 더 이상 갱신하지 않는다. IK/task/제한은 불변.
- 테스트: r53_live_model_20260906.xml, 71 passed/10 subtests passed. 모델 블록과 소켓/뷰어 대역 main 검사.
  이전 생성 mock이 새 loader를 방해한 실패를 수정하고 재실행.
- 남은 항목: right_arm_jog_safety_guard의 GENERATED_MODEL_PATH 해시는 여전히
  공유 파일을 참조한다. 이를 실제 validator 모델과 연결하기 전 물리 경로 완료 아님.
  캡처 당시 모델/asset binding 및 실제 Unity/VR 검증도 미완료.

## R53 실제 offline renderer smoke 검증

- 검토: 임시 XML을 실제 spawned ProcessRenderer에 전달하는 경로 확인.
- 코드 수정: 없음. 문서/검증 기록만 갱신.
- 테스트: 640x480 20프레임, 누락/관절값 불일치 0. 실제 이미지 육안 확인.
  자식 종료/임시 XML 삭제/공유 XML 불변 확인.
  logs/test_results/r53_render_smoke_20260906/result.json.
  첫 stdin 실행은 Windows spawn의 <stdin> 경로 오류로 실패; -c 실행으로 재검증 통과.
- 남은 항목: 정지 q와 이동 마커의 짧은 smoke이며 전체 IK/장시간 부하 검증 아님.
  live main과 캡처 모델/asset binding은 여전히 미완료. G1/DDS 미실행.

## R53 rendered replay 모델 수명 수정

- 검토: 부모 LoadReplay와 ProcessRenderer가 공유 XML에 의존. 기존 R53.
- 코드 수정: main의 임시 XML을 RunReplay 종료까지 유지하고 자식에도 동일 경로 전달.
  기존 LoadReplay 3인자 호출은 독립 모델을 생성. IK/제한/렌더 알고리즘 변경 없음.
- 테스트: r53_render_reader_20260906.xml, 65 passed. 실제 모델 로드 두 경로와
  렌더러 대역의 정상/초기화 실패/재생 실패 파일 수명 확인. GPU/spawn 실검증 아님.
- 남은 항목: 실제 렌더 재생, live main, 캡처 모델/asset binding. R53 partial.

## R53 candidate benchmark reader 수정

- 검토: benchmark_mink_candidate의 공유 XML 로드/해시 의존 확인. 기존 R53.
- 코드 수정: 현재 소스 격리 모델과 metadata 사용. planner/속도/충돌 설정 불변.
- 테스트: r53_candidate_reader_20260906.xml, 60 passed. 캡처/모델/엔진/horizon
  불일치 중단 및 결과 저장 검사. main의 RunBenchmark는 대체; 전체 성능 재측정 아님.
- 남은 항목: rendered replay의 자식 프로세스 XML 수명, live main, 캡처 모델 binding.
  장비/네트워크 실행 없음. R53 partial 유지.

## R53 return inspection reader 수정

- 검토: 공유 XML 의존이 남은 inspect_feasible_target_return 확인. 기존 R53.
- 코드 수정: 격리 모델/실제 XML 해시 사용. 기준 해시 불일치 중단 유지.
- 테스트: r53_return_reader_20260906.xml, 37 passed. main 저장/불일치 검사 포함;
  전체 재생/렌더링 및 장비 실행은 제외.
- 남은 항목: benchmark reader/live main/캡처 모델 binding; R53 partial 유지.
  전체 검토 대상 338개 완료는 수정 완료를 뜻하지 않는다.

## R53 임시 모델 보고서 해시 수정

- 검토: 직전 reader 분리 후 세 보고서가 공유 XML 해시를 계속 기록하는 누락 확인.
- 코드 수정: LoadMinkModelWithMetadata가 실제 생성/로드 XML 해시 제공.
  audit_wrist_target_mapping/compare_mink_step_acceptance/distance_invariance 연결.
  삭제된 임시 XML 경로는 null. 외부 자산/실행 중 제한은 해시 범위 밖.
- 테스트: 격리/step acceptance/distance invariance 69 passed.
  r53_model_hash_20260906.xml. 실제 장비/네트워크 미실행.
- 남은 항목: 라이브 main/기타 reader/캡처 당시 모델 binding. R53 완료 아님.

## R53 backend 모델 reader 독립화

- 검토: backend 진단 10개가 기존 DEMO_XML을 읽어 라이브 생성 이력에 의존.
- 코드 수정: base.LoadMinkModel 공통 임시 생성/로드 helper와 reader 10개 연결.
  operational limits는 기존 호출부에서 그대로 적용. 라이브 main은 아직 미변경.
- 테스트: 격리/가시성/reach 41 passed. r53_diagnostic_readers_20260906.xml.
  reader 모델 대입 블록 검사와 실제 loader 모델 배열/정리 검사. 전체 CLI 미실행.
- 남은 항목: 과거 캡처 모델 binding, 다른 reader 및 라이브 main. 장비 실행 없음.

## R53 캡처 파일 충돌 방지

- 검토: 라이브 XML은 일부 offline reader의 입력. 캡처 manifest에는 XML binding 없음.
  라이브 모델 경로만 변경하면 stale reader 문제가 있어 변경 보류.
- 코드 수정: gate7_mink_capture 자동 이름 UUID, 기존 capture/result 사전 거부,
  exclusive create로 검사 이후 파일 생성 경쟁도 덮어쓰기 차단.
- 테스트: fake socket/clock으로 6 passed. r53_capture_outputs_20260906.xml.
- 남은 항목: 라이브 모델 및 reader/provenance 동시 설계. 실제 UDP 실행 없음.

## R53 FK export / LowState viewer 모델 격리

- 검토: export_g1_mink_fk_reference 및 live_lowstate_mujoco.LoadModel 공유 XML 쓰기.
- 코드 수정: 두 곳 임시 모델 생성/로드. 샘플/가시성/제어 값 미변경.
- 테스트: 격리/가시성 24 passed. r53_viewer_export_20260906.xml.
  viewer는 LoadModel만 실행하고 socket 금지. FK 결과는 임시 폴더에 저장.
- 남은 항목: 라이브 제어기와 캡처 모델 provenance 연결 확인. 장비 실행 없음.

## R53 recovery/editor 모델 격리

- 검토: plan/simulate/replay_startup 및 edit_startup_ready_pose의 공통 XML 생성.
- 코드 수정: 네 경로 임시 XML 생성/로드. 복구 궤적·속도·자세 미변경.
- 테스트: 격리/가시성 21 passed. r53_recovery_models_20260906.xml.
  모델 로드 블록 정상/실패와 editor CreateModel의 관절값 유지 확인.
- 남은 항목: 전체 recovery/viewer 실행 및 다른 writer/provenance 점검.
  실제 G1/WSL/DDS, 준비 자세 저장, strategy atlas 재개 없음.

## R53 startup 진단 모델 격리

- 검토: check_startup_readiness/diagnose_initial_pose_collision의 공통 XML 쓰기.
- 코드 수정: 임시 경로 생성/로드로 변경. 충돌/준비 판정 기준 미변경.
- 테스트: 모델 격리/가시성 12 passed. r53_startup_models_20260906.xml.
  사전검사 수치 helper는 가상 29축 입력으로 실행; UDP main 미실행.
- 남은 항목: recovery/editor 등 writer 및 provenance. 실제 장비 실행 없음.

## R53 오프라인 모델 writer 격리

- 검토: pose-sync 검증기와 Gate7 offline 충돌 검증기의 공통 XML 쓰기 확인.
- 코드 수정: 두 경로 임시 XML 생성/로드/정리. 제어 설정 미변경.
- 테스트: 격리/가시성 7 passed. r53_offline_models_20260906.xml.
  pose-sync는 모델 로드 블록만 실행, 실제 capture/전체 main 미실행.
- 남은 항목: 다른 startup/recovery/editor writer 및 provenance. R53 부분 수정.
  실제 G1/WSL/DDS/네트워크 실행 없음.

## R20 도달 범위 진단 종료 코드

- 검토: diagnose_recorded_reach도 REVIEW_REQUIRED + 성공 종료, 기존 R20 확장.
- 코드 수정: 보고서 저장 후 return 3, SystemExit로 전달. 제어 파라미터 미변경.
- 테스트: reach 5 + diagnostic exit 92 = 97. r20_reach_exit_20260906.xml.
  실제 모델 FK 기반 main 테스트; capture decode/구간 추출은 mock.
- 남은 항목: 전체 캡처/렌더 CLI 통합 및 R24/R53 등. G1/WSL/네트워크 미실행.

## R58 Ethernet 설정 복구

- 검토: IP 변경 후 DNS/표식 실패가 발생하면 중간 설정이 남는 문제.
- 코드 수정: 공통 G1_ETHERNET_TRANSACTION.ps1로 active/persistent 설정과 DNS
  snapshot, 변경, 검증, 실패 복구. DHCP는 임대 주소 재생 대신 자동 모드 복원.
  사용자 지정 경로/임시 수동 주소/서로 다른 store 설정은 변경 전 차단.
- 테스트: Ethernet 28 + DNS/기존 진단 103 = 131 passed.
  logs/test_results/r58_ethernet_20260906.xml. 실제 네트워크 변경 없음.
- 남은 항목: 실제 Windows provider/store 상호작용 및 DHCP 재확보 확인.
  강제 종료/동시 외부 변경/사용자 지정 경로 복구는 지원하지 않음.
  R58은 지원 범위 source mitigation이며 물리/환경 검증 완료가 아니다.

## R58 IPv4 DNS 범위와 복구

- 검토: DNS reset이 interface 전체로 지정되어 있었고 실패 복구가 없었음.
- 코드 수정: G1_ETHERNET_DNS.ps1 공통 helper. IP 변경 전에 IPv4 DNS 모드/수동
  서버 목록 snapshot, IP 검증 후 IPv4 객체만 reset. DNS 실패 시 모드 복구.
- 테스트: DNS 12 + 기존 진단 91 = 103 passed. r58_dns_20260906.xml.
- 남은 항목: 전체 IP/route rollback, 완료 표식 저장 실패 복구, 실제 환경 검증.
  DNS rollback이 성공해도 이미 바뀐 IP는 복구되지 않는다. 전체 R58 완료 아님.
  실제 네트워크/registry/WSL/G1 변경 없음.

## R58 DDS 방화벽 규칙 쌍 복구

- 검토: 두 규칙 삭제/재생성 중 실패 시 중간 상태가 남는 R58 확인.
- 코드 수정: 두 규칙 사전 snapshot, 직접 갱신/검증, 역순 복구와 오류 집계.
  복수 ASIX는 명시적 index 요구. BAT 복구 실패 안내 추가.
- 테스트: DDS 32 + LowState 15 모의 사례. r58_dds_rollback_20260906.xml.
- 남은 항목: Ethernet/DNS 복구 및 실제 환경 검증. 실제 네트워크/G1 변경 없음.

## R58 LowState 방화벽 실패 복구

- 검토: 규칙 삭제 후 생성 실패 문제를 기존 R58에 연결.
- 코드 수정: PersistentStore snapshot, 기존 규칙 직접 갱신, 적용값 검증,
  실패 시 복구/재검증. 신규 규칙 실패 시 제거. 복구 실패는 별도 오류.
- 테스트: 외부 cmdlet/파일 작업을 모두 mock한 15 cases passed.
  logs/test_results/r58_firewall_rollback_20260906.xml 참조.
- 남은 항목: DDS 규칙/Ethernet/DNS 복구, 실제 환경 검증.
  실제 방화벽/WSL/G1 변경 없음. 전체 수정 완료가 아니다.

## 검토 상태 정리 및 R57

- 검토: REVIEW_LATEST의 오래된 coverage/진행 설명을 현재 표와 과거 기록으로 분리.
- 코드 수정: LowState firewall 범위를 G1 ASIX + 192.168.123.0/24로 축소;
  복수 어댑터는 명시적 index 요구. 실제 방화벽은 변경하지 않음.
- 테스트: 모든 외부/파일 작업을 mock한 PowerShell 5 cases passed.
- 남은 항목: R58 rollback/DNS, R20/R24/R53/R63 일부, R50 및 물리 검증 등.
  REMEDIATION_20260906_FIREWALL_SCOPE.md 참조. 전체 수정 완료가 아니다.

## 3.12 로컬 실행 선택 연결

- 검토: 전역 설치와 물리 경로를 유지하며 별도 엔진 선택/출처 경계 확인.
- 코드 수정: run_mink_g1_simulation_312.py 추가. START_VR_STANDARD_MINK만
  --mujoco312 선택; 카메라/WSL 감지 건너뜀. simulation_only 패킷은 물리 경로 거부.
- 테스트: 전용 entry + standard 25 passed. validate-only로 실제 3.12
  import 확인, 기본 3.11 유지. compile 확인.
- 남은 항목: Unity Play/Quest 검증. 물리 경로는 기존 3.11 및 잠금 그대로.
  STANDARD_MINK_LIVE.md 실행법 참고. 새 엔진 설치나 G1/WSL 실행 없음.

## MuJoCo 3.12 로컬 전환 후보 검증

- 검토: 격리 버전에서 standard/계층형 IK, 공개 API, 입력, 충돌, 궤적 확인.
- 코드 수정: 없음. 기본 엔진/WSL/물리 프로파일 유지.
- 테스트: 83 passed / 26 subtests (mujoco312_expanded_20260906.xml).
  6종 headless 입력, 이미지 렌더 확인, passive viewer 5프레임 정상 종료.
- 남은 항목: 기본 3.11.0 유지; 전체 프로젝트/VR/WSL/물리 검증은 아님.
  로컬 3.12 전환 후보 근거 확보. 상세 DIAGNOSIS_20260906_WRIST_ROLL_DISTANCE.md.

## Standard Mink 장비 없는 검증 확대

- 검토: IK -> 지원 provenance -> 릴레이 -> 가상 Gate 7 계약 확인.
- 코드 수정: 연속 7종/2프로파일 테스트; 가상 E2E token 갱신 및
  선택적 relay bind 준비 신호 추가. 실제 안전 규칙/IK 설정/잠금 유지.
- 테스트: 최종 51 passed, 릴레이 반복 8 passed, 입력 39 passed/122 subtests.
  격리 3.12에서 22 passed/3 subtests. C# 증분 빌드 두 개/compile 통과.
- 남은 항목: 3.11 거리 문제, 실제 VR/WSL/DDS/G1 검증.
  STANDARD_MINK_OFFLINE_20260906.md에 중간 실패와 최종 결과 경로 기록.

## Standard Mink를 공통 Gate 7 루프에 연결

- 검토: prototype 전용 루프와 공통 live 루프의 피드백 차이를 확인했다.
- 코드 수정: `--ik-solver vanilla`로 StandardMinkPlanner 선택. 일반 6D QP와
  기존 계층형 IK가 동일 입력/궤적/상태/출력 검증 경로를 공유한다.
  vanilla의 위치 기준은 wrist-yaw이며 기존 기본값 hierarchical은 유지.
  START_VR_STANDARD_MINK 및 tools/START_G1_GATE7_STANDARD_MINK 추가.
- 테스트: 첫 묶음 27 passed/10 subtests, 최종 선택/피드백 7 passed
  (중복 3개; 고유 31개). 변경 Python 3파일 py_compile 통과.
  QP 첫 단계 일치 및 충돌 경로 거부 HOLD를 두 프로파일에서 검증.
- 남은 항목: VR/실물 end-to-end 검증, 기존 MuJoCo 3.11 거리 문제.
  하드웨어 출력 잠금 유지, WSL/DDS/G1 실행 없음.
  상세: STANDARD_MINK_LIVE.md.

## MuJoCo 격리 버전 비교 결과

- 검토: 동일 wrist-roll fixture를 3.10/3.11/3.12 native에서 비교.
- 코드 수정: 없음. logs/diagnostics/mujoco_versions에 3.10.0/3.12.0 wheel만
  --no-deps --target 설치. 기본 Python은 3.11.0 유지/모듈 경로 재확인.
- 테스트: 3.10/3.11 부호 불일치, 3.12는 7표본 모두 양수.
  3.12 격리 wrist regression 4 passed/3 subtests;
  관련 IK/거리 6파일 43 passed/12 subtests. 전체 47 passed/15 subtests.
- 남은 항목: 3.12 전체 회귀/뷰어 호환성 후 기본 환경 전환 검토.
  현재 기본 3.11의 실패를 해결 처리하지 않는다. G1/WSL/DDS/물리 출력 없음.
  DIAGNOSIS_20260906_WRIST_ROLL_DISTANCE.md 참조.

## 거리 엔진 옵션 비교

- 검토: 같은 손목 roll 실패 qpos의 native/legacy 및 반복/허용오차 차이.
- 코드 수정: 없음. 임시 MjModel 옵션만 실험 프로세스 내 변경.
- 테스트: native 35/1e-6 및 200/1e-9 모두 부호 불일치; legacy는
  이동 7표본 모두 +133.205498mm. 진단 문서에 표와 공식 문서 링크 추가.
- 남은 항목: 엔진 버전/최소 모델 격리 비교. legacy의 일반 거리 정확도
  한계가 있으므로 실시간 적용하지 않는다. 기존 회귀 실패 유지.

## 손목 roll 실패 원인 좁히기

- 검토: 기존 kinematics regression 재실행: 4 passed/2 subtests/1 failed.
- 코드 수정: 없음. 충돌 제한/비용/테스트 기준 유지.
- 테스트: 실패 qpos를 고정한 거리 검사에서 전체 X를 1e-12m 이동하면
  -133.205mm가 +133.205mm로 반전. 정점 투영 하한은 130mm 이상.
  DISTANCE_INCONSISTENT 재현. DIAGNOSIS_20260906_WRIST_ROLL_DISTANCE.md에 qpos/표 기록.
- 남은 항목: 거리 엔진/설정 격리 비교. 실제 관통으로 단정하거나 양수값만
  선택해 통과시키지 않는다. G1/WSL/DDS 실행 없음.

## 2026-09-06 묶음 회귀 및 C# 프로젝트 빌드

- 검토: 최근 R53/R54/R56/R58/R61/R63 수정 후 관련 회귀를 묶어 확인.
- 코드 수정: 없음. 빌드 중 누락된 NuGet assets를 복원하여 Temp 산출물 생성.
  Packages/ProjectSettings에는 git 변경 없음.
- 테스트: diagnostic_exit_contract, foundation, test_sweep,
  test_mink_feasible_target, test_mink_collision_diagnostics,
  test_mink_virtual_center_trajectory, test_virtual_center_orientation_policy,
  test_recorded_reach_bound: 161 passed/106 subtests (106.51 s).
  변경 Python 5파일 py_compile 통과.
  dotnet build Assembly-CSharp.csproj: 오류 0/경고 63.
  dotnet build Assembly-CSharp-Editor.csproj: 오류 0/경고 6.
  csproj에 G1HeadCameraPiP.cs와 G1VRBuild.cs가 포함됨을 확인했다.
- 남은 항목: Unity Editor 자체의 재import/Play/Player build는 미실행.
  기존 test_virtual_center_kinematics_regression 손목 roll 거리 실패는
  이번 suite 미포함이며 해결로 처리하지 않는다. R58 rollback/R57/R63 owner 등 유지.
  G1/WSL/DDS 및 실제 네트워크 설정 변경 없음.

## R61 카메라 프레임 수신 deadline

- 검토: partial header/payload가 ReadExactly를 무기한 점유할 수 있었다.
- 코드 수정: 헤더+본문 공통 2초 Stopwatch deadline 및 남은 시간 기반
  ReadTimeout. 시간 초과 IOException은 기존 RunReceiver catch/finally로
  전달되어 client를 닫고 accept loop를 계속한다. 정상 JPEG 계약은 유지.
- 테스트: diagnostic_exit_contract 91 passed. 실제 C# ReadExactly를 추출해
  Add-Type 컴파일 후 모의 Stream으로 분할 읽기/EOF/취소/만료/정체/공통
  deadline 검증. 소켓을 열지 않았다.
- 남은 항목: Unity 전체 빌드, 실제 NetworkStream 정체 후 재연결/VR 표시
  검증은 미실행. 저속 연결에서는 2초 제한에 의해 재연결될 수 있다.
  G1/WSL/DDS/물리 명령 없음.

## R63 카메라 수치 입력 검증

- 검토: profile의 int coercion 및 live/replay CLI의 NaN 비교 누락.
- 코드 수정: width/height/fps는 양의 int만 허용, FOV는 유한한 0~180도
  열린 구간. profile 로딩과 source 생성 경계에서 모두 검사한다.
  두 CLI의 fps/timeout/reconnect/duration은 유한 수만 허용한다.
- 테스트: diagnostic_exit_contract + foundation: 115 passed/80 subtests.
  CLI 검증 함수만 AST 추출 실행; 카메라/네트워크/G1 구동 없음.
- 남은 항목: R63 설정 owner 및 경로별 fps 통합은 미완료.
  현재 profile/게인/속도 값은 변경하지 않았다.

## R58 IPv4/DHCP 최종 상태 검증

- 검토: setter 반환 뒤 실제 상태 확인 없이 성공 종료/marker 작성.
- 코드 수정: static 경로는 DHCP Disabled 및 단일 192.168.123.99/24,
  DHCP 복원은 Enabled 및 Manual IPv4 없음 확인. 변경 전에 이전 static
  marker 제거. IP 제거 오류는 숨기지 않는다. DNS 최종 상태 검증은 미포함.
- 테스트: diagnostic_exit_contract 50 passed. 추가 8개 경로는 모든 네트워크
  cmdlet을 모의 함수로 대체한 PowerShell 실행(정상/다른 DHCP/잔여 IP/인터페이스 없음).
  실제 네트워크 명령이나 관리자 실행 없음.
- 남은 항목: rollback, DNS 검증, R57 방화벽 범위. DHCP 성공 문구는
  DHCP lease 획득/인터넷 연결 성공을 뜻하지 않는다.

## R58 어댑터 선택 경계

- 검토: static-IP/DHCP 복원 스크립트가 첫 번째 ASIX 어댑터를 임의 선택했다.
- 코드 수정: 후보가 정확히 하나일 때만 계속한다. 여러 개면 -InterfaceIndex
  명시가 필요하며 잘못된 index는 차단한다. 이후 명령도 index를 사용한다.
- 테스트: diagnostic_exit_contract 42 passed. 두 스크립트 선택부를 모의
  Get-NetAdapter로 검증했다(없음/중복/단일/명시 선택/없는 index).
  실제 네트워크 setter/관리자 명령/G1 실행 없음.
- 남은 항목: R58 rollback/최종 상태 검증, R57 방화벽 범위는 여전히 미완료.
  자동 복원을 구현한 것으로 해석하지 않는다.

## R56 네트워크 진단 완료 판정

- 검토: pktmon native 명령 실패를 확인하지 않고 done을 생성했다.
- 코드 수정: start/stop/format 종료 코드 및 비어 있지 않은 ETL/text 확인 후
  done 생성. 시작 전 무조건 stop 제거. 자신이 시작한 capture만 오류 시 정리 시도.
- 테스트: test_diagnostic_exit_contract.py 32 passed. pktmon/Start-Sleep을
  PowerShell 함수로 대체하여 정상/각 단계 실패/출력 누락 6경로 검증.
  실행 정책 옵션은 테스트 자식 프로세스 한정이며 시스템 정책은 변경하지 않았다.
- 남은 항목: 실제 관리자 pktmon/네트워크 동작 미검증. 다른 R 항목은 별도.
  G1/WSL/DDS 실행 및 네트워크 설정 변경 없음.

## R53 보존 결과 무결성 검증

- 검토: resume의 보존 항목은 파일 존재/내용과 summary 일치를 검사하지 않았다.
- 코드 수정: 입력/result/log SHA256 저장. 보존 시 cases 경로 내부 파일인지,
  해시 및 초기 자세가 같은지, PASS/FAIL과 결과 boolean/exit code가 맞는지 검사.
  SKIPPED는 입력만 검사한다. 검증 기록 없는 항목은 새 실행이 필요하다.
- 테스트: test_sweep.py 12 passed/14 subtests. 파일 변경/삭제/해시 누락,
  summary 모순, SKIPPED를 포함한다. subprocess mock; 전체 sweep 미실행.
- 남은 항목: 다른 experiment runner, summary 자체의 서명/위변조 방어는 범위 밖.
  기존 손목 roll 충돌 거리 회귀 실패 및 물리 검증은 해결되지 않았다.
  G1/WSL/DDS/물리 출력 설정 변경 없음.

## R53 개별 스윕 재시도 결과 격리

- 검토: RunCase 재시도 시 기존 result.json이 새 결과로 읽힐 수 있었다.
- 코드 수정: case 아래 UUID 실행 폴더를 생성하여 입력/결과/로그를 격리.
  기존 파일은 보존한다. 잘못된 JSON/비객체/비boolean passed는 ERROR로 기록.
  timeout stdout/stderr의 bytes/str 혼합도 정상 저장한다.
- 테스트: test_sweep.py 11 passed/11 subtests. subprocess는 mock이며,
  이전 PASS 보존 및 재사용 차단/잘못된 결과/timeout 출력 회귀를 검증했다.
  기존 MuJoCo 모델 로딩 테스트도 통과. 전체 sweep/G1/WSL/DDS 실행 없음.
- 남은 항목: 재개 시 보존하는 개별 결과의 무결성 검증 및 다른 실험 runner.
  기존 손목 roll 충돌 거리 회귀 실패는 별개로 남아 있다.

## R53 스윕 재개 provenance

- 검토: 기존 resume은 코드/모델/입력이 바뀌어도 성공 결과를 재사용했다.
- 코드 수정: source state, bridge/scripts/backend/sweep Python, config JSON,
  G1 asset 파일의 SHA256 및 Python/주요 패키지 버전 저장. 재개 시 정확히
  일치하지 않으면 차단하며 기록 없는 구버전 지도는 새 실행이 필요하다.
  실행 종료 시에도 다시 비교하여 변경 시 latest 결과로 승격하지 않는다.
- 테스트: test_sweep.py 8 passed/7 subtests. 실제 파일 manifest 생성 및
  입력 변경 감지 검증. 전체 sweep/G1/WSL/DDS 실행 없음.
- 남은 항목: 다른 experiment writer 및 개별 결과 artifact 검증.
  실행 중 파일이 바뀌었다가 복원되는 경우까지 감시하는 구조는 아니다.
  무관한 소스 수정도 보수적으로 재개를 차단할 수 있다.

## R53 자세 스윕 모델 격리

- 검토: 부모 PrepareModel과 자식 G1_SWEEP_MODEL_PREPARED가 공용 XML을 공유했다.
- 코드 수정: 부모 XML 생성 제거, single_pose_runner가 프로세스별 임시 XML 사용.
  예외 시에도 기존 controller 모델 경로와 prepare 함수를 복원한다.
- 테스트: test_sweep.py 6 passed/7 subtests. 실제 MuJoCo XML 로딩, 공용 파일
  바이트 불변, 예외 정리 확인. 전체 스윕/WSL/DDS/G1 실행 없음.
- 남은 항목: 재개 시 기존 결과 provenance 및 다른 실험 writer 검토,
  기존 손목 roll 충돌 거리 회귀 실패. 복구 알고리즘/물리 설정 변경 없음.

## R54 스윕 결과 판정

- 검토: 스윕 완료와 자세 복구 성공을 혼동하는 기존 R54.
- 코드 수정: outcome/exit_code 구분, 성공 없음은 코드 3, 두 BAT의 PASS 표현 수정.
- 테스트: 5 passed/7 subtests. 실제 스윕/로봇 실행 없음.
- 남은 항목: R53 실험 provenance 및 기존 손목 roll 거리 실패.
  REMEDIATION_20260905_SWEEP_OUTCOME.md 참조. 복구 동작 자체는 변경하지 않았다.

## R53 backend 테스트 writer 격리 계속

- 검토: 남은 직접 모델 생성 backend 테스트6파일.
- 코드 수정: TemporaryDirectory/output_path 사용, test 소스 AST guard 추가.
  제어 비용/제약/기대값 변경 없음.
- 테스트: 38 passed/12 subtests. DDS/UDP/Unity/G1 실행 없음.
- 남은 항목: 실험 runner provenance와 기존 손목 roll 거리 실패 유지.
  REMEDIATION_20260905_MODEL_ISOLATION.md에 기록.

## 2026-09-05 APK 및 settle 수정

- 검토: R59/R67 APK output 불일치, R52 stale settle 재확인.
- 코드 수정: GUID output/env 공유/SHA256/명시 serial 설치, settle freshness와
  gap 검사 및 publisher 직전 snapshot 재검증. 물리 설정 그대로.
- 테스트: 57 passed/3 subtests. 실제 Unity build/Quest install/G1 실행 없음.
- 남은 항목: R53/R50 및 손목 roll 거리 실패 포함 전체 수정 아직 미완료.
  REMEDIATION_20260905_APK_AND_SETTLE.md 참조.

## VR 없는 MuJoCo IK 비교

- 루트 VIEW_IK_COMPARISON.bat 추가. 1/2 표시 전환, N 동작 전환,
  Space 일시정지, R 동일 초기 자세 재시작. 두 solver 동시 계산.
- 기존 hierarchy Plan과 프로젝트 vanilla 6D FrameTask QP를 비교한다.
  공식 예제 전체 복제 아님. 양쪽 기본5/10mm, 같은 속도/목표.
- 임시 XML, 네트워크/물리 출력 없음. 6동작 각각1200step 실행 완료,
  offscreen 이미지 및 viewer 5frame smoke 통과, 독립상태/reset 검사 통과.
- docs/IK_VISUAL_COMPARISON.md 참고. 물리 안전/정확도 우위의 증명 아님.

## 2026-09-05 손목 회귀 입력 속도 수정

- 검토: R24 후속. 25도/12초 목표는 peak13.1 deg/s 요구.
- 코드 수정: cap 절반 이하의 사인파 주기 계산. 정확도 기준/진폭 유지.
  수치 진단에 최소거리 발생 qpos/시간/geom 쌍 추가. 라이브 변경 없음.
- 테스트: 수치4 passed/2 subtests passed/1 subtest failed. 위치/회전/근위
  조건은 모두 통과하지만 roll에서 -133.20548mm 거리 실패 유지.
- 남은 항목: shoulder_yaw/wrist_yaw geom 거리의 동일 qpos 재검증.
  원인은 아직 확정하지 않았다. REMEDIATION_20260905_MODEL_ISOLATION.md 참고.

## 2026-09-05 수정 재개: 모델 격리

- 검토: R53 공통 모델 writer, R24 수치 테스트 속도 전제.
- 코드 수정: optional output_path와 자산 경로 처리. 카메라/가시성/수치
  회귀 검사 임시 XML 사용. 기존 기본 실행 경로와 제어 설정 유지.
- 테스트: 관련124 passed/64 subtests, compileall 통과. 별도 수치검사에서
  손목3축 subtest 실패(근위7.77/11.59/24.81도). 기준 완화 없음.
- 남은 항목: 단일 QP 수치검사와 현재 계층형 경로 구분 및 R53 잔여 writer.
  상세 REMEDIATION_20260905_MODEL_ISOLATION.md. 전체 수정 미완료.

## 2026-09-05 전체 finding 수정 요청: 첫 수정 묶음

- 검토: R20/R24/R25/R26/R28 소스 재확인. 전체 수정은 아직 미완료.
- 코드 수정: 진단 CLI 종료 코드, 실제 속도 metadata, stale Unity DLL 차단,
  최소 solver duration, workspace 유한 시간 계약. 물리/IK 설정 유지.
- 테스트: 9개 파일 121 passed, 64 subtests passed. PowerShell fixture 포함.
- 남은 항목: R24 잔여 기대값/R53 및 기존 미해결 항목. 실제 장치 시험 없음.
  상세는 REMEDIATION_20260905_DIAGNOSTICS.md. 다음 작업은 새 실험이 아닌 잔여 수정.

## 2026-09-05 R27 수정 및 실험 기준

- 검토: R27 입력행렬 rigid rotation 전제 확인. 새 임의 cost sweep은 중단한다.
- 코드 수정: 공통 SO(3)/SE(3) 검사, 변환/캘리브레이션에 적용,
  실패 샘플 부분저장 방지. IK/물리 설정 변경 없음.
- 테스트: 관련85 passed/90 subtests. 실제 입력 통합/원격CI 미검증.
- 남은 항목: R20/R24/R53 수정 우선, R50 미검증 유지.
  동일 목표/모델/속도/충돌 쌍의 단일 QP 기준선 및 기존 후보만 평가한다.
  추종 정확도/근위 이동/정체/복귀를 함께 보고 새로운 비용 후보를 늘리지 않는다.
  상세: REMEDIATION_20260905_RIGID_POSE.md. G1/WSL/DDS/Unity 실행 없음.

## 2026-09-05 수정 재개 및 IK 단계 축소

- 검토: 한정된 코드 색인320/320 full_text 완료. 전체 문제 수정 완료는 아님.
  R32 V1 정수 coercion을 별도 수정. R27/R20/R24/R53 및 R50 잔여는 유지.
- 코드 수정: V1 파서에 기존 strict _integer 적용, 정상정수/생략기본값 유지.
  IK는 offline --single-qp-backtrack만 추가. live 및 물리 설정 변경 없음.
- 테스트: 관련81 passed/42 subtests. backtrack 두 프로필 x 3동작=6회 완료.
  toward_body 20/40mm에서 최종79.98mm 잔차가 계산상0으로 감소.
  축소단계2회, 최소거리20.00474mm. 접근 중 큰 목표오차는 남아 있음.
- 남은 항목: 실제 IK 미채택, 목표도달/전역안전 보장 아님. 다음 정식 수정은
  R27 회전행렬 검증부터. R32 수정 문서는 REMEDIATION_20260905_PROTOCOL_V1.md.
  G1/WSL/DDS/Unity 실행 및 publisher 생성 없음.

## 2026-09-05 경계 복귀 정체 원인 진단

- 검토: toward_body/단일QP/cost0.03의 경로 거절 관찰.
  20/40mm 671회 모두 hip_pitch와 wrist_yaw geom 거리 미달.
  관절범위 원인0, 마지막 거절 후보19.98975mm(요구20mm).
- 코드 수정: offline --diagnose-path 추가. 원래 판단 유지, live 변경 없음.
- 테스트: 두 프로필 재실행, 관련33 passed. 주요 비시간 지표 진단 전후 동일.
- 남은 항목: 선형 QP와 비선형 경로검사의 차이 분석 및 보호조건을 유지한
  단계 축소 비교. 거절 후보와 실행 자세 구분. G1/Quest/WSL 실행 없음.

## 2026-09-05 단일 QP 비용1 동작 회귀 비교

- 검토: combined/reversal_step/toward_body x 비용0.03/1 x 5/10 및20/40mm.
  동일 중립 시작/월드X 회전/0.16rad/s, 기존 offline 도구로12회 완료.
- 코드 수정: 없음. live/물리 설정 유지.
- 테스트: 관련32 passed. combined 위치P95 7.35 -> 11.31mm로 악화,
  근위 누적123.12 -> 92.16deg로 감소(5/10mm). reversal 회전P95 약29.5deg.
  toward_body 20/40mm에서 비용0.03은 최종79.98mm 잔차 및 경로거절671회,
  비용1은 최종0.0044mm 잔차. 하지만 이동 중 위치P95는 양쪽 약150mm.
  샘플 충돌거리 위반0이며 도달/연속 안전 보장이 아니다.
- 남은 항목: 비용1 일괄 적용 미채택. 단일 QP 몸통 경계 복귀 정체의 경로검사
  원인을 다음 source/오프라인 진단 대상으로 기록. 승인/충돌 검사를 끄지 않는다.
  toward_body 목표의 도달가능성은 미확정. G1/Quest/WSL 실행 없음.

## 2026-09-05 단일 QP 근위 damping 비용 비교

- 검토: 단일 QP의 DampingTask 근위4축 cost만 0.1/0.3/1/3으로 변경.
  기본0.03 결과와 비교. 설치 Mink 소스에서 cost 제곱이 관절 변위 비용에
  들어감을 확인했다. PD gain이나 관절 속도 설정이 아니다.
- 코드 수정: offline --single-qp-proximal-cost 옵션 및 단위시험2개 추가.
  single_weighted_qp 모드에만 허용. 기본None, live 불변.
- 테스트: 중립/pitch80 x 월드3축 x 4비용=24회. 관련32 passed 및 compile 통과.
  중립에서는 회전P95 약0.24deg 유지. pitch80 X에서 비용0.03/1/3의
  근위 누적99.87/77.47/60.07deg, 위치P95 3.96/4.86/9.98mm,
  회전P95 1.31/1.59/2.88deg. 샘플 충돌거리 위반0.
- 남은 항목: 비용1은 추가 비교 후보일 뿐 미채택. combined/급변/몸통 접근 및
  다른 충돌 프로필 회귀 미검증. 고정 cost로 모든 자세 최적화를 보장하지 않는다.
  G1/Quest/WSL 실행 없음. 상세 표는 비교 문서.

## 2026-09-05 단일 QP 한계 자세 기준선

- 검토: 두 번째 hierarchy QP는 이미 위치/회전 목표를 함께 포함한다.
  목표 누락이 아니라 progress 등식 및 merit 승인 계층을 구분해야 한다.
  프로젝트 단일 weighted QP를 pitch+80 월드3축에서 두 충돌 프로필로 비교했다.
- 코드 수정: 없음. 기존 offline 비교 도구만 사용. live 유지.
- 테스트: 6회 완료 및 관련30 passed. 회전 P95 X/Y/Z=1.31/0.25/0.24deg,
  위치 최대=4.115/3.215/0.060mm. 근위 누적=99.87/56.80/16.91deg 수준.
  5/10mm 및 20/40mm에서 유사. 모든 실행780프레임 승인, 샘플 거리 위반0.
- 남은 항목: 단일 QP도 근위 움직임 억제와 정확한 추종을 동시에 보장하지 않음.
  기존 등식 제거+비용0.03+merit 제외 결과와 주요 오차/이동 지표가 유사하다.
  완전 vanilla 설정은 아님. 다음 후보는 단일 QP의 근위 비용만 바꾸는
  통제 비교로 검토하되 중립 wrist-only와 한계 자세를 동시에 평가한다.
  G1/Quest/WSL 실행 없음. 단순 live 교체는 미채택.

## 2026-09-05 위치 merit 1mm dead zone 시험

- 검토: 기존 등식 제거+근위 비용0.03 후보의 위치 merit를
  cost^2 * max(0, Euclidean_error - 0.001)^2로 변경한 offline 비교.
  허용범위 안에서는 회전 개선을 승인하고 밖에서는 기존 감소 조건을 유지한다.
  이 값은 hard constraint 또는 움직이는 목표의 절대 오차 보장이 아니다.
- 코드 수정: 합성 도구에 --merit-position-tolerance-mm 추가 및 검증2개 추가.
  기본0으로 기존 동작 유지, merit 전체 제외와 혼용 금지. live 수정 없음.
- 테스트: 30 passed, pitch+80 월드3축 및 중립 combined 총4회 완료.
  회전 P95 X/Y/Z=13.46/4.37/0.24deg. X/Y local_limit=286/149프레임.
  위치 최대 X/Y=1.00122/1.00149mm(기존 수치 허용치 포함), Z=0.060mm.
  combined 위치/회전 P95=7.35mm/0.32deg. 샘플 거리 위반0.
- 남은 항목: 이 후보도 미채택. X/Y 정체가 남아 있어 단순 tolerance로 해결 안 됨.
  위치 허용오차/근위 이동/회전 추종의 기준을 함께 정한 뒤 후보를 비교해야 한다.
  G1/Quest/WSL 실행 없음. 상세 및 결과 경로는 비교 문서 참조.

## 2026-09-05 pitch+80 merit 승인 조건 분리

- 검토: 등식 제거+근위 비용0.03 후보에서 merit 승인 조건만 제외하여 비교.
  위치 merit는 위치 오차 제곱에 POSITION_COST 제곱을 곱한 값이다.
  기존 승인은 위치 merit 감소, 또는 위치 merit 비증가와 회전 merit 감소를 요구한다.
- 코드 수정: 없음. 기존 offline 옵션 사용, live/물리 설정 유지.
- 테스트: 월드 X/Y/Z 3회 완료, 관련 pytest 28 passed.
  회전 P95는 19.25/16.11/16.81에서 1.31/0.25/0.24deg로 감소.
  위치 P95는 3.96/3.16/0.058mm, 근위 누적 이동은 99.87/56.80/16.91deg.
  샘플 충돌거리 위반0. X에서 미세 속도 초과 후보1회 거절.
- 남은 항목: 단순 승인 제거는 미채택. 회전 개선과 위치/근위 이동의 교환관계다.
  앞선 combined 시험에서는 승인 제거 효과가 작았으므로 일반화하지 않는다.
  다음은 명시적 위치 허용오차 내 회전 개선 승인 방식의 오프라인 비교 검토.
  G1/Quest 실행 없음. 상세 표는 IK_RECORDED_COMPARISON_20260905.md.

## 2026-09-05 손목 한계 근처 비교: 변경안 일반화 불가

- 검토: pitch+80/yaw-80 시작에서 월드3축 회전 비교.
  yaw+80은 초기 모델 최소거리 -27.186mm로 차단되어 실행하지 않았다.
- 코드 수정: 없음. 기존 도구 사용. live 제어와 물리 설정 유지.
- 테스트: 12회 완료, 시작차단1회, 관련28 passed.
  pitch+80 회전 P95 기존/변경 X=7.25/19.25, Y=5.06/16.11,
  Z=1.91/16.81deg. 변경안 local_limit X/Y/Z=413/331/343프레임.
  yaw-80은 양쪽 모두 약0.24deg로 잘 추종. 샘플 최소거리 위반0.
- 남은 항목: 등식 제거+낮은 근위 비용을 live에 적용하지 않는다.
  중립 자세 결과로 일반화할 수 없음. pitch+80에서 필요 근위 움직임과
  회전 추종 정체를 분리해야 한다. 표/경로는 IK_RECORDED_COMPARISON_20260905.md.
  Quest/G1 실행 없음.

## 2026-09-05 팔꿈치 20/100도 시작 자세 비교

- 검토: 나머지 관절은 [10,-22,0,elbow,0,0,0]deg로 유지하고 팔꿈치만
  20/100도로 바꿨다. 5/10mm, 각 월드 X/Y/Z 0.35rad 왕복. 시작 관절 범위와
  충돌 여유 검증 후 오프라인 실행했다. 시작 최소거리 둘 다 40.38mm.
- 코드 수정: 합성 도구에 초기 관절값/방식 선택 및 시작 자세 검사 추가.
  live 제어 변경 없음. Startup Recovery 실험과 별개이며 그 경로는 수정하지 않음.
- 테스트: 2자세 x 3축 x 기존/변경 = 12회 완료. 관련 28 passed, compileall 통과.
  변경안 근위 누적 최대 0.1402deg, 최대 위치 오차 0.001604mm,
  회전 P95 약0.24deg, 검사된 충돌거리 위반 0. 기존의 근위 이동은 더 작다.
- 남은 항목: 팔꿈치 각도 변화에서 큰 근위 움직임은 재현 안 됨.
  어깨/손목 비중립 시작과 한계/특이점 부근은 아직 미검증. live 미채택 유지.
  `logs/test_results/ik_pose{20,100}_{x,y,z}_{original,modified}_20260905.json`.

## 2026-09-05 손목 3축 비교 완료

- 검토: 5/10mm 프로필, 기존 [10,-22,0,55,0,0,0]deg 초기 자세에서
  월드 X/Y/Z 각각 0 -> 0.35 -> 0rad, 8초+hold 5초를 비교했다.
- 코드 수정: 합성 도구에 `--axis`와 `--profile` 선택 추가. live 변경 없음.
- 테스트: 3축 x 기존/변경 x 단일QP/계층 경로 총 12회, 관련 27 passed,
  compileall 통과. 변경은 equality 제거 + proximal cost 0.03이다.
  변경안 근위 누적 이동 X/Y/Z=0.0104/0.0822/0.1324deg,
  최대 위치 오차 0.00136mm 이하, 회전 P95 약 0.24deg. 샘플 거리 위반 0.
- 남은 항목: 이 조건에서는 큰 근위 움직임이 재현되지 않았다.
  기존 계층형의 근위 이동은 더 작다. 한 자세/양의 20도 회전만으로
  모든 자세의 인간다운 동작을 보장하지 않는다. live 채택 전 다중 시작 자세,
  손목 한계 부근 및 실제 Quest 검증 필요. G1/Quest 실행 없음.
  결과: `logs/test_results/ik_wrist_{x,y,z}_{original,modified}_20260905.json`.

## 2026-09-05 equality x 비용 원인 분리 완료

- 검토: combined에서 equality 제거만 및 제거+근위 비용 0.03을 대조했다.
  기존 equality/100 및 equality/0.03 결과까지 네 조건을 비교했다.
- 코드 수정: 합성 도구 `--remove-progress-offline`만 추가, band/shadow와
  혼용 차단. default false. frozen/충돌/속도 제약 유지. live 변경 없음.
- 테스트: 신규 8회 완료, 관련 26 passed 및 compileall 통과.
  등식 제거/100은 위치 P95 52.65mm, 회전 0.24deg.
  등식 제거/0.03은 두 프로필 모두 7.35mm/0.32deg로 단일 QP와 비슷하다.
  샘플 최소거리 위반 0. 단일 QP처럼 된 것을 계층형 개선이라 부르지 않는다.
- 남은 항목: 이 조합은 원인 분리용, 미채택. wrist-only 다른 회전축에서
  불필요한 근위 움직임이 되살아나는지 확인해야 한다. 실제 G1/Quest 시험 없음.
  결과/네 조건 표는 `IK_RECORDED_COMPARISON_20260905.md` 참고.

## 2026-09-05 회전 단계 근위 비용 분리: 미채택

- 검토: combined에서 위치 진행 equality와 merit 검사는 원래대로 유지하고
  회전 QP의 proximal damping max만 100 -> 0.03으로 변경했다.
  min도 0.03이므로 해당 damping만 단일 QP와 같아진다. 위치 QP의 손목 비용
  0.50, 계층 equality 등은 여전히 다르므로 완전 동일 비용/구조 비교는 아니다.
- 코드 수정: 합성 도구에 `--proximal-cost` 추가. context에서 복원, live 변경 없음.
- 테스트: 두 프로필 x 두 방식 4회 완료, 관련 25 passed, compileall 통과.
  계층 회전 P95 10.96 -> 10.86deg, 위치 P95 6.87mm 유지.
  근위 누적 이동은 5/10mm에서 165.17 -> 182.34deg로 증가했다.
- 남은 항목: 이 입력에서 고비용만이 주요 원인이라는 가설은 지지되지 않는다.
  위치 QP가 만드는 진행 방향과 equality를 함께 검토할 수 있으나 자동으로
  제약을 완화하지 않는다. 비용 변경 미채택, 물리/Quest 실행 없음.
  결과 `logs/test_results/ik_combined_cost003_20260905.json`.

## 2026-09-05 merit acceptance 분리: 주요 오차 원인 아님

- 검토: 1mm target-error-band combined 조건에서 merit 승인 검사만 제외했다.
  QP 충돌/속도/관절 제약과 경로 충돌 검사는 유지했다. 실험용 factory만 변경.
- 코드 수정: 합성 도구 `--disable-merit-offline` 옵션 추가, 기본 false.
  live 제어에는 적용하지 않았다.
- 테스트: 4회 완료, 관련 24 passed, compileall 통과.
  두 프로필 모두 P95 위치 10.81mm / 회전 6.01deg로 기존 band와 같았다.
  local_limit 212 -> 0이나 최종 위치는 1.8659 -> 1.8576mm로 거의 동일했다.
  following/following_tangent라는 상태가 의미 있는 추종 개선의 증거는 아니다.
- 남은 항목: merit 검사는 정체 상태 표시에 기여했으나 큰 추종 오차의
  주원인으로 확인되지 않았다. 추가 허용량 조정 대신 단일 QP 기준으로
  비용/계층 차이를 분리할지 검토해야 한다. 실험 플래그 live 적용 금지.
  결과 `logs/test_results/ik_combined_no_merit_20260905.json`; 물리 실행 없음.

## 2026-09-05 목표 오차 band 실험: 미채택

- 검토: 순간 진행 band 대신 task-frame 선형 잔차 `e + J dq`를 제한했다.
  축별 bound는 `max(1mm, abs(e + J dq_primary))`이다. 범위 밖에서는
  1차 QP의 예측 잔차보다 악화하지 않는 복구 규칙이지 전체 실측 1mm 보장이 아니다.
- 코드 수정: 합성 도구에 `--target-error-band` 추가. 기본 off, live 변경 없음.
- 테스트: combined 4회, 관련 23 passed, compileall 통과.
  계층형 위치 P95 10.81mm / 회전 P95 6.01deg; 최대 위치 11.01mm,
  최종 1.87mm 잔류. 프로필별 local_limit 212, invalid_velocity 2회.
  단일 QP는 기존 7.35mm / 0.32deg로 이번 입력에서 더 좋았다.
- 남은 항목: 실험 미채택. 전역 오차 보장 아님. 비선형 acceptance와 band가
  충돌하는지 분석하지 않고 추가 허용량을 조정하지 않는다.
  `logs/test_results/ik_combined_target_band_1_20260905.json` 참고. 물리 출력 없음.

## 2026-09-05 순간 위치 진행 완화 실험: 적용 보류

- 검토: 위치 진행 equality를 축별 한 step 0.1 mm 부등식으로 대체하는
  오프라인 실험을 했다. 누적/절대 손 위치 허용량이 아니다.
- 코드 수정: 합성 비교기 안에 `UseProgressBand`와 `--progress-band-mm`만
  추가했다. context 종료 시 원래 solve 복원. 기본값 0은 기존 equality 유지.
  live 제어기, 속도/충돌 제약과 nonlinear acceptance는 변경하지 않았다.
- 테스트: combined 두 프로필 x 두 방식 4회 완료. 22 passed, compileall 통과.
  계층형 위치 P95 6.87 -> 28.19 mm, 회전 P95 10.96 -> 0.24 deg.
  최대 위치 오차 28.36 mm, 최종 hold 후 위치 오차 약 1.20 mm.
  샘플 최소거리 위반 0이나 추종 개선 성공으로 보지 않는다.
- 남은 항목: 이 완화를 live에 적용하지 않는다. 다음 후보는 목표에 대한
  절대 위치 오차 예산과 복귀 조건을 함께 둔 실험이며 아직 구현하지 않았다.
  G1/Quest 실행 없음. 결과 `logs/test_results/ik_combined_band_01_20260905.json`.

## 2026-09-05 combined QP 진단

- 검토: 위치+회전 합성 입력에서 첫 QP 쌍을 관찰하고 위치 진행 equality만
  제거한 shadow를 비교했다. shadow는 적분/명령에 적용하지 않는다.
- 코드 수정: 합성 비교기에 `--case combined --diagnose-qp` 선택 기능과
  30도 이하 오차도 포함하는 QP 통계를 추가했다. live 제어/제한 변경 없음.
- 테스트: 두 프로필 x 두 방식 4회 완료. 이전 비시간 통계 전부 동일.
  관련 21 passed. 프로필별 479쌍에서 위치 QP 속도 포화 76.62%,
  최종 손목 roll 포화 88.31%. shadow의 회전 예측 개선 비율 76.41%.
- 남은 항목: 위치 진행 보존 조건이 회전 추종을 제약한다는 국소적 근거다.
  다음은 위치 오차 허용량을 명시한 오프라인 완화 실험이며 아직 구현하지 않았다.
  속도/충돌 제한은 유지해야 한다. 실제 G1/Quest 실행 없음.
  결과: `logs/test_results/ik_combined_qp_diagnosis_20260905.json`.

## 2026-09-05 합성 동작 16회 비교 완료

- 검토: `compare_synthetic_ik.py`로 손목 X축/동시 이동/몸통 접근/급변 왕복을
  프로젝트 단일 QP 및 계층형, 5/10 및 20/40 mm에서 비교했다.
  upstream vanilla 기본값 비교가 아니다. 조건과 표는 `IK_RECORDED_COMPARISON_20260905.md`.
- 코드 수정: 오프라인 시험 도구와 입력 검증만 추가했다. live/물리 설정 유지.
- 테스트: 16회 완료, 관련 20 passed 및 compileall 통과. 샘플 최소거리 위반 0.
  combined 회전 P95는 단일 0.32 / 계층 10.96 deg로 계층형이 불리했다.
  guarded 몸통 복귀는 단일 79.98 mm 잔류, 계층 0.00057 mm 잔류였다.
  일부 QP 후보 거부가 있어 전체 정상 추종 성공으로 부르지 않는다.
- 남은 항목: combined 회전 비용/계층 제약과 guarded 단일 QP 복귀 거부를
  각각 분석한다. 비용이나 속도를 바로 변경하지 않는다. Quest/G1 시험 없음.
  결과: `logs/test_results/ik_synthetic_comparison_20260905.json`.

## 2026-09-05 회전 로그 오프라인 분석기

- 검토: 프레임 샘플과 마지막 패킷은 비동기이며 누락 송신을 복원하지 않는다.
  새 세션과 추적 손실 전후를 연속 회전으로 오인하지 않아야 한다.
- 코드 수정: `backend/tools/analyze_rotation_trace.py` 추가. source/semantic/heading
  변화량, 패킷 회전 변화, engage revision 및 anatomical 선택 변경을 요약한다.
  기본 5도 기준은 분석용이며 제어 제한이 아니다. 제어 코드 변경 없음.
- 테스트: 새 합성/CLI 시험 8개 포함 관련 39 passed. quaternion 부호,
  중복 패킷, 세션 변경, 추적 손실, 잘못된 입력 및 파일 출력 검증.
- 남은 항목: 실제 Quest 기록 분석과 Unity 컴파일/기록 검증은 아직 필요하다.
  G1/WSL/DDS runtime 실행 없음. 아래 명령은 로컬 파일만 읽고 결과를 저장한다.

```powershell
py -3.11 backend/tools/analyze_rotation_trace.py "Unity_G1_VR/Logs/rotation_trace_<실제파일명>.jsonl"
```

결과는 입력 옆 `.analysis.json`이며 콘솔에 절대 경로가 표시된다.
`events`는 관측 변화의 목록이지 자동 원인 판정이 아니다. 기존 CSV나
지난 backend capture는 입력 형식이 다르므로 이 도구에 직접 넣지 않는다.

## 2026-09-05 실행별 회전 provenance 준비

- 검토: 기존 CSV 소비자와 UDP 형식은 유지해야 한다. 프레임 관측과 패킷 전송은
  동시가 아니므로 동일 시각의 센서/명령 쌍으로 단정하면 안 된다.
- 코드 수정: Unity `Logs/rotation_trace_<UTC>_<GUID>.jsonl`을 실행별 생성한다.
  source wrist transform 회전, semantic 회전, anatomical 사용 여부, heading,
  engage frame revision/state, 머리 회전, 마지막 성공 송신 JSON을 기록한다.
  패킷 내부 session/sequence/timestamp로 반복 관측을 구분한다.
  기존 `live_quest_trace.csv`는 그대로 유지한다. 비용/속도/명령 형식 변경 없음.
- 테스트: Python 정적 계약 및 오프라인 회귀시험 수행. Unity 컴파일과 실제
  프레임 기록은 아직 검증하지 않았다. G1/WSL/DDS runtime 실행 없음.
- 남은 항목: 다음 Quest 실행에서 Console의 `G1 rotation provenance:` 경로를
  확인하고 같은 실행의 backend capture와 비교한다. 이 파일은 60 Hz 이하의
  프레임 샘플이므로 모든 송신 이벤트의 손 입력을 보장하지 않으며,
  `source_wrist`도 Unity transform 값이지 Quest 센서 내부 원시 데이터는 아니다.

## 2026-09-05 목표 회전 입력 경로 확인

- 검토: 손 anatomical frame -> 고정 heading -> Slerp -> basis 변환 ->
  engage 상대 회전 경로를 확인했다. 16:46 캡처의 원시 로그는 확인되지 않았다.
  Unity trace는 실행마다 덮어쓰며 현재 파일 수정 시각은 17:55:50이다.
- 코드 수정: `test_recorded_ik_hierarchy.py`에 고정 basis/clutch 회전 변화량
  보존 및 quaternion 부호 동등성 시험만 추가했다. live 동작은 변경하지 않았다.
- 테스트: 18 passed. 고정 변환 자체의 각도 증폭은 재현되지 않았다.
- 남은 항목: anatomical/fallback 전환과 기준 재설정은 원인 후보이지 확정이 아니다.
  다음은 실행별 동기화 입력 기록 준비다. 비용/속도를 더 조정하지 않는다.
  상세: `IK_RECORDED_COMPARISON_20260905.md`. G1/WSL/DDS 실행 없음.

## 2026-09-04 Vanilla Mink A/B 비교 경로

- `START_VR_HAND_TO_MUJOCO_VANILLA_MINK.bat`를 추가했다.
- Unity 입력, G1 모델, UDP 계약은 현재 제어기와 공유한다.
- IK만 `right_wrist_yaw_link` 단일 6D `FrameTask`를 사용하는 비교 기준이다.
- 로컬 충돌 프로필은 Mink 기본값인 minimum 5 mm / detection 10 mm다.
- 이 경로는 MuJoCo 비교 전용이며 Unitree publisher와 실제 로봇 명령이 없다.
- 기존 제어기가 UDP 5005를 점유하면 잘못된 A/B 실행을 막기 위해 시작을 거부한다.

## 1. Start here

For every new project conversation:

1. Work from `main`.
2. Read this file, [`ARCHITECTURE.md`](ARCHITECTURE.md), and [`REVIEW_LATEST.md`](REVIEW_LATEST.md).
3. Read the relevant review/remediation log before changing a reviewed defect.
4. Read [`CODE_GUIDE.md`](CODE_GUIDE.md) before changing a control path.
5. Inspect current HEAD and working-tree state before edits or cleanup.
6. Keep review findings, production changes and physical tests separately labeled.

Do not remove safety checks, loosen limits or change gains merely to make a test pass. Do not treat unit/static/simulation/transport tests as physical validation.

## 2. Repository checkpoint

```text
Repository : Y1048/Y
Primary branch : main
Old main archive : archive/old-main-20260820
```

`main` contains the former `refactor/teleop-architecture` work. The old refactor branch has been retired by the user. Do not target it in new automation or Codex instructions.

The default launcher remains:

```text
START_VR_HAND_TO_MUJOCO.bat
```

It launches the provenance-marking virtual-center entrypoint; `--baseline` uses the corresponding prototype entrypoint.

## 3. Current remediation/review state

The precision review records R1-R67 and remains incomplete. `REVIEW_LATEST.md` is authoritative for current status.

Key state:

- **R15/R35/R65** supported command provenance/freshness paths are source-mitigated and current-checkout CI is green.
- **R21/R51** supported LowState startup paths use per-run forward tokens and provenance/state/raw-odometry-bound prechecks.
- **R1/R3/R34/R64** have source fixes with offline regression coverage.
- **R2/R33/R41/R42** supported Gate 7/Jog collision/acquisition guards have offline regression coverage.
- **R46** is integrated into `g1_right_arm_jog.py`; planned/fault release share the SDK-neutral finalizer and incomplete evidence is fail-closed.
- **R40** supported physical paths bind current 29-joint/model/config evidence and raw `rt/odommodestate` position/quaternion back to startup, while requiring live base stability. Connected-G1 validation is still not done.
- **R50** supported paths supervise LowState IMU roll/pitch, motor temperature/fault/tau finiteness, and runtime base/odometry stability. Remote/deadman and CRC/integrity remain open until actual read-only SDK fields are verified.
- **R20/R24/R53** remain open. R27/R32 were locally remediated on 2026-09-05; see the dated remediation documents. Other supported-path and physical validation boundaries remain open as recorded.
- **R53** remains open. Camera validation and inspection-scene tests add shared generated-MuJoCo-XML writer surfaces to the existing model/evidence provenance finding.
- The bounded 308-file source inventory is fully read. This closes the review queue only; it does not close any R-number or authorize physical output.

## 4. Reconciled review coverage

Current canonical ledger:

```text
total current scoped files : 314
full_text_review           : 314
static_only                : 0
static check failures      : 0
```

Use:

```text
logs/review/20260903/source_checks.csv
logs/review/20260903/source_checks_summary_20260904.json
docs/CODE_INDEX.md
```

Latest review batches:

```text
docs/REVIEW_20260904_BACKEND_CORE.md
docs/REVIEW_20260904_BACKEND_SUPPORT.md
docs/REVIEW_20260904_BACKEND_DIAGNOSTICS.md
docs/REVIEW_20260904_BACKEND_DIAGNOSTICS_2.md
docs/REVIEW_20260904_BACKEND_DIAGNOSTICS_3.md
docs/REVIEW_20260904_LAUNCHERS.md
docs/REVIEW_20260904_CONFIG_AND_FRAME.md
docs/REVIEW_20260904_RECOVERY_MULTISTRATEGY.md
docs/REVIEW_20260904_REMAINING_EXPERIMENTS_AND_HARDWARE_HELPERS.md
```

The current bounded inventory has no remaining `static_only` files. This is
full-text review coverage, not a correctness or physical-validation claim.

## 5. Offline regression evidence

```text
.github/workflows/offline-provenance-regression.yml
Run 33824261133 : PASS
```

```text
.github/workflows/offline-safety-regression.yml
Run 33824155653 : PASS
```

These workflows are robot-offline and create no Unitree publisher, DDS endpoint, WSL runtime, Unity/Quest runtime or G1 connection.

## 6. Immediate next work

```text
1. Continue R20/R24/R53 remediation separately from completed review bookkeeping; R27/R32 are locally fixed.
2. Preserve the experimental TWIST2 R43-R45/R49 block before any further physical use.
3. Do not invent R50 remote/deadman/CRC checks; verify actual read-only Unitree SDK fields first.
4. Plan simulation/WSL integration checks with hardware output locked.
5. Reconcile CODE_INDEX/source_checks whenever scoped files change.
```

The first explicitly approved right-shoulder-pitch sign/response trial completed
on 2026-09-04. `Q` increased raw q and moved the arm backward; `Z` decreased raw
q and moved it forward. The run also included an absolute-zero `A` input, so it
is not a strict +/- one-step acceptance test. See
[`PHYSICAL_TEST_20260904_TWIST2_RIGHT_SHOULDER_PITCH.md`](PHYSICAL_TEST_20260904_TWIST2_RIGHT_SHOULDER_PITCH.md).
Do not expand physical testing without a new exact approval.

The captured 1,538-row full-body CSV now has a local-only visual replay at
`experiments/twist2_right_arm_manual/VIEW_PHYSICAL_CSV_MUJOCO.bat`. It maps
measured `q_0..q_28` directly to the canonical MuJoCo motor order and creates no
Unitree SDK, DDS, socket, publisher or robot command. Automated schema/model
validation passes. The human visual comparison on 2026-09-04 confirmed that
Q=backward and Z=forward match the physical G1 for right shoulder pitch. This
does not validate the remaining six arm axes or combined motion.

## 6A. Rejected Mink collision-boundary experiment

The temporary split-clearance experiment was rejected after the first
Quest/MuJoCo visual test. It allowed the torso/right-shoulder-yaw pair to reach
12.0018 mm and produced an abnormal arm posture. The rejected 20/12 mm split is
not active and the policy identifier remains `checked_local_lookahead_v1`.
Collision settings are selected explicitly. Local Unity/MuJoCo launchers now
default to Mink's 5/10 mm distances. The Gate 7 hardware launcher passes
`--hardware-display`, which always forces the guarded 20/40 mm profile. The
physical adapter still applies its independent 12 mm hard stop.

Do not reapply the rejected 20 mm QP / 12 mm post-QP split. Evaluate the
MuJoCo-only 5/10 mm profile before changing planner merit or tangent behavior,
and do not use it as an implicit physical-output policy. See
`docs/REMEDIATION_20260904_MINK_COLLISION_PROGRESS.md`.

A 2026-09-04 automatic wrist-only preference experiment was rejected and
removed after the first Quest test. Per-frame hand-motion classification
latched during ordinary motion; the 51.08-second active trace drove the elbow
from 55 to its 5-degree lower limit, reported collision limiting for 738 frames,
and produced 16.19 cm position-error p95. Do not restore that detector or its
target-position latch. The pre-existing wrist/proximal redundancy issue remains
open and needs a continuous objective or explicit operator mode, not this
discarded heuristic.

The first retest after this rollback did not exercise the local 5/10 mm
profile: PID 35608 was still bound to UDP 5005/5012 with the old explicit
`--collision-profile hardware-guarded` command. Runtime status showed the
torso/right-shoulder-yaw pair stopped at 20.0005 mm. The local stale process was
identified and closed; the next ordinary launcher run starts with 5/10 mm.

The subsequent 5/10 mm retest reached the true local boundary at 5.0011 mm.
Local simulation now uses `mink_local_detour_checked_v1`: a 5.5 mm QP reserve with
a 5.0 mm nonlinear validation floor, and geometry-safe tangent steps do not
need strict per-frame merit decrease. `hardware-guarded` remains monotone and
unchanged. Reconstructed first-step evidence changed the saved boundary pose
from zero motion to a 0.0764 degree maximum joint step without dropping below
5.0011 mm. This is local avoidance, not a global path planner; APF or a broader
path layer is still required if the short waypoint reaches another local minimum. The first
local detour is an 8 cm outward waypoint, held for at most 30 frames before the
unchanged operator target is retried. A measured-pose 180-frame offline
regression requires at least 120 moving frames, lower final target error and a
5 mm minimum checked clearance.

The latest ordinary `START_VR_HAND_TO_MUJOCO.bat` session
`b815b13bc45f4fe9be13eae1522544c8` accepted all 1,476 input packets and reported
no solver exception. Unity replay error and command delay stayed small, so the
trace does not support a UDP-loss or display-replay fault. However, 8 of 20
sampled wrist-control diagnostics were collision-limited, wrist-control error
reached 14.3 cm, and the final nearest pair was
`torso_link`/`right_shoulder_yaw_link` at 5.096 mm. Three tracking-loss
disengagements also created three different neutral references after re-engage.
The observed abnormal motion is therefore most consistent with the local
planner reaching the torso/shoulder collision boundary, compounded by tracking
loss and re-engagement; it is not evidence of an axis inversion or solver crash.

Do not retune collision distances, task costs or joint weights from this sparse
status log. Reproduce the same motion with
`tools/START_G1_GATE7_VR_RECORDING.bat`, stop the recorder cleanly, and run
`tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat` before changing planner behavior.
This recording path is local-only and creates no Unitree SDK publisher or robot
command.

That strict reproduction was captured as
`logs/captures/g1_mink_capture_20260904_160021.jsonl` and analyzed in
`logs/quality/g1_gate7_capture_quality_20260904_160527.json`. Its single active
segment lasted 45.906 seconds. All 1,387 active packets were retained;
collision limiting occurred in 95 packets, but position-error p95 was 19.453 cm
and orientation-error p95 was 78.029 degrees. The error started before the first
collision-limited packet: within about 1.06 seconds of engagement the operator
target moved 11.4 cm while the simulated wrist moved only about 2.8 cm. At the
end, after the target slowed, position error recovered to 0.896 cm. Target and
wrist total path lengths were also close (1.276 m and 1.269 m), which does not
support an axis inversion.

The dominant cause in this reproduction was the uniform limit used by that
capture: both proximal and wrist joints were capped at 0.08 rad/s
(4.584 deg/s). It is too slow for the recorded hand translation and especially
for wrist orientation tracking. Collision limiting adds short local holds but
does not explain the full active interval. Do not loosen collision clearance to
address this trace. The current local prototype now keeps one shared 0.16 rad/s
arm limit; no second velocity profile was introduced. The independently
guarded Gate 7 physical-output configuration remains locked and unchanged by
this local implementation.

The local Mink source passes each
collision-checked three-step IK look-ahead target through
`g1_mink_trajectory.StatefulMinkTrajectory`. The stateful Ruckig layer uses
0.32 rad/s2 acceleration and 1.28 rad/s3 jerk limits, then rechecks four
intermediate configurations against the same planner collision/joint policy.
These velocity, acceleration and jerk constants are defined once in
`run_mink_g1_right_arm_prototype.py`; the virtual-center path reuses them rather
than maintaining a separate tuning profile.
Tracking disengagement, external feedback rebasing, an unavailable IK step or a
rejected shaped path resets the trajectory to the current pose. This changes
only local Mink/MuJoCo target shaping; Gate 7 physical-output configuration and
authorization remain unchanged. A new Quest/MuJoCo visual capture is still
required before accepting the behavior.

The supported live path now uses a continuous wrist-first hierarchy rather
than the rejected hard-decoupling experiment. The position QP maps Quest
translation to `right_wrist_roll_link`; its finite damping prefers the proximal
four joints. The following orientation QP keeps the position task active and
normally assigns proximal/wrist damping costs of 100.0/0.015. Wrist joint margin
and the minimum singular value of the wrist rotation Jacobian produce a
continuous assist value. As assist rises from 0 to 1, proximal damping falls to
0.03. No right-arm DOF is hard-frozen, while joint, velocity and collision
constraints remain hard.

Both stages now solve at the same configuration with the same limits.
The second QP preserves the first QP's linear position displacement using
`J_position * delta_q_2 = J_position * delta_q_1`. Only the second velocity is
integrated; the old post-QP clipping and sequential integration are removed.
The final displacement is sampled for joint and collision validity, with a
position-first nonlinear acceptance check. The synthetic 25-degree wrist
roll/pitch/yaw cycles keep proximal excursion below 0.5 degree. A mixed 6D pose
known to be feasible under the vanilla model converges below 2 mm and 0.2 degree,
and a wrist pose with 1 degree limit margin enables measurable proximal assist.
The no-socket runtime packet regression also passes. The legacy two-argument
`FeasibleTargetPlanner.Plan(q, goal)` remains backward compatible.

The previously failing boundary-stop/inward-return regression now passes with
the same speed and collision limits. This is a specific numerical regression,
not a guarantee of convergence for every target or collision configuration.
The following experiment entries are historical; see the latest entry below.

### 2026-09-05 validation continuation

- 검토: 두 단계 QP의 경계 정지 회귀시험과 오프라인 시험 프로파일을 확인했다.
- 코드 수정: `verify_feasible_target.BuildPlanner`의 감지 거리를 명시적인
  `hardware-guarded` 40 mm로 맞췄다. 기존 최소 여유 20 mm와 혼재했던
  prototype 감지 거리 10 mm 참조만 제거했으며 live/hardware 설정은 변경하지 않았다.
- 테스트: planner pytest 13 passed / 1 failed. 프로파일 수정 후 경계 시험만
  재실행해도 동일하게 실패했다. 마지막 1초 최대 속도 0.160 rad/s로,
  시험 기준 0.008727 rad/s 미만에 도달하지 않았다. compileall은 통과했다.
- 남은 항목: 도달 불가능한 고정 목표에서 경계 운동의 수렴을 수정하고,
  안쪽 목표로 돌아오는 검증까지 완료해야 한다. 현재 시험은 앞선 정지
  assertion에서 종료되므로 복귀 성공을 이번 결과로 주장할 수 없다.
  현재 구조는 유한 비용과 단계별 수용 검사를 쓰는 두 단계 QP이며,
  엄밀한 lexicographic HQP 또는 모든 vanilla 도달 자세 보장을 뜻하지 않는다.
  G1/WSL/DDS 실행과 물리 출력은 수행하지 않았다.

### 2026-09-05 rejected acceptance-rule experiments

- 검토: 중간 위치/회전 단계의 개선 플래그가 최종 후보 개선을 보장하지 않는
  점을 확인하고 두 가지 승인 규칙을 오프라인에서 비교했다.
- 코드 수정: 실험 변경은 모두 원복했다. 최종 합산 오차 감소만 요구하면
  경계 정지는 통과하지만 안쪽 복귀 오차 30.56 mm, 혼합 목표 오차
  112.81 mm로 실패했다. 위치 감소를 우선 승인하면 경계 운동이 재발하고
  손목 한계에서 근위 보조가 0으로 막혔다. 두 방식을 live에 남기지 않았다.
- 테스트: 각 실험 planner suite는 12 passed / 2 failed.
  관련 policy/trajectory/compatibility/Unity suite는 26 passed 및
  11 subtests passed. 원복 후 손목 한계 근위 보조 시험 1 passed.
- 남은 항목: 기존 경계 정지 실패는 미해결이다. 다음에는 단순 merit 승인
  변경이 아니라 두 QP 사이의 작업 보존 제약과 공유 속도 예산을 QP 내부에서
  구성하는 방안을 검증해야 한다. VR 및 물리 동작 검증 완료로 취급하지 않는다.
  G1, WSL, DDS runtime은 실행하지 않았다.

### 2026-09-05 same-origin position-progress hierarchy

- 검토: 순차 적분과 단계 중간 개선 판단이 서로 다른 자세를 비교하던 구조를
  변경했다. 이번 보존 대상은 1단계 위치 Jacobian의 선형 변위다.
- 코드 수정: `PositionProgressConstraint`를 Mink 등식 제약으로 추가했다.
  두 QP는 같은 q와 hard limits를 공유한다. 속도 합산/사후 clipping과
  1 mm 단계별 허용 누적을 제거하고 최종 속도 하나만 검사·적분한다.
  위치 오차 개선을 우선하며 위치가 악화되지 않는 회전 개선을 승인한다.
  `Plan(q, goal)` legacy 경로와 local detour 경로는 유지했다.
- 테스트: 기존 관련 40개 및 11 subtests 통과. 추가 등식 보존/동일 선형화
  지점/공통 limits 검사와 두 단계의 NaN, Inf, 과속, 고정축 움직임 거부 검사 통과.
  최종 통합 42 passed / 19 subtests passed. 추가로 경계 정지/안쪽 복귀를
  5/10 mm와 20/40 mm 양쪽 프로파일에서 실행해 1 passed / 2 subtests passed.
  변경한 Python 파일의 compileall도 통과했다.
- 남은 항목: Quest에서 손목 단독 회전, 큰 위치 이동, 경계 이탈 후 복귀를
  시각적으로 확인해야 한다. 전역 도달성, 모든 시작 자세, 물리 G1 안전성은
  이 시험으로 보장하지 않는다. G1/WSL/DDS 실행이나 물리 출력은 하지 않았다.

### 2026-09-05 recorded offline comparison

- 검토: 원시 Quest가 아닌 저장된 목표를 동일한 중립 기준으로 정규화해 비교했다.
- 코드 수정: `backend/tools/compare_recorded_ik_hierarchy.py`와 단위시험을 추가했다.
  현재 제어 로직/비용/속도/출력 설정은 변경하지 않았다.
- 테스트: 단위시험 2 passed. 164343과 164644 기록의 단일 weighted QP 대
  현재 hierarchy 비교를 완료했다. 상세 조건/표는 `IK_RECORDED_COMPARISON_20260905.md`.
- 남은 항목: hierarchy 최종 수렴은 좋지만 164644 회전 P95가 126.18 deg로
  컸다. 164343에는 미세한 속도 상한 초과로 7프레임 거부가 있었다.
  회귀시험 통과가 기록 전체의 좋은 추종을 보장하지 않음을 확인했다.
  원시 입력/완전 vanilla/물리 동역학 비교로 해석하지 않는다.

### 2026-09-05 playback-speed isolation

- 검토: 164644의 동일 목표를 1/0.5/0.25배 시간축으로 비교했다.
- 코드 수정: 오프라인 도구에 playback-speed/mode 및 이동 구간 P95/포화
  통계를 추가했다. live 제어 설정은 변경하지 않았다.
- 테스트: 단위시험 7 passed, compileall 통과. 이동 중 회전 P95는
  128.02/94.63/48.41 deg, 속도 포화 비율은 64.08/49.72/37.25%였다.
  세 조건 모두 최종 수렴했으며 검사 샘플 충돌 위반은 0회였다.
- 남은 항목: 속도 영향은 있으나 유일 원인은 아니다. 다음은 고정 속도에서
  근위 damping 비용 비교와 미세 속도 초과의 QP 잔차 확인이다.
  자세한 조건/한계는 `IK_RECORDED_COMPARISON_20260905.md`의 추가 실험 참조.

### 2026-09-05 proximal damping ablation

- 검토: 164644의 1.0x 재생에서 회전 proximal damping 최대값만 100/10/1 비교.
- 코드 수정: offline CLI에 임시 비용 override 추가. 제어기 값은 수정하지 않았다.
- 테스트: 도구 12 passed. 비용 10/1의 회전 P95는 117.23/111.24 deg로
  현재 128.02보다 조금 줄었지만 근위 누적 이동은 증가했다.
  손목 단독 회귀시험의 첫 wrist-roll 주기에서 각각 3.70/5.25 deg 근위
  변화가 발생해 0.5 deg 기준을 실패했다. 두 후보는 미채택이다.
  기본 비용 100의 손목 단독 회귀시험 재실행은 통과했다.
- 남은 항목: 현재 최대 비용 100을 유지한다. 다음 분석은 위치/회전의
  속도 예산 경쟁 및 QP 수치 잔차이며 물리 속도 증가를 제안한 것이 아니다.
  상세 결과는 `IK_RECORDED_COMPARISON_20260905.md` 참조.

### 2026-09-05 QP budget observation

- 검토: 164644의 첫 QP 쌍 3171프레임을 관찰했다. 위치 QP에서 손목 포화는
  0%, 최종 회전 QP에서는 wrist roll/pitch/yaw 40.30/34.75/33.93%였다.
  위치가 손목 속도를 모두 소모한다는 설명은 이 기록에서 지지되지 않는다.
- 코드 수정: offline `--diagnose-qp`만 추가. 위치 보존 등식을 제거한 shadow는
  진단용으로만 풀고 적용하지 않는다. live 설정은 그대로다.
- 테스트: 단위시험 13 passed. 진단 전후 기존 비시간 통계 모두 동일.
  회전 오차 30deg 초과 959프레임 중 shadow가 개선한 비율 60.27%,
  1-step 예측 차이 중앙값/P95 0.003427/0.084462 deg. 전역 개선 보장 아님.
- 남은 항목: 목표 급변 구간과 회전 오차 대조 및 미세 QP 잔차 분석.
  상세 조건/한계는 `IK_RECORDED_COMPARISON_20260905.md` 참조.

### 2026-09-05 target rotation event trace

- 검토: 164644에서 목표 5deg 이상 step 16개가 두 구간에 집중됐다.
  20.9~21.5초 목표 회전 누적 166.12deg에 로봇은 12.74deg 움직였고,
  21.5초 오차 158.60deg였다. 구간 상태는 following이며 연동해제 아님.
- 코드 수정: offline frame trace/event summary 추가. 제어 설정은 그대로다.
- 테스트: 단위시험 14 passed, compileall 통과. 기존 비시간 지표 동일.
- 남은 항목: 처리된 목표의 급변 원인이 실제 손/추적복구/기준변환 중 무엇인지
  현재 기록만으로는 미확정. 원시 입력과 목표 생성 경로를 확인한다.
  `IK_RECORDED_COMPARISON_20260905.md`에 조건/한계/결과 경로 기록.

## 7. Hardware boundary

- Repository hardware authorization remains locked.
- Do not assume G1 Ethernet, WSL DDS, Unity, Quest or any publisher is currently running.
- No physical command, G1 file mutation, service/mode change or administrator network change is authorized by this handoff.
- Runtime-base changes add only read-only `rt/odommodestate` subscriptions on supported physical paths; they have not been executed against G1 in this remediation session.
- Preserve calibration and intentional local work; inspect Git state before cleanup/reset/restore.

## 8. Historical handoff

Historical detail remains in [`CHAT_HANDOFF_HISTORY_20260903.md`](CHAT_HANDOFF_HISTORY_20260903.md). Use this current handoff and `REVIEW_LATEST.md` first.





2026-09-07 Mink audit 공급기 종료 후 확인: seed_exists=False, directory_entries=0.

### 2026-09-10 small-signal PD sweep replacement

- 검토: 회수한 `g1_pd_backward_abort_20260910/policy.csv`의 대형 전방 reach는
  첫 Kp 40 후보에서 22번 관절 오차가 50 Hz 기록상 0.233 rad까지 증가했고,
  500 Hz 검사에서 0.25 rad를 넘어 중단됐다. 사용자가 뒤로 넘어지려는 경향을
  관찰했으므로 이 궤적은 PD 식별 입력으로 계속 사용하지 않는다.
- 코드 수정: `--pd-sweep-trial`을 준비 자세 기준 22번 관절만
  `+8 deg -> -8 deg -> ready`로 움직이는 3회 궤적으로 교체했다. 5차
  smoothstep 구간은 최고 20 deg/s, 최고 60 deg/s^2를 수식으로 제한하며,
  나머지 28개 관절 목표는 입력 baseline을 그대로 유지한다. 기존 단일
  `--pd-reach-trial` 구현은 보존했다.
- 오프라인 검증: C++17 경고 옵션 빌드와 실행 통과. 0.5 ms 간격 전 구간에서
  ±8 deg를 지나치지 않고, 속도/가속도 제한을 넘지 않으며, 22번 외 목표가
  정확히 유지되고, 역행 clock 및 비유한 baseline이 거부됨을 확인했다.
  관련 Python 회귀시험 7개도 통과했다.
- G1 반영: 별도 후보 폴더 `/home/unitree/g1_mink_cycle_compare_20260909`에
  소스와 새 헤더를 전송하고 해당 ARM 타깃을 `--clean-first`로 컴파일했다.
  실행 파일 SHA-256은
  `f62c025358786e7bfbe82bf8248f1a9b656005585211a3a456f33df8a985926b`이다.
  모터 프로그램은 실행하지 않았다.
- 남은 항목: Robot/All launcher 차단은 유지한다. 이 작은 궤적도 실제 G1
  안전성 검증이 아니며, 다음 물리 시험은 지지와 자세 관찰 조건을 다시 갖춘 뒤
  22번 단독 Kp 40/48/56, Kd 5 기록부터 시작한다.

### 2026-09-10 verified Regular handoff candidate

- FSM ID는 전환 명령으로 사용하지 않는다. `SelectMode("ai")`가 서비스 전환
  요청이고, 시작 시 기록한 Regular FSM 500/501은 전환 결과 검증에만 쓴다.
- 작은 PD sweep 완료에만 후보 종료 절차를 연결했다. 마지막 목표를 계속
  송신하면서 상체 관절 15..28의 목표 오차와 속도가 각각 0.1 rad,
  0.1 rad/s 이내로 1초 유지되는지 확인한 뒤 500 Hz writer를 완전히
  정지한다. 그 다음에만 `SelectMode("ai")`를 호출하고 `CheckMode==ai`,
  원래 FSM ID, 유효한 LowState가 다시 1초 연속 유지돼야 완료한다.
- 오프라인 검증: handoff gate 및 작은 궤적 C++ 시험 2개와 Python 회귀시험
  8개가 통과했다. writer 정지가 `SelectMode("ai")`보다 앞서는 순서도
  회귀시험으로 고정했다.
- G1 후보 폴더에 소스를 전송하고 ARM 컴파일/링크를 완료했다. 현재 ELF
  SHA-256은 `b2dc0cdea51bea9013ca133b377efcdcd92e9ecd06e2e042c440b2a5ea85d9cc`이다.
  실행 중인 해당 제어기는 없었고 모터 프로그램은 실행하지 않았다.
- 남은 항목: 공개 Unitree 예제는 저수준 writer에서 Regular로 돌아가는
  무중단 handoff를 규정하지 않는다. 따라서 이 순서는 아직 물리 검증 전 후보이며
  Robot/All 실행 차단을 해제하지 않았다. 실패 시 writer가 이미 멈춘 뒤이므로
  무조건 무토크 전환이 없다고 보장할 수 없다.

#### Regular handoff failure containment

- `SelectMode("ai")`의 반환값만으로 소유권을 추정하지 않는다. 실패 또는 10초
  검증 timeout 뒤 `CheckMode`가 성공하고 service 이름이 비어 있을 때만 기존
  publisher로 마지막 TWIST2 위치 hold를 다시 시작한다.
- `ai` 또는 다른/알 수 없는 service가 관찰되면 LowCmd를 재개하지 않는다.
  owner overlap을 막은 채 `CheckMode`, 시작 FSM ID, LowState를 계속 확인하며
  프로세스도 종료하지 않는다. 뒤늦게 1초 연속 검증되면 정상 종료한다.
- 관련 Python 회귀시험 9개가 통과했고 ARM 컴파일/링크도 통과했다. 최종 후보
  SHA-256은 `28c16d62671445571d04711bb1a2e881a070cdf01703b171faa4c1ac36ecb1e7`이다.
  모터 출력은 실행하지 않았고 Robot/All 차단은 유지한다.

#### Handoff-only transition probe preparation

- `--handoff-only-trial`을 추가했다. 29개 관절의 최초 측정 목표를 유지하며
  1초 capture와 4초 TWIST2 blend 후 바로 verified Regular handoff를
  요청한다. 팔 궤적, UDP 입력, PD gain override는 사용하지 않는다.
- PD 옵션 파서는 이 모드의 추가 gain 인수를 거부한다. C++ 옵션 시험 1개와
  Python 제어 흐름 회귀시험 10개가 통과했다. launcher Check도 파싱됐으며
  Robot/All 차단은 그대로다.
- G1에 최종 C++와 옵션 헤더 전송은 완료됐지만 `--clean-first` ARM 빌드 중
  SSH가 끊겼다. 이어진 SSH와 ping 모두 timeout이므로 최종 링크와 새 해시는
  확인되지 않았다. 기존 launcher 해시를 새 결과라고 갱신하지 않았다.
- 모터 프로그램은 실행하지 않았다. 다음에는 G1 유선 연결이 돌아온 뒤 원격
  빌드 상태를 읽고, 필요하면 빌드만 재개하여 ELF 해시를 확정한다.

#### Offline handoff concurrency review while G1 charges

- handoff settle 판정이 writer 전용 `last_target_`을 직접 읽던 데이터 경쟁
  가능성을 제거했다. 이제 mutex로 발행되는 완성된 `WriterFrame` 스냅샷의
  `target`과 측정 LowState를 비교하며, 아직 유효한 frame이 없으면 안정으로
  판정하지 않는다.
- WriterFrame 동시 발행/읽기 10,000회 일관성 시험, PD 옵션, Regular gate,
  small-signal 궤적 C++ 시험이 통과했고 Python 제어 흐름 시험 10개도 통과했다.
- 공개 SDK 헤더에는 `RecurrentThread` 종료자 선언만 있고 저수준 writer에서
  `SelectMode("ai")`로 복귀하는 완료 계약은 제시되지 않는다. `writer_.reset()`이
  실제 ARM SDK 빌드에서 종료 동기화되는지는 G1 연결 복구 후 소스/링크 결과와
  최소 handoff-only 시험에서 확인해야 한다.
- G1이 충전 중이고 192.168.123.164가 응답하지 않아 이 최종 동시성 수정본은
  아직 원격 빌드되지 않았다. launcher는 계속 차단돼 있으므로 이전 해시가
  물리 실행으로 이어지지 않는다.

### 2026-09-14 G1 camera PiP enlargement

- 사용자 요청에 따라 Unity의 시야 고정 G1 카메라 PiP 선형 크기를 기존보다
  약 1.67배 확대했다. 320x240 캔버스, 4:3 비율, CenterEye 기준 전방 0.8 m,
  중앙 고정 위치는 유지하고 `DefaultCanvasScale`만 0.00075에서 0.00125로
  변경했다. 표시 폭은 약 0.24 m에서 0.40 m, 수평 시야각은 약 17도에서
  28도로 증가한다.
- 기존 TCP5011 수신, JPEG 검증/디코딩, 상태등, stale timeout 및 같은 파일의
  frame-assembly timeout 변경은 건드리지 않았다. G1/WSL/DDS/카메라 브리지와
  물리 출력은 실행하지 않았다.
- 검증: Unity 6000.5.4f1 batch validator에서 확대값 assertion을 포함한 전체
  `G1TeleopBatchValidator.ValidateTeleoperationProject`가 통과했다. 실제 G1이나
  카메라 브리지는 실행하지 않았다.
- APK 빌드는 기존 `AndroidManifest.xml`이 요구하는
  `Theme.AppCompat.DayNight.NoActionBar` 리소스가 Gradle 의존성에 없어
  `processReleaseResources`에서 실패했다. 확대 코드의 C# 컴파일 실패가 아니며,
  빌드 과정이 바꾼 product name/application identifier는 원래 값으로 복구했다.
- 남은 항목: 기존 AppCompat 패키징 문제를 별도로 해결한 뒤 APK를 만들고,
  Quest에서 실제 크기와 시야 방해 여부를 확인한다.
- 후속 표시 조정: 사용자 요청에 따라 스케일을 0.00125에서 0.00135로 한 번 더
  키우고 CenterEye 기준 y를 0에서 -0.04 m로 내렸다. 최종 폭은 약 0.43 m,
  수평 시야각은 약 30도이며 최초 설정보다 선형 크기가 약 1.8배다.
- 후속 조정의 transform assertion과 `git diff --check`는 통과했다. 동일 프로젝트가
  사용자 Unity Editor에서 열려 있어 별도 batch validator 재실행은 project lock으로
  종료됐으며, 이 최종 크기와 위치의 Quest 시각 확인은 아직이다.
- 추가 확대 요청으로 최종 스케일을 0.00150으로 변경했다. 시선 0.8 m 앞에서
  폭 약 0.48 m, 수평 시야각 약 33도이며 최초 0.00075 설정의 2배다. 아래쪽
  오프셋 -0.04 m와 4:3 비율은 유지했다.
- 다시 요청된 20% 확대를 적용해 최종 스케일은 0.00180이다. 폭 약 0.576 m,
  수평 시야각 약 40도이며 아래쪽 오프셋 -0.04 m와 4:3 비율은 유지했다.

### 2026-09-14 abstract Unity operator environment

- 사용자 요청에 따라 기존 기본 하늘/평지 표시를 특정 제어실을 묘사하지 않는
  추상적인 실내형 공간으로 교체하는 `G1AmbientOperatorEnvironment`를 추가했다.
  어두운 청회색 바닥/벽/천장, 중앙 플랫폼과 청록색 조명선으로만 구성하며
  `G1HeadLockedCamera`가 Play 시작 시 런타임 생성한다.
- 생성된 15개 시각 요소에서는 collider를 모두 제거했다. 기존 G1, 손 추적,
  Mink/UDP, 카메라 TCP 경로와 물리 제어 값은 변경하지 않았다.
- Unity 6000.5.4f1의 기존 Bee response 파일을 복제해 새 런타임 스크립트를
  포함한 `Assembly-CSharp`와 갱신된 `Assembly-CSharp-Editor`를 별도 Temp 출력으로
  컴파일했으며 둘 다 exit 0이었다. 사용자 Unity Editor가 프로젝트를 열고 있어
  batch scene validator와 Quest 시각 확인은 아직이다.

### 2026-09-14 Unity keypad velocity + Mink right-arm integration

#### 2026-09-15 continuous velocity-policy ownership restored locally

- 목표를 Unity 숫자 키패드로 velocity policy의 전후/좌우/회전 명령을 만들고
  기존 Mink 오른팔과 한 LowCmd owner에서 합치는 것으로 다시 고정했다.
- `G1_VELOCITY_CONTINUOUS_GAIT=1`을 통합 target에 적용했다. 하체 0..11은
  시작부터 velocity policy가 계속 소유한다. 키 해제나 250 ms UDP timeout은
  목표만 `[0,0,0]`으로 만들며 gait phase와 능동 균형 출력을 끊지 않는다.
- 팔 `udp_ready` 전에는 operator velocity target을 0으로 유지하지만 하체
  velocity policy는 계속 실행한다. 따라서 제자리걸음은 허용되며 완전한 정지는
  이번 후보의 완료 조건이 아니다.
- 검증: Python keypad relay 8개 PASS, C++ velocity packet contract PASS,
  leg-policy state-machine test PASS, continuous-owner source contract PASS.
  전체 x86 CMake configure는 성공했으나 로컬 WSL에 Unitree SDK의
  `unitree/idl/hg/LowCmd_.hpp`가 없어 main translation-unit compile은 불가했다.
- G1 ARM build, 전송 및 물리 실행은 하지 않았다. 이전 fixed-joint 전도
  실행본과 dual-policy 후보를 보존했고 Robot/All 실행 차단도 유지했다.
- 이후 사용자 지시로 패키지를 G1의 기존 새 통합 프로젝트에 전송했다. 적용 전
  소스, ELF, SHA256SUMS는
  `source_backups/pre_continuous_keypad_20260915`에 보존했다. ARM compile/link가
  성공했고 새 aarch64 ELF SHA-256은
  `18abaa4335f1135e9f72908b8521ee5a81d9e2ed38a56d2ffcb4328dd90d4876`이다.
  원격 C++ 시험 `leg policy switch`와 `velocity keypad contract`가 직접 실행
  PASS했고, compile flags에서 `G1_VELOCITY_CONTINUOUS_GAIT=1`을 확인했다.
  갱신한 원격 `SHA256SUMS`의 ELF, 핵심 소스, 두 policy, 실행 스크립트가 모두
  OK였다. 빌드와 검사 중 DDS/LowCmd 실행 및 모터 출력은 없었다.
- 통합 물리 실행은 여전히 하지 않았으며 Windows Robot/All 차단도 유지한다.
- 원격 continuous-gait ELF와 해시 검증이 끝난 뒤 Windows
  `START_G1_VELOCITY_MINK_KEYPAD`의 Robot/All 차단을 해제했다. Robot 명령은
  원격 `SHA256SUMS` 전체 검사가 통과한 뒤에만 실행 스크립트로 진행한다.
  `-Mode All -Preview`에서 Input, ArmRelay, VelocityRelay, Camera, Robot 다섯
  창과 동일 token 전달을 확인했고 `-Mode Check`도 exit 0이었다. preview/check는
  DDS나 모터 출력을 만들지 않았다.
- 첫 물리 확인 순서는 지지대와 Regular 시작 상태에서 배치파일 실행, 다섯 창
  유지, Robot SSH 로그인 후 대문자 `P`, 0속도 제자리 gait 확인, Unity Play,
  짧은 `8` 전진 입력, 키 해제 후 다시 0속도 gait 확인이다. 이 순서의 실제
  균형과 방향 convention은 아직 검증되지 않았다.
- 종료 질문을 검토하면서 이 후보에도 검증된 LowCmd successor handoff가 없음을
  재확인했다. `Q`/Ctrl+C는 safe arm return 후 현재 owner의 hold를 유지할 뿐
  정상 종료가 아니고, 창을 닫으면 지지력이 사라질 수 있다. 종료 불가능한 물리
  실행을 열어두지 않기 위해 같은 turn에서 Robot/All을 다시 차단했다. 위의
  차단 해제 기록은 중간 상태이며 현재 최종 상태는 **차단**이다.
- 사용자가 현재는 정상 AI handoff보다 Unity keypad 기능 구현을 우선하며 종료 시
  damping 전환을 허용한다고 명시했다. 이에 Robot/All 차단을 다시 해제했다.
  현재 시험 종료는 AI/Regular 복귀가 아니라 Robot 프로세스 종료 후 damping을
  사용한다. 이 선택은 기능 시험용이며 검증된 정상 운용 종료로 기록하지 않는다.
- Unity Play 재시작 후 keypad가 멈춘 현상을 진단했다. 송신 컴포넌트 Awake는
  실행됐지만 처음에는 main-frame Update 패킷이 나오지 않았고, 이후에는 빠른
  Play 재시작으로 session UUID가 바뀌자 PC relay가 종료됐다. Windows Editor의
  keypad 송신을 Unity frame/XR 초기화와 독립된 50 Hz timer heartbeat로 바꾸고
  `GetAsyncKeyState`로 NumLock 양쪽 입력을 받게 했다. PC relay는 새 session의
  sequence 0만 restart로 허용하고 같은 session의 비단조 sequence는 계속
  거부한다. Python relay 시험 10개가 PASS했다.
- 수정된 Unity Assembly-CSharp.dll은 10:54:33에 컴파일됐고 오류가 없었다.
  갱신 relay를 현재 token으로 재시작한 뒤 localhost 5016 수신과 새 Unity
  session `a285e70b8961444f9ac52702b6ed5a1f`, sequence 0, velocity `[0,0,0]`
  heartbeat 수신을 확인했다. 이는 PC 입력 경로 확인이며 G1 이동 검증은 아니다.

- 기존 G1 프로젝트
  `/home/unitree/g1_velocity_continuous_gait_backup_20260914`와
  `/home/unitree/g1_mink_cycle_compare_20260909`를 변경하지 않고, 새 프로젝트
  `/home/unitree/g1_velocity_mink_keypad_right_arm_20260914`를 만들었다.
- 새 C++는 `g1_velocity_12dof_motion.pt` 하체 policy가 관절 0..11을,
  기존 Mink cycle 경로가 오른팔 22..28을 맡으며 `rt/lowcmd` publisher는
  하나뿐이다. 기존 왼팔 terminal keyboard 입력은 포함하지 않았다.
- Unity에 `G1KeypadLocomotionUdpSender`를 추가했다. Play 중 숫자 키패드
  8/2=전후, 4/6=좌우, 7/9=좌우 회전, 5=정지이며 동시 전후/좌우 입력은
  정규화된 대각 이동이다. Unity는 localhost UDP 5016만 사용한다.
- 새 Python relay는 `g1.velocity.keypad.v1` 패킷의 provenance, 유한값,
  범위, session/sequence와 중복 JSON key를 검증해 G1 UDP 5017로 전달한다.
  G1 수신기는 같은 token/source IP를 검증하며, 250 ms 입력 timeout에서는
  하체 목표 속도를 0으로 만든다. Mink는 기존 localhost 5008 -> G1 5014다.
- 실행 진입점은 `tools/START_G1_VELOCITY_MINK_KEYPAD.bat`이다. All 모드는
  Input, arm relay, velocity relay, camera, Robot 창을 열며 Robot 창에서 SSH
  로그인과 `P`는 사용자가 직접 수행한다.
- 검증: Python relay unit test 6개 통과, 순수 C++ contract 시험 통과,
  Unity 6000.5.4f1 response-file C# compile exit 0, PowerShell All preview 성공,
  source static check에서 LowCmd publisher=1/left keyboard=0이었다.
- G1 ARM CMake build/link가 완료됐고 ELF는 aarch64다. binary SHA-256은
  `d0ecc96f57bbe6f8c123cb22b7a8b494ab75f8b50d68cddff4ac8b37df72aa87`,
  velocity policy SHA-256은
  `cf668f75b90d1abf73d2b87612a6e76bccc61ff7e083b63582d3f6aaa3c1759d`다.
  G1 실행 중인 관련 프로세스가 없음을 확인했고 모터 프로그램은 실행하지 않았다.
- 남은 검증: Unity Play에서 키패드 localhost 패킷과 정지/대각 입력을 확인한 뒤,
  별도 물리 시험에서 하체 방향 convention과 오른팔 동시 추종을 확인한다.
- 최초 통합 launcher 시험에서 Input 창이 일반 live 모드로 시작되어 ArmRelay가
  `cycle provenance/profile`로 종료됐다. 새 launcher의 Input에도 공유 token을
  전달하고, `G1_CYCLE_RELAY_TOKEN`, 고정 MuJoCo 3.12 runtime,
  `--live-cycle-candidate --upstream-mink-collision --speed-profile today`를 적용했다.
  이는 PC Input 시작 구성 수정이며 G1 바이너리와 물리 제어 코드는 바꾸지 않았다.
- 다음 실행에서 Arm/Input/Robot은 살아 있었지만 velocity relay Python만 종료되고
  UDP 5016 bind가 사라졌다. G1이 UDP 5017을 bind하기 전에 Unity가 송신하면
  Windows가 다음 `recvfrom`에 WinError 10054를 전달하는 경우를 처리하지 못한
  것이 원인이었다. relay가 10054를 무시하고 Robot 시작을 계속 기다리도록 했고,
  수락한 velocity가 바뀔 때 `[KEYPAD] velocity=(...)`를 출력하게 했다.
- 10054 처리만 추가한 첫 재시작도 즉시 종료되어, Arm relay와 동일하게
  localhost:5016 수신 socket과 G1:5017 송신 socket을 분리했다. Windows에서
  송신 결과의 ICMP 오류가 다음 localhost `recvfrom` 상태를 오염시키지 않는다.
- 첫 물리 시작에서 continuous-gait compile define 때문에 0속도에서도 하체
  gait phase가 계속 돌아 팔 measured-ready 안정 조건 진입을 방해했다. 통합
  target에서는 이 define을 제거하고, `alpha==1`이며 G1 arm target이 최초
  `udp_ready`를 만든 뒤에만 Unity keypad 속도를 policy에 허용한다. 이후에는
  키를 누르면 gait가 시작되고 0명령이면 non-continuous phase clock의 정지
  cycle을 거쳐 멈춘다. 원본 lower-body backup은 변경하지 않았다.
- ready-gated 변경본은 G1에서 ARM compile/link를 통과했다. 새 aarch64 ELF
  SHA-256은 `3726636bcfcec217f7ab962a683cb8b12d0eab5c721e3172e36073189ab5c1aa`다.
  직전 continuous-gait 바이너리는 같은 새 프로젝트의
  `build/g1_velocity_mink_keypad_right_arm_continuous_gait_backup`으로 보존했다.
  배포 중 controller 프로세스가 없음을 확인했고 새 바이너리는 실행하지 않았다.
- 이 변경본의 첫 물리 시작은 키패드 상태가 계속 `[0,0,0]`인데도 하체가
  움직였고 13.48초에 soft-limit hold로 들어갔다. 회수한 674-row CSV에서
  joint 5 right ankle-roll q=0.211391 rad, soft upper=0.2118 rad,
  policy target=0.199648 rad, action=0.798591가 마지막 표본이었다. 다음 writer
  주기에서 경계를 넘은 것으로 판단된다. 따라서 0속도 policy inference 자체를
  정적 hold로 사용할 수 없다는 실제 측정 근거가 생겼다.
- 후속 후보는 최초 locomotion 전까지 captured leg target을 유지한다.
  keypad motion 또는 진행 중 gait phase에서만 velocity-policy leg target을
  적용하고, phase가 정지하면 마지막 안전 leg target을 유지한다. 모든 leg
  target margin은 0.08 rad, ankle-roll 5/11은 기존 lower-body static helper와
  같은 0.12 rad로 강화했다.
- 이 후속 후보를 새 통합 프로젝트에만 전송하여 G1 ARM compile/link를 완료했다.
  `G1_VELOCITY_CONTINUOUS_GAIT`가 compile flags에 없고
  `G1_VELOCITY_POLICY=1`만 있음을 확인했다. 새 aarch64 ELF SHA-256은
  `13932c7c8a28e284cef5c4ae39d228bf1150f6a0bceb73cda1b53148ca26663e`다.
  직전 ready-gated 바이너리는
  `build/g1_velocity_mink_keypad_right_arm_pre_zero_hold_20260914`로,
  최초 continuous-gait 바이너리는 기존 backup 이름으로 보존했다.
  원격 `SHA256SUMS` 검증은 전체 OK였고 관련 controller가 실행 중이지 않음을
  배포 전후 확인했다. 모터 프로그램은 실행하지 않았다.
- 남은 검증: 이 빌드는 정지 상태에서 policy leg target 대신 captured/last-safe
  leg target을 사용하는 첫 물리 후보다. G1의 실제 정지 유지, 첫 키 입력 시
  보행 시작, 키 해제 후 정지와 오른팔 동시 추종은 아직 검증하지 않았다.

#### Fixed-joint idle physical failure and launcher block

- 사용자가 지지대를 설치하고 Regular 상태에서 통합 launcher를 시작했다.
  키패드와 VR engage 입력 없이 Robot 창에서 `P`를 입력하자 로봇이 즉시
  앞으로 넘어졌다. 지지대가 낙상을 막았고 사용자는 G1 전원을 꺼 배터리를
  충전했다. 이 실행은 성공한 정지 유지 시험이 아니다.
- Unity keypad relay의 마지막 상태는 velocity `[0,0,0]`이었다. 이번 후보는
  그 상태에서 하체 0..11을 captured joint-position target으로 고정해
  velocity policy 출력을 대체했다. AI motion service handoff 직후 능동 균형
  policy가 사라진 것이 전도의 설계상 원인으로 판단된다.
- 연결 복구 후 원격 실행 폴더
  `g1_twist2_trial_1789368216703978_14661`의 CSV/run/result를 회수했다.
  `result.json`은 256개 50 Hz 표본, 5.12초에
  `RuntimeError: IMU roll/pitch limit`을 기록한다. pitch는 0.04580에서
  0.34669 rad로 증가했고 roll 최대값은 0.01408 rad였다. 하체 desired target은
  처음부터 끝까지 변화량 0이었으나 실측 leg q 최대 drift는 0.25881 rad,
  실측 leg dq 최대값은 0.58469 rad/s였다. capture feedforward 최대값은
  13.0078 Nm에서 alpha와 함께 0 Nm로 사라졌다. 이는 고정 관절 목표가
  균형 policy를 대신하지 못했다는 해석과 일치한다.
- 회수한 `policy.csv` SHA-256은
  `334421c02959ad71a30d43094f3bf1d1d287b74d7cd63fb2493be125d3dbd338`,
  `run.json`은
  `f53b56189c7e38445c0ce930ad4cc3241fdd7a6c7c23fec116cd993189b3c2e7`이며
  원격 `result.json` 내부 값 및 직접 계산값과 일치했다.
- 동일 물리 실행을 막기 위해
  `tools/START_G1_VELOCITY_MINK_KEYPAD.ps1`의 `All`과 `Robot`을 즉시 차단했다.
  `Check`는 계속 사용할 수 있고 차단 회귀 확인에서 All/Robot exit 1,
  Check exit 0이었다. 사고 후 관련 PC Input/Relay/Robot 프로세스와
  UDP 5005/5008/5016 점유가 모두 종료된 것도 확인했다.
- 다음 실행의 진단 손실을 막기 위해 child mode 콘솔을
  `logs/test_results/velocity_mink_console/<timestamp>_<mode>.log`에 transcript로
  남기도록 했다. 현재 Robot 차단보다 뒤에서만 동작하므로 이 변경이 물리
  실행을 다시 허용하지는 않는다.

#### Dual-policy idle replacement prepared locally

- 고정 joint target idle을 제거했다. 시작/idle에서는 기존
  `twist2_1017_20k_torchscript.pt` static-stand policy가 하체 균형 출력을
  계속 만든다. measured-ready 이후 nonzero keypad 입력이 들어오면 4초 동안
  velocity policy로 blend하고, zero-command gait가 정지 phase를 마치면 6초
  동안 static-stand policy로 되돌아간다. 전환 중 취소와 재시작도 처리한다.
- 두 policy 모두 DDS handoff 전에 load/warm-up하고, 기존 단일 full-body
  `rt/lowcmd` publisher가 다리, waist hold, Mink 오른팔을 계속 합친다.
  하체 0.08 rad 및 ankle-roll 5/11의 0.12 rad command margin은 유지한다.
- 오프라인 검증: 전체 G1 C++ translation unit의 WSL x86 syntax-only compile,
  leg-policy 상태 전환 C++ 시험, velocity keypad contract C++ 시험,
  Python relay 8개 시험, 단일 LowCmd publisher/static-policy 사용/no-fixed-hold
  source contract와 `git diff --check`가 모두 통과했다.
- 연결 복구 후 이 dual-policy 후보를 새 통합 프로젝트에 전송하여 ARM
  compile/link를 완료했다. 새 aarch64 ELF SHA-256은
  `a8810309f3955a2b0ff67b506cd095cc38870586d13959309069b7a6d4ac0782`다.
  원격 CTest의 `leg_policy_switch`, `velocity_keypad_contract` 2개가 통과했고,
  velocity/static-stand 두 policy와 source/header/CMake/ELF를 포함한 원격
  `SHA256SUMS` 전체 항목도 OK였다. 로컬과 원격 핵심 source hash가 일치한다.
- 사고 바이너리 `13932c7c...26663e`는
  `build/g1_velocity_mink_keypad_right_arm_fixed_joint_unsafe_do_not_run_20260914`
  로 격리 보존했다. 그 전 ready-gated 및 continuous-gait 바이너리도 기존
  backup 이름으로 유지했다. 배포 전후 관련 controller가 없음을 확인했고
  새 바이너리는 실행하지 않았다.
- `START_G1_VELOCITY_MINK_KEYPAD`의 All/Robot 물리 실행 차단은 유지한다.
  dual-policy의 ARM 빌드와 offline/compile 검증은 실제 균형 또는 정책 간 전환
  검증이 아니다. 다음 물리 단계는 지지 상태에서 **키 입력 없는 static-stand
  takeover만** 짧게 관찰하는 별도 시험 절차를 먼저 고정해야 한다.

#### Static-stand takeover/handoff probe prepared

- 기존 `--handoff-only-trial`을 새 dual-policy 구조에 맞는 제한 시험으로
  명확히 했다. 이 모드는 Unity, Mink UDP, keypad 입력과 팔 궤적을 열지 않는다.
  1초 capture 후 4초 동안 하체만 TWIST2 static-stand 정책으로 blend하고,
  기존 writer-stop 및 검증된 Regular/AI handoff 후보를 호출한다. 상체 목표는
  최초 측정값으로 유지한다.
- 별도 `run_static_stand_handoff_probe.sh`를 추가했다. 실행 전에 원격
  `SHA256SUMS` 전체를 검사하도록 했으며, 통합 실행 스크립트에도 같은 검사를
  추가했다. periodic CSV에는 각 50 Hz 표본의 `leg_policy_mode`를 기록한다.
- 로컬 검증: leg-policy C++ 상태 전환/이름 시험, velocity keypad C++ 계약,
  Python relay 8개, 두 shell script의 `bash -n`, 단일 LowCmd publisher,
  no-fixed-hold, static policy 및 CSV mode source contract가 통과했다.
- 패키지 `experiments/g1_velocity_mink_right_arm_20260914/`
  `static_stand_probe_update.tar.gz`를 만들었다. SHA-256은
  `e205231dc17dfc9fed03809d849dc92c08613b213810cab35f84370565d351f6`이다.
- 첫 연결에서는 SSH 및 기존 ELF 해시 `a8810309...0782`를 읽기 전용으로
  확인했고 관련 controller 프로세스가 없었다. 전송 직전 유선 링크가 한 번
  끊겼지만 재연결 후 패키지 SHA-256 일치를 확인하고 새 통합 프로젝트에만
  반영했다. 기존 소스는 `source_backups/pre_static_probe_20260914`에 보존했다.
- ARM clean build/link와 빌드 디렉터리 CTest 2개가 통과했다. 새 aarch64 ELF
  SHA-256은
  `29f32101fb9ad8aefb36e24c0fefecb20465923f83468d5a0ca923df98ee073d`다.
  binary, source, policy 2개 및 실행 스크립트가 포함된 원격 `SHA256SUMS`
  전체 항목도 OK였다. 빌드 전후 물리 제어 프로그램은 실행하지 않았다.
- `START_G1_VELOCITY_MINK_KEYPAD`의 All/Robot 차단은 계속 유지한다. 이 probe의
  ARM 빌드 성공도 실제 균형이나 Regular handoff 성공을 의미하지 않는다.
- 물리 시험 전용 Windows 진입점
  `tools/START_G1_STATIC_STAND_HANDOFF_PROBE.bat`을 추가했다. `--preview`는
  SSH/DDS 없이 실제로 사용할 원격 명령만 표시한다. 일반 실행도 원격 해시
  검사가 먼저 통과해야 하며, 사용자가 G1을 확인한 뒤 대문자 `P`를 직접
  입력해야 handoff가 시작된다.

#### Static-stand handoff probe physical failure

- 실제 probe는 249개 표본, 약 4.98초까지 TWIST2 static-stand 목표를 송신한
  뒤 `handoff-only completed` 경로로 들어갔다. 그 직후 LowCmd writer가 먼저
  정지했고 Regular/AI 소유권은 확인되지 않아 로봇의 관절 지지력이 풀렸다.
  프로세스 PID 4053은 writer가 멈춘 채 handoff 확인 loop에 남아 있었다.
- 회수 로그는
  `logs/test_results/g1_static_stand_handoff_probe/`
  `g1_twist2_trial_1789372885273387_4053`에 있다. 실행 중
  `leg_policy_mode=twist2`, roll 최대 0.01448 rad, pitch 최대 0.11087 rad였고
  기록된 제어 fault는 없다. 따라서 힘이 풀린 직접 시점은 자세 guard가 아니라
  writer-stop/handoff 경계와 일치한다.
- 마지막 표본에서 큰 하체 q-command 차이는 joint 4 약 0.481 rad, joint 10
  약 0.388 rad였다. 이 값은 static policy 출력과 실제 관절 사이 차이이므로
  정책 자체의 적합성도 별도 검토해야 하며, 이번 5초 기록을 균형 검증으로
  해석하지 않는다.
- `START_G1_STATIC_STAND_HANDOFF_PROBE.bat`은 즉시 fail-closed 차단했다.
  통합 Robot/All 차단도 유지한다. 확인되지 않은 writer-stop 또는 자동 AI
  handoff를 이후 물리 시험의 정상 종료 경로로 사용하지 않는다.
- 사용자가 G1 전원을 다시 켜고 Regular mode로 복귀했다. 재부팅 후 이전
  PID 4053과 관련 controller가 모두 사라졌음을 읽기 전용으로 확인했다.
- 차단을 G1에도 반영했다. `run_static_stand_handoff_probe.sh`는 즉시 종료 코드
  1을 반환하고, C++ `--handoff-only-trial`도 `Controller` 생성 및 DDS 초기화
  전에 종료 코드 1로 거부한다. PD sweep 완료 경로에서도
  `verified_regular_handoff()` 호출을 제거해 writer를 먼저 멈추지 않는다.
- 원격 ARM clean build/link, CTest 2개, `SHA256SUMS` 전체 검사가 통과했다.
  차단된 shell과 차단된 C++ 옵션을 원격에서 직접 실행해 둘 다 종료 코드 1,
  관련 controller 잔류 없음도 확인했다. 이 검사는 DDS/LowCmd/모터 출력을
  만들지 않았다. 새 aarch64 ELF SHA-256은
  `9f870992dd3f10e9be79ed16866a3e2cdc6297297b1ea591cb89eaf2fbbcebca`다.
- 차단 전 source/ELF는 원격
  `source_backups/pre_handoff_block_20260914`에 보존했다. mode handoff가 별도로
  검증되기 전까지 실제 VR/키패드/PD 물리 실행은 계속 차단한다.

#### Unity keypad value received but locomotion suppressed: fixed and deployed

- PC `velocityrelay` 로그에서 Unity keypad의 forward/strafe/yaw 값과 key-up
  zero가 정상 수신되는 것을 확인했다. 반면 회수한 최신 G1 `policy.csv`의
  4177개 표본은 약 83.54초 동안 계속 `phase=arm_initializing`이었다.
- C++에서 오른팔 `udp_target->Ready()`가 false인 동안
  `VelocityCommand::Stop()`을 호출하여, 정상 수신된 하체 이동 명령도 매 loop
  zero로 덮어쓰는 결합을 확인했다. CSV에는 당시 velocity command 열이 없어
  zero 덮어쓰기 자체는 source와 phase를 결합한 진단이다.
- 초기 4초 full-body takeover blend 중에는 기존대로 zero를 유지하되, blend가
  끝난 뒤에는 오른팔 ready 상태와 관계없이 keypad velocity를 velocity policy에
  전달하도록 수정했다. 따라서 팔이 `arm_initializing`이어도 하체 입력은 적용된다.
- 로컬 검증: Python keypad relay 10개 시험, C++ velocity keypad contract,
  leg-policy switch 및 arm-ready gate 제거 source check가 모두 통과했다.
- G1의 기존 source/README/ELF/SHA256SUMS는
  `source_backups/pre_arm_ready_decouple_20260915`에 보존하고 수정본을 빌드했다.
  원격 C++ 시험 `leg policy switch`, `velocity keypad contract`가 통과했으며
  `SHA256SUMS` 전체 항목이 OK였다. 새 aarch64 ELF SHA-256은
  `b57c3912fa9d5b4f68bc17b2399cbc2b13c477cc968d9a2549c1c1b11a91772b`다.
- 배포 직후 관련 G1 controller가 실행 중이지 않음을 확인했다. 빌드 및 시험은
  모터 프로그램을 시작하지 않았으며, 실제 이동 적용은 다음 지지 시험에서만
  확인할 수 있다.

#### Latched keypad velocity and preliminary left-leg asymmetry review

- Unity keypad를 key-hold 방식에서 rising-edge 누적 방식으로 바꿨다. `8/2`는
  longitudinal, `4/6`은 lateral, `7/9`는 yaw 목표를 누를 때마다 각각
  `+/-0.2`씩 바꾼다. key release는 목표를 변경하지 않고 `5`만 세 축을 zero로
  초기화한다. 각 축은 `[-0.8, 0.8]`로 clamp된다.
- Unity sender, PC relay validator, G1 JSON contract 및 velocity policy target
  validator의 허용 범위를 모두 `+/-0.8`로 맞췄다. Unity는 변경 후
  `Assembly-CSharp.dll`을 2026-09-15 11:27:39에 다시 만들었고 Editor log에
  관련 C# compile error가 없었다.
- 로컬 Python relay 10개 시험과 C++ `velocity keypad contract`,
  `leg policy switch` 시험이 통과했다. G1에서도 ARM build/link, 동일 C++ 시험
  2개와 `SHA256SUMS` 전체 검사가 통과했다. 배포된 aarch64 ELF SHA-256은
  `7ed14c2416902026a394ac7dfdf97b539b2b175a45e973a4d6e2b66319378dd2`다.
  이전 파일은 원격 `source_backups/pre_keypad_latched_08_20260915`에 보존했다.
- `velocity_mink_latest_policy.csv`의 velocity-policy/비-capture 표본 3928개를
  좌우 대응 관절로 비교했다. 전 표본이 `arm_initializing`이어서 관찰한 움직임은
  zero-command continuous gait다. 왼 ankle-pitch writer tracking-error RMS는
  0.311 rad로 오른쪽 0.233 rad보다 컸고, action RMS도 왼쪽 1.080, 오른쪽
  0.915였다. 왼 knee torque-estimate RMS는 15.7 Nm, 오른쪽은 19.9 Nm였다.
  hip-roll 및 ankle-roll의 action은 좌우가 비교적 비슷했다.
- 이 결과만으로 왼발 actuator가 약하다고 결론낼 수 없다. 로그에 foot contact
  force와 velocity command가 없으며, torque는 측정된 접촉력이 아니라 SDK의
  estimate다. 현재 우선 가설은 continuous zero-command gait의 좌우 비대칭과
  왼 ankle-pitch의 큰 추종 부담이다. 실제 이동 구간의 command/contact가 포함된
  새 로그로 정책 출력, 추종, 물리 하중을 분리해야 한다.

#### Initial arm-ready condition adapted to continuous gait

- Continuous gait가 하체뿐 아니라 몸통 동역학과 양팔 `q/dq`에도 지속 진동을
  만들 수 있다는 사용자 지적을 반영했다. 기존 초기 ready는 양팔 15..28이
  관절별 position-error 범위와 순간 `abs(dq) <= 0.05 rad/s`를 0.5초 연속
  만족해야 해서 zero-command gait 중 영구 차단될 수 있었다.
- 초기 ready 전체를 생략하지 않았다. 초기 궤적 완료, fresh LowState 및 양팔
  position-error 범위는 유지하고, 초기 판정에서만 순간 dq 조건을 제거했다.
  대신 position-error가 1.0초 연속 허용 범위에 있어야 한다. 이는 50 Hz,
  40-step velocity gait 한 주기 약 0.8초보다 길다.
- 복귀 완료와 추적 중 상태/속도 제한은 기존 `MeasuredReadyJoint`를 계속 써서
  저속 조건을 유지한다. ACK blocker도 초기 판정에서 speed가 관찰값일 뿐
  ready 조건에 사용되지 않음을 명시한다.
- 새 회귀 시험은 양팔 dq가 계속 +/-0.30 rad/s인 조건에서 1초 전 ready를
  거부하고, 1초 position dwell 뒤 ready를 허용하며, position-error 초과와
  복귀 속도 조건 완화가 없음을 검증한다.
- 로컬 C++ 시험과 G1 ARM build/link가 통과했다. G1에서 `leg policy switch`,
  `velocity keypad contract`, `initial ready continuous gait` 3개 시험 및
  `SHA256SUMS` 전체 항목이 통과했다. 새 aarch64 ELF SHA-256은
  `e8c3df7be5b38a22e9e1a8887744758bb62d513000a2c0d4b3741272cf78d47d`다.
  배포 전 파일은 원격
  `source_backups/pre_continuous_gait_arm_ready_20260915`에 보존했다. 제어
  프로그램은 실행하지 않았고 실제 continuous-gait ready 진입은 미검증이다.

#### 2026-09-15 continuous zero-command gait fall and immediate block

- 최신 물리 실행에서 G1은 `P` 이후 zero-command velocity gait를 지속했고,
  약 79초의 Robot console 시점에 사용자가 관찰한 대로 스스로 넘어졌다.
  지지대가 아닌 사용자가 배터리를 꺼 정지했다. Robot transcript는
  `logs/test_results/velocity_mink_console/20260915_113847_5347632_robot.log`이며
  마지막 출력은 `phase=udp_ready`, roll 약 0.03 rad, pitch 약 0.00 rad 뒤의
  connection reset이다. 원격 CSV는 G1 전원이 꺼져 아직 회수하지 못했다.
- 같은 실행에서 PC velocity relay는 첫 zero packet 뒤 같은 session의
  non-monotonic/duplicate sequence를 받아 `ValueError: sequence`로 종료했다.
  stale UDP packet을 G1에 전달하지 않는 동작은 맞지만 relay 전체 종료는
  부적절했다. `StalePacket`으로 분리하여 stale sequence를 기록·폐기하고 다음
  packet을 계속 받도록 바꿨다. Python relay 시험은 11개가 통과했다.
- 실제 낙상 원인은 engage나 nonzero keypad 입력 전의 continuous velocity-policy
  gait 자체다. 따라서 ready 조건 완화로 해결할 수 없다. 로컬 launcher의
  `Robot`과 `All`을 즉시 fail-closed 차단했고 관련 로컬 UDP 프로세스가 남지
  않았음을 확인했다.
- 로컬 후보에서는 `G1_VELOCITY_CONTINUOUS_GAIT` compile flag를 제거했다.
  zero command에서는 TWIST2 static-stand policy가 하체를 소유하고, nonzero
  keypad 입력에서 4초 velocity-policy blend, `5` 이후 gait settle과 6초
  static-stand 복귀를 사용하는 기존 단일-writer dual-policy 전환을 다시
  활성화한다. C++ 전환, keypad contract, continuous-gait arm-ready 시험과
  Python relay 11개가 통과했다.
- G1은 꺼져 있어 dual-policy 후보를 아직 전송·ARM 빌드하지 않았다. 원격에
  마지막 배포된 `e8c3df7b...d47d`는 continuous gait 빌드이므로 실행하면 안 된다.
  다음 단계는 G1 전원 복구 후 낙상 CSV 회수, controller 부재 확인, dual-policy
  ARM 빌드까지만 수행한다. 그 빌드 성공은 실제 균형 검증이 아니다.

#### Fall CSV recovery and dual-policy idle ARM deployment

- 낙상 실행의 원격 `policy.csv`를
  `logs/test_results/g1_velocity_fall_20260915/policy.csv`로 회수했다. 원격 파일
  SHA-256은 `20e7aa1c838d9897f58f7b906fa94286fe1e0f42e1bee58e34d91b9364bb3b0e`이며,
  3796개 표본과 마지막 elapsed 75.9201초를 확인했다.
- 0~60초에는 roll/pitch 절대 최대가 대체로 약 0.064 rad 이하였다. 60~70초에는
  roll 0.1271 rad, pitch 0.1095 rad로 커졌고, 마지막 70~75.9초에는 roll
  0.2383 rad, pitch 0.1593 rad, 다리 `dq` 절대 최대 4.9899 rad/s,
  `tau_est` 절대 최대 56.25 Nm까지 증가했다. 이는 zero-command continuous
  velocity gait가 점차 발산했다는 로그 근거이며, 접촉력 측정이 없으므로 정확한
  물리 원인을 확정한 것은 아니다.
- 마지막 20초에서 ankle-pitch command-to-measurement error RMS는 왼쪽
  0.3480 rad, 오른쪽 0.2604 rad였고, action RMS는 왼쪽 1.3548, 오른쪽
  1.1015였다. PC relay의 stale-sequence 종료는 별도 통신 결함이며 낙상의 직접
  원인으로 판단하지 않는다.
- G1 원격 프로젝트에 dual-policy idle 후보를 전송하고 ARM 빌드만 수행했다.
  배포 전 파일은
  `source_backups/pre_dual_policy_idle_20260915`에 보존했다. 원격에서
  `leg policy switch`, `velocity keypad contract`,
  `initial ready continuous gait` 시험과 `SHA256SUMS` 검사가 모두 통과했다.
  새 aarch64 ELF SHA-256은
  `f3d35075f15e21ed21823fd65bb8cd0106f9fa0429542e548a948fe959d06850`이다.
- 새 후보는 zero command에서 TWIST2 static-stand, nonzero keypad에서 4초
  blend 후 velocity policy, 숫자 5 이후 gait settle과 6초 blend를 거쳐
  static-stand로 돌아가는 단일 LowCmd writer 구조다. 배포 후 해당 controller가
  실행 중이지 않음을 확인했다. 물리 균형과 정책 전환은 검증하지 않았으며,
  낙상 후 `Robot/All` launcher 차단도 유지한다.

#### 2026-09-15 alternative locomotion policy review (no hardware execution)

- Correction: the earlier statement that the velocity policy itself caused the
  fall was too strong. Logs establish growing instability in the integrated
  zero-command run, not whether weights, observation construction, PD, output
  clipping, physical configuration, or their combination caused it. The untouched
  upstream controller has not been shown to fail by this run.
- Current `g1_velocity_policy.hpp` builds 47 observations from IMU, velocity
  command, leg q/dq, previous action and phase. It does not explicitly observe
  upper-body joint posture. It also clamps leg targets and reconstructs previous
  action with [-2,2] clipping. Training/deployment parity must be checked before
  interpreting the result as a policy-only failure.
- Preferred fit for simultaneous Mink arms and keypad/Omni locomotion: HOMIE.
  Official project describes training for continuously varying upper-body poses,
  G1 deployment, and an example `deploy.onnx` checkpoint. This is a candidate
  selection based on task fit, not evidence of better stability on this G1.
  Official deployment assumes G1 with Dex3 hands; mass/configuration, observation
  order, action joints, history, gains and command semantics need adapter review.
  Its CC-BY-NC-SA-4.0 terms prohibit commercial use without permission; do not
  describe it as unrestricted open source or assume company use is authorized.
  Sources checked: https://github.com/InternRobotics/Homie and
  https://raw.githubusercontent.com/InternRobotics/Homie/main/HomieDeploy/README.md
- Official walking-only comparison candidate: Unitree RL Lab G1-29dof velocity.
  Published deploy.yaml uses 29-joint actions and five-frame observation history;
  it is not a drop-in 12-leg-output replacement. Replacing its arm outputs with
  Mink cannot be assumed to preserve the trained controller behavior.
  https://github.com/unitreerobotics/unitree_rl_lab
  https://raw.githubusercontent.com/unitreerobotics/unitree_rl_lab/main/deploy/robots/g1_29dof/config/policy/velocity/v0/params/deploy.yaml
- Unitree RL Gym's official deployment README explicitly describes its controller
  as a demonstration rather than a stable control program. The current local
  checkpoint's precise upstream identity has not been verified in this review.
  https://github.com/unitreerobotics/unitree_rl_gym/blob/main/deploy/deploy_real/README.md
- Next: resolve HOMIE usage scope, inspect its checkpoint and adapter contract in
  a separate local candidate, then evaluate zero-command standing, start/stop,
  lateral/yaw commands and moving-arm disturbance in simulation. No new policy
  was installed on G1, no physical test ran, and the launcher block remains.

#### 2026-09-15 technology-transfer IK license inventory and independent training direction

- User clarified technology-transfer context and accepted checking Mink/dependencies.
- Added `tools/audit_ik_licenses.py`; executed under Python 3.11 with the live MuJoCo
  3.12.0 overlay. Eight selected distributions found; 35 license/notice files copied
  with original/copy SHA-256 equality verified. Evidence is in
  `logs/license_audit/20260915_ik/inventory.json` and its `notices/` directory.
- Installed Mink 1.3.0 is Apache-2.0; qpsolvers 4.13.0 is LGPLv3. LGPL is not a
  noncommercial restriction, but delivery/source/replacement obligations need review.
  This inventory is not a complete dependency audit or release approval.
- Added `docs/TECH_TRANSFER_LICENSE_AUDIT_20260915.md` with findings, exclusions,
  reproducible command, and an independent lower-body training specification.
- Selected Unitree RL Lab (Apache-2.0) + Isaac Lab (BSD-3-Clause) as the initial
  training-base candidate. Runtime/assets/dependencies still need review. HOMIE
  code/configuration/checkpoints are not adopted; use paper-level ideas with our
  implementation and newly trained weights. No claim of patent clearance.
- No training, package installation, G1 access, physical execution or live control
  changes in this step. Next implementation: inventory training runtime/GPU and
  reproduce original G1 simulation baseline before adding upper-body-conditioned
  12-leg-action training.

#### 2026-09-15 independent learning runtime preparation (installation in progress)

- Measured RTX 5070 Laptop 8151 MiB VRAM, Windows driver 610.62; GPU also visible
  in WSL Ubuntu. C: free space about 103.7 GB, not the WSL virtual disk's 951 GB.
- Because current Isaac Sim documents a 16 GB minimum, selected mjlab/MuJoCo-Warp
  for the initial local runtime feasibility check. This updates the prior
  provisional Isaac Lab selection, not the existing live simulation engine.
- Cloned official mjlab to `/home/user/g1-learning/mjlab-20260915`, commit
  `8ee51fbcf806a7419189f706d9e394cbeb7790fa`. Read its AGENTS.md; source unmodified.
- uv locked install with Python 3.12/CUDA 12.8 is still downloading. Session 24825.
- Added `experiments/independent_locomotion/smoke_mjlab.py`, `verify_mjlab.sh`,
  and README. Python AST and bash syntax checks passed. Queued verification
  session 11403 waits on uv's environment lock and will then attempt four G1
  environments/50 zero-action steps and 16-environment/two-iteration PPO.
- Log: `logs/test_results/mjlab_setup_20260915T044305Z/console.log`.
  Do not claim runtime or training passed until results are inspected. These
  are synthetic pipeline checks, not a trained walking policy or hardware test.
- No G1 connection, live gain/IK/launcher changes, or policy deployment occurred.

#### 2026-09-15 upper-body-conditioned mjlab training pipeline

- The mjlab installation at `/home/user/g1-learning/mjlab-20260915` completed at
  pinned upstream commit `8ee51fbcf806a7419189f706d9e394cbeb7790fa`.
  Base verification passed at
  `logs/test_results/mjlab_setup_20260915T060836Z/`: CUDA RTX 5070 Laptop,
  four G1 environments/50 zero-action steps and 16 environments/two PPO
  iterations. This establishes runtime functionality only.
- Added `experiments/independent_locomotion/upper_body_conditioned_env.py`.
  It exposes exactly 12 leg-joint policy actions, separately commands 17
  waist/arm position targets, and gives those targets to actor and critic. The
  current smooth sine target is a conservative generated fixture, not recorded
  Mink data or a final motion distribution.
- Added structural smoke, local training entrypoint and combined verifier:
  `smoke_upper_body_conditioned.py`, `train_upper_body_conditioned.py`, and
  `verify_upper_body_conditioned.sh`. The training entrypoint registers a local
  task at runtime and forces TensorBoard, so no WandB account/upload is needed.
- Completed evidence:
  `logs/test_results/mjlab_upper_conditioned_20260915T062006Z/`. Structural test
  passed 4 environments/100 steps with actor shape 99, critic shape 111, action
  shape 12 and upper target shape 17. Training test passed 16 environments/two
  PPO iterations and created `model_0.pt`, `model_1.pt` plus serialized configs.
- All four structural environments reset, and the untrained two-iteration actor
  reported falls. These checkpoints are generated pipeline fixtures and must not
  be called trained walking policies or deployed to G1. No G1, SDK, DDS, network,
  LowCmd, physical output, live gain, IK or launcher path was used or changed.
- Next: freeze train/held-out evaluation trajectories and metrics, replace the
  sine fixture with independently generated/recorded Mink trajectories, then run
  fixed-upper baseline versus upper-conditioned training under matched seeds.

#### 2026-09-15 frozen Mink command split for locomotion learning

- Added `mink_trajectory_dataset.py` and `prepare_mink_trajectory_split.py`.
  Seven complete PC-side Mink command sessions are frozen at file level: five
  train and two validation. SHA-256 overlap, malformed/non-monotonic samples and
  nonfinite values fail closed. These are recorded command targets, not measured
  G1 joint responses; only right-arm motion is present and stored as offsets from
  each session's first active sample.
- Generated versioned artifacts under
  `experiments/independent_locomotion/data/mink_command_trajectories_v1.{json,npz}`.
  Added `evaluation_protocol_v1.json` before trained-candidate validation, fixing
  four seeds, seven velocity commands, 20 s episodes, metrics and initial
  simulation research thresholds.
- The mjlab event now optionally replays the selected frozen split. Combined
  verification uses validation only for structural stepping and train only for
  the two-iteration PPO pipeline. Evidence:
  `logs/test_results/mjlab_upper_conditioned_20260915T063433Z/`; completion marker,
  validation structural smoke and train-only `model_0.pt`/`model_1.pt` all exist.
- Dataset unit tests passed: disjoint split load, overlap rejection, and nonfinite
  source rejection. Full CUDA verifier passed after correcting vectorized target
  indexing. The untrained fixtures still fall and are not walking policies.
- Next: implement a weight-frozen deterministic evaluator, then obtain matched
  fixed-upper baseline and conditioned-candidate metrics. No G1/SDK/DDS/network,
  hardware output, deployment, live gain/IK or launcher change occurred.

#### 2026-09-15 deterministic checkpoint evaluator

- Added `experiments/independent_locomotion/evaluate_upper_body_conditioned.py`.
  It uses the frozen validation split and command grid, reapplies fixed commands
  every step, accumulates only until each environment's first fall, and records
  fall rate, linear/yaw velocity RMSE, maximum absolute roll/pitch and mean foot
  slip velocity.
- The evaluator snapshots every actor parameter and observation-normalizer buffer
  before and after inference and fails if any value changes. Explicit smoke
  overrides (`--steps`, `--max-seeds`) make the output non-protocol-compliant.
- Pipeline smoke passed on the two-iteration generated fixture with one seed,
  seven commands and 50 steps. Evidence:
  `logs/test_results/mjlab_upper_conditioned_eval_smoke_20260915.json`;
  `weights_and_normalizers_unchanged=true`, `protocol_compliant=false`. Its 1 s
  zero-fall result is not a locomotion result and was not judged against the
  frozen 20 s acceptance gate.
- No complete candidate validation has been run, so the held-out set has not been
  used for model selection. Next: implement fixed-upper mode, train matched
  baseline/candidate on train episodes, then perform one complete frozen
  validation. No G1 or command-capable path was used.

#### 2026-09-15 matched stage-1 train-only run

- Added fixed-upper mode while retaining the same 99-input/12-output actor shape,
  plus `matched_training_stage1.json`, `run_matched_training_stage1.sh`, and
  `summarize_matched_training.py`.
- Both fixed-upper and recorded-upper models completed seed 1509, 256 environments
  and 500 PPO iterations: 3,072,000 train samples per model. Checkpoints were
  saved every 50 iterations through `model_499.pt`; all completion markers exist
  under `logs/test_results/mjlab_matched_stage1_20260915/`.
- `train_summary.json` reads TensorBoard train scalars only and explicitly records
  `validation_data_read=false`, `selection_decision=null`. Last-50 means: fixed
  reward 4.012, episode length 185.84 steps, xy/yaw error 0.325/0.458, slip 0.214;
  recorded reward 2.265, episode length 121.87, xy/yaw error 0.200/0.278, slip
  0.184. The recorded model improved command-error/slip train scalars but survived
  for less time and had a higher `fell_over` log scalar. That scalar is not a
  normalized validation fall rate.
- Neither model approaches a demonstrated 20 s survival result, so full frozen
  validation was intentionally not run and no candidate was selected. These are
  preliminary simulation checkpoints and are not approved for G1 deployment.
  Next: matched train-only continuation, then one frozen validation after the
  training stopping rule is met. No G1/SDK/DDS/network or live control changed.

#### 2026-09-15 user-runnable matched continuation

- Added `--resume-checkpoint` to
  `experiments/independent_locomotion/train_upper_body_conditioned.py`. Resume
  restores the runner checkpoint into a new run directory; it does not overwrite
  the stage-1 checkpoint.
- Added `experiments/independent_locomotion/run_matched_training_continuation.sh`,
  `tools/START_MJLAB_MATCHED_CONTINUATION.bat`, and
  `tools/CHECK_MJLAB_MATCHED_TRAINING.bat`. Double-clicking the start batch runs
  fixed-upper then recorded-upper sequentially for 500 additional iterations per
  model. A positional batch argument overrides that count.
- Verified the resume path with one additional iteration per model. Evidence is
  `logs/test_results/mjlab_matched_continuation_20260915T073955Z/`; both console
  logs report loading their copied `model_499.pt`, and `COMPLETE` contains
  `MATCHED_CONTINUATION_COMPLETE`.
- The one-iteration run verifies checkpoint loading and orchestration only. It is
  not held-out validation, policy selection, G1 validation, or deployment. No
  G1/SDK/DDS/network, publisher, motor output, gain, IK, or launcher path was used.
- Added `select_matched_resume.py` and selection tests. Repeated batch launches
  now resume the newest run having `COMPLETE`, both per-mode completion markers,
  valid result JSON and existing in-run checkpoints. Interrupted/incomplete runs
  are skipped; stage-1 is used only when no valid continuation exists.

#### 2026-09-15 matched continuation readiness after model 1497

- Two matched 500-iteration continuations completed after stage 1. The newest
  completed run is `logs/test_results/mjlab_matched_continuation_20260915T082411Z`;
  both modes reached `model_1497.pt` with `status=passed`.
- Before reading validation, froze the train-readiness rule: both models must
  reach a last-50 mean episode length of at least 900 control steps (18 s at
  0.02 s/step) before the single 20 s held-out validation run.
- Train-only evidence is saved as `train_summary_window50.json` and
  `train_readiness.json` in that run. Fixed averaged 554.44 steps (11.089 s);
  recorded averaged 291.29 steps (5.826 s). Neither passes the readiness rule.
  Recorded training was also unstable in the last window, so validation remains
  unread and unexecuted. Decision: one more matched 500-iteration continuation,
  then reassess rather than launching validation now.
- These are simulation training metrics, not measured G1 behavior or hardware
  validation. No G1/SDK/DDS/network/publisher/motor output was used.

#### 2026-09-16 recorded-upper train curriculum

- Unchanged training reached `model_2994.pt`. Last-50 train survival was fixed
  16.053 s and recorded 8.698 s, so neither passed the frozen 18 s readiness
  threshold and validation remained unread. Blind unchanged continuation was
  stopped because recorded survival had plateaued near 9 s.
- Added an explicit recorded trajectory amplitude curriculum. The new default
  launcher `tools/START_MJLAB_RECORDED_CURRICULUM.bat` trains both models for
  1,000 more iterations; fixed remains unchanged while recorded ramps frozen
  train-trajectory offsets from 25% to 100% over 800 iterations and remains at
  100% for the final 200 iterations.
- Added fail-closed curriculum bounds, cross-run latest-complete checkpoint
  selection, and tests. Eleven dataset/selection/curriculum tests passed, along
  with Python compilation, shell syntax, and diff checks.
- One-iteration pipeline smoke passed at
  `logs/test_results/mjlab_recorded_curriculum_20260916T000756Z`. It resumed both
  `model_2994.pt` checkpoints and recorded the requested scale parameters. This
  smoke is not performance training or validation.
- Entire path remains simulation-only; no G1, SDK, DDS, network, publisher,
  motor output, live gain, IK, or launcher behavior was used or changed.
- The full 1,000-iteration curriculum completed at
  `logs/test_results/mjlab_recorded_curriculum_20260916T000948Z`, reaching
  `model_3993.pt` for both modes. Last-50 survival: fixed 19.101 s (passes the
  frozen 18 s train-readiness threshold), recorded 11.462 s (improved from
  8.698 s but does not pass). The last 200 iterations were at 100% recorded
  amplitude. Next decision is 1,000 iterations of 100%-amplitude consolidation,
  not another amplitude reset. The existing matched continuation launcher was
  verified to select both curriculum `model_3993.pt` checkpoints.

#### 2026-09-16 VR/Mink/Omni protocol handoff memo

- Added `docs/G1_VR_MINK_OMNI_PROTOCOL_MEMO_20260916.md` as a shareable protocol
  description. It records current ports, packet examples, joint ordering, timing,
  relay/ACK binding, single-LowCmd-owner composition, camera path, the observed
  Omni Connect WebSocket fields, and the planned distinct Omni velocity schema.
- The memo separates implemented PC contracts, blocked historical physical
  candidates, and the not-yet-exported upper-conditioned mjlab policy. It does
  not claim that Omni→G1 or the new policy deployment is complete.

# 2026-09-16 protocol memo update

- 공유용 `G1_VR_MINK_OMNI_PROTOCOL_MEMO_20260916.md`는 전체 구조와 현재 상태만 설명하는 짧은 문서로 정리했다.
- Omni 입력은 Unity 안에서 처리하지 않고 Omni Connect가 실행되는 Windows PC의 독립 `Omni Gateway`가 `ws://127.0.0.1:32123`을 읽는 구성을 권장한다.
- 원격 서버는 기록·분석 용도로만 두고 실시간 제어 루프에는 넣지 않는다.
- 기존 상세 포트·JSON·검증 설명은 `G1_VR_MINK_OMNI_PROTOCOL_TECHNICAL_APPENDIX_20260916.md`에 보존했다.

## 2026-09-16 velocity endpoint discovery

- 하체 이동 송신 경로에서 G1의 `192.168.123.164` 고정 주소를 제거할 수 있도록
  `g1.velocity.discovery.v1` UDP discovery 계약을 추가했다.
- G1 후보 수신기는 같은 실행 token을 포함한 announcement를 UDP `5018`로 1 Hz
  broadcast하고, PC relay는 패킷의 실제 송신 IP와 안내된 velocity 포트를 선택한다.
- G1의 허용 PC source IP를 명시하지 않은 경우에는 token 검증을 통과한 첫 sender에
  잠기도록 후보 코드를 변경했다. 명시적인 기존 source IP 방식은 계속 지원한다.
- Python 계약 단위 테스트 4개와 localhost discovery→velocity 전달 시험은 통과했다.
- C++ 단위 target 3개는 빌드됐지만 전체 G1 executable은 이 PC WSL에 Unitree SDK
  header가 없어 컴파일 완료하지 못했다. G1 전송·실행·DDS 초기화는 하지 않았다.

## 2026-09-16 Omni velocity gateway

- `g1_omni_velocity_gateway.py`를 추가했다. Omni Connect WebSocket의
  `movementXY`와 `armYaw`를 읽어 시작 X/Y 영점, deadzone, gain, 제한을 적용한다.
- yaw는 G1 yaw feedback 없이 연속 Omni yaw 차이를 unwrap하고 `delta/dt`를
  low-pass하여 개방루프 `yaw_rate`로 변환한다.
- Gateway는 token-bound UDP `5018` discovery로 G1을 찾고 공통
  `g1.velocity.command.v1` 패킷을 발견된 UDP `5017`로 직접 보낸다.
- native velocity 계약은 기존 keypad schema와 새 Omni schema를 모두 허용한다.
- Python discovery/mapper 테스트 10개와 C++ velocity contract test가 통과했다.
- `websocket-client==1.8.0`을 현재 Python 3.11에 설치하고 requirements에 고정했다.
- 실제 Omni 및 G1에는 연결하거나 송신하지 않았다.
- `CHECK_OMNI_GATEWAY_OFFLINE.bat`와 가짜 Omni WebSocket/G1 UDP 종단 fixture를
  추가했다. 자동 발견 뒤 forward/lateral/yaw 명령과 종료 시 최종 zero packet을
  확인했으며 10개 명령 packet을 수신해 PASS했다.
- `START_OMNI_GATEWAY_READONLY.bat`를 추가했다. `--dry-run`은 discovery와 UDP
  송신을 만들지 않고 Omni `32123`만 읽어 보정된 `vx/vy/yaw_rate`를 콘솔과 CSV에
  기록한다. 현재 Omni Connect 프로세스는 실행 중이지만 `32123`이 열려 있지 않아
  실제 장치 기록은 Bluetooth 연결 대기 상태다.
- 이후 Omni Connect가 `127.0.0.1:32123`을 열어 실제 read-only 10초 기록을
  완료했다. 951 samples, calibrated 848 samples였고 정지 중 `vx=vy=0`이었다.
  raw yaw burst로 최대 약 `0.052 rad/s` 출력이 남아 출력단 yaw deadzone을
  `0.08 rad/s`로 추가했다. 동일 receive timestamp burst는 직전 출력으로 합치고
  역행 timestamp는 계속 거부한다. 실제 보행/회전 동작 기록은 아직 하지 않았다.
### 2026-09-16 Omni Gateway actual read-only movement capture

- User-operated Omni Connect capture completed without G1 discovery, UDP output, SDK/DDS initialization, or motor output.
- Source CSV: `logs/test_results/omni_gateway_readonly/omni_gateway_20260916_114957.csv`
- 12,279 samples over 107.312 s (about 114.4 samples/s); 12,179 post-calibration samples.
- Observed ranges after mapping: `vx [-0.1652, +0.1652]`, `vy [-0.3478, +0.3217]`, `yaw_rate [-0.8, +0.8]` (SI command units).
- Both translation axes and both yaw directions were exercised. Large motion groups appeared around 42-45 s, 49-62 s, 70-80 s, 82-85 s, 87-91 s, and 93-101 s after calibration.
- The intended six labels cannot be assigned solely from this recording with high confidence because the translation groups contain axis mixing and their chronological axis/sign pattern does not match a clean forward/back/left/right sequence. Do not change axis signs from this capture alone.
- Stationary yaw noise motivated an output yaw deadzone of `0.08 rad/s`; offline unit and fake-WebSocket/fake-G1 end-to-end tests remained passing after that change.
### 2026-09-16 one-click Omni to fake-G1 integration harness

- Added `tools/START_OMNI_FAKE_G1_INTEGRATION.bat` for a single-window test using real Omni Connect input and a local fake G1 receiver.
- Added `hardware/g1_arm_bridge/run_omni_fake_g1_integration.py`.
- The harness binds both test UDP endpoints to `127.0.0.1` and uses ports 55118/55117, so physical G1 discovery/output is structurally excluded.
- It exercises Omni WebSocket input, startup zeroing, relative `armYaw` mapping, token-bound discovery, command encoding, sequence validation, fake reception, CSV capture, and a peak-value summary.
- It contains no Unitree SDK, DDS, LowCmd, SSH, or motor-output path. Default run time is 120 s; an optional first BAT argument changes the duration.
### 2026-09-16 solo Omni preparation delay

- The one-click fake-G1 BAT now waits 20 s before starting the 1 s Omni zero calibration, allowing one operator to launch it and walk to the Omni.
- During the preparation delay the Gateway receives Omni samples but emits only zero velocity. The mapper state is not advanced, so the yaw/movement origin is captured after the delay.
- BAT arguments are `[total_duration_seconds] [preparation_delay_seconds]`; defaults are `120 20`.
### 2026-09-16 solo one-click Omni to fake-G1 result

- Actual capture: `logs/test_results/omni_fake_g1/omni_fake_g1_20260916_122700.csv`.
- 9,489 samples over 73.562 s at about 129 Hz.
- The first mapped-ready sample occurred exactly 21.0 s after capture start, confirming the configured 20 s preparation delay plus 1 s zero calibration.
- Post-calibration command ranges were `vx [-0.2957, +0.1652] m/s`, `vy [-0.7217, +0.2870] m/s`, and `yaw_rate [-0.8, +0.8] rad/s`.
- Both signs of all three command axes were observed, so the real Omni Connect -> Gateway -> loopback discovery -> fake G1 UDP receive path is operational.
- This was PC-only evidence. No physical G1 discovery, SDK/DDS initialization, LowCmd publisher, SSH, or motor output was used.
- The recording demonstrates transport and mapping range, but it does not establish that the selected signs match the operator's intended G1 forward/left/yaw directions or validate the locomotion policy on hardware.
### 2026-09-16 official-policy MuJoCo direction audit

- Downloaded Unitree's official `unitree_rl_gym/deploy/pre_train/g1/motion.pt`; SHA-256 is `cf668f75b90d1abf73d2b87612a6e76bccc61ff7e083b63582d3f6aaa3c1759d`, exactly matching the candidate C++ pin.
- Added `tools/evaluate_g1_velocity_direction_mujoco.py`, mirroring the official 2 ms dynamics step, 50 Hz policy step, 47 observations, 12 actions, default angles, PD gains and command/action scales.
- Six independent headless trials used 2 s zero-command warmup followed by 4 s at magnitude 0.2. Results are in `logs/test_results/g1_velocity_direction_mujoco_20260916.csv`.
- `+vx` produced +0.7503 m body-forward; `-vx` produced -0.6477 m.
- `+vy` produced +0.4817 m body-left; `-vy` produced -0.6741 m.
- `+yaw` produced +0.7063 rad yaw; `-yaw` produced -0.7768 rad.
- Therefore the policy convention is `+vx=forward`, `+vy=left`, `+yaw=left/CCW`. The Omni reference defines `movementX` as right-positive and `movementY` as forward-positive, so Gateway lateral mapping was corrected from `vy=+movementX` to `vy=-movementX`. Forward and yaw signs were retained.
- This is official-policy MuJoCo evidence, not physical G1 validation.
### 2026-09-16 corrected Omni recording replayed through official G1 MuJoCo policy

- Added `tools/replay_omni_velocity_mujoco.py` and replayed the calibrated portion of `omni_fake_g1_20260916_122700.csv` through the exact official velocity policy.
- Because the capture preceded the lateral sign correction, replay used stored `vx`, negated stored `vy`, and unchanged stored `yaw_rate`.
- Replay duration was 52.562 s after a 2 s zero-command warmup.
- No simulated fall threshold was crossed: minimum pelvis height 0.7698 m, maximum absolute roll 0.08149 rad (4.67 deg), maximum absolute pitch 0.06041 rad (3.46 deg).
- Net body-frame displacement was -0.3109 m forward and -0.7508 m left; this is the integral outcome of the user's unlabeled movement sequence, not a direction-label test.
- Outputs: `logs/test_results/omni_mujoco_replay_20260916.csv` and `logs/test_results/omni_mujoco_replay_20260916_summary.json`.
- This improves confidence in the corrected mapping and recorded command envelope only in the official MuJoCo model. It does not prove physical G1 balance, stop behavior, surface interaction, or safe real-world execution.
### 2026-09-16 physical axis-trial sender prepared, not actuated

- Read-only SSH inspection found no running G1 velocity/TWIST2 process.
- The deployed `g1_velocity_policy.hpp`, `leg_policy_switch.hpp`, and launcher hashes exactly match the local dual-policy candidate. The binary contains the static TWIST2 stand mode and was built without `G1_VELOCITY_CONTINUOUS_GAIT`.
- Added `hardware/g1_arm_bridge/g1_velocity_axis_trial_sender.py`. It creates no SDK/DDS/LowCmd publisher; it discovers the existing token-bound single owner and sends one selected axis at at most 0.10, then a mandatory zero tail.
- Defaults are zero 6 s (covering initial takeover), magnitude 0.05 for 8 s (covering the 4 s velocity-policy blend), then zero 12 s (covering settle and 6 s return blend).
- Actual actuation has not started. The existing full-body owner still needs its arm-input/runtime prerequisites, and physical support/current robot mode must be confirmed before starting it.
