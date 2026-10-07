using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;
using Newtonsoft.Json;

// Full 29-joint measured pose. Legacy class name retained; no root motion or commands.
[DefaultExecutionOrder(20000)]
public sealed class G1LowStateLegView : MonoBehaviour
{
    [Serializable] public sealed class Frame
    {
        public string schema, session;
        public long sequence;
        public double source_monotonic_s, age_s;
        public bool crc_valid;
        public string[] joint_names;
        public float[] q_rad, dq_rad_s, tau_est_nm;
    }
    public bool HasFreshState => IsFreshAt(Time.realtimeSinceStartupAsDouble);
    public Frame LatestState => latest;
    public double ReceivedAt => received;
    public long AppliedSequence { get; private set; } = -1;
    private UdpClient client;
    private G1OfficialRig rig;
    private Frame latest;
    private double received;
    private string[] names;
    private bool wasFresh;
    private readonly HashSet<string> retiredSessions = new HashSet<string>();

    private void Start()
    {
        rig = GetComponent<G1OfficialRig>();
        names = G1OfficialRig.GetFullBodyJointNames();
        try
        {
            client = new UdpClient(AddressFamily.InterNetwork);
            client.ExclusiveAddressUse = true;
            client.Client.Bind(new IPEndPoint(IPAddress.Loopback, 55073));
            client.Client.Blocking = false;
        }
        catch (SocketException error)
        {
            client?.Close(); client = null;
            Debug.LogWarning("[G1 LOWSTATE VIEW] unavailable: " + error.Message);
        }
    }

    public bool IsFreshAt(double now)
        => latest != null && !double.IsNaN(now) && !double.IsInfinity(now)
            && now >= received && now - received + latest.age_s <= 0.5;

    public static bool Valid(Frame value, string[] expected)
    {
        if (value == null || value.schema != "g1.lowstate.view.v1" || !value.crc_valid
            || string.IsNullOrEmpty(value.session) || value.session.Length > 64
            || value.sequence < 0 || value.sequence > 9007199254740991L
            || double.IsNaN(value.source_monotonic_s) || double.IsInfinity(value.source_monotonic_s)
            || value.source_monotonic_s < 0 || double.IsNaN(value.age_s) || double.IsInfinity(value.age_s)
            || value.age_s < 0 || value.age_s > 0.5
            || value.joint_names == null || value.joint_names.Length != 29
            || expected == null || expected.Length != 29) return false;
        foreach (var values in new[] { value.q_rad, value.dq_rad_s, value.tau_est_nm })
        {
            if (values == null || values.Length != 29) return false;
            foreach (float q in values) if (float.IsNaN(q) || float.IsInfinity(q)) return false;
        }
        for (int i = 0; i < 29; i++) if (value.joint_names[i] != expected[i]) return false;
        return true;
    }

    // Also used by edit-mode validation without starting a socket or robot worker.
    public bool TryAcceptFrame(Frame value, double now)
    {
        if (names == null) names = G1OfficialRig.GetFullBodyJointNames();
        if (!Valid(value, names) || double.IsNaN(now) || double.IsInfinity(now) || now < 0
            || retiredSessions.Contains(value.session)) return false;
        if (latest != null && value.session == latest.session
            && (value.sequence <= latest.sequence
                || value.source_monotonic_s <= latest.source_monotonic_s)) return false;
        if (latest != null && value.session != latest.session)
            retiredSessions.Add(latest.session);
        latest = new Frame {
            schema = value.schema, session = value.session, sequence = value.sequence,
            source_monotonic_s = value.source_monotonic_s, age_s = value.age_s,
            crc_valid = value.crc_valid, joint_names = (string[])value.joint_names.Clone(),
            q_rad = (float[])value.q_rad.Clone(), dq_rad_s = (float[])value.dq_rad_s.Clone(),
            tau_est_nm = (float[])value.tau_est_nm.Clone()
        };
        received = now;
        return true;
    }

    private void Update()
    {
        if (client == null) return;
        for (int n = 0; n < 128 && client.Available > 0; n++)
        {
            try
            {
                var peer = new IPEndPoint(IPAddress.Any, 0);
                byte[] bytes = client.Receive(ref peer);
                if (!IPAddress.IsLoopback(peer.Address) || bytes.Length > 16384) continue;
                var value = JsonConvert.DeserializeObject<Frame>(Encoding.UTF8.GetString(bytes));
                TryAcceptFrame(value, Time.realtimeSinceStartupAsDouble);
            }
            catch (JsonException) { }
            catch (SocketException) { break; }
        }
        if (HasFreshState != wasFresh)
        {
            wasFresh = HasFreshState;
            // Receipt is not proof that a renderer applied the sample.
            Debug.Log("[G1 LOWSTATE RX] " + (wasFresh ? "LIVE: 29-joint sample available"
                : "STALE: last valid sample retained"));
        }
    }

    // Only the preview chooses when this is applied, before measured wrist markers.
    public bool ApplyMeasuredPose()
    {
        if (rig == null) rig = GetComponent<G1OfficialRig>();
        if (latest == null || rig == null || !rig.ApplyAllJointPositions(names, latest.q_rad)) return false;
        AppliedSequence = latest.sequence;
        // Root/Omni frame belongs to the preview, not to joint telemetry.
        return true; // Stale input holds measured joints; never substitutes IK.
    }
    private void OnDestroy() { client?.Close(); }
}
