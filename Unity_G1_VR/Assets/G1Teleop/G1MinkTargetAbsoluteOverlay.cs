using UnityEngine;

/// <summary>
/// Repositions the green operator target marker from Mink's current absolute
/// right_wrist_yaw positions rather than a historical Unity calibration baseline.
///
/// The world-space target is reconstructed as:
/// UnityActualWrist + R_root * (MinkTarget - MinkWrist)
///
/// This removes HMD-anchor, pelvis-origin, and clutch-timing ambiguity while
/// preserving the exact instantaneous target-follow vector solved by Mink.
/// </summary>
[DefaultExecutionOrder(11000)]
public sealed class G1MinkTargetAbsoluteOverlay : MonoBehaviour
{
    private static bool installed;
    private float log_timer;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        if (installed)
        {
            return;
        }

        installed = true;
        GameObject host = new GameObject("G1_Mink_Target_Absolute_Overlay");
        DontDestroyOnLoad(host);
        host.AddComponent<G1MinkTargetAbsoluteOverlay>();
    }

    private void LateUpdate()
    {
        G1RobotStateUdpReceiver state = Object.FindFirstObjectByType<G1RobotStateUdpReceiver>(
            FindObjectsInactive.Include);
        G1OfficialRig rig = Object.FindFirstObjectByType<G1OfficialRig>(
            FindObjectsInactive.Include);
        GameObject target_marker = GameObject.Find("operator_hand_target_marker");

        if (state == null
            || rig == null
            || target_marker == null
            || !state.HasRecentState
            || !state.HasAbsoluteMinkPositions)
        {
            return;
        }

        Transform actual_wrist = rig.GetRightWristPositionReference();
        if (actual_wrist == null)
        {
            return;
        }

        Vector3 mink_error_robot = state.LatestTargetRobotPosition
            - state.LatestWristRobotPosition;
        Vector3 mink_error_unity_local = RobotVectorToUnity(mink_error_robot);
        Vector3 mink_error_world = rig.transform.rotation * mink_error_unity_local;
        Vector3 target_world = actual_wrist.position + mink_error_world;

        target_marker.transform.position = target_world;

        log_timer += Time.deltaTime;
        if (log_timer >= 2.0f)
        {
            log_timer = 0.0f;
            Debug.Log(
                "G1 MINK FRAME active=" + state.IsTeleoperationActive
                + " target-follow=" + (mink_error_world.magnitude * 100.0f).ToString("F2")
                + " cm | MuJoCo IK=" + (state.LatestPositionError * 100.0f).ToString("F2")
                + " cm");
        }
    }

    private static Vector3 RobotVectorToUnity(Vector3 robot_vector)
    {
        // MuJoCo G1: +X forward, +Y left, +Z up.
        // Unity G1 root: +X right, +Y up, +Z forward.
        return new Vector3(
            -robot_vector.y,
            robot_vector.z,
            robot_vector.x);
    }
}
