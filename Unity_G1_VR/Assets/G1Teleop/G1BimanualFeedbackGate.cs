using System;

/// <summary>Orders feedback from Python instances on the same loopback host.</summary>
public sealed class G1BimanualFeedbackGate
{
    public string BackendId { get; private set; }
    public long StartedNs { get; private set; }
    public long StateSequence { get; private set; } = -1;
    public long InputSequence { get; private set; } = -1;

    public bool Accept(string id, long startedNs, long stateSequence,
        long inputSequence, long nextInputSequence, out bool restarted)
    {
        restarted = false;
        Guid parsed;
        if (!Guid.TryParseExact(id, "N", out parsed) || startedNs <= 0 ||
            stateSequence < 0 || inputSequence < 0 || inputSequence >= nextInputSequence)
            return false;
        if (BackendId != null)
        {
            if (id == BackendId)
            {
                if (startedNs != StartedNs || stateSequence <= StateSequence ||
                    inputSequence < InputSequence) return false;
            }
            else
            {
                // Also reject delayed feedback from an instance never observed
                // before this one. This is ordering, not Unity/Python clock subtraction.
                if (startedNs <= StartedNs) return false;
                restarted = true;
            }
        }
        BackendId = id;
        StartedNs = startedNs;
        StateSequence = stateSequence;
        InputSequence = inputSequence;
        return true;
    }
}
