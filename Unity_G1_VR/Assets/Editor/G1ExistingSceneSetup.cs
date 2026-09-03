using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class G1ExistingSceneSetup
{
    private const string scene_path = "Assets/Scenes/SampleScene.unity";

    [MenuItem("G1 Teleop/Setup Existing Scene")]
    public static void SetupExistingScene()
    {
        UnityEngine.SceneManagement.Scene scene_value = EditorSceneManager.OpenScene(scene_path);
        GameObject target_object = GetObjectByAnyName(
            scene_value,
            "G1_Teleoperation_System",
            "target");
        GameObject camera_rig_object = GetObjectByAnyName(
            scene_value,
            "VR_XR_Rig",
            "Quest3S_XR_Rig",
            "OVRCameraRigInteraction");
        GameObject center_eye_object = camera_rig_object == null
            ? null
            : GetChildObjectByName(camera_rig_object.transform, "CenterEyeAnchor");
        GameObject right_ovr_hand_object = camera_rig_object == null
            ? null
            : GetChildObjectByName(camera_rig_object.transform, "RightOVRHand");
        GameObject right_hand_anchor_object = camera_rig_object == null
            ? null
            : GetChildObjectByName(camera_rig_object.transform, "RightHandAnchor");

        if (target_object == null)
        {
            Debug.LogError("target object was not found in " + scene_path);
            return;
        }

        RemoveLegacyTargetComponents(target_object);

        G1ExistingTargetUdpSender sender_value = target_object.GetComponent<G1ExistingTargetUdpSender>();
        if (sender_value == null)
        {
            sender_value = target_object.AddComponent<G1ExistingTargetUdpSender>();
        }

        sender_value.right_hand_target = target_object.transform;
        sender_value.udp_host = "127.0.0.1";
        sender_value.udp_port = 5005;
        sender_value.send_hz = 60.0f;
        sender_value.robot_center = new Vector3(0.42f, -0.16f, 1.05f);
        sender_value.position_offset = Vector3.zero;
        sender_value.robot_min = new Vector3(0.28f, -0.38f, 0.82f);
        sender_value.robot_max = new Vector3(0.58f, 0.22f, 1.34f);

        G1ExistingHandTargetBinder binder_value = target_object.GetComponent<G1ExistingHandTargetBinder>();
        if (binder_value == null)
        {
            binder_value = target_object.AddComponent<G1ExistingHandTargetBinder>();
        }

        binder_value.target_transform = target_object.transform;
        binder_value.source_hand = right_hand_anchor_object == null
            ? (right_ovr_hand_object == null ? null : right_ovr_hand_object.transform)
            : right_hand_anchor_object.transform;
        binder_value.reference_transform = center_eye_object == null
            ? null
            : center_eye_object.transform;
        binder_value.ovr_hand = right_ovr_hand_object == null
            ? null
            : right_ovr_hand_object.GetComponent<OVRHand>();
        binder_value.ovr_skeleton = right_ovr_hand_object == null
            ? null
            : right_ovr_hand_object.GetComponent<OVRSkeleton>();
        binder_value.prefer_skeleton_wrist = true;
        binder_value.use_anatomical_hand_frame = true;
        // Position control must use Hand_WristRoot. A palm-center control point
        // translates in an arc during pure wrist rotation and moves the elbow.
        binder_value.use_palm_center = false;
        binder_value.require_tracked_hand = true;
        binder_value.apply_position = true;
        binder_value.apply_rotation = true;
        binder_value.auto_calibrate_on_first_track = true;
        binder_value.require_alignment_to_engage = true;
        binder_value.require_orientation_alignment_to_engage = false;
        binder_value.use_reference_yaw = true;
        binder_value.preview_neutral_offset = new Vector3(0.22f, -0.24f, 0.48f);
        binder_value.movement_scale = Vector3.one;
        binder_value.position_offset = Vector3.zero;
        binder_value.position_smoothing = 1.00f;
        binder_value.auto_calibration_delay = 0.35f;
        binder_value.engagement_distance = 0.07f;
        binder_value.engagement_orientation_tolerance_degrees = 30.0f;
        binder_value.engagement_hold_duration = 0.35f;
        binder_value.engagement_position_stability = 0.015f;
        binder_value.engagement_rotation_stability_degrees = 10.0f;
        binder_value.engagement_frame_initialization_delay = 0.25f;
        binder_value.tracked_wrist_max_speed_mps = 1.10f;
        binder_value.tracked_wrist_min_step_allowance = 0.020f;
        sender_value.hand_binder = binder_value;
        sender_value.disengage_on_tracking_loss = true;
        sender_value.tracking_loss_confirm_seconds = 0.35f;

        G1RobotStateUdpReceiver receiver_value = GetOrAddStateReceiver(
            target_object,
            5006);
        receiver_value.udp_port = 5006;
        receiver_value.state_timeout = 0.5f;
        receiver_value.expected_state_source = G1RobotStateUdpReceiver.MinkStateSource;
        receiver_value.accept_packets_without_source = true;
        G1RobotStateUdpReceiver hardware_receiver_value = GetOrAddStateReceiver(
            target_object,
            5010);
        hardware_receiver_value.udp_port = 5010;
        hardware_receiver_value.state_timeout = 0.5f;
        hardware_receiver_value.expected_state_source =
            G1RobotStateUdpReceiver.HardwareStateSource;
        hardware_receiver_value.accept_packets_without_source = false;
        sender_value.state_receiver = receiver_value;
        sender_value.disengage_on_workspace_exit = false;

        G1UnityRightArmPreview preview_value = target_object.GetComponent<G1UnityRightArmPreview>();
        if (preview_value == null)
        {
            preview_value = target_object.AddComponent<G1UnityRightArmPreview>();
        }

        preview_value.hand_binder = binder_value;
        preview_value.target_sender = sender_value;
        preview_value.state_receiver = receiver_value;
        preview_value.hardware_state_receiver = hardware_receiver_value;
        preview_value.wrist_target = target_object.transform;
        preview_value.show_tracking_markers = true;
        preview_value.show_inspection_scene = false;
        preview_value.tracking_axis_length = 0.10f;
        G1HeadLockedCamera camera_lock_value = ConfigureHeadLockedCamera(
            target_object,
            center_eye_object,
            preview_value);
        binder_value.head_camera_alignment = camera_lock_value;
        preview_value.head_camera_alignment = camera_lock_value;

        if (camera_rig_object != null)
        {
            camera_rig_object.name = "Quest3S_XR_Rig";
            camera_rig_object.transform.position = Vector3.zero;
            camera_rig_object.transform.rotation = Quaternion.identity;
            EditorUtility.SetDirty(camera_rig_object);
        }

        target_object.name = "G1_Teleoperation_System";
        RemoveLegacySceneObjects(scene_value, target_object, camera_rig_object);
        OrganizeEnvironment(scene_value);

        EditorUtility.SetDirty(target_object);
        EditorSceneManager.MarkSceneDirty(scene_value);
        EditorSceneManager.SaveScene(scene_value);
        Debug.Log("G1 existing scene setup complete.");
    }

    private static G1RobotStateUdpReceiver GetOrAddStateReceiver(
        GameObject target_object,
        int udp_port)
    {
        G1RobotStateUdpReceiver[] receiver_values =
            target_object.GetComponents<G1RobotStateUdpReceiver>();
        foreach (G1RobotStateUdpReceiver receiver_value in receiver_values)
        {
            if (receiver_value.udp_port == udp_port)
            {
                return receiver_value;
            }
        }

        return target_object.AddComponent<G1RobotStateUdpReceiver>();
    }

    [MenuItem("G1 Teleop/Setup Head-Locked Camera")]
    public static void SetupHeadLockedCamera()
    {
        UnityEngine.SceneManagement.Scene scene_value =
            EditorSceneManager.OpenScene(scene_path);
        GameObject target_object = GetObjectByAnyName(
            scene_value,
            "G1_Teleoperation_System",
            "target");
        GameObject camera_rig_object = GetObjectByAnyName(
            scene_value,
            "VR_XR_Rig",
            "Quest3S_XR_Rig",
            "OVRCameraRigInteraction");
        G1ExistingHandTargetBinder binder_value = target_object == null
            ? null
            : target_object.GetComponent<G1ExistingHandTargetBinder>();
        GameObject center_eye_object = binder_value != null
            && binder_value.reference_transform != null
            ? binder_value.reference_transform.gameObject
            : camera_rig_object == null
                ? null
                : GetChildObjectByName(
                    camera_rig_object.transform,
                    "CenterEyeAnchor");
        G1UnityRightArmPreview preview_value = target_object == null
            ? null
            : target_object.GetComponent<G1UnityRightArmPreview>();

        G1HeadLockedCamera camera_lock_value = ConfigureHeadLockedCamera(
            target_object,
            center_eye_object,
            preview_value);
        if (camera_lock_value == null)
        {
            throw new MissingReferenceException(
                "G1 head-locked camera references could not be configured.");
        }

        binder_value.head_camera_alignment = camera_lock_value;
        preview_value.head_camera_alignment = camera_lock_value;
        EditorUtility.SetDirty(binder_value);
        EditorUtility.SetDirty(preview_value);

        EditorSceneManager.MarkSceneDirty(scene_value);
        EditorSceneManager.SaveScene(scene_value);
        Debug.Log("G1 head-locked camera setup complete.");
    }

    private static G1HeadLockedCamera ConfigureHeadLockedCamera(
        GameObject target_object,
        GameObject center_eye_object,
        G1UnityRightArmPreview preview_value)
    {
        if (target_object == null
            || center_eye_object == null
            || preview_value == null)
        {
            Debug.LogError(
                "G1 head-locked camera setup requires the teleoperation system, "
                + "CenterEyeAnchor, and G1 preview.");
            return null;
        }

        G1HeadLockedCamera camera_lock_value =
            target_object.GetComponent<G1HeadLockedCamera>();
        if (camera_lock_value == null)
        {
            camera_lock_value = target_object.AddComponent<G1HeadLockedCamera>();
        }

        camera_lock_value.xr_center_eye = center_eye_object.transform;
        camera_lock_value.xr_tracking_space = center_eye_object.transform.parent;
        camera_lock_value.robot_preview = preview_value;
        camera_lock_value.align_position_once = true;
        camera_lock_value.lock_position = true;
        camera_lock_value.head_tracking_stable_duration = 0.15f;
        camera_lock_value.minimum_floor_head_height = 0.4f;
        camera_lock_value.show_head_camera_pip = true;
        camera_lock_value.head_camera_tcp_port =
            G1HeadCameraPiP.DefaultTcpPort;
        EditorUtility.SetDirty(camera_lock_value);
        return camera_lock_value;
    }

    private static GameObject GetObjectByAnyName(
        UnityEngine.SceneManagement.Scene scene_value,
        params string[] object_names)
    {
        foreach (string object_name in object_names)
        {
            GameObject object_value = GetRootObjectByName(scene_value, object_name);
            if (object_value != null)
            {
                return object_value;
            }
        }

        return null;
    }

    private static void RemoveLegacyTargetComponents(GameObject target_object)
    {
        Component[] component_values = target_object.GetComponents<Component>();
        foreach (Component component_value in component_values)
        {
            if (component_value == null)
            {
                GameObjectUtility.RemoveMonoBehavioursWithMissingScript(target_object);
                continue;
            }

            if (component_value is Transform
                || component_value is G1ExistingTargetUdpSender
                || component_value is G1ExistingHandTargetBinder
                || component_value is G1UnityRightArmPreview
                || component_value is G1RobotStateUdpReceiver
                || component_value is G1HeadLockedCamera)
            {
                continue;
            }

            Object.DestroyImmediate(component_value, true);
        }
    }

    private static void RemoveLegacySceneObjects(
        UnityEngine.SceneManagement.Scene scene_value,
        GameObject target_object,
        GameObject camera_rig_object)
    {
        string[] legacy_object_names =
        {
            "Main Camera",
            "Mobile_Box",
            "Low_Pass_Filter",
            "Communication_1",
            "haptic_test",
            "Canvas",
            "EventSystem",
            "XR Interaction Manager"
        };

        foreach (string object_name in legacy_object_names)
        {
            GameObject object_value = GetRootObjectByName(scene_value, object_name);
            if (object_value == null
                || object_value == target_object
                || object_value == camera_rig_object)
            {
                continue;
            }

            Object.DestroyImmediate(object_value, true);
        }
    }

    private static void OrganizeEnvironment(UnityEngine.SceneManagement.Scene scene_value)
    {
        GameObject environment_object = GetRootObjectByName(
            scene_value,
            "Simulation_Environment");
        if (environment_object == null)
        {
            environment_object = new GameObject("Simulation_Environment");
        }

        GameObject floor_object = GetObjectByAnyName(
            scene_value,
            "Simulation_Floor",
            "Plane");
        if (floor_object != null)
        {
            floor_object.name = "Simulation_Floor";
            floor_object.transform.SetParent(environment_object.transform, true);
        }

        GameObject light_object = GetObjectByAnyName(
            scene_value,
            "Scene_Lighting",
            "Directional Light");
        if (light_object != null)
        {
            light_object.name = "Scene_Lighting";
            light_object.transform.SetParent(environment_object.transform, true);
        }
    }

    private static GameObject GetRootObjectByName(UnityEngine.SceneManagement.Scene scene_value, string object_name)
    {
        foreach (GameObject root_object in scene_value.GetRootGameObjects())
        {
            GameObject result_object = GetChildObjectByName(root_object.transform, object_name);
            if (result_object != null)
            {
                return result_object;
            }
        }

        return null;
    }

    private static GameObject GetRootObjectByTag(UnityEngine.SceneManagement.Scene scene_value, string tag_name)
    {
        foreach (GameObject root_object in scene_value.GetRootGameObjects())
        {
            GameObject result_object = GetChildObjectByTag(root_object.transform, tag_name);
            if (result_object != null)
            {
                return result_object;
            }
        }

        return null;
    }

    private static GameObject GetChildObjectByName(Transform parent_value, string object_name)
    {
        if (parent_value.name == object_name)
        {
            return parent_value.gameObject;
        }

        for (int child_index = 0; child_index < parent_value.childCount; child_index++)
        {
            GameObject result_object = GetChildObjectByName(parent_value.GetChild(child_index), object_name);
            if (result_object != null)
            {
                return result_object;
            }
        }

        return null;
    }

    private static GameObject GetChildObjectByTag(Transform parent_value, string tag_name)
    {
        if (parent_value.CompareTag(tag_name))
        {
            return parent_value.gameObject;
        }

        for (int child_index = 0; child_index < parent_value.childCount; child_index++)
        {
            GameObject result_object = GetChildObjectByTag(parent_value.GetChild(child_index), tag_name);
            if (result_object != null)
            {
                return result_object;
            }
        }

        return null;
    }
}
