using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.SceneManagement;

// Remove SDK-injected editor credentials from this observation APK before serialization.
public sealed class G1QuestObservationResourceGuard : IPreprocessBuildWithReport
{
    public int callbackOrder => int.MaxValue;
    public void OnPreprocessBuild(BuildReport report)
    {
        if (report.summary.platform != BuildTarget.Android || PlayerSettings.applicationIdentifier != G1QuestObservationBuild.AppId) return;
        var asset = AssetDatabase.LoadMainAssetAtPath("Assets/Resources/DevAgentSettings.asset");
        if (asset == null) throw new InvalidDataException("Expected DevAgent settings asset missing.");
        var settings = new SerializedObject(asset);
        foreach (string field in new[] { "serverAddress", "accessToken", "witClientAccessToken" }) {
            var property = settings.FindProperty(field);
            if (property == null) throw new InvalidDataException("DevAgent schema changed: " + field);
            property.stringValue = "";
        }
        var enabled = settings.FindProperty("enabled");
        if (enabled == null) throw new InvalidDataException("DevAgent enabled field missing.");
        enabled.boolValue = false;
        settings.ApplyModifiedPropertiesWithoutUndo();
        Debug.Log("Observation APK: editor agent disabled and credential fields cleared before serialization.");
    }
}

public static class G1QuestObservationBuild
{
    public const string AppId = "kr.kaeri.g1questobservation";
    private const string ScenePath = "Assets/Scenes/G1QuestObservation.unity";

    private static GameObject Prefab(string file)
    {
        string path = "Packages/com.meta.xr.sdk.core/Prefabs/" + file + ".prefab";
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
        if (prefab == null) throw new FileNotFoundException("SDK prefab missing", path);
        return (GameObject)PrefabUtility.InstantiatePrefab(prefab);
    }
    public static void CreateScene()
    {
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        GameObject rigObject = Prefab("OVRCameraRig");
        var rig = rigObject.GetComponent<OVRCameraRig>();
        if (rig == null) throw new InvalidDataException("SDK rig missing.");
        if (rigObject.GetComponent<OVRManager>() == null) rigObject.AddComponent<OVRManager>();
        var sender = rigObject.AddComponent<G1QuestObservationSender>();
        sender.rig = rig;
        for (int i = 0; i < 2; i++) {
            GameObject handObject = Prefab("OVRHandPrefab");
            handObject.name = i == 0 ? "ObservationLeftHand" : "ObservationRightHand";
            handObject.transform.SetParent(i == 0 ? rig.leftHandAnchor : rig.rightHandAnchor, false);
            var hand = handObject.GetComponent<OVRHand>();
            var settings = new SerializedObject(hand);
            var type = settings.FindProperty("HandType");
            if (type == null) throw new InvalidDataException("OVRHand HandType missing.");
            type.intValue = i;
            settings.ApplyModifiedPropertiesWithoutUndo();
            hand.OnValidate(); // Synchronizes skeleton and mesh side/version with HandType.
            if (i == 0) { sender.leftHand = hand; sender.leftSkeleton = handObject.GetComponent<OVRSkeleton>(); }
            else { sender.rightHand = hand; sender.rightSkeleton = handObject.GetComponent<OVRSkeleton>(); }
        }
        var canvasObject = new GameObject("ObservationStatus", typeof(RectTransform), typeof(Canvas));
        var canvas = canvasObject.GetComponent<Canvas>();
        canvas.renderMode = RenderMode.WorldSpace;
        canvasObject.transform.SetParent(rig.centerEyeAnchor, false);
        canvasObject.transform.localPosition = new Vector3(0, 0, 1.2f);
        canvasObject.transform.localScale = Vector3.one * .002f;
        var rect = canvasObject.GetComponent<RectTransform>(); rect.sizeDelta = new Vector2(700, 400);
        var textObject = new GameObject("Status", typeof(RectTransform), typeof(Text), typeof(G1QuestObservationStatus));
        textObject.transform.SetParent(canvasObject.transform, false);
        var text = textObject.GetComponent<Text>();
        text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        text.fontSize = 25; text.alignment = TextAnchor.MiddleCenter; text.color = Color.cyan;
        text.rectTransform.sizeDelta = rect.sizeDelta;
        textObject.GetComponent<G1QuestObservationStatus>().sender = sender;
        RenderSettings.ambientLight = Color.white;
        var light = new GameObject("ObservationLight", typeof(Light)).GetComponent<Light>();
        light.type = LightType.Directional;
        EditorSceneManager.SaveScene(SceneManager.GetActiveScene(), ScenePath);
    }
    public static void Build()
    {
        EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
        CreateScene();
        PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, AppId);
        PlayerSettings.productName = "G1 Quest Input Observation";
        PlayerSettings.companyName = "KAERI";
        PlayerSettings.SplashScreen.showUnityLogo = false;
        PlayerSettings.SplashScreen.show = false;
        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel32;
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
        PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
        PlayerSettings.Android.forceInternetPermission = true;
        string output = Environment.GetEnvironmentVariable("G1_QUEST_OBSERVATION_APK");
        if (string.IsNullOrWhiteSpace(output) || File.Exists(output)) throw new InvalidOperationException("Specify a new G1_QUEST_OBSERVATION_APK path.");
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(output)));
        BuildReport result = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
            scenes = new[] { ScenePath }, locationPathName = output,
            target = BuildTarget.Android, options = BuildOptions.None
        });
        if (result.summary.result != BuildResult.Succeeded) throw new Exception("Observation APK build failed: " + result.summary.result);
        Debug.Log("Quest observation APK build succeeded: " + output);
    }
}
