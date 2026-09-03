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
        ValidateStateReceivers(sender_value, preview_value);
        AssertCondition(
            !preview_value.show_inspection_scene,
            "Inspection panel visuals must remain hidden by default.");
        ValidateBaseCoordinateMapping();
        ValidateHeadLockedCamera(camera_lock_value, preview_value);
        ValidateHeadCameraPiP();
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
            AssertCondition(
                !rig_value.show_inspection_tool,
                "Inspection tool visual must remain hidden by default.");

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

            string[] full_body_joint_names = G1OfficialRig.GetFullBodyJointNames();
            float[] full_body_joint_positions = new float[full_body_joint_names.Length];
            AssertCondition(
                full_body_joint_names.Length == 29
                    && rig_value.ApplyAllJointPositions(
                        full_body_joint_names,
                        full_body_joint_positions),
                "G1 rig does not accept the canonical 29-joint state contract.");
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(instance_value);
        }
    }

    private static void ValidateStateReceivers(
        G1ExistingTargetUdpSender sender_value,
        G1UnityRightArmPreview preview_value)
    {
        G1RobotStateUdpReceiver simulation_receiver = preview_value.state_receiver;
        G1RobotStateUdpReceiver hardware_receiver =
            preview_value.hardware_state_receiver;
        AssertCondition(
            simulation_receiver != null,
            "Mink simulation state receiver is missing.");
        AssertCondition(
            hardware_receiver != null,
            "Read-only G1 hardware state receiver is missing.");
        AssertCondition(
            simulation_receiver != hardware_receiver,
            "Simulation and hardware state must use separate receivers.");
        AssertCondition(
            simulation_receiver.udp_port == 5006
                && simulation_receiver.expected_state_source
                    == G1RobotStateUdpReceiver.MinkStateSource,
            "Mink simulation state receiver contract is invalid.");
        AssertCondition(
            hardware_receiver.udp_port == 5010
                && hardware_receiver.expected_state_source
                    == G1RobotStateUdpReceiver.HardwareStateSource
                && !hardware_receiver.accept_packets_without_source,
            "Read-only G1 hardware state receiver contract is invalid.");
        AssertCondition(
            sender_value.state_receiver == simulation_receiver,
            "Target sender safety feedback must remain on the Mink receiver.");
    }

    private static void ValidateBaseCoordinateMapping()
    {
        AssertVector(
            G1UnityRightArmPreview.RobotVectorToUnity(
                new Vector3(1.0f, 2.0f, 3.0f)),
            new Vector3(-2.0f, 3.0f, 1.0f),
            "G1 base position axis conversion is invalid.");

        Quaternion unity_identity =
            G1UnityRightArmPreview.RobotQuaternionToUnity(
                Quaternion.identity);
        AssertCondition(
            Quaternion.Angle(unity_identity, Quaternion.identity) < 0.001f,
            "Identity G1 base rotation did not map to Unity identity.");

        Quaternion robot_yaw_left = Quaternion.AngleAxis(
            90.0f,
            Vector3.forward);
        Quaternion unity_yaw_left =
            G1UnityRightArmPreview.RobotQuaternionToUnity(robot_yaw_left);
        AssertVector(
            unity_yaw_left * Vector3.forward,
            Vector3.left,
            "Positive G1 yaw did not rotate the Unity robot toward its left.");
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
            preview_value.head_camera_alignment == camera_lock_value,
            "G1 preview must wait for the validated initial head pose.");
        AssertCondition(
            preview_value.hand_binder != null
                && preview_value.hand_binder.head_camera_alignment
                    == camera_lock_value,
            "Engagement frame must wait for the validated initial head pose.");
        AssertCondition(
            camera_lock_value.align_position_once,
            "G1 head camera must align to the robot head once at startup.");
        AssertCondition(
            camera_lock_value.lock_position,
            "G1 head camera position must continuously follow the robot head mount.");
        AssertCondition(
            camera_lock_value.head_tracking_stable_duration >= 0.1f
                && camera_lock_value.head_tracking_stable_duration <= 0.5f,
            "Initial G1 head alignment must wait for stable XR tracking.");
        AssertCondition(
            camera_lock_value.minimum_floor_head_height >= 0.3f
                && camera_lock_value.minimum_floor_head_height <= 0.6f,
            "Initial G1 head alignment must reject an uninitialized floor-space pose.");
        AssertCondition(
            camera_lock_value.show_head_camera_pip,
            "G1 head-camera PiP must be enabled for the operator view.");
        AssertCondition(
            camera_lock_value.head_camera_tcp_port
                == G1HeadCameraPiP.DefaultTcpPort,
            "G1 head-camera PiP must use the local read-only bridge port.");
        AssertCondition(
            G1HeadLockedCamera.IsTrackedHeadPoseValid(true, true, true, true)
                && !G1HeadLockedCamera.IsTrackedHeadPoseValid(false, true, true, true)
                && !G1HeadLockedCamera.IsTrackedHeadPoseValid(true, false, true, true)
                && !G1HeadLockedCamera.IsTrackedHeadPoseValid(true, true, false, true)
                && !G1HeadLockedCamera.IsTrackedHeadPoseValid(true, true, true, false),
            "Initial G1 head alignment must require a fully tracked and valid HMD pose.");
        AssertCondition(
            G1HeadLockedCamera.IsTrackedHeadTransformReady(
                new Vector3(0.0f, 1.1f, 0.0f),
                0.4f)
                && !G1HeadLockedCamera.IsTrackedHeadTransformReady(
                    Vector3.zero,
                    0.4f)
                && !G1HeadLockedCamera.IsTrackedHeadTransformReady(
                    new Vector3(0.0f, float.NaN, 0.0f),
                    0.4f),
            "Initial G1 head alignment must wait for the tracked pose to reach CenterEyeAnchor.");

        GameObject tracking_space_object = new GameObject("tracking_space_lock_test");
        GameObject camera_object = new GameObject("camera_position_lock_test");
        GameObject hand_object = new GameObject("hand_position_lock_test");
        GameObject head_mount_object = new GameObject("g1_head_mount_lock_test");
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
            head_mount_object.transform.SetPositionAndRotation(
                mount_position,
                Quaternion.Euler(0.0f, -35.0f, 0.0f));
            Quaternion camera_local_rotation_before = camera_object.transform.localRotation;
            Vector3 local_hand_to_head_before =
                tracking_space_object.transform.InverseTransformVector(
                    hand_object.transform.position - camera_object.transform.position);

            float yaw_correction = G1HeadLockedCamera.AlignTrackingSpaceToHeadMount(
                tracking_space_object.transform,
                camera_object.transform,
                head_mount_object.transform,
                out Vector3 position_correction);

            AssertVector(
                camera_object.transform.position,
                mount_position,
                "Initial camera alignment did not adopt the G1 head position.");
            AssertCondition(
                Vector3.Angle(
                    Vector3.ProjectOnPlane(
                        camera_object.transform.forward,
                        Vector3.up),
                    Vector3.ProjectOnPlane(
                        head_mount_object.transform.forward,
                        Vector3.up))
                    < 0.001f,
                "Initial camera alignment did not adopt the G1 horizontal heading.");
            AssertCondition(
                Quaternion.Angle(
                    camera_object.transform.localRotation,
                    camera_local_rotation_before) < 0.001f,
                "TrackingSpace alignment changed the local tracked HMD rotation.");
            AssertVector(
                tracking_space_object.transform.InverseTransformVector(
                    hand_object.transform.position - camera_object.transform.position),
                local_hand_to_head_before,
                "Initial TrackingSpace alignment changed the hand-to-head relative position.");
            AssertCondition(
                Mathf.Abs(yaw_correction) > 1.0f
                    && position_correction.sqrMagnitude > 0.0001f,
                "Initial TrackingSpace alignment did not exercise yaw and position correction.");

            Quaternion camera_rotation_before_follow =
                camera_object.transform.rotation;
            head_mount_object.transform.position +=
                new Vector3(0.2f, 0.1f, -0.15f);
            G1HeadLockedCamera.LockTrackingSpacePosition(
                tracking_space_object.transform,
                camera_object.transform,
                head_mount_object.transform.position);
            AssertVector(
                camera_object.transform.position,
                head_mount_object.transform.position,
                "Continuous camera following did not adopt the moved G1 head position.");
            AssertCondition(
                Quaternion.Angle(
                    camera_object.transform.rotation,
                    camera_rotation_before_follow) < 0.001f,
                "Continuous G1 head position following changed the tracked HMD rotation.");

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
            UnityEngine.Object.DestroyImmediate(head_mount_object);
        }
    }

    private static void ValidateHeadCameraPiP()
    {
        GameObject camera_object = new GameObject(
            "g1_head_camera_pip_validation",
            typeof(Camera));
        try
        {
            G1HeadCameraPiP pip_value = G1HeadCameraPiP.Create(
                camera_object.transform,
                G1HeadCameraPiP.DefaultTcpPort);
            AssertCondition(
                pip_value != null,
                "G1 head-camera PiP could not be created.");
            AssertCondition(
                pip_value.transform.parent == camera_object.transform,
                "G1 head-camera PiP is not view-locked to CenterEyeAnchor.");
            AssertCondition(
                pip_value.video_image != null
                    && pip_value.status_indicator != null,
                "G1 head-camera PiP visual components are missing.");
            AssertCondition(
                pip_value.GetComponent<Canvas>() != null
                    && pip_value.GetComponent<Canvas>().renderMode
                        == RenderMode.WorldSpace,
                "G1 head-camera PiP must use a world-space canvas.");
            AssertCondition(
                G1HeadCameraPiP.IsValidLoopbackPort(
                    G1HeadCameraPiP.DefaultTcpPort)
                    && !G1HeadCameraPiP.IsValidLoopbackPort(0)
                    && !G1HeadCameraPiP.IsValidLoopbackPort(65536),
                "G1 head-camera PiP TCP port guard is invalid.");

            byte[] frame_header = new byte[G1HeadCameraPiP.FrameHeaderSize];
            frame_header[0] = (byte)'G';
            frame_header[1] = (byte)'1';
            frame_header[2] = (byte)'C';
            frame_header[3] = (byte)'M';
            frame_header[7] = 1;
            frame_header[11] = 7;
            frame_header[19] = 9;
            frame_header[22] = 4;
            AssertCondition(
                G1HeadCameraPiP.TryParseFrameHeader(
                    frame_header,
                    out uint sequence,
                    out ulong timestamp_ns,
                    out int payload_size)
                    && sequence == 7
                    && timestamp_ns == 9
                    && payload_size == 1024,
                "G1 head-camera PiP frame-header parser is invalid.");
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(camera_object);
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
