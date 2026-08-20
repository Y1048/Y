using UnityEngine;

public class G1GameHudOverlay : MonoBehaviour
{
    public static G1GameHudOverlay Active { get; private set; }

    public G1HandPoseUdpSender sender;
    public G1Quest3SXRHandsInput questHandsInput;

    GUIStyle title_style;
    GUIStyle label_style;
    GUIStyle small_label_style;
    Texture2D red_texture;
    Texture2D green_texture;
    Texture2D blue_texture;
    Texture2D white_texture;
    Texture2D black_texture;
    Texture2D panel_texture;
    Texture2D grid_texture;

    void OnEnable()
    {
        Active = this;
    }

    void OnDisable()
    {
        if (Active == this)
            Active = null;
    }

    void OnGUI()
    {
        if (sender == null)
            sender = G1HandPoseUdpSender.Active;
        if (questHandsInput == null)
            questHandsInput = G1Quest3SXRHandsInput.Active;
        if (sender == null)
            return;

        EnsureStyles();

        Rect panel_rect = new Rect(Screen.width - 620.0f, 18.0f, 600.0f, 520.0f);
        GUI.DrawTexture(panel_rect, panel_texture);

        Vector3 hand_delta = sender.RightHandDelta;
        Vector3 robot_delta = sender.RightTarget - sender.rightRobotCenter;
        Vector3 sensitivity = sender.handToRobotScale;
        string tracking_status = "NOT TRACKED";
        if (questHandsInput != null && questHandsInput.RightTracked)
            tracking_status = "TRACKED";
        else if (sender.RightTrackingHeld)
            tracking_status = "HOLD";
        else if (!sender.RightValid)
            tracking_status = "LOST";
        string workspace_status = sender.RightWorkspaceLimited ? "LIMIT" : "OK";
        string speed_status = sender.RightSpeedLimited ? "LIMIT" : "OK";

        GUI.Label(new Rect(panel_rect.x + 20.0f, panel_rect.y + 14.0f, 560.0f, 34.0f), "G1 Quest Hand Debug", title_style);
        GUI.Label(new Rect(panel_rect.x + 20.0f, panel_rect.y + 54.0f, 270.0f, 26.0f), $"Right hand: {tracking_status}", label_style);
        GUI.Label(new Rect(panel_rect.x + 300.0f, panel_rect.y + 54.0f, 270.0f, 26.0f), $"Mode: {sender.inputMode}", label_style);

        GUI.Label(new Rect(panel_rect.x + 20.0f, panel_rect.y + 86.0f, 560.0f, 24.0f), $"Raw hand delta xyz: {hand_delta.x:F2}, {hand_delta.y:F2}, {hand_delta.z:F2}", small_label_style);
        GUI.Label(new Rect(panel_rect.x + 20.0f, panel_rect.y + 114.0f, 560.0f, 24.0f), $"G1 target xyz: {sender.RightTarget.x:F2}, {sender.RightTarget.y:F2}, {sender.RightTarget.z:F2}", small_label_style);
        GUI.Label(new Rect(panel_rect.x + 20.0f, panel_rect.y + 142.0f, 560.0f, 24.0f), $"Center xyz: {sender.rightRobotCenter.x:F2}, {sender.rightRobotCenter.y:F2}, {sender.rightRobotCenter.z:F2}", small_label_style);
        GUI.Label(new Rect(panel_rect.x + 20.0f, panel_rect.y + 166.0f, 560.0f, 24.0f), $"Robot delta xyz: {robot_delta.x:F2}, {robot_delta.y:F2}, {robot_delta.z:F2} | F/H/V: {sensitivity.x:F2}, {sensitivity.y:F2}, {sensitivity.z:F2} | Smooth: {sender.positionAlpha:F2}", small_label_style);
        GUI.Label(new Rect(panel_rect.x + 20.0f, panel_rect.y + 190.0f, 560.0f, 24.0f), $"Workspace: {workspace_status} | Speed: {speed_status} max {sender.maxTargetSpeed:F2} m/s", small_label_style);

        Rect front_rect = new Rect(panel_rect.x + 20.0f, panel_rect.y + 222.0f, 260.0f, 170.0f);
        Rect side_rect = new Rect(panel_rect.x + 320.0f, panel_rect.y + 222.0f, 260.0f, 170.0f);
        DrawMap(front_rect, "Front view  right/up", -hand_delta.x, hand_delta.y, -robot_delta.y, robot_delta.z);
        DrawMap(side_rect, "Side view  forward/up", -hand_delta.z, hand_delta.y, robot_delta.x, robot_delta.z);

        Rect arm_rect = new Rect(panel_rect.x + 20.0f, panel_rect.y + 402.0f, 560.0f, 58.0f);
        DrawArmPreview(arm_rect, robot_delta);

        DrawSensitivityButtons(new Rect(panel_rect.x + 20.0f, panel_rect.y + 466.0f, 560.0f, 32.0f));
        GUI.Label(new Rect(panel_rect.x + 20.0f, panel_rect.y + 498.0f, 560.0f, 20.0f), "Keys: F -/+ = -/=, H -/+ = ,/., V -/+ = [/], S -/+ = ;/' | C calibrate", small_label_style);
    }

    void DrawSensitivityButtons(Rect rect)
    {
        float button_width = 62.0f;
        float gap = 6.0f;
        float x = rect.x;

        if (GUI.Button(new Rect(x, rect.y, button_width, rect.height), "F-"))
            sender.AddForwardSensitivity(-0.05f);
        x += button_width + gap;
        if (GUI.Button(new Rect(x, rect.y, button_width, rect.height), "F+"))
            sender.AddForwardSensitivity(0.05f);
        x += button_width + gap;

        if (GUI.Button(new Rect(x, rect.y, button_width, rect.height), "H-"))
            sender.AddHorizontalSensitivity(-0.05f);
        x += button_width + gap;
        if (GUI.Button(new Rect(x, rect.y, button_width, rect.height), "H+"))
            sender.AddHorizontalSensitivity(0.05f);
        x += button_width + gap;

        if (GUI.Button(new Rect(x, rect.y, button_width, rect.height), "V-"))
            sender.AddVerticalSensitivity(-0.05f);
        x += button_width + gap;
        if (GUI.Button(new Rect(x, rect.y, button_width, rect.height), "V+"))
            sender.AddVerticalSensitivity(0.05f);
        x += button_width + gap;

        if (GUI.Button(new Rect(x, rect.y, button_width, rect.height), "S-"))
            sender.AddSmoothing(-0.02f);
        x += button_width + gap;
        if (GUI.Button(new Rect(x, rect.y, button_width, rect.height), "S+"))
            sender.AddSmoothing(0.02f);
        x += button_width + gap;

        if (GUI.Button(new Rect(x, rect.y, 92.0f, rect.height), "Calib"))
            sender.Calibrate();
    }

    void DrawMap(Rect map_rect, string title, float hand_horizontal, float hand_vertical, float target_horizontal, float target_vertical)
    {
        GUI.DrawTexture(map_rect, grid_texture);
        GUI.Box(map_rect, "");
        GUI.Label(new Rect(map_rect.x + 10.0f, map_rect.y + 8.0f, map_rect.width - 20.0f, 24.0f), title, small_label_style);

        DrawLine(new Vector2(map_rect.center.x, map_rect.y + 34.0f), new Vector2(map_rect.center.x, map_rect.yMax - 14.0f), white_texture, 1.0f);
        DrawLine(new Vector2(map_rect.x + 12.0f, map_rect.center.y), new Vector2(map_rect.xMax - 12.0f, map_rect.center.y), white_texture, 1.0f);

        Vector2 hand_point = new Vector2(
            map_rect.center.x + Mathf.Clamp(hand_horizontal, -0.45f, 0.45f) * 190.0f,
            map_rect.center.y - Mathf.Clamp(hand_vertical, -0.35f, 0.35f) * 190.0f
        );
        Vector2 target_point = new Vector2(
            map_rect.center.x + Mathf.Clamp(target_horizontal, -0.30f, 0.30f) * 260.0f,
            map_rect.center.y - Mathf.Clamp(target_vertical, -0.30f, 0.30f) * 260.0f
        );

        DrawDot(hand_point, 18.0f, red_texture);
        DrawDot(target_point, 20.0f, green_texture);
    }

    void DrawArmPreview(Rect arm_rect, Vector3 robot_delta)
    {
        GUI.DrawTexture(arm_rect, grid_texture);
        GUI.Box(arm_rect, "");

        Vector2 shoulder_point = new Vector2(arm_rect.x + 90.0f, arm_rect.center.y);
        Vector2 wrist_point = new Vector2(
            arm_rect.x + 410.0f + Mathf.Clamp(robot_delta.x, -0.25f, 0.25f) * 160.0f,
            arm_rect.center.y - Mathf.Clamp(robot_delta.z, -0.25f, 0.25f) * 110.0f
        );
        Vector2 elbow_point = Vector2.Lerp(shoulder_point, wrist_point, 0.55f) + new Vector2(0.0f, 34.0f);

        DrawLine(shoulder_point, elbow_point, white_texture, 8.0f);
        DrawLine(elbow_point, wrist_point, white_texture, 8.0f);
        DrawDot(shoulder_point, 18.0f, blue_texture);
        DrawDot(elbow_point, 18.0f, red_texture);
        DrawDot(wrist_point, 22.0f, green_texture);
    }

    void DrawDot(Vector2 center, float size, Texture2D texture)
    {
        GUI.DrawTexture(new Rect(center.x - size * 0.5f, center.y - size * 0.5f, size, size), texture);
    }

    void DrawLine(Vector2 start, Vector2 end, Texture2D texture, float width)
    {
        Matrix4x4 previous_matrix = GUI.matrix;
        Vector2 delta = end - start;
        float angle = Mathf.Atan2(delta.y, delta.x) * Mathf.Rad2Deg;
        GUIUtility.RotateAroundPivot(angle, start);
        GUI.DrawTexture(new Rect(start.x, start.y - width * 0.5f, delta.magnitude, width), texture);
        GUI.matrix = previous_matrix;
    }

    void EnsureStyles()
    {
        if (title_style == null)
        {
            title_style = new GUIStyle(GUI.skin.label);
            title_style.fontSize = 28;
            title_style.normal.textColor = Color.white;
            title_style.fontStyle = FontStyle.Bold;
        }

        if (label_style == null)
        {
            label_style = new GUIStyle(GUI.skin.label);
            label_style.fontSize = 21;
            label_style.normal.textColor = Color.white;
        }

        if (small_label_style == null)
        {
            small_label_style = new GUIStyle(GUI.skin.label);
            small_label_style.fontSize = 17;
            small_label_style.normal.textColor = Color.white;
        }

        if (panel_texture == null)
            panel_texture = CreateTexture(new Color(0.02f, 0.03f, 0.04f, 0.90f));
        if (grid_texture == null)
            grid_texture = CreateTexture(new Color(0.10f, 0.12f, 0.14f, 0.82f));
        if (red_texture == null)
            red_texture = CreateTexture(Color.red);
        if (green_texture == null)
            green_texture = CreateTexture(Color.green);
        if (blue_texture == null)
            blue_texture = CreateTexture(new Color(0.2f, 0.55f, 1.0f));
        if (white_texture == null)
            white_texture = CreateTexture(Color.white);
        if (black_texture == null)
            black_texture = CreateTexture(Color.black);
    }

    Texture2D CreateTexture(Color color)
    {
        Texture2D texture = new Texture2D(1, 1);
        texture.SetPixel(0, 0, color);
        texture.Apply();
        return texture;
    }
}
