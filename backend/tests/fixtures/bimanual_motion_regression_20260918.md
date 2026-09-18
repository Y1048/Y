# Recorded bimanual motion regression (2026-09-18)

This is a selected window of the laptop's recorded Quest/Unity **simulation** input,
not measured G1 motion. The original whole recording remains laptop-local.

Source: `logs/test_results/bimanual/unity_20260918_110743_5190141.jsonl`.
Selection uses the frozen prefix `live_snapshot.jsonl` from
`logs/test_results/bimanual_ik_audit_20260918_111242/` (8,244,327 bytes;
SHA-256 `583a6c82c7dbc6951998136a9c362ad91d9fe60d15cfb6caa05af88662c97780`).
That prefix was taken while the original logger was still running; it is not
represented as a complete original-session export.

Keep the last inactive packet before engage sequence 137, then the tracking and
pinch return through the first ready event. Input JSON and receiver monotonic
times are preserved. State rows retain only time, sequence and original cycle
state/reason; joint snapshots are omitted. 2,335 rows, including 1,404 state ticks.

The regression advances the revised controller at those saved tick times. It
requires finite/range/speed/acceleration/sample-clearance checks, no BLOCKED,
non-arm freeze, and return to ready. Original joint trajectories are NOT golden
outputs: changing the bad trajectory is the intended correction. The original
667-tick tracking segment had 91 checked-braking ticks according to the prior
laptop replay. A new controller need not trigger those same fallbacks.

This fixture does not establish current Quest comfort, all-motion robustness,
continuous collision freedom, moving-obstacle handling or real G1 safety.
