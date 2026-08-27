using UnityEngine;

/// <summary>
/// Quest 손 -> 작업자 기준 프레임 -> UDP 목표 경로를 기록하는 실행 중 진단기다.
/// Play 모드에서 자동 설치되며 공개된 binder/sender 상태만 읽고 제어 상태는 변경하지 않는다.
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
            + " head_world=" + binder.TrackedHeadPosition.ToString("F3")
            + " neutral_world=" + binder.CalibratedWristPosition.ToString("F3")
            + " neutral_head_world=" + binder.CalibratedHeadPosition.ToString("F3")
            + " world_delta=" + worldDelta.ToString("F3")
            + " engage_local_delta=" + localDelta.ToString("F3")
            + " body_compensated_delta=" + binder.BodyCompensatedTrackingDelta.ToString("F3")
            + " body_translation=" + binder.EstimatedBodyTranslation.ToString("F3")
            + " body_compensation=" + binder.HasBodyTranslationCompensation
            + " head_speed_deg_s=" + binder.TrackedHeadAngularSpeedDegrees.ToString("F1")
            + " head_motion_hold=" + binder.IsHeadMotionHold
            + " movement_scale=" + binder.movement_scale.ToString("F3")
            + " scaled_delta=" + scaledDelta.ToString("F3")
            + " operator_delta=" + operatorDelta.ToString("F3")
            + " preview_world=" + previewPosition.ToString("F3")
            + senderText);
    }
}
