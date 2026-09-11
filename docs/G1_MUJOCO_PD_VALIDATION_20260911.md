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
