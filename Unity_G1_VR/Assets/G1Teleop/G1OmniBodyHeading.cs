using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

/// <summary>
/// Separates operator body yaw from measured G1 body yaw. The XR display follows
/// measured LowState base yaw while the hand binders recover body-relative input
/// poses without inheriting the display correction.
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
    private G1OmniHeadingState state = new G1OmniHeadingState();
    private double measured_base_degrees;
    private double previous_measured_base_yaw;
    private double applied_tracking_correction;
    private ulong measured_state_revision;
    private bool measured_base_initialized;

    public double OperatorBodyYawDegrees
        => G1OmniHeadingState.ToUnityYawDelta(state.Degrees);
    public double MeasuredRobotYawDegrees => measured_base_degrees;
    public double InputObservedBodyYawDegrees => measured_base_initialized
        ? measured_base_degrees
        : OperatorBodyYawDegrees;

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
        UpdateMeasuredBaseHeading();
        double desired_correction = measured_base_initialized
            ? G1OmniHeadingState.TrackingCorrectionDegrees(
                measured_base_degrees,
                OperatorBodyYawDegrees)
            : 0.0;
        double correction_delta = desired_correction - applied_tracking_correction;
        if (correction_delta == 0) return;
        Quaternion turn = Quaternion.AngleAxis((float)correction_delta, Vector3.up);
        Transform tracking = alignment.TrackingSpace;
        Vector3 eye = alignment.xr_center_eye.position;
        tracking.rotation = turn * tracking.rotation;
        tracking.position += eye - alignment.xr_center_eye.position;
        applied_tracking_correction = desired_correction;
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

    public Vector3 DisplayInputPosition(Vector3 correctedWorldPosition)
    {
        if (alignment == null || alignment.xr_center_eye == null)
        {
            return correctedWorldPosition;
        }
        Vector3 pivot = alignment.xr_center_eye.position;
        Quaternion display = Quaternion.AngleAxis(
            (float)InputObservedBodyYawDegrees,
            Vector3.up);
        return pivot + display * (correctedWorldPosition - pivot);
    }

    public Quaternion DisplayInputRotation(Quaternion correctedWorldRotation)
    {
        return Quaternion.AngleAxis(
            (float)InputObservedBodyYawDegrees,
            Vector3.up) * correctedWorldRotation;
    }

    private void UpdateMeasuredBaseHeading()
    {
        G1RobotStateUdpReceiver hardware = alignment == null
            || alignment.robot_preview == null
            ? null
            : alignment.robot_preview.hardware_state_receiver;
        if (hardware == null
            || !hardware.HasBasePoseState
            || hardware.StateRevision == measured_state_revision)
        {
            return;
        }

        measured_state_revision = hardware.StateRevision;
        Quaternion unity_rotation = G1UnityRightArmPreview.RobotQuaternionToUnity(
            hardware.LatestBaseRotationRobot);
        Vector3 forward = Vector3.ProjectOnPlane(
            unity_rotation * Vector3.forward,
            Vector3.up);
        if (forward.sqrMagnitude < 0.000001f)
        {
            return;
        }
        double yaw = Mathf.Atan2(forward.x, forward.z) * Mathf.Rad2Deg;
        if (!measured_base_initialized)
        {
            previous_measured_base_yaw = yaw;
            measured_base_initialized = true;
            return;
        }
        measured_base_degrees += G1OmniHeadingState.Delta(
            yaw,
            previous_measured_base_yaw);
        previous_measured_base_yaw = yaw;
    }

    private void OnDestroy()
    {
        receiver?.Close(); receiver = null;
    }
}
