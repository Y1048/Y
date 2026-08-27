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
    def test_live_sender_keeps_manual_pinch_and_disables_workspace_disengage(self):
        sender = (TELEOP_ROOT / "G1ExistingTargetUdpSender.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("pinch_disengaged", sender)
        self.assertIn("UpdatePinchDisengage", sender)
        self.assertIn("pinch_disengage_hold_seconds = 0.50f", sender)
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
        self.assertNotIn(
            "feasible_target_position = robot_wrist_at_calibration",
            preview,
        )
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

        self.assertIn("tracked_wrist_max_speed_mps = 1.10f", binder)
        self.assertIn("tracked_pose_outlier_latched = true", binder)
        self.assertNotIn("neutral_wrist_position += tracking_jump", binder)
        self.assertNotIn("RebaseCalibrationPreservingCurrentTarget", binder)
        self.assertIn("disengage_on_tracking_loss = true", sender)
        self.assertIn("tracking_loss_confirm_seconds = 0.35f", sender)
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
        self.assertIn("pinch_disengage_hold_seconds = 0.50f", sender)
        self.assertIn("pinch_wait_for_release", sender)

    def test_live_scene_disables_workspace_disengagement(self):
        scene = (
            PROJECT_ROOT / "Unity_G1_VR" / "Assets" / "Scenes" / "SampleScene.unity"
        ).read_text(encoding="utf-8")

        self.assertIn("disengage_on_workspace_exit: 0", scene)
        self.assertIn("disengage_on_tracking_loss: 1", scene)
        self.assertIn("tracking_loss_confirm_seconds: 0.35", scene)

    def test_head_camera_aligns_once_without_continuous_position_lock(self):
        scene = (
            PROJECT_ROOT / "Unity_G1_VR" / "Assets" / "Scenes" / "SampleScene.unity"
        ).read_text(encoding="utf-8")
        camera = (TELEOP_ROOT / "G1HeadLockedCamera.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("align_position_once: 1", scene)
        self.assertIn("lock_position: 0", scene)
        self.assertIn("initial_alignment_needed", camera)
        self.assertIn("IsInitialAlignmentApplied = true", camera)

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

    def test_smooth_controller_sends_direct_green_target_to_limited_ik(self):
        controller = SMOOTH_CONTROLLER.read_text(encoding="utf-8")

        self.assertNotIn("WorkspaceTargetProjector", controller)
        self.assertNotIn("FEASIBLE_TARGET_ACCEPT_ERROR_M", controller)
        self.assertNotIn("last_feasible_center_position", controller)
        self.assertNotIn("target_accepted", controller)
        self.assertNotIn("commanded_center_position = base.step_position(", controller)
        self.assertNotIn("commanded_target_rotation = base.step_rotation(", controller)
        self.assertIn("target_center_position = desired_center_position", controller)
        self.assertIn("target_rotation = desired_target_rotation", controller)
        self.assertIn('clutch_reference["yaw_position"]', controller)
        self.assertIn("operator_target_position - current_center_to_yaw", controller)
        self.assertIn(
            "external_target_position = operator_target_position.copy()",
            controller,
        )
        self.assertIn("feasible_target_position = external_target_position.copy()", controller)
        self.assertIn("workspace_limited=False", controller)
        self.assertNotIn("reachability_limited", controller)



if __name__ == "__main__":
    unittest.main()
