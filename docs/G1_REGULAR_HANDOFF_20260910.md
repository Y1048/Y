# G1 TWIST2 Regular handoff worktree handoff

## Current state

- The G1 is powered off for battery charging. Do not assume
  `192.168.123.164` is reachable.
- Do not start a DDS publisher or a motor-output program while continuing this
  handoff.
- `tools/START_TWIST2_MINK_CYCLE_CANDIDATE.ps1` blocks every `Robot` and `All`
  launch before SSH.
- The launcher hash is from the last confirmed build. A later `--clean-first`
  build lost SSH before completion, so the remote executable and hash must be
  checked again after the G1 reconnects.
- The 2026-09-11 changes below are offline-tested source changes, not a new
  approved robot binary. Keep all physical launch blocks in place.

## PD identification change

The large full-forward reach was rejected after the G1 showed a backward-fall
tendency during the first Kp 40 candidate. `--pd-sweep-trial` now moves only
right shoulder pitch joint 22 around the ready pose:

1. `ready -> +8 deg`
2. `+8 deg -> -8 deg`
3. `-8 deg -> ready`

It uses quintic smoothstep segments, a 20 deg/s velocity limit, a 60 deg/s^2
acceleration limit, and three cycles for each proximal Kp candidate 40, 48,
and 56 with Kd 5. The other 28 reference targets remain equal to the supplied
baseline; this does not mean the full-body writer freezes the policy-driven
legs. The old `--pd-reach-trial` implementation remains available in source but
must not be used for another physical run.

## Regular handoff candidate

FSM 500/501 is a verification value, not the mode-change command. The command
is `MotionSwitcherClient.SelectMode("ai")`.

The candidate sequence is:

1. Continue the final LowCmd position target.
2. Require joints 15..28 to stay within 0.1 rad position error and 0.1 rad/s
   measured speed for one second. Require a fresh WriterFrame and bounded
   observation gaps; a refusal/error retains the existing hold.
3. Stop output, drain the in-flight write callback, and destroy the 500 Hz writer.
4. Call `SelectMode("ai")` once. A returned error or exception is an unknown
   outcome to observe, not permission to restart LowCmd or retry selection.
5. Require `CheckMode == ai`, the captured starting FSM ID, and valid LowState
   for one sampled continuous second. Slow verification rounds and observation
   gaps reset the window instead of counting as verified time.
6. Destroy the publisher and print `SHUTDOWN COMPLETE` only after verification.

If selection cannot be verified, LowCmd resumes only after a NEW `CheckMode`
query succeeds with an empty service, valid LowState, and a fresh observation.
The replacement writer is prepared INACTIVE before that query, with no further
RPC, logging, allocation or mutex acquisition between the final time check and
enabling output. If `ai`, another service, an error, stale data, or an unknown
result is observed, output remains stopped and the process continues monitoring.
A fresh empty observation is not an atomic ownership lease: an external service
can still change afterwards. Do not treat this software check as proof of
race-free ownership on the installed robot.

`--handoff-only-trial` keeps captured upper-body references, performs the
one-second capture and four-second TWIST2 LEG blend, then runs this handoff.
It accepts no UDP input, arm trajectory, or PD gain override. It is NOT a
whole-body no-motion test: leg targets remain policy-driven and the existing
writer limits can affect actual commands. Do not remove the leg policy to make
a no-motion claim true.

The settle check reads the mutex-protected `WriterFrame.target` snapshot. It
does not read the writer-owned `last_target_` concurrently.

## Verified locally before the 2026-09-11 changes (historical)

- Python control-flow regression tests: 10 passed in the original handoff.
- C++ tests passed for the PD option parser, small-signal trajectory, Regular
  handoff gate, and 10,000 concurrent WriterFrame publications/reads.
- These were offline/software checks, not physical G1 safety validation.
- A later review of `05d4ebf` found that long observation gaps could pass the
  old gate despite those tests. That review alone did not change this branch.

## 2026-09-11 — owner lifetime and observation hardening

Base: `05d4ebf3827ffbaf287d3d6d39ce4ef89c6ed3e8` on
`codex/g1-regular-handoff-20260910`.
Change set: `fix: harden G1 regular handoff offline safety and record validation`.

### Changes applied

- **R1 — owner lifetime:** `RunOwnerProtected` covers acquisition, the policy
  loop, post-loop logging, handoff, and normal returns. Recovery runs while the
  Controller and its dependencies still exist. Holding errors retain the same
  writer; stopped/uncertain-owner errors monitor without unconditional restart.
  A failed/throwing ReleaseMode is also treated as an uncertain outcome.
  Settle timeout, invalid LowState, or stale WriterFrame returns to current hold.
  Destruction stops callbacks before destroying their state/mutex members.
- **R1 — artifacts:** CSV Finish, hashes, result writes, and final handoff
  outcome writes are exception-isolated. `result.json` is explicitly a
  `pre_handoff_checkpoint`; `handoff.json` records the subsequent verified
  owner or persistent hold outcome. A logging failure is not reported as
  complete artifacts and cannot itself unwind an unresolved controller.
- **R2 — fallback:** create an inactive writer, make a fresh empty-service
  query, validate state and observation age, then recheck age immediately before
  enabling. A failed/slow query, changed owner, invalid state, or preparation
  error does not enable output. No GetFsmId call intervenes in this final query.
- **R3 — continuity:** reject non-finite, negative, repeated and reversed times;
  reset after invalid samples and excessive gaps. Verification rounds and
  inter-observation gaps are capped at **250 ms**, with a full **1 s** window.
  Settle observations use a **50 ms** maximum gap and **20 ms** WriterFrame age.
  These are conservative software candidate bounds based on the existing
  50/100 ms verification polling, 10 ms settle polling and 20 ms state timeout;
  they are NOT robot-timing measurements or physical safety approval.
- **R4 — meaning:** correct handoff-only console/launcher/documentation text.
  Keep the leg blend, PD gains, small-signal reference and motion limits intact.
- **R5 — tracked build graph:** native CMake defaults
  `BUILD_LEGACY_NATIVE_TARGETS=OFF`, so the cycle target does not depend on absent
  `twist2_vr_native_draft.cpp`, `pc_native_receive_probe.cpp`, or
  `twist2_mink_udp_trial.cpp`. Explicitly enabling missing legacy targets fails
  with the missing source name. The cycle executable remains EXCLUDE_FROM_ALL.
  This fixes the source-graph dependency, not the unverified ARM build/toolchain.
- Add a standalone `offline_handoff_tests` CMake project and
  `verify_regular_handoff_offline.py`. They use an explicit memory-only test
  allowlist and do not discover/load SDK, DDS, Torch, robot policy or transports.
  The native-graph test only configures with empty dependency path placeholders;
  it never compiles, links or executes any native/ARM target.

### Verification actually performed

All three configurations passed: GCC **14.2.0**, GCC **ASan/UBSan**, and Clang
**17.0.0**, using CMake **3.31.6** and assertions explicitly enabled.

- **6/6 C++ executables:** PD parser, small-signal trajectory, WriterFrame,
  continuity gate, fresh-owner/exception helpers, and real CSV worker failure.
- **13/13 Python tests:** existing analysis/control-flow coverage plus owner
  guards, candidate build graph, and extracted production handoff methods.
- The extracted-method harness ran **12 scenarios per configuration** against
  memory-only clock, mode/FSM, state and writer fakes. It covered settle error/
  timeout/stale WriterFrame, selection/CheckMode/GetFsmId exceptions, empty
  fallback, cached empty becoming ai, another owner, and slow RPC observations.
  This compiles the actual handoff methods, NOT the complete hardware Controller
  or its constructor, and is NOT SDK/DDS integration validation.
- WriterFrame stress: **20 additional repetitions per configuration**, each
  with **10,000** memory publications/reads. These are not DDS publications.
- Original controller/launcher/native-CMake and unchanged test dependencies
  used locally were checked against their GitHub blob identities before edits.
- Sanitizer runs emitted no sanitizer diagnostics. No robot connection, SSH to
  G1, DDS publisher/subscriber, SDK initialization, motor output, or ARM build/
  execution was performed. The unrelated user worktree was not reset or cleaned.

Reproduce on Linux/WSL with Python 3, CMake, CTest, and GCC/Clang, from the
repository root. Each command builds only in its own temporary directory:

```bash
python3 experiments/twist2_right_arm_manual/verify_regular_handoff_offline.py --output /tmp/g1-gcc.json
python3 experiments/twist2_right_arm_manual/verify_regular_handoff_offline.py --sanitizers --output /tmp/g1-asan.json
python3 experiments/twist2_right_arm_manual/verify_regular_handoff_offline.py --compiler clang++ --output /tmp/g1-clang.json
```

Exit 0 means these offline checks passed; it does not authorize actuation.

### Still unverified / next work

The full Controller with the installed Unitree SDK, real RPC latency/semantics,
SDK recurrent-thread destruction/join, ARM compile/link, remote source/build
state, robot executable SHA-256, PowerShell runtime behavior and physical
balance/support during handoff have NOT been validated. Source-order tests cover
the launcher block; no Robot/All launch is permitted to test it on hardware.
CheckMode-based rechecking cannot prove atomic ownership. Review the installed
service behavior and the candidate timing bounds before considering a physical
trial. Do not change the old launcher hash to a guessed value.

## Next actions after the G1 reconnects

1. Read-only check for an existing `g1_twist2_mink_cycle_trial` process.
2. Inspect the remote source/build state left by the interrupted build, the
   installed SDK, and actual CMake source/compiler/Torch paths. Do not reset or
   clean the wider worktree.
3. Rebuild only the reviewed ARM cycle target with legacy targets disabled and
   record its SHA-256. Do not execute it. Offline configuration with placeholder
   dependencies does not substitute for this real compile/link.
4. Keep `Robot` and `All` blocked until the final binary, owner semantics,
   timing results, and exact command are reviewed.
5. The first physical candidate remains `--handoff-only-trial`, with no intended
   arm trajectory, NOT guaranteed whole-body immobility. Do not run it during
   charging or without separate approval. Unexpected mode change, loss of
   support, sound or movement means a failed physical test.

## Continuing this handoff on GitHub

Append a dated entry here for each subsequent change set; retain older results
as historical evidence rather than silently replacing them. Read the current
branch head and this document before editing. Commit code, tests and the handoff
together to this branch, and verify the remote head after pushing. Do not
force-push over concurrent work.

Each entry must record: base commit and scope; files/behavior changed; exact
checks performed and pass/fail counts; checks not performed and remaining
risks; the next permitted action and physical launch-block status. Do not write
"fixed", "verified", "safe", or "complete" for a check that was only planned.

## 2026-09-11 — preserve VR-to-G1 operation; round-trip PD tuning is the objective

Base: `ded85fff529e6d143721683950056bbf016a190d`.
Scope: documentation only, recording the user's clarified priority. No runtime,
launcher, gain, trajectory, transport, build or deployed-binary change in this entry.

### User requirement and mode separation

The user reports that START_TWIST2_MINK_CYCLE_CANDIDATE already enabled a usable
VR-to-G1 workflow, although it was not perfect. Preserve that working capability.
The engineering objective is to find suitable PD gains using repeated round-trip
trajectories and measured responses, not to replace teleoperation or PD testing
with a handoff-only project. Regular handoff is supporting exit/ownership work.

- Preserve normal VR/Mink -> relay/UDP -> G1 operation via the existing launcher
  and `--udp-right-arm`. Do not silently default to PD sweep or handoff-only.
- `-PdSweep` / `--pd-sweep-trial` is the explicit repeatable PD experiment.
  `-HandoffOnly` / `--handoff-only-trial` is a separate ownership diagnostic,
  not a source of PD identification data or a replacement for normal operation.
- Preserve the deployed working baseline before deploying a modified candidate.
  Do not overwrite it merely because offline tests pass. Compare the actual
  PC launcher, input/relay dependencies, robot source, binary and command when
  access is permitted; the reported working local version has not been matched
  to an immutable Git commit in this review.

### What ded85fff did and did not change

The commit hardened lifecycle/exception handling, writer-stop synchronization,
fresh-owner fallback, verification continuity and artifact recording, and isolated
legacy build targets. It did NOT change the existing round-trip reference,
Kp/Kd candidate values, UDP packet adapter or target-generation files. The
launcher change was limited to Check-mode messages; trial selection and the
robot command were retained. However, lifecycle protection and the writer mutex
are shared by UDP and PD modes. Full VR-to-G1 timing/behavior after rebuilding
has NOT been revalidated; source-path preservation is not an end-to-end pass.

The inherited PD sweep excites joint 22 with ready -> +8 deg -> -8 deg -> ready,
three cycles per candidate. It changes Kp together on joints 22..25 to 40, 48,
and 56, with Kd fixed at 5; this is not an independent Kp/Kd search for every
arm joint. The small-signal reference already existed in 05d4ebf. Do not claim
that ded85fff found new PD values or introduced that amplitude change. Keep the
full-forward-reach physical restriction; restoring VR does not authorize that trial.

### Checks and next permitted action

Reviewed the ded85fff changed-file list/diff, both launcher versions, the current
PD reference, gain setter and UDP/PD dispatch. No new execution tests, hardware
checks or gain-selection experiments were performed for this documentation-only
entry; earlier pass counts above belong to their earlier change set.

The checked-in Robot/All block already existed in 05d4ebf and is still present:
this GitHub version cannot currently launch straight into the robot. It is an
operational restriction, NOT removal of the VR feature, and it was not lifted
while the G1 is charging. The charging/no-DDS constraint remains unchanged.
The handoff-only-first instruction above applies to validating the modified
handoff candidate; it does not redefine the normal VR operating mode.

Next offline work should support the round-trip comparison: audit repeatability,
logged commanded versus measured positions/velocities, actual gains and trial
completion, while preserving the existing VR mode. Before any later approved
physical use, reconcile the working baseline and candidate separately and review
the actual executable/hash and launch conditions. Do not auto-apply a selected
gain to normal VR operation or change the trajectory without recording its scope.

## 2026-09-11 — separate fixed-pelvis MuJoCo round-trip PD experiment

Base: `27a6134c7576898e2d793a72673a81a9c3532d0d`.
Scope: additive offline experiment. Existing VR launcher, runtime, UDP adapters,
C++ PD reference, live gains, XML/meshes and robot binary remain unchanged.

Added `mujoco_pd_contract.py`, `mujoco_pd_sweep.py`, tests, isolated requirements,
`tools/RUN_MUJOCO_PD_SWEEP.bat`, a GitHub-hosted offline workflow, and the usage
manual `experiments/twist2_right_arm_manual/MUJOCO_PD_SWEEP.md`.

The G1 XML is modified only in memory to fix pelvis. All 29 hinge states then
come from torque-driven mj_step, not qpos playback. Use the inherited joint22
+8/-8/ready reference (3 cycles), proximal-group gains, 50 Hz reference and
500 Hz writer limiting. Each pair starts from a reset MjData and identical
3 s warmup. The ideal internal PD is evaluated at the 1 ms physics timestep;
this is not a measurement of the actual G1 motor loop. dq_cmd and tau_ff are zero.

CSV separates original reference, limited command and simulated response.
Summary reports RMSE, overshoot, endpoint settling, speed/torque and limit/contact
ratios. Incomplete/contact/numerical/guard-failed or heavily limited trials are
excluded from ranking. No result is automatically applied to hardware.

Verification at this commit: 14 local math/summary tests passed, including
sample-by-sample comparison with the actual C++ PdSmallSignalTrial header and
100 randomized scalar limiter comparisons. Uploaded Python blobs were matched
to the locally tested file hashes. Local MuJoCo installation was unavailable
(network/package download failed); do NOT call this a passed dynamics run yet.
The workflow is configured to require MuJoCo, run the full dynamics suite and
3x3 sweep, and reject socket audit events during the sweep. Its actual result
must be recorded in a subsequent dated entry after inspection, not assumed.

Not verified: MuJoCo runtime at this commit, Windows launcher/GUI, free-base
TWIST2 standing balance, physical gains, actual handoff/SDK/ARM deployment.
Next permitted action: inspect and fix offline CI results, record measurements,
then compare timestep/model sensitivity offline. Robot/All remain blocked.

## 2026-09-11 — first dynamics CI result and CLI manifest fix

Base: `032f3462abbd09ed836eb76d3a3f550851bda790`.
CI evidence: Actions run `34563019765`, job `103149451841`.

The first GitHub-hosted MuJoCo run passed **19/19 tests** with Python 3.11.16,
MuJoCo 3.3.7 and NumPy 2.4.6. Actual torque-driven runs reproduced identical
40/5 traces from reset, different responses at 56/5, three full cycles, and
rejection of the deliberately unsuitable 1/0.1 pair. The five protected VR/PD
source hashes matched. These were simulated responses, not hardware tests.

The separate 3x3 CLI step FAILED before executing its sweep: `runpy.run_path`
provided a relative `__file__`, but the provenance manifest tried to make it
relative to an absolute repository root. No 3x3 ranking or artifact existed
in that failed run. Do not treat the passing unit suite as a completed sweep.

Changes: normalize source paths before hashing; add relative-path math coverage
and a real relative-runpy CLI regression that checks CSV/JSON hashes and refusal
to overwrite an existing result. Add only `/.venv-mujoco-pd/` to .gitignore to
keep the separate simulation environment out of Git. No control math, model,
trial limits, existing launcher, VR runtime, or hardware values changed.

Local math/summary suite now passes **15/15**. The two modified Python files
match the uploaded Git blob identities. The new full **21-test** CI suite and
3x3 sweep are to be inspected after this commit; no pass is claimed for them
at commit creation. Continue offline only and append the actual outcome here.
Windows GUI/launcher, timestep/model sensitivity, free-base TWIST2 balance,
actual SDK/handoff and G1 gains remain unverified. Robot/All remain blocked.

## 2026-09-11 — corrected MuJoCo fixture and completed nine-pair screening

Base and tested code: `516afef2f5ff74c3aaf198c091f890b6565b2e95`.
This final entry changes documentation only. Full failed-run history, contact
probe evidence, corrected metrics and artifact hashes are preserved in
[G1_MUJOCO_PD_VALIDATION_20260911.md](G1_MUJOCO_PD_VALIDATION_20260911.md).
Usage is in `experiments/twist2_right_arm_manual/MUJOCO_PD_SWEEP.md`.

### Changes and failed runs retained

After the CLI fix, `610c5bab` passed 21 tests and completed nine trajectories,
but all were contact-flagged and excluded; no accepted result was claimed.
`fcfb2160` added the contact probe and hosted diagnostic, which found two
active pelvis/hip assembly contacts introduced by fixing the free pelvis.
`516afef2` added `mujoco_pd_fixture.py` and six regressions, restoring only the
source model's three direct pelvis-child parent exclusions in the in-memory
fixture. Source XML/meshes, geometry masks and all nonadjacent collision checks
remain unchanged. This is not a blanket collision-disable or relaxed ranking.
The manual now explains this correction, and the supplemental record retains
the invalid earlier run rather than relabeling its results as accepted.

### Actual final validation

GitHub-hosted Actions **34564937652**, job **103155008114**, completed
**successfully** using Python **3.11.16**, MuJoCo **3.3.7**, NumPy **2.4.6**.
The completed job status and decoded output log were checked.

- **27/27 tests passed, no skips:** 21 main and six fixture tests, including
  actual dynamics, reset/repeatability, C++ reference parity, relative CLI and
  artifact integrity, unsuitable-gain exclusion and protected live-file hashes.
- Source free-root, broken fixed-root and corrected fixed-root collision tests
  passed. An added nonadjacent wrist obstacle still produced contact, proving
  that the relevant collision checks were not globally disabled.
- **9/9 Kp/Kd pairs completed and were eligible**, each with three cycles and
  **7,633 trial samples**. All recorded trial contact, torque-target-limiting,
  hard-clipping and slew-exceeded ratios were zero. No numerical/tracking/
  velocity guard interrupted these runs.
- The full sweep ran with Python socket audit events forbidden. No G1 network
  access, DDS, SDK, physical motor execution or deployed gain change occurred.

In this fixed-pelvis model and tested grid, **Kp=56, Kd=3** had the lowest
joint22 ORIGINAL-reference RMSE: **0.014649809182167359 rad**, compared with
**0.025205712094970766 rad** for **40/5**. The full nine-pair table is in the
supplemental record. These are simulation-screening results, not independently
identified gains for all arm joints, global optimality, or a hardware recommendation.
`recommended_hardware_gains=null` and `hardware_config_modified=false` remain.

Successful output is retained in Actions artifact **mujoco-pd-fixed-pelvis**,
ID **10185682363**, run **34564937652**: run/summary JSON and nine candidate
CSVs, 11 files total. Its configured retention is 14 days; compact numerical
results and provenance are also committed in the supplemental document.

### Preservation, limitations and next permitted action

The existing `START_TWIST2_MINK_CYCLE_CANDIDATE.ps1`, robot runtime, UDP/Mink
adapters, C++ PD trajectory, source XML/meshes and physical gains were not
changed by this MuJoCo work. The five protected runtime/reference blob checks
passed. All commits were added to this branch without force-pushing.

The new simulation launcher is `tools/RUN_MUJOCO_PD_SWEEP.bat`; it uses a
separate `.venv-mujoco-pd` environment and never starts the real launcher.
Actual verification was on hosted Linux, not local Windows. Windows BAT/GUI,
timestep and parameter/payload/delay sensitivity, free-base TWIST2 standing
balance, actual motor behavior and physical handoff remain unverified.

Next permitted work is offline sensitivity/comparison around the screened
candidates, retaining this reproducible baseline. No automatic gain deployment.
Robot/All blocks and the charging/no-DDS restriction are unchanged. No physical
trial is authorized by a passed MuJoCo workflow.

## 2026-09-11 — completed two-timestep comparison and independent CSV verification

Verification implementation: `1c983195c12f509d89e27036117f612e91a70ed6`.
Result document: `40582a8308c1d229c168f58a817718824e1b8618`.
This append-only closeout preserves the concurrent `7262645d` documentation
and all previous code. The full two-grid table, provenance, artifact identifiers,
usage and limits are recorded in
[G1_MUJOCO_PD_TIMESTEP_20260911.md](G1_MUJOCO_PD_TIMESTEP_20260911.md).

The added read-only result verifier and seven artifact tests are separate from
the unchanged simulation engine. `.github/workflows/mujoco-pd-sensitivity.yml`
runs both full grids and verifies their CSVs; the previous workflow is retained.
No VR launcher, UDP adapter, LowCmd controller, C++ reference, live gain,
source model/mesh or deployed binary was modified by this verification addition.

Inspected Actions **34565313166**, job **103156119792**, on **1c983195**:
**success**, Python **3.11.16**, MuJoCo **3.3.7**, NumPy **2.4.6**.

- **34/34 tests passed, no skips:** 21 main, six fixture and seven artifact tests.
- **18/18 candidate runs completed and were eligible:** all nine pairs at
  **1 ms** and **0.5 ms**; three cycles and **7,633 trial samples** per run.
- All recorded trial contact, arm torque-target limiting and arm hard-clipping
  ratios were zero. CSV hashes, continuous 500 Hz timestamps, actual gains,
  cycle/segment coverage, recomputed metrics, eligibility and ranking passed.
- The full ranking was identical at both timesteps. Maximum relative reference
  RMSE change was **0.18366134615613872%**. The best tested pair remained
  **56/3**, with joint22 reference RMSE **0.014649809182167359 rad** at 1 ms
  and **0.014676715218920633 rad** at 0.5 ms.
- Protected live-file identity tests passed. The sweeps rejected Python socket
  audit events; no G1, DDS, SDK or physical motor program was used.

Artifact **mujoco-pd-timestep-comparison**, ID **10185845868**, run
**34565313166**, contains **23 files**: 18 CSVs, two run manifests, two summaries
and validation.json. Retention is 14 days; the compact table and hashes are
committed in the linked report. The base workflow on the same tested commit
also passed (run **34565313037**, **27 tests** plus its nine-pair 1 ms sweep).

The earlier "timestep sensitivity unverified" entries are historical; the two
configurations above are now checked. Timestep also changes the ideal motor
PD evaluation rate, so this is NOT pure integrator convergence. Model/payload/
friction/delay sensitivity, free-base TWIST2 balance, Windows BAT/GUI, physical
G1 gains and real handoff remain unverified. The winning pair lies on the grid
boundary and is not a proven optimum or a hardware recommendation.

Next permitted work: offline uncertainty/expanded-grid comparison while
preserving this baseline. No automatic gain application or replacement of the
working VR setup. Robot/All remain blocked during charging; no physical trial
is authorized by these completed simulation checks.


## 2026-09-11 — expanded PD grid and torque-path uncertainty screening

Base `b61def51ae57cac7a31daf9d169abece6a5cd615`; retain all earlier results as historical evidence.
Added expanded/model driver, torque-delay/lag/friction driver, independent
compressed-trace auditor and tests. One pre-existing test assertion now accepts
native Windows manifest separators. Existing dynamics engine, C++ reference,
VR launcher/UDP/LowCmd code, XML/meshes and live gains were not changed.

Actual runs:448 expanded/model +270 motor/friction =718 attempts;
678 completed/eligible,40 excluded.192 coarse +56 fine distinct nominal pairs.
100/0.1 wins nominal RMSE but passes only9/18 motor/friction conditions.
100/1,100/2,80/1 pass18/18;100/1 has the lowest worst-case error among fully
eligible pairs in that15-pair comparison. Boundary Kp100 is not a proven
optimum or a hardware recommendation. No automatic deployment.

Final tests:60 passed,1 skipped,zero failures/errors.
The one skipped test needs a C++ compiler absent on this Windows host.
All718 traces were reloaded and hash/metric/cycle/eligibility checked;
15 common nominal q22 arrays matched exactly. Other-joint aggregate metrics
and physics counters are recorded but not fully reconstructed from compact
joint22-only traces. Exact source/model bytes were checked against manifests.

The actual local vanilla/StandardMinkPlanner/UpstreamMinkTracking route was
inspected, not assumed to use hierarchical proximal cost100. PD bypasses IK;
no damp/cost change or IK optimum is claimed. Uncommitted local VR work was
not overwritten or merged into this isolated experiment.

Full protocol, measurements and limits:
[G1_MUJOCO_PD_EXPANDED_20260911.md](G1_MUJOCO_PD_EXPANDED_20260911.md).
Compact evidence:`docs/validation/g1_pd_expanded_20260911/`.
Raw traces retained at`C:\Users\user\Documents\G1_PD_Expanded_20260911`.
No G1, DDS, SDK, motor output, GUI/BAT, ARM build or deployment.
Fixed pelvis and hypothetical torque-path uncertainty do not validate standing
balance or real motor behavior. Robot/All blocks remain. Next work:offline only.


## 2026-09-11 — strict all29 inner-limit PD acceptance

Base `78f50f5d5232bbb67418e0557ae8992e686ceb69`. Implemented the user requirement as a mandatory offline
limit envelope, NOT a deployed physical stopping controller.

Added joint_limit_guard.py and its tests; integrated default preflight/command/
pre-step/post-step/final-state checks in mujoco_pd_sweep.py. Added exact718-plan
replay and evidence tests; added guard dependency hashes to expanded/motor
manifests, manual documentation and an isolated hosted all-joint test workflow.

All29 joints use the existing soft/XML-onset intersection plus0.05rad inner
reserve. Equality, command modification, exhausted directional stopping budget
or active joint-limit constraint refuses the trial. No qpos projection,
reference substitution or relaxed XML/real limit. Stopping assumptions are20ms
reaction,2rad/s² outward acceleration and1rad/s² braking, not measured G1 values.

Actual Windows replay:718 conditions,678 eligible,40 rejected.
Rejections:28 warmup,6 measured velocity,6 earlier stopping-envelope refusals.
No observed soft/hard touch. Accepted minimum soft margin=0.211798601708536rad,
XML-hard margin=0.261798601708536rad.89 tests passed,1 legacy C++
compiler-dependent check skipped,0 failures/errors. Hosted CI not yet claimed.

All718 q22 traces reloaded and metric/hash checked;20,822 all-joint minima
witnesses and pre/post/final coverage checked. Full all29 trajectories are not
saved or independently reconstructed; raw per-step observations are reduced
to minima/witnesses/events. This is not an absolute physical no-contact proof.

Details: [G1_JOINT_LIMIT_GUARD_20260911.md](G1_JOINT_LIMIT_GUARD_20260911.md).
Evidence: `docs/validation/g1_pd_limits_20260911/`. Raw retained at`C:\Users\user\Documents\G1_PD_JointLimits_20260911`.

Preserved live VR/UDP/controller/C++reference, source model/meshes and gains.
No G1 connection,DDS,motor output,ARM build or deployment. Original dirty
worktree untouched; Robot/All block remains. Next permitted work:offline only;
calibrate braking/latency and review actual-owner integration before any later
physical adoption. Do not describe simulation refusal as a physical hold.


## 2026-09-11 — hosted all-joint verification completed

Tested code `8dbe3bc4304882b9bae3775c2bcc359a56193dd0`. Inspected Actions run **34584881165**,
job **103216672502** (`all-joint-limits`): **success**. The full decoded job
log reports **90/90 tests passed, no skips**, including the original C++
reference compilation/parity check skipped on the Windows host. Hosted
Ubuntu24.04.5, Python3.11.16, MuJoCo3.3.7, NumPy2.4.6. The tests ran in79.105s.

The earlier hosted-pending entry is historical. This append and hosted_ci.json
record the observed outcome; they do not change code, model parameters,
thresholds, the718-case result, VR/G1 configuration or deployment state.
The full718 replay was on the isolated Windows host, not rerun by this90-test
workflow. No physical guarantee, robot connection, DDS or motor output.

Evidence: `docs/validation/g1_pd_limits_20260911/hosted_ci.json`.
Next permitted work remains offline; actual braking/latency and hardware
owner integration must be validated before a physical guard is deployed.


## 2026-09-11 — robust PD refinement protocol and verified offline regressions

Base `6b1421703bfef6a8ac2a84687ced15e2be8124fa`. Additive optimization driver,
regressions, usage manual and isolated CI. No modification of the existing
PD engine, all29 limit envelope, torque path, C++ reference, XML/meshes, live
VR/UDP/controller code, motor gains or IK damp/cost. All physical blocks remain.

The prespecified search compares44 pairs over the SAME27 existing motor/model
conditions (1188 simulations). No nominal-only shortlist substitutes for this
common-condition comparison. All27 must pass before minimizing worst original
reference RMSE. Freeze the best6 plus fixed controls before checking8 separate,
prespecified holdout scenarios. Do not retune on the holdout outcome or increase
the existing Kp100 ceiling. Missing/rejected cases are not selectable.

Actual validation before this code commit:19 new tests passed. The full local
allowlist then passed108 tests, skipped1 C++ compiler-dependent parity test,
with0 failures/errors out of109. Windows Python3.11.9/MuJoCo3.3.7/NumPy2.4.6.
The smoke study is8 cases, not the full experiment. It verified zero-change
parity with the existing guarded motor engine and original trace, minimum
margin evidence, holdout isolation, duplicate/missing case refusal and artifact
modification detection. The new hosted workflow includes the C++ parity test;
its outcome is NOT claimed before inspection.

The full optimization is running at this commit; final counts, ranking and
holdout pass/fail are not yet claimed. Its source/model identities are frozen
in the run manifest. Append the inspected full result instead of replacing
this historical entry. Usage: experiments/twist2_right_arm_manual/MUJOCO_PD_ROBUST_REFINEMENT.md.

The original dirty PC worktree remains untouched; computation uses a detached
worktree. No robot, DDS, SDK, motor execution or deployment. Fixed-pelvis and
hypothetical motor/model uncertainty are not physical validation. Next permitted
work is to complete/audit this offline plan and record its outcome.


## 2026-09-11 — completed robust PD refinement and held-out validation

Tested code `7577ed97fcf1f0ae8e9edf4777ef03f9dabaf380`; base `6b1421703bfef6a8ac2a84687ced15e2be8124fa`.
This append closes the previous running entry without changing the engine or
relabeling prior results. Full protocol/table/limits:
[G1_PD_ROBUST_REFINEMENT_20260911.md](G1_PD_ROBUST_REFINEMENT_20260911.md).

Actual isolated Windows study:1268 attempts,
1188 calibration +80 holdout;
1240 completed/1240 eligible/28 rejected.
44pairs saw identical27conditions; 10 finalists/controls were
frozen BEFORE eight prespecified holdouts. Selection rule and raw case hashes
were verified. Survivors in unchanged calibration order:[[100, 2.0], [80, 1.0], [56.0, 3.0]].
The first surviving pair in frozen calibration order is **100/2**. Its worst calibration RMSE is **0.0100312489177771 rad** and worst held-out RMSE **0.00975311816778928 rad**. The nominal RMSE is **0.00755652846809067 rad**. This is a finite-grid simulation screening result, NOT hardware gains or an optimum proof.

All29 guard, reserve, stopping assumptions and original limits remain.
Observed minimum soft/model-hard margins:0.211798601708536/0.261798601708536rad.
Guard reasons:{"joint_stopping_envelope_exhausted": 3}.
No physical safety invariant, hardware recommendation or deployment is claimed.

Local tests108pass/1C++skip/0fail. Inspected hosted run34589643742,
job103231729623:109pass/0skip/0fail, including C++ parity.
CI tests and eight-case smoke only; full study ran on Windows, not CI.
Reloaded1268 q22 traces and36772 all-joint
minimum/witness records. Full all29 trajectories are not independently replayed.
Raw source/model hashes and preserved original runtime paths were checked.

Evidence:`docs/validation/g1_pd_robust_refine_20260911/`.
Raw copied/hash-verified at`C:\Users\user\Documents\G1_PD_RobustRefine_20260911`.
Original live dirty worktree, VR/UDP/controller/C++reference, source XML/meshes,
physical gains and IK damp/cost unchanged. No real G1,DDS,SDK,ARM,GUI/BAT,
motor output or launch-block removal. Continue offline only.


## 2026-09-11 — accuracy and endpoint stability, frozen new validation

Base `41b25f87a7bbf959c658d1c023f74ebe260d3f23`. Additive offline search.
User objective: low tracking error AND stable response, with all previous
joint-limit restrictions retained. Do not equate low nominal RMSE with stability.

Added mujoco_pd_accuracy_stability.py, regression tests, usage manual and
isolated hosted workflow. Twelve fixed gain pairs share35 known conditions;
previous holdouts are explicitly now calibration data, not independent tests.
Ten NEW conditions are frozen before the first run. The first4 preferred pairs
plus100/2,80/1,56/3 controls are frozen before those new conditions are inspected.
No gains, thresholds or cases are retuned to rescue held-out failures.

Existing all29 limit/warmup/velocity/contact/command guards remain unchanged.
Additional performance screen: final100ms of all9 holds must have q22 error
<=0.02rad and speed<=0.1rad/s; all right7 tail p2p<=0.005rad and RMS speed<=0.05rad/s.
After all conditions pass, minimize worst original-reference RMSE. Within2%
of the calibration minimum, prefer less right7 tail RMS motion, then less
position variation. Report both accuracy leader and Pareto tradeoffs; this is
not proof that one pair simultaneously minimizes all objectives.

All29 q/dq/reference/command arrays are now also saved at500Hz for every run.
The independent reader recomputes endpoint metrics, verifies compact/full q22
parity, all29 sampled margins, physics-rate extrema/witness coverage and frozen
selection. Full physics-rate trajectories/continuous safety are NOT proven.

Actual code validation: four-case smoke completed and audited. Full local
allowlist135 discovered:134 passed,1 compiler-dependent C++ parity skipped,
0 failures/errors. Windows Python3.11.9, MuJoCo3.3.7, NumPy2.4.6. Hosted result
is not claimed at this commit. The full optimization is still running; append
its inspected outcome, counts, exclusions and source/artifact hashes afterwards.

Use `experiments/twist2_right_arm_manual/MUJOCO_PD_ACCURACY_STABILITY.md`.
Original guarded simulation engine, reference, model XML/meshes, live VR/UDP/
LowCmd code, IK damp/cost, physical gains and Robot/All blocks are unchanged.
No G1, DDS, SDK, physical output, ARM build or deployment. Live dirty PC worktree
is not reset/cleaned/overwritten. Next action: finish/audit this offline study.


## 2026-09-11 — completed accuracy/stability comparison and full-state audit

Base `41b25f87a7bbf959c658d1c023f74ebe260d3f23`, tested code `f4078fdd3309019a888d47c05197cc05fe118029`. This closes the running entry above.
Actual full study:490 attempts,420 known-condition calibration,
70 new validation, 487 completed,
487 old-guard eligible, 482 endpoint-quality eligible.
Added quality criteria are performance screening, not model-limit relaxation.
First survivor in the frozen calibration preference is **100/1.3**. It passes35/35 known and10/10 new conditions. Worst calibration RMSE=0.00932800765182386rad, worst new-condition RMSE=0.00922649250092812rad. This is a finite-grid, finite-horizon simulation candidate, not deployed hardware gains or a proven optimum.
Frozen survivors:[[100.0, 1.3], [100.0, 1.4], [100.0, 2.0]]. Calibration-only accuracy leader:[100.0, 1.1].
All rejected conditions and unselected candidates remain explicitly distinguished.

Base reasons:{"ready_pose_not_settled_in_final_warmup_second": 3}.
Quality reasons:{"max_q22_tail_error_rad": 5}.
Guard events:{}.
All29 minimum soft/XML-hard margin:0.211798601708536/0.261798601708536rad.
No real-world stability/limit invariant or optimality proof is claimed.

Local134pass/1compiler skip/0fail; inspected hosted run34593608750 job103244239811:
135pass/0skip/0fail including C++ parity. Full study on Windows; CI tests+smoke only.
All490 compact/full trace pairs and 4452271 full29
500Hz sample rows audited; physics extrema/witnesses and frozen selection verified.
Continuous-time/full physics-rate trajectories are not reconstructed.

Details:G1_PD_ACCURACY_STABILITY_20260911.md.
Evidence:docs/validation/g1_pd_accuracy_stability_20260911/.
Raw copy/hash verified at`C:\Users\user\Documents\G1_PD_AccuracyStability_20260911`. Existing reference, guarded engine, live
VR/UDP/LowCmd/IK settings, source XML/meshes and real gains remain unchanged.
No G1,DDS,SDK,physical output,ARM deployment or launch-block removal.
Continue offline; do not auto-apply simulation candidates.


## 2026-09-11 — strict minimum-error finite-grid search started

Base `1d7b1f76111034a468774e5748eae8d30da5b42d`. User prioritizes the lowest
tracking error while retaining stable behavior and every all29 limit rule.
Additive experiment only: mujoco_pd_minerror.py, tests, manual, isolated CI.
The guarded dynamics, all29 inner reserve/stopping assumptions, quality
thresholds, original roundtrip, C++ contract, model limits and live paths are
unchanged. No IK damp/cost or actual gain change.

This experiment explicitly replaces the previous2% accuracy preference WITHIN
ITS OWN ranking only: first require every known quality condition, then minimize
worst ORIGINAL-reference RMSE; endpoint motion only breaks exact numerical ties.
482 distinct pairs: broad Kp16..100 plus Kp96/98/99/99.5/100 and Kd1.200..1.350
at0.005 resolution, with comparison controls. Kp100 ceiling is retained.
45 previously observed scenarios are now known calibration.16 new scenarios
are frozen before the first run (seed20260911 parameter generation, not random
motor noise). Do not call reused conditions fresh validation.

Rerun the seed controls over all45 to establish feasible bounds. A partial
maximum error is a lower bound on a candidate's final maximum; a strictly
worse bound can exclude it without all remaining simulations. Every grid cell
gets a full result, an actual failed-constraint witness, or a pruning proof
referencing a fully tested incumbent. Keep those categories distinct; report
ACTUAL simulations, not the full482x45 Cartesian product. Eight top fully tested
pairs plus seed controls are frozen before the16 new conditions are run.
Discrete-grid calibration optimality is not a continuous or physical optimum,
and the shortlist does not prove whole-grid optimality on unobserved conditions.

Validation before this commit:24 new tests passed including actual six-case
smoke and full-state audit. Initial prototype smoke caught a tuple/list
serialization comparison issue; JSON normalization was fixed before the full
run, without a dynamics change. Complete Windows allowlist159 discovered:
158 passed,1 C++ compilation test skipped,zero failures/errors. Hosted outcome
not yet claimed. Full optimization is in progress; append audited outcomes,
actual counts, exclusions and hashes afterwards. Source/model identities are
frozen in manifest.json; failed smoke evidence is retained separately.

Usage:experiments/twist2_right_arm_manual/MUJOCO_PD_MINERROR.md.
No robot connection,DDS,SDK,motor output,GUI/BAT or ARM deployment. Working VR
files and original dirty PC worktree are not overwritten. Charging-time
Robot/All blocks remain. Finish and audit this offline plan before promoting
a simulation candidate; never auto-apply it to G1.


## 2026-09-11 — strict minimum-error search completed and audited

Base `1d7b1f76111034a468774e5748eae8d30da5b42d`; tested code `1d768b7cefe44adc4027346aa17f9af1a10e385a`. Closes the running entry.
482 grid decisions;1161 actual simulations
(1001 known +160 fresh).
Completed1100; base eligible1100;
quality eligible938.
Decision classes:{"bound_pruned": 248, "constraint_rejected": 223, "fully_evaluated": 11}.
Known-grid winner:[100.0, 1.275].
The first strict-calibration-order validation survivor is **100/1.275**. Known45 worst RMSE=0.00930442651158736rad; fresh16 worst RMSE=0.00952406318834176rad. This is a bounded finite-grid, finite-horizon simulation candidate, NOT a physical optimum or deployment.
Survivors:[[100.0, 1.275], [100.0, 1.28], [100.0, 1.285], [100.0, 1.29], [100.0, 1.295], [100, 1.3], [100.0, 1.325], [100.0, 1.35], [100.0, 1.4], [100, 2.0]]. Pruned conditions were NOT run or claimed
stable; each exclusion has an actual constraint or minimax-bound witness.
Verified minimum is restricted to this finite grid and45 known conditions;
it is not an optimum over all unseen conditions, continuous gains or hardware.

Base refusals:{"joint_stopping_envelope_exhausted": 10, "measured_velocity_limit": 3, "ready_pose_not_settled_in_final_warmup_second": 48}.
Quality refusals:{"max_q22_tail_error_rad": 162, "max_right7_tail_p2p_rad": 2, "max_right7_tail_rms_speed_rad_s": 3}.
Guard events:{"joint_stopping_envelope_exhausted": 10}.
Minimum soft/model-hard clearance:0.211798601708536/0.261798601708536rad.
No relaxed stability threshold, limit, reference or live gain.

Reloaded1161 full/compact traces,10120147 full29
sample rows and33669 extrema records; all482 grid
decisions, incumbent witnesses, frozen hashes and scores checked.
135 seed full-state trajectories match previous data exactly.
Local158pass/1C++skip/0fail; inspected hosted run34602915247 job103274322288:
159pass/0skip/0fail. Full experiment on Windows; CI tests+smoke only.

Details:G1_PD_MINERROR_20260911.md; evidence:docs/validation/g1_pd_minerror_20260911/.
Raw retained/hash-verified:`C:\Users\user\Documents\G1_PD_MinError_20260911`. Earlier records preserved.
No G1,DDS,SDK,motor output,VR/IK change,ARM deployment or launch-block removal.
Original dirty live tree unchanged. Continue offline; no automatic gain adoption
or absolute physical stability/limit guarantee.


## 2026-09-11 — coupled uncertainty and complete matrix started

Base `884882d8175676caac7e852547de90b48aa1c700`. User requests more coverage,
not a claim that all continuous gains or every possible operating condition
has been tested. Additive offline study, no hardware or live-path changes.

Added mujoco_pd_coupled_stress.py and mujoco_pd_coupled_matrix.py with tests,
manual and isolated CI. Twelve fixed gain pairs see the same65 calibration
conditions:nominal + all64 combinations of right-arm mass/inertia scale,
passive damping scale, friction scale, torque delay, torque lag and timestep.
Unlike earlier separate model/motor trials these factors coexist in one model.
All780 calibration cells are simulated without pruning. Freeze top6 plus
controls, then16 new seeded combined validation conditions. A separate matrix
completion stage executes ALL missing non-finalist cells too, for a prescribed
12x81=972 actual attempts. Original selection remains historical; the full81
ranking is explicitly descriptive after all conditions have been observed.
Missing or early-refused cells are never counted as completed motions.

The original +/-8deg joint22 reference, grouped gains22..25, Kp100 ceiling,
all29 guards, 0.05rad reserve, stopping assumptions and endpoint-quality policy
are preserved. Strict worst original-reference RMSE is the objective only after
all constraints pass. No qpos projection, limit expansion, new feedforward or
IK damp/cost adjustment. Model changes are in private MjModel instances only;
mj_setConst propagates mass/inertia updates. Torque delay/lag is hypothetical,
not measured G1/network behavior. All29 sampled traces and physics-rate limit
witnesses are retained and independently read back for checks.

Observed pre-commit validation:24 new coupled tests passed, including exact
nominal, motor-only and model-only parity against existing guarded trajectories.
The full local allowlist then passed182 tests, skipped1 original C++ compiler
parity test, zero failures/errors(183 discovered). Ten separate new matrix tests
also passed. Thus192 distinct local tests passed,1 skipped; repeated24-test runs
are not added again. Windows Python3.11.9,MuJoCo3.3.7,NumPy2.4.6.
Hosted193-test outcome is pending, not yet claimed. Four-case smoke and artifact
audit passed. The full972-cell study is still running; final counts, rankings,
failures and hashes will be appended after observed completion and audit.

No G1 connection,DDS,SDK,motor output,ARM build,deployment or launch-block removal.
Original dirty live PC tree and all existing VR/UDP/LowCmd/IK/model files remain.
Usage:experiments/twist2_right_arm_manual/MUJOCO_PD_COUPLED_STRESS.md.
Next permitted step:complete/audit this offline plan; no automatic gain adoption.


## 2026-09-11 — coupled uncertainty full matrix completed and audited

Base `884882d8175676caac7e852547de90b48aa1c700`; tested code `47b85fe66ee43a3a841b3d9657568ec8d00f5ac1`. Closes the running entry above.
Every declared12gain pairs x81conditions was actually attempted:972 runs,
969 completed/969 endpoint-quality eligible.
The first-stage780 calibration+128 frozen validation
is preserved;64 supplemental runs fill every unselected cell too.
No pruning, no hidden missing cases, and no failed attempt counted as three cycles.
The lowest worst-error pair that passed all81 conditions among these12 tested pairs is **100/1.4**. This is only the finite tested matrix, not every continuous or real case.
Complete descriptive ranking does not become independent future validation data.

Base reasons:{"ready_pose_not_settled_in_final_warmup_second": 3}.
Quality reasons:{}.
Guard events:{}.
All29 min soft/model-hard clearance:0.211798601708536/0.261798601708536rad.
Original reserve, stop assumptions, endpoint quality and model limits unchanged.
Prior100/1.275 evidence is historical, not a universal stability assertion.
See G1_PD_COUPLED_20260911.md for complete table and failure configurations.

Local192pass/1C++skip/0fail; inspected hosted run34609334553 job103295578442:
193pass/0skip/0fail. CI tests+smoke only; full972 matrix ran in isolated Windows.
Re-read972 compact/full29 traces,8854377500Hz sample rows and
28188 extrema records; source/model hashes, all cells,
mutation evidence, frozen selections and ranks verified. No continuous-time proof.
Raw copied/hash-verified at`C:\Users\user\Documents\G1_PD_Coupled_20260911`.
Evidence:docs/validation/g1_pd_coupled_20260911/.

Live dirty tree, VR/UDP/LowCmd/IK settings, real gains, XML/meshes and Robot/All
blocks preserved. No robot connection,DDS,SDK,motor output or ARM deployment.
All possible cases remain untested; continue separately scoped offline work only.


## 2026-09-12 — wider operating-envelope verification started

Base `4b9dde3d0c11e54672e71243ed0092ebae70b017`. User requests substantially
more coverage. Add a separate operating core and full-matrix runner, tests,
manual and hosted workflow; retain original VR/UDP/LowCmd, simulation engine,
model XML/meshes, joint-limit guard, actual gains and IK damp/cost unchanged.

Declared plan:1728 actual attempts, no pruning. Main1440=12 group-gain pairs
x4 independently excited proximal joints22..25 x5 motion/start profiles x6
combined model/motor scenarios. Long288=12pairs x4axes x3 repetition/soak/start
profiles x2scenarios. Maximum12round trips,30s extra hold, amplitudes4/8/12deg,
speed caps10/20/30deg/s and elbow baseline offsets+/-10deg. This explicitly
extends the offline reference; it does not replace the original C++ trial.
The original0.05rad reserve and29-joint pre/post/final checks remain, and the
new engine also rejects post-step velocity violations, including the last step.

Endpoint tolerance is unchanged in value and now applies both to joint22 and
the actually excited axis. Preserve right7 residual-motion checks; audit every
hold and the whole last second of an extended post-hold. Worst original-reference
RMSE is selectable ONLY after every declared cell passes. If no common group
pair qualifies, report none rather than relaxing tolerance or hiding an axis.

Observed before this commit:36 new tests passed, including exact all29 default
parity with the inherited engine, coupled-model parity, generalized references,
non-pitch excitation, final-state limit fault, reference/score/trace tampering
and a two-case smoke audit. That smoke reproduced the nominal23-axis endpoint
error failure at100/1.4; do not equate the former22-only optimum with a common
four-axis optimum. The full1728 study and complete legacy allowlist are running;
final counts, hardware-free coverage and hosted result are NOT yet claimed.

Use experiments/twist2_right_arm_manual/MUJOCO_PD_OPERATING.md. Full29 sampled
states/torques and physics-rate guard witnesses are recorded. Fixed pelvis and
hypothetical motor parameters are not physical balance, thermal/noise/backlash
or continuous-time safety validation. No G1,DDS,SDK,motor output,ARM deployment,
robot launcher execution or launch-block removal. Original dirty live tree is
not reset/cleaned/overwritten. Append inspected completion and failures here.


## 2026-09-12 — operating matrix completed and audited

Base `4b9dde3d0c11e54672e71243ed0092ebae70b017`; tested implementation `df0620d800bf37b57dc414b2a85f7848fd7035c7`. Closes the running entry above.
1728 actual attempts:1440 main+288 long. Completed1636;
quality eligible1226; rejected502.
NONE of the12 tested common group-gain pairs passes every operating cell. No common PD optimum or hardware gain is promoted.
Keep prior22-only optima scoped; other-axis endpoint error was not formerly
part of that optimization objective. Do not promote a partial/failed group.

Every12pairs x144operating cells was attempted:four individual proximal axes,
4/8/12deg amplitudes,10/20/30deg/s speed caps,elbow start shifts,12repeats and30s
post-hold. Original C++ reference/engine/VR control is not replaced by this
separate operating runner. Same tolerances now cover the excited axis as well
as22. The post-step velocity check includes the final step. No threshold or
joint limit was relaxed; no compensation or projection added to hide errors.
Base failures:{"ready_pose_not_settled_in_final_warmup_second": 92}.
All exclusion labels(overlapping):{"active_tail_error_rad": 410, "post_hold_last_second_not_settled": 64, "ready_pose_not_settled_in_final_warmup_second": 92}.
Guard events:{}.
All29 observed minimum soft/model-hard margin:
0.211798601205472/0.261798601205472rad.

Read back1728 full29 traces,19602672 sampled rows and
50112 guard extrema records. Source/mesh hashes,
analytic held references, matrix coverage, scores/quality and rankings verified.
The initial local test wrapper failed on Windows spawn; its evidence is retained
and the entire suite was rerun using a corrected local wrapper without code changes.
Final local228pass/1C++skip/0fail; inspected hosted run34616834178 job103320746401:
229pass/0skip/0fail. Full study on Windows; CI tests+smoke only.

Report:G1_PD_OPERATING_20260912.md. Compact evidence:
docs/validation/g1_pd_operating_20260912/. Raw retained/hash-verified at`C:\Users\user\Documents\G1_PD_Operating_20260912`.
Nominal roll static/trace diagnostics are descriptive, not real motor identification.
Original live dirty tree, actual gains,VR/UDP/LowCmd/IK,source model and launch
blocks are preserved. No robot,DDS,SDK,motor output or ARM deployment. No thermal,
noise/backlash,free-base or continuous-time guarantee. Continue separately scoped
offline per-joint verification; do not auto-apply a common group candidate.


## 2026-09-12 — independent PD search started

Base2ae59402367def9d28e823c59e81bc09a5a8040e. User asks to find optimal PD after
common gains failed roll endpoint accuracy. Additive per-joint research only.

Introduce mujoco_pd_perjoint.py, mujoco_pd_perjoint_study.py,27tests, usage and CI.
Only the isolated simulator extends joint23 Kp search cap from100 to300 because
observed pure-PD static load error remained above0.02rad at100. The300 cap is a
research bound, NOT a motor rating or physical permission. Original hardware,
C++ and normal simulator100Kp validators remain intact, as do joint/torque/velocity
limits, inner reserve, stopping assumptions and all endpoint criteria. No feedforward,
integral action, target bias or IK adjustment. Actual gains are explicit vectors.

Protocol:40roll pairs x6cases; coordinate-search22/24/25; freeze deduplicated
candidate vectors and verify each on all144previous operating cells; freeze up
to3 passing vectors before48new operating cases. Fresh parameters are fixed in
manifest before main dynamics; they are hypothetical, not measured probabilities.
No data from fresh validation changes candidates, policies or the main result.
No global optimum is implied by coordinate search or a capped grid.

Observed before main execution:12exploratory probe runs retained separately,
not included in formal study counts. Increasing roll Kp reduced nominal error;
low Kd failed delayed dynamics, so nominal error alone cannot select a candidate.
27new tests passed, including exact old-engine all29 trajectory parity with uniform
gains, pure-PD torque readback, unchanged live validator, reference/limit tampering
checks and JSON summary roundtrip. Initial test assertion compared tuple/list;
its expectation was corrected without a controller change. Full suite and full
study outcomes remain pending; append actual audited results, not planned counts.

Working VR/UDP/LowCmd/IK, source XML/meshes, actual gains and Robot/All blocks are
unchanged. Isolated worktree, no G1 connection/DDS/SDK/motor output or deployment.
Usage:experiments/twist2_right_arm_manual/MUJOCO_PD_PERJOINT.md. Complete the
current offline experiment/audit; never copy research gains to the live launcher.


## 2026-09-12 — deterministic per-joint result processing correction

The1020formal integrations finished on4eed0c5b763f03b121a1929eacd53c3ae750c97b.
Final audit rejected summary comparison because as_completed ordered failure
lists differently from the case-id readback. Verified that sorting ONLY those
failure lists makes the original/rebuilt summaries identical: counts, all
numeric metrics, eligibility, rankings and selected vector are unchanged.

Fix make_summary by sorting input records by case_id; add reverse-input-order
regression. No controller, source model, candidate, threshold or simulation
trace change.28per-joint tests passed after this correction. Original full
suite had255pass/1C++skip locally,256/256pass on inspected hosted run34623413791,
job103342607795. Those hosted counts apply to4eed0c5, not this processing patch.

Retain original summary and all48manifest source/model/mesh inputs byte-for-byte
under the raw result folder. Corrected audit uses that original input archive,
not a rewritten provenance manifest. CaseJSON/trace and frozen selection remain
unchanged. Complete the saved-data audit before final outcome promotion. No
additional dynamics or physical/G1/DDS operation is part of this correction.


## 2026-09-12 — independent PD search completed and audited

Base2ae59402367def9d28e823c59e81bc09a5a8040e; dynamics4eed0c5b763f03b121a1929eacd53c3ae750c97b; processing768a2355ea5b716137858851eb2f721ce023e783.
1020formal runs=240roll+108coordinate+576operating+96fresh;978completed,886eligible.
12pilot runs and unit tests are separate.57distinct gain vectors observed.
Selected SIMULATION vector22..25:Kp=[100.0, 300.0, 100.0, 100.0],Kd=[1.4, 4.0, 1.4, 1.4].
It passed144/144old operating+48/48new prespecified cases, including all4axes,
changed amplitude/speed/start,12cycles and30s holds. Worst activeRMSE
0.011962761307211rad; worst endpoint error0.0178481020382143rad.
Nominal roll RMSE0.0230798161033409 ->0.0084943385038965rad(63.195814% lower),
with peak torque3.04551853307257 ->3.4126274894744Nm. No feedforward/integral.
Lower-Dcoordinate failed4/144and was excluded; common100/1.4passed108/144.
Higher-Dcomparison passed192but had higherworstRMSE. No global optimum claimed.

IMPORTANT:rollKp300is research-only, outside unchanged hardware100cap. Never
copy it to VR/G1 or widen livevalidation. Physical gains, reference/innerreserve,
torque/velocity/joint limits, stopping assumptions, IK damp/cost were not changed.
42post-stepvelocity refusals+92completed endpoint failures;6overlap posthold.
No joint-limit guard events; minsoft/modelhard0.211798601205472/0.261798601205472rad.
Not an absolute physical stability or limit-contact guarantee.

Full audit reloaded1020full29traces,11,159,730 rows sampled at 500 Hz and 29,580 witnesses.
Ordering-only initial audit failure preserved/corrected; every number, ranking,
selection and raw trace unchanged. Original48input files hash-verified separately.
All144baseline trajectories exactly match prior operating study. Final local
256pass/1C++skip; inspected hosted257pass/0skip,run34626120122,job103351536341.
Full matrix ranWindows; CItests/componentdynamics only.

Report:G1_PD_PERJOINT_20260912.md; evidence:docs/validation/g1_pd_perjoint_20260912/.
Raw:C:\Users\user\Documents\G1_PD_PerJoint_20260912. Dirtyliveworktree,VR/UDP/LowCmd/IK,actualgains,XML andRobot/Allblocks
preserved. NoG1,DDS,SDK,actuation,ARMdeployment. Continueoffline; noauto-adoption.


## 2026-09-12 — final PD optimization/review entry point started

Base0634844115368a5e910e07891ec2fcacb221f857 (includes completed per-joint evidence).
Add mujoco_pd_final.py,25tests,RUN_MUJOCO_PD_FINAL.bat,manual and isolated CI.
Modes optimize/finalize/verify connect the existing bounded per-joint search to
strict source audit, frozen extra conditions, full-state reread and review JSON.
Do not rerun or replace the accepted per-joint source merely to obtain new counts.

Require144operating+48prior-fresh passes before selecting up to2 vectors in the
original operating minimax order. Freeze6new combinations x4separately excited
axes per vector (48planned integrations). Additional endpoint gate checks ALL4
proximal joints, including inactive ones, under unchanged0.02rad/0.1rad/s limits.
Every original rejection remains; entire last1s post-hold checked. All29 reserve,
stopping and model constraints unchanged. No PD/IK/feedforward/VR modifications.
Export only a simulation-review candidate, never a robot config or actuation command.

25new tests passed, including actual MuJoCo2-case bundle with mocked source
fixture, source/trace/decision/policy/hardware-field tampering and failed-gate
handling. Initial fixture expected a tuple from JSON and a full500samples from
exactly1s post-hold; corrected those TEST expectations/profile (2s fixture), not
controller or formal conditions. Initial3assertion failures retained as test
history; final25/25 passed. Full282-test allowlist and48formal additional cases
are running; completion and hosted counts are not claimed in this entry.

Original1020-case study gets fully reaudited, archived input bytes stay immutable.
Joint23 research cap300 does NOT widen live100cap; export flags all cap hits and
keeps hardware_approved=false/recommended_hardware_gains=null. Source/model byte
identity required for verify; do not substitute an untested checkout. No G1,DDS,
SDK,publisher/subscriber,motor output,ARM deployment or Robot/All unblocking.
Usage:experiments/twist2_right_arm_manual/MUJOCO_PD_FINAL.md. Append results after
actual completion; no global/continuous optimum or physical finalization claim.


## 2026-09-12 — final PD review completed; simulation-only candidate retained

Base0634844115368a5e910e07891ec2fcacb221f857; tested code
c9aea11d1774a823104d10f662896c5c358cfe5a. Closes the running entry above.
The reusable optimize/finalize/verify path is implemented. This execution used
finalize on the completed1020-case source, then standalone verify(exit0).
Source1020 integrations were audited, NOT rerun or counted as new dynamics.
New48integrations(two vectors x24frozen conditions) all completed and passed.

Retained SIMULATION vector22..25:Kp=[100,300,100,100],Kd=[1.4,4,1.4,1.4].
Prior192/192 conditions keep the prior criteria; additional24/24 check ALL4
proximal endpoints, including inactive axes, and entire last1s final hold.
This does not retroactively assert the new all4 criterion over the old192.
Selected new worst activeRMSE0.011031113650149922rad; descriptive worst over216
0.011962761307210974rad. Alternative sameKp,Kd=[3,5,3,3] also24/24, new worst
0.011236348013604548rad. No final-outcome retuning or selection-order change.
All4 Kp are on research caps; roll300 exceeds unchanged live100 cap.
Hardware_approved=false,recommended_hardware_gains=null; no deployable optimum.

No relaxed all29 reserve, stopping envelope, model limit, torque or velocity
criterion. No guard events; minima soft/modelhard/stopping slack:
0.2117986012054719/0.2617986012054719/0.1605986012054719rad.
Recorded torque-limiting and clipping ratios0. No qpos projection or new bias,
feedforward, integral or IK damp/cost change. Fixed pelvis/individual excitation
is not simultaneous VR, full-body or continuous-time physical safety proof.

Reread1020original cases and48new full29traces; new1,173,280rows at500Hz and
1,392margin records. Local282discovered:281pass/1C++compiler skip/0fail.
Inspected decoded hosted run34629170943,job103361523344 on tested code:
282pass/0skip/0fail including C++ parity. CI regressions/component dynamics,
not formal48 or a rerun of1020. Optimize routing was mocked; actual finalize
and verify modes executed. Pythonhelp and BATmissing-env exit2 checked; full
configured-env BAT simulation untested. Later BAT-only help exit-status fix
leaves the frozen computational Python code unchanged.

Raw final bundle confirmed atC:\Users\user\Documents\G1_PD_Final_20260912;
122files/879998674bytes. Original source study remainsG1_PD_PerJoint_20260912.
Raw final manifestSHA=f9d9543d7a7f4ffb5076b9cf325e508de4d25eef83f5aa6a3b95019b875bc28a;
raw candidateSHA=b3a501fa560e8e26c7284093083203fdfa5be27a608514de04afb39be81f110a.
After successful simulation/audit/export the PC connector stopped responding.
Closeout is published directly through GitHub. Compact observed result and CI
metadata are in docs/validation/g1_pd_final_20260912/; raw48-case CSV/full-state
files are confirmed onPC but NOT uploaded by this fallback. Do not claim a
complete raw-log GitHub upload. Local isolated worktree has not received this
fallback commit; read remoteHEAD and reconcile without resetting live files.

Report:G1_PD_FINAL_20260912.md; manual:experiments/twist2_right_arm_manual/MUJOCO_PD_FINAL.md.
Original live dirty tree unchanged at last successful status check. No G1SSH,
DDS,SDK,publisher/subscriber,motor output,ARM deployment or Robot/All unblock.
Final hardware tuning remains blocked by actual drive limits/rates/delay,
simultaneous VR/free-base behavior,payload/braking/noise/thermal/SDK review.
Never copy researchKp300 into liveG1 or call a bounded coordinate search a
universal optimum. Continue offline or separately approved hardware review.


## 2026-09-12 — simultaneous-axis PD verification started

Base bb642d11f0ea91c9aa97862996319027ced6602c. Continue offline on an isolated
worktree; the working VR tree has uncommitted changes and is not reset/edited.
Add a separate multiaxis core/study,32tests,manual and hosted workflow.
The original simulation cores, live gains, model files, IK and launch blocks stay.

Both accepted research vectors are frozen: Kp[100,300,100,100], with
Kd[1.4,4,1.4,1.4] versus[3,5,3,3]. Kp300 remains outside the unchanged live100
validator. This stage validates simultaneous motion; it does not retune gains.
Plan256main+32long=288attempts: all16 sign combinations on4axes, two basic
profiles and4known model/motor scenarios; additional large/long signed profiles.
All29 guard and unchanged endpoint/velocity/contact/torque checks remain.
Each of4axes is scored; no low partial error can hide a failing joint/condition.
No independent phase-shifted, recorded VR, free-base or physical claim.

Observed before formal execution:32/32new tests passed, including exact full29
single-axis parity on22..25, simultaneous motion, vector torque equations,
all4endpoint scoring, command-at-limit refusal, socket denial, frozen-source/
trace/plan/policy tampering, missing-cell refusal and two-case smoke audit.
Full288study and314-test allowlist are not yet claimed; append inspected results.
Raw outputs will retain full29traces, extrema, frozen sources/models and exact plan.
No G1 connection,DDS/SDK,publisher,motor output,ARM deployment or live config edit.
Usage: experiments/twist2_right_arm_manual/MUJOCO_PD_MULTIAXIS.md.


## 2026-09-12 — simultaneous matrix audited; yaw-specific refinement started

Tested multiaxis implementation dd96aebd0a55360fac93ea099b480cb69e108a39.
All288planned cells executed:208completed/eligible,80stopped for post-step
measured velocity. Both original vectors pass104/144,not all144. All80failures
are delay_boundary (mass1.35,damping0.85,friction0.15,delay4ms,lag8ms,dt0.5ms);
maximum final upper-joint speed is joint24 in every failed run. Nominal80/80,
half64/64,heavy64/64 passed; delay_boundary0/80. No final multiaxis candidate.
This does not erase the earlier independent-axis passes or validate arbitraryVR.
Raw:Documents/G1_PD_Multiaxis_20260912. Full288trace audit passed,2,455,975
full29sample rows and8,352guard extrema. No limit events; minima soft/hard
0.2117986012054719/0.2617986012054719rad. Local314suite:313pass,1C++skip.
The ambiguous compound REPL commit request was blocked by the terminal tool;
explicit,reviewable git staging/commit/push later succeeded without force.

Next separate study changes ONLY joint24 Kp/Kd; all other gains and every
controller/model/quality/limit rule remain fixed. Add yaw refinement runner
and17tests. Grid42pairs x3known simultaneous conditions=126screen attempts.
Freeze best2all-pass vectors for each144operating cells, then freeze survivors
for24new prespecified conditions each. No subsequent retuning or ranking from
new outcomes. All conditional phase plans and selection hashes are audited.
17/17new tests passed, including real-vector torque/full-state audit, complete
matrix decisions, field corruption and failure refusal. Full study is not yet
claimed. All caps unchanged; no G1,DDS,SDK,physical output or live/IK edits.


## 2026-09-12 — simultaneous validation and yaw refinement closed

Implementations dd96aeb (initialmatrix),649a052 (focusedsearch); basebb642d1.
Initial288attempts:208pass,80post-stepvelocity aborts,all80withjoint24fastest
in thedelay-boundary condition. Neitheroriginalvectorpassed144/144.
Separate yaw study:462attempts,427completed,409eligible;
phasecounts{"operating": 288, "screen": 126, "validation": 48}. Selectedsimultaneousvector
{"kd": [1.4, 4.0, 1.0, 1.4], "kp": [100.0, 300.0, 72.0, 100.0]}. Allothergains,limits,model andcriteriafixed.
Newgainvector does NOT inherit old216single-axis passes. No globaloptimality
or hardwareapproval,especiallyunchangedlive100boundversusresearchroll300.
Allstagesaudited fromfull29traces,sourcearchives,plansandfrozenselections.
Initial2455975sampledrows; yaw4978359rows.
Guardevents initial{},yaw{}.
Local313pass/1C++skip plus17newpasses; inspectedCI331pass/0skip,
run34687197494,job103536139776. FullmatricesonWindows,CIregressionsonly.
Report:G1_PD_MULTIAXIS_20260912.md; compactevidence:docs/validation/g1_pd_multiaxis_20260912/.
Raw:Documents/G1_PD_Multiaxis_20260912 andG1_PD_MultiaxisYaw_20260912.
320protectedfilehashes anddirtylivetree statusunchanged. NoG1,DDS,SDK,
physicaloutput,ARMdeployment,VR/IKedits orlaunchunblocking. Continueoffline
validation ofnewgains; neither genericVR nor realstability is certified.


## 2026-09-12 — yaw candidates: individual-axis regression started

Base 649a052124b195b7c039124144759af0fb234757. Recovered and packaged the
completed 288-case simultaneous study and 462-case yaw refinement, rather than
repeating them or counting them as new runs. The recorded 72/1 and 64/1 yaw
candidates pass their own 144+24 simultaneous cases. They do not inherit the
previous 216 single-axis passes from the different 100/1.4 yaw vector.

Add mujoco_pd_yaw_regression.py, 27 tests and its usage manual; extend the existing
multiaxis CI allowlist. Freeze both accepted yaw vectors in source operating order
and run 216 known individual-axis conditions per vector (432 integrations).
Use exactly one nonzero scale in the unchanged multiaxis core. This preserves
individual-axis dynamics but applies endpoint criteria to all four proximal
axes, including stationary axes, on every new run. Old condition names "fresh"
and "final" are history labels here, not claims of unseen validation data.

Observed before this commit: all 27 new tests passed, including real two-case
bundle audit (mocked source receipt), exact original-engine full-state parity,
wrong/missing/tampered evidence, frozen-source refusal and failure exclusion.
The first 22-test pass is a subset, not 22 additional tests. Prior 331-test hosted
run 34687197494/job 103536139776 on 649a052 passed with no skips; decoded logs checked.
The new full 358-test suite and 432-run regression are in progress, not yet claimed.

All original simulation/VR/UDP/LowCmd/model files and real gains are unchanged.
Kp23=300 remains research-only, outside the unchanged live100 bound. No G1,
DDS/SDK, publishers, physical output, deployment or launch-block removal.
Append measured outcomes and verification after completing the new readback.


## 2026-09-12 — yaw regression completed and audited

Implementation25095da; recovered prior750attempts are historical, not new.
Actually executed432new individual-axis regressions, completed432,eligible432.
Both source yaw finalists see identical216knownprofiles; all4endpoint rules
apply to inactive axes as well. No old gain-vector passes were inherited.
Selected research vector:{"kd": [1.4, 4.0, 1.0, 1.4], "kp": [100.0, 300.0, 72.0, 100.0]}.
A passing vector now has168source simultaneous +216own individual conditions,
not a global optimum or new384condition holdout. Kp23=300still exceeds live100.
Reaudited source462 and new432traces,5786288new29-joint rows,
12528extrema; standaloneaudit-onlyexit0.
Guardevents{}; minsoft/hard/stopslack
0.2117986012054719/0.2617986012054719/0.1605986012054719rad.
No changed reference, feedforward, limits, quality, IK or actual hardware gains.
Local357pass/1C++skip; inspected hosted358pass/0skip,run34689112317,job103541156241.
CItests only; formal432matrix onWindows.27new tests include mocked-source
two-case bundle; no fixture counted as a formal full study.
Report:G1_PD_YAW_REGRESSION_20260912.md; evidence:docs/validation/g1_pd_yaw_regression_20260912/.
Raw:C:\Users\user\Documents\G1_PD_YawRegression_20260912. RawNPZretained onPC,not uploaded; inventory hashes preserved.
320protectedsourcehashes anddirtylivestatusunchanged. NoG1,DDS,SDK,
actuation,deployment orRobot/Allunblocking. Continueoffline; nothardwareapproval.
Descriptive combined384minimum is {"kp": [100.0, 300.0, 64.0, 100.0], "kd": [1.4, 4.0, 1.0, 1.4]}, RMSE0.011938015614587846, 0.064767%below frozen72/1survivor. Do not claim72/1is the combined minimum or retune from this audit.


## 2026-09-12 — independent-clock simultaneous verification started

Base402e1ed9e20fcac98caca2c696158409f1fc83fa. Next stage validates timing beyond
synchronized signs or isolated axes. Add a separate timing core/study,35tests
and manual; extend the existing CI allowlist. Both yaw64/1 and72/1 vectors are
frozen with otherKp[100,300,*,100],Kd[1.4,4,1,1.4]. No gain retuning.

Plan96actual attempts: two vectors x8synthetic timing/start/period/soak profiles
x6model/motor conditions, including the known coupled delay-boundary. Each axis
uses its own continuous rest-to-rest path and start clock. Original control
loop, model/torque mutations, bounds, all29guard and0.05reserve are unchanged.
Own-axis holds use the same numeric thresholds; all4and right7rest checks apply
at the shared final hold. Intentionally moving other axes are not treated as
residual motion. New acceptance mapping does not reclassify earlier results.

Observed before formal run:35/35new tests passed, including exact synchronized
full29state parity, staggered dynamics, own-window bias, wrist/common-rest motion,
missing/tampered source/trace/plan/metrics, frozen vectors and socket refusal.
Two initial TEST assumptions failed (nonoverlapping hold/cross window and wrong
text spelling of existing gain bound); assertions corrected, not controller or
formal conditions. Earlier failure record retained. Full393suite and96study
are running; do not claim their final counts or candidate yet.

No live tree reset/overwrite, G1,DDS,SDK,publisher,motor output,IK changes or
Robot/All unblock. Research rollKp300still outside unchanged live100validator.
Usage:experiments/twist2_right_arm_manual/MUJOCO_PD_INDEPENDENT_TIMING.md.
Append audited outcome; neither synthetic clocks nor finite passed matrices
prove arbitraryVR stability, full-body balance or physical deployment safety.


## 2026-09-12 — independent-study elapsed-time aggregation correction

All96formal integrations on bbc4b55 finished and passed their run criteria.
The first full readback rejected only simulated_seconds: parallel completion
sum3067.4730000001064 versus case-order sum3067.473000000107seconds. No score,
gain, pass flag, condition or trajectory differed. Do not label the first
failed post-processing command successful.

Use math.fsum for future totals. Readback permits1e-9second absolute tolerance
ONLY on total simulated time; all scores/rankings/other fields remain exact.
Only the known archived pre-fix runner hash is recognized as compatible;
every original physics/model/other source byte stays strict. Raw manifest,
summary, caseJSON and NPZ are retained unchanged; archived code is not executed.

Observed correction validation:40/40dedicated tests passed (five new rounding/
source-compatibility regressions), standalone96case audit exit0,1,533,780all29
500Hzrows and2,784margin records reread. Earlier local393suite passed392with
oneC++compiler skip; current398suite/hosted result are not yet claimed.
No new dynamics were needed for this processing-only correction. Same frozen
96case plan, gain vectors, guards and live paths. Append final inspected result.


## 2026-09-12 — independent-clock study completed and audited

Base402e1ed, dynamicsbbc4b55, aggregation615b96a. Executed96formal integrations:
two frozen vectors x8profiles x6scenarios, all96completed/eligible. Twelve
synchronous controls plus84independent-clock runs. Yaw72/1 is the new48case
minimax choice, with otherKp[100,300,*,100],Kd[1.4,4,1,1.4]; both pass48/48.
The new-condition error reduction is3.494076% versus64/1. Prior384descriptive
maxima still slightly favor64; do not claim universal72dominance. No retuning.

All29limits/reserve and numeric criteria remain. Own-axis rest windows and
common final right7rest are explicit; no intentionally moving-axis false failure.
No earlier pass retroactively assigned this mapping. No guard events; minimum
soft/hard/slack=0.211798601205472/0.261798601205472/0.160598601205472 rad.
Read back all96traces, 1,533,780 full29sample rows, 2,784 minima records.
First postprocessing failed only from total-time sum roundoff; raw manifest,
summary, cases and NPZ unchanged. Recognized original runner and1e-9s total-time
comparison fix passed standalone audit(no dynamics). Scores remain exact.

Final local397pass/1C++skip; hosted398pass/0skip, run34692035188, job103548879462.
CItests/component dynamics only; formal96study onWindows. Dedicated40tests pass.
Report:G1_PD_INDEPENDENT_TIMING_20260912.md.
Evidence:docs/validation/g1_pd_independent_20260912/.
Raw:C:\Users\user\Documents\G1_PD_IndependentTiming_20260912; NPZonPC,notGitHub. 359 protected hashes andliveGitstatus unchanged.
NoG1,DDS,SDK,actuation,IK/livegain edit,ARMdeployment orlaunchunblock. RollKp300
stillresearch-only above live100cap. Synthetic clocks are NOT recordedVR or
full-body/physical proof. Continue offline, no automatic gain adoption.


## 2026-09-12 — recorded seven-joint target comparison started

Base f5672cdd28ddc93cc0e89a98f1af6169b7763f09. Add isolated recorded-input
parser, replay core/study and42tests. Preserve previous dynamics/VR/IK/model
files and all hardware settings. Both yaw64/1 and72/1 candidates remain frozen;
rollKp300 is still simulation research above the unchanged live100cap.

Read the explicit cycle_packets_20260910_150530_0603774.jsonl PC-send recording.
One complete target episode:1618samples,27.453s PCsend /26.95s source clock;
all7right-arm targets move. Source SHA2562710d76445c3e004f811567b38f289e8451a47fb2960d43576b021a9e87f7871.
This is not measured robot response or proof of target acceptance. Bulk log
analysis was not completed; do not claim coverage of all recordings. Replay
uses original unscaled goals, captured today speed caps, two clock assumptions,
3s ready warmup and explicitly appended5s final hold. Score recorded segment
only, and require all7final errors/speeds. Original29guards and conservative
1.5rad/s measured upper speed remain. No protocol or full-body simulation claim.

Observed before formal execution:42/42new tests passed. Initial tests found a
local/global wrist-index mistake in a fixture and numpy-scalar time rejection;
fix local index and allow finiteReal replay time without weakening JSON numeric
validation. No formal condition or threshold changed. New suite/24formal runs
are not yet claimed; append inspected outcomes after full original-input audit.
No G1,DDS,SDK,publisher/subscriber,live environment edit,actuation,ARM deployment
or Robot/All unblock. Manual:MUJOCO_PD_RECORDED_TARGETS.md.


## 2026-09-12 — raw target and causal command-pipeline outcomes

Direct24case experiment: processing/audit completed, but all24trajectories
stopped at wrist27 command-governor intervention after0.58/0.60s of input.
Nominal send case command slope2.26021rad/s exceeds1.66967rad/s governor bound,
while modeled joint speed is0.07107rad/s and soft clearance1.54610rad. This is
NOT measured hard/soft contact or proof of physical PD instability. All original
raw input, frozen sources, partial traces and failures are retained.

Add a SEPARATE fixed20ms causal command-ramp comparison, with13passing tests.
No lookahead, input rescaling, original-score change or guard/limit relaxation.
It is explicitly a PD+prefilter pipeline, not an unchanged-controller/PD-only pass.
Ran24additional cases on identical source bytes, two frozen vectors, two clocks
and six models.22completed/eligible; both candidates fail one delay-boundary
PC-send case each at post-step yaw24velocity1.505838/1.515689rad/s. No selected
filtered-pipeline vector. Do not rescue partial low errors or alter thresholds.

Source-target audit passed on both sets:43080+395920all29rows;1392joint extrema.
Dedicated42+13tests passed. Full Windows/hosted counts still pending inspection.
An attempted documentation append had a REPL block-termination error; source
and raw simulation data were unaffected. Existing VR,SDK/DDS,G1launch/gain/model
settings remain untouched. Append inspected CI and packaged evidence next.


## 2026-09-12 — recorded-target pipeline verification closed

Base f5672cd; implementation5398312463bcd29864b20bb7859d406e1c020a91.
Executed48NEWintegrations using ONE complete recorded seven-joint PC-send target
session, two clock interpretations, six model conditions, and two frozen yaw
candidates. Direct24:0trajectorycomplete/eligible, alljoint27command-governor
refusals. Separate causal20mscommand interpolation24:22complete/eligible, two
joint24post-step measured-speed failures in the PC-send delay-boundary condition.
Both yaw64/1 and72/1 pass11/12only in the filtered pipeline. No all-condition
candidate and no retuning. Do not rank partial lowerrors or relabel the original
rejected pipeline. RollKp300 still research-only above unchanged live100cap.

Raw record1618targets,27.453sPCsend/26.95ssource clock, provenance send_attempt,
NOT measured robot response or verified motor acceptance. Three repeated send
timestamps retained. No scaling or altered original score target. Warmup3s and
finalhold5s are explicitly synthetic additions; only original recorded segment
enters trackingRMSE. Bothrawinputs and24cell plans are byte-identical across the
two experiments. All original numeric guard/quality bounds remain unchanged.

Direct nominal joint27command slope2.26021rad/s exceeded governor1.66967rad/s,
while modeled actualspeed0.07107rad/s andsoftclearance1.54610rad were benign.
This is NOT observed soft/hardcontact or physical instability. Causal cases
failed yaw24 at1.505838/1.515689rad/s versus conservative1.5bound; nojoint-envelope
events in that phase. Live-today speed rules are not equated with this stricter
offline gate. The prefilter is additive offline research, not deployedVR code.

Readback passed for43080direct+395920causal full29rows and696+696guardminima.
Standalone audit-only commands both exited0,with no newdynamics and unchanged
rawmanifest/plan/summary/inputSHA. All55newtests passed. FinalWindows453discovered,
452pass/oneexistingCPPskip,0failures. InspectedLinux453/453pass,0skips,
run34696117419/job103559778760 on5398312. CIcomponent tests are not additional
formal cases. Initialtwo unit-test errors and documentation REPL input error
were corrected without changing conditions,limits,originalsource or rawdata.

Report:docs/G1_PD_RECORDED_TARGETS_20260912.md.
Evidence:docs/validation/g1_pd_recorded_20260912/.
Raw:Documents/G1_PD_RecordedTargets_20260912 andG1_PD_RecordedRamp_20260912.
RawJSONL/NPZ remain onPC; compactCSV/JSONreports andhashinventories onGitHub.
All438protectedsourcehashes anddirtyliveGitstatusunchanged. NoG1SSH,DDS/SDK,
actuation,ARMdeployment,IK/livegain/model edits orRobot/Allunblock. Nextoffline
work must separate command-generation timing from yawtuning and regress new
vectors across priorconditions; no automatic adoption or hardwareapproval.


## 2026-09-12 — recorded-pipeline roll/yaw refinement started

Base 450f4241c61143236f0530e89138e8152885c0c3. The user requests further PD
research, not deployment. Keep the causal20ms pipeline fixed and preserve the
raw rejected prior study. Add a separate coordinate-search runner and24tests.
Yaw36vectors x3knownconditions; then roll20vectors x3conditions at the best
all-pass yaw. Freeze up to4 finalists for both clocks and all6models, followed
by14declared synthetic regression cases per replay survivor. Stage dependencies
and all plans are recorded before their execution. No global optimum or new
holdout claim. Only a process-local research context extends rollKp300to350;
all old files, actual hardware gains, input bounds, model limits and guards stay.

Observed:24/24new tests pass, including full-state baseline parity, actual350
simulation and audit, scope restoration, stage selection, failed-case exclusion,
tampered manifest/trace/score refusal and synthetic smoke. The full study is now
running; its counts and selected candidate are not yet known. Smoke is not
formal data. Append actual results and final regression/CI outcomes after audit.
No G1 SSH, DDS/SDK, live publisher, VR/IK edit, deployment or launch unblock.
Usage: experiments/twist2_right_arm_manual/MUJOCO_PD_RECORDED_ROLL_YAW.md.


## 2026-09-12 — recorded roll/yaw refinement completed and audited

Base450f424; implementationa7602dd91c0c6c003f9bb473edfe718fe49877f0.
Actually ran272new integrations across55distinct vectors:108yaw,60roll,
48recorded validation and56synthetic regression.227completed/eligible;
45excluded:24stopping-envelope and21post-step speed failures. Do not hide the
failed cohort or describe all272as completed trajectories. Every declared
cell in each conditional phase was attempted; unit tests are not formal cases.

Fixed causal20ms pipeline and original recorded7joint score reference.
No new recording/holdout: same previously observed1618target episode and
hypothetical model conditions. Bounded coordinate search, not global optimization.
Separate process-local roll cap350restores old300on exit. Original hardware100
validator, guards, model ranges, torque/speed limits and real gains unchanged.

Selected filtered-pipeline candidate: Kp22..25=[100,300,64,100],
Kd=[1.4,3,1.2,1.4]. All12recorded cells and14declared synthetic regressions pass.
Three other finalists also26/26pass; no old hundreds of passes are inherited.
Roll275/3with sameyaw64/1.2 is a useful lower-Kp comparison: recorded worst
0.014015164998115616rad versus selected0.014014588331269116rad, only0.004114761225%
difference. The275candidate has slightly lower synthetic worst error.
All recorded minimax scores are dominated byjoint22; do not claim300uniquely
optimal or higherrollalwaysbetter.350/5and325/4passed3/3screen conditions but
were not top-two-roll finalists and did not receive full12+14validation.

Selected26cases have no guard events and minimumstopslack0.10584676943408566rad;
peakupperspeed1.2322443701578378rad/s, recordedfinalerror0.010221682262337994rad.
Global soft/modelhard minima0.21179860120574887/0.2617986012057489rad.
Global stopping slack -0.010142237703702373belongs to rejected trials; it is
NOT a safe margin. All29reserve0.05,pre/post/finalchecks and numeric quality
thresholds remain unchanged. No observed positional limit contact; no absolute
physical braking/no-contact or balance guarantee. Kp300/350stillresearch-only.

Re-read272full29traces:3,802,512sample rows at500Hz and7,888joint extrema.
Both automatic and standaloneaudit-only passed. Six original recording cases
match prior causal-run arrays,metrics,eligibility and refusal reasons exactly.
Dedicated24tests pass; inspected Linux477/477pass,zero skips,
run34699671159/job103569085281 on a7602dd. FinalWindows477discovered,
476pass/oneexistingC++skip,zero failures/errors. Earlier temporary local test
harness lacked a multiprocessing main guard; its owned process tree was stopped,
harness corrected and full suite rerun. Retain failure receipt; formal data and
repository simulation code were unaffected. CI is not the272case formal study.

Report:docs/G1_PD_RECORDED_ROLL_YAW_20260912.md.
Evidence:docs/validation/g1_pd_recorded_roll_yaw_20260912/.
Raw:C:\Users\user\Documents\G1_PD_RecordedRollYaw_20260912;616files,3046738352bytes.
RawJSONL/fullNPZonPC,notGitHub; compact plans, metrics, failures and hashes saved.
All446protectedhashes anddirtyliveGitstatusunchanged. NoG1SSH,DDS/SDK,
publisher,realoutput,ARMdeployment,VR/IK/livegain/model edits orlaunchunblock.
Continue offline with wider/newrecorded inputs and pitch22/wrist27 errors;
do not overwrite prior unfiltered failure or promote research gains tohardware.


## 2026-09-13 — pitch22 and wrist27 research started; compute relocation

Base43fd4ea11a2d057853688a943a16a6d0505e21fb. Keep causal20ms command mapping,
original-goal scores and all safety/quality thresholds unchanged. Add a separate
pitch/wrist runner,28tests and manual. Pitch15pairs x3conditions, wrist12pairs
x3conditions at the best pitch, up to4 finalists x16recorded conditions, then
14known synthetic regressions per survivor. Only this process-local adapter
permits pitchKp160 and wrist27Kp40; oldcap files/live100validator remain unchanged.
No G1,DDS,SDK,VR/IK,model limits or actual gain edits.

Observed before formal execution:28/28dedicated tests pass, including exact
old-baseline arrays, extended pitch/wrist dynamics+audit, wrist-specific torque
fields, scope restoration, unchanged guards and artifact tampering refusal.
Formal local startup refused insufficient disk BEFORE creating an output or
integrating a case. PC free space was falling during this task. Do not delete
prior logs or weaken the2GB disk reserve. A lossless LZMA storage probe gave
insufficient savings; it changed no simulation or prior data. No formal result
is yet claimed. Relocate compute using an approved simulation-only GitHub bundle.

The private repo receives only exact original lines950..3940 of the existing
recording:2991lines,1085109bytes, exportedSHA4d5b4c3477c45cd25160dfd80dc08b3c318f7e37c4cb4df62277b1482464453f.
OriginalSHA2710d76445c3e004f811567b38f289e8451a47fb2960d43576b021a9e87f7871.
All1618target arrays, both clocks, sequences/events and1373ACKcount match exactly.
No token/secret/password/credential key was found. Full original log stays onPC.
Export provenance is recorded; this is not new data or delivery/robot measurement.
An export-check script initially referenced a nonexistent attribute; querying the
existing metadata API fixed that check, and the full equivalence check passed.
Append final actual simulation, audit and hosted CI outcomes after inspection.


## 2026-09-13 — standalone compute dependency correction

The portable source archive initially omitted the canonical joint-name tuple
module hardware/g1_arm_bridge/g1_joint_contract.py. Standalone import refused
before simulation. Added that exact existing module to packaging and the new
study source-hash dependency set. Its blob b8b8e2f793c9b295e8048ab0efec62a085385b53
was checked after transfer. No gains, dynamics, grids, input, guards or thresholds
changed. Preserve the failed import log separately; rerun dedicated tests before
formal execution in the isolated Linux runtime. PC space remains insufficient.


## 2026-09-13 — pitch/wrist investigation completed; no all-condition candidate

Base43fd4ea; implementation1db575f, provenance fixb9c14d2e9f1033eb2f8d40c2ea164bc3db1eb010.
Executed145NEWformal integrations in isolated ChatGPT Linux, not onPC/hostedCI.
26distinct full gain specs; phases45pitch+36wrist+64recordedvalidation+0regression.
133completed/eligible;12refused (7stopping-envelope,5post-step speed). All four
finalists15/16; regression entry condition not met, plan empty, no inherited
synthetic passes. selected_filtered_pipeline_spec is null. Do not claim a winner.

Under the SAME12known conditions,pitch120/1+wrist27 30/1 gives worstall7RMSE
0.0118017425371684rad versus baseline0.014014588331269116 (15.7895883%lower);
wristerror0.009424094299826978 versus0.013735342449834119 (31.3879917%lower).
Otherroll/yaw/elbow fixed300/3,64/1.2,100/1.4. Fixedcausal20mscommand filter,
original unsmoothed outgoing-goal score. Same known1618target episode, not new
operator data or motor acceptance evidence. No gains/model/threshold retuning
after validation. The research adapter extends only pitchcap160/wrist27cap40;
real100validator unchanged. No bare-PD or realG1approval.

All4fail sendclock newmix_a (mass1.1,damping0.7,friction0.2,torquedelay6ms,lag6ms,
dt1ms). Baseline failsyaw24;120/1+wrist20/1failselbow25; bothwrist30finalists
failyaw24. Correct reading: offline1.5rad/s criterion exceeded, not proof of
physical instability or positional contact. Newmix_b andother15cells pass.
Globalsoft/modelhardmin0.21179860120574887/0.2617986012057489rad. Stopping slack
-0.019975967903626435rad is fromREJECTEDruns; do not report safe positive margins.
All29reserve0.05,pre/post/final,torque/speed/settlingchecks unchanged.

Automatic and separateaudits passed:145full29traces,2392319sample rows,4205minima;
CSVsha87f00b26602d6fc217554a2df8e085b8688f7e129f9bd3b461e0fb3d0e1eecc6.
Dedicated28passWindows/28passLinux. Inspectedhosted505/505pass,0skips/failures,
run34704567847/job103582176999 onb9c14d2,includingC++parity (842.073s).
FormalenvPython3.13.5/MuJoCo3.3.7/NumPy2.4.6; hostedtestsPython3.11.16.
Windowsformalstart refused disk beforecreatingoutput; no oldlogsdeleted.
Portablemissingtupledependency fixed beforeformalruns; no changed dynamics.

Report:docs/G1_PD_PITCH_WRIST_20260913.md; compactreceipts in
docs/validation/g1_pd_pitch_wrist_20260913/. FullCSV/plans/metrics/failures/audits
are in attached204141byte evidenceZIP; fullraw1,898,970,936byte/364fileZIP in
conversation sandbox,NOT PC Documents orGitHub. RawZIPCRCpassed;sha
7de22496e7c970f3488d62bd467f67cc5329b6407fe24be40faa6160b890f3f3.
Do not claim the entire raw/evidence archive was pushed. All260protectedhashes
anddirtyliveGitstatusunchanged. NoG1,DDS/SDK,actuation,ARM,VR/IK/real gain/model
edit orlaunchunblock. Nextallowedofflinework: separate yaw/elbow delay study
then fulldeclared regression. Preserve this no-candidate result unchanged.
