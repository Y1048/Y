using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;
using Newtonsoft.Json;

// Read-only overlay: only legs 0..11. No root motion or robot commands.
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
    public bool HasFreshState => latest != null && Time.realtimeSinceStartup - received <= 0.5f;
    public Frame LatestState => latest;
    private UdpClient client;
    private G1OfficialRig rig;
    private Frame latest;
    private float received;
    private string[] names;
    private bool wasFresh;
    private Vector3 fixedPosition;
    private void Start()
    {
        rig = GetComponent<G1OfficialRig>();
        names = G1OfficialRig.GetFullBodyJointNames();
        fixedPosition = transform.localPosition;
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
    public static bool Valid(Frame value, string[] expected)
    {
        if (value == null || value.schema != "g1.lowstate.view.v1" || !value.crc_valid
            || string.IsNullOrEmpty(value.session) || value.session.Length > 64
            || value.sequence < 0 || value.sequence > 9007199254740991L
            || double.IsNaN(value.source_monotonic_s) || double.IsInfinity(value.source_monotonic_s)
            || value.source_monotonic_s < 0 || double.IsNaN(value.age_s)
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
    private void LateUpdate()
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
                if (!Valid(value, names)) continue;
                if (latest != null && value.session == latest.session
                    && (value.sequence <= latest.sequence || value.source_monotonic_s <= latest.source_monotonic_s)) continue;
                latest = value; received = Time.realtimeSinceStartup;
            }
            catch (JsonException) { }
            catch (SocketException) { break; }
        }
        if (latest != null && rig != null)
        {
            for (int i = 0; i < 12; i++) rig.ApplyJointPosition(names[i] + "_joint", latest.q_rad[i]);
            transform.localPosition = fixedPosition;
        }
        if (HasFreshState != wasFresh)
        {
            wasFresh = HasFreshState;
            Debug.Log("[G1 LOWSTATE VIEW] " + (wasFresh ? "LIVE: measured legs, IK arms, fixed position" : "STALE: holding last measured legs"));
        }
    }
    private void OnDestroy() { client?.Close(); }
}
