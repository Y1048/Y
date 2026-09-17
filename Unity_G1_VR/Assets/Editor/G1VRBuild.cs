using System.IO;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

public static class G1VRBuild
{
    private const string scene_path = "Assets/Scenes/SampleScene.unity";
    private const string output_path = "../Builds/G1TeleopVR.apk";

    public static void BuildApk()
    {
        EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);

        PlayerSettings.SetApplicationIdentifier(
            NamedBuildTarget.Android,
            "kr.kaeri.g1teleopvr");
        PlayerSettings.productName = "G1 Teleop VR";
        PlayerSettings.companyName = "KAERI";
        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel29;
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;

        EditorBuildSettings.scenes = new[]
        {
            new EditorBuildSettingsScene(scene_path, true)
        };

        string requested_output_path = System.Environment.GetEnvironmentVariable("G1_APK_OUTPUT_PATH");
        string absolute_output_path = string.IsNullOrEmpty(requested_output_path)
            ? Path.GetFullPath(Path.Combine(Application.dataPath, output_path))
            : Path.GetFullPath(requested_output_path);
        if (!string.IsNullOrEmpty(requested_output_path) && File.Exists(absolute_output_path))
        {
            throw new System.InvalidOperationException("The requested APK path must be new for this build.");
        }
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
            throw new System.Exception("VR APK build failed: " + report.summary.result);
        }

        if (!File.Exists(absolute_output_path))
        {
            throw new System.IO.FileNotFoundException("Build reported success without an APK.", absolute_output_path);
        }
        using (SHA256 hash = SHA256.Create())
        using (FileStream stream = File.OpenRead(absolute_output_path))
        {
            string digest = System.BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "");
            File.WriteAllText(absolute_output_path + ".sha256", digest);
        }

        Debug.Log("VR APK build succeeded: " + absolute_output_path);
    }
}
