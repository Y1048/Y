using UnityEngine;

/// <summary>
/// Optional experimental mode that delegates workspace authority to the backend.
/// It is deliberately opt-in and is not installed automatically at runtime.
/// </summary>
[DisallowMultipleComponent]
public sealed class G1BackendWorkspaceAuthority : MonoBehaviour
{
    private const float DisabledWorkspaceExtent = 1000.0f;

    public bool enable_backend_workspace_authority;
    public G1ExistingTargetUdpSender target_sender;

    private void Awake()
    {
        if (!enable_backend_workspace_authority)
        {
            return;
        }

        if (target_sender == null)
        {
            target_sender = GetComponent<G1ExistingTargetUdpSender>();
        }

        if (target_sender == null)
        {
            Debug.LogWarning(
                "G1 backend workspace authority requires an assigned target sender.");
            enabled = false;
            return;
        }

        ApplyBackendAuthority(target_sender);
    }

    private static void ApplyBackendAuthority(G1ExistingTargetUdpSender sender)
    {
        sender.disengage_on_workspace_exit = false;
        sender.robot_min = new Vector3(
            -DisabledWorkspaceExtent,
            -DisabledWorkspaceExtent,
            -DisabledWorkspaceExtent);
        sender.robot_max = new Vector3(
            DisabledWorkspaceExtent,
            DisabledWorkspaceExtent,
            DisabledWorkspaceExtent);

        Debug.Log(
            "Experimental backend workspace authority enabled explicitly."
            + " Unity workspace disengagement is disabled for this sender.");
    }
}
