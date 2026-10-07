# Omni optional receiver validation — 2026-10-07

Status: **DEPLOYED_SELF_TESTED_PHYSICAL_RUN_UNVERIFIED**.

## Cause and minimal change

The existing onboard parser validated Omni numeric ages, source identity and calibration before reading bilateral arm targets. The actual PC producer's first-sample state is exactly `{"status":"WAIT","source_age_s":null,"values":null}`. This was rejected with `source_age_s`, even though fresh bilateral targets were present.

The parser now accepts only that canonical WAIT shape as a missing Omni source. It records no Omni source session, marks the Omni age unavailable, and sets normalized locomotion/yaw fields to zero. The unchanged command loop gates locomotion on `omni_live`, so WAIT never becomes a fresh or calibrated Omni sample. Bilateral freshness, joint-array validation and tracking/returning activation remain unchanged.

Missing payload/Omni objects, malformed WAIT values, nonfinite numbers, invalid arm arrays and invalid outer session/sequence are still rejected. This is not a catch-all validation bypass. Non-WAIT Omni packets retain the old validation, including the requirement that `calibrated` is true; supporting arms during a live-but-uncalibrated interval is not part of this patch.

The optional source session does not clear the previous heading-source identity. Diagnostics serialize an unavailable Omni age as JSON null rather than Infinity, preserving the existing finite-JSON log contract. Original datagram forwarding and ACK semantics remain unchanged.

## Files and deployment

Repository copy: `tools/onboard/g1_omni_heading_controller.py` (Linux onboard source; not a new Windows worker).

Actual G1 target: `/home/unitree/groot_onboard_runtime/tools/g1_omni_heading_controller.py`.

Original SHA256: `84d09bb678f720664bd0d273df2089ebdf1d35bdf2c1a71a783d46d3aa72cb92`.

Installed SHA256: `d2e35cd28046861de2c64f60cac8727ef91f53fd22d08c0d613df31e6ed8a2b2`.

Backup: `/home/unitree/groot_onboard_runtime/tools/g1_omni_heading_controller.py.pre_omni_optional_20261007_84d09bb678f7`.

Deployment checked that both the heading controller and actuator were stopped, checked the original hash before writing, tested the staged file with `--self-test`, checked the original hash/process state again, and atomically replaced one Python file. File permissions were preserved. No control loop, motor output, Unity session, camera follower or robot process was started/restarted.

The C++ actuator source, external bridge source/header and actuator binary hashes were identical before/after. PC bilateral IK, 12/1.5 position/orientation tracking, 150/180 deg/s tracking limits, 300 deg/s^2 tracking acceleration, conservative return limits, launcher, camera and Balance/Walk policy logic were not edited.

## Validation

- Full backend: 288 tests, exit 0.
- Full hardware: 44 tests, exit 0.
- New optional-Omni tests: 12, including the actual PC producer's WAIT shape and the actual onboard run loop with all sockets/log sinks/clock/terminal replaced by deterministic test doubles.
- 1,000 normal/stale parser inputs: outputs exactly match the original source.
- 24 malformed non-WAIT inputs: rejection types/reasons match the original.
- Existing normal/disconnect/reconnect scenarios, yaw signs -1 and +1: 48 command ticks per sign, every emitted datagram and diagnostic row equal to the original.
- Cold start without Omni: zero vx/vy/wz with active fresh bilateral targets. Ready/blocked/stale/missing arm inputs do not activate arms; timeout still expires the arm target. Reordered WAIT cannot overwrite a newer live sample.
- Onboard native Python self-test: exit 0; ran before replacement without constructing control sockets.
- Candidate source and test hashes unchanged throughout the full suites.

Evidence folder: `logs/test_results/omni_optional_20261007_093821/`. Original source, narrow diff, test logs, deterministic differential replay, hashes and deployment report are retained. The original G1.zip was not modified.

## Operation and limitations

Use the existing `START_G1_VR_TELEOP.bat`; no fake Omni publisher or new flag is needed. The usual actuation confirmation and G1 startup checks still apply. With no Omni source the command path is zero locomotion plus independently validated bilateral targets; the existing actuator's Balance selection is unchanged. `--no-groot-actuation` still does not start motor actuation and is not a shutdown command.

No physical run of Quest hand tracking plus G1 balance/arms without Omni was performed in this validation. This validates the software path and regression scope, not physical balance, clearance or latency. First live verification still needs the existing support/harness and emergency-stop precautions. Do not replace a running controller to roll back: stop through the existing controlled-shutdown procedure and restore the recorded backup only after confirming the processes are stopped.
