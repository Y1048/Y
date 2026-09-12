# G1 simultaneous PD and focused yaw refinement — 2026-09-12

Base: bb642d11f0ea91c9aa97862996319027ced6602c.
Simultaneous implementation: dd96aebd0a55360fac93ea099b480cb69e108a39.
Focused yaw implementation: 649a052124b195b7c039124144759af0fb234757.
This is offline research, not a robot gain configuration or global optimum.

## Initial validation and diagnosis

All288declared simultaneous cells were attempted.208completed and passed;
80stopped for integrated measured velocity. Each old candidate passes104/144.
Nominal80/80, half-timestep64/64, heavy64/64 passed. Delay-boundary0/80.
All80failed final states identify joint24 as the fastest upper-body joint.
The boundary is hypothetical mass/inertia1.35,passive damping0.85,friction0.15,
pure torque delay4ms,first-order torque lag8ms,physics timestep0.5ms.
This is not a measurement of real servo or UDP latency.

Sixteen sign combinations simultaneously excite all4proximal axes. Main256
runs compare4deg/10deg/s and8deg/20deg/s profiles. Long32runs add12deg,
12repeats,30-second final holds and shifted elbow starts. Absolute all4endpoint
quality and inherited all29safety checks remain mandatory. Original single-axis
results are not erased but do NOT establish general simultaneous stability.

## Focused refinement

Only joint24Kp/Kd varied:42pairs(Kp32,48,64,72,80,88,100;
Kd0.4,0.7,1,1.4,2,3). Other axes remain Kp[100,300,*,100] and
Kd[1.4,4,*,1.4]. The42pairs each see3known screen conditions. The top2all-pass
vectors are frozen before each144operating cases. Operating survivors are
frozen before each24new combined simultaneous cases. No final data retunes
or reorders the operating selection. These are bounded conditional phases,
not all42pairs over the full operating matrix or a global8D optimization.

Actual yaw-refinement runs:462; completed:427;
all-criteria eligible:409. Phase counts:{"operating": 288, "screen": 126, "validation": 48}.
The initial288matrix is separate and is not recounted as new optimization.
Recovered studies contain 750 formal attempts. They were not rerun to package this evidence.
Unit-test dynamics are separate, not included in these counts.

Selected simultaneous SIMULATION candidate:{"kd": [1.4, 4.0, 1.0, 1.4], "kp": [100.0, 300.0, 72.0, 100.0]}.

|Vector Kp22..25|Vector Kd22..25|Operating passes|New validation passes|Operating worst all4 RMSE rad|
|---|---|---:|---:|---:|
|[100.0, 300.0, 72.0, 100.0]|[1.4, 4.0, 1.0, 1.4]|144/144|24/24|0.0118736665155|
|[100.0, 300.0, 64.0, 100.0]|[1.4, 4.0, 1.0, 1.4]|144/144|24/24|0.0118740758678|

An unverified or failed candidate receives no selectable complete-matrix error.
Raw failures, partial observations and rejected vectors remain in the evidence.
Only the new candidates' own conditions count toward their coverage. Do NOT
reuse the old different-gain216individual-axis passes as validation of new gains.
The newly tuned vector still needs its own wider individual-axis and arbitrary
phase-shifted/recordedVR validation before any general control claim.

## Guards, model and audit

No live or model limit, stopping assumption, writer rate, torque restriction,
quality threshold, IK cost/damping, compensation or original controller was
changed. PurePD has zero commanded velocity/feedforward. Kp23=300 remains
outside the unchanged liveKp100validator. It is not an actuator rating.
Original0.05rad inner reserve and pre/post/final all29checks remain.
Initial guard events:{}.
Yaw-study guard events:{}.
Observed minimum soft/hard clearances in yaw study:
0.211798601205472/0.261798601205472rad.
These XML ranges are not measured mechanical stops; an offline abort is not
verified physical braking or a guarantee that real hardware never reaches a limit.

Every formal trace was reloaded. Initial audit:2455975full29
rows at500Hz and8352guard extrema records.
Yaw audit:4978359rows and13398extrema records.
Audits reconstruct original signed held references, all4endpoint metrics,
vectorPD equations, sampled margins, physical-step extrema/witnesses, exact
plans, adaptive selections and frozen outcome hashes. Full physics-rate
continuous trajectories are not independently reconstructed.

## Tests and publication

Local original314-test suite:313passed,1C++compiler-dependent skip,0failures.
Additional yaw tests:17/17passed, including a real changed-gain full-state audit.
Hosted run34687197494,job103536139776 on649a052:
331/331passed,0skips; decoded logs inspected. Hosted tests include C++ parity,
exact single-axis29-state parity, simultaneous dynamics, missing/tampered
traces/plans/limits, and failure-isolated selection. CI ran tests and component
simulations, NOT the entire formal optimization. Full studies ran Windows.

Raw data remain in Documents/G1_PD_Multiaxis_20260912 and
Documents/G1_PD_MultiaxisYaw_20260912. Compact tables, manifests, frozen plans,
selections, failures, audits and complete raw SHA256 inventories are in
`docs/validation/g1_pd_multiaxis_20260912/`. The fullNPZstreams are onPC, not
silently claimed to be uploaded toGitHub. Each raw run has frozen source/model
bytes. Usage and commands:experiments/twist2_right_arm_manual/MUJOCO_PD_MULTIAXIS.md.

320preexisting protected runtime/model files match their original hashes.
The dirty workingVRtree status is unchanged; no reset/clean/overwrite. New work
uses a separate detached worktree. No robotSSH,DDS/SDK,publishers/subscribers,
physical output,ARMdeployment or Robot/All unblocking. Nominal/perturbed small
fixed-pelvis simulations do not validate sensornoise,backlash,thermal behavior,
actual payload/braking,full-body TWIST2 balance or deployment feasibility.
