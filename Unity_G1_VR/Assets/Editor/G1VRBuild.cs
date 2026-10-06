using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

public static class G1VRBuild
{
    private const string scene_path = "Assets/Scenes/SampleScene.unity";
    private const string output_path = "../Builds/G1TeleopVR.apk";
    private const string windows_output_path = "../../Builds/Windows/G1Teleop.exe";
    private const string dev_agent_settings_path = "Assets/Resources/DevAgentSettings.asset";

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

    public static void BuildWindows()
    {
        EditorUserBuildSettings.SwitchActiveBuildTarget(
            BuildTargetGroup.Standalone,
            BuildTarget.StandaloneWindows64);

        PlayerSettings.productName = "G1 Teleop";
        PlayerSettings.companyName = "KAERI";
        EditorBuildSettings.scenes = new[]
        {
            new EditorBuildSettingsScene(scene_path, true)
        };

        string requested_output_path =
            System.Environment.GetEnvironmentVariable("G1_WINDOWS_OUTPUT_PATH");
        string absolute_output_path = string.IsNullOrEmpty(requested_output_path)
            ? Path.GetFullPath(Path.Combine(Application.dataPath, windows_output_path))
            : Path.GetFullPath(requested_output_path);
        if (!absolute_output_path.EndsWith(".exe", System.StringComparison.OrdinalIgnoreCase))
        {
            throw new System.InvalidOperationException(
                "The Windows player output path must end with .exe.");
        }
        if (File.Exists(absolute_output_path))
        {
            throw new System.InvalidOperationException(
                "The Windows player output path already exists; use a new build folder.");
        }
        Directory.CreateDirectory(Path.GetDirectoryName(absolute_output_path));

        BuildPlayerOptions build_options = new BuildPlayerOptions
        {
            scenes = new[] { scene_path },
            locationPathName = absolute_output_path,
            target = BuildTarget.StandaloneWindows64,
            options = BuildOptions.None
        };

        BuildReport report = BuildPipeline.BuildPlayer(build_options);
        if (report.summary.result != BuildResult.Succeeded)
        {
            throw new System.Exception(
                "Windows VR player build failed: " + report.summary.result);
        }

        if (!File.Exists(absolute_output_path))
        {
            throw new FileNotFoundException(
                "Build reported success without a Windows player.",
                absolute_output_path);
        }

        SanitizeWindowsBuildResources(absolute_output_path);

        using (SHA256 hash = SHA256.Create())
        using (FileStream stream = File.OpenRead(absolute_output_path))
        {
            string digest = System.BitConverter.ToString(
                hash.ComputeHash(stream)).Replace("-", "");
            File.WriteAllText(absolute_output_path + ".sha256", digest);
        }

        Debug.Log("Windows VR player build succeeded: " + absolute_output_path);
    }

    private static void SanitizeWindowsBuildResources(string executable_path)
    {
        string project_root = Directory.GetParent(Application.dataPath).FullName;
        string settings_path = Path.Combine(
            project_root,
            dev_agent_settings_path.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(settings_path))
        {
            throw new FileNotFoundException(
                "DevAgent settings are missing; refusing an unverifiable Windows build.",
                settings_path);
        }

        string settings_text = File.ReadAllText(settings_path);
        string access_token = ReadYamlValue(settings_text, "accessToken");
        string server_address = ReadYamlValue(settings_text, "serverAddress");
        string data_directory = Path.Combine(
            Path.GetDirectoryName(executable_path),
            Path.GetFileNameWithoutExtension(executable_path) + "_Data");
        string resources_path = Path.Combine(data_directory, "resources.assets");
        if (!File.Exists(resources_path))
        {
            throw new FileNotFoundException(
                "Windows build has no resources.assets to sanitize.",
                resources_path);
        }

        byte[] resources = File.ReadAllBytes(resources_path);
        ReplaceUniqueUtf8Value(resources, access_token, "DevAgent access token");
        ReplaceUniqueUtf8Value(resources, server_address, "DevAgent server address");
        File.WriteAllBytes(resources_path, resources);

        if ((!string.IsNullOrEmpty(access_token)
                && CountOccurrences(
                    resources,
                    Encoding.UTF8.GetBytes(access_token)) != 0)
            || (!string.IsNullOrEmpty(server_address)
                && CountOccurrences(
                    resources,
                    Encoding.UTF8.GetBytes(server_address)) != 0))
        {
            throw new InvalidDataException(
                "DevAgent data remained in the Windows build after sanitization.");
        }

        Debug.Log(
            "Windows build resources sanitized: local DevAgent token/address removed.");
    }

    private static string ReadYamlValue(string text, string key)
    {
        Match match = Regex.Match(
            text,
            "^  " + Regex.Escape(key) + @":\s*(.*)$",
            RegexOptions.Multiline);
        if (!match.Success)
        {
            throw new InvalidDataException(
                "DevAgent settings have no " + key + " field.");
        }
        return match.Groups[1].Value.Trim();
    }

    private static void ReplaceUniqueUtf8Value(
        byte[] data,
        string value,
        string label)
    {
        if (string.IsNullOrEmpty(value))
        {
            return;
        }

        byte[] needle = Encoding.UTF8.GetBytes(value);
        int count = 0;
        int match_index = -1;
        for (int index = 0; index <= data.Length - needle.Length; index++)
        {
            bool matches = true;
            for (int offset = 0; offset < needle.Length; offset++)
            {
                if (data[index + offset] != needle[offset])
                {
                    matches = false;
                    break;
                }
            }
            if (!matches)
            {
                continue;
            }
            count += 1;
            match_index = index;
            index += needle.Length - 1;
        }

        if (count != 1)
        {
            throw new InvalidDataException(
                label + " occurrence count in resources.assets was "
                + count + "; refusing to publish the build.");
        }

        for (int offset = 0; offset < needle.Length; offset++)
        {
            data[match_index + offset] = (byte)'0';
        }
    }

    private static int CountOccurrences(byte[] data, byte[] needle)
    {
        if (needle == null || needle.Length == 0)
        {
            return 0;
        }

        int count = 0;
        for (int index = 0; index <= data.Length - needle.Length; index++)
        {
            bool matches = true;
            for (int offset = 0; offset < needle.Length; offset++)
            {
                if (data[index + offset] != needle[offset])
                {
                    matches = false;
                    break;
                }
            }
            if (matches)
            {
                count += 1;
                index += needle.Length - 1;
            }
        }
        return count;
    }
}
