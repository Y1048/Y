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
