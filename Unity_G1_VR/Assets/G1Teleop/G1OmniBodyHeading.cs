using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

/// <summary>
/// Robot-centred rendering: rotate the environment and XR frame by inverse body yaw.
/// The fixed-base IK robot stays in its existing coordinate frame. Physical body
/// rotation is removed from tracked hands, while relative head/hand motion remains.
/// This is not measured G1 odometry and does not rotate a physical camera.
/// </summary>
[DefaultExecutionOrder(-30000)]
public sealed class G1OmniBodyHeading : MonoBehaviour
{
    [Serializable] private sealed class Packet
    {
        public string schema;
        public string session;
        public double[] sample; // sequence, producer monotonic seconds, absolute Omni yaw degrees
    }
    private UdpClient receiver;
    private G1HeadLockedCamera alignment;
    private Transform environment;
    private G1OmniHeadingState state = new G1OmniHeadingState();
    private double applied;

    public void Initialize(G1HeadLockedCamera cameraAlignment, Transform surroundings)
    {
        alignment = cameraAlignment;
        environment = surroundings;
        try
        {
            receiver = new UdpClient(AddressFamily.InterNetwork);
            receiver.ExclusiveAddressUse = true;
            receiver.Client.Bind(new IPEndPoint(IPAddress.Loopback, 55072));
            receiver.Client.Blocking = false;
        }
        catch (SocketException error)
        {
            receiver?.Close(); receiver = null;
            Debug.LogError("Omni view heading unavailable on UDP 55072: " + error.Message);
        }
    }

    private void LateUpdate()
    {
        if (receiver == null) return;
        bool ready = alignment != null && alignment.IsInitialAlignmentApplied && alignment.TrackingSpace != null;
        // Bounded drain, never wait for a device. No motion while startup alignment is pending.
        for (int i = 0; i < 128 && receiver.Available > 0; ++i)
        {
            try
            {
                IPEndPoint peer = new IPEndPoint(IPAddress.Any, 0);
                byte[] raw = receiver.Receive(ref peer);
                if (!ready || raw.Length > 1024 || !IPAddress.IsLoopback(peer.Address)) continue;
                Packet packet = JsonUtility.FromJson<Packet>(Encoding.UTF8.GetString(raw));
                if (packet == null || packet.schema != "g1.omni.unity.heading.v1") continue;
                state.Accept(packet.session, packet.sample, Time.realtimeSinceStartupAsDouble);
            }
            catch (SocketException) { break; }
            catch (ArgumentException) { /* malformed view-only packet */ }
        }
        if (!ready) return;
        float delta = (float)(state.Degrees - applied);
        if (delta == 0) return;
        // Omni positive yaw = robot left; Unity body yaw would be negative.
        // Its inverse rotates the robot-centred world/XR by positive Unity yaw.
        Quaternion turn = Quaternion.AngleAxis(delta, Vector3.up);
        Transform tracking = alignment.TrackingSpace;
        Vector3 eye = alignment.xr_center_eye.position;
        tracking.rotation = turn * tracking.rotation;
        tracking.position += eye - alignment.xr_center_eye.position;
        if (environment != null) environment.rotation = turn * environment.rotation;
        applied = state.Degrees;
    }

    private void OnDestroy()
    {
        receiver?.Close(); receiver = null;
    }
}
