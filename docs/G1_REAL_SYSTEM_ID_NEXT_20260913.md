# G1 real-response identification next step — 2026-09-13

Current base: `70e7fe86b3f1e858b35843629467c80a691fe069` on
`codex/g1-regular-handoff-20260910`.

## Decision

Do **not** continue treating more MuJoCo gain sweeps as sufficient evidence for
real-G1 gains. The next engineering milestone is to measure the real command to
joint response path, calibrate the offline model from that data, validate the
calibrated model on unused real episodes, and only then resume PD optimization.

The latest pitch/wrist study selected no final vector. A research combination
with pitch22 `120/1`, roll23 `300/3`, yaw24 `64/1.2`, elbow25 `100/1.4`, and
wrist-pitch27 `30/1` improved the matched known-recording error, but every frozen
finalist failed one expanded delay/model condition. Research gains above the
unchanged live Kp100 validator are not approved for deployment.

## Phase 1 — read-only real-response logger

Implement a logger that cannot publish motor commands or modify gains. During
normal existing control it must record enough information to distinguish target
generation, command shaping/transmission, and measured robot response.
Required channels/fields, when available:

- monotonic timestamps for target creation, command write/send, and LowState receive;
- original VR/Mink joint target before writer shaping;
- the actual command sent after slew/torque/range limiting (`q`, `dq`, `kp`, `kd`, `tau_ff`);
- measured LowState joint `q`, `dq`, estimated/observed torque fields if available;
- IMU orientation/angular velocity/acceleration needed to detect body motion;
- motor temperature/status fields if exposed without changing the controller;
- sequence/session/state/mode metadata needed to align records and reject gaps.

Logging must be buffered/asynchronous so disk I/O does not materially alter the
writer loop. Use a versioned schema, explicit units, joint indices/names, clock
source, and source provenance. Detect dropped/nonmonotonic samples. Never infer
that a sent command was accepted unless the available protocol explicitly proves
it. Do not embed credentials, tokens or unrelated personal data in logs.

The first implementation can be tested entirely offline with generated LowState
fixtures. Do not connect to the G1 merely to prove the logger builds.

## Phase 2 — deliberately small identification dataset

Only after the user explicitly authorizes physical measurement and the robot is
properly supported with emergency-stop/control ownership verified: keep the
existing reviewed live gains and obtain small-signal records. Do not start with
research Kp120/300. Record quiet standing/hold noise first, then small individual
right-arm motions for joints 22, 23, 24, 25 and 27.
Do not reuse the old dangerous full-forward reach experiment. Keep commanded
motion strictly inside the existing conservative inner joint envelope. Physical
test amplitudes/speeds and gain changes require a separate reviewed procedure;
this document does not authorize actuation.

## Phase 3 — offline model identification

Build an offline fitter/replay tool that consumes only saved logs. Estimate at
least:

- command-to-observation timing/latency and clock offset;
- actuator delay/first-order lag or another justified low-order response model;
- joint-dependent effective damping/friction and steady-state bias;
- effective load/inertia parameters only where they are identifiable from data.

Fit on one set of episodes and validate on different episodes. Never optimize
and score on the same episode and call that predictive validation. Report
parameter uncertainty/sensitivity and retain the raw measured traces.

The objective is not merely low fitted RMSE. The calibrated simulation should
predict `q(t)`, `dq(t)`, settling behavior and the location of the dominant error
on unused small-signal trials. Validation thresholds must be frozen before the
validation set is inspected and should be based on measured repeatability/noise,
not relaxed after seeing a failure.

## Phase 4 — resume PD optimization only after model validation

Once the calibrated model predicts unused real trials adequately, rerun the
finite-grid/robust PD studies using measured timing/uncertainty ranges. Keep a
calibration/validation split, all29 guards, torque/speed/settling checks, and
`recommended_hardware_gains = null` until a separately approved hardware trial.
## Repository/implementation constraints

- Continue from the current branch; do not create a replacement project.
- Work in an isolated clean worktree. Do not reset/clean the user's dirty live VR worktree.
- Read the latest `docs/G1_REGULAR_HANDOFF_20260910.md` and this file before editing.
- Preserve existing VR -> Mink -> UDP -> LowCmd behavior, XML/meshes and gain validators.
- Keep `Robot`/`All` launch blocking and the live Kp100 validation unless explicitly reviewed later.
- No G1 SSH, SDK/DDS initialization, publisher, motor output or ARM deployment during offline development.
- A read-only subscriber/logger implementation must be architecturally incapable of publishing commands.
- Do not change IK damp/cost while identifying motor/PD dynamics.
- Do not force-push. Reconcile remote HEAD before and after writes.
- Distinguish unit/replay tests, simulated dynamics, and actual measured-G1 evidence in every report.

## Definition of completion for the next Codex task

The next task is complete when the repository contains a reviewed read-only
logging schema/implementation plus an offline parser/fitter skeleton with tests
and documentation, without any physical run. If real logs are not supplied,
stop there and state that parameter identification remains data-blocked. Do not
invent measured latency/friction/inertia values and do not promote any current
research vector to a real-G1 recommendation.
