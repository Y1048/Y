using UnityEngine;

public class UdpTargetVisualizer : MonoBehaviour
{
    public EditorTestUdpHandSender sender;
    public G1HandPoseUdpSender g1Sender;
    public G1Quest3SXRHandsInput questHandsInput;
    public Camera mainCamera;
    public Transform rightHandSource;
    public Transform leftHandSource;
    public bool anchorPreviewToCamera = true;
    public Vector3 cameraPreviewOffset = new Vector3(0.0f, -0.05f, 1.15f);
    Transform targetSphere;
    Transform floorTransform;
    Transform panelTransform;
    Transform rangeTransform;
    G1GameHudOverlay gameHudOverlay;
    Vector3 unityCenter = new Vector3(0.0f, 1.2f, 2.0f);
    float visualScale = 1.15f;

    void Start()
    {
        CreateScene();
    }

    void Update()
    {
        CacheActiveReferences();
        UpdatePreviewCenter();

        if (targetSphere == null)
            return;

        Vector3 delta;
        if (g1Sender != null)
            delta = g1Sender.RightTarget - g1Sender.rightRobotCenter;
        else if (sender != null)
            delta = sender.CurrentTarget - sender.center;
        else
            return;

        Vector3 targetOffset = new Vector3(-delta.y, delta.z, delta.x) * visualScale;
        if (anchorPreviewToCamera && mainCamera != null)
        {
            AttachToCamera(targetSphere);
            targetSphere.localPosition = cameraPreviewOffset + targetOffset;
            targetSphere.localRotation = Quaternion.identity;
        }
        else
        {
            targetSphere.position = PreviewLocalToWorld(targetOffset);
        }
        UpdateSceneObjects();
    }

    void CacheActiveReferences()
    {
        if (g1Sender == null)
            g1Sender = G1HandPoseUdpSender.Active;
        if (questHandsInput == null)
            questHandsInput = G1Quest3SXRHandsInput.Active;
        if (rightHandSource == null && g1Sender != null)
            rightHandSource = g1Sender.rightHandSource;
        if (leftHandSource == null && g1Sender != null)
            leftHandSource = g1Sender.leftHandSource;
        mainCamera = ResolveRenderCamera();

        if (gameHudOverlay == null)
            CreateGameHudOverlay();
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

    void CreateScene()
    {
        if (mainCamera != null)
        {
            mainCamera.transform.position = new Vector3(0, 1.6f, -4.2f);
            mainCamera.transform.rotation = Quaternion.Euler(10, 0, 0);
        }

        GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Cube);
        floor.name = "Preview Floor";
        floor.transform.position = new Vector3(0, -0.05f, 1.8f);
        floor.transform.localScale = new Vector3(1.4f, 0.025f, 1.0f);
        floor.GetComponent<Renderer>().material.color = new Color(0.72f, 0.82f, 0.88f);
        floorTransform = floor.transform;

        GameObject panel = GameObject.CreatePrimitive(PrimitiveType.Cube);
        panel.name = "Preview Inspection Panel";
        panel.transform.position = unityCenter + new Vector3(0, 0, 0.46f);
        panel.transform.localScale = new Vector3(0.7f, 0.45f, 0.035f);
        panel.GetComponent<Renderer>().material.color = new Color(0.12f, 0.14f, 0.16f);
        panelTransform = panel.transform;

        GameObject sphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        sphere.name = "UDP Target Preview";
        sphere.transform.localScale = Vector3.one * 0.12f;
        sphere.GetComponent<Renderer>().material.color = Color.green;
        targetSphere = sphere.transform;

        GameObject path = GameObject.CreatePrimitive(PrimitiveType.Cube);
        path.name = "Target Motion Range";
        path.transform.position = unityCenter;
        path.transform.localScale = new Vector3(0.42f, 0.24f, 0.012f);
        path.GetComponent<Renderer>().material.color = new Color(0.0f, 0.6f, 0.2f, 0.25f);
        rangeTransform = path.transform;

        CacheActiveReferences();
    }

    void UpdatePreviewCenter()
    {
        if (!anchorPreviewToCamera || mainCamera == null)
            return;

        Transform cameraTransform = mainCamera.transform;
        unityCenter = cameraTransform.position
            + cameraTransform.right * cameraPreviewOffset.x
            + cameraTransform.up * cameraPreviewOffset.y
            + cameraTransform.forward * cameraPreviewOffset.z;
    }

    Vector3 PreviewLocalToWorld(Vector3 localOffset)
    {
        if (anchorPreviewToCamera && mainCamera != null)
        {
            Transform cameraTransform = mainCamera.transform;
            return unityCenter
                + cameraTransform.right * localOffset.x
                + cameraTransform.up * localOffset.y
                + cameraTransform.forward * localOffset.z;
        }

        return unityCenter + localOffset;
    }

    void UpdateSceneObjects()
    {
        if (anchorPreviewToCamera && mainCamera != null)
        {
            if (floorTransform != null)
            {
                AttachToCamera(floorTransform);
                floorTransform.localPosition = cameraPreviewOffset + new Vector3(0.0f, -0.45f, 0.0f);
                floorTransform.localRotation = Quaternion.identity;
            }

            if (panelTransform != null)
            {
                AttachToCamera(panelTransform);
                panelTransform.localPosition = cameraPreviewOffset + new Vector3(0.0f, 0.0f, 0.22f);
                panelTransform.localRotation = Quaternion.identity;
            }

            if (rangeTransform != null)
            {
                AttachToCamera(rangeTransform);
                rangeTransform.localPosition = cameraPreviewOffset;
                rangeTransform.localRotation = Quaternion.identity;
            }

            return;
        }

        if (floorTransform != null)
            floorTransform.position = unityCenter + new Vector3(0.0f, -1.25f, 0.0f);

        if (panelTransform != null)
        {
            panelTransform.position = PreviewLocalToWorld(new Vector3(0.0f, 0.0f, 0.46f));
            if (mainCamera != null)
                panelTransform.rotation = Quaternion.LookRotation(-mainCamera.transform.forward, mainCamera.transform.up);
        }

        if (rangeTransform != null)
            rangeTransform.position = unityCenter;
    }

    void AttachToCamera(Transform target)
    {
        if (target == null || mainCamera == null || target.parent == mainCamera.transform)
            return;

        target.SetParent(mainCamera.transform, false);
    }

    void CreateGameHudOverlay()
    {
        gameHudOverlay = G1GameHudOverlay.Active;
        if (gameHudOverlay != null)
        {
            gameHudOverlay.sender = g1Sender;
            gameHudOverlay.questHandsInput = questHandsInput;
            return;
        }

        GameObject overlayObject = new GameObject("G1 Game HUD Overlay");
        gameHudOverlay = overlayObject.AddComponent<G1GameHudOverlay>();
        gameHudOverlay.sender = g1Sender;
        gameHudOverlay.questHandsInput = questHandsInput;
        Debug.Log("G1 Game HUD Overlay created for Game view debugging.");
    }
}
