using UnityEngine;

// Read-only input diagnosis: does not enable features, send packets, or change hand poses.
public sealed class G1LinkHandDiagnostics : MonoBehaviour
{
    private float nextReport;
    private OVRPlugin.HandState left;
    private OVRPlugin.HandState right;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        var diagnostic = new GameObject("G1 Link Hand Diagnostics");
        DontDestroyOnLoad(diagnostic);
        diagnostic.AddComponent<G1LinkHandDiagnostics>();
    }

    private void Update()
    {
        if (Time.unscaledTime < nextReport) return;
        nextReport = Time.unscaledTime + 2f;
        try
        {
            bool enabled = OVRPlugin.GetHandTrackingEnabled();
            bool leftOk = OVRPlugin.GetHandState(OVRPlugin.Step.Render, OVRPlugin.Hand.HandLeft, ref left);
            bool rightOk = OVRPlugin.GetHandState(OVRPlugin.Step.Render, OVRPlugin.Hand.HandRight, ref right);
            Debug.Log($"[G1 XR HAND] editor={Application.isEditor} development={Debug.isDebugBuild} " +
                $"focused={Application.isFocused} runtime_hands_enabled={enabled} " +
                $"active_controller={OVRPlugin.GetActiveController()} " +
                $"left_query_ok={leftOk} left_status={(leftOk ? left.Status.ToString() : "unavailable")} " +
                $"right_query_ok={rightOk} right_status={(rightOk ? right.Status.ToString() : "unavailable")}");
        }
        catch (System.Exception error)
        {
            Debug.LogWarning("[G1 XR HAND] query failed: " + error.GetType().Name);
        }
    }
}