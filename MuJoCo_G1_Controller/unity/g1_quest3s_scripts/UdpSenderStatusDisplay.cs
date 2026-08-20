using UnityEngine;

public class UdpSenderStatusDisplay : MonoBehaviour
{
    public EditorTestUdpHandSender sender;
    public G1HandPoseUdpSender g1Sender;
    public G1Quest3SXRHandsInput questHandsInput;
    GUIStyle labelStyle;
    GUIStyle smallLabelStyle;
    GUIStyle buttonStyle;

    void OnGUI()
    {
        EnsureStyles();

        if (g1Sender != null)
        {
            DrawG1Panel();
            return;
        }

        DrawLegacyPanel();
    }

    void DrawG1Panel()
    {
        float panelWidth = Mathf.Min(Screen.width - 24, 640);
        GUILayout.BeginArea(new Rect(12, 12, panelWidth, 430), GUI.skin.box);

        GUILayout.Label($"G1 Quest 3S UDP Sender  |  Mode: {g1Sender.inputMode}", labelStyle);
        GUILayout.Label("Keys: 1 Manual, 2 Auto, 3 Quest, C Calibrate, R Reset", smallLabelStyle);
        GUILayout.Label(GetQuestHandsStatus(), smallLabelStyle);
        GUILayout.Label(GetRightTargetStatus(), smallLabelStyle);
        GUILayout.Label(GetRawHandStatus(), smallLabelStyle);

        GUILayout.BeginHorizontal();
        if (GUILayout.Button("Manual", buttonStyle, GUILayout.Height(52)))
            g1Sender.inputMode = G1HandPoseUdpSender.InputMode.ManualKeyboard;
        if (GUILayout.Button("Auto", buttonStyle, GUILayout.Height(52)))
            g1Sender.inputMode = G1HandPoseUdpSender.InputMode.AutoMotion;
        GUILayout.EndHorizontal();

        GUILayout.BeginHorizontal();
        if (GUILayout.Button("Quest", buttonStyle, GUILayout.Height(52)))
            g1Sender.inputMode = G1HandPoseUdpSender.InputMode.TransformSources;
        if (GUILayout.Button("Calibrate", buttonStyle, GUILayout.Height(52)))
            g1Sender.Calibrate();
        if (GUILayout.Button("Reset", buttonStyle, GUILayout.Height(52)))
            g1Sender.ResetTargets();
        GUILayout.EndHorizontal();

        GUILayout.BeginHorizontal();
        if (GUILayout.Button("Up X", buttonStyle, GUILayout.Height(44)))
            g1Sender.upAxis = G1HandPoseUdpSender.MappingAxis.X;
        if (GUILayout.Button("Up Y", buttonStyle, GUILayout.Height(44)))
            g1Sender.upAxis = G1HandPoseUdpSender.MappingAxis.Y;
        if (GUILayout.Button("Up Z", buttonStyle, GUILayout.Height(44)))
            g1Sender.upAxis = G1HandPoseUdpSender.MappingAxis.Z;
        if (GUILayout.Button("Flip Up", buttonStyle, GUILayout.Height(44)))
            g1Sender.invertUp = !g1Sender.invertUp;
        GUILayout.EndHorizontal();

        GUILayout.Label($"Up axis: {g1Sender.upAxis}, flip: {g1Sender.invertUp}", smallLabelStyle);
        GUILayout.Label($"Flip F/R/U: {g1Sender.invertForward}, {g1Sender.invertRight}, {g1Sender.invertUp}", smallLabelStyle);
        GUILayout.Label(GetSensitivityStatus(), smallLabelStyle);

        GUILayout.BeginHorizontal();
        if (GUILayout.Button("H -", buttonStyle, GUILayout.Height(40)))
            g1Sender.AddHorizontalSensitivity(-0.05f);
        if (GUILayout.Button("H +", buttonStyle, GUILayout.Height(40)))
            g1Sender.AddHorizontalSensitivity(0.05f);
        if (GUILayout.Button("V -", buttonStyle, GUILayout.Height(40)))
            g1Sender.AddVerticalSensitivity(-0.05f);
        if (GUILayout.Button("V +", buttonStyle, GUILayout.Height(40)))
            g1Sender.AddVerticalSensitivity(0.05f);
        GUILayout.EndHorizontal();

        GUILayout.BeginHorizontal();
        if (GUILayout.Button("F -", buttonStyle, GUILayout.Height(40)))
            g1Sender.AddForwardSensitivity(-0.05f);
        if (GUILayout.Button("F +", buttonStyle, GUILayout.Height(40)))
            g1Sender.AddForwardSensitivity(0.05f);
        GUILayout.EndHorizontal();

        GUILayout.Label("Manual move: W/S/A/D/Q/E, Shift = fast", smallLabelStyle);
        GUILayout.EndArea();
    }

    string GetQuestHandsStatus()
    {
        if (questHandsInput == null)
            return "Quest Link hand source: script not found";

        string subsystemStatus = questHandsInput.SubsystemRunning ? "XR Hands ON" : "XR Hands OFF";
        string rightStatus = questHandsInput.RightTracked ? "Right tracked" : "Right not tracked";
        string leftStatus = questHandsInput.LeftTracked ? "Left tracked" : "Left not tracked";
        return $"Quest Link hand source: {subsystemStatus} | {rightStatus} | {leftStatus}";
    }

    string GetRightTargetStatus()
    {
        Vector3 target = g1Sender.RightTarget;
        Vector3 center = g1Sender.rightRobotCenter;
        Vector3 delta = target - center;
        return $"Right target xyz: {target.x:F2}, {target.y:F2}, {target.z:F2} | delta: {delta.x:F2}, {delta.y:F2}, {delta.z:F2}";
    }

    string GetRawHandStatus()
    {
        Vector3 handDelta = g1Sender.RightHandDelta;
        Vector3 robotDelta = g1Sender.RightRobotDelta;
        return $"Raw hand delta xyz: {handDelta.x:F2}, {handDelta.y:F2}, {handDelta.z:F2} | robot delta xyz: {robotDelta.x:F2}, {robotDelta.y:F2}, {robotDelta.z:F2}";
    }

    string GetSensitivityStatus()
    {
        Vector3 scale = g1Sender.handToRobotScale;
        return $"Sensitivity F/H/V: {scale.x:F2}, {scale.y:F2}, {scale.z:F2}";
    }

    void DrawLegacyPanel()
    {
        string mode = sender != null && sender.autoMode ? "AUTO" : "MANUAL";
        float panelWidth = Mathf.Min(Screen.width - 24, 560);
        GUILayout.BeginArea(new Rect(12, 12, panelWidth, 170), GUI.skin.box);
        GUILayout.Label($"UDP target sender  |  Mode: {mode}", labelStyle);
        GUILayout.Label("Keys: T auto/manual, W/S/A/D/Q/E move, Shift fast, R reset", smallLabelStyle);

        GUILayout.BeginHorizontal();
        if (sender != null && GUILayout.Button("Toggle Auto", buttonStyle, GUILayout.Height(52)))
            sender.ToggleAutoMode();

        if (sender != null && GUILayout.Button("Reset", buttonStyle, GUILayout.Height(52)))
            sender.ResetTarget();
        GUILayout.EndHorizontal();
        GUILayout.EndArea();
    }

    void EnsureStyles()
    {
        if (labelStyle == null)
        {
            labelStyle = new GUIStyle(GUI.skin.label);
            labelStyle.fontSize = 22;
            labelStyle.normal.textColor = Color.white;
        }

        if (smallLabelStyle == null)
        {
            smallLabelStyle = new GUIStyle(GUI.skin.label);
            smallLabelStyle.fontSize = 18;
            smallLabelStyle.normal.textColor = Color.white;
            smallLabelStyle.wordWrap = true;
        }

        if (buttonStyle == null)
        {
            buttonStyle = new GUIStyle(GUI.skin.button);
            buttonStyle.fontSize = 22;
        }
    }
}
