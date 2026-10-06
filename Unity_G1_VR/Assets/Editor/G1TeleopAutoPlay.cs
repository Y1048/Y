using System;
using System.Globalization;
using System.IO;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class G1TeleopAutoPlay
{
    private const string request_file_name = "G1TeleopAutoPlay.request";
    private const long max_request_age_seconds = 120;
    private const long max_future_skew_seconds = 30;

    static G1TeleopAutoPlay()
    {
        EditorApplication.update += TryConsumeRequest;
    }

    private static void TryConsumeRequest()
    {
        if (EditorApplication.isCompiling || EditorApplication.isUpdating)
        {
            return;
        }

        string project_root = Directory.GetParent(Application.dataPath).FullName;
        string request_path = Path.Combine(
            project_root,
            "Library",
            request_file_name);
        if (!File.Exists(request_path))
        {
            return;
        }

        string text;
        try
        {
            text = File.ReadAllText(request_path).Trim();
        }
        catch (IOException)
        {
            return;
        }

        if (!long.TryParse(
                text,
                NumberStyles.Integer,
                CultureInfo.InvariantCulture,
                out long requested_at))
        {
            File.Delete(request_path);
            Debug.LogWarning(
                "[G1 AUTO PLAY] Invalid request removed; Play was not started.");
            return;
        }

        long now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        long age = now - requested_at;
        if (age > max_request_age_seconds || age < -max_future_skew_seconds)
        {
            File.Delete(request_path);
            Debug.LogWarning(
                "[G1 AUTO PLAY] Stale request removed; Play was not started.");
            return;
        }

        File.Delete(request_path);
        if (EditorApplication.isPlayingOrWillChangePlaymode)
        {
            Debug.Log("[G1 AUTO PLAY] Editor is already entering or in Play mode.");
            return;
        }

        Debug.Log("[G1 AUTO PLAY] Starting Play mode from launcher request.");
        EditorApplication.isPlaying = true;
    }
}
