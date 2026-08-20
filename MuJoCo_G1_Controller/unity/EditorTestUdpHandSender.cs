using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

public class EditorTestUdpHandSender : MonoBehaviour
{
    [Header("UDP")]
    public string host = "127.0.0.1";
    public int port = 5005;

    [Header("MuJoCo target workspace")]
    public Vector3 center = new Vector3(0.42f, -0.16f, 1.05f);
    public Vector3 amplitude = new Vector3(0.0f, 0.13f, 0.10f);
    public float speed = 1.0f;
    public float sendRateHz = 60.0f;

    UdpClient udp;
    IPEndPoint endpoint;
    float nextSendTime;

    void OnEnable()
    {
        Application.runInBackground = true;
        udp = new UdpClient();
        endpoint = new IPEndPoint(IPAddress.Parse(host), port);
        nextSendTime = 0.0f;
    }

    void OnDisable()
    {
        udp?.Close();
        udp = null;
    }

    void Update()
    {
        if (udp == null || Time.time < nextSendTime)
            return;

        nextSendTime = Time.time + 1.0f / Mathf.Max(1.0f, sendRateHz);

        float t = Time.time * speed;
        Vector3 pos = new Vector3(
            center.x + amplitude.x * Mathf.Sin(0.6f * t),
            center.y + amplitude.y * Mathf.Sin(0.8f * t),
            center.z + amplitude.z * Mathf.Sin(1.1f * t)
        );

        SendRightHandPosition(pos);
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
}
