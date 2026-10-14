using System;
using System.Globalization;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

[InitializeOnLoad]
public static class G1TeleopAutoPlay
{
    private const string request_file_name = "G1TeleopAutoPlay.request";
    private const string teleop_scene = "Assets/Scenes/SampleScene.unity";
    private const long startup_grace_seconds = 120;
    private const long max_future_skew_seconds = 30;
    // Process start survives domain reloads and long first imports. An old request
    // from a previous Editor session must not trigger Play after a later restart.
    private static readonly long editor_started_at = new DateTimeOffset(
        System.Diagnostics.Process.GetCurrentProcess().StartTime.ToUniversalTime()).ToUnixTimeSeconds();

    static G1TeleopAutoPlay()
    {
        EditorApplication.update += TryConsumeRequest;
        EditorApplication.quitting += CancelPendingRequest;
    }

    internal static bool RequestIsCurrent(string text, long now, long process_started_at)
    {
        long requested_at;
        return long.TryParse(text.Trim(), NumberStyles.Integer,
                   CultureInfo.InvariantCulture, out requested_at)
            && requested_at >= process_started_at - startup_grace_seconds
            && requested_at <= now + max_future_skew_seconds;
    }

    private static string RequestPath()
    {
        return Path.Combine(Directory.GetParent(Application.dataPath).FullName,
            "Library", request_file_name);
    }

    private static void CancelPendingRequest()
    {
        try { File.Delete(RequestPath()); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }

    private static void TryConsumeRequest()
    {
        if (EditorApplication.isCompiling || EditorApplication.isUpdating) return;
        string request_path = RequestPath();
        if (!File.Exists(request_path)) return;
        string text;
        try
        {
            text = File.ReadAllText(request_path);
            // Consume once, including cancel/failure. A new BAT invocation can retry.
            File.Delete(request_path);
        }
        catch (IOException) { return; }
        catch (UnauthorizedAccessException) { return; }

        long now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        if (!RequestIsCurrent(text, now, editor_started_at))
        {
            Debug.LogWarning("[G1 AUTO PLAY] Invalid or previous-session request removed; Play was not started.");
            return;
        }
        if (EditorApplication.isPlayingOrWillChangePlaymode)
        {
            Debug.Log("[G1 AUTO PLAY] Already playing; current scene preserved.");
            return;
        }
        if (EditorUtility.scriptCompilationFailed)
        {
            Debug.LogError("[G1 AUTO PLAY] Script compilation failed. Fix Console errors and run the launcher again.");
            return;
        }
        if (AssetDatabase.LoadAssetAtPath<SceneAsset>(teleop_scene) == null)
        {
            Debug.LogError("[G1 AUTO PLAY] Missing " + teleop_scene + "; Play was not started.");
            return;
        }
        try
        {
            // Build Settings do not select the Editor scene on a fresh clone.
            // Preserve user edits through Unity's normal save/discard/cancel dialog.
            if (SceneManager.sceneCount != 1 || SceneManager.GetActiveScene().path != teleop_scene)
            {
                if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
                {
                    Debug.LogWarning("[G1 AUTO PLAY] Scene switch cancelled; rerun the launcher when ready.");
                    return;
                }
                EditorSceneManager.OpenScene(teleop_scene, OpenSceneMode.Single);
            }
            if (SceneManager.sceneCount != 1 || SceneManager.GetActiveScene().path != teleop_scene)
                throw new InvalidOperationException("Teleop scene did not become active.");
            Debug.Log("[G1 AUTO PLAY] Import complete, SampleScene ready; starting Play mode.");
            EditorApplication.isPlaying = true;
        }
        catch (Exception error)
        {
            Debug.LogError("[G1 AUTO PLAY] Scene preparation failed; Play was not started. " + error.Message);
        }
    }
}
