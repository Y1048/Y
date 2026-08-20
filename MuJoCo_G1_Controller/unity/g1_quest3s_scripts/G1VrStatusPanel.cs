using UnityEngine;

public class G1VrStatusPanel : MonoBehaviour
{
    public Vector3 localPosition = new Vector3(0.0f, 0.0f, 0.75f);
    public Vector2 panelSize = new Vector2(1.15f, 0.64f);
    public G1HandPoseUdpSender sender;
    public G1Quest3SXRHandsInput questHandsInput;
    public Transform cameraTransform;

    TextMesh frontText;
    TextMesh backText;

    void Start()
    {
        CreateWorldPanel();
        Debug.Log("G1 VR status panel created and attached to headset camera.");
    }

    void LateUpdate()
    {
        AttachToCamera();
        UpdateText();
    }

    void AttachToCamera()
    {
        if (cameraTransform == null)
            return;

        if (transform.parent != cameraTransform)
            transform.SetParent(cameraTransform, false);

        transform.localPosition = localPosition;
        transform.localRotation = Quaternion.identity;
        transform.localScale = Vector3.one;
    }

    void CreateWorldPanel()
    {
        CreateBackground("G1_VR_Status_Background_Front", 0.001f, Quaternion.identity);
        CreateBackground("G1_VR_Status_Background_Back", -0.001f, Quaternion.Euler(0.0f, 180.0f, 0.0f));

        frontText = CreateText("G1_VR_Status_Text_Front", 0.006f, Quaternion.identity);
        backText = CreateText("G1_VR_Status_Text_Back", -0.006f, Quaternion.Euler(0.0f, 180.0f, 0.0f));
    }

    void CreateBackground(string objectName, float zOffset, Quaternion localRotation)
    {
        GameObject backgroundObject = GameObject.CreatePrimitive(PrimitiveType.Quad);
        backgroundObject.name = objectName;
        backgroundObject.transform.SetParent(transform, false);
        backgroundObject.transform.localPosition = new Vector3(0.0f, 0.0f, zOffset);
        backgroundObject.transform.localRotation = localRotation;
        backgroundObject.transform.localScale = new Vector3(panelSize.x, panelSize.y, 1.0f);

        Renderer renderer = backgroundObject.GetComponent<Renderer>();
        Shader shader = Shader.Find("Unlit/Color");
        if (shader == null)
            shader = Shader.Find("Standard");
        renderer.material = new Material(shader);
        renderer.material.color = new Color(0.0f, 0.13f, 0.18f, 1.0f);
    }

    TextMesh CreateText(string objectName, float zOffset, Quaternion localRotation)
    {
        GameObject textObject = new GameObject(objectName);
        textObject.transform.SetParent(transform, false);
        textObject.transform.localPosition = new Vector3(-panelSize.x * 0.46f, panelSize.y * 0.38f, zOffset);
        textObject.transform.localRotation = localRotation;

        TextMesh textMesh = textObject.AddComponent<TextMesh>();
        textMesh.anchor = TextAnchor.UpperLeft;
        textMesh.alignment = TextAlignment.Left;
        textMesh.characterSize = 0.030f;
        textMesh.fontSize = 96;
        textMesh.color = new Color(0.7f, 1.0f, 0.45f, 1.0f);
        return textMesh;
    }

    void UpdateText()
    {
        if (sender == null)
            return;

        string status = BuildStatusText();
        if (frontText != null)
            frontText.text = status;
        if (backText != null)
            backText.text = status;
    }

    string BuildStatusText()
    {
        string subsystemStatus = "XR Hands OFF";
        string rightStatus = "Right not tracked";
        string lastSeenStatus = "last right: never";
        if (questHandsInput != null)
        {
            subsystemStatus = questHandsInput.SubsystemRunning ? "XR Hands ON" : "XR Hands OFF";
            rightStatus = questHandsInput.RightTracked ? "Right tracked" : "Right not tracked";
            if (questHandsInput.LastRightTrackedTime > 0.0f)
                lastSeenStatus = $"last right: {Time.time - questHandsInput.LastRightTrackedTime:F1}s ago";
        }

        Vector3 target = sender.RightTarget;
        Vector3 handDelta = sender.RightHandDelta;
        Vector3 robotDelta = sender.RightRobotDelta;
        Vector3 scale = sender.handToRobotScale;

        return
            "G1 VR HUD VISIBLE\n" +
            "G1 TELEOP STATUS\n" +
            $"Mode: {sender.inputMode}\n" +
            $"{subsystemStatus} | {rightStatus}\n" +
            $"{lastSeenStatus}\n" +
            $"UDP sent: {sender.SentCount}\n" +
            $"Target: {target.x:F2}, {target.y:F2}, {target.z:F2}\n" +
            $"Hand d: {handDelta.x:F2}, {handDelta.y:F2}, {handDelta.z:F2}\n" +
            $"Robot d: {robotDelta.x:F2}, {robotDelta.y:F2}, {robotDelta.z:F2}\n" +
            $"Scale F/H/V: {scale.x:F2}, {scale.y:F2}, {scale.z:F2}\n" +
            $"Flip F/R/U: {sender.invertForward}, {sender.invertRight}, {sender.invertUp}\n" +
            $"Up axis: {sender.upAxis}\n" +
            "Keys: C Calib | O/P/I Flip | U Up | [ ] V";
    }
}
