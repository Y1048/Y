using System;
using UnityEngine;

/// <summary>Versioned idle-start handshake, not continuous measured IK feedback.</summary>
public static class G1MeasuredStartState
{
    public const string InputSchema = "g1.bimanual.unity.sim.v5";
    public const double MaximumAgeSeconds = .10;

    [Serializable] public sealed class Snapshot
    {
        public string schema = "g1.lowstate.view.v1";
        public string session;
        public long sequence;
        public double source_monotonic_s, receipt_age_s;
        public bool crc_valid;
        public string[] joint_names;
        public float[] q_rad, dq_rad_s;
    }

    [Serializable] public sealed class Acknowledgement
    {
        public bool ready;
        public long revision;
        public string reason, session;
        public float[] body_q_rad;
    }

    public static Snapshot Capture(G1LowStateLegView receiver, double now)
    {
        var value = receiver == null ? null : receiver.LatestState;
        if (value == null || !receiver.IsFreshAt(now)) return null;
        double age = now - receiver.ReceivedAt + value.age_s;
        if (age < 0 || age > MaximumAgeSeconds) return null;
        return new Snapshot {
            session = value.session, sequence = value.sequence,
            source_monotonic_s = value.source_monotonic_s, receipt_age_s = age,
            crc_valid = value.crc_valid, joint_names = (string[])value.joint_names.Clone(),
            q_rad = (float[])value.q_rad.Clone(), dq_rad_s = (float[])value.dq_rad_s.Clone()
        };
    }

    public static bool Valid(Acknowledgement value)
    {
        if (value == null || value.revision < 0 || value.revision > 9007199254740991L
            || string.IsNullOrEmpty(value.reason) || value.reason.Length > 128) return false;
        if (value.revision == 0)
            // JsonUtility maps explicit JSON null strings/arrays to empty values.
            // This is an uninitialized acknowledgement only; it cannot engage.
            return !value.ready && string.IsNullOrEmpty(value.session)
                && (value.body_q_rad == null || value.body_q_rad.Length == 0);
        if (string.IsNullOrEmpty(value.session) || value.session.Length > 64
            || value.body_q_rad == null || value.body_q_rad.Length != 15) return false;
        foreach (float q in value.body_q_rad)
            if (float.IsNaN(q) || float.IsInfinity(q)) return false;
        return true;
    }

    public static bool CanEngage(Acknowledgement value, long preparedRevision,
        Snapshot current, bool commandFresh)
        => Valid(value) && value.ready && value.revision > 0
            && preparedRevision == value.revision && commandFresh
            && current != null && current.session == value.session
            && current.receipt_age_s <= MaximumAgeSeconds;
}
