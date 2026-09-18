using System;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class G1BimanualSimulationSetup
{
    [MenuItem("G1 Teleop/Create Separate Bimanual Simulation Scene")]
    public static void CreateScene()
    {
        if (Application.isPlaying) throw new InvalidOperationException("Stop Play first.");
        if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
        const string destination = "Assets/Scenes/BimanualSimulation.unity";
        if (System.IO.File.Exists(destination))
            throw new InvalidOperationException("BimanualSimulation.unity already exists. Open that scene; it is not overwritten.");
        var original = EditorSceneManager.OpenScene("Assets/Scenes/SampleScene.unity");
        if (!EditorSceneManager.SaveScene(original, destination, true))
            throw new InvalidOperationException("Could not copy source scene.");
        var scene = EditorSceneManager.OpenScene(destination);
        OVRHand left = null, right = null;
        Transform head = null;
        foreach (var root in scene.GetRootGameObjects())
        {
            foreach (var component in root.GetComponentsInChildren<MonoBehaviour>(true))
            {
                if (component == null) continue;
                // Remove old G1 components in the COPY. Merely disabling them
                // would still allow Awake to create sockets/timers.
                if (component.GetType().Name.StartsWith("G1", StringComparison.Ordinal))
                {
                    UnityEngine.Object.DestroyImmediate(component);
                    continue;
                }
                if (component is OVRHand hand)
                {
                    for (Transform t = hand.transform; t != null; t = t.parent)
                    {
                        if (t.name.IndexOf("Left", StringComparison.OrdinalIgnoreCase) >= 0) { left = hand; break; }
                        if (t.name.IndexOf("Right", StringComparison.OrdinalIgnoreCase) >= 0) { right = hand; break; }
                    }
                }
            }
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
                if (t.name == "CenterEyeAnchor") head = t;
        }
        if (left == null || right == null || head == null)
            throw new InvalidOperationException("Both OVRHands and CenterEyeAnchor are required in the copied scene.");
        var sender = new GameObject("Bimanual Simulation Input ONLY").AddComponent<G1BimanualSimulationSender>();
        sender.head = head;
        sender.leftHand = left;
        sender.rightHand = right;
        sender.leftSkeleton = left.GetComponent<OVRSkeleton>();
        sender.rightSkeleton = right.GetComponent<OVRSkeleton>();
        if (sender.leftSkeleton == null || sender.rightSkeleton == null)
            throw new InvalidOperationException("Missing OVRSkeleton on OVRHand.");
        EditorSceneManager.SaveScene(scene);
        Debug.Log("BimanualSimulation scene saved. Start START_BIMANUAL_UNITY_SIM.bat, then Play. No G1 connection.");
    }
}
