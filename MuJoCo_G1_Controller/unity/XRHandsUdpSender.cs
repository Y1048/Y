using System.Collections.Generic;
using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;
using UnityEngine.XR.Hands;
using UnityEngine.XR.Management;

public class XRHandsUdpSender : MonoBehaviour
{
    [Header("UDP")]
    public string host = "127.0.0.1";
    public int port = 5005;
    public float sendRateHz = 60.0f;

    [Header("MuJoCo workspace")]
    public Vector3 mujocoCenter = new Vector3(0.42f, -0.16f, 1.05f);
    public float motionScale = 0.45f;
    public Vector3 minTarget = new Vector3(0.28f, -0.38f, 0.82f);
    public Vector3 maxTarget = new Vector3(0.58f, 0.22f, 1.34f);

    [Header("Filtering")]
    [Range(0.01f, 1.0f)]
    public float smoothing = 0.15f;

    UdpClient udp;
    IPEndPoint endpoint;
    XRHandSubsystem handSubsystem;
    Vector3? initialRightPalm;
    Vector3 filteredTarget;
    float nextSendTime;

    void OnEnable()
    {
        Application.runInBackground = true;
        udp = new UdpClient();
        endpoint = new IPEndPoint(IPAddress.Parse(host), port);
        filteredTarget = mujocoCenter;
        nextSendTime = 0.0f;
    }

    void OnDisable()
    {
        udp?.Close();
        udp = null;
    }

    void Update()
    {
        if (Time.time < nextSendTime)
            return;

        nextSendTime = Time.time + 1.0f / Mathf.Max(1.0f, sendRateHz);

        if (handSubsystem == null)
            handSubsystem = TryGetHandSubsystem();

        if (handSubsystem == null || !handSubsystem.running)
            return;

        XRHand rightHand = handSubsystem.rightHand;
        if (!rightHand.isTracked)
            return;

        XRHandJoint palm = rightHand.GetJoint(XRHandJointID.Palm);
        if (!palm.TryGetPose(out Pose palmPose))
            return;

        Vector3 palmPos = palmPose.position;

        if (!initialRightPalm.HasValue)
            initialRightPalm = palmPos;

        Vector3 delta = palmPos - initialRightPalm.Value;

        // Practical first-pass mapping:
        // Unity x: right, y: up, z: forward
        // MuJoCo target: x fixed near panel, y horizontal sweep, z vertical sweep
        Vector3 rawTarget = new Vector3(
            mujocoCenter.x + motionScale * delta.z,
            mujocoCenter.y - motionScale * delta.x,
            mujocoCenter.z + motionScale * delta.y
        );

        rawTarget = ClampVector(rawTarget, minTarget, maxTarget);
        filteredTarget = Vector3.Lerp(filteredTarget, rawTarget, smoothing);

        SendRightHandPosition(filteredTarget);
    }

    XRHandSubsystem TryGetHandSubsystem()
    {
        XRGeneralSettings settings = XRGeneralSettings.Instance;
        if (settings == null || settings.Manager == null || settings.Manager.activeLoader == null)
            return null;

        var subsystems = new List<XRHandSubsystem>();
        settings.Manager.activeLoader.GetLoadedSubsystems(subsystems);
        return subsystems.Count > 0 ? subsystems[0] : null;
    }

    static Vector3 ClampVector(Vector3 value, Vector3 min, Vector3 max)
    {
        return new Vector3(
            Mathf.Clamp(value.x, min.x, max.x),
            Mathf.Clamp(value.y, min.y, max.y),
            Mathf.Clamp(value.z, min.z, max.z)
        );
    }

    void SendRightHandPosition(Vector3 pos)
    {
        string json = string.Format(
            CultureInfo.InvariantCulture,
            "{{\"right\":{{\"pos\":[{0:F5},{1:F5},{2:F5}]}}}}",
            pos.x, pos.y, pos.z
        );

        byte[] bytes = Encoding.UTF8.GetBytes(json);
        udp.Send(bytes, bytes.Length, endpoint);
    }

    [ContextMenu("Reset Hand Origin")]
    public void ResetHandOrigin()
    {
        initialRightPalm = null;
        filteredTarget = mujocoCenter;
    }
}
