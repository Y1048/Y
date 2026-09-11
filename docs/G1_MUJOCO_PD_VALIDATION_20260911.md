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
