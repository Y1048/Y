# Recorded staged-return session — 2026-09-18

Source log: `unity_20260918_134204_4595123.jsonl`, recorded by the existing
Unity loopback simulator on the laptop. This is not measured G1 telemetry.
The current task read the existing recording; it did not start Unity/Quest.

The source log carries `bimanual_motion_v1`, `bimanual_boundary_v1`, and
`bimanual_staged_return_v1`. All five recorded Python file hashes match the
source files at `7e742190dc291dbe403a238a455f000ed828d5b5`.

Selected interval: startup through the first completed tracking-loss return.
The gzip contains JSON with original packet values and receipt/tick times,
recorded output joint positions, states, actions, and return-stage diagnostics.
It omits the long idle tail, routine timing diagnostics, and redundant fields.
No input was synthesized for this fixture. Gzip mtime is fixed to zero.

- Selected records: 5,635 (2,202 input rows and 3,433 state rows).
- Source frozen prefix: 53,426,095 bytes.
- Source prefix SHA-256: `08e63f708c22b2423705cb62ba5843f8610be47d0c4e11ba72974be3d5353700`.
- Compressed fixture SHA-256: `a7410f6433fa5f18c73fbcc23880ca14213f78e4accc1e70e46e2e6ffc855341`.

`test_bimanual_recorded_session.py` replays the actual decoder and UnityCycle
without sockets, compares logged joint output (absolute tolerance 5e-6 rad),
and checks fixed-dt output continuity, joint/rate bounds, sampled bilateral
clearance, tracking-loss braking, waypoint/home/settle completion, and zero-speed READY.
Both fixture provenance and replay tests are included in `--mode test`.

```powershell
py -3.11 MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py --mode test --engine-root '<directory containing mujoco 3.12.0>'
```

This session contains one tracking-loss return and no subsequent re-engage.
Do not cite it as a pinch-return, reconnect, subjective comfort, continuous
collision-proof, or physical braking validation. Near-boundary geometry
(about 5mm) is recorded as a limitation, not additional clearance margin.
The full original log and frozen prefix remain on the laptop.
