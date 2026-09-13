# G1 real-response logger offline foundation — 2026-09-14

Baseline: `origin/main` at `0da866f7833c21ee1898c3e3ccf7932cdb401475`.

`real_response_log.py` defines `g1.real-response.v1`, strict parsing, gap and
clock-order checks, and a bounded asynchronous JSONL sink. It contains no
Unitree SDK, DDS, socket, subprocess, publisher, `LowCmd`, or gain-changing
code. It therefore cannot collect from or command a G1 by itself. A later,
separately reviewed controller instrumentation point must construct records
from values it already owns and pass them to this sink.

Each record carries monotonic target/command/LowState timestamps, original
seven-joint Mink target, shaped command q/dq/Kp/Kd/tau_ff, measured q/dq,
session/sequence/state and controller provenance. Optional observed torque,
IMU and motor-health objects are preserved for a later concrete adapter. A
command timestamp records an attempted writer event; it is not proof that DDS
or a motor accepted the command.

`real_response_identification.py` is an offline parser/fitter skeleton. It
refuses sequence gaps, reports the observed clock intervals, and performs a
per-joint least-squares fit of acceleration against command error, velocity and
bias. Its output always leaves `recommended_hardware_gains` null and explicitly
marks the missing holdout validation. It does not estimate a deployable PD
vector from one episode.

Run the offline regression from the experiment directory:

```powershell
python -m unittest -v test_real_response_identification.py
```

Verified on Windows with Python 3.14: 5/5 new tests passed. The tests cover
asynchronous round-trip writing and parameter recovery, sequence-gap refusal,
nonmonotonic-clock refusal, nonfinite-field refusal, and the absence of
command-capable imports. The existing recorded-target parser regression was
also rerun separately; these checks create no SDK/DDS endpoint or robot output.

Remaining work requires a separate review before any physical run:

1. Add a minimal instrumentation adapter inside the existing single LowCmd
   owner so the exact pre-shaping target and post-limiter command are observed.
2. Map the actual SDK LowState torque, IMU, temperature and status fields
   without inventing unavailable fields.
3. Measure quiet hold and small-signal episodes only after explicit physical
   authorization, then freeze train/validation episode splits.
4. Add delay estimation and held-out prediction scoring after real records
   exist. No latency, friction, inertia or final PD value is claimed here.
