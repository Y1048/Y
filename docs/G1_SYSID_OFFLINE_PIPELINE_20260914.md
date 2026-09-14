# Read-only system-identification foundation

## Scope and current decision

Continue `codex/g1-main-continuation-20260914` from `5de85864988e2c62671dbe7ec6ecc9826dd45ebd`,
which contains canonical main `0da866f7833c21ee1898c3e3ccf7932cdb401475`.
Development used a separate initially clean local clone/worktree; the two dirty
working copies were not reset, cleaned, switched or copied into this change.
No new control hook, gain edit, launch unblock, hardware connection or deployment
is included. The user's later clarification permits obtaining data, but does not
make this offline work a physical trial. Mode-transition research remains on hold.

The sequence is measurement -> identification -> independent episode validation
-> PD optimization. There is no final PD vector. Pitch120/1, roll300/3,
yaw64/1.2, elbow100/1.4 and wrist pitch30/1 remain research context only.
The prior 15/16 result is preserved, not a deployable gain recommendation.

**actual parameter identification is data-blocked**: no suitable independently
excited measurement plus held-out data in the new schema is supplied here.
An earlier 2500-row handoff capture held all seven arm targets constant; old VR
CSV is descriptive evidence, not automatically a timing-calibrated v2 episode.

## Modules and schema

`experiments/twist2_right_arm_manual/sysid_capture.py` is a file-only sink and
strict parser; it imports no transport, SDK, controller or actuation API.
`sysid_model.py` operates on saved files only. Neither can create a motor command
publisher. No connection mechanism is hidden in a command-line option.

Schema `g1.sysid.observation.v2` is deliberately separate from the older right-arm
`g1.real-response.v1`; v1 controller records are NOT silently upgraded or relabelled.
`validate()` is the executable schema, constants define vector order and units.
The entire canonical G1 29-axis ordering is stored in every record and tested
against `hardware/g1_arm_bridge/g1_joint_contract.py`.

|Fields|Meaning|
|---|---|
|session, episode, sequence, state, mode|Acquisition identity, ordering and observed mode; unavailable mode is null|
|provenance.kind/source|generated, replay or measured, plus source identity; a label alone is not hardware proof|
|clock.source/domain|One explicitly shared monotonic clock for this record; no implicit wall-clock conversion|
|target_ns|Creation time of original target, not serialization time|
|write_begin_ns, write_end_ns|Observed call boundaries, not motor acceptance time|
|state_receive_ns|Host receipt time of the paired state, not device sampling time|
|target_q|Original 29-axis reference before shaping|
|command_q/dq, kp/kd, tau_ff|Actual post-shaping values supplied to the existing write call|
|measured_q/dq|Observed joint values, never synthesized for missing joints|
|torque_estimate, temperature, motor_status|Optional 29-vectors or null; estimated torque is not certified applied torque|
|imu_rpy/gyro/accel|Optional 3-vectors or null, rad/rad/s/m/s^2|
|acceptance|Always unknown; a returned write does not prove execution|
|dropped_samples|Acquisition-reported loss; nonzero disqualifies fitting|

No observer adapter is connected in this change. An eventual adapter must copy
already-owned values without modifying them; unavailable required measurements
must reject the sample instead of inventing zero. Original bytes are retained
for all accepted records, including optional metadata. Numeric JSON round-trip
retains Python integer timestamps and float values; no rounding or unit rewriting.

## Asynchronous capture contract

Create `Capture(path)` outside a control callback. The single producer supplies
immutable, single-line JSON `bytes` to `offer(raw)`. The producer does no file I/O,
JSON parsing, queue waits or exception propagation for invalid type/full queue.
It returns false and increments losses when unavailable/full. The consumer checks
and writes exact bytes. Validation failure makes the capture incomplete.

Encoding/copying must happen before offer and is NOT free. Python's GIL, queue
lock and scheduler do not guarantee hard real-time latency. This reference sink
is not an approved 500Hz adapter. It must not be wired into the controller until
producer overhead is separately measured/reviewed; a fixed-size native copy/ring
is a possible future adapter. No physical timing claim is made from fixtures.

Call `close()` only after producer quiescence, outside control flow. It drains
with a bounded join and writes a SHA256-bound receipt. File/receipt failures can
raise there and must not unwind a future controller. Queue overflow, missing
receipt, crash, writer failure or modified bytes prohibit fitting. A timed-out
worker yields an incomplete receipt, never a successful truncated dataset.
Raw logs/receipts use exclusive creation; existing captures cannot be overwritten.

## Fitter contract and honest parameter limits

The initial baseline fits independent closed-loop first-order position dynamics:

`q[k+1] = a*q[k] + b*command_q[k-delay] + c`.

A predeclared integer delay grid is ranked on training one-step error using the
same rows for every candidate. Rank/conditioning, stable a, positive b and
nonconstant commands are required. Effective delay, lag `-dt/log(a)`, steady gain
and bias are descriptive closed-loop quantities. The per-delay training scores
are sensitivity information, not statistical confidence intervals.

This narrow baseline requires uniform, aligned write/state grids in a declared
shared clock, constant gains/dq/feedforward and compatible dt across episodes.
It rejects asynchronous/repeated-state records for fitting; the logger/parser
can preserve those records. No silent interpolation, resampling or clock shifting.
This intentionally prevents the current asynchronous real trace being treated
as a synchronous fixture. A timestamp-aware model is future work.

Clock offset is zero only by the required shared-clock contract, not estimated.
Effective command-to-observation delay cannot uniquely separate actuator pure
delay from transport/sensor/host effects. `actuator_pure_delay_s`, physical
damping, friction, effective inertia and load scale remain null. Estimating these
requires a torque-based model and independently informative/calibrated data;
schema fields reserve measured torque/IMU/health information for that stage.
No invented inertia, noise or measured latency. `recommended_hardware_gains`
always stays null. This is a fitter foundation, not a calibrated G1 model.

## Freeze then fit then validate

Before reading validation outcomes, call `create_plan()` with disjoint episode
IDs, joints, delay grid, positive q/dq RMSE thresholds and their evidence basis.
The function opens no episodes and creates the plan exclusively. For real use,
derive criteria from separate noise/repeatability data, not the held-out result.
No real default threshold is supplied. Plan hashes bind fit and validation;
this detects plan changes, not external editing of all artifacts or historical
proof of when a person first looked at data.

Validation requires different session IDs and rejects duplicate signal data even
if relabelled. Model coefficients are frozen: recursive prediction starts once,
does not reset to measured q each step, and is scored on unused episodes. The dq
score uses interval-average predicted velocity versus endpoint measured dq; this
is an explicit approximation rather than a separate velocity-state model.
Settling/overshoot need annotated endpoint holds; not claimed by this skeleton.

From `experiments/twist2_right_arm_manual`, after preparing a plan and records:

```powershell
py -3.14 -B sysid_model.py fit --plan plan.json --output model.json train.jsonl
py -3.14 -B sysid_model.py validate --plan plan.json --model model.json --output validation.json heldout.jsonl
py -3.14 -B -m unittest -v test_sysid_pipeline
```

`test_sysid_pipeline.py` supplies a complete generated fixture showing plan
creation before validation generation. Its thresholds are only for noiseless
synthetic equations and must not be copied as robot acceptance criteria.

## Verification boundaries

Generated tests exercise exact bytes/schema, all29 ordering, clock and sequence
rejection, malformed/nonfinite data, queue/file failure, delay recovery, plan
freeze, independent sessions and relabelled-data leakage, and failed validation
without retuning. Import checks enforce the file/numerical-only dependency list.
Preservation receipts compare existing tracked files and dirty worktree status.
No MuJoCo integrations, hardware measurements, model calibration, C++/ARM build,
mode switching or gain recommendation are claimed for this change.

## Native observer candidate added after the initial foundation

`sysid_native_observer.hpp` now offers an opt-in observation hook in the existing
controller (`G1_SYSID_CAPTURE_V2=1`); default launch configuration remains unchanged.
This supersedes the earlier statement that no adapter code exists, but not the
lack of hardware validation. See CHAT_HANDOFF's native observer entry for fields
and tests. SDK-free tests passed; full ARM Controller build and timing remain
unverified. The new v2 output is asynchronous and the initial synchronous fitter
will deliberately reject it until timestamp-aware fitting is implemented.
Do not fabricate alignment to make that test pass. Existing legacy v1 logging
remains present and is not promoted to a validated recording/control path.
