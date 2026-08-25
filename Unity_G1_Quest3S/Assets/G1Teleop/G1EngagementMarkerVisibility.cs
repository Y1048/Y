using UnityEngine;

/// <summary>
/// Keeps the engagement spheres visible, centers them on the operator palm,
/// and suppresses orientation-axis / mapping-line debug geometry.
/// Presentation only: wrist-based robot control, UDP, and Mink IK are unchanged.
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
            // visible. G1UnityRightArmPreview currently initializes this false,
            // so restore marker rendering after its own LateUpdate.
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

        if (!TryGetPalmCenter(binder, out Vector3 palm_center))
        {
            return;
        }

        GameObject tracked_marker = GameObject.Find("tracked_quest_wrist_marker");
        if (tracked_marker != null && binder.IsTrackingValid)
        {
            tracked_marker.transform.position = palm_center;
        }

        GameObject target_marker = GameObject.Find("operator_hand_target_marker");
        if (target_marker == null)
        {
            return;
        }

        // Convert the measured wrist->palm offset into the semantic hand frame,
        // then apply the same offset to the target wrist pose. Preview resets the
        // target marker to the wrist command every frame before this executes, so
        // this addition never accumulates frame-to-frame.
        Vector3 local_palm_offset = Quaternion.Inverse(binder.TrackedWristRotation)
            * (palm_center - binder.TrackedWristPosition);
        target_marker.transform.position += target_marker.transform.rotation
            * local_palm_offset;
    }

    private static bool TryGetPalmCenter(
        G1ExistingHandTargetBinder binder,
        out Vector3 palm_center)
    {
        palm_center = binder.TrackedWristPosition;
        if (binder.ovr_skeleton == null || binder.ovr_skeleton.Bones == null)
        {
            return false;
        }

        foreach (OVRBone bone_value in binder.ovr_skeleton.Bones)
        {
            if (bone_value != null
                && bone_value.Id == OVRSkeleton.BoneId.Hand_Middle1)
            {
                palm_center = Vector3.Lerp(
                    binder.TrackedWristPosition,
                    bone_value.Transform.position,
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
