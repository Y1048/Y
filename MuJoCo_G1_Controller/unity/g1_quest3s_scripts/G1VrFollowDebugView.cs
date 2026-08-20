using UnityEngine;

public class G1VrFollowDebugView : MonoBehaviour
{
    public G1HandPoseUdpSender sender;
    public G1Quest3SXRHandsInput questHandsInput;
    public Vector3 localPosition = new Vector3(0.0f, -0.18f, 1.4f);

    Transform board;
    Transform rightHandMarker;
    Transform robotTargetMarker;
    Transform shoulderMarker;
    Transform elbowMarker;
    Transform upperArmLink;
    Transform lowerArmLink;
    TextMesh statusText;

    void Start()
    {
        CreateObjects();
    }

    void LateUpdate()
    {
        transform.localPosition = localPosition;
        transform.localRotation = Quaternion.identity;
        UpdatePreview();
    }

    void CreateObjects()
    {
        board = CreateCube("VR Follow Board", new Vector3(0.0f, 0.0f, 0.0f), new Vector3(1.25f, 0.72f, 0.08f), Color.yellow).transform;
        rightHandMarker = CreateSphere("VR Raw Right Marker", new Vector3(-0.34f, -0.1f, -0.12f), 0.08f, Color.red).transform;
        robotTargetMarker = CreateSphere("VR G1 Target Marker", new Vector3(0.36f, -0.1f, -0.12f), 0.09f, Color.green).transform;
        shoulderMarker = CreateSphere("VR G1 Shoulder Marker", new Vector3(0.08f, -0.1f, -0.12f), 0.06f, Color.white).transform;
        elbowMarker = CreateSphere("VR G1 Elbow Marker", new Vector3(0.22f, -0.24f, -0.12f), 0.06f, Color.magenta).transform;
        upperArmLink = CreateCylinder("VR G1 Upper Arm", Color.white).transform;
        lowerArmLink = CreateCylinder("VR G1 Lower Arm", Color.white).transform;

        GameObject textObject = new GameObject("VR Follow Status Text");
        textObject.transform.SetParent(transform, false);
        textObject.transform.localPosition = new Vector3(-0.56f, 0.28f, -0.18f);
        textObject.transform.localRotation = Quaternion.identity;
        statusText = textObject.AddComponent<TextMesh>();
        statusText.anchor = TextAnchor.UpperLeft;
        statusText.alignment = TextAlignment.Left;
        statusText.characterSize = 0.035f;
        statusText.fontSize = 96;
        statusText.color = Color.black;
        statusText.text = "VR DEBUG\nred: hand\ngreen: target";

        Debug.Log("G1 VR follow debug view created under Main Camera.");
    }

    GameObject CreateCube(string objectName, Vector3 localPositionValue, Vector3 localScaleValue, Color color)
    {
        GameObject cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
        cube.name = objectName;
        cube.transform.SetParent(transform, false);
        cube.transform.localPosition = localPositionValue;
        cube.transform.localScale = localScaleValue;
        cube.GetComponent<Renderer>().material.color = color;
        return cube;
    }

    GameObject CreateSphere(string objectName, Vector3 localPositionValue, float radius, Color color)
    {
        GameObject sphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        sphere.name = objectName;
        sphere.transform.SetParent(transform, false);
        sphere.transform.localPosition = localPositionValue;
        sphere.transform.localScale = Vector3.one * radius;
        sphere.GetComponent<Renderer>().material.color = color;
        return sphere;
    }

    GameObject CreateCylinder(string objectName, Color color)
    {
        GameObject cylinder = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        cylinder.name = objectName;
        cylinder.transform.SetParent(transform, false);
        cylinder.transform.localScale = new Vector3(0.018f, 0.1f, 0.018f);
        cylinder.GetComponent<Renderer>().material.color = color;
        return cylinder;
    }

    void UpdatePreview()
    {
        if (sender == null)
            sender = G1HandPoseUdpSender.Active;
        if (questHandsInput == null)
            questHandsInput = G1Quest3SXRHandsInput.Active;
        if (sender == null)
            return;

        Vector3 handDelta = sender.RightHandDelta;
        Vector3 robotDelta = sender.RightTarget - sender.rightRobotCenter;

        rightHandMarker.localPosition = new Vector3(-0.34f + handDelta.x * 0.35f, -0.1f + handDelta.y * 0.35f, -0.12f + handDelta.z * 0.35f);

        Vector3 targetPosition = new Vector3(0.36f - robotDelta.y * 0.8f, -0.1f + robotDelta.z * 0.8f, -0.12f + robotDelta.x * 0.8f);
        Vector3 shoulderPosition = new Vector3(0.08f, -0.1f, -0.12f);
        Vector3 elbowPosition = Vector3.Lerp(shoulderPosition, targetPosition, 0.5f) + new Vector3(0.0f, -0.14f, 0.0f);

        robotTargetMarker.localPosition = targetPosition;
        shoulderMarker.localPosition = shoulderPosition;
        elbowMarker.localPosition = elbowPosition;
        UpdateLink(upperArmLink, shoulderPosition, elbowPosition);
        UpdateLink(lowerArmLink, elbowPosition, targetPosition);

        if (statusText != null)
        {
            string handStatus = questHandsInput != null && questHandsInput.RightTracked ? "tracked" : "not tracked";
            statusText.text =
                "VR DEBUG\n" +
                $"right: {handStatus}\n" +
                $"hand {handDelta.x:F2} {handDelta.y:F2} {handDelta.z:F2}\n" +
                $"target {sender.RightTarget.x:F2} {sender.RightTarget.y:F2} {sender.RightTarget.z:F2}";
        }
    }

    void UpdateLink(Transform link, Vector3 start, Vector3 end)
    {
        Vector3 direction = end - start;
        float length = direction.magnitude;
        link.localPosition = (start + end) * 0.5f;
        link.localScale = new Vector3(0.018f, length * 0.5f, 0.018f);
        if (length > 1e-6f)
            link.localRotation = Quaternion.FromToRotation(Vector3.up, direction.normalized);
    }
}
