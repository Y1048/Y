# Configuration and wrist-frame full-text review - 2026-09-04

Branch: `main`

This is a **review-only** batch. No configuration value, authorization, camera
source or controller behavior was changed.

## 검토

The following remaining `static_only` files were read in full:

```text
MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py
config/camera_profile.json
config/g1_gate6_hold.json
config/g1_gate6_interrupt_release_test.json
config/g1_regular_arm_pose.json
config/g1_right_arm_jog.json
config/g1_right_shoulder_pitch_full_authority_trial.json
config/teleop.json
config/teleimager_real_d435i.yaml
config/teleimager_simulation.yaml
```

### Existing R66 remains confirmed

`config/teleop.json` contains legacy DLS, voxel-workspace and fallback fields,
but it is not the single authoritative source for the active virtual-center
Mink controller. Editing it does not necessarily change the active task costs,
gains or limits. This is the existing R66 configuration-authority finding.

### Physical profile locks remain closed

The reviewed Gate 6 HOLD, interruption, right-arm Jog and shoulder trial
profiles all retain `hardware_output_authorized: false`. The measured Regular
arm-pose artifact also records `physical_output_authorized: false`. Reading
these values is not physical authorization and no profile was unlocked.

### Camera configuration boundaries

- `camera_profile.json` selects the local simulation adapter and records the
  MuJoCo/shared-memory contract plus measurements still required for real D435i
  acceptance.
- The two `teleimager_*.yaml` files describe separate ZMQ/WebRTC TeleImager
  source profiles. They are not evidence that the active Unity camera preview
  currently uses WebRTC or that a physical D435i has been accepted.

### Wrist-frame contract boundary

The static wrist-frame test verifies selected source strings for the Mink yaw
wrist frame, Unity yaw joint reference and translation scale. It does not run
FK, Unity Play, Quest tracking or a connected G1, so its PASS must remain a
source-contract result only.

No new independent P1/P2/P3 finding was identified in this batch.

## 코드 수정

```text
Configuration changes       : NONE
Authorization changes       : NONE
Controller changes          : NONE
Review artifacts only       : YES
```

The pre-existing local Unity code-coverage settings modification was not
touched.

## 테스트

Executed locally:

```text
py -3.11 MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py
py -3.11 -c "parse all config/*.json"
```

Result:

```text
wrist-frame static contract : PASS
config JSON parse            : PASS (15 files)
```

The YAML files were read in full but no TeleImager process was started. No WSL,
DDS, Unity, Quest, camera device or G1 runtime was used.

## 남은 항목

1. Continue the remaining experiment and hardware-helper `static_only` files.
2. Keep R66 remediation separate from review bookkeeping.
3. Preserve all physical profile locks until exact physical action approval.

Review result:

```text
new R-number findings       : 0
existing finding confirmed : R66
physical validation        : NOT AUTHORIZED / NOT RUN
```
