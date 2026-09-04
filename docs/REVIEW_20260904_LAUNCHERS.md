# Tools BAT and launcher full-text review - 2026-09-04

Branch: `main`

This is a **review-only** batch. No BAT was executed, no administrator action
was requested, and no WSL, DDS, Unity, Quest or G1 runtime was started.

## 검토

The following remaining launcher-layer `static_only` files were read in full:

```text
hardware/g1_arm_bridge/test_lowstate_provenance_launchers.py
tools/ALLOW_G1_DDS_WSL.bat
tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat
tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat
tools/BUILD_AND_INSTALL_VR_APK.bat
tools/CHECK_G1_TELEOP_STARTUP.bat
tools/CONFIGURE_G1_ETHERNET.bat
tools/DETECT_G1_NETWORK.bat
tools/PREPARE_G1_GATE6_HOLD.bat
tools/RESTORE_G1_ETHERNET_DHCP.bat
tools/START_G1_GATE5_READ_ONLY.bat
tools/START_G1_GATE7_LIVE_DRY_RUN.bat
tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat
tools/START_G1_GATE7_VR_RECORDING.bat
tools/START_G1_READ_ONLY.bat
tools/TEST_FAKE_MINK_SAFETY_E2E.bat
tools/TEST_G1_GATE5_READ_ONLY.bat
tools/TEST_G1_GATE6_HOLD_OFFLINE.bat
tools/TEST_G1_GATE6_INTERRUPT_RELEASE_OFFLINE.bat
tools/TEST_G1_GATE7_FAULT_MATRIX_OFFLINE.bat
tools/TEST_G1_GATE7_FIRST_LIVE_OFFLINE.bat
tools/TEST_G1_GATE7_HARDWARE_FOUNDATION_OFFLINE.bat
tools/TEST_G1_GATE7_LATEST_CAPTURE_FAULT_MATRIX.bat
tools/TEST_G1_GATE7_LIVE_DRY_RUN.bat
tools/TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat
tools/TEST_G1_GATE7_RUCKIG_HARDWARE_PROFILE_OFFLINE.bat
tools/TEST_G1_GATE7_VIRTUAL_HARDWARE_E2E.bat
tools/TEST_G1_HARDWARE_SAFETY_GATE.bat
tools/TEST_G1_HARDWARE_STATE.bat
tools/TEST_G1_RIGHT_ARM_JOG_OFFLINE.bat
tools/TEST_G1_SHOULDER_PITCH_FULL_AUTHORITY_OFFLINE.bat
tools/TEST_MINK_SAFETY_PIPELINE.bat
tools/TEST_MINK_WRIST_FRAME.bat
tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat
```

### Existing R51 remains on legacy read-only launchers

`CHECK_G1_TELEOP_STARTUP.bat` and `START_G1_GATE5_READ_ONLY.bat` start the
older tokenless UDP 5007 forwarder path. The startup checker/monitor validates
packet fields but does not bind those packets to a one-run forward token.
`START_G1_GATE7_LOWSTATE_DRY_RUN.bat` also uses that tokenless read-only
forwarder, although it cannot publish a robot command.

This is the existing R51 source boundary. The supported physical launchers
covered by `test_lowstate_provenance_launchers.py` use per-run tokens; the
legacy read-only diagnostics above must not be treated as equivalent provenance
evidence.

### Existing R29 remains confirmed

`START_G1_GATE7_VR_RECORDING.bat` checks that the recorder binds UDP 5008 but
does not verify Gate 7 receiver liveness/bind on UDP 5014 before recording. A
capture can therefore exist without proving that the forwarded stream reached
Gate 7. This is already R29.

### Existing R24 extends to launcher text and aggregate test entry

`TEST_G1_GATE7_RUCKIG_HARDWARE_PROFILE_OFFLINE.bat` still labels its velocity
profile `40/100 deg/s` while the controller now uses `0.08 rad/s` for all seven
right-arm joints. `VERIFY_HEAD_CAMERA_FOUNDATION.bat` discovers every backend
test, including the stale exact `40/100` assertion recorded in R24, so the
aggregate camera entry currently inherits that known failure before camera
validation can complete.

### Existing R56-R58 and R59/R67 remain confirmed

- The elevated network BAT files correctly propagate their child PowerShell
  exit code, but do not remedy the underlying `pktmon` result validation and
  transactional network/firewall findings R56-R58.
- `BUILD_AND_INSTALL_VR_APK.bat` still checks/installs the repository-root APK
  path and does not bind installation to a verified Quest serial. This remains
  R59/R67.

### Other conclusions

- Offline test wrappers generally preserve nonzero child status and print a
  concrete result/log path plus an operator action.
- Supported physical launcher provenance tests require one token at forwarder
  and receiver boundaries and reject the retired direct forwarder pattern.
- Detached dry-run/recording windows still rely partly on operator cleanup.
  This was already documented as a process-lifecycle operating limitation and
  is not duplicated as a new R-number here.
- No reviewed BAT was executed because several launch WSL/DDS, alter Windows
  network/firewall state, install an APK, or create runtime listeners.
- No new independent P1/P2/P3 finding was identified in this batch.

## 코드 수정

```text
Launcher behavior changes   : NONE
Production/controller changes: NONE
Network/firewall changes    : NONE
Authorization changes       : NONE
Review artifacts only       : YES
```

The pre-existing local Unity code-coverage settings modification was not
touched.

## 테스트

Executed only the source-inspection launcher regression:

```text
py -3.11 -m unittest hardware.g1_arm_bridge.test_lowstate_provenance_launchers
```

Result:

```text
4 tests run
4 passed
```

No BAT, administrator script, WSL, DDS, Unity, ADB, Quest or G1 process was
executed.

## 남은 항목

1. Continue the remaining non-BAT `static_only` files.
2. Keep R24/R29/R51/R56-R59/R67 remediation separate from this review batch.
3. Do not use tokenless read-only launcher results as supported physical
   startup provenance.
4. Do not run network, publisher or connected-G1 paths without exact user
   authorization.

Review result:

```text
new R-number findings       : 0
existing findings confirmed: R24, R29, R51, R56-R59, R67
physical validation        : NOT AUTHORIZED / NOT RUN
```
