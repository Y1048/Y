# Recorded bimanual simulation regression

The adjacent JSONL contains a selected time window from laptop file
`logs/test_results/bimanual/unity_20260918_094323_0712614.jsonl`.
These are recorded Quest/Unity inputs and MuJoCo simulation state events,
**not measured G1 data**. No hardware output is part of this test.

Input raw JSON and receipt times are retained. State rows retain only tick
times, sequence and original state/reason; redundant joint snapshots were
removed. The original recording is preserved on the laptop.

Start with the last inactive input before engage (529). Original solver
failed at sequence 607 after 2.188 seconds with `qp_infeasible`. The fixture
continues through the subsequent inactive inputs after Unity saw BLOCKED.
New replay must not block, must use checked braking, and must retain angle,
velocity, acceleration and sampled clearance limits. This fixture does not
prove all possible user motions or physical robot safety.
