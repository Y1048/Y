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

The existing single-owner `twist2_mink_cycle_trial.cpp` now copies its completed
500 Hz `WriterFrame` into `real_response.jsonl`. The copy occurs only after the
existing publisher `Write()` returns. It records joints 22..28 from the original
policy/Mink desired target and from the final post-slew/range/torque command,
along with the exact LowState used to form that command. This remains a paired
input-state sample rather than a later response or device acknowledgement.
`real_response_frame.hpp` is only a bounded asynchronous file sink and has no
command API. No control equation, limit, gain, IK value or publisher ownership
was changed.

Run the offline regression from the experiment directory:

```powershell
python -m unittest -v test_real_response_identification.py
```

Verified on Windows with Python 3.14: 5/5 new tests passed. The tests cover
asynchronous round-trip writing and parameter recovery, sequence-gap refusal,
nonmonotonic-clock refusal, nonfinite-field refusal, and the absence of
command-capable imports. The existing recorded-target parser regression was
also rerun separately; these checks create no SDK/DDS endpoint or robot output.
Two C++ tests compiled with `-Wall -Wextra -Wpedantic -Werror` and passed in
local WSL: the new response-frame schema/slicing/finish test and the existing
asynchronous writer-failure test. Full Unitree ARM linking remains unverified.
The existing native CMake contract test could not start because CMake is absent
from both the selected Windows Python environment and local WSL; this is an
environment prerequisite failure rather than a compiled-controller result.

Remaining work requires a separate review before any physical run:

1. Review and ARM-compile the integrated controller without running it.
2. Measure quiet hold and small-signal episodes only after explicit physical
   authorization, then freeze train/validation episode splits.
3. Add delay estimation and held-out prediction scoring after real records
   exist. No latency, friction, inertia or final PD value is claimed here.
