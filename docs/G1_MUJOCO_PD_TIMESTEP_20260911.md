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
