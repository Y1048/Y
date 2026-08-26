using UnityEngine;

/// <summary>
/// Slightly enlarges the operator engagement/command target sphere while
/// preserving the preview's progress pulse. This changes visualization only.
/// </summary>
[DefaultExecutionOrder(12000)]
public sealed class G1EngagementTargetSizePolicy : MonoBehaviour
{
    private const float original_base_size_m = 0.045f;
    private const float desired_base_size_m = 0.055f;
    private static bool installed;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        if (installed)
        {
            return;
        }

        installed = true;
        GameObject host = new GameObject("G1_Engagement_Target_Size_Policy");
        DontDestroyOnLoad(host);
        host.AddComponent<G1EngagementTargetSizePolicy>();
    }

    private void LateUpdate()
    {
        GameObject marker = GameObject.Find("operator_hand_target_marker");
        if (marker == null || !marker.activeSelf)
        {
            return;
        }

        // G1UnityRightArmPreview restores the marker scale every LateUpdate.
        // Apply one final fixed ratio afterwards so the engage-progress pulse is
        // retained without accumulating scale frame-to-frame.
        float ratio = desired_base_size_m / original_base_size_m;
        marker.transform.localScale *= ratio;
    }
}
