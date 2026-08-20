# G1 Quest 3S Hand Teleoperation Interface

## Goal

Use Quest 3S hand tracking in Unity as the input source, then send a stable hand target message to the G1 MuJoCo / robot controller.

## Runtime Split

```text
Quest 3S / Unity
-> hand pose smoothing
-> coordinate mapping
-> UDP JSON message
-> MuJoCo G1 IK controller
-> right_arm_q_target[7]
-> later: Unitree LowCmd / DDS bridge
```

## Unity Scripts

Current Unity project:

```text
C:\Users\user\Desktop\G1_Teleop_Project\Unity_G1_Quest3S
```

Main scripts:

```text
C:\Users\user\Desktop\G1_Teleop_Project\Unity_G1_Quest3S\Assets\G1Teleop\G1ExistingTargetUdpSender.cs
C:\Users\user\Desktop\G1_Teleop_Project\Unity_G1_Quest3S\Assets\G1Teleop\G1ExistingHandTargetBinder.cs
C:\Users\user\Desktop\G1_Teleop_Project\Unity_G1_Quest3S\Assets\G1Teleop\G1UnityRightArmPreview.cs
```

## Input Modes

The current scene uses the existing KAERI VR input object and sends the target transform to MuJoCo.

```text
1: ManualKeyboard
2: AutoMotion
3: TransformSources
```

Quest 3S hand tracking is bound to the scene target through `G1ExistingHandTargetBinder`.

Hotkeys:

```text
1: manual keyboard mode
2: automatic fake motion mode
3: Quest/Transform source mode
C: recalibrate hand origin
R: reset robot target
W/S/A/D/Q/E: move manual target
Shift: faster manual movement
```

## UDP Message

Default target:

```text
127.0.0.1:5005
```

JSON format:

```json
{
  "right": {
    "pos": [0.42, -0.16, 1.05],
    "rot": [0.0, 0.0, 0.0, 1.0],
    "valid": true
  },
  "timestamp": 0.0,
  "source": "unity_quest3s_or_fake"
}
```

Optional left hand:

```json
{
  "right": {
    "pos": [0.42, -0.16, 1.05],
    "rot": [0.0, 0.0, 0.0, 1.0],
    "valid": true
  },
  "left": {
    "pos": [0.42, 0.16, 1.05],
    "rot": [0.0, 0.0, 0.0, 1.0],
    "valid": true
  },
  "timestamp": 0.0,
  "source": "unity_quest3s_or_fake"
}
```

## Quest Link Editor Test Route

Current practical route:

```text
Quest 3S
-> Meta Horizon Link / Quest Link
-> Unity Editor Play Mode
-> Unity XR Hands
-> G1Quest3SXRHandsInput
-> G1HandPoseUdpSender TransformSources mode
-> UDP target to MuJoCo
```

This avoids installing an APK through ADB during early testing.

Editor test steps:

```text
1. Connect Quest through Meta Horizon Link.
2. Open the Unity project.
3. Enable OpenXR and XR Hands provider settings if Unity asks for them.
4. Press Play.
5. Click Quest mode or press key 3.
6. Check the on-screen status:
   - XR Hands ON
   - Right tracked
   - Left tracked
7. Press C once while wearing the headset to calibrate the current hand origin.
8. Move the right hand and check whether the Unity green target and MuJoCo target move together.
```

If the status remains `XR Hands OFF`, Unity is not receiving a hand tracking subsystem from the current OpenXR/Link runtime yet.

If the status is `XR Hands ON` but `Right not tracked`, the runtime is active but the headset is not currently providing tracked hand joints.

## Mapping Rule

The sender uses relative hand motion, not absolute world position.

```text
hand_delta = current_hand_position - calibrated_hand_origin
robot_target = robot_center + scale * hand_delta
```

Current default scale:

```text
handToRobotScale = [0.7, -0.7, 0.7]
```

The negative Y scale handles left/right direction mismatch seen during Unity/MuJoCo comparison.

## Why This Is Useful For The Supervisor Code

The Unity side does not send motor torques. It only sends a stable hand/tool target.

The downstream G1 controller can then do:

```text
UDP hand target
-> coordinate/workspace validation
-> G1 7DoF arm IK
-> right_arm_q_target[7]
-> existing LowCmd/DDS safety/control structure
```

This keeps Unity/Quest input separate from the real robot command layer.
