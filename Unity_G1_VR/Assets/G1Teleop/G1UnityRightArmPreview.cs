using UnityEngine;

/// <summary>
/// 백엔드가 계산한 7개 관절값으로 Unity의 공식 G1 모델과 디버그 표식을 갱신한다.
/// 이 클래스는 결과를 보여주기만 하며, 프리뷰 위치나 표식이 UDP 목표 또는 IK 입력으로
/// 되돌아가지 않도록 제어 경로와 분리되어 있다.
/// </summary>
public class G1UnityRightArmPreview : MonoBehaviour
{
    public G1ExistingHandTargetBinder hand_binder;
    public G1ExistingTargetUdpSender target_sender;
    public G1RobotStateUdpReceiver state_receiver;
    public Transform wrist_target;
    public bool show_tracking_markers = true;
    public bool show_orientation_axes = false;
    public float tracking_axis_length = 0.10f;

    private static readonly float[] fallback_right_arm_positions =
    {
        10.0f * Mathf.Deg2Rad,
        -22.0f * Mathf.Deg2Rad,
        0.0f,
        55.0f * Mathf.Deg2Rad,
        0.0f,
        0.0f,
        0.0f
    };

    private static readonly float[] fallback_left_arm_positions =
    {
        10.0f * Mathf.Deg2Rad,
        22.0f * Mathf.Deg2Rad,
        0.0f,
        55.0f * Mathf.Deg2Rad,
        0.0f,
        0.0f,
        0.0f
    };

    private static readonly string[] left_arm_joint_names =
    {
        "left_shoulder_pitch_joint",
        "left_shoulder_roll_joint",
        "left_shoulder_yaw_joint",
        "left_elbow_joint",
        "left_wrist_roll_joint",
        "left_wrist_pitch_joint",
        "left_wrist_yaw_joint"
    };

    private Transform preview_root;
    private GameObject official_g1_object;
    private G1OfficialRig official_g1_rig;
    private Transform tracked_hand_marker;
    private Transform robot_wrist_marker;
    private Transform target_hand_marker;
    private Transform tracked_hand_axes;
    private Transform mapped_hand_axes;
    private Transform target_hand_axes;
    private Material tracked_hand_material;
    private Material robot_wrist_material;
    private Material target_hand_material;
    private Material engagement_waiting_material;
    private Material engagement_ready_material;
    private Material axis_x_material;
    private Material axis_y_material;
    private Material axis_z_material;
    private Material mapping_line_material;
    private LineRenderer mapping_line;
    private Renderer target_hand_renderer;
    private Transform inspection_panel;
    private Transform inspection_target_marker;
    private Renderer inspection_target_renderer;
    private Material inspection_panel_material;
    private Material inspection_target_material;
    private bool robot_anchored;
    private bool robot_state_pose_applied;
    private bool calibration_reference_captured;
    private bool previous_preview_calibrated;
    private Vector3 robot_wrist_at_calibration;
    private float alignment_log_timer;

    public float WristAlignmentError { get; private set; }
    public float RawHandVisualOffset { get; private set; }
    public float MuJoCoPositionError { get; private set; }
    public float UnityReplayError { get; private set; }
    public float CommandTransportError { get; private set; }
    public bool IsRobotAnchored => robot_anchored;
    public Transform HeadCameraMount => official_g1_rig == null
        ? null
        : official_g1_rig.head_camera_mount;

    private void Awake()
    {
        CreatePreview();
    }

    private void LateUpdate()
    {
        // 관절 프리뷰를 먼저 적용한 뒤 같은 프레임의 손/목표 표식을 배치해
        // 화면에 보이는 오차가 한 프레임씩 어긋나지 않게 한다.
        UpdateOfficialRobotPose();

        if (!robot_anchored
            && hand_binder != null
            && hand_binder.IsEngagementFrameLocked)
        {
            AnchorOfficialRobot();
        }

        Transform robot_position_reference = GetRobotPositionReference();
        Transform robot_orientation_reference = GetRobotOrientationReference();
        if (robot_anchored
            && hand_binder != null
            && !hand_binder.IsCalibrated
            && robot_position_reference != null
            && robot_orientation_reference != null)
        {
            hand_binder.SetEngagementTargetPose(
                robot_position_reference.position,
                robot_orientation_reference.rotation);
        }

        UpdateCalibrationReference(robot_position_reference);
        UpdateTrackingMarkers();
        UpdateInspectionDemo();
    }

    private void CreatePreview()
    {
        preview_root = new GameObject("G1_Teleop_Runtime").transform;
        preview_root.SetParent(null, false);

        GameObject prefab_value = Resources.Load<GameObject>("G1Official/G1_29DoF_Official");
        if (prefab_value == null)
        {
            Debug.LogError(
                "Official G1 prefab is missing. Run G1 Teleop/Rebuild Official G1 Model.");
        }
        else
        {
            official_g1_object = Instantiate(prefab_value, preview_root);
            official_g1_object.name = "G1_29DoF_Official";
            official_g1_rig = official_g1_object.GetComponent<G1OfficialRig>();
            ApplyFallbackPosture();
            official_g1_object.SetActive(false);
        }

        tracked_hand_material = CreateUnlitMaterial(
            "tracked_wrist_material",
            new Color(0.0f, 0.90f, 1.0f, 1.0f));
        robot_wrist_material = CreateUnlitMaterial(
            "g1_actual_wrist_material",
            new Color(1.0f, 0.18f, 0.60f, 1.0f));
        target_hand_material = CreateUnlitMaterial(
            "operator_hand_target_material",
            new Color(0.15f, 1.0f, 0.25f, 1.0f));
        engagement_waiting_material = CreateUnlitMaterial(
            "g1_engagement_waiting_material",
            Color.white);
        engagement_ready_material = CreateUnlitMaterial(
            "g1_engagement_ready_material",
            new Color(1.0f, 0.85f, 0.05f, 1.0f));
        axis_x_material = CreateUnlitMaterial(
            "wrist_axis_x_material",
            new Color(1.0f, 0.12f, 0.12f, 1.0f));
        axis_y_material = CreateUnlitMaterial(
            "wrist_axis_y_material",
            new Color(0.15f, 1.0f, 0.25f, 1.0f));
        axis_z_material = CreateUnlitMaterial(
            "wrist_axis_z_material",
            new Color(0.15f, 0.45f, 1.0f, 1.0f));
        mapping_line_material = CreateUnlitMaterial(
            "hand_mapping_line_material",
            Color.white);

        tracked_hand_marker = CreateSphere(
            "tracked_quest_wrist_marker",
            tracked_hand_material,
            Vector3.one * 0.060f);
        robot_wrist_marker = CreateSphere(
            "g1_actual_wrist_marker",
            robot_wrist_material,
            Vector3.one * 0.035f);
        target_hand_marker = CreateSphere(
            "g1_feasible_motion_target_marker",
            target_hand_material,
            Vector3.one * 0.055f);
        target_hand_renderer = target_hand_marker.GetComponent<Renderer>();
        tracked_hand_axes = CreateOrientationAxes("tracked_quest_wrist_axes");
        mapped_hand_axes = CreateOrientationAxes("mapped_quest_command_axes");
        target_hand_axes = CreateOrientationAxes("g1_feasible_motion_target_axes");
        mapping_line = CreateMappingLine();
        CreateInspectionDemoVisuals();
    }

    private void CreateInspectionDemoVisuals()
    {
        inspection_panel_material = CreateUnlitMaterial(
            "inspection_panel_material",
            new Color(0.16f, 0.18f, 0.20f, 1.0f));
        inspection_target_material = CreateUnlitMaterial(
            "inspection_demo_target_material",
            InspectionStateColor("waiting"));

        GameObject panel_object = GameObject.CreatePrimitive(PrimitiveType.Cube);
        panel_object.name = "inspection_panel";
        panel_object.transform.SetParent(preview_root, false);
        panel_object.GetComponent<Renderer>().sharedMaterial = inspection_panel_material;
        DestroyCollider(panel_object);
        inspection_panel = panel_object.transform;

        inspection_target_marker = CreateSphere(
            "inspection_demo_target_marker",
            inspection_target_material,
            Vector3.one * 0.09f);
        inspection_target_renderer = inspection_target_marker.GetComponent<Renderer>();
        inspection_panel.gameObject.SetActive(false);
        inspection_target_marker.gameObject.SetActive(false);
    }

    private void UpdateInspectionDemo()
    {
        bool visible = robot_anchored
            && official_g1_object != null
            && official_g1_rig != null
            && state_receiver != null
            && state_receiver.HasRecentState
            && state_receiver.HasInspectionState;
        inspection_panel.gameObject.SetActive(visible);
        inspection_target_marker.gameObject.SetActive(visible);
        if (!visible)
        {
            return;
        }

        Transform wrist_reference = GetRobotStateWristReference();
        if (wrist_reference == null)
        {
            return;
        }

        Quaternion robot_rotation = official_g1_object.transform.rotation;
        Vector3 wrist_robot_position = state_receiver.LatestWristRobotPosition;
        inspection_target_marker.position = wrist_reference.position
            + robot_rotation * RobotVectorToUnity(
                state_receiver.LatestInspectionTargetRobotPosition
                - wrist_robot_position);
        inspection_panel.position = wrist_reference.position
            + robot_rotation * RobotVectorToUnity(
                state_receiver.LatestInspectionPanelRobotPosition
                - wrist_robot_position);
        inspection_panel.rotation = robot_rotation;

        Vector3 panel_half_size = state_receiver.LatestInspectionPanelHalfSize;
        inspection_panel.localScale = new Vector3(
            panel_half_size.y * 2.0f,
            panel_half_size.z * 2.0f,
            panel_half_size.x * 2.0f);

        Color state_color = InspectionStateColor(
            state_receiver.LatestInspectionState);
        inspection_target_material.color = state_color;
        if (inspection_target_material.HasProperty("_BaseColor"))
        {
            inspection_target_material.SetColor("_BaseColor", state_color);
        }
        inspection_target_renderer.sharedMaterial = inspection_target_material;

        float progress_scale = state_receiver.LatestInspectionState == "holding"
            ? 1.0f + 0.35f * state_receiver.LatestInspectionHoldProgress
            : 1.0f;
        inspection_target_marker.localScale = Vector3.one * 0.09f * progress_scale;
    }

    private static Color InspectionStateColor(string state_value)
    {
        switch (state_value)
        {
            case "approach":
                return new Color(1.0f, 0.82f, 0.05f, 1.0f);
            case "holding":
                return new Color(1.0f, 0.35f, 0.05f, 1.0f);
            case "complete":
                return new Color(0.10f, 1.0f, 0.25f, 1.0f);
            default:
                return new Color(0.05f, 0.65f, 1.0f, 1.0f);
        }
    }

    private static Vector3 RobotVectorToUnity(Vector3 robot_vector)
    {
        return new Vector3(-robot_vector.y, robot_vector.z, robot_vector.x);
    }

    private void UpdateOfficialRobotPose()
    {
        if (official_g1_rig == null)
        {
            return;
        }

        bool robot_state_available = state_receiver != null
            && state_receiver.HasRecentState;

        if (robot_state_available)
        {
            official_g1_rig.ApplyRightArmJointPositions(
                state_receiver.LatestRightArmJoints);
            robot_state_pose_applied = true;
            return;
        }

        if (robot_state_pose_applied)
        {
            ApplyFallbackPosture();
            robot_state_pose_applied = false;
        }
    }

    private void AnchorOfficialRobot()
    {
        if (official_g1_object == null
            || official_g1_rig == null
            || GetRobotPositionReference() == null
            || GetRobotOrientationReference() == null
            || official_g1_rig.head_camera_mount == null)
        {
            return;
        }

        official_g1_object.SetActive(true);
        official_g1_object.transform.position = Vector3.zero;
        official_g1_object.transform.rotation = hand_binder.OperatorHeading;

        Vector3 camera_alignment_delta = hand_binder.OperatorOrigin
            - official_g1_rig.head_camera_mount.position;
        official_g1_object.transform.position += camera_alignment_delta;
        official_g1_rig.SetFirstPersonView(true);
        hand_binder.SetEngagementTargetPose(
            GetRobotPositionReference().position,
            GetRobotOrientationReference().rotation);
        robot_anchored = true;
        Debug.Log(
            "Official G1 head camera aligned to the initial HMD pose and locked in world coordinates.");
    }

    private void ApplyFallbackPosture()
    {
        if (official_g1_rig == null)
        {
            return;
        }

        official_g1_rig.ApplyRightArmJointPositions(fallback_right_arm_positions);
        for (int joint_index = 0; joint_index < left_arm_joint_names.Length; joint_index++)
        {
            official_g1_rig.ApplyJointPosition(
                left_arm_joint_names[joint_index],
                fallback_left_arm_positions[joint_index]);
        }
    }

    private void UpdateTrackingMarkers()
    {
        // cyan: 실제 Quest 손목, magenta: 백엔드가 계산한 G1 손목,
        // green: 로봇이 추종 중인 제한된 목표. 표식과 선은 진단 전용이다.
        bool target_visible = show_tracking_markers
            && hand_binder != null
            && hand_binder.IsEngagementFrameLocked;
        bool tracking_visible = target_visible && hand_binder.IsTrackingValid;
        bool command_active = hand_binder.IsCalibrated
            && target_sender != null
            && target_sender.IsCommandValid;
        bool mapping_visible = tracking_visible && command_active;

        SetTargetTrackingObjectsActive(target_visible, command_active);
        SetActualTrackingObjectsActive(tracking_visible, mapping_visible);
        if (!target_visible)
        {
            return;
        }

        Transform robot_position_reference = GetRobotPositionReference();
        Transform robot_orientation_reference = GetRobotOrientationReference();
        bool robot_reference_available = hand_binder.IsCalibrated
            && robot_position_reference != null
            && robot_orientation_reference != null;
        Vector3 robot_position = robot_reference_available
            ? robot_position_reference.position
            : hand_binder.EngagementTargetPosition;

        Vector3 command_position = command_active && target_sender != null
            ? hand_binder.EngagementTargetPosition
                + hand_binder.OperatorHeading
                * target_sender.LastOperatorTargetDelta
            : hand_binder.EngagementTargetPosition;
        Quaternion command_rotation = command_active
            ? hand_binder.MappedHandRotation
            : hand_binder.EngagementTargetRotation;

        // Blue and green are local input/command visuals, so network round-trip
        // latency cannot make the green marker trail or pass the operator hand.
        // Pink alone follows the joint state returned by MuJoCo.
        Vector3 command_target_position = command_position;

        target_hand_marker.position = command_target_position;
        target_hand_marker.rotation = command_rotation;
        target_hand_axes.position = command_target_position;
        target_hand_axes.rotation = command_rotation;
        robot_wrist_marker.position = robot_position;
        robot_wrist_marker.rotation = robot_orientation_reference == null
            ? command_rotation
            : robot_orientation_reference.rotation;

        if (tracking_visible)
        {
            Vector3 raw_hand_position = hand_binder.TrackedWristPosition;
            tracked_hand_marker.position = raw_hand_position;
            tracked_hand_marker.rotation = hand_binder.TrackedWristRotation;
            tracked_hand_axes.position = raw_hand_position;
            tracked_hand_axes.rotation = hand_binder.TrackedWristRotation;

            if (mapping_visible)
            {
                mapped_hand_axes.position = command_position;
                mapped_hand_axes.rotation = hand_binder.MappedHandRotation;
                mapping_line.startColor = Color.white;
                mapping_line.endColor = Color.white;
                mapping_line.SetPosition(0, raw_hand_position);
                mapping_line.SetPosition(1, robot_position);
            }

            WristAlignmentError = Vector3.Distance(command_position, robot_position);
            RawHandVisualOffset = Vector3.Distance(raw_hand_position, command_position);
            UpdateMotionDiagnostics(command_position);

            if (command_active)
            {
                alignment_log_timer += Time.deltaTime;
                if (alignment_log_timer >= 2.0f)
                {
                    alignment_log_timer = 0.0f;
                    LogMotionDiagnostics();
                }
            }
        }

        if (!command_active)
        {
            target_hand_renderer.sharedMaterial = hand_binder.IsAlignmentReady
                ? engagement_ready_material
                : engagement_waiting_material;
            float progress_scale = 1.0f + 0.35f * hand_binder.EngagementProgress;
            target_hand_marker.localScale = Vector3.one * 0.055f * progress_scale;
        }
        else
        {
            target_hand_renderer.sharedMaterial = target_hand_material;
            target_hand_marker.localScale = Vector3.one * 0.055f;
        }
    }

    private void SetActualTrackingObjectsActive(
        bool tracking_active,
        bool mapping_active)
    {
        tracked_hand_marker.gameObject.SetActive(tracking_active);
        tracked_hand_axes.gameObject.SetActive(show_orientation_axes && tracking_active);
        mapped_hand_axes.gameObject.SetActive(show_orientation_axes && mapping_active);
        mapping_line.gameObject.SetActive(mapping_active);
    }

    private void SetTargetTrackingObjectsActive(
        bool target_active,
        bool robot_active)
    {
        robot_wrist_marker.gameObject.SetActive(robot_active);
        target_hand_marker.gameObject.SetActive(target_active);
        target_hand_axes.gameObject.SetActive(show_orientation_axes && target_active);
    }

    private Transform GetRobotPositionReference()
    {
        return official_g1_rig == null
            ? null
            : official_g1_rig.GetRightWristPositionReference();
    }

    private Transform GetRobotOrientationReference()
    {
        return official_g1_rig == null
            ? null
            : official_g1_rig.GetRightHandSemanticReference();
    }

    private Transform GetRobotStateWristReference()
    {
        return official_g1_rig == null
            ? null
            : official_g1_rig.GetRightWristPositionReference();
    }

    private void UpdateCalibrationReference(Transform robot_position_reference)
    {
        if (hand_binder == null)
        {
            return;
        }

        bool calibrated = hand_binder.IsCalibrated;
        bool calibration_started = calibrated && !previous_preview_calibrated;
        previous_preview_calibrated = calibrated;
        if ((calibration_started || !calibration_reference_captured)
            && calibrated
            && robot_position_reference != null)
        {
            robot_wrist_at_calibration = robot_position_reference.position;
            calibration_reference_captured = true;
        }
    }

    private void UpdateMotionDiagnostics(Vector3 command_position)
    {
        if (!calibration_reference_captured
            || state_receiver == null
            || !state_receiver.HasRecentState
            || !state_receiver.HasMotionDiagnostics)
        {
            MuJoCoPositionError = 0.0f;
            UnityReplayError = 0.0f;
            CommandTransportError = 0.0f;
            return;
        }

        Transform robot_state_wrist_reference = GetRobotStateWristReference();
        if (robot_state_wrist_reference == null)
        {
            return;
        }

        Vector3 mujoco_wrist_position = robot_wrist_at_calibration
            + hand_binder.OperatorHeading * state_receiver.LatestWristOperatorDelta;
        Vector3 mujoco_target_position = robot_wrist_at_calibration
            + hand_binder.OperatorHeading * state_receiver.LatestTargetOperatorDelta;
        MuJoCoPositionError = state_receiver.LatestPositionError;
        UnityReplayError = Vector3.Distance(
            robot_state_wrist_reference.position,
            mujoco_wrist_position);
        CommandTransportError = Vector3.Distance(command_position, mujoco_target_position);
    }

    private void LogMotionDiagnostics()
    {
        bool command_active = hand_binder != null
            && hand_binder.IsCalibrated
            && target_sender != null
            && target_sender.IsCommandValid;
        string safety_value = "clear";
        if (command_active
            && state_receiver != null
            && state_receiver.IsCollisionLimited)
        {
            safety_value = "collision";
        }
        else if ((target_sender != null && target_sender.IsWorkspaceLimited)
            || (command_active
                && state_receiver != null
                && state_receiver.IsWorkspaceLimited))
        {
            safety_value = "workspace";
        }

        Debug.Log(
            "G1 wrist control="
            + (WristAlignmentError * 100.0f).ToString("F1")
            + " cm | MuJoCo IK="
            + (MuJoCoPositionError * 100.0f).ToString("F1")
            + " cm | Unity replay="
            + (UnityReplayError * 100.0f).ToString("F1")
            + " cm | command delay="
            + (CommandTransportError * 100.0f).ToString("F1")
            + " cm | raw-hand offset="
            + (RawHandVisualOffset * 100.0f).ToString("F1")
            + " cm | safety="
            + safety_value);
    }

    private Transform CreateSphere(string object_name, Material material_value, Vector3 scale_value)
    {
        GameObject object_value = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        object_value.name = object_name;
        object_value.transform.SetParent(preview_root, false);
        object_value.transform.localScale = scale_value;
        object_value.GetComponent<Renderer>().sharedMaterial = material_value;
        DestroyCollider(object_value);
        return object_value.transform;
    }

    private Transform CreateOrientationAxes(string object_name)
    {
        Transform axes_root = new GameObject(object_name).transform;
        axes_root.SetParent(preview_root, false);
        float axis_radius = Mathf.Max(0.003f, tracking_axis_length * 0.045f);
        CreateAxis("x", axes_root, axis_x_material, Vector3.right, axis_radius);
        CreateAxis("y", axes_root, axis_y_material, Vector3.up, axis_radius);
        CreateAxis("z", axes_root, axis_z_material, Vector3.forward, axis_radius);
        return axes_root;
    }

    private void CreateAxis(
        string axis_name,
        Transform axes_root,
        Material material_value,
        Vector3 axis_direction,
        float axis_radius)
    {
        GameObject axis_object = GameObject.CreatePrimitive(PrimitiveType.Cube);
        axis_object.name = axes_root.name + "_" + axis_name;
        axis_object.transform.SetParent(axes_root, false);
        axis_object.transform.localPosition = axis_direction * tracking_axis_length * 0.5f;
        axis_object.transform.localRotation = Quaternion.FromToRotation(
            Vector3.forward,
            axis_direction);
        axis_object.transform.localScale = new Vector3(
            axis_radius,
            axis_radius,
            tracking_axis_length);
        axis_object.GetComponent<Renderer>().sharedMaterial = material_value;
        DestroyCollider(axis_object);
    }

    private LineRenderer CreateMappingLine()
    {
        GameObject line_object = new GameObject("operator_to_g1_wrist_path");
        line_object.transform.SetParent(preview_root, false);
        LineRenderer line_value = line_object.AddComponent<LineRenderer>();
        line_value.positionCount = 2;
        line_value.useWorldSpace = true;
        line_value.startWidth = 0.004f;
        line_value.endWidth = 0.004f;
        line_value.sharedMaterial = mapping_line_material;
        line_value.startColor = Color.white;
        line_value.endColor = Color.white;
        return line_value;
    }

    private Material CreateUnlitMaterial(string material_name, Color color_value)
    {
        Shader shader_value = Shader.Find("Unlit/Color");
        if (shader_value == null)
        {
            shader_value = Shader.Find("Universal Render Pipeline/Unlit");
        }
        if (shader_value == null)
        {
            shader_value = Shader.Find("Standard");
        }

        Material material_value = new Material(shader_value);
        material_value.name = material_name;
        material_value.color = color_value;
        return material_value;
    }

    private static void DestroyCollider(GameObject object_value)
    {
        Collider collider_value = object_value.GetComponent<Collider>();
        if (collider_value != null)
        {
            Destroy(collider_value);
        }
    }

    private void OnDestroy()
    {
        if (preview_root != null)
        {
            Destroy(preview_root.gameObject);
        }
    }
}
