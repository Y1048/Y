using UnityEngine;

public class G1HandSceneVisualizer : MonoBehaviour
{
    public G1HandPoseUdpSender sender;
    public G1Quest3SXRHandsInput questHandsInput;
    public Transform rightHandSource;
    public Transform leftHandSource;
    public Camera mainCamera;
    public Vector3 robotPreviewCenter = new Vector3(0.0f, 1.2f, 2.0f);
    public float robotPreviewScale = 1.15f;
    public bool anchorPreviewToCamera = true;
    public Vector3 cameraPreviewOffset = new Vector3(0.0f, -0.05f, 1.15f);

    Transform rightRawMarker;
    Transform leftRawMarker;
    Transform robotTargetMarker;
    Transform shoulderMarker;
    Transform elbowMarker;
    Transform wristMarker;
    Transform upperArmLink;
    Transform lowerArmLink;
    Transform inspectionTool;
    Transform toolTipMarker;
    Transform panelContactMarker;
    Transform statusBoard;
    TextMesh statusText;

    void Start()
    {
        CreateSceneObjects();
    }

    void Update()
    {
        CacheCamera();
        UpdatePreviewCenter();
        UpdateRawHandMarkers();
        UpdateRobotArmPreview();
        UpdateStatusText();
    }

    void CreateSceneObjects()
    {
        CreateInstructionBoard();

        rightRawMarker = CreateSphere("right_raw_hand_marker", 0.09f, Color.red).transform;
        leftRawMarker = CreateSphere("left_raw_hand_marker", 0.09f, Color.blue).transform;
        robotTargetMarker = CreateSphere("robot_target_marker", 0.11f, Color.green).transform;
        panelContactMarker = CreateSphere("inspection_contact_point", 0.08f, new Color(0.0f, 0.9f, 1.0f)).transform;

        shoulderMarker = CreateSphere("g1_right_shoulder_preview", 0.08f, Color.white).transform;
        elbowMarker = CreateSphere("g1_right_elbow_preview", 0.07f, new Color(1.0f, 0.75f, 0.0f)).transform;
        wristMarker = CreateSphere("g1_right_wrist_preview", 0.075f, Color.green).transform;

        upperArmLink = CreateCylinder("g1_upper_arm_preview", new Color(0.9f, 0.9f, 0.9f)).transform;
        lowerArmLink = CreateCylinder("g1_lower_arm_preview", new Color(0.9f, 0.9f, 0.9f)).transform;
        inspectionTool = CreateCylinder("inspection_tool_preview", new Color(0.1f, 0.1f, 0.1f)).transform;
        toolTipMarker = CreateSphere("inspection_tool_tip", 0.045f, new Color(1.0f, 0.2f, 0.0f)).transform;

        GameObject textObject = new GameObject("g1_hand_scene_status_text");
        textObject.transform.SetParent(transform, false);
        textObject.transform.position = new Vector3(-1.35f, 2.18f, 1.55f);
        statusText = textObject.AddComponent<TextMesh>();
        statusText.anchor = TextAnchor.UpperLeft;
        statusText.alignment = TextAlignment.Left;
        statusText.characterSize = 0.026f;
        statusText.fontSize = 96;
        statusText.color = Color.black;
    }

    void CreateInstructionBoard()
    {
        GameObject board = GameObject.CreatePrimitive(PrimitiveType.Cube);
        board.name = "Unity Demo Status Board";
        board.transform.SetParent(transform, false);
        board.transform.position = new Vector3(-1.05f, 1.62f, 1.95f);
        board.transform.localScale = new Vector3(0.72f, 0.48f, 0.025f);
        board.GetComponent<Renderer>().material.color = new Color(0.92f, 0.92f, 0.82f);
        statusBoard = board.transform;
    }

    void CacheCamera()
    {
        mainCamera = ResolveRenderCamera();
    }

    Camera ResolveRenderCamera()
    {
        Camera[] cameras = Camera.allCameras;
        foreach (Camera camera in cameras)
        {
            if (camera != null && camera.enabled && camera.stereoEnabled)
                return camera;
        }

        foreach (Camera camera in cameras)
        {
            if (camera != null && camera.enabled && camera.stereoTargetEye != StereoTargetEyeMask.None)
                return camera;
        }

        if (mainCamera != null)
            return mainCamera;

        return Camera.main;
    }

    void UpdatePreviewCenter()
    {
        if (!anchorPreviewToCamera || mainCamera == null)
            return;

        robotPreviewCenter = CameraLocalToWorld(cameraPreviewOffset);
    }

    Vector3 CameraLocalToWorld(Vector3 localOffset)
    {
        Transform cameraTransform = mainCamera.transform;
        return cameraTransform.position
            + cameraTransform.right * localOffset.x
            + cameraTransform.up * localOffset.y
            + cameraTransform.forward * localOffset.z;
    }

    Vector3 PreviewLocalToWorld(Vector3 localOffset)
    {
        if (anchorPreviewToCamera && mainCamera != null)
        {
            Transform cameraTransform = mainCamera.transform;
            return robotPreviewCenter
                + cameraTransform.right * localOffset.x
                + cameraTransform.up * localOffset.y
                + cameraTransform.forward * localOffset.z;
        }

        return robotPreviewCenter + localOffset;
    }

    GameObject CreateSphere(string objectName, float radius, Color color)
    {
        GameObject sphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        sphere.name = objectName;
        sphere.transform.SetParent(transform, false);
        sphere.transform.localScale = Vector3.one * radius;
        sphere.GetComponent<Renderer>().material.color = color;
        return sphere;
    }

    GameObject CreateCylinder(string objectName, Color color)
    {
        GameObject cylinder = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        cylinder.name = objectName;
        cylinder.transform.SetParent(transform, false);
        cylinder.transform.localScale = new Vector3(0.035f, 0.5f, 0.035f);
        cylinder.GetComponent<Renderer>().material.color = color;
        return cylinder;
    }

    void UpdateRawHandMarkers()
    {
        if (rightRawMarker != null && rightHandSource != null)
        {
            rightRawMarker.position = rightHandSource.position;
            rightRawMarker.rotation = rightHandSource.rotation;
        }

        if (leftRawMarker != null && leftHandSource != null)
        {
            leftRawMarker.position = leftHandSource.position;
            leftRawMarker.rotation = leftHandSource.rotation;
        }
    }

    void UpdateRobotArmPreview()
    {
        if (sender == null)
            return;

        Vector3 robotDelta = sender.RightTarget - sender.rightRobotCenter;
        if (anchorPreviewToCamera && mainCamera != null)
        {
            UpdateCameraAnchoredRobotArmPreview(robotDelta);
            return;
        }

        Vector3 wristPosition = PreviewLocalToWorld(new Vector3(-robotDelta.y, robotDelta.z, robotDelta.x) * robotPreviewScale);
        Vector3 shoulderPosition = PreviewLocalToWorld(new Vector3(0.42f, 0.05f, -0.2f));
        Vector3 elbowHint = PreviewLocalToWorld(new Vector3(0.64f, -0.17f, -0.08f));
        Vector3 elbowPosition = GetElbowPosition(shoulderPosition, wristPosition, elbowHint, 0.42f, 0.38f);

        shoulderMarker.position = shoulderPosition;
        elbowMarker.position = elbowPosition;
        wristMarker.position = wristPosition;
        robotTargetMarker.position = wristPosition;
        panelContactMarker.position = PreviewLocalToWorld(new Vector3(0.0f, 0.0f, 0.46f));

        UpdateLink(upperArmLink, shoulderPosition, elbowPosition);
        UpdateLink(lowerArmLink, elbowPosition, wristPosition);
        UpdateInspectionTool(wristPosition, panelContactMarker.position);
    }

    void UpdateCameraAnchoredRobotArmPreview(Vector3 robotDelta)
    {
        Vector3 wristPosition = cameraPreviewOffset + new Vector3(-robotDelta.y, robotDelta.z, robotDelta.x) * robotPreviewScale;
        Vector3 shoulderPosition = cameraPreviewOffset + new Vector3(0.18f, 0.02f, -0.08f);
        Vector3 elbowHint = cameraPreviewOffset + new Vector3(0.28f, -0.08f, -0.02f);
        Vector3 elbowPosition = GetElbowPosition(shoulderPosition, wristPosition, elbowHint, 0.24f, 0.22f);
        Vector3 contactPosition = cameraPreviewOffset + new Vector3(0.0f, 0.0f, 0.22f);

        AttachToCamera(shoulderMarker);
        AttachToCamera(elbowMarker);
        AttachToCamera(wristMarker);
        AttachToCamera(robotTargetMarker);
        AttachToCamera(panelContactMarker);
        AttachToCamera(upperArmLink);
        AttachToCamera(lowerArmLink);
        AttachToCamera(inspectionTool);
        AttachToCamera(toolTipMarker);

        shoulderMarker.localPosition = shoulderPosition;
        elbowMarker.localPosition = elbowPosition;
        wristMarker.localPosition = wristPosition;
        robotTargetMarker.localPosition = wristPosition;
        panelContactMarker.localPosition = contactPosition;

        UpdateLocalLink(upperArmLink, shoulderPosition, elbowPosition);
        UpdateLocalLink(lowerArmLink, elbowPosition, wristPosition);
        UpdateLocalInspectionTool(wristPosition, contactPosition);
    }

    void UpdateInspectionTool(Vector3 wristPosition, Vector3 contactPosition)
    {
        Vector3 toolDirection = (contactPosition - wristPosition).normalized;
        if (toolDirection.sqrMagnitude < 1e-6f)
            toolDirection = Vector3.forward;

        Vector3 toolBase = wristPosition + toolDirection * 0.05f;
        Vector3 toolTip = wristPosition + toolDirection * 0.34f;
        UpdateLink(inspectionTool, toolBase, toolTip);
        toolTipMarker.position = toolTip;
    }

    void UpdateLocalInspectionTool(Vector3 wristPosition, Vector3 contactPosition)
    {
        Vector3 toolDirection = (contactPosition - wristPosition).normalized;
        if (toolDirection.sqrMagnitude < 1e-6f)
            toolDirection = Vector3.forward;

        Vector3 toolBase = wristPosition + toolDirection * 0.05f;
        Vector3 toolTip = wristPosition + toolDirection * 0.34f;
        UpdateLocalLink(inspectionTool, toolBase, toolTip);
        toolTipMarker.localPosition = toolTip;
    }

    Vector3 GetElbowPosition(Vector3 shoulderPosition, Vector3 wristPosition, Vector3 elbowHint, float upperLength, float lowerLength)
    {
        Vector3 shoulderToWrist = wristPosition - shoulderPosition;
        float distance = Mathf.Clamp(shoulderToWrist.magnitude, 0.05f, upperLength + lowerLength - 0.02f);
        Vector3 direction = shoulderToWrist.normalized;
        if (direction.sqrMagnitude < 1e-6f)
            direction = Vector3.forward;

        float along = (upperLength * upperLength - lowerLength * lowerLength + distance * distance) / (2.0f * distance);
        float height = Mathf.Sqrt(Mathf.Max(0.0f, upperLength * upperLength - along * along));
        Vector3 bendDirection = Vector3.ProjectOnPlane(elbowHint - shoulderPosition, direction).normalized;
        if (bendDirection.sqrMagnitude < 1e-6f)
            bendDirection = Vector3.down;

        return shoulderPosition + direction * along + bendDirection * height;
    }

    void UpdateLink(Transform link, Vector3 start, Vector3 end)
    {
        Vector3 center = (start + end) * 0.5f;
        Vector3 direction = end - start;
        float length = direction.magnitude;

        link.position = center;
        link.localScale = new Vector3(0.045f, length * 0.5f, 0.045f);
        if (length > 1e-6f)
            link.rotation = Quaternion.FromToRotation(Vector3.up, direction.normalized);
    }

    void UpdateLocalLink(Transform link, Vector3 start, Vector3 end)
    {
        Vector3 center = (start + end) * 0.5f;
        Vector3 direction = end - start;
        float length = direction.magnitude;

        link.localPosition = center;
        link.localScale = new Vector3(0.045f, length * 0.5f, 0.045f);
        if (length > 1e-6f)
            link.localRotation = Quaternion.FromToRotation(Vector3.up, direction.normalized);
    }

    void AttachToCamera(Transform target)
    {
        if (target == null || mainCamera == null || target.parent == mainCamera.transform)
            return;

        target.SetParent(mainCamera.transform, false);
    }

    void UpdateStatusText()
    {
        if (statusText == null || sender == null)
            return;

        string rightStatus = "Right hand: not tracked";
        if (questHandsInput != null && questHandsInput.RightTracked)
            rightStatus = "Right hand: tracked";

        Vector3 rawPosition = rightHandSource != null ? rightHandSource.position : Vector3.zero;
        Vector3 target = sender.RightTarget;
        string workspaceStatus = sender.RightWorkspaceLimited ? "LIMIT" : "OK";
        string speedStatus = sender.RightSpeedLimited ? "LIMIT" : "OK";

        if (mainCamera != null)
        {
            Vector3 boardPosition = new Vector3(-0.34f, 0.22f, 0.95f);
            if (statusBoard != null)
            {
                AttachToCamera(statusBoard);
                statusBoard.localPosition = boardPosition;
                statusBoard.localRotation = Quaternion.identity;
            }

            AttachToCamera(statusText.transform);
            statusText.transform.localPosition = boardPosition + new Vector3(-0.24f, 0.22f, -0.03f);
            statusText.transform.localRotation = Quaternion.identity;
        }

        statusText.text =
            "Unity Teleop Preview\n" +
            $"{rightStatus}\n" +
            $"Workspace: {workspaceStatus} / Speed: {speedStatus}\n" +
            $"Raw hand: {rawPosition.x:F2}, {rawPosition.y:F2}, {rawPosition.z:F2}\n" +
            $"G1 target: {target.x:F2}, {target.y:F2}, {target.z:F2}\n" +
            "Red: raw hand\n" +
            "Green: G1 wrist target\n" +
            "Orange tip: inspection tool";
    }
}
