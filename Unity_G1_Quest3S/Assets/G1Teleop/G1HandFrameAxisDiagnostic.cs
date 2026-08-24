using UnityEngine;

public class G1HandFrameAxisDiagnostic : MonoBehaviour
{
    private G1ExistingHandTargetBinder binder;
    private const float AxisLength = 0.16f;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        if (FindFirstObjectByType<G1HandFrameAxisDiagnostic>() != null)
        {
            return;
        }
        var host = new GameObject("G1HandFrameAxisDiagnostic");
        DontDestroyOnLoad(host);
        host.AddComponent<G1HandFrameAxisDiagnostic>();
    }

    private void LateUpdate()
    {
        if (binder == null)
        {
            binder = FindFirstObjectByType<G1ExistingHandTargetBinder>();
            if (binder == null)
            {
                return;
            }
        }

        Vector3 origin = binder.TrackedWristPosition;
        Quaternion rotation = binder.TrackedWristRotation;
        Debug.DrawRay(origin, rotation * Vector3.right * AxisLength, Color.red, 0.0f, false);
        Debug.DrawRay(origin, rotation * Vector3.up * AxisLength, Color.green, 0.0f, false);
        Debug.DrawRay(origin, rotation * Vector3.forward * AxisLength, Color.blue, 0.0f, false);
    }
}
