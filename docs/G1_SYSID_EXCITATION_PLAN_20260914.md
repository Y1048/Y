# G1 system-identification excitation plan

`sysid_excitation_plan.py` creates an offline trajectory description for the
next measured-response experiment. It cannot execute the plan: it imports no
Unitree SDK, DDS, socket, subprocess or controller module and always writes
`command_capable=false` and `execution_authorized=false`.

The request must explicitly bind the controller source SHA-256, all 29 start
angles, all 29 effective soft bounds, all 29 current Kp/Kd values, and seven
right-arm amplitudes, speed limits and acceleration limits. No physical default
is supplied. A request is rejected if a start angle is outside its soft bounds,
either signed excursion crosses a bound, a value is nonfinite, or joint order is
not exactly 22 through 28.

Each joint is excited alone using a zero-velocity/zero-acceleration endpoint
quintic path:

`start -> +amplitude -> start -> -amplitude -> start`

The move duration is rounded up to the requested sample period so the analytic
peak velocity and acceleration stay within the supplied limits. Training uses
joint order 22..28 and validation uses 28..22 with the first sign reversed.
This separation changes the schedule but does not itself prove statistical
independence; acquisition must still use different session/episode IDs and the
validation data must remain unopened until thresholds are frozen.

Create a request JSON with schema `g1.sysid.excitation-request.v1`, then run:

```powershell
py -3.11 -B experiments\twist2_right_arm_manual\sysid_excitation_plan.py `
  request.json --output excitation-plan.json
```

Required request fields:

```json
{
  "schema": "g1.sysid.excitation-request.v1",
  "contract_id": "chosen-before-collection",
  "controller_source_sha256": "64 lowercase hexadecimal characters",
  "joint_indices": [22, 23, 24, 25, 26, 27, 28],
  "start_q_rad": "29 finite numbers",
  "soft_lower_q_rad": "29 finite numbers",
  "soft_upper_q_rad": "29 finite numbers",
  "kp_nm_rad": "29 positive finite numbers",
  "kd_nm_s_rad": "29 positive finite numbers",
  "amplitude_rad": "7 positive finite numbers",
  "velocity_limit_rad_s": "7 positive finite numbers",
  "acceleration_limit_rad_s2": "7 positive finite numbers",
  "sample_period_s": 0.002,
  "hold_s": "at least one sample period",
  "cycles": "positive integer",
  "termination_owner_contract": {
    "status": "unresolved or reviewed",
    "description": "exact owner and termination behavior"
  }
}
```

For the current project, termination ownership remains unresolved because mode
handoff research is on hold after the force-loss incident. Therefore this plan
must not be connected to `LowCmd` or used as a physical-run instruction. Once
the supervisor selects the lower-body/ownership policy, bind its exact source,
measured start pose and reviewed termination behavior in a new request. The
existing subscriber-only logger can then observe a separately reviewed run.

Offline verification:

```powershell
py -3.11 -B -m unittest -v test_sysid_excitation_plan.py
```

Generated fixture tests verify sequential excitation, analytic speed and
acceleration bounds, deterministic hash binding, exact right-arm ordering,
limit/nonfinite/missing-field rejection and absence of command-capable imports.
No hardware gain is recommended; `recommended_hardware_gains` remains null.

## Read-only readiness comparison

After a plan exists, `sysid_excitation_readiness.py` can compare it with a
completed subscriber-only capture. It reads files only and reports the final
window's right-arm start-pose error, maximum measured velocity, observed mode
pairs, LowCmd coverage and whether observed Kp/Kd match the plan.

```powershell
py -3.11 -B experiments\twist2_right_arm_manual\sysid_excitation_readiness.py `
  excitation-plan.json capture.jsonl `
  --pose-tolerance-rad VALUE_CHOSEN_BEFORE_CAPTURE `
  --velocity-tolerance-rad-s VALUE_CHOSEN_BEFORE_CAPTURE `
  --output readiness.json
```

No tolerance defaults are supplied. Missing observed LowCmd leaves gain matching
as null rather than claiming a match. An unresolved termination owner, unstable
mode, excessive motion, pose mismatch or observed gain mismatch is listed as a
blocker. `physical_execution_authorized` is always false: a passing saved-file
comparison is evidence for review, not knowledge of the robot's current state.

## Build a request without copying 29 values by hand

`sysid_excitation_request.py` reads literal `kKp`, `kKd`, `kLower`, `kUpper`
and `kJointLimitMargin` arrays from the selected `twist2_common.hpp`. It derives
the start pose as the per-axis median of a stable tail from a completed read-only
capture. The request and receipt bind SHA-256 hashes of the capture, common
header and selected controller source. Source text is parsed as numeric literals;
it is never compiled, imported or executed.

The accompanying draft-spec JSON must provide every experimental choice:
amplitudes, speed/acceleration limits, sample period, hold duration, cycles,
stable-tail duration/tolerances and termination-owner contract. There are no
physical defaults. It must also state the parameter basis, which is hash-bound
in the receipt. Create the request with:

```powershell
py -3.11 -B experiments\twist2_right_arm_manual\sysid_excitation_request.py `
  capture.jsonl draft-spec.json `
  --common-source references\lower_body\twist2_deploy\cpp_g1_twist2\twist2_common.hpp `
  --controller-source experiments\twist2_right_arm_manual\twist2_mink_cycle_trial.cpp `
  --output request.json
```

The tool rejects a short/moving/variable-mode tail and then runs the complete
plan request validator. It writes `request.json.receipt.json` but still does not
authorize execution. Existing ZeroTorque recordings are retained as measured
state evidence; they are not automatically selected as a controlled start pose.

`G1_SYSID_EXCITATION_DRAFT_SPEC_20260914.json` is a review draft based on the
existing joint-22 `PdSmallSignalTrial`: ±8 degrees, 20 deg/s, 60 deg/s² and
three cycles. Reusing that shape sequentially for joints 23..28 is explicitly
unvalidated. The owner remains `unresolved`, so the draft cannot support a
physical run. Its pose/velocity tail thresholds are acquisition-screening
choices rather than measured sensor-noise limits.

The draft shape contains 169 segments per episode. Its generated training and
validation schedules are each 116.252 s; combined commanded time would be
232.504 s before any external setup time. These are computed reference durations,
not a completed or approved robot run.

## Sample-level waveform preview

`sysid_excitation_preview.py` expands a completed plan into `training.csv`,
`validation.csv` and a SHA-bound `summary.json`. Each row contains time, segment,
active joint, all seven offsets, active velocity and active acceleration. The
expander rejects discontinuities, off-grid durations, unknown joints and an
episode that does not finish at zero offset. Output directories are exclusive,
so an earlier preview cannot be overwritten silently.

```powershell
py -3.11 -B experiments\twist2_right_arm_manual\sysid_excitation_preview.py `
  excitation-plan.json --output-directory excitation-preview
```

The CSV is generated reference data only. The preview module has no SDK,
transport, publisher or process-launching imports and its summary always records
`physical_execution_authorized=false` and `recommended_hardware_gains=null`.

## SDK-free C++ waveform reference

`sysid_excitation_reference.hpp` mirrors only the duration-grid and quintic
position, velocity and acceleration math used by the Python plan and preview.
It has no Unitree SDK, DDS, publisher, controller, clock, file, concurrency or
network dependency. It is deliberately not included from a LowCmd writer or any
robot executable.

The native test samples the full ±8 degree draft move at 2 ms, verifies endpoint
clamping and monotonic position, and checks that the 20 deg/s velocity and
60 deg/s² acceleration limits are not exceeded. The matching Python test checks
the same constants and the expected grid duration of 0.878 s.

```powershell
wsl.exe -e bash -lc "cd /mnt/c/path/to/repo/experiments/twist2_right_arm_manual && g++ -std=c++17 -Wall -Wextra -Wpedantic -Werror -UNDEBUG test_sysid_excitation_reference.cpp -o /tmp/test_sysid_excitation_reference && /tmp/test_sysid_excitation_reference"
py -3.11 -B -m unittest -v test_sysid_excitation_reference.py
```

These tests establish offline formula parity only. They do not validate control
loop timing, motor response, physical safety or command ownership, and they do
not authorize a hardware run. `recommended_hardware_gains` remains null.

## SDK-free C++ sequence core

`sysid_excitation_sequence.hpp` adds deterministic sample-grid sequencing around
the waveform reference. It accepts a 29-axis start vector and a list of holds and
single-axis quintic moves. Construction fails closed on nonfinite data, off-grid
durations, joints outside 22..28, discontinuous holds/moves, empty sequences and
sequences that do not return every arm offset to zero.

`AtTick()` produces one 29-axis target sample without reading a clock. The native
test moves joints 22..28 one at a time, proves that all inactive joints remain
bit-for-bit equal to their starting values, checks target bounds and verifies the
final sample equals the complete starting vector. It also exercises invalid joint,
discontinuity and off-grid rejection.

This sequence core itself has no plan-file parser, SDK, DDS, network, publisher,
controller or process entry point and is not linked to the existing runtime. The
separate offline saved-plan adapter is described below.

## Saved-plan C++ adapter

`sysid_excitation_plan_adapter.hpp` strictly converts a parsed
`g1.sysid.excitation-plan.v1` JSON value into the sequence core. It rejects a
plan unless `command_capable` and `execution_authorized` are both false and
`recommended_hardware_gains` is null. It also checks the exact 29-axis start and
soft-limit vectors, right-arm indices/names, fixed training/validation ordering,
segment continuity, endpoint soft limits and independently recomputed analytic
peak velocity/acceleration.

`sysid_excitation_plan_check.cpp` is a file-only command-line checker. It parses
one saved plan, constructs both sequences and prints their sample counts and
period; it has no SDK, DDS, publisher, network or controller code. A Python-built
schema fixture was opened successfully by the compiled C++ checker and produced
47,906 ticks for each episode at 2 ms. The native malformed-plan tests cover
execution flags, identity mismatch, altered analytic metadata, soft-limit breach,
discontinuity and nonfinite input.

```powershell
wsl.exe -e g++ -std=c++17 -Wall -Wextra -Wpedantic -Werror `
  experiments/twist2_right_arm_manual/sysid_excitation_plan_check.cpp `
  -o /tmp/sysid_excitation_plan_check
wsl.exe -e /tmp/sysid_excitation_plan_check /mnt/c/path/to/excitation-plan.json
```

This remains offline validation. It does not create or send targets and is not
linked to a robot runtime. Physical execution and gain recommendations remain
blocked on the separately reviewed acquisition and command-ownership procedure.

## Full native/Python sample cross-check

`sysid_excitation_plan_dump.cpp` expands either saved episode through the C++
adapter and sequence core into a review CSV. It refuses an existing output path
and contains no SDK, DDS, publisher, network or controller dependency.
`sysid_excitation_crosscheck.py` independently expands the same plan through the
Python implementation and compares row count, time, segment, active joint, all
seven offsets, active velocity and active acceleration. It rejects missing rows,
identity changes, nonfinite values and numeric mismatches.

An actually executed cross-language fixture comparison checked all 47,907 rows
in each of the training and validation episodes. The largest numeric difference
was `8.526512829121202e-14`, below the frozen per-field tolerances. The fixture was
generated from the test request and contains no measured G1 data.

These files remain review tools only. They do not provide a clocked runtime or
write targets to another process, and they do not resolve physical acquisition,
termination ownership or hardware gains.

## Detached 500 Hz writer-hook candidate

The existing controller generates policy targets at 50 Hz and its writer runs at
500 Hz. Feeding the 2 ms excitation plan through the policy loop would therefore
discard nine of every ten planned samples. `sysid_excitation_writer_hook.hpp`
models the required writer-side boundary without being included by the physical
controller.

The hook accepts only the seven right-arm positions, never a complete command.
Before arming it requires an explicitly supplied writer period, start-pose
tolerance and gain tolerance. It rejects a plan-period mismatch, right-arm start
mismatch, current Kp/Kd mismatch, nonfinite inputs, repeat arming and sampling
before arming. `Next()` advances exactly one plan tick and holds the final starting
pose after completion. It does not change gains and has no clock, SDK, DDS,
publisher, network, termination or process ownership code.

The saved-plan adapter now retains and validates all 29 planned Kp/Kd values so
the hook can compare joints 22..28 against the active values. Native tests cover
arming gates, all seven bounded trajectories, completion hold and 20 ms versus
2 ms period rejection. The existing physical controller source was deliberately
left unchanged; its SHA-256 remains
`aa38a2e7d7e1686493b9c535ee2d13636856025f1a67928ef4c9290da5e01359`.

This is not yet a command-capable option. Connecting the hook requires a reviewed
start tolerance, explicit episode selection, logger provenance and fault/completion
ownership behavior. No value in the draft supplies hardware approval.

## Detached runtime state and provenance

`sysid_excitation_runtime.hpp` wraps the writer hook with explicit `disarmed`,
`running`, `complete_hold` and `fault_hold` states. Every returned sample carries
the plan-file SHA-256, request SHA-256, contract id, termination-owner status,
episode, plan tick, segment and active joint. The saved-plan adapter now validates
and retains the request hash, contract id and termination-owner status as well as
the planned gains.

After the first valid sample, `LatchFault()` freezes the last seven right-arm
targets, zeroes the reported planned velocity and acceleration, preserves the
first fault reason and prevents the plan tick from advancing. Normal completion
holds the plan's original right-arm start pose and likewise stops advancing. A
fault before the first valid target is rejected because this detached component
cannot choose a safe full-body fallback by itself.

Native tests verify both state paths, immutable provenance, repeated hold samples,
invalid plan hashes and pre-sample fault rejection. The coordinator emits only
seven positions and still has no SDK, DDS, publisher, clock, gain mutation,
full-body target or termination implementation. The physical controller remains
unchanged. Connecting these fields to the asynchronous observer is the next
offline integration step; selecting an actual fallback owner remains separately
blocked.
