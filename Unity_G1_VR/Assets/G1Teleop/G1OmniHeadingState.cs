using System;
using System.Collections.Generic;

/// <summary>Omni input validation and unwrapped yaw; no transforms or robot transport.</summary>
public sealed class G1OmniHeadingState
{
    // Freshness is diagnostic only: stationary Omni may stop publishing.
    // Hold the last heading without pausing upper-body tracking or IK.
    public const double StaleSeconds = .50;
    public double Degrees { get; private set; }
    public double LastReceipt { get; private set; } = double.NegativeInfinity;
    private string session;
    private double sequence = -1, stamp, yaw;
    private readonly HashSet<string> retired = new HashSet<string>();

    public static double Delta(double current, double previous)
        => ((current - previous) % 360 + 540) % 360 - 180;

    // The imported G1 model's visible forward direction uses the same signed
    // yaw observed from Omni. Keep this conversion explicit and testable.
    public static double ToUnityYawDelta(double omniYawDelta)
        => omniYawDelta;

    private static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);

    public bool Accept(string id, double[] sample, double receipt)
    {
        if (string.IsNullOrEmpty(id) || id.Length > 64 || sample == null || sample.Length != 3 ||
            !Finite(receipt) || !Finite(sample[0]) || !Finite(sample[1]) || !Finite(sample[2]) ||
            sample[0] < 0 || sample[0] > 9007199254740991d || sample[0] != Math.Floor(sample[0]) || sample[1] < 0 ||
            receipt < LastReceipt || retired.Contains(id)) return false;
        bool changed = id != session;
        if (!changed && (sample[0] <= sequence || sample[1] <= stamp)) return false;
        // Only a source restart rebases. A silent stationary interval must not
        // discard the first subsequent heading change.
        bool rebase = changed;
        double step = Delta(sample[2], yaw);
        if (!rebase && Math.Abs(step) > Math.Min(180, 720 * (sample[1] - stamp) + 2)) return false;
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
