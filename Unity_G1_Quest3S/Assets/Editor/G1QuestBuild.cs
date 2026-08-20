using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

public static class G1QuestBuild
{
    private const string scene_path = "Assets/Scenes/SampleScene.unity";
    private const string output_path = "../Builds/G1Quest3STeleop.apk";

    public static void BuildApk()
    {
        EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);

        PlayerSettings.SetApplicationIdentifier(
            NamedBuildTarget.Android,
            "kr.kaeri.g1quest3steleop");
        PlayerSettings.productName = "G1 Quest3S Teleop";
        PlayerSettings.companyName = "KAERI";
        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel29;
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;

        EditorBuildSettings.scenes = new[]
        {
            new EditorBuildSettingsScene(scene_path, true)
        };

        string absolute_output_path = Path.GetFullPath(Path.Combine(Application.dataPath, output_path));
        Directory.CreateDirectory(Path.GetDirectoryName(absolute_output_path));

        BuildPlayerOptions build_options = new BuildPlayerOptions
        {
            scenes = new[] { scene_path },
            locationPathName = absolute_output_path,
            target = BuildTarget.Android,
            options = BuildOptions.None
        };

        BuildReport report = BuildPipeline.BuildPlayer(build_options);
        if (report.summary.result != BuildResult.Succeeded)
        {
            throw new System.Exception("Quest APK build failed: " + report.summary.result);
        }

        Debug.Log("Quest APK build succeeded: " + absolute_output_path);
    }
}
