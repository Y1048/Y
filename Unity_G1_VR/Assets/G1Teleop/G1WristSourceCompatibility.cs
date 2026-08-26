using UnityEngine;

/// <summary>
/// Meta XR SDK compatibility policy for the G1 teleoperation wrist source.
///
/// The project historically uses the Quest rig's source_hand transform as the
/// operator wrist reference. Newer Meta XR packages can place Hand_WristRoot
/// visually farther into the palm. Keep the original rig wrist reference for
/// position while the binder still derives the semantic hand orientation from
/// the hand skeleton.
/// </summary>
[DefaultExecutionOrder(-10000)]
public sealed class G1WristSourceCompatibility : MonoBehaviour
{
    private static bool installed;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        ApplyPolicy();

        if (installed)
        {
            return;
        }

        installed = true;
        GameObject host = new GameObject("G1_Wrist_Source_Compatibility");
        DontDestroyOnLoad(host);
        host.AddComponent<G1WristSourceCompatibility>();
    }

    private void Update()
    {
        ApplyPolicy();
    }

    private static void ApplyPolicy()
    {
        G1ExistingHandTargetBinder[] binders = Object.FindObjectsByType<G1ExistingHandTargetBinder>(
            FindObjectsInactive.Include,
            FindObjectsSortMode.None);

        foreach (G1ExistingHandTargetBinder binder in binders)
        {
            if (binder.source_hand != null)
            {
                binder.prefer_skeleton_wrist = false;
            }
        }
    }
}
