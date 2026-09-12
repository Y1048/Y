# Independently timed PD verification (simulation only)

Compare the frozen yaw64/1 and yaw72/1 research candidates when all four
proximal axes have different start times, periods, directions and amplitudes.
This is a new reference class, not another decimal-place gain search. It is
synthetic and does not claim to replay recorded VR packets or certify hardware.

## Run

Use the existing isolated `.venv-mujoco-pd` environment, never the VR environment.
From the repository root on Windows:

```powershell
$out = ".\logs\test_results\pd_independent\$(Get-Date -Format 'yyyyMMdd_HHmmss')"
.\.venv-mujoco-pd\Scripts\python.exe -B .\experiments\twist2_right_arm_manual\mujoco_pd_independent_study.py --output $out --workers 4
.\.venv-mujoco-pd\Scripts\python.exe -B .\experiments\twist2_right_arm_manual\mujoco_pd_independent_study.py --output $out --audit-only
```

On Linux use the same Python script with `python3`. Dependencies are the existing
`mujoco_pd_requirements.txt`. Workers1..6 are allowed; output must not exist.
`--smoke` runs two synchronous component cases only and never exports a winner.
A full run has96cells: two vectors x8motions x6model/motor scenarios. Every cell
is attempted; failed motions are retained and never counted as completed.
No result automatically changes any live parameter or reference.

## Frozen candidates and conditions

Both vectors: Kp22..25=[100,300,yaw,100], Kd22..25=[1.4,4,1,1.4]. Yaw Kp is64
or72. Kp23=300 is research-only and beyond the unchanged live100 validator.
The controller remains purePD, zero velocity target and zero feedforward.
No IK damp/cost, limit, braking assumption, gain cap or source model is changed.

Eight motions include one synchronous parity control, forward/reverse stagger,
unequal amplitudes/speeds/repetition counts, paired starts, six-cycle30s soak,
and an elbow-shifted start. Each scalar trajectory reuses the existing smooth
round-trip primitive and its original speed/acceleration bounds. All start from
rest: a delay does not insert a discontinuous phase-shifted position.
Each axis is held at baseline when it has finished while the others continue.

The six scenarios include nominal, half timestep, heavy, the previously failing
coupled delay-boundary, and two further prespecified mixtures. They are assumed
parameter sensitivities, NOT measured real-drive uncertainties or probabilities.
All96conditions and both candidates are frozen before running. No retuning.

## Acceptance and evidence

Existing29-joint pre/post/final checks,0.05rad inner reserve, stopping-envelope,
contacts, measured speed, warmup, reference error and torque limits remain.
The motion timestamps are independent; the rest-window mapping therefore differs
from the old synchronous-only evaluation. Numeric tolerances are unchanged:
- Every axis's own last100ms of each endpoint: error<=0.02rad, speed<=0.1rad/s,
  position variation<=0.005rad, RMS speed<=0.05rad/s.
- Last1s of the common final rest: all4error<=0.02rad and speed<=0.1rad/s.
- Last100ms of common rest: right7position variation<=0.005rad and RMS<=0.05rad/s.
Other intentionally moving axes are NOT mislabeled as residual oscillation during
one axis's hold. They retain their own endpoint and all-time state constraints.
No earlier pass counts are retroactively assigned this new acceptance policy.

Ranking requires all48cells per candidate; then minimize worst original-reference
RMSE over the four proximal joints. Partial/incomplete results have no selectable
score. A result may truthfully have no passing candidate. All errors include the
original target, not a command shortened by a limiter.

Full29 q/dq/reference/command/torques at500Hz plus individual segment/cycle metadata
are saved per run. The independent reader rebuilds each held50Hz scalar target
from its own clock, checks gains/torque equations, model evidence, joint minima,
coverage, metrics and rankings. Physics-rate traces are not reconstructed, so
this is not continuous-time safety proof. Archived source/model bytes and the
current computational revision must match; archived Python is never executed.

Working VR/Mink/UDP/LowCmd, source models and hardware gains remain untouched.
No G1 access, DDS, motor output, deployment or Robot/All unblocking is performed.
