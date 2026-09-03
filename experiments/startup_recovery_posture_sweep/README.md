# Startup Recovery posture sweep

This isolated offline experiment generates multiple synthetic right-arm initial
poses and runs the current validated Startup Recovery on every sample.

The default quick map keeps shoulder pitch at the captured value and evaluates
a `3 x 3` grid:

- shoulder roll offset: `-15, 0, +15 deg`
- elbow offset: `-15, 0, +15 deg`
- shoulder yaw and all wrist joints: captured values

Run it with:

```powershell
.\experiments\startup_recovery_posture_sweep\RUN_POSTURE_SWEEP.bat
```

Outputs are written under:

```text
logs/experiments/startup_recovery_posture_sweep/
```

The main artifacts are `latest_map.html`, `latest_summary.json`, and
`latest_results.csv`. Each case also retains its complete recovery result and
log for diagnosis.

For a denser three-slice map, run:

```powershell
.\experiments\startup_recovery_posture_sweep\RUN_STANDARD_POSTURE_SWEEP.bat
```

This evaluates 75 exact samples. It can take tens of minutes because every
sample retains the existing QP, joint-limit, collision, velocity,
acceleration, jerk, Safety Gate, and 0.001-degree swept-path checks.

If a slow case reaches the per-case wall-clock limit, preserve completed cells
and rerun only `ERROR` cells with a larger limit:

```powershell
py -3.11 experiments\startup_recovery_posture_sweep\run_sweep.py `
  --resume-run logs\experiments\startup_recovery_posture_sweep\runs\RUN_NAME `
  --case-timeout 420 --workers 1
```

The map is not a proof about unsampled poses between cells. It uses no Unitree
SDK, DDS, network socket, or command publisher, and every result remains
`hardware_ready=false` and `command_output_enabled=false`.
