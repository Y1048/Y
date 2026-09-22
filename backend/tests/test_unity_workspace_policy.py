from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TELEOP_ROOT = PROJECT_ROOT / "Unity_G1_VR" / "Assets" / "G1Teleop"
SMOOTH_CONTROLLER = (
    PROJECT_ROOT
    / "MuJoCo_G1_Controller"
    / "scripts"
    / "run_mink_g1_right_arm_virtual_center_live.py"
)
MINK_BASE_CONTROLLER = (
    PROJECT_ROOT
    / "MuJoCo_G1_Controller"
    / "scripts"
    / "run_mink_g1_right_arm_prototype.py"
)


class UnityWorkspacePolicyTest(unittest.TestCase):
    def test_play_mode_uses_fast_scene_reset_with_domain_reload(self):
        settings = (PROJECT_ROOT / "Unity_G1_VR/ProjectSettings/EditorSettings.asset").read_text(
            encoding="utf-8")
        self.assertIn("m_EnterPlayModeOptionsEnabled: 1", settings)
        self.assertIn("m_EnterPlayModeOptions: 2", settings)

    def test_rotation_provenance_is_unique_and_observational(self):
        trace = (TELEOP_ROOT / "G1LiveTeleopTrace.cs").read_text(encoding="utf-8")
        binder = (TELEOP_ROOT / "G1ExistingHandTargetBinder.cs").read_text(encoding="utf-8")
        sender = (TELEOP_ROOT / "G1ExistingTargetUdpSender.cs").read_text(encoding="utf-8")
        self.assertIn('"rotation_trace_"', trace)
        self.assertIn("FileMode.CreateNew", trace)
        self.assertIn('Guid.NewGuid().ToString("N")', trace)
        for field in ("SourceWristRotation", "TrackedWristRotation", "OperatorHeading",
                      "EngagementFrameRevision", "IsAnatomicalRotationUsed", "LastSentPacket"):
            self.assertIn(field, trace)
        self.assertLess(sender.index("if (!SendPacket(json_text)) return;"),
                        sender.index("LastSentPacket = json_text;"))
        self.assertIn("IsAnatomicalRotationUsed = false;", binder)
        self.assertIn("IsAnatomicalRotationUsed = true;", binder)
        self.assertNotIn("SendPacket(", trace)

    def test_display_source_selection_is_explicit_and_launchers_choose_modes(self):
        preview = (TELEOP_ROOT / "G1UnityRightArmPreview.cs").read_text(encoding="utf-8")
        receiver = (TELEOP_ROOT / "G1RobotStateUdpReceiver.cs").read_text(encoding="utf-8")
        self.assertIn("SelectDisplaySource(ActiveDisplayMode, display_mode_changed", preview)
        self.assertIn("display_mode_changed |= ReadDisplayMode() != ActiveDisplayMode", preview)
        self.assertIn("G1 STATE LOST / WAITING - POSE FROZEN", preview)
        self.assertIn("RECORDED G1 - NOT LIVE", preview)
        self.assertIn("udp_port == 5010 ? HardwareStateSource", receiver)
        root_launcher = (PROJECT_ROOT / "START_VR_HAND_TO_MUJOCO.bat").read_text()
        self.assertIn('set "DISPLAY_MODE=simulation"', root_launcher)
        self.assertIn('"--hardware-display" set "DISPLAY_MODE=hardware"', root_launcher)
        for name, mode in (("START_G1_GATE7_LIVE_HARDWARE.bat", "hardware"),
                           ("VIEW_G1_LIVE_MUJOCO.bat", "hardware"),
                           ("VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat", "recorded")):
            content = (PROJECT_ROOT / "tools" / name).read_text()
            self.assertIn('SET_UNITY_DISPLAY_MODE.ps1" -Mode ' + mode, content)
        hardware = (PROJECT_ROOT / "tools/START_G1_GATE7_LIVE_HARDWARE.bat").read_text()
        self.assertIn('START_VR_HAND_TO_MUJOCO.bat" --hardware-display', hardware)

    def test_vanilla_mink_comparison_launcher_is_explicit_and_simulation_only(self):
        root_launcher = (PROJECT_ROOT / "START_VR_HAND_TO_MUJOCO.bat").read_text()
        vanilla_launcher = (
            PROJECT_ROOT / "START_VR_HAND_TO_MUJOCO_VANILLA_MINK.bat"
        ).read_text()
        prototype = MINK_BASE_CONTROLLER.read_text(encoding="utf-8")

        self.assertIn('"--vanilla-mink"', root_launcher)
        self.assertIn("run_mink_g1_right_arm_prototype_entry.py", root_launcher)
        self.assertIn(
            'START_VR_HAND_TO_MUJOCO.bat" --vanilla-mink --mink-default',
            vanilla_launcher,
        )
        self.assertIn("G1 publisher: NONE / Robot command: NONE", vanilla_launcher)
        self.assertIn("UDP %UDP_PORT% is already used by another controller", vanilla_launcher)
        self.assertIn("Close the existing Mink/MuJoCo window", vanilla_launcher)
        self.assertIn('frame_name="right_wrist_yaw_link"', prototype)
        self.assertIn("position_cost=POSITION_COST", prototype)
        self.assertIn("orientation_cost=ORIENTATION_COST", prototype)
        self.assertIn('"--collision-profile"', prototype)

    def test_live_sender_keeps_manual_pinch_and_disables_workspace_disengage(self):
        sender = (TELEOP_ROOT / "G1ExistingTargetUdpSender.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("pinch_disengaged", sender)
        self.assertIn("UpdatePinchDisengage", sender)
        self.assertIn("pinch_disengage_hold_seconds = 1.00f", sender)
        self.assertIn("disengage_on_workspace_exit = false", sender)
        self.assertIn(
            "clamped_robot_target = use_rectangular_workspace_fallback",
            sender,
        )
        self.assertIn(": UnclampedRobotTarget;", sender)
        self.assertIn('? "workspace_exit"', sender)
        self.assertIn(': command_valid ? "active" : "idle";', sender)

    def test_preview_shows_blue_green_pink_markers_and_white_path(self):
        preview = (TELEOP_ROOT / "G1UnityRightArmPreview.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn('"tracked_quest_wrist_marker"', preview)
        self.assertIn('"g1_actual_wrist_marker"', preview)
        self.assertIn('"g1_feasible_motion_target_marker"', preview)
        self.assertIn("Vector3 command_target_position = command_position", preview)
        self.assertIn("state_receiver.LatestFeasibleTargetOperatorDelta", preview)
        self.assertIn("state_receiver.HasFeasibleTarget", preview)
        self.assertIn("state_receiver.LatestSessionId == target_sender.CurrentSessionId", preview)
        self.assertIn('"operator_to_g1_wrist_path"', preview)
        self.assertIn("mapping_line.startColor = Color.white", preview)
        self.assertIn("mapping_line.SetPosition(0, raw_hand_position)", preview)
        self.assertIn("mapping_line.SetPosition(1, robot_position)", preview)
        self.assertIn("show_orientation_axes = false", preview)
        self.assertIn(
            "SetTargetTrackingObjectsActive(target_visible, command_active)",
            preview,
        )
        self.assertIn("robot_wrist_marker.gameObject.SetActive(robot_active)", preview)
        self.assertIn("Vector3.one * 0.055f * progress_scale", preview)
        self.assertIn(
            "target_hand_axes.gameObject.SetActive(show_orientation_axes && target_active)",
            preview,
        )
        self.assertNotIn("CreateWorkspaceWarningRing", preview)
        self.assertNotIn("workspace_limit_material", preview)

    def test_preview_is_the_only_runtime_marker_owner(self):
        obsolete_marker_owners = (
            "G1ActualWristYawMarker.cs",
            "G1MinkTargetAbsoluteOverlay.cs",
            "G1MinkWristFrameOverlay.cs",
            "G1EngagementTargetSizePolicy.cs",
            "G1DebugVisualFilter.cs",
        )

        for file_name in obsolete_marker_owners:
            self.assertFalse(
                (TELEOP_ROOT / file_name).exists(),
                f"obsolete runtime marker owner still exists: {file_name}",
            )

        runtime_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in TELEOP_ROOT.glob("*.cs")
        )
        self.assertNotIn('GameObject.Find("operator_hand_target_marker")', runtime_source)

    def test_confirmed_tracking_loss_disengages_without_rebasing(self):
        binder = (TELEOP_ROOT / "G1ExistingHandTargetBinder.cs").read_text(
            encoding="utf-8"
        )
        sender = (TELEOP_ROOT / "G1ExistingTargetUdpSender.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("tracked_wrist_max_speed_mps = 5.00f", binder)
        self.assertIn("previous_observed_wrist_position", binder)
        self.assertIn("previous_observed_wrist_position = current_wrist_position", binder)
        self.assertIn("tracked_pose_outlier_latched = true", binder)
        self.assertIn("IsRawTrackingAvailable = GetHandTracked();", binder)
        self.assertNotIn("neutral_wrist_position += tracking_jump", binder)
        self.assertNotIn("RebaseCalibrationPreservingCurrentTarget", binder)
        self.assertIn("disengage_on_tracking_loss = true", sender)
        self.assertIn("tracking_loss_confirm_seconds = 0.35f", sender)
        self.assertIn("!raw_tracking_available", sender)
        self.assertNotIn("&& !tracking_valid;", sender)
        self.assertIn('IsTrackingLossDisengaged ? "tracking_disengaged"', sender)
        self.assertIn("hand_binder.ResetCalibration();", sender)

    def test_obsolete_optional_components_are_removed(self):
        self.assertFalse((TELEOP_ROOT / "G1BackendWorkspaceAuthority.cs").exists())
        self.assertFalse((TELEOP_ROOT / "G1PinchTeleopDisengage.cs").exists())

    def test_alignment_engage_keeps_only_index_pinch_disengage(self):
        sender = (TELEOP_ROOT / "G1ExistingTargetUdpSender.cs").read_text(
            encoding="utf-8"
        )
        binder = (TELEOP_ROOT / "G1ExistingHandTargetBinder.cs").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("OVRHand.HandFinger.Middle", sender)
        self.assertNotIn("middle_pinch_engage", sender)
        self.assertIn("engagement_hold_duration = 0.55f", binder)
        self.assertIn("if (auto_calibrate_on_first_track && EngagementProgress >= 1.0f)", binder)
        self.assertIn("Calibrate();", binder)
        self.assertIn("OVRHand.HandFinger.Index", sender)
        self.assertIn("pinch_disengage_hold_seconds = 1.00f", sender)
        self.assertIn("pinch_wait_for_release", sender)

    def test_live_scene_disables_workspace_disengagement(self):
        scene = (
            PROJECT_ROOT / "Unity_G1_VR" / "Assets" / "Scenes" / "SampleScene.unity"
        ).read_text(encoding="utf-8")

        self.assertIn("disengage_on_workspace_exit: 0", scene)
        self.assertIn("disengage_on_tracking_loss: 1", scene)
        self.assertIn("tracking_loss_confirm_seconds: 0.35", scene)

    def test_head_camera_aligns_once_and_follows_displayed_robot_position(self):
        scene = (
            PROJECT_ROOT / "Unity_G1_VR" / "Assets" / "Scenes" / "SampleScene.unity"
        ).read_text(encoding="utf-8")
        camera = (TELEOP_ROOT / "G1HeadLockedCamera.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("align_position_once: 1", scene)
        self.assertIn("lock_position: 1", scene)
        self.assertIn("initial_alignment_needed", camera)
        self.assertIn("IsInitialAlignmentApplied = true", camera)
        self.assertIn("LockTrackingSpacePosition", camera)

    def test_virtual_wrist_target_follows_measured_robot_base_rotation(self):
        preview = (TELEOP_ROOT / "G1UnityRightArmPreview.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("robot_base_position_at_calibration", preview)
        self.assertIn("robot_base_rotation_at_calibration", preview)
        self.assertIn("FollowRobotBaseFromCalibration(command_position)", preview)
        self.assertIn("FollowRobotBaseFromCalibration(command_rotation)", preview)
        self.assertIn(
            "official_g1_object.transform.rotation\n"
            "            * Quaternion.Inverse(robot_base_rotation_at_calibration)",
            preview,
        )

    def test_cyan_quest_wrist_uses_display_pose_without_changing_command_pose(self):
        binder = (TELEOP_ROOT / "G1ExistingHandTargetBinder.cs").read_text(
            encoding="utf-8"
        )
        preview = (TELEOP_ROOT / "G1UnityRightArmPreview.cs").read_text(
            encoding="utf-8"
        )
        bimanual = (TELEOP_ROOT / "G1BimanualSimulationSender.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "DisplayedWristPosition = tracked_wrist_transform.position", binder
        )
        self.assertIn(
            "TrackedWristPosition = current_wrist_position", binder
        )
        self.assertIn("hand_binder.DisplayedWristPosition", preview)
        self.assertIn("hand_binder.DisplayedWristRotation", preview)
        self.assertIn("leftBinder.DisplayedWristPosition", bimanual)
        self.assertIn("leftBinder.DisplayedWristRotation", bimanual)

    def test_head_only_motion_is_not_subtracted_from_the_wrist(self):
        binder = (TELEOP_ROOT / "G1ExistingHandTargetBinder.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("GetCommonBodyTranslationStep", binder)
        self.assertIn("CalculateBodyCompensatedTrackingDelta", binder)
        self.assertNotIn("CalculateHeadRelativeTrackingDelta", binder)
        self.assertIn("return head_step;", binder)
        self.assertIn("UpdateHeadMotionDiagnostics", binder)
        self.assertNotIn("active-hold-head-motion", binder)
        self.assertNotIn("head_motion_hold_threshold_deg_s", binder)
        self.assertNotIn("head_motion_resume_wrist_tolerance", binder)
        self.assertIn("IsHeadMotionHold = false", binder)

    def test_smooth_controller_preserves_raw_target_and_checks_green_separately(self):
        controller = SMOOTH_CONTROLLER.read_text(encoding="utf-8")

        self.assertNotIn("WorkspaceTargetProjector", controller)
        self.assertNotIn("FEASIBLE_TARGET_ACCEPT_ERROR_M", controller)
        self.assertNotIn("last_feasible_center_position", controller)
        self.assertNotIn("target_accepted", controller)
        self.assertNotIn("commanded_center_position = base.step_position(", controller)
        self.assertNotIn("commanded_target_rotation = base.step_rotation(", controller)
        self.assertIn("target_center_position = operator_target_position.copy()", controller)
        self.assertIn("target_rotation = desired_target_rotation", controller)
        self.assertIn('clutch_reference["center_position"]', controller)
        self.assertNotIn('clutch_reference["yaw_position"]', controller)
        self.assertIn(
            "external_target_position = operator_target_position.copy()",
            controller,
        )
        self.assertNotIn("feasible_target_position = external_target_position.copy()", controller)
        self.assertIn("feasible_target_position = feasible_plan.target_position", controller)
        self.assertIn("trajectory.Step(", controller)
        self.assertIn("configuration.update(trajectory_step.q)", controller)
        self.assertIn('"feasible_target_valid": feasible_target_valid', controller)
        self.assertIn("workspace_limited=False", controller)
        self.assertNotIn("reachability_limited", controller)



if __name__ == "__main__":
    unittest.main()
