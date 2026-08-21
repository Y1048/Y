using UnityEngine;

/// <summary>
/// Runtime-only diagnostics for the Quest hand -> operator frame -> UDP target chain.
/// The component installs itself automatically in Play mode and never modifies
/// teleoperation state; it only reads public binder/sender diagnostics.
/// </summary>
public sealed class G1HandUdpDiagnostics : MonoBehaviour
{
    private const float LogIntervalSeconds = 0.50f;

    private G1ExistingHandTargetBinder binder;
    private G1ExistingTargetUdpSender sender;
    private float logTimer;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        if (FindObjectOfType<G1HandUdpDiagnostics>() != null)
        {
            return;
        }

        GameObject diagnosticsObject = new GameObject("G1HandUdpDiagnostics");
        DontDestroyOnLoad(diagnosticsObject);
        diagnosticsObject.AddComponent<G1HandUdpDiagnostics>();
    }

    private void Update()
    {
        if (binder == null)
        {
            binder = FindObjectOfType<G1ExistingHandTargetBinder>();
        }
        if (sender == null)
        {
            sender = FindObjectOfType<G1ExistingTargetUdpSender>();
        }

        logTimer += Time.unscaledDeltaTime;
        if (logTimer < LogIntervalSeconds)
        {
            return;
        }
        logTimer = 0.0f;

        if (binder == null)
        {
            Debug.Log("G1 INPUT DIAG binder=missing");
            return;
        }

        Vector3 worldDelta = binder.TrackedWristPosition - binder.CalibratedWristPosition;
        Vector3 localDelta = Quaternion.Inverse(binder.OperatorHeading) * worldDelta;
        Vector3 scaledDelta = Vector3.Scale(localDelta, binder.movement_scale);
        Vector3 operatorDelta = binder.OperatorTargetDelta;
        Vector3 previewPosition = binder.target_transform == null
            ? Vector3.zero
            : binder.target_transform.position;

        string senderText;
        if (sender == null)
        {
            senderText = " sender=missing";
        }
        else
        {
            Vector3 udpUnclamped = sender.UnclampedRobotTarget;
            Vector3 udpSent = sender.LastRobotTarget;
            senderText =
                " udp_unclamped=" + udpUnclamped.ToString("F3")
                + " udp_last_sent=" + udpSent.ToString("F3")
                + " udp_valid=" + sender.IsCommandValid;
        }

        string wristSource = binder.IsUsingSkeletonWrist ? "skeleton_wrist" : "source_hand";
        Debug.Log(
            "G1 INPUT DIAG"
            + " active=" + binder.IsCalibrated
            + " tracked=" + binder.IsTrackingValid
            + " wrist_source=" + wristSource
            + " wrist_world=" + binder.TrackedWristPosition.ToString("F3")
            + " neutral_world=" + binder.CalibratedWristPosition.ToString("F3")
            + " world_delta=" + worldDelta.ToString("F3")
            + " head_local_delta=" + localDelta.ToString("F3")
            + " movement_scale=" + binder.movement_scale.ToString("F3")
            + " scaled_delta=" + scaledDelta.ToString("F3")
            + " operator_delta=" + operatorDelta.ToString("F3")
            + " preview_world=" + previewPosition.ToString("F3")
            + senderText);
    }
}
