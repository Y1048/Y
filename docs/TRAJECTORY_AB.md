# Offline Trajectory A/B

Run `VIEW_TRAJECTORY_AB.bat` from the project root. No VR/G1 is required.
This launcher loads isolated MuJoCo 3.12 and cannot send robot commands.
Do not replace a hardware launcher with this experiment.

## Controls

The launcher now starts case 9 with a 40-second clip: move the goal 4 cm
forward during 0-5 s, settle during 5-20 s, rotate around the initial local
wrist X axis by 35 degrees during 20-30 s, then hold until 40 s. Position target
does not move after 5 s. This special case overrides the generic timing below.
The overlay reports shoulder pitch/roll/yaw and elbow cumulative travel during
the rotation phase only. `settled before turn` requires position error below
5 mm and orientation error below 2 degrees; False means residual reach motion
confounds the result. This measures cumulative travel, not net angle change.

- F8: switch A/B without changing replay time.
- F9: select another motion (first calculation takes time).
- F10: restart the same clip.
- F11: change playback speed only; simulation dt stays fixed.
- F12: pause/resume. Close the window to finish.

Both runs use standard project Mink 6D, identical input, initial pose, limits
and four-sample collision checking of shaped steps. Targets stop changing at
10 seconds; the remaining 10 seconds show settling. The cyan point is the goal.
These are synthetic motions, not yet replay of the saved Quest capture.

## Meaning

A is the current zero-terminal-velocity Ruckig behavior. B is an experimental
terminal velocity of 0.1 times waypoint displacement divided by the three-step
horizon duration, bounded by the same joint speed limits. It is not a validated
improvement and does not change Mink's IK costs or hard collision inequalities.
Both are project-adapted Mink, not an unchanged upstream example.

The initial coefficient 0.5 failed settling and was rejected. Coefficient 0.1
passed the isolated stop/bounds test but its moving-waypoint steady speed was
0.03944 rad/s versus A's 0.04152 rad/s. Thus this candidate does NOT establish
a solution to the slowdown. Keep A as the live default.

The 20-second headless runs completed for all ten synthetic motions, with a
rendered snapshot inspected. This is not a ten-case success criterion: the
toward-body case holds near 5 mm with about 105 mm residual error in both modes;
A also reports invalid-velocity rejections in the wrist-Z case. These remain
visible comparison outcomes, not reasons to disable checks. Interactive key
use has not been manually verified in a live viewer this turn.

Results: `logs/experiments/trajectory_ab/latest.json` (overwritten per run).
The viewer shows position/rotation error, clearance and travel for both modes.
Collision holds can reset velocity; this is not a physical dynamics/contact
simulation and does not establish continuous collision safety or hardware
acceleration continuity. Further candidate design and captured-input comparison
remain necessary before any live integration.
