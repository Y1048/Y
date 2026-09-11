# MuJoCo PD validation evidence — 2026-09-11

This supplements `G1_REGULAR_HANDOFF_20260910.md`. Simulation only; all existing
VR/G1 files and physical launch restrictions remain unchanged.

## Completed runs

- `032f3462`, Actions `34563019765`: 19/19 tests passed. The separate CLI sweep
  failed before starting due to relative `__file__` in provenance recording.
- `610c5bab`, Actions `34563855695`, job `103151845735`: 21/21 tests passed.
  All nine Kp={40,48,56} x Kd={3,5,7} trajectories completed three cycles each.
  Each candidate recorded 7,633 trial samples. No candidate tripped numerical,
  tracking or velocity guards. Every candidate had `contact_sample_ratio=1.0`,
  so all nine were correctly excluded under the current conservative rule.
  The ranking is empty and the CLI returned 2: NOT an accepted tuning result.
  Artifact `10185310029` contains run/summary JSON and all nine CSV files.

The 40/5 reference RMSE was 0.025205712094970766 rad and 56/3 was
0.014649809182167359 rad, but these are **contact-flagged**, unranked results.
Do not recommend these gains or erase contact exclusions to obtain a pass.

## Contact diagnosis change

Base: `610c5babf57617633f7bfa94c0ce3d7296195fc7`.
Add an offline probe that observes the SAME run_candidate/mj_step execution,
records contacting geom/body pairs, distances, active constraints, and wrench
magnitudes using mj_contactForce. It never suppresses collisions or changes
runtime, fixture, gains or acceptance policy. A separate hosted workflow runs
this diagnostic without Python socket events. Result is pending inspection at
commit creation. The main handoff will link the measured resolution.

## Diagnosed source and fixture correction

Base: `fcfb2160d8c1ac54e272ea69b970e4b34596d410`.
Actions `34564228397`, job `103152936418` succeeded. Its 40/5 probe observed
18,265 physics steps and exactly two contacting body pairs throughout:
`pelvis / left_hip_pitch_link` and `pelvis / right_hip_pitch_link`. These were
ACTIVE contacts, not harmless margin-only flags. Peak simulated forces were
41,090.08 N and 38,854.48 N, with initial penetrations under 0.7 mm. Those
forces are artifacts of this fixture, NOT measured forces on a G1.

Removing the pelvis free joint makes its weld root static/world. MuJoCo's
normal parent-child collision filtering is not applied to that static parent,
so assembly contacts appear that the original free-root model filtered out.
Primary reference: MuJoCo computation documentation, Collision detection /
Filtering, https://mujoco.readthedocs.io/en/3.3.5/computation/.

Correction: `mujoco_pd_fixture.py` recreates ONLY the source pelvis direct-child
filter for left_hip_pitch, right_hip_pitch, and waist_yaw in the in-memory model.
It validates the exact source topology and refuses explicitly disabled parent
filters or explicit geom pairs. No source XML/mesh, collision mask, nonadjacent
collision, trajectory, gain, hardware code, or ranking threshold is changed.
The generated exclusions and helper hash are recorded in run.json.

Add regressions comparing original free-root collision pairs, the broken fixed
fixture, and the corrected fixture; preserve geometry masks; demonstrate that
an added nonadjacent wrist obstacle still causes contact; require a completed
40/5 trial to be contact-free. Existing contact exclusion in ranking is retained.
Local pure math/summary/XML tests: **18/18 passed**, with exact uploaded engine
blob matching the tested file. Hosted **21+6 tests** and nine-pair sweep are
pending at commit creation and must be inspected before claiming a result.

Limitations remain fixed pelvis, ideal motors, uncalibrated inertial/friction
parameters, no TWIST2 standing balance, no physical validation, and no local
Windows GUI test. This correction restores a documented source-model behavior;
it is not a calibration of the real robot.

## Final inspected result — corrected fixture

Tested code: `516afef2f5ff74c3aaf198c091f890b6565b2e95`.
Engine blob: `96ca17fe73cc4d9214977ebadfef5a283e8d8462`.
Actions run: https://github.com/Y1048/Y/actions/runs/34564937652
Job: `103155008114`, `fixed-pelvis`, conclusion **success**.
Environment: GitHub-hosted Ubuntu, Python **3.11.16**, MuJoCo **3.3.7**,
NumPy **2.4.6**. This was not a local Windows or G1 run.

The decoded job log and completed job status were inspected after execution:
**21/21 main tests + 6/6 fixture tests = 27/27 passed, no skips**. This includes
actual dynamics, deterministic reset/repeatability, gain-dependent response,
original C++ trajectory parity, failure exclusions, relative CLI execution,
artifact hash/overwrite checks, and all five protected VR/PD source identities.
The free-root/broken-fixed/corrected-fixed collision comparison and an added
wrist-obstacle contact test also passed. Geometry masks remain unchanged.

The full **3 x 3 sweep completed 9/9 candidates**, each with **3 cycles** and
**7,633 trial samples**. All **9/9 were eligible** under the unchanged criteria.
Every candidate had zero recorded trial contact ratio, torque-target limiting
ratio, hard-clipping ratio and slew-exceeded ratio. No numerical, tracking or
velocity guard interrupted these runs. The sweep rejected Python socket audit
events; no DDS, SDK or physical robot program was used.

### Measured simulation comparison

These values are the ORIGINAL reference RMSE of joint 22 in radians, not the
RMSE against a potentially limited command. The table is from the corrected
run above, not a relabeling of the earlier contact-excluded artifact.

| Rank | Kp, joints 22..25 | Kd, joints 22..25 | Joint 22 reference RMSE (rad) |
| --- | --- | --- | --- |
| 1 | 56 | 3 | 0.014649809182167359 |
| 2 | 48 | 3 | 0.016795829286464642 |
| 3 | 56 | 5 | 0.018921798305581865 |
| 4 | 40 | 3 | 0.019699686702942264 |
| 5 | 48 | 5 | 0.021619100697789242 |
| 6 | 56 | 7 | 0.023209737262166845 |
| 7 | 40 | 5 | 0.025205712094970766 |
| 8 | 48 | 7 | 0.02636257061783423 |
| 9 | 40 | 7 | 0.030484238815065033 |

For the lowest-RMSE tested pair **56/3**, joint 22 peak reference error was
**0.028574143159700638 rad**, peak hold overshoot
**0.00017898283131112525 rad**, peak speed **0.32241947056412 rad/s**,
and peak simulated actuator torque **0.9475641881246373 Nm**.
These are not zero tracking error or absence of all vibration. Only joint 22
was excited; this does not independently tune every proximal joint.

**56/3 is a simulation-screening candidate within this grid and model, not a
hardware recommendation or proof of a global optimum.** No gains were applied
to real G1 or normal VR configuration. `recommended_hardware_gains` stays null
and `hardware_config_modified` stays false.

### Retained outputs

The successful run uploaded **11 files**: `run.json`, `summary.json`, and nine
candidate CSV files in artifact **mujoco-pd-fixed-pelvis**, ID **10185682363**:
https://github.com/Y1048/Y/actions/runs/34564937652/artifacts/10185682363

Artifact ZIP SHA-256:
`56605d6cad411d8cc94ea2ee47ddcc3e7f450987189bd550f224f3482ec1321b`.
Recorded `run.json` SHA-256:
`0a91cf2e1bc3ecc8fa1e04345db878c886bce1b71fed5e33fc339f5a18bdbd58`.
The workflow retains downloadable artifacts for 14 days; the compact result
and provenance above remain committed after artifact expiry.

### Remaining validation

Windows BAT/GUI execution, timestep sensitivity, parameter/payload/delay
sensitivity, free-base standing with TWIST2, real motor behavior, and physical
handoff are not validated by this run. No additional trials were performed
for this documentation-only result entry. Continue with separate offline
sensitivity tests rather than deploying this grid winner automatically.
