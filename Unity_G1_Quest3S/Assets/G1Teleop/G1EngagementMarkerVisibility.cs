using UnityEngine;

/// <summary>
/// Keeps engagement spheres visible, centers them on the operator palm, and
/// suppresses orientation-axis / mapping-line debug geometry. Wrist-based robot
/// control, UDP targets, and Mink IK are unchanged.
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
            preview.show_tracking_markers = true;
            CenterMarkersOnPalm(preview);
        }

        HideDebugObject("tracked_quest_wrist_axes");
        HideDebugObject("mapped_quest_command_axes");
        HideDebugObject("operator_hand_target_axes");
        HideDebugObject("tracked_to_target_line");
    }

    private static void CenterMarkersOnPalm(G1UnityRightArmPreview preview)
    {
        G1ExistingHandTargetBinder binder = preview.hand_binder;
        if (binder == null || !binder.IsEngagementFrameLocked)
        {
            return;
        }

        if (!TryGetPalmCenter(binder, out Vector3 palmCenter))
        {
            return;
        }

        GameObject trackedMarker = GameObject.Find("tracked_quest_wrist_marker");
        if (trackedMarker != null && binder.IsTrackingValid)
        {
            trackedMarker.transform.position = palmCenter;
        }

        GameObject targetMarker = GameObject.Find("operator_hand_target_marker");
        if (targetMarker == null)
        {
            return;
        }

        Vector3 localPalmOffset = Quaternion.Inverse(binder.TrackedWristRotation)
            * (palmCenter - binder.TrackedWristPosition);

        // G1UnityRightArmPreview resets this marker to the target wrist pose in
        // its own LateUpdate. Apply the corresponding wrist->palm offset after
        // that update, so this does not accumulate between frames.
        targetMarker.transform.position += targetMarker.transform.rotation
            * localPalmOffset;
    }

    private static bool TryGetPalmCenter(
        G1ExistingHandTargetBinder binder,
        out Vector3 palmCenter)
    {
        palmCenter = binder.TrackedWristPosition;
        if (binder.ovr_skeleton == null || binder.ovr_skeleton.Bones == null)
        {
            return false;
        }

        foreach (OVRBone boneValue in binder.ovr_skeleton.Bones)
        {
            if (boneValue != null
                && boneValue.Id == OVRSkeleton.BoneId.Hand_Middle1)
            {
                palmCenter = Vector3.Lerp(
                    binder.TrackedWristPosition,
                    boneValue.Transform.position,
                    0.50f);
                return true;
            }
        }

        return false;
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
