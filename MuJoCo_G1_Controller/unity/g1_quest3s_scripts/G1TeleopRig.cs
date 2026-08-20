using UnityEngine;

public class G1TeleopRig : MonoBehaviour
{
    public G1HandPoseUdpSender sender;
    public G1Quest3SXRHandsInput questHandsInput;
    public UdpSenderStatusDisplay statusDisplay;
    public UdpTargetVisualizer targetVisualizer;
    public G1HandSceneVisualizer handSceneVisualizer;
    public G1VrStatusPanel vrStatusPanel;
    public G1VrFollowDebugView vrFollowDebugView;
    public G1GameHudOverlay gameHudOverlay;
    public G1VrForceVisibleOverlay vrForceVisibleOverlay;
    public G1XrHeadPoseDriver headPoseDriver;
    public Camera mainCamera;
    public Transform rightHandSource;
    public Transform leftHandSource;

    void Awake()
    {
        Application.runInBackground = true;

        rightHandSource = CreateTransformSource("right_hand_source", Vector3.zero);
        leftHandSource = CreateTransformSource("left_hand_source", new Vector3(0.0f, 0.2f, 0.0f));

        GameObject senderObject = CreateChildObject("g1_teleop_sender");
        sender = senderObject.AddComponent<G1HandPoseUdpSender>();
        statusDisplay = senderObject.AddComponent<UdpSenderStatusDisplay>();
        questHandsInput = senderObject.AddComponent<G1Quest3SXRHandsInput>();

        sender.rightHandSource = rightHandSource;
        sender.leftHandSource = leftHandSource;
        sender.questHandsInput = questHandsInput;
        sender.inputMode = G1HandPoseUdpSender.InputMode.TransformSources;
        ApplyDefaultMapping();

        statusDisplay.g1Sender = sender;
        statusDisplay.questHandsInput = questHandsInput;

        gameHudOverlay = G1GameHudOverlay.Active;
        if (gameHudOverlay == null)
            gameHudOverlay = senderObject.AddComponent<G1GameHudOverlay>();

        gameHudOverlay.sender = sender;
        gameHudOverlay.questHandsInput = questHandsInput;

        vrForceVisibleOverlay = senderObject.AddComponent<G1VrForceVisibleOverlay>();
        vrForceVisibleOverlay.sender = sender;
        vrForceVisibleOverlay.questHandsInput = questHandsInput;

        questHandsInput.rightPalmTarget = rightHandSource;
        questHandsInput.leftPalmTarget = leftHandSource;

        GameObject visualizerObject = CreateChildObject("g1_target_visualizer");
        targetVisualizer = visualizerObject.AddComponent<UdpTargetVisualizer>();
        targetVisualizer.g1Sender = sender;
        targetVisualizer.questHandsInput = questHandsInput;
        targetVisualizer.rightHandSource = rightHandSource;
        targetVisualizer.leftHandSource = leftHandSource;

        GameObject handSceneObject = CreateChildObject("g1_hand_scene_visualizer");
        handSceneVisualizer = handSceneObject.AddComponent<G1HandSceneVisualizer>();
        handSceneVisualizer.sender = sender;
        handSceneVisualizer.questHandsInput = questHandsInput;
        handSceneVisualizer.rightHandSource = rightHandSource;
        handSceneVisualizer.leftHandSource = leftHandSource;

        mainCamera = Camera.main;
        if (mainCamera != null)
        {
            headPoseDriver = mainCamera.GetComponent<G1XrHeadPoseDriver>();
            if (headPoseDriver == null)
                headPoseDriver = mainCamera.gameObject.AddComponent<G1XrHeadPoseDriver>();

            targetVisualizer.mainCamera = mainCamera;
            handSceneVisualizer.mainCamera = mainCamera;
        }

        GameObject panelObject = CreateChildObject("g1_vr_status_panel");
        vrStatusPanel = panelObject.AddComponent<G1VrStatusPanel>();
        vrStatusPanel.sender = sender;
        vrStatusPanel.questHandsInput = questHandsInput;
        if (mainCamera != null)
        {
            vrStatusPanel.cameraTransform = mainCamera.transform;
            vrStatusPanel.enabled = false;
        }

        Debug.Log("G1 teleop rig initialized through getcomponent_list.");
    }

    Transform CreateTransformSource(string objectName, Vector3 localPosition)
    {
        GameObject sourceObject = CreateChildObject(objectName);
        sourceObject.transform.localPosition = localPosition;
        return sourceObject.transform;
    }

    GameObject CreateChildObject(string objectName)
    {
        GameObject childObject = new GameObject(objectName);
        childObject.transform.SetParent(transform, false);
        return childObject;
    }

    void ApplyDefaultMapping()
    {
        sender.rightRobotCenter = new Vector3(0.42f, -0.16f, 1.05f);
        sender.handToRobotScale = new Vector3(1.00f, 0.80f, 1.10f);
        sender.positionAlpha = 0.25f;
        sender.rotationAlpha = 0.25f;
        sender.maxTargetSpeed = 0.30f;
        sender.trackingHoldSeconds = 0.80f;
        sender.trackingTimeoutSeconds = 0.60f;
        sender.workspaceExitConfirmSeconds = 0.80f;
        sender.minTarget = new Vector3(0.22f, -0.50f, 0.70f);
        sender.maxTarget = new Vector3(0.70f, 0.30f, 1.50f);

        sender.forwardAxis = G1HandPoseUdpSender.MappingAxis.Z;
        sender.rightAxis = G1HandPoseUdpSender.MappingAxis.X;
        sender.upAxis = G1HandPoseUdpSender.MappingAxis.Y;

        sender.invertForward = false;
        sender.invertRight = true;
        sender.invertUp = false;
    }
}
