using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

/// <summary>One Play-time Omni origin; never rotates the Quest tracking space.</summary>
[DefaultExecutionOrder(-30000)]
public sealed class G1OmniBodyHeading : MonoBehaviour
{
    [Serializable] private sealed class Packet
    {
        public string schema, session;
        public double[] sample;
    }
    private UdpClient receiver;
    private G1HeadLockedCamera alignment;
    private G1OmniHeadingState state = new G1OmniHeadingState();
    private string sourceSession;
    private double stableSince = double.NegativeInfinity, stableYaw, originYaw;
    private double sourceStamp;
    private bool faulted;
    public bool IsAligned { get; private set; }
    public bool HasStableSample => !faulted && IsFresh &&
        Time.realtimeSinceStartupAsDouble - stableSince >= 1.0;
    public bool IsFresh => Time.realtimeSinceStartupAsDouble - state.LastReceipt <= G1OmniHeadingState.StaleSeconds;
    public bool IsReady => IsAligned && IsFresh && !faulted;
    public double OperatorBodyYawDegrees => IsAligned
        ? G1OmniHeadingState.ToUnityYawDelta(state.Degrees - originYaw) : 0;
    public Quaternion BaseRotation => Quaternion.AngleAxis((float)OperatorBodyYawDegrees, Vector3.up);
    public string Status => faulted ? "OMNI LOST: restart Play and align again"
        : IsReady ? "ALIGNED: release external hold; align hands to engage"
        : "ALIGNING: hold still, face forward, keep external hold pressed";

    public void Initialize(G1HeadLockedCamera cameraAlignment)
    {
        alignment = cameraAlignment;
        try
        {
            receiver = new UdpClient(AddressFamily.InterNetwork);
            receiver.ExclusiveAddressUse = true;
            receiver.Client.Bind(new IPEndPoint(IPAddress.Loopback, 55072));
            receiver.Client.Blocking = false;
        }
        catch (SocketException error) { receiver?.Close(); receiver = null; Debug.LogError(error.Message); }
    }

    private void LateUpdate()
    {
        double now = Time.realtimeSinceStartupAsDouble;
        if (IsAligned && !IsFresh) faulted = true;
        if (receiver == null) return;
        for (int i = 0; i < 128 && receiver.Available > 0; ++i)
        {
            try
            {
                IPEndPoint peer = new IPEndPoint(IPAddress.Any, 0);
                byte[] raw = receiver.Receive(ref peer);
                if (raw.Length > 1024 || !IPAddress.IsLoopback(peer.Address)) continue;
                var packet = JsonUtility.FromJson<Packet>(Encoding.UTF8.GetString(raw));
                if (packet == null || packet.schema != "g1.omni.unity.heading.v1") continue;
                double previousReceipt = state.LastReceipt;
                if (!state.Accept(packet.session, packet.sample, now)) continue;
                bool discontinuity = sourceSession != packet.session ||
                    now - previousReceipt > G1OmniHeadingState.StaleSeconds ||
                    packet.sample[1] - sourceStamp > G1OmniHeadingState.StaleSeconds;
                if (IsAligned && discontinuity) faulted = true;
                sourceSession = packet.session;
                sourceStamp = packet.sample[1];
                if (discontinuity || Math.Abs(state.Degrees - stableYaw) > 2)
                { stableSince = now; stableYaw = state.Degrees; }
            }
            catch (SocketException) { break; }
            catch (ArgumentException) { }
        }
        if (!IsAligned && HasStableSample && alignment != null && alignment.IsInitialAlignmentApplied)
        {
            originYaw = state.Degrees;
            IsAligned = true;
            Debug.Log("[OMNI ALIGNMENT] ALIGNED: release external hold. This button is not electronically observed.");
        }
    }

    // Input and display now share the same once-aligned world coordinates.
    public Vector3 CorrectInputPosition(Vector3 value) => value;
    public Quaternion CorrectInputRotation(Quaternion value) => value;
    public Vector3 DisplayInputPosition(Vector3 value) => value;
    public Quaternion DisplayInputRotation(Quaternion value) => value;
    private void OnDestroy() { receiver?.Close(); }
}
