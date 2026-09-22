using System;
using System.Collections.Generic;

/// <summary>View-only heading gate. No Unity transforms, IK, or robot transport.</summary>
public sealed class G1OmniHeadingState
{
    public const double StaleSeconds = .25;
    public double Degrees { get; private set; }
    public double LastReceipt { get; private set; } = double.NegativeInfinity;
    private string session;
    private double sequence = -1, stamp, yaw;
    private readonly HashSet<string> retired = new HashSet<string>();

    public static double Delta(double current, double previous)
        => ((current - previous) % 360 + 540) % 360 - 180;

    // Omni/G1 positive yaw is counter-clockwise (left) when viewed from above.
    // Unity's positive Y rotation turns the rendered forward direction right, so
    // the view transform must use the opposite sign to show the same body turn.
    public static double ToUnityYawDelta(double omniYawDelta)
        => -omniYawDelta;

    public static double TrackingCorrectionDegrees(
        double measuredRobotYawDelta,
        double operatorBodyYawDelta)
        => measuredRobotYawDelta - operatorBodyYawDelta;

    private static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);

    public bool Accept(string id, double[] sample, double receipt)
    {
        if (string.IsNullOrEmpty(id) || id.Length > 64 || sample == null || sample.Length != 3 ||
            !Finite(receipt) || !Finite(sample[0]) || !Finite(sample[1]) || !Finite(sample[2]) ||
            sample[0] < 0 || sample[0] > 9007199254740991d || sample[0] != Math.Floor(sample[0]) || sample[1] < 0 ||
            receipt < LastReceipt || retired.Contains(id)) return false;
        bool changed = id != session;
        if (!changed && (sample[0] <= sequence || sample[1] <= stamp)) return false;
        // A restart or tracking gap establishes a new origin without a view jump.
        bool rebase = changed || receipt - LastReceipt > StaleSeconds || sample[1] - stamp > StaleSeconds;
        double step = Delta(sample[2], yaw);
        if (!rebase && Math.Abs(step) > Math.Min(45, 720 * (sample[1] - stamp) + 2)) return false;
        if (changed && session != null)
        {
            if (retired.Count >= 64) return false;
            retired.Add(session);
        }
        if (!rebase) Degrees += step;
        session = id; sequence = sample[0]; stamp = sample[1]; yaw = sample[2]; LastReceipt = receipt;
        return true;
    }
}
