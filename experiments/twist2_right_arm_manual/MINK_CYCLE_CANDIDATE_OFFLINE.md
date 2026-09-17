# Absolute Mink cycle candidate — offline only

This is a separate C++ sample consumer, not a robot executable. Existing
`twist2_mink_udp_trial.cpp`, `MinkUdpTarget` and `InputValidator` are unchanged.
No SDK, socket, publisher, policy worker or robot writer is included.

## Run the local verification

From the project root on this Windows PC (Visual Studio 18 Community, Python 3.11):

```powershell
.\tools\TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat
```

The script rebuilds seven offline executables with warnings-as-errors, runs the
24 cycle, 20 native-feedback/owner, 16 resampler, 8 integrated-owner and 11 policy-hold scenarios, then feeds actual Mink/Ruckig model samples through a local
stdio pipe. Output: `logs/test_results/mink_cycle_candidate_model_replay.json`.

## Contract

- Absolute right-arm samples, fixed order G1 joints 22..28. No relative-anchor
  rebasing. Other 22 target values remain exactly the supplied baseline.
- Sample velocity limits: first four joints 90 deg/s, last three 180 deg/s;
  acceleration 60 deg/s^2. Joint bounds and baseline are explicit constructor
  inputs. The candidate validates samples; it does not reshape their path.
- Ordered session/sequence/epoch, finite numeric arrays, <=250 ms source age,
  <=250 ms receive timeout, increasing sample time with <=60 ms interval.
- Fresh feedback <=50 ms and R1 held; `stop` represents Select/B/p or another
  owner emergency input. A violation latches Stopped and leaves the previous
  target untouched. A future physical owner must respond with its stop routine.
- Idle before engage. Tracking release (`pinch` or `tracking_disengaged`)
  enters Returning and increments epoch. During return only explicit `return`
  samples with that epoch are accepted. Active/duplicate release cannot bypass it.
- Return completion requires target within 1e-6 rad of baseline, command speed
  below 1e-6 rad/s, measured error <=0.02 rad and measured speed <=0.05 rad/s
  for 0.5 s. Return timeout is 30 s. Fresh idle is required before re-engage.
- Every accepted segment calls the supplied path validator. The C++ class does
  not implement collision geometry. Missing validator prevents construction.

Example packet at the supplied model ready baseline (not valid for the live relay):

```json
{
  "schema": "g1.mink.cycle.offline.v1",
  "provenance": "offline_only",
  "profile": "right_arm_90_180_a60",
  "session": "offline-model-cycle",
  "sequence": 1,
  "epoch": 0,
  "source_age_s": 0.0,
  "event": "idle",
  "joints": [0.17453292519943295, -0.3839724354387525, 0.0, 0.9599310885968813, 0.0, 0.0, 0.0]
}
```

The release packet still carries the old epoch and the first continuous return
sample; subsequent return packets use the incremented epoch returned by C++.
This is a new explicit protocol, not a relabeling of Unity simulation feedback.

## Evidence and limits

- 24 C++ scenarios cover absolute samples, two releases, return/re-engage,
  29-joint preservation, per-joint speed caps, invalid profile/provenance/numbers,
  session/sequence/epoch failures, acceleration jump, path rejection, controls,
  malformed JSON, input/feedback timeout, clock reversal and measured settling.
- Model integration accepted 579 samples through two complete cycles, returned
  in 107 / 106 model ticks, and re-engaged afterward. Return path samples were
  checked with the existing MuJoCo geometry checker. No transport was created.
- Feedback in this replay is the previous model target and zero measured speed.
  It is not measured G1 LowState, dynamic simulation, or physical safety evidence.
- The pipe driver accepts `path_checked` only as a trusted test-harness result.
  A network sender must never be allowed to self-authorize its collision path.
- This validates sample-time derivatives, not a 500 Hz output waveform. Network
  jitter, resampling, model/LowState initialization, actual feedback freshness,
  return-path failures and real robot stopping remain future integration work.
- The candidate must NOT be plugged into the existing Robot launcher. Future
  integration needs an authenticated event adapter, trusted geometry check and
  the single full-body owner. Existing working robot control remains preserved.

## Native feedback and owner reference adapter (2026-09-09)

`mink_cycle_owner_offline.hpp` now wraps the cycle with the existing pinned
native-packed LowState decoder and receipt/tick continuity checks. It does not
subscribe to DDS. The 20 tests use synthetic CRC-packed native-layout bytes,
not a newly captured G1 stream. Deployment ABI equivalence is still unverified.

Call sequence in a local harness:

1. Construct with an explicit ready pose, right-arm bounds, health limits,
   arm segment checker and full-body measured-to-reference path checker.
2. `Observe(bytes, profile, received, now)` at each fresh state receipt. The
   decoder supplies measured q/dq and remote R1/Select/B. No input JSON can
   substitute for these fields. Receipt and tick progress use existing 20 ms
   continuity limits; motor faults, mode and configured health limits are checked.
3. `Receive(packet, now, keyboard_stop)` for each ordered cycle sample.
4. `Compose(PolicyPositions, now, keyboard_stop)` with already converted leg
   positions (not raw policy actions) tied to `StateSequence()` and a valid
   inference creation time. Output is an optional **reference snapshot only**:
   policy legs 0..11, supplied ready waist/left arm 12..21, cycle right arm 22..28.
5. `Poll(now, keyboard_stop)` between receipts. Any failure latches the owner
   stopped and clears the reference. New observation/input also invalidates the
   previous reference; failed/stale inference cannot silently reuse it.

The two path callbacks are trusted host geometry checks, not network flags.
The full-body checker sees measured pose and the composed leg/arm reference.
Tests inject checkers to verify rejection/ownership wiring, not geometric safety.
Health limits are caller-supplied; the fixture values are not hardware tuning.

20 scenarios cover ownership, absent state, CRC, R1/B/p, motor fault, stale
receipt, stalled/reversed tick, policy-state mismatch, future/expired policy,
full-body path rejection, leg limits/nonfinite values, invalidation, reversed
clock, input timeout with continuing state receipts and unsupported ABI.
All passed with MSVC /W4 /WX. Existing 24 cycle scenarios and 579 model samples
also passed again; the model replay still uses the original stdio consumer,
not this new native-byte adapter.

Remaining before physical integration: actual ready-pose transition and alignment,
500 Hz bounded resampling (with geometry recheck), event acknowledgement transport,
trusted geometry runtime, policy action conversion/inference wiring, damping
response and timing validation. This adapter neither generates damping nor
licenses direct 60 Hz target steps to a 500 Hz motor writer. Physical trial,
Robot launcher and G1 files were not changed or executed.


## 60 Hz to 500 Hz bounded smoothing (2026-09-09)

`mink_resampler_offline.hpp` is a separate fixed-grid, right-arm-only reference
resampler. It is NOT attached to the owner/Robot launcher. It starts at a supplied
stationary baseline; measured ready-pose settling remains an integration gate.
`Push(q7, sequence, source_time, receipt_time)` requires contiguous 60 Hz source
times, <=20 ms receipt delay and the existing per-joint speed/acceleration bounds.
`Step(time, owner_ok)` requires a 500 Hz logical output grid and rechecks a trusted
path callback before committing each output. It changes only joints 22..28.
An owner fault, missing buffered sample, missed output tick, malformed input or
path rejection latches stop and invalidates the output. It never extrapolates or
publishes a frozen target as an emergency stop. No physical damping is implemented.

For source spacing h=1/60 and phase u in [0,1], the quadratic B-spline is:

```
q = 0.5*(1-u)^2*a + (0.5+u-u^2)*b + 0.5*u^2*c
v = ((1-u)*(b-a) + u*(c-b))/h
a_out = (c-2*b+a)/h^2
```

Weights are nonnegative and sum to one: each joint stays in the three-knot range.
Velocity is continuous at knot boundaries and is a convex combination of source
interval velocities. Acceleration is bounded by the source second-difference
check. This is smoothing, not exact waypoint interpolation: reversal corners
round off, a new moving target may be passed while the delayed path is followed,
and there is no claim of zero tracking error. A constant settled target is reached
exactly after buffered motion drains. A two-frame playback offset plus the
half-frame smoothing lag gives 41.7 ms steady linear-ramp delay (about 50 ms).
Constant-final-sample settling takes at most 50 ms after that sample, provided
additional hold samples continue arriving. Output geometry must be rechecked;
a convex combination of collision-free poses is not necessarily collision-free.

The queue is capped at 64 knots. The floating-clock comparison has 1 ns tolerance
for arithmetic roundoff; this is not a relaxed scheduling watchdog. Real wall-clock
jitter is not supported as an arbitrary Step interval. A future scheduler needs
an explicitly reviewed logical-grid/delay policy, not silent catch-up publishing.

Tests: full reach/return with and without 8 ms receipt delay, 90/180 deg/s cap
attainment, output acceleration continuity, range preservation, fixed non-arm
values, exact final hold, stop/path rejection, missed ticks, underrun, sequence,
source time/age, speed/acceleration violation, nonfinite values, clock and overflow.
The cap fixtures use synthetic bounds/trajectories, not approved robot motions.

`mink_resampler_batch_offline.cpp` generates unvalidated mathematical fixtures
and explicitly marks `geometry_checked=false`. The separate audit_mink_resampler_geometry.py then
checks EVERY generated segment with the existing MuJoCo checker before reporting
success. This batch interface must never be used as a physical write authorization.
Reports: `logs/test_results/mink_resampler_geometry_3.11.0.json` and
`logs/test_results/mink_resampler_geometry_3.12.0.json`.

Next integration: owner-selected resampled output, full-body measured geometry,
return acknowledgement after buffered output and measured settling, actual timing,
feedback and emergency stop handling. Existing physical source/launcher unchanged.


### Observed geometry runtime discrepancy

The saved model trajectory produces 4,909 output segments (with ten final hold
input samples). The existing default MuJoCo 3.11.0 rejects segment 6.256 s at its
midpoint, reporting -0.1333500474 m for shoulder-yaw/wrist-yaw mesh geometry.
The same pose in the already-installed isolated 3.12.0 gives nearest clearance
+0.0404418982 m. The full saved output passes all 4,909 segments in 3.12.0;
maximum arm speed is 0.12532229 rad/s and acceleration 1.04719755 rad/s^2.
This is a runtime-dependent geometry discrepancy, not proof the default runtime
or physical collision model is safe. The default installation and active scripts
were not changed, and no failing distance was clamped or bypassed.

The batch verification now explicitly runs its final geometry audit using the
existing isolated directory `logs/diagnostics/mujoco_versions/3.12.0`. It fails
if this dependency is missing/wrong; no automatic install or runtime replacement.
To reproduce the default-runtime rejection separately:

```powershell
py -3.11 -B experiments/twist2_right_arm_manual/audit_mink_resampler_geometry.py
```

Expected current result: exit 1 with the saved 3.11.0 rejection report. To check
the same saved output under the isolated runtime, add `--isolated-mujoco`.
The successful isolated audit must not be presented as fixing the live 3.11 route.
Before live integration, choose and verify one geometry runtime consistently for
both IK and output checking. Output/owner integration and buffered return-ack
remain unimplemented; the resampler is currently a separately tested component.


## Integrated resampled owner and consistent simulation runtime (2026-09-09)

`MinkCycleOwnerOffline(..., resample=true)` now owns the resampler. Call Observe
at state receipt, Receive on the fixed 60 Hz source/receipt grid, and Compose on
the 500 Hz logical grid, starting with Observe/Compose at the constructor time.
The resampled right arm is merged with the current leg policy positions; waist
and left arm retain the supplied ready baseline. The measured-to-composed full
body path check runs after this merge. Reference velocity/acceleration fields
contain the resampled seven-joint derivatives; they are diagnostics, not SDK dq
commands. Legacy resample=false behavior stays available for existing tests.
This integrated interface currently assumes punctual, equal source/receipt times;
it does not implement jittered network input or a real-time policy scheduler.

Return settling now also requires the last successfully composed output to be
<=2 ms old, at ready within 1e-6 rad and stopped within 1e-6 rad/s. This gate is
ANDed with existing target and measured q/dq checks for the full 0.5 s interval.
Old buffered/absent/stale output cannot acknowledge return. The offline candidate
Receive has an optional output_settled argument, default true only for the legacy
standalone fixture; the integrated owner supplies the actual gate. A stopped
owner clears its public reference and cannot resume without reconstruction.

8 integration scenarios pass: pinch and tracking release with stationary or
moving synthetic measured feedback (four complete return/re-engage cycles),
missed 500 Hz tick, full-body geometry rejection, emergency stop, and stale-output
return-ack rejection. Synthetic native bytes and injected geometry callbacks are
not a hardware or integrated MuJoCo dynamics test. Existing 60 scenarios pass too.

The offline model producer now pins MuJoCo 3.12.0 before importing Mink, matching
the output geometry auditor. Both IK and output audit pass on the same runtime:
579 source samples, two returns/re-engage, 4,909 output segments. The historical
3.11 discrepancy report remains evidence, not an expected failure of this route.

`tools/START_MINK_ARM_CYCLE_SIMULATION.bat` now sets a process-local
G1_MINK_SIM_MUJOCO_ROOT to the existing isolated 3.12.0 folder. The entrypoint
checks the requested mode, version and resolved module path before controller
imports. Missing/wrong runtime fails; it never falls back to 3.11. The environment
pin is rejected without --simulation-arm-cycle. Global Python installs and the
Robot launcher remain unchanged. Verification-only command (no controller/UDP):

```powershell
$env:G1_MINK_SIM_MUJOCO_ROOT = Join-Path (Get-Location) 'logs/diagnostics/mujoco_versions/3.12.0'
py -3.11 -B MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py --simulation-arm-cycle --check-simulation-runtime
Remove-Item Env:G1_MINK_SIM_MUJOCO_ROOT
```

Four subprocess runtime checks and four simulation provenance boundary tests pass.
The simulation UI was not launched this turn: restart is needed to use the new
runtime, and Unity/Quest visual confirmation is pending. The launcher still runs
the Python simulation cycle; it does NOT start the new C++ owner. Physical
LowState/DDS adapter, ready transition, network events/ack transport, real-time
policy and stop/damping wiring remain unimplemented. No G1 files were changed.


## Simulation v5 objective priority (2026-09-09)

User-approved position priority now temporarily scales wrist orientation cost
from 2 to .5 after constrained >80 mm position error persists .3 s. The original
clutch-relative rotation target remains intact. Once position error is <30 mm,
or clearance and joint margins are comfortably restored, .3 s dwell starts a
smooth ramp back to normal orientation priority. Cost-scale change <=1/s;
all existing velocity, acceleration and exact geometry limits still apply.
Reset/BeginReturn clear the temporary priority. This is task-objective scheduling,
not a PD gain change, target rebasing or removal of collision constraints.

Two held-goal model cases improve position residual to 52.84/59.36 mm at the
expense of 34.24/44.74 deg orientation error. Returning to their original reachable
goals restores scale=1 and finishes at ~2 mm / .074 deg after 15 simulated seconds.
This does not guarantee immediate recovery or reaching every requested pose.
Eight tracking tests and the existing 579-input / 4,909-output model replay pass
under isolated MuJoCo 3.12.0. The offline validation batch includes these tests.

Restart START_MINK_ARM_CYCLE_SIMULATION.bat to load v5. Runtime status includes
position_priority_active and orientation_priority_scale. No VR visual test or
physical robot execution was performed while implementing this change.


## 50 Hz policy / 500 Hz owner reference handoff (2026-09-09)

The offline owner now supports one asynchronous policy request at a time without
requiring inference at every 500 Hz arm output. This is an interface and synthetic
schedule test, not an actual inference worker or real-time thread implementation.

1. After Observe, call BeginPolicy(now). The returned PolicyTicket contains a
   unique request ID and a COPY of the decoded state, including its receipt time
   and sequence. Compute against this snapshot, not subsequently changing state.
2. Continue Observe/Receive and ComposeHeldPolicy on the owner thread. While a
   new request is pending, the previous accepted policy may be used within its
   original freshness budget. A first accepted result is required before output.
3. Call SubmitPolicy(ticket.id, policy, completion_time) on the owner thread.
   policy.state_sequence must match the ticket snapshot; policy.created is actual
   result creation time. Newer measured state does not invalidate a timely result.
   Missing/mismatched/duplicate requests, malformed/late results latch stop.
4. ComposeHeldPolicy at 500 Hz merges cached leg positions with the resampled arm.
   Every call still polls fresh state, tick progress and operator controls, then
   checks the measured-to-composed full-body path. A cached result is NOT a cached
   safety decision. No reference is returned after stop or expiry.

Budget is min(configured OfflineHealthLimits.policy_age, 0.025) seconds, measured
from the policy INPUT snapshot receipt, not result completion or each output.
The new fixture explicitly sets policy_age=.025 for 50 Hz plus 2 ms inference
latency. Existing stricter callers remain stricter; no physical threshold changed.
Reference now records both current state_sequence and policy_state_sequence plus
policy_created, so a reused result is never restamped as fresh inference.

All methods are serialized owner-thread methods; a future worker needs a bounded
message handoff and must not call this object concurrently. Use exactly one of
Compose or ComposeHeldPolicy per output tick. Original Compose remains strict
about a newly supplied policy matching the current state, preserving old tests.
Inputs remain already-converted 12 leg positions, not raw TWIST2 policy actions.
No inference, policy action conversion, DDS or motor writer is implemented here.

11 new scenarios pass: 201 output ticks with 21 policy requests (including the
initial request) at 50 Hz and 2 ms later completion, state provenance, expiry,
missing/duplicate/mismatched/future results, overlapping requests, invalid leg
positions, current geometry/operator stop checks, and expiry based on original
input age even when inference completed late. Existing owner/cycle tests remain.
The 25 ms budget is a local design setting requiring real timing validation.


## Actual Torch CPU inference integration (2026-09-09)

Run separately with the existing CPU-only Torch environment:

```powershell
.\tools\TEST_MINK_TORCH_OWNER_OFFLINE.bat
```

This builds mink_torch_owner_stdio_offline.cpp and runs replay_mink_torch_owner.py.
The verified TorchScript bytes are loaded on CPU; the C++ observation builder
provides 1432 values, the actual model produces 29 actions, and the new owner
accepts request-bound, converted/clamped leg positions. Observation history is
committed from accepted composed command, not blindly from all raw actions.
The 50-request replay accepted all 50 results, committed 50 history frames and
produced 492 logical output ticks. Maximum measured compute was 5.4338 ms.
Report: logs/test_results/mink_torch_owner_replay.json. Subsequent runs can differ.
Malformed shape and delayed-completion fault injections also rejected as expected.

The synthetic native-state fixture follows previous reference with zero measured
velocity, uses the policy default arm pose, and deliberately has NO geometry
validation. Its pipe outputs state geometry_checked=false. It never authorizes
physical output. Model inference timing is measured, rounded up to logical 2 ms
slots; IPC/wall-clock deadlines are not measured by this harness. Initial model
inference occurs before the logical output epoch. No real asynchronous worker,
MuJoCo dynamics, moving v5 arm integration, robot feedback, SDK or publisher is
present. Those are separate remaining integration/validation items.
