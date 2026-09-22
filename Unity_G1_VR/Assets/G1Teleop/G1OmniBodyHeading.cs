using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

/// <summary>
/// Robot-centred rendering follows the operator's Omni body yaw immediately.
/// The fixed-base preview remains in its robot frame while XR and surroundings
/// rotate inversely; hand input is corrected back into that same robot frame.
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
    private double applied_operator_yaw;

    public double OperatorBodyYawDegrees
        => G1OmniHeadingState.ToUnityYawDelta(state.Degrees);
    public double InputObservedBodyYawDegrees => OperatorBodyYawDegrees;

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
        double operator_delta = state.Degrees - applied_operator_yaw;
        if (operator_delta == 0) return;
        Quaternion turn = Quaternion.AngleAxis(
            (float)G1OmniHeadingState.ToUnityYawDelta(operator_delta), Vector3.up);
        Transform tracking = alignment.TrackingSpace;
        Vector3 eye = alignment.xr_center_eye.position;
        tracking.rotation = turn * tracking.rotation;
        tracking.position += eye - alignment.xr_center_eye.position;
        if (environment != null) environment.rotation = turn * environment.rotation;
        applied_operator_yaw = state.Degrees;
    }

    public Vector3 CorrectInputPosition(Vector3 displayedWorldPosition)
    {
        if (alignment == null || alignment.xr_center_eye == null)
        {
            return displayedWorldPosition;
        }
        Vector3 pivot = alignment.xr_center_eye.position;
        Quaternion correction = Quaternion.AngleAxis(
            (float)-InputObservedBodyYawDegrees,
            Vector3.up);
        return pivot + correction * (displayedWorldPosition - pivot);
    }

    public Quaternion CorrectInputRotation(Quaternion displayedWorldRotation)
    {
        return Quaternion.AngleAxis(
            (float)-InputObservedBodyYawDegrees,
            Vector3.up) * displayedWorldRotation;
    }

    private void OnDestroy()
    {
        receiver?.Close(); receiver = null;
    }
}
