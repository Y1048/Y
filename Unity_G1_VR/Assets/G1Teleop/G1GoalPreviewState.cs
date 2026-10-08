using System;
using UnityEngine;

/// <summary>
/// Wrist FK of the checked joint command in the same backend feedback packet.
/// This is the exported IK command target, not a separate geometric solution
/// or measured physical motion. The class name is retained for scene compatibility.
/// </summary>
public static class G1GoalPreviewState
{
    public const string Schema = "g1.bimanual.command.target.v1";
    public const double MaximumAgeSeconds = 0.20;

    [Serializable]
    public sealed class Frame
    {
        public string schema, status;
        public bool valid;
        public long source_sequence, feedback_sequence;
        public double age_s;
        public float[] left_world_m, right_world_m;
        public float[] left_world_wxyz, right_world_wxyz;
    }

    private static bool Finite(double value)
        => !double.IsNaN(value) && !double.IsInfinity(value);

    private static bool Vector(float[] value, int count)
    {
        if (value == null || value.Length != count) return false;
        foreach (float item in value) if (!Finite(item)) return false;
        return true;
    }

    private static bool Rotation(float[] value)
    {
        if (!Vector(value, 4)) return false;
        double norm = 0;
        foreach (float item in value) norm += (double)item * item;
        return Math.Abs(norm - 1) < 0.001;
    }

    public static bool Valid(Frame value)
        => value != null && value.schema == Schema && value.valid
            && value.status == "checked_command_fk"
            && value.source_sequence >= 0 && value.source_sequence <= 9007199254740991L
            && value.feedback_sequence >= 0 && value.feedback_sequence <= 9007199254740991L
            && Finite(value.age_s) && value.age_s >= 0
            && value.age_s <= MaximumAgeSeconds
            && Vector(value.left_world_m, 3) && Vector(value.right_world_m, 3)
            && Rotation(value.left_world_wxyz) && Rotation(value.right_world_wxyz);

    public static bool Fresh(Frame value, double received, double now)
        => Valid(value) && Finite(received) && Finite(now) && now >= received
            && value.age_s + now - received <= MaximumAgeSeconds;

    public static bool ValidForFeedback(Frame value, long sourceSequence, long feedbackSequence)
        => Valid(value) && value.source_sequence == sourceSequence
            && value.feedback_sequence == feedbackSequence;

    public static Vector3 Position(Frame value, bool left)
    {
        float[] p = left ? value.left_world_m : value.right_world_m;
        return new Vector3(p[0], p[1], p[2]);
    }

    public static Quaternion RightRotation(Frame value)
    {
        float[] q = value.right_world_wxyz;
        return new Quaternion(q[1], q[2], q[3], q[0]);
    }
}
