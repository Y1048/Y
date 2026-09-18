using System;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>Extend the existing scene. No replacement scene or prefab is generated.</summary>
public static class G1SameSceneBimanualSetup
{
    [MenuItem("G1 Teleop/Arms/Use Both Arms (Simulation)")]
    public static void Both() { Configure(true); }

    [MenuItem("G1 Teleop/Arms/Use Original Right Arm")]
    public static void Right() { Configure(false); }

    private static void Configure(bool both)
    {
        if (Application.isPlaying) throw new InvalidOperationException("Stop Play before changing arm mode.");
        var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
        G1ExistingTargetUdpSender original = null;
        G1UnityRightArmPreview preview = null;
        OVRHand leftHand = null;
        foreach (var root in scene.GetRootGameObjects())
        {
            if (original == null) original = root.GetComponentInChildren<G1ExistingTargetUdpSender>(true);
            if (preview == null) preview = root.GetComponentInChildren<G1UnityRightArmPreview>(true);
            foreach (var hand in root.GetComponentsInChildren<OVRHand>(true))
                for (var t = hand.transform; t != null; t = t.parent)
                    if (t.name.IndexOf("Left", StringComparison.OrdinalIgnoreCase) >= 0)
                    { leftHand = hand; break; }
        }
        if (original == null || original.hand_binder == null || preview == null)
            throw new InvalidOperationException("Open the original SampleScene with its right-arm sender/binder/preview.");
        var dual = original.GetComponent<G1BimanualSimulationSender>();
        if (!both && dual == null) { Debug.Log("Original right-arm mode already selected."); return; }
        if (both && (leftHand == null || leftHand.GetComponent<OVRSkeleton>() == null))
            throw new InvalidOperationException("Left OVRHand and OVRSkeleton are required.");
        if (dual == null) dual = Undo.AddComponent<G1BimanualSimulationSender>(original.gameObject);
        Undo.RecordObject(dual, "Select G1 arm mode");
        Undo.RecordObject(preview, "Connect two-arm preview");
        dual.useExistingScene = true;
        dual.armMode = both ? G1BimanualSimulationSender.ArmMode.BimanualSimulation
                            : G1BimanualSimulationSender.ArmMode.RightArm;
        dual.existingSender = original;
        dual.rightBinder = original.hand_binder;
        dual.rightHand = original.hand_binder.ovr_hand;
        dual.rightSkeleton = original.hand_binder.ovr_skeleton;
        dual.head = original.hand_binder.reference_transform;
        if (both)
        {
            dual.leftHand = leftHand;
            dual.leftSkeleton = leftHand.GetComponent<OVRSkeleton>();
            if (dual.leftBinder == null)
            {
                var left = new GameObject("G1_Left_Hand_Target");
                Undo.RegisterCreatedObjectUndo(left, "Add left hand target");
                left.transform.SetParent(original.transform.parent, false);
                dual.leftBinder = Undo.AddComponent<G1ExistingHandTargetBinder>(left);
                // Reuse current serialized tuning instead of new hardcoded input defaults.
                EditorJsonUtility.FromJsonOverwrite(EditorJsonUtility.ToJson(original.hand_binder), dual.leftBinder);
                dual.leftBinder.target_transform = left.transform;
                dual.leftBinder.ovr_hand = leftHand;
                dual.leftBinder.ovr_skeleton = dual.leftSkeleton;
                dual.leftBinder.source_hand = leftHand.transform;
                // Mirror the existing source choice when a LeftHandAnchor is present.
                foreach (var root in scene.GetRootGameObjects())
                    foreach (var t in root.GetComponentsInChildren<Transform>(true))
                        if (t.name == "LeftHandAnchor") dual.leftBinder.source_hand = t;
                var offset = original.hand_binder.preview_neutral_offset;
                offset.x = -offset.x;
                dual.leftBinder.preview_neutral_offset = offset;
            }
        }
        if (dual.leftBinder != null)
        {
            Undo.RecordObject(dual.leftBinder, "Select left input mode");
            // EditorJsonUtility does not reliably preserve cross-object scene
            // references when copying components. Assign these explicitly,
            // including when repairing an already installed left binder.
            dual.leftBinder.reference_transform = original.hand_binder.reference_transform;
            dual.leftBinder.head_camera_alignment = original.hand_binder.head_camera_alignment;
            dual.leftBinder.enabled = both;
            EditorUtility.SetDirty(dual.leftBinder);
        }
        preview.bimanual_simulation = dual;
        EditorUtility.SetDirty(dual);
        EditorUtility.SetDirty(preview);
        EditorSceneManager.MarkSceneDirty(scene);
        Selection.activeGameObject = original.gameObject;
        Debug.Log(both ? "Same scene: BOTH ARMS SIMULATION selected. Save scene, start START_BIMANUAL_UNITY_SIM.bat, then Play."
                       : "Same scene: ORIGINAL RIGHT ARM selected. Save scene, use your original launcher, then Play.");
    }
}
