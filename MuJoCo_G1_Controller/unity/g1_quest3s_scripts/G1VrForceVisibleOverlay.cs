using System.Collections.Generic;
using UnityEngine;

public class G1VrForceVisibleOverlay : MonoBehaviour
{
    public G1HandPoseUdpSender sender;
    public G1Quest3SXRHandsInput questHandsInput;
    public Vector3 localPosition = new Vector3(0.0f, 0.0f, 0.85f);
    public Vector3 panelScale = new Vector3(0.7f, 0.32f, 0.02f);

    readonly Dictionary<Camera, Transform> panelTable = new Dictionary<Camera, Transform>();
    readonly Dictionary<Camera, TextMesh> textTable = new Dictionary<Camera, TextMesh>();

    void LateUpdate()
    {
        if (sender == null)
            sender = G1HandPoseUdpSender.Active;
        if (questHandsInput == null)
            questHandsInput = G1Quest3SXRHandsInput.Active;

        Camera[] cameras = Camera.allCameras;
        foreach (Camera camera in cameras)
        {
            if (camera == null || !camera.enabled)
                continue;

            EnsureCameraOverlay(camera);
            UpdateCameraOverlay(camera);
        }
    }

    void EnsureCameraOverlay(Camera camera)
    {
        if (!panelTable.ContainsKey(camera))
        {
            GameObject panelObject = GameObject.CreatePrimitive(PrimitiveType.Cube);
            panelObject.name = "G1 VR Force Visible Panel";
            panelObject.transform.SetParent(camera.transform, false);
            panelObject.transform.localScale = panelScale;
            panelObject.GetComponent<Renderer>().material.color = new Color(1.0f, 0.9f, 0.05f);
            panelTable[camera] = panelObject.transform;
        }

        if (!textTable.ContainsKey(camera))
        {
            GameObject textObject = new GameObject("G1 VR Force Visible Text");
            textObject.transform.SetParent(camera.transform, false);
            TextMesh textMesh = textObject.AddComponent<TextMesh>();
            textMesh.anchor = TextAnchor.MiddleCenter;
            textMesh.alignment = TextAlignment.Center;
            textMesh.characterSize = 0.035f;
            textMesh.fontSize = 96;
            textMesh.color = Color.black;
            textTable[camera] = textMesh;
        }
    }

    void UpdateCameraOverlay(Camera camera)
    {
        Transform panel = panelTable[camera];
        TextMesh textMesh = textTable[camera];

        panel.localPosition = localPosition;
        panel.localRotation = Quaternion.identity;
        panel.localScale = panelScale;

        textMesh.transform.localPosition = localPosition + new Vector3(0.0f, 0.0f, -0.025f);
        textMesh.transform.localRotation = Quaternion.identity;

        string trackingStatus = questHandsInput != null && questHandsInput.RightTracked ? "TRACKED" : "NOT TRACKED";
        string senderStatus = sender != null ? $"{sender.RightTarget.x:F2}, {sender.RightTarget.y:F2}, {sender.RightTarget.z:F2}" : "no sender";
        textMesh.text = $"VR TEST PANEL\n{camera.name}\nRight: {trackingStatus}\nTarget: {senderStatus}";
    }
}
