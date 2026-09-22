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
    private Vector3 questOriginWorld;
    private Vector3 robotShoulderOriginWorld;
    public bool HasSpatialOrigin { get; private set; }
    public Vector3 QuestOriginWorld => questOriginWorld;
    public Vector3 RobotShoulderOriginWorld => robotShoulderOriginWorld;
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
                "[OMNI ALIGNMENT] ALIGNED: HMD origin={0} -> G1 shoulder center={1}; release external hold.",
                questOriginWorld.ToString("F3"), robotShoulderOriginWorld.ToString("F3")));
        }
    }

    // One direct world transform: the Play-time HMD origin maps to the current
    // G1 shoulder center. The rotating IK base interprets this world target.
    public static Vector3 MapWorldPosition(
        Vector3 quest_world_position,
        Vector3 quest_origin_world,
        Vector3 robot_shoulder_center_world)
        => robot_shoulder_center_world + (quest_world_position - quest_origin_world);

    public Vector3 CorrectInputPosition(Vector3 value)
    {
        if (!HasSpatialOrigin || alignment == null || alignment.robot_preview == null)
        {
            return value;
        }
        Vector3 shoulder = robotShoulderOriginWorld;
        alignment.robot_preview.TryGetBimanualWorldFrame(
            out _, out _, out shoulder, out _, out _);
        return MapWorldPosition(value, questOriginWorld, shoulder);
    }
    public Quaternion CorrectInputRotation(Quaternion value) => value;
    public Vector3 DisplayInputPosition(Vector3 value) => value;
    public Quaternion DisplayInputRotation(Quaternion value) => value;
    private void OnDestroy() { receiver?.Close(); }
}
