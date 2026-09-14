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
