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
