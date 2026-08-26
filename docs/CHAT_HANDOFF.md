# G1 Teleop Project Chat Handoff

Last updated: 2026-08-26

## 0. Operating rules for any ChatGPT conversation

This file is the canonical cross-chat handoff for the project.

Any ChatGPT conversation that continues work on this project should follow these rules automatically after this file is provided or read:

1. Read this file first, then read `docs/ARCHITECTURE.md` before making project changes.
2. Treat the project state, protected local changes, safety constraints, and unresolved cautions recorded here as binding unless the user explicitly changes them.
3. Inspect the current Git/project state before destructive operations such as reset, checkout, stash cleanup, bulk restore, or conflict resolution.
4. After any meaningful milestone, design decision, debugging conclusion, important code change, environment change, or hardware-integration progress, update this file so it reflects the latest state.
5. Keep this document concise and state-oriented. Do not turn it into a raw conversation log.
6. Preserve important existing information when updating. Remove or rewrite stale information only when a newer verified state supersedes it.
7. Keep `docs/ARCHITECTURE.md` for long-lived architecture/design truth and use this file for the current operational checkpoint and handoff state.
8. When a task changes the repository through GitHub, include the handoff update in the same working session whenever practical.

For a new chat, the user should only need to say something equivalent to:

```text
Read docs/CHAT_HANDOFF.md and continue the project from there.
```

No additional explanation of the handoff workflow should be required once this file has been read.

---

This document is the operational handoff for continuing work across ChatGPT conversations.
Read this file together with `docs/ARCHITECTURE.md` before making project changes.
After meaningful work, update this file with the current state, important decisions, unresolved issues, protected local changes, and next steps.

## 1. Repository

- Repository: `Y1048/Y`
- Working branch: `refactor/teleop-architecture`
- Local Windows repo: `C:\Users\user\Desktop\G1_Teleop_Project`
- Unity project: `Unity_G1_VR`
- Main launcher: `START_VR_HAND_TO_MUJOCO.bat`

## 2. Current end-to-end simulation path

Current working path:

```text
Quest / Meta Horizon Link
    -> Unity_G1_VR
    -> UDP target stream
    -> Mink IK controller
    -> joint / velocity / collision constraints
    -> MuJoCo G1 right-arm simulation
    -> UDP robot-state feedback to Unity
```

The current control scope is the G1 **right arm only**.
Non-right-arm DOFs are constrained/frozen in the Mink controller.

Main controller entry point used by the launcher:

```text
MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py
```

Important controller properties already in place:

- Mink IK
- DAQP preferred QP solver
- right-arm control only
- configuration/joint limits
- velocity limits
- collision avoidance
- non-right-arm DOF freeze
- UDP command watchdog/session logic

## 3. Protected local modifications

The following local modifications must not be overwritten or reverted accidentally.
Before any reset, checkout, pull conflict resolution, stash cleanup, or bulk restore, verify these files first.

### 3.1 `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py`

Contains local experimental/comment changes around the Mink/DAQP control path.
Preserve current local edits.

### 3.2 `Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs`

The palm normal / orientation cross product must remain:

```csharp
Vector3.Cross(finger_direction, palm_across)
```

Do not revert it to:

```csharp
Vector3.Cross(palm_across, finger_direction)
```

### 3.3 `config/wrist_frame_calibration.json`

Current calibration is real measured calibration and must be preserved.

```json
"calibrated": true
```

Measured rotation matrix:

```json
[
  [0.9924449310842209, -0.05620383861431516, 0.10906047538064291],
  [0.11826344367346008, 0.20158636449624312, -0.9723048367357238],
  [0.03266215938559683, 0.9778568740742197, 0.20671022512218856]
]
```

## 4. Naming policy

Project-owned naming was cleaned up from Quest-specific wording to generic VR wording where appropriate.

Use `VR` for project-owned names where the concept is headset-independent.

Do **not** globally replace genuine hardware/SDK/protocol-specific Quest names.
Examples that may legitimately remain Quest/Meta-specific include device identifiers, SDK classes, XR rig names, tracked Quest wrist axes, Meta Quest integration names, and vendor-defined concepts.

## 5. Unity status

Unity version currently used by the launcher:

```text
Unity 6000.5.4f1
C:\Program Files\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe
```

`START_VR_HAND_TO_MUJOCO.bat --check` currently passes its prerequisite checks.

Latest functional validation:

- Meta Horizon Link runtime detected
- Unity opens successfully
- `START_VR_HAND_TO_MUJOCO.bat` executes successfully
- Unity Play mode / Quest hand path works
- Mink/MuJoCo right arm follows correctly
- user reported the current live simulation path works very well

### 5.1 Unity crash investigation on 2026-08-26

Unity temporarily crashed immediately while opening `Unity_G1_VR`.
Direct launch and launcher launch both reproduced the issue.

Observed Windows process exit code:

```text
-1073740791 = 0xC0000409
```

Windows Error Reporting identified the faulting module as:

```text
OVRPlugin.dll
version 1.205.0.0
exception 0xc0000409
```

Faulting package path was under:

```text
Library/PackageCache/com.meta.xr.sdk.core@.../Plugins/Win64OpenXR/OVRPlugin.dll
```

Tests performed:

- `-force-d3d11` -> crash
- `-force-d3d12` -> crash
- empty Unity 6000.5.4f1 project -> normal
- original Library renamed and rebuilt -> initially still crashed
- old-name test copy `Unity_G1_Quest3S_TEST` created -> initially still crashed
- temporary bHaptics native DLL disable coincided with first successful launch
- bHaptics DLL was then restored and Unity still opened normally
- original launcher subsequently worked normally

Conclusion at current checkpoint:

- Unity installation and GPU backend are not the primary problem.
- bHaptics was **not proven to be the root cause**.
- historical crash was clearly inside Meta `OVRPlugin.dll` initialization.
- the issue is currently not reproducing after project/package reinitialization.
- do not make unnecessary plugin changes while the system is stable.

Temporary diagnostic artifacts may exist locally:

```text
Unity_G1_VR/Library_BACKUP_20260826
Unity_G1_Quest3S_TEST
```

Do not delete them until the user explicitly decides cleanup is safe.

### 5.2 Oculus XR deprecation warning

Unity currently shows an `Oculus Plugin Deprecation` dialog stating that the Oculus XR plugin provider is deprecated on Unity 6+ and recommending OpenXR.

Current decision:

- click `OK` and continue working
- do not use `Dismiss forever` yet
- do not immediately migrate while the current teleoperation path is stable
- OpenXR migration should be treated as a separate controlled task with regression testing of Quest hand tracking, Unity XR rig/input, Meta XR SDK behavior, and build/runtime behavior

## 6. WSL / Windows environment

WSL installation is complete.

Windows / WSL observations:

```text
WSL: 2.7.12.0
WSL kernel: 6.18.33.2-2
Ubuntu: 26.04 (Resolute Raccoon)
Python in WSL: 3.14.4
```

WSL repo path:

```text
/mnt/c/Users/user/Desktop/G1_Teleop_Project
```

Git initially reported dubious ownership under WSL.
This was addressed with:

```bash
git config --global --add safe.directory /mnt/c/Users/user/Desktop/G1_Teleop_Project
```

Current WSL networking before physical G1 Ethernet work:

```text
eth0: 172.20.140.130/20
mode: default WSL2 NAT
```

Windows active interfaces observed at the checkpoint:

- Wi-Fi: MediaTek Wi-Fi 6E MT7922
- WSL virtual Ethernet: active
- physical Realtek Gaming GbE Family Controller: disconnected

## 7. Physical G1 hardware integration status

Physical G1 Ethernet integration has **not started yet**.
The user explicitly postponed it after preparing WSL.

Current hardware status:

- G1 not yet connected to PC by Ethernet
- Realtek physical Ethernet was disconnected at last check
- Unitree SDK2 not yet installed/configured in the WSL hardware path
- no real G1 actuator command has been sent from this project

Planned architecture:

```text
Quest / Unity (Windows)
    -> desired target
Mink IK controller
    -> desired right-arm joint state
Hardware Safety Gate
    -> validated command
Unitree SDK2 / DDS
    -> Physical G1 right arm
```

Planned hardware integration order:

1. Connect PC <-> G1 by physical Ethernet.
2. Verify Windows Realtek NIC link and actual G1 subnet/IP configuration.
3. Configure WSL networking suitable for DDS/multicast, likely mirrored networking if required.
4. Establish a compatible Python environment for Unitree SDK2; do not assume WSL Python 3.14 is the desired SDK runtime.
5. Install/configure Unitree SDK2.
6. Implement **read-only `LowState` reception first**.
7. Verify G1 model/DoF count, joint ordering, right-arm joint mapping, state values, packet frequency, and timeout behavior.
8. Build the project-owned Hardware Safety Gate.
9. Only after read-only and safety validation, connect the command publisher.

Do not begin physical testing by publishing `LowCmd` blindly.

## 8. Hardware Safety Gate requirements

Before allowing actual G1 right-arm commands, the hardware-side adapter/gate should independently enforce at least:

- startup state validation
- explicit operator enable/engagement state
- packet/session timeout watchdog
- joint position limits
- joint velocity limits
- per-cycle `delta q` limit
- collision/workspace fault handling
- non-right-arm DOF hold/freeze policy
- safe disengagement/hold behavior
- command rejection on invalid/stale state

Unity-side safety is not sufficient by itself; the hardware backend must enforce safety independently.

## 9. Existing Git/stash caution

A previous sync used a stash named similar to:

```text
before-sync-f28689d
```

That stash included an untracked file named:

```text
dasdasd
```

Its importance was never confirmed.
Do not drop the stash merely because the three protected local edits were restored.
If cleanup is considered, inspect the untracked stash tree first.

Useful commands if that stash still exists:

```powershell
git ls-tree -r --name-only 'stash@{0}^3'
git show 'stash@{0}^3:dasdasd'
```

If only `dasdasd` needs restoring:

```powershell
git restore --source='stash@{0}^3' --worktree -- dasdasd
```

Avoid restoring overlapping project files wholesale from the old stash.

## 10. Current priority / next work

Immediate simulation/Unity path is currently healthy.
Do not destabilize it unnecessarily.

Current likely next major task:

```text
resume physical G1 connection preparation
```

When that resumes, begin from Ethernet/NIC state verification, not actuator commands.

OpenXR migration is a separate later stabilization/refactor task and is not the current blocking issue.

## 11. Handoff maintenance

The operating rules at the top of this file are the authoritative instructions for future ChatGPT conversations.

Future updates should maintain this document as the current project checkpoint, including:

- completed work
- current work in progress
- important design decisions
- protected local changes
- unresolved issues and cautions
- environment/hardware state
- next steps

A new chat should not require the user to restate these rules. Reading this file is sufficient.
