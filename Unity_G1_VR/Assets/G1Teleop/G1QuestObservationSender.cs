using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

// Dedicated APK input experiment. No IK, motor commands, or existing teleop ports.
[DefaultExecutionOrder(1000)]
public sealed class G1QuestObservationSender : MonoBehaviour
{
    public const int Port = 55100;
    public OVRCameraRig rig;
    public OVRHand leftHand, rightHand;
    public OVRSkeleton leftSkeleton, rightSkeleton;
    private UdpClient socket;
    private IPEndPoint pc;
    private readonly string session = Guid.NewGuid().ToString("N");
    private readonly Dictionary<string, IPEndPoint> offers = new Dictionary<string, IPEndPoint>();
    private string nonce;
    private double nextProbe, offerDeadline, lastAck, nextSend;
    private long sequence;
    private long lastAckSequence = -1;
    private string status = "Discovering PC observation receiver";
    public string Status => status;

    [Serializable] public class Pose { public float[] position_m, quaternion_xyzw; }
    [Serializable] public class Hand
    {
        public bool tracked, high_confidence, pinch;
        public Pose wrist, index_base, middle_base, pinky_base;
    }
    [Serializable] public class Packet
    {
        public string schema = "g1.quest.raw_input.v1";
        public bool observation_only = true;
        public string session_id, clock_source = "quest_unity_realtime_since_startup";
        public string frame = "unity_tracking_origin_lh_xright_yup_zforward";
        public long sequence;
        public double source_time_s;
        public int send_hz = 60;
        public bool focused, head_tracked;
        public Pose head;
        public Hand left, right;
    }
    [Serializable] private class Message
    {
        public string schema, nonce, receiver_id, session_id;
        public long sequence;
    }

    private void Start()
    {
        socket = new UdpClient(0);
        socket.EnableBroadcast = true;
        socket.Client.Blocking = false;
        BeginDiscovery();
    }
    private void BeginDiscovery()
    {
        pc = null;
        offers.Clear();
        nonce = Guid.NewGuid().ToString("N");
        nextProbe = Time.realtimeSinceStartupAsDouble;
        offerDeadline = nextProbe + 1.5;
    }
    private void LateUpdate()
    {
        if (socket == null || rig == null) return;
        double now = Time.realtimeSinceStartupAsDouble;
        try
        {
            for (int i = 0; i < 16 && socket.Available > 0; i++)
            {
                IPEndPoint peer = new IPEndPoint(IPAddress.Any, 0);
                byte[] raw = socket.Receive(ref peer);
                if (raw.Length > 2048 || peer.Port != Port) continue;
                Message reply = JsonUtility.FromJson<Message>(Encoding.UTF8.GetString(raw));
                if (reply == null) continue;
                if (pc == null && reply.schema == "g1.quest.observation.offer.v1"
                    && reply.nonce == nonce && !string.IsNullOrEmpty(reply.receiver_id))
                    offers[peer.Address.ToString()] = peer;
                if (pc != null && peer.Equals(pc) && reply.schema == "g1.quest.observation.ack.v1"
                    && reply.session_id == session && reply.sequence > lastAckSequence && reply.sequence < sequence) {
                    lastAck = now; lastAckSequence = reply.sequence;
                }
            }
            if (pc == null)
            {
                if (now < offerDeadline && now >= nextProbe)
                {
                    Send(new Message { schema = "g1.quest.observation.discover.v1", nonce = nonce },
                        new IPEndPoint(IPAddress.Broadcast, Port));
                    nextProbe = now + .4;
                }
                if (now >= offerDeadline)
                {
                    if (offers.Count == 1)
                    {
                        foreach (IPEndPoint offer in offers.Values) pc = offer;
                        lastAck = now;
                        nextSend = now;
                    }
                    else
                    {
                        status = offers.Count > 1 ? "Multiple PC receivers: close extra receivers" : "No PC receiver: same LAN/Wi-Fi required";
                        if (now > offerDeadline + 2) BeginDiscovery();
                    }
                }
                return;
            }
            if (now - lastAck > 3) { status = "PC ACK lost; rediscovering"; BeginDiscovery(); return; }
            if (now < nextSend) return;
            // At most one sample per rendered frame; never burst catch-up samples.
            nextSend += 1.0 / 60;
            if (nextSend <= now) nextSend = now + 1.0 / 60;
            bool headTracked = OVRPlugin.GetNodePositionTracked(OVRPlugin.Node.Head)
                && OVRPlugin.GetNodeOrientationTracked(OVRPlugin.Node.Head);
            var packet = new Packet {
                session_id = session, sequence = sequence++, source_time_s = now,
                focused = OVRManager.hasInputFocus, head_tracked = headTracked,
                head = headTracked ? ReadPose(rig.centerEyeAnchor) : null,
                left = ReadHand(leftHand, leftSkeleton), right = ReadHand(rightHand, rightSkeleton)
            };
            Send(packet, pc);
            status = $"OBSERVATION ONLY | PC {pc.Address}\nL tracked={packet.left.tracked} R tracked={packet.right.tracked}\nseq={packet.sequence} ACK age={now-lastAck:F2}s\nNo G1 output. Index pinch is recorded only.";
        }
        catch (SocketException error)
        {
            status = "Network unavailable: " + error.SocketErrorCode;
        }
    }
    private void Send(object packet, IPEndPoint peer)
    {
        byte[] bytes = Encoding.UTF8.GetBytes(JsonUtility.ToJson(packet));
        socket.Send(bytes, bytes.Length, peer);
    }
    private Pose ReadPose(Transform value)
    {
        Vector3 p = rig.trackingSpace.InverseTransformPoint(value.position);
        Quaternion q = Quaternion.Inverse(rig.trackingSpace.rotation) * value.rotation;
        return new Pose { position_m = new[] { p.x, p.y, p.z }, quaternion_xyzw = new[] { q.x, q.y, q.z, q.w } };
    }
    private Transform Bone(OVRSkeleton skeleton, G1HandSkeletonMapping.Joint joint)
    {
        if (skeleton == null || skeleton.Bones == null) return null;
        OVRSkeleton.BoneId wanted = G1HandSkeletonMapping.Bone(skeleton.GetSkeletonType(), joint);
        if (wanted == OVRSkeleton.BoneId.Invalid) return null;
        foreach (OVRBone bone in skeleton.Bones)
            if (bone != null && bone.Id == wanted) return bone.Transform;
        return null;
    }
    private Hand ReadHand(OVRHand hand, OVRSkeleton skeleton)
    {
        Transform wrist = Bone(skeleton, G1HandSkeletonMapping.Joint.Wrist);
        Transform index = Bone(skeleton, G1HandSkeletonMapping.Joint.IndexBase);
        Transform middle = Bone(skeleton, G1HandSkeletonMapping.Joint.MiddleBase);
        Transform pinky = Bone(skeleton, G1HandSkeletonMapping.Joint.PinkyBase);
        bool valid = hand != null && hand.IsTracked && wrist != null
            && index != null && middle != null && pinky != null;
        var result = new Hand {
            tracked = valid, high_confidence = valid && hand.IsDataHighConfidence,
            pinch = valid && hand.GetFingerIsPinching(OVRHand.HandFinger.Index)
        };
        if (valid) {
            result.wrist = ReadPose(wrist); result.index_base = ReadPose(index);
            result.middle_base = ReadPose(middle); result.pinky_base = ReadPose(pinky);
        }
        return result;
    }
    private void OnDestroy() { socket?.Close(); socket = null; }
}
