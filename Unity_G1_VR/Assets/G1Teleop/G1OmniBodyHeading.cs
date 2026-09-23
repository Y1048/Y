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
    private double originYaw;
    private Vector3 questOriginWorld;
    private Vector3 robotShoulderOriginWorld;
    public bool HasSpatialOrigin { get; private set; }
    public Vector3 QuestOriginWorld => questOriginWorld;
    public double SourceYawDegrees => state.Degrees;
    public double OriginYawDegrees => originYaw;
    public Vector3 RobotShoulderOriginWorld => robotShoulderOriginWorld;
    public bool IsAligned { get; private set; }
    public bool HasSample => !double.IsNegativeInfinity(state.LastReceipt);
    public bool IsFresh => Time.realtimeSinceStartupAsDouble - state.LastReceipt <= G1OmniHeadingState.StaleSeconds;
    public bool IsReady => IsAligned;
    public double OperatorBodyYawDegrees => IsAligned
        ? G1OmniHeadingState.ToUnityYawDelta(state.Degrees - originYaw) : 0;
    public Quaternion BaseRotation => Quaternion.AngleAxis((float)OperatorBodyYawDegrees, Vector3.up);
    public string Status => !HasSample ? "OMNI: no sample; using zero heading (arms available)"
        : !IsAligned ? "OMNI: awaiting initial HMD alignment (arms independent)"
        : IsFresh ? "OMNI: heading updated" : "OMNI: holding last heading (arms available)";

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
                state.Accept(packet.session, packet.sample, now);
            }
            catch (SocketException) { break; }
            catch (ArgumentException) { }
        }
        if (!IsAligned && HasSample && alignment != null && alignment.IsInitialAlignmentApplied)
        {
            if (alignment.xr_center_eye == null
                || alignment.robot_preview == null
                || !alignment.robot_preview.TryGetBimanualWorldFrame(
                    out _, out _, out robotShoulderOriginWorld, out _, out _))
            {
                return;
            }
            questOriginWorld = alignment.xr_center_eye.position;
            HasSpatialOrigin = true;
            originYaw = state.Degrees;
            IsAligned = true;
            Debug.Log(string.Format(
                "[OMNI ALIGNMENT] ALIGNED: displayed HMD={0}, G1 shoulder center={1}; release external hold.",
                questOriginWorld.ToString("F3"), robotShoulderOriginWorld.ToString("F3")));
        }
    }

    // The whole Quest TrackingSpace is placed once by G1HeadLockedCamera.
    // Display and IK consume the exact same world-space pose after that move.
    public Vector3 CorrectInputPosition(Vector3 value) => value;
    public Quaternion CorrectInputRotation(Quaternion value) => value;
    public Vector3 DisplayInputPosition(Vector3 value) => value;
    public Quaternion DisplayInputRotation(Quaternion value) => value;
    private void OnDestroy() { receiver?.Close(); }
}
