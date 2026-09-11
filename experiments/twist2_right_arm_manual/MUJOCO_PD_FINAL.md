# Final PD optimization and review (offline only)

This is a single entry point for bounded **per-joint** pure-PD search, complete
operating verification, new final checks, and a tamper-checked review bundle.
It never updates the VR launcher, DDS, robot gains, source model or live limits.
A final **simulation** candidate is not an approved physical controller.

## Prerequisites

From the repository root, create a separate environment. Do not install into
the working VR environment:

```powershell
py -3.11 -m venv .venv-mujoco-pd
.\.venv-mujoco-pd\Scripts\python.exe -m pip install -r .\experiments\twist2_right_arm_manual\mujoco_pd_requirements.txt
```

## One-command search and finalization

```powershell
$out = ".\logs\test_results\pd_final\$(Get-Date -Format 'yyyyMMdd_HHmmss')"
.\tools\RUN_MUJOCO_PD_FINAL.bat optimize --output $out --workers 6
```

This executes the existing per-joint search, audits it, and then validates its
up-to-two accepted vectors under the final conditions. Results are `$out\search`
and `$out\final`. Maximum workers is 8; existing output is always refused.
The simulator Kp caps are `[100,300,100,100]` for joints22..25. These are research
bounds, not actuator ratings. All four gains can differ. Wrist gains stay fixed.
The pure-PD law remains `tau=Kp*(q_cmd-q)-Kd*dq` with zero feedforward. No hidden
integral term, gravity compensation, target bias or IK damp/cost change.

The underlying coordinate search is bounded and not a global 8D optimization.
Results on a cap must be reported as boundary candidates, not interior optima.

## Finalize the completed study without repeating the search

```powershell
$out = ".\logs\test_results\pd_final\$(Get-Date -Format 'yyyyMMdd_HHmmss')"
.\tools\RUN_MUJOCO_PD_FINAL.bat finalize --study "$env:USERPROFILE\Documents\G1_PD_PerJoint_20260912" --output $out --workers 6
.\tools\RUN_MUJOCO_PD_FINAL.bat verify --study "$env:USERPROFILE\Documents\G1_PD_PerJoint_20260912" --output $out
```

`finalize` rereads the entire original search, verifies applied gain vectors,
full29 state traces, reference/torque equations, guard evidence, plans and frozen
selections. It then performs new simulations; old pass flags alone are not used.
`verify` rereads all evidence again but does not integrate new dynamics. The
underlying search auditor may regenerate equivalent audit/CSV derivatives; it
does not rewrite original manifests, selections, case JSON or NPZ trajectories.

On Linux use the same Python script directly:

```bash
python3 experiments/twist2_right_arm_manual/mujoco_pd_final.py finalize --study /path/to/search --output /path/to/new/final --workers 6
python3 experiments/twist2_right_arm_manual/mujoco_pd_final.py verify --study /path/to/search --output /path/to/new/final
```

Verification requires the recorded source revision AND exact recorded bytes,
including source line endings and model/mesh bytes. It intentionally refuses a
changed implementation. Archived source is read as evidence, never executed.
A prior processing-only source archive is supported without changing provenance.
Keep the source study alongside the final bundle; the final bundle is not an
independent replacement for all source trajectories.

## Final gate and artifacts

Up to two vectors that passed all144 operating +48 prior fresh cases are frozen
in their original operating minimax order. Six new model/actuator mixtures x
four axes =24 additional conditions per vector, including6/12 repeats, altered
amplitudes/speeds/starts, and30-second final hold. Conditions are fixed before
new dynamics. No final outcome changes the candidate, model or tolerances.

The original all29 inner reserve, stopping-envelope, pre/post/final checks and
endpoint criteria remain. Final checks additionally require ALL four proximal
joints, including inactive ones, to have <=0.02rad endpoint error and <=0.1rad/s
speed. Each endpoint uses its last100ms; the entire last1s of final hold is
checked. Every original rejection remains a rejection. Tests with only a1s
post-hold can lack500 recorded samples due to50Hz reference-phase alignment;
formal final profiles use at least5s, without relaxing the full1s requirement.

Artifacts:

- `manifest.json`, `plan.json`, `source_receipt.json`: frozen provenance,
  source decisions, exact profiles and conditions.
- `cases/`, `full_state/`: per-case results and all29 state/torque arrays,
  including rejected cases. They are simulation data, not G1 measurements.
- `simulation_candidate.json`: selected vector only when all checks pass,
  comparison metrics, cap flags and explicit physical blockers.
- `verification.json`: counts, hashes and reconstructed decision. A successful
  audit can correctly verify a `no_final_candidate` result.

Exit0: accepted simulation candidate, or a successful `verify` (even if no
candidate qualified). Exit2: no final candidate, invalid CLI or missing isolated
launcher environment. Unexpected audit/infrastructure exceptions fail nonzero;
partial outputs are never treated as a verified bundle. No overwrite/resume is
attempted after an interrupted run: retain it and use a new output directory.

## Physical boundary

`hardware_approved=false`, `recommended_hardware_gains=null` and
`hardware_config_modified=false` are mandatory. `legacy_hardware_gain_compatible`
means only the old software Kp bound, NOT permission to actuate. Joint23 Kp>100
remains incompatible with the unchanged live validator. Never copy research
Kp300 into START_TWIST2_MINK_CYCLE_CANDIDATE or lift Robot/All charging blocks.

Remaining physical checks: actual drive/servo rates and allowed gains, motor
latency, simultaneous VR motion, free-base TWIST2 balance, calibrated payload,
mechanical limits/braking, sensor noise/backlash/temperature and ownership/ARM
binary review. These are deployment blockers, not claims that more repeated
single-axis simulation can prove universal safety. This tool does not tune IK.
