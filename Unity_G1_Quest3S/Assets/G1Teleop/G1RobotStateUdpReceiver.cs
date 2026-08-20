using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

public class G1RobotStateUdpReceiver : MonoBehaviour
{
    [Serializable]
    private class RightArmState
    {
        public float[] joints;
        public bool active;
        public float[] wrist_delta;
        public float[] target_delta;
        public float position_error;
        public bool workspace_limited;
        public bool collision_limited;
    }

    [Serializable]
    private class RobotStatePacket
    {
        public RightArmState right_arm;
        public double timestamp;
    }

    public int udp_port = 5006;
    public float state_timeout = 0.5f;

    public bool HasRecentState
    {
        get
        {
            return latest_right_arm_joints != null
                && Time.realtimeSinceStartup - latest_packet_time <= state_timeout;
        }
    }

    public bool IsTeleoperationActive { get; private set; }
    public float[] LatestRightArmJoints => latest_right_arm_joints;
    public Vector3 LatestWristOperatorDelta { get; private set; }
    public Vector3 LatestTargetOperatorDelta { get; private set; }
    public float LatestPositionError { get; private set; }
    public bool IsWorkspaceLimited { get; private set; }
    public bool IsCollisionLimited { get; private set; }
    public bool HasMotionDiagnostics { get; private set; }
    public ulong StateRevision { get; private set; }

    private UdpClient udp_client;
    private IPEndPoint receive_endpoint;
    private float[] latest_right_arm_joints;
    private float latest_packet_time = float.NegativeInfinity;
    private bool state_timed_out = true;

    private void OnEnable()
    {
        OpenSocket();
    }

    private void Update()
    {
        if (udp_client == null)
        {
            return;
        }

        try
        {
            while (udp_client.Available > 0)
            {
                byte[] packet_data = udp_client.Receive(ref receive_endpoint);
                RobotStatePacket packet_value = JsonUtility.FromJson<RobotStatePacket>(
                    Encoding.UTF8.GetString(packet_data));
                if (packet_value == null
                    || packet_value.right_arm == null
                    || packet_value.right_arm.joints == null
                    || packet_value.right_arm.joints.Length < 7)
                {
                    continue;
                }

                latest_right_arm_joints = packet_value.right_arm.joints;
                IsTeleoperationActive = packet_value.right_arm.active;
                LatestPositionError = packet_value.right_arm.position_error;
                IsWorkspaceLimited = packet_value.right_arm.workspace_limited;
                IsCollisionLimited = packet_value.right_arm.collision_limited;
                HasMotionDiagnostics = HasVector(packet_value.right_arm.wrist_delta)
                    && HasVector(packet_value.right_arm.target_delta);
                if (HasMotionDiagnostics)
                {
                    LatestWristOperatorDelta = RobotToOperatorDelta(
                        packet_value.right_arm.wrist_delta);
                    LatestTargetOperatorDelta = RobotToOperatorDelta(
                        packet_value.right_arm.target_delta);
                }
                else
                {
                    LatestWristOperatorDelta = Vector3.zero;
                    LatestTargetOperatorDelta = Vector3.zero;
                }

                latest_packet_time = Time.realtimeSinceStartup;
                state_timed_out = false;
                StateRevision++;
            }
        }
        catch (SocketException exception_value)
        {
            if (exception_value.SocketErrorCode != SocketError.WouldBlock)
            {
                Debug.LogWarning("G1 robot-state UDP receive failed: " + exception_value.Message);
            }
        }
        catch (ObjectDisposedException)
        {
        }

        if (!state_timed_out
            && Time.realtimeSinceStartup - latest_packet_time > state_timeout)
        {
            ResetRuntimeState(false);
            state_timed_out = true;
        }
    }

    private void OnDisable()
    {
        CloseSocket();
    }

    private void OnDestroy()
    {
        CloseSocket();
    }

    private void OpenSocket()
    {
        CloseSocket();

        try
        {
            udp_client = new UdpClient();
            udp_client.Client.SetSocketOption(
                SocketOptionLevel.Socket,
                SocketOptionName.ReuseAddress,
                true);
            udp_client.Client.Bind(new IPEndPoint(IPAddress.Any, udp_port));
            udp_client.Client.Blocking = false;
            receive_endpoint = new IPEndPoint(IPAddress.Any, 0);
            Debug.Log("G1 robot-state UDP listening on port " + udp_port + ".");
        }
        catch (SocketException exception_value)
        {
            Debug.LogError("Could not open G1 robot-state UDP port "
                + udp_port + ": " + exception_value.Message);
            CloseSocket();
        }
    }

    private void CloseSocket()
    {
        if (udp_client != null)
        {
            udp_client.Close();
            udp_client = null;
        }

        ResetRuntimeState(true);
        StateRevision = 0;
        state_timed_out = true;
    }

    private void ResetRuntimeState(bool clear_joint_state)
    {
        IsTeleoperationActive = false;
        LatestWristOperatorDelta = Vector3.zero;
        LatestTargetOperatorDelta = Vector3.zero;
        LatestPositionError = 0.0f;
        IsWorkspaceLimited = false;
        IsCollisionLimited = false;
        HasMotionDiagnostics = false;

        if (clear_joint_state)
        {
            latest_right_arm_joints = null;
            latest_packet_time = float.NegativeInfinity;
        }
    }

    private static bool HasVector(float[] vector_value)
    {
        return vector_value != null && vector_value.Length >= 3;
    }

    private static Vector3 RobotToOperatorDelta(float[] robot_delta)
    {
        // MuJoCo G1: +X forward, +Y left, +Z up.
        // Unity operator: +X right, +Y up, +Z forward.
        return new Vector3(
            -robot_delta[1],
            robot_delta[2],
            robot_delta[0]);
    }
}
