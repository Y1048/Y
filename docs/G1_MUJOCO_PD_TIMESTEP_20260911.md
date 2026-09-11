# MuJoCo round-trip PD: timestep and artifact verification

## 2026-09-11 — verification addition

Base: `516afef2f5ff74c3aaf198c091f890b6565b2e95`.
This is a continuation record for `G1_REGULAR_HANDOFF_20260910.md`.

While preparing an overlapping CLI path fix, the branch advanced through
`610c5bab` (path fix), `fcfb2160` (contact diagnosis) and `516afef2` (fixture
filter correction). Those commits and their tests/docs were retained. The
unpublished overlapping patch was not pushed or used to replace their work.

Add ONLY `mujoco_pd_validate_results.py`, `test_mujoco_pd_artifacts.py`, a
separate `.github/workflows/mujoco-pd-sensitivity.yml`, and this record.
No existing simulation engine, model fixture, original CI workflow, live VR
launcher, UDP path, C++ controller, trajectory, gains, XML/meshes or robot
binary changes in this change set. Robot/All blocks remain unchanged.

The reader verifies run/CSV hashes, 500 Hz log continuity, actual gain fields,
three-cycle segment coverage, and recomputes original-reference/command RMSE,
peak error, speed, torque, contact/limiting ratios and ranking from CSV. It does
not rerun physics, connect to a robot or recommend hardware gains.

The separate hosted workflow runs the existing 21+6 simulation/fixture tests,
seven synthetic artifact tests, and the unchanged full 3x3 grid at 1 ms and
0.5 ms with Python socket audit events forbidden. It retains both sweeps and
validation.json. A failed sweep remains a failure; acceptance is not relaxed.

Local verification before commit: seven artifact tests passed, Python syntax,
workflow YAML and both embedded Python scripts checked. The validator/test
Git blobs match the locally tested bytes. Local MuJoCo is unavailable because
the package download failed; no local dynamics result is claimed.
Hosted sensitivity measurements are pending at this commit, not assumed.

Changing timestep also changes the ideal PD evaluation frequency. Thus this
is combined numerical/control-rate sensitivity, not pure integrator convergence,
not physical calibration, and not standing-balance validation. Model parameter
uncertainty, Windows GUI, real SDK/handoff and real G1 gains remain unverified.

After producing both output folders:

```bash
python experiments/twist2_right_arm_manual/mujoco_pd_validate_results.py results/dt_1ms results/dt_0_5ms --output results/validation.json
```

Next action: inspect the hosted run, record actual results and link this record
from the main handoff. Continue offline only; no robot deployment or actuation.

## 2026-09-11 — inspected successful hosted comparison

Tested commit: `1c983195c12f509d89e27036117f612e91a70ed6`.
The documentation-only closeout also preserves concurrent documentation commit
`7262645dc6575936b038efa436da9299292c42ad`; none of its historical results are
replaced by the results below.

Actions run: `34565313166`, job `103156119792` (`sensitivity`).
The completed job status, all steps, and full decoded log were inspected.
Conclusion: **success**. Environment: GitHub-hosted Ubuntu 24.04, Python
**3.11.16**, MuJoCo **3.3.7**, NumPy **2.4.6**. This was not a local Windows
or physical G1 run.

### Checks actually completed

- **34/34 tests, no skips:** 21 sweep/math/dynamics/preservation tests, six
  fixed-pelvis fixture tests, and seven synthetic artifact-integrity tests.
- **18/18 full candidate runs completed and were eligible:** nine Kp/Kd pairs
  at 1 ms plus the same nine at 0.5 ms. Each completed three round-trip cycles
  and recorded **7,633 trial samples at 500 Hz**, excluding warmup samples.
- All recorded trial contact, arm torque-target limiting and arm hard-clipping
  ratios were **zero**. No numerical, tracking or velocity guard stopped a run.
- The read-only verifier checked run/CSV hashes, contiguous 500 Hz logs, actual
  gain fields and cycle/segment coverage. Independently recomputed CSV metrics
  matched the stored reference/command RMSE, peak error/speed/torque and
  contact/limiting ratios. Eligibility and sorted ranking matched the data.
- Source and asset hashes matched across the two grids. Both the complete
  ranking and eligibility were unchanged. The ideal motor evaluation rate
  changed with the physics timestep; the 50 Hz reference and 500 Hz writer did not.
- The full sweeps used a Python audit hook that rejects socket events. No SDK,
  DDS or G1 program was imported or executed. Live VR source-identity regression
  checks passed, and no real robot gain/configuration was changed.

The separate base workflow on the same commit also passed: Actions
`34565313037`, job `103156119346`, **27/27 tests** and its nine-pair 1 ms sweep.
Do not add these repeated tests to the 34-test count as distinct coverage.

### Measured joint 22 ORIGINAL-reference RMSE

All values below are radians. Gains are applied as a group to joints 22..25;
only joint 22 is excited by the inherited ready -> +8 deg -> -8 deg -> ready
reference. The three repetitions and independent initial-state reset/warmup are
unchanged. Ranking is by ORIGINAL reference, not by the limited command.

| Rank, both timesteps | Kp | Kd | RMSE at 1 ms (rad) | RMSE at 0.5 ms (rad) |
| --- | --- | --- | --- | --- |
| 1 | 56 | 3 | 0.014649809182167359 | 0.014676715218920633 |
| 2 | 48 | 3 | 0.016795829286464642 | 0.01682191385908477 |
| 3 | 56 | 5 | 0.018921798305581865 | 0.01895246686752665 |
| 4 | 40 | 3 | 0.019699686702942264 | 0.01972465588252712 |
| 5 | 48 | 5 | 0.021619100697789242 | 0.02164904649440146 |
| 6 | 56 | 7 | 0.023209737262166845 | 0.023243063959461713 |
| 7 | 40 | 5 | 0.025205712094970766 | 0.0252348103982672 |
| 8 | 48 | 7 | 0.02636257061783423 | 0.026395262525911563 |
| 9 | 40 | 7 | 0.030484238815065033 | 0.030515971155548303 |

Maximum relative RMSE change from the 1 ms baseline was
**0.18366134615613872%** (56/3). Maximum absolute RMSE change was
**0.00003332669729486787 rad** (56/7). This is only the measured sensitivity
between these two numerical/control-rate configurations, not a model-error bound.

For the lowest-RMSE tested pair **56/3**:

| Metric, joint 22 | 1 ms | 0.5 ms |
| --- | --- | --- |
| Command tracking RMSE (rad) | 0.014291788281260032 | 0.014318020862790158 |
| Peak original-reference error (rad) | 0.028574143159700638 | 0.028647407445291317 |
| Peak simulated actuator torque (Nm) | 0.9475641881246373 | 0.9472287135950397 |
| Peak measured simulation speed (rad/s) | 0.32241947056412 | 0.32242957287688584 |

The 1 ms original-reference RMSE is **0.839372 degrees**, compared with
**1.444181 degrees** for 40/5, a **41.879%** reduction calculated from the
recorded simulation values. This does not establish the same improvement on G1.

**56/3 is only the best of the nine tested pairs in this fixed-pelvis model.**
It lies on the tested grid boundary (largest Kp, smallest Kd), so these results
do not establish a local or global optimum. They also do not independently
identify the gains of joints 23..25 or any wrist joint. No automatic hardware
recommendation or application is made.

### Artifact and source provenance retained in Git

Artifact name: **mujoco-pd-timestep-comparison**.
Actions run **34565313166**, artifact ID **10185845868**.
Uploaded **23 files**, **138,368,203 bytes** compressed: two run manifests,
two summaries, 18 candidate CSV files and `validation.json`.
Configured retention: **14 days**. The table and hashes in this document remain
in Git after the downloadable CI artifact expires.

ZIP SHA-256:
`70bedd5a8a8819b2f0081d8ea43bf7818d5802316d8530cbd2daa19ef9525f10`.

| File | SHA-256 |
| --- | --- |
| dt_1ms/run.json | `0a91cf2e1bc3ecc8fa1e04345db878c886bce1b71fed5e33fc339f5a18bdbd58` |
| dt_1ms/summary.json | `b4a74c6487c094d694091aa32e4bf7d499dac88ce29e4e2e45aa2ee0a1171082` |
| dt_0_5ms/run.json | `934c3b1d7514ad22986fe879f68a412fce4760510bd7f658cc325c259425ec2a` |
| dt_0_5ms/summary.json | `064e8a4c230a57b4ce59eae09487154db6b95c953b62ec21452cb35f67285eca` |
| dt_1ms/candidate_006.csv (56/3) | `88dee6f2336933c1068c70bb562149c5f3a5062d9d1144df8fd44a0712fbd79d` |
| dt_0_5ms/candidate_006.csv (56/3) | `576a750a7637420efd3adeb89cdd052f1e98412eda823cf46ce1e393d396327a` |

Shared source SHA-256 values from the validated manifests:

| Source | SHA-256 |
| --- | --- |
| mujoco_pd_sweep.py | `479a00108433da16a8bf5291c57940d151f7f386435559919ce07f3225ea9a66` |
| mujoco_pd_contract.py | `698448b9e23f698cbb0b40de090f7b520b18688ddb21add6bb914251f455a71f` |
| mujoco_pd_fixture.py | `5d69af081b4a7a2419ffc1de0f347a1140ceebe8cc0a2229efc8fd81ebbc745b` |
| pd_small_signal_trial.hpp | `6b1df6d7dff08f49b595cf5d32a1feadfe0652a58297b9211f49de0bc4957dbc` |
| twist2_common.hpp | `4b6a6842ab8ff8701c6d8a99e1342f6f6c78856b50288cbf22ec2339a882e53a` |
| g1_joint_contract.py | `04109d0c0746f1223de168d92c2006bdf88142a9b19ee649324ec9a444f1c9ee` |
| Source g1_29dof.xml | `423e28bd718b19f7a65cda539b6f794ddbb268b4b9bdbd85f4bd982b30729617` |

Mesh hashes are retained in both run manifests and `validation.json`. This
closeout does not rewrite those output files or relabel earlier excluded runs.

### Reproduce separately from VR / G1

From the repository root in Windows PowerShell, create the isolated environment
once (package installation needs Internet; the simulation itself does not):

```powershell
py -3.11 -m venv .venv-mujoco-pd
.\.venv-mujoco-pd\Scripts\python.exe -m pip install -r .\experiments\twist2_right_arm_manual\mujoco_pd_requirements.txt
```

Run the nine-pair comparison without starting VR, DDS or G1:

```powershell
.\tools\RUN_MUJOCO_PD_SWEEP.bat --kp-values 40 48 56 --kd-values 3 5 7
```

Optional local visualization of one simulation pair:

```powershell
.\tools\RUN_MUJOCO_PD_SWEEP.bat --kp-values 56 --kd-values 3 --viewer
```

Default output is a new timestamped directory under
`logs/test_results/mujoco_pd`, containing `run.json`, candidate CSVs and
`summary.json`. Existing result folders are not overwritten. The visualizer
and Windows BAT have not been executed in this hosted headless validation.
The existing `START_TWIST2_MINK_CYCLE_CANDIDATE` is not called by this launcher.

### Next permitted work and remaining limits

This completes the initial fixed-pelvis nine-pair screening and two-timestep
artifact-verified comparison. It does not complete real-robot PD calibration.
Continue offline with model/payload/friction/actuator-delay uncertainty and,
where justified, a recorded expanded grid rather than declaring the boundary
winner optimal. Any later free-base TWIST2 balance assessment is a separate
experiment. Do not overwrite the known working VR baseline or deploy these
gains automatically. Robot/All remain blocked during charging; real G1, DDS,
SDK, ARM builds, hardware handoff and motor output were not used here.
