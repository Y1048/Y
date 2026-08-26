using UnityEngine;

/// <summary>
/// Shows the actual Unity-replayed G1 right_wrist_yaw frame.
/// This marker follows the robot FK only; it is not the operator target marker.
/// </summary>
[DefaultExecutionOrder(9000)]
public sealed class G1ActualWristYawMarker : MonoBehaviour
{
    private const float marker_size_m = 0.065f;
    private static bool installed;
    private Transform marker_transform;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        if (installed)
        {
            return;
        }

        installed = true;
        GameObject host = new GameObject("G1_Actual_Wrist_Yaw_Marker_Controller");
        DontDestroyOnLoad(host);
        host.AddComponent<G1ActualWristYawMarker>();
    }

    private void LateUpdate()
    {
        G1OfficialRig rig = Object.FindFirstObjectByType<G1OfficialRig>(FindObjectsInactive.Include);
        if (rig == null)
        {
            SetMarkerActive(false);
            return;
        }

        Transform wrist = rig.GetRightWristPositionReference();
        if (wrist == null)
        {
            SetMarkerActive(false);
            return;
        }

        if (marker_transform == null)
        {
            marker_transform = CreateMarker();
        }

        marker_transform.position = wrist.position;
        marker_transform.rotation = wrist.rotation;
        SetMarkerActive(rig.gameObject.activeInHierarchy);
    }

    private Transform CreateMarker()
    {
        GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        marker.name = "g1_actual_right_wrist_yaw_marker";
        marker.transform.localScale = Vector3.one * marker_size_m;

        Renderer renderer_value = marker.GetComponent<Renderer>();
        Shader shader_value = Shader.Find("Unlit/Color");
        if (shader_value == null)
        {
            shader_value = Shader.Find("Universal Render Pipeline/Unlit");
        }
        if (shader_value == null)
        {
            shader_value = Shader.Find("Standard");
        }

        Material material_value = new Material(shader_value);
        material_value.name = "g1_actual_wrist_yaw_marker_material";
        material_value.color = new Color(1.0f, 0.15f, 0.85f, 1.0f);
        renderer_value.sharedMaterial = material_value;

        Collider collider_value = marker.GetComponent<Collider>();
        if (collider_value != null)
        {
            Destroy(collider_value);
        }

        return marker.transform;
    }

    private void SetMarkerActive(bool active_value)
    {
        if (marker_transform != null && marker_transform.gameObject.activeSelf != active_value)
        {
            marker_transform.gameObject.SetActive(active_value);
        }
    }

    private void OnDestroy()
    {
        if (marker_transform != null)
        {
            Destroy(marker_transform.gameObject);
        }
    }
}
