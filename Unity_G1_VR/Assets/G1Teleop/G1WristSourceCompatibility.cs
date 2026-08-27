using UnityEngine;

/// <summary>
/// Meta XR SDK 버전 차이에도 G1 텔레오퍼레이션 손목 기준을 일정하게 유지한다.
///
/// 위치는 기존 Quest rig의 source_hand를 사용한다. 일부 최신 Meta XR 패키지의
/// Hand_WristRoot가 손바닥 안쪽으로 이동해 보이는 차이를 피하면서, 의미 있는 손 방향은
/// binder가 계속 skeleton에서 계산하도록 한다.
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
