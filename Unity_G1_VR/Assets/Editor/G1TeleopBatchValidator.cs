using System;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class G1TeleopBatchValidator
{
    private const string scene_path = "Assets/Scenes/SampleScene.unity";
    private const string g1_prefab_path =
        "Assets/Resources/G1Official/G1_29DoF_Official.prefab";

    [MenuItem("G1 Teleop/Validate Teleoperation Project")]
    public static void ValidateTeleoperationProject()
    {
        EditorSceneManager.OpenScene(scene_path, OpenSceneMode.Single);

        G1ExistingHandTargetBinder binder_value =
            FindSceneComponent<G1ExistingHandTargetBinder>();
        G1ExistingTargetUdpSender sender_value =
            FindSceneComponent<G1ExistingTargetUdpSender>();
        G1UnityRightArmPreview preview_value =
            FindSceneComponent<G1UnityRightArmPreview>();
        G1HeadLockedCamera camera_lock_value =
            FindSceneComponent<G1HeadLockedCamera>();

        AssertCondition(binder_value != null, "Hand target binder is missing.");
        AssertCondition(sender_value != null, "UDP sender is missing.");
        AssertCondition(preview_value != null, "Unity arm preview is missing.");
        AssertCondition(camera_lock_value != null, "G1 head-locked camera is missing.");

        ValidateBinder(binder_value);
        ValidateSender(sender_value, binder_value);
        ValidateHeadLockedCamera(camera_lock_value, preview_value);
        ValidateOfficialRig();
        ValidatePositionOnlyEngagement();
        ValidateTriggerRelativeRotation();
        ValidateWorkspaceReengagement();

        Debug.Log("G1 teleoperation project validation passed.");
    }

    private static T FindSceneComponent<T>() where T : Component
    {
        T[] component_values = Resources.FindObjectsOfTypeAll<T>();
        foreach (T component_value in component_values)
        {
            if (component_value.gameObject.scene.IsValid()
                && component_value.gameObject.scene.isLoaded)
            {
                return component_value;
            }
        }

        return null;
    }

    private static void ValidateBinder(G1ExistingHandTargetBinder binder_value)
    {
        AssertCondition(
            binder_value.prefer_skeleton_wrist,
            "Skeleton wrist must be the position reference.");
        AssertCondition(
            binder_value.use_anatomical_hand_frame,
            "Anatomical hand frame must be enabled.");
        AssertCondition(
            !binder_value.use_palm_center,
            "Palm center must not drive wrist position.");
        AssertCondition(
            binder_value.require_alignment_to_engage,
            "Alignment hold must be required before engagement.");
        AssertCondition(
            !binder_value.require_orientation_alignment_to_engage,
            "Engagement must use wrist contact, not an absolute hand-frame orientation gate.");
        AssertCondition(
            binder_value.apply_position && binder_value.apply_rotation,
            "Position and rotation control must both be enabled.");
        AssertVector(
            binder_value.movement_scale,
            Vector3.one,
            "Operator motion scale must remain one-to-one.");
        AssertCondition(
            binder_value.target_transform != null,
            "Binder target transform is missing.");
        AssertCondition(
            binder_value.reference_transform != null,
            "Binder heading reference is missing.");
        AssertCondition(
            binder_value.tracked_wrist_max_speed_mps > 0.0f,
            "Tracked wrist outlier speed gate must be enabled.");
        AssertCondition(
            G1ExistingHandTargetBinder.IsTrackedWristStepPlausible(
                new Vector3(0.02f, 0.0f, 0.0f),
                Vector3.zero,
                0.02f,
                1.10f,
                0.020f),
            "A normal tracked wrist step was rejected.");
        AssertCondition(
            !G1ExistingHandTargetBinder.IsTrackedWristStepPlausible(
                new Vector3(0.04f, 0.0f, 0.0f),
                Vector3.zero,
                0.02f,
                1.10f,
                0.020f),
            "An implausible tracked wrist step was accepted.");
    }

    private static void ValidateSender(
        G1ExistingTargetUdpSender sender_value,
        G1ExistingHandTargetBinder binder_value)
    {
        AssertCondition(
            sender_value.hand_binder == binder_value,
            "UDP sender is not connected to the hand binder.");
        AssertCondition(
            !sender_value.disengage_on_workspace_exit,
            "Automatic workspace disengagement must remain disabled.");
        AssertCondition(
            !sender_value.use_rectangular_workspace_fallback,
            "Disabled rectangular workspace fallback must not clamp UDP targets.");
        AssertCondition(
            sender_value.disengage_on_tracking_loss,
            "Confirmed hand-tracking loss must disengage teleoperation.");
        AssertCondition(
            sender_value.tracking_loss_confirm_seconds >= 0.30f,
            "Tracking-loss disengagement debounce is too short.");
    }

    private static void ValidateOfficialRig()
    {
        GameObject prefab_value = AssetDatabase.LoadAssetAtPath<GameObject>(
            g1_prefab_path);
        AssertCondition(prefab_value != null, "Official G1 prefab is missing.");

        GameObject instance_value = PrefabUtility.InstantiatePrefab(
            prefab_value) as GameObject;
        AssertCondition(instance_value != null, "Official G1 prefab could not be instantiated.");

        try
        {
            G1OfficialRig rig_value = instance_value.GetComponent<G1OfficialRig>();
            AssertCondition(rig_value != null, "Official G1 rig component is missing.");

            Transform semantic_reference_value =
                rig_value.GetRightHandSemanticReference();
            AssertCondition(
                semantic_reference_value != null,
                "G1 semantic wrist reference is missing.");
            AssertVector(
                semantic_reference_value.localPosition,
                Vector3.zero,
                "G1 semantic wrist reference has a position offset.");
            AssertCondition(
                Quaternion.Angle(
                    semantic_reference_value.localRotation,
                    Quaternion.identity) < 0.01f,
                "G1 semantic wrist axes are not aligned with the imported wrist frame.");
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(instance_value);
        }
    }

    private static void ValidateHeadLockedCamera(
        G1HeadLockedCamera camera_lock_value,
        G1UnityRightArmPreview preview_value)
    {
        AssertCondition(
            camera_lock_value.xr_center_eye != null,
            "Head-locked camera CenterEyeAnchor reference is missing.");
        AssertCondition(
            camera_lock_value.TrackingSpace != null,
            "Head-locked camera TrackingSpace reference is missing.");
        AssertCondition(
            camera_lock_value.robot_preview == preview_value,
            "Head-locked camera is not connected to the active G1 preview.");
        AssertCondition(
            camera_lock_value.align_position_once,
            "G1 head camera must align to the robot head once at startup.");
        AssertCondition(
            !camera_lock_value.lock_position,
            "Continuous G1 head camera position lock must be disabled for VR comfort.");

        GameObject tracking_space_object = new GameObject("tracking_space_lock_test");
        GameObject camera_object = new GameObject("camera_position_lock_test");
        GameObject hand_object = new GameObject("hand_position_lock_test");
        try
        {
            Quaternion tracked_rotation = Quaternion.Euler(18.0f, 42.0f, -7.0f);
            Vector3 mount_position = new Vector3(1.2f, 1.6f, -0.4f);
            tracking_space_object.transform.SetPositionAndRotation(
                new Vector3(-0.3f, 0.2f, 0.1f),
                Quaternion.identity);
            camera_object.transform.SetParent(tracking_space_object.transform, false);
            hand_object.transform.SetParent(tracking_space_object.transform, false);
            camera_object.transform.SetLocalPositionAndRotation(
                new Vector3(0.1f, 1.6f, 0.2f),
                tracked_rotation);
            hand_object.transform.localPosition = new Vector3(0.4f, 1.2f, 0.5f);
            Vector3 hand_to_head_before = hand_object.transform.position
                - camera_object.transform.position;

            G1HeadLockedCamera.LockTrackingSpacePosition(
                tracking_space_object.transform,
                camera_object.transform,
                mount_position);

            AssertVector(
                camera_object.transform.position,
                mount_position,
                "Initial camera alignment did not adopt the G1 head position.");
            AssertCondition(
                Quaternion.Angle(camera_object.transform.rotation, tracked_rotation)
                    < 0.001f,
                "Initial camera alignment must preserve tracked HMD rotation.");
            AssertVector(
                hand_object.transform.position - camera_object.transform.position,
                hand_to_head_before,
                "Initial TrackingSpace alignment changed the hand-to-head relative position.");

            Vector3 operator_step = new Vector3(0.025f, 0.0f, 0.0f);
            Vector3 common_body_step =
                G1ExistingHandTargetBinder.GetCommonBodyTranslationStep(
                    operator_step,
                    operator_step,
                    0.0005f,
                    0.85f,
                    0.55f,
                    0.012f);
            AssertVector(
                common_body_step,
                operator_step,
                "Equal head and wrist motion was not recognized as body translation.");
            AssertVector(
                G1ExistingHandTargetBinder.CalculateBodyCompensatedTrackingDelta(
                    new Vector3(0.3f, 1.2f, 0.5f) + operator_step,
                    new Vector3(0.3f, 1.2f, 0.5f),
                    common_body_step),
                Vector3.zero,
                "Operator body translation leaked into the robot hand target frame.");
            AssertVector(
                G1ExistingHandTargetBinder.GetCommonBodyTranslationStep(
                    Vector3.zero,
                    operator_step,
                    0.0005f,
                    0.85f,
                    0.55f,
                    0.012f),
                Vector3.zero,
                "Head-only translation was incorrectly classified as body motion.");
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(tracking_space_object);
        }
    }

    private static void ValidateTriggerRelativeRotation()
    {
        Quaternion neutral_hand_rotation = Quaternion.Euler(12.0f, -18.0f, 25.0f);
        Quaternion neutral_target_rotation = Quaternion.Euler(-20.0f, 35.0f, 7.0f);
        Quaternion hand_rotation_delta =
            Quaternion.AngleAxis(15.0f, Vector3.up)
            * Quaternion.AngleAxis(-8.0f, Vector3.right);

        Quaternion current_hand_rotation =
            hand_rotation_delta * neutral_hand_rotation;
        Quaternion mapped_rotation = current_hand_rotation
            * Quaternion.Inverse(neutral_hand_rotation)
            * neutral_target_rotation;
        Quaternion expected_rotation =
            hand_rotation_delta * neutral_target_rotation;

        AssertCondition(
            Quaternion.Angle(mapped_rotation, expected_rotation) < 0.01f,
            "Trigger-relative wrist rotation changes the operator axes.");

        Quaternion engagement_rotation = neutral_hand_rotation
            * Quaternion.Inverse(neutral_hand_rotation)
            * neutral_target_rotation;
        AssertCondition(
            Quaternion.Angle(
                engagement_rotation,
                neutral_target_rotation) < 0.01f,
            "Wrist orientation jumps at engagement.");
    }

    private static void ValidatePositionOnlyEngagement()
    {
        AssertCondition(
            G1ExistingHandTargetBinder.GetAlignmentReady(
                true,
                false,
                0.03f,
                0.07f,
                95.0f,
                30.0f),
            "A wrist inside the contact radius must not be blocked by absolute hand orientation.");
        AssertCondition(
            !G1ExistingHandTargetBinder.GetAlignmentReady(
                true,
                false,
                0.08f,
                0.07f,
                0.0f,
                30.0f),
            "A wrist outside the contact radius must not engage teleoperation.");
        AssertCondition(
            !G1ExistingHandTargetBinder.GetAlignmentReady(
                true,
                true,
                0.03f,
                0.07f,
                95.0f,
                30.0f),
            "The optional orientation gate must still work when explicitly enabled.");
    }

    private static void ValidateWorkspaceReengagement()
    {
        AssertCondition(
            !G1ExistingTargetUdpSender.GetCommandValidity(true, false),
            "Temporary tracking loss must emit an idle hold command.");
        AssertCondition(
            G1ExistingTargetUdpSender.GetCommandValidity(true, true),
            "Calibrated valid tracking must emit an active command.");
        AssertCondition(
            !G1ExistingTargetUdpSender.GetCommandValidity(false, true),
            "Tracking alone must not activate an uncalibrated command.");
        AssertCondition(
            !G1ExistingTargetUdpSender.ShouldDisengageForWorkspace(
                false,
                true,
                false),
            "A stale backend workspace limit must not cancel a new engagement.");
        AssertCondition(
            G1ExistingTargetUdpSender.ShouldDisengageForWorkspace(
                true,
                false,
                false),
            "A local workspace exit must always disengage teleoperation.");
        AssertCondition(
            G1ExistingTargetUdpSender.ShouldDisengageForWorkspace(
                false,
                true,
                true),
            "A fresh backend workspace limit must disengage teleoperation.");

        AssertCondition(
            !G1ExistingTargetUdpSender.ShouldDisengageForWorkspace(
                false,
                false,
                true),
            "Tracking continuity without a workspace exit must keep teleoperation engaged.");

        float exit_duration = G1ExistingTargetUdpSender.UpdateWorkspaceExitDuration(
            true,
            0.0f,
            0.08f);
        AssertCondition(
            !G1ExistingTargetUdpSender.IsWorkspaceExitConfirmed(exit_duration, 0.20f),
            "A brief workspace excursion must not disengage teleoperation.");
        exit_duration = G1ExistingTargetUdpSender.UpdateWorkspaceExitDuration(
            false,
            exit_duration,
            0.02f);
        AssertCondition(
            Mathf.Approximately(exit_duration, 0.0f),
            "Returning inside the workspace must clear the pending exit timer.");
    }

    private static void AssertVector(
        Vector3 actual_value,
        Vector3 expected_value,
        string message_value)
    {
        AssertCondition(
            Vector3.Distance(actual_value, expected_value) < 0.0001f,
            message_value + " Actual=" + actual_value + " Expected=" + expected_value);
    }

    private static void AssertCondition(bool condition_value, string message_value)
    {
        if (!condition_value)
        {
            throw new InvalidOperationException(message_value);
        }
    }
}
