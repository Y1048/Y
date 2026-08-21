using UnityEngine;

/// <summary>
/// Makes the MuJoCo voxel workspace the single workspace authority during Play mode.
/// Unity keeps generating the operator target, but does not clamp or disengage on its
/// legacy rectangular workspace. The backend remains responsible for projection,
/// boundary sliding, collision handling, and workspace feedback.
/// </summary>
public sealed class G1BackendWorkspaceAuthority : MonoBehaviour
{
    private const float DisabledWorkspaceExtent = 1000.0f;

    private G1ExistingTargetUdpSender configuredSender;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        if (FindObjectOfType<G1BackendWorkspaceAuthority>() != null)
        {
            return;
        }

        GameObject authorityObject = new GameObject("G1BackendWorkspaceAuthority");
        DontDestroyOnLoad(authorityObject);
        authorityObject.AddComponent<G1BackendWorkspaceAuthority>();
    }

    private void Update()
    {
        G1ExistingTargetUdpSender sender = FindObjectOfType<G1ExistingTargetUdpSender>();
        if (sender == null || sender == configuredSender)
        {
            return;
        }

        ApplyBackendAuthority(sender);
        configuredSender = sender;
    }

    private static void ApplyBackendAuthority(G1ExistingTargetUdpSender sender)
    {
        // Do not turn backend workspace feedback into a Unity-side clutch release.
        // This also prevents the old excursion-cleared path from repeatedly
        // ResetCalibration()/Calibrate()-ing and shrinking OperatorTargetDelta.
        sender.disengage_on_workspace_exit = false;

        // The sender still calls ClampToRobotWorkspace internally. Widening these
        // legacy transport bounds makes that clamp a no-op for any realistic hand
        // motion while leaving the original code path available for legacy scenes.
        sender.robot_min = new Vector3(
            -DisabledWorkspaceExtent,
            -DisabledWorkspaceExtent,
            -DisabledWorkspaceExtent);
        sender.robot_max = new Vector3(
            DisabledWorkspaceExtent,
            DisabledWorkspaceExtent,
            DisabledWorkspaceExtent);

        Debug.Log(
            "G1 backend voxel workspace authority enabled: Unity rectangular "
            + "workspace clamp/disengage disabled for teleoperation.");
    }
}
