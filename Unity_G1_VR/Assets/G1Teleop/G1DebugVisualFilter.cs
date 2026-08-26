using UnityEngine;

/// <summary>
/// Presentation-only filter for G1 teleoperation debug geometry.
/// It never changes engagement marker position, scale, color, tracking,
/// calibration, UDP, or IK state.
/// </summary>
[DefaultExecutionOrder(10000)]
public sealed class G1DebugVisualFilter : MonoBehaviour
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
        GameObject host = new GameObject("G1_Debug_Visual_Filter");
        DontDestroyOnLoad(host);
        host.AddComponent<G1DebugVisualFilter>();
    }

    private void LateUpdate()
    {
        Hide("tracked_quest_wrist_axes");
        Hide("mapped_quest_command_axes");
        Hide("operator_hand_target_axes");
        Hide("tracked_to_target_line");
    }

    private static void Hide(string objectName)
    {
        GameObject value = GameObject.Find(objectName);
        if (value != null && value.activeSelf)
        {
            value.SetActive(false);
        }
    }
}
