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
