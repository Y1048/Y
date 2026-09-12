# Recorded-pipeline yaw and roll PD refinement — 2026-09-12

Base: `450f4241c61143236f0530e89138e8152885c0c3`.
Implementation: `a7602dd91c0c6c003f9bb473edfe718fe49877f0`.
This is simulation research, not a deployable G1 configuration.

## Question, fixed pipeline and actual executions

The user requested further optimization, including whether shoulder-roll Kp300
was merely a search-boundary result. We kept the existing causal20ms command
interpolation fixed and first addressed the yaw failures in the recorded input.
No recorded reference smoothing, range scaling, time stretching or new IK solve
was introduced. Scores use the original seven-joint goals, not filtered commands.
The direct unfiltered failures from the previous study remain unchanged.

| Phase | Scope | Actual integrations |
|---|---|---:|
| Yaw | 36 gain vectors, three identical screening conditions each | 108 |
| Roll | 20 roll pairs at the best passing yaw, same three conditions | 60 |
| Recorded validation | Four frozen finalists, two clocks x six models | 48 |
| Synthetic regression | Four replay survivors, 14 declared cases each | 56 |
| **Total** | **55 distinct gain vectors; all declared cells attempted** | **272** |

227 trajectories completed and passed all applicable criteria. 45 stopped and
were excluded: 24 stopping-envelope failures and 21 post-step speed failures.
Failed or partial trajectories never receive a selectable RMSE score. Unit-test
fixtures and read-only audits are not included in the 272 simulation count.
The summed simulated duration is 7604.7504999992925s, not wall-clock runtime.

## Finite search and data reuse

Yaw Kp={40,48,56,64,72,80}, Kd={0.6,0.8,1,1.2,1.4,1.6}; roll initially300/4.
Each pair sees send/nominal, send/delay_boundary and sample/delay_boundary.
The best passing yaw was64/1.2. Roll then tests Kp={250,275,300,325,350} and
Kd={3,4,5,6}. The deduplicated top two roll vectors and top two yaw vectors
were frozen before running all12 recorded conditions. All four passed.

Regression then tests each survivor on three synchronous/independent profiles
and four isolated axes, each at nominal and the known delay-boundary model.
This is 14 explicitly declared synthetic checks, NOT all previous hundreds of
conditions. Synthetic metrics are separate and not mixed into recorded scores.

The same previously observed recording is used: 1618 targets,27.453s PC-send
clock and26.950s source clock. Three-second warmup and five-second final hold
are simulation additions; the hold cannot dilute tracking RMSE. Raw SHA256:
`2710d76445c3e004f811567b38f289e8451a47fb2960d43576b021a9e87f7871`.
This is outgoing target data, not confirmed robot acceptance or measured response.
It is one known episode, not a new independent holdout. Model/torque-delay
perturbations are assumptions rather than measured hardware uncertainty.

## Finalists on the same validation and regression conditions

Joint22 remains100/1.4; joint25 remains100/1.4; all other gains stay unchanged.

| Roll Kp/Kd | Yaw Kp/Kd | Recorded passes | Synthetic passes | Worst recorded all7 RMSE rad | Worst synthetic all4 RMSE rad |
|---|---|---:|---:|---:|---:|
| **300/3** | **64/1.2** | **12/12** | **14/14** | **0.0140145883312691** | 0.0113566955705915 |
| 275/3 | 64/1.2 | 12/12 | 14/14 | 0.0140151649981156 | **0.0113358216869601** |
| 300/4 | 56/1.2 | 12/12 | 14/14 | 0.0140151839475655 | 0.0129050163977421 |
| 300/4 | 64/1.2 | 12/12 | 14/14 | 0.0140154928216618 | 0.0113591845150646 |

The strict recorded-input objective selects Kp=[100,300,64,100] and
Kd=[1.4,3,1.2,1.4]. It is a PD-plus-prefilter candidate, not a PD-only optimum.
The roll275 alternative's recorded score is only0.004114761225% worse and its
synthetic score is slightly better. This is not evidence that300 is uniquely
optimal. No untested real-world difference is inferred from such a small gap.

All four recorded minimax scores are dominated by joint22 shoulder pitch.
For the selected vector, per-joint worst RMSE over12 recordings is:
22:0.0140145883313; 23:0.0104983278499; 24:0.0100633278087;
25:0.0116756193856; 26:0.00749786339513; 27:0.0137353424498;
28:0.00482380657987rad. Further roll tuning alone need not reduce this maximum.

Higher roll Kp was not automatically better:350/3 and350/4 each passed2/3
screen cases;350/5 passed3/3.325/4 also passed3/3. The latter two were not in the
predefined top-two-roll finalist set, so they did NOT receive full12+14 checks;
they are not labeled universally unstable. This is a bounded coordinate search,
not the full yaw/roll Cartesian product or an eight-dimensional global proof.

## Selected candidate margins and demand

Across the selected12recorded+14synthetic cases: all26 pass; no guard event.
Peak upper-joint speed:1.2322443701578378rad/s, below the unchanged1.5rad/s gate.
Minimum stopping-envelope slack:0.10584676943408566rad.
Recorded final-hold max all7error:0.010221682262337994rad;
max all7speed:2.655528095509185e-7rad/s. Existing tail requirements remain
error<=0.02rad,speed<=0.1rad/s over the whole final second, and position
variation<=0.005rad,speedRMS<=0.05rad/s over the last100ms.

Selected roll peak recorded torque is6.812105642859314Nm; the275/3 alternative
is6.454833709343437Nm. Smaller tracking error is not zero extra actuator demand.

## Failed trials and unchanged protection

Across ALL272attempts,24stopping-envelope events occurred. Global minimum
stopping slack is -0.010142237703702373rad in the rejected cohort; it must not be
reported as a safe positive margin. The other21failures exceed post-step speed.
These are safety-screening refusals, not passed trajectories. Neither failed
cohort is hidden by the four fully passing finalists.

Global minimum measured soft clearance remains0.21179860120574887rad and
model-hard clearance0.2617986012057489rad; positional limit contacts were not
observed. Positive positional clearance does not erase a braking-slack failure.
The0.05rad inner reserve, assumed stopping parameters, all29pre/post/final-step
checks, source XML ranges, original torque and measured-speed limits are intact.
Software/XML hard limits are not measured mechanical stops, and these finite
simulations do not prove real braking, no-contact or full-body stability.

Only this additive experiment temporarily extends the process-local roll search
bound from300to350. It restores the old bound on exit, including exceptions.
The original simulation cap file and actual live Kp100 validator are unchanged.
No feedforward, gravity compensation, integral term, target bias, qpos projection,
IK damp/cost edit, or automatic deployment was introduced.

## Verification actually performed

Dedicated tests24/24passed. Hosted Linux run34699671159,job103569085281 on
a7602dd passed477/477tests,zero skips,including C++ reference parity; decoded
logs were inspected. Python3.11.16,MuJoCo3.3.7,NumPy2.4.6,Ubuntu24.04.5.
CI ran regressions and component dynamics, NOT the full272formal study.
The formal study ran isolated Windows Python3.11.9,MuJoCo3.3.7,NumPy2.4.6.

Final Windows full suite:477discovered,476passed,one existing C++compiler skip,
zero failures/errors. An earlier temporary test harness lacked the Windows
multiprocessing __main__ guard and reran tests in children. Only its owned
process tree was stopped; that incomplete run is not a pass. A new guarded
harness reran the complete suite. Original harness/log and the correction
receipt are retained. No formal simulation data or repository code changed.

Automatic audit and a separate audit-only CLI both passed.272full-state traces
were reread:3,802,512all29rows sampled at500Hz and7,888joint extrema records.
Audits check original recorded targets, causal command interpolation, actual
gains, PD/limiter equations, per-stage plans and selection, final quality,
source/model/trace hashes and guard evidence. They do not independently
reintegrate continuous trajectories between sampled records.

Six matching original64/1and72/1recorded cases were compared with the prior
causal study. Every saved29joint array, metric, eligibility and refusal reason
matches exactly. These actual-record parity checks are not extra simulations.

## Records and remaining scope

Raw: `C:\Users\user\Documents\G1_PD_RecordedRollYaw_20260912`.
Compact evidence: `docs/validation/g1_pd_recorded_roll_yaw_20260912/`.
Manual: `experiments/twist2_right_arm_manual/MUJOCO_PD_RECORDED_ROLL_YAW.md`.
Raw JSONL/fullNPZstreams remain onPC; no claim that they were uploaded toGitHub.
Comparison CSV SHA256:
`dcef1b6b1151212c1b29ca9878724a36c678cad5c00a15d9e318206220a430e7`.

All446pre-existing protected experiment/runtime/model/tool files match their
initial hashes. The original dirty live worktree Git status is unchanged.
No robot SSH, DDS/SDK initialization, publisher, real output, ARM deployment,
VR environment edit, IK change or Robot/All unblocking was performed.

The result is a feasible finite-grid candidate under the declared PD-plus-
prefilter experiment. The original unfiltered recording still fails its
command-governor test and has not been reclassified. New vectors do not inherit
old broad validation merely because they passed the14selected regressions.
More independent recordings, wider prior regression, sensor noise/backlash,
actual motor limits and delay, payload geometry, heating and free-base balance
remain unverified. The recorded error is now dominated by pitch22 and then
wristpitch27; investigate those and new input coverage before micro-optimizing
roll based on the0.0041% aggregate score difference. Keep275/3as a comparison
candidate and do not automatically copy research gains into the robot.
