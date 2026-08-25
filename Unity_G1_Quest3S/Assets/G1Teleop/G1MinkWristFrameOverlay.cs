using UnityEngine;

/// <summary>
/// Reconstructs the Mink right_wrist_yaw clutch frame directly from the live
/// MuJoCo wrist delta and the Unity-replayed wrist pose. This avoids comparing
/// diagnostics against a calibration timestamp that may precede Mink ACTIVE.
///
/// Cyan marker: Quest wrist (owned by G1UnityRightArmPreview)
/// Green marker: Mink target wrist (corrected here)
/// Magenta marker: Unity-replayed G1 right_wrist_yaw (separate helper)
/// </summary>
[DefaultExecutionOrder(9500)]
public sealed class G1MinkWristFrameOverlay : MonoBehaviour
{
    private static bool installed;
    private bool reference_valid;
    private Vector3 mink_reference_world;
    private float log_timer;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        if (installed)
        {
            return;
        }

        installed = true;
        GameObject host = new GameObject("G1_Mink_Wrist_Frame_Overlay");
        DontDestroyOnLoad(host);
        host.AddComponent<G1MinkWristFrameOverlay>();
    }

    private void LateUpdate()
    {
        G1ExistingHandTargetBinder binder = Object.FindFirstObjectByType<G1ExistingHandTargetBinder>(
            FindObjectsInactive.Include);
        G1RobotStateUdpReceiver receiver = Object.FindFirstObjectByType<G1RobotStateUdpReceiver>(
            FindObjectsInactive.Include);
        G1OfficialRig rig = Object.FindFirstObjectByType<G1OfficialRig>(
            FindObjectsInactive.Include);

        if (binder == null
            || receiver == null
            || rig == null
            || !receiver.HasRecentState
            || !receiver.IsTeleoperationActive
            || !receiver.HasMotionDiagnostics)
        {
            reference_valid = false;
            log_timer = 0.0f;
            return;
        }

        Transform unity_wrist = rig.GetRightWristPositionReference();
        if (unity_wrist == null)
        {
            reference_valid = false;
            return;
        }

        Vector3 wrist_delta_world = binder.OperatorHeading
            * receiver.LatestWristOperatorDelta;

        if (!reference_valid)
        {
            // The state packet defines wrist_delta relative to Mink's clutch
            // reference. Since Unity already replays the same q[7], subtracting
            // that delta from the live Unity FK yields the same clutch origin in
            // Unity world coordinates, independent of activation timing.
            mink_reference_world = unity_wrist.position - wrist_delta_world;
            reference_valid = true;
            Debug.Log("G1 Mink wrist-yaw reference synchronized from live ACTIVE state.");
        }

        Vector3 mink_target_world = mink_reference_world
            + binder.OperatorHeading * receiver.LatestTargetOperatorDelta;
        Vector3 reconstructed_wrist_world = mink_reference_world + wrist_delta_world;

        GameObject target_marker = GameObject.Find("operator_hand_target_marker");
        if (target_marker != null)
        {
            target_marker.transform.position = mink_target_world;
        }

        log_timer += Time.deltaTime;
        if (log_timer >= 2.0f)
        {
            log_timer = 0.0f;
            float replay_error_cm = Vector3.Distance(
                unity_wrist.position,
                reconstructed_wrist_world) * 100.0f;
            float target_error_cm = Vector3.Distance(
                unity_wrist.position,
                mink_target_world) * 100.0f;
            Debug.Log(
                "G1 MINK FRAME replay=" + replay_error_cm.ToString("F2")
                + " cm | target-follow=" + target_error_cm.ToString("F2")
                + " cm | MuJoCo IK=" + (receiver.LatestPositionError * 100.0f).ToString("F2")
                + " cm");
        }
    }
}
