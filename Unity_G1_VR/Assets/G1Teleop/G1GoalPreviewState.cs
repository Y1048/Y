using System;
using UnityEngine;

/// <summary>
/// Display-only checked goal prefix. Not a motor goal, a stopping endpoint,
/// a global workspace boundary, or measured physical motion.
/// </summary>
public static class G1GoalPreviewState
{
    public const string Schema = "g1.bimanual.goal.preview.v1";
    public const double MaximumAgeSeconds = 0.20;

    [Serializable]
    public sealed class Frame
    {
        public string schema, status;
        public bool valid;
        public int horizon_steps, accepted_steps, braking_steps;
        public long source_sequence;
        public double age_s, horizon_s, compute_ms;
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
            && (value.status == "checked_goal_prefix"
                || value.status == "checked_braking_prefix")
            && value.horizon_steps == 3 && value.accepted_steps == 3
            && value.braking_steps >= 0 && value.braking_steps <= 3
            && value.source_sequence >= 0 && value.source_sequence <= 9007199254740991L
            && Finite(value.age_s) && value.age_s >= 0
            && value.age_s <= MaximumAgeSeconds
            && Finite(value.horizon_s) && Math.Abs(value.horizon_s - 0.05) < 0.000001
            && Finite(value.compute_ms) && value.compute_ms >= 0
            && Vector(value.left_world_m, 3) && Vector(value.right_world_m, 3)
            && Rotation(value.left_world_wxyz) && Rotation(value.right_world_wxyz);

    public static bool Fresh(Frame value, double received, double now)
        => Valid(value) && Finite(received) && Finite(now) && now >= received
            && value.age_s + now - received <= MaximumAgeSeconds;

    public static bool ValidForSequence(Frame value, long commandSequence)
        => Valid(value) && value.source_sequence <= commandSequence;

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
