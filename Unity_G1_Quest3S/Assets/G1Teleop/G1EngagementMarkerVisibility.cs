using UnityEngine;

/// <summary>
/// Keeps the engagement spheres visible while suppressing orientation-axis and
/// mapping-line debug geometry. This is presentation-only: tracking, engage,
/// UDP, IK, and diagnostics are unchanged.
/// </summary>
[DefaultExecutionOrder(10000)]
public sealed class G1EngagementMarkerVisibility : MonoBehaviour
{
    private static bool installed;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        if (installed)
        {
            return;
        }

        installed = true;
        GameObject host = new GameObject("G1_Engagement_Marker_Visibility");
        DontDestroyOnLoad(host);
        host.AddComponent<G1EngagementMarkerVisibility>();
    }

    private void LateUpdate()
    {
        G1UnityRightArmPreview[] previews = Object.FindObjectsByType<G1UnityRightArmPreview>(
            FindObjectsInactive.Include,
            FindObjectsSortMode.None);

        foreach (G1UnityRightArmPreview preview in previews)
        {
            // The spheres are part of the operator engage workflow and must stay
            // visible. G1UnityRightArmPreview may initialize this false, so this
            // policy restores it before the next rendered frame.
            preview.show_tracking_markers = true;
        }

        HideDebugObject("tracked_quest_wrist_axes");
        HideDebugObject("mapped_quest_command_axes");
        HideDebugObject("operator_hand_target_axes");
        HideDebugObject("tracked_to_target_line");
    }

    private static void HideDebugObject(string objectName)
    {
        GameObject value = GameObject.Find(objectName);
        if (value != null && value.activeSelf)
        {
            value.SetActive(false);
        }
    }
}
