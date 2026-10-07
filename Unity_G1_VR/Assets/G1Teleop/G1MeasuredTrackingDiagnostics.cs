using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Newtonsoft.Json;
using UnityEngine;

/// <summary>Read-only measured/command comparison. Never alters IK, engagement, or robot commands.</summary>
public sealed class G1MeasuredTrackingDiagnostics : IDisposable
{
    private StreamWriter writer;
    private double nextSample;
    private double nextFlush;
    private bool disabled;
    public string LogPath { get; private set; }

    public static Dictionary<string, object> BuildRecord(
        G1LowStateLegView receiver, G1BimanualCommandFrame commandFrame,
        G1BimanualSimulationSender sender, Transform measuredLeft, Transform measuredRight,
        bool measuredApplied, double now)
    {
        var measured = receiver == null ? null : receiver.LatestState;
        bool measuredFresh = receiver != null && receiver.IsFreshAt(now);
        bool commandFresh = sender != null && sender.HasFreshJoints;
        var command = sender == null ? null : sender.LatestJoints;
        bool comparable = measuredApplied && measuredFresh && commandFresh
            && measured != null && command != null && command.Length == 14;
        float[] jointError = null;
        double? maximumError = null;
        if (comparable)
        {
            jointError = new float[14];
            double maximum = 0;
            for (int i = 0; i < 14; ++i)
            {
                jointError[i] = measured.q_rad[15 + i] - command[i];
                maximum = Math.Max(maximum, Math.Abs(jointError[i]));
            }
            maximumError = maximum;
        }
        Vector3 leftGoal = Vector3.zero, rightGoal = Vector3.zero;
        bool leftGoalValid = sender != null && sender.TryGetRequestedWorldTarget(true, out leftGoal);
        bool rightGoalValid = sender != null && sender.TryGetRequestedWorldTarget(false, out rightGoal);
        var record = new Dictionary<string, object> {
            ["schema"] = "g1.measured_tracking.diagnostic.v1",
            ["diagnostics_only"] = true,
            ["unity_receipt_clock_s"] = now,
            ["coordinate_frame"] = "unity_fixed_base_omni_yaw",
            ["absolute_robot_world_pose_available"] = false,
            ["measured_applied"] = measuredApplied,
            ["measured_fresh"] = measuredFresh,
            ["command_fresh"] = commandFresh,
            ["comparison_valid"] = comparable,
            ["measured_session"] = measured == null ? null : measured.session,
            ["measured_sequence"] = measured == null ? (long?)null : measured.sequence,
            ["measured_source_monotonic_s"] = measured == null ? (double?)null : measured.source_monotonic_s,
            ["measured_receipt_age_s"] = measured == null ? (double?)null : Math.Max(0, now - receiver.ReceivedAt),
            ["measured_excess_transport_delay_s"] = measured == null ? (double?)null : measured.age_s,
            ["absolute_transport_latency_available"] = false,
            ["command_backend_id"] = sender == null ? null : sender.CommandBackendId,
            ["command_feedback_sequence"] = sender == null ? (long?)null : sender.CommandFeedbackSequence,
            ["command_receipt_age_s"] = sender == null || command == null ? (double?)null
                : Math.Max(0, now - sender.CommandReceivedAt),
            ["q_measured_rad"] = measured == null ? null : (float[])measured.q_rad.Clone(),
            ["dq_measured_rad_s"] = measured == null ? null : (float[])measured.dq_rad_s.Clone(),
            ["q_command_rad"] = command == null ? null : (float[])command.Clone(),
            ["arm_measured_minus_command_rad"] = jointError,
            ["maximum_arm_joint_error_rad"] = maximumError,
            ["left_measured_fk_world_m"] = measuredApplied && measuredLeft != null ? V3(measuredLeft.position) : null,
            ["right_measured_fk_world_m"] = measuredApplied && measuredRight != null ? V3(measuredRight.position) : null,
            ["left_command_fk_world_m"] = commandFrame == null ? null : V3(commandFrame.LeftWrist.position),
            ["right_command_fk_world_m"] = commandFrame == null ? null : V3(commandFrame.RightWrist.position),
            ["left_requested_ik_goal_world_m"] = leftGoalValid ? V3(leftGoal) : null,
            ["right_requested_ik_goal_world_m"] = rightGoalValid ? V3(rightGoal) : null,
            ["left_measured_to_command_fk_m"] = comparable && commandFrame != null && measuredLeft != null
                ? (double?)Vector3.Distance(measuredLeft.position, commandFrame.LeftWrist.position) : null,
            ["right_measured_to_command_fk_m"] = comparable && commandFrame != null && measuredRight != null
                ? (double?)Vector3.Distance(measuredRight.position, commandFrame.RightWrist.position) : null,
            ["left_measured_to_requested_goal_m"] = comparable && leftGoalValid && measuredLeft != null
                ? (double?)Vector3.Distance(measuredLeft.position, leftGoal) : null,
            ["right_measured_to_requested_goal_m"] = comparable && rightGoalValid && measuredRight != null
                ? (double?)Vector3.Distance(measuredRight.position, rightGoal) : null,
            ["alignment_interpretation"] = "Latest receipt-time snapshots, not synchronized latency or physical stopping proof"
        };
        return record;
    }

    private static float[] V3(Vector3 value) => new[] { value.x, value.y, value.z };

    public void Sample(G1LowStateLegView receiver, G1BimanualCommandFrame commandFrame,
        G1BimanualSimulationSender sender, Transform left, Transform right, bool applied)
    {
        if (!Application.isPlaying || disabled) return;
        double now = Time.realtimeSinceStartupAsDouble;
        if (now < nextSample) return;
        nextSample = now + 0.2; // 5 Hz diagnostics; never a control input or extra worker.
        try
        {
            if (writer == null)
            {
                string folder = Path.GetFullPath(Path.Combine(Application.dataPath,
                    "../../logs/test_results/measured_tracking"));
                Directory.CreateDirectory(folder);
                LogPath = Path.Combine(folder, "unity_measured_" + DateTime.Now.ToString("yyyyMMdd_HHmmss")
                    + "_" + Guid.NewGuid().ToString("N") + ".jsonl");
                writer = new StreamWriter(new FileStream(LogPath, FileMode.CreateNew,
                    FileAccess.Write, FileShare.Read), new UTF8Encoding(false));
                Debug.Log("[G1 MEASURED DIAGNOSTICS] " + LogPath);
            }
            writer.WriteLine(JsonConvert.SerializeObject(
                BuildRecord(receiver, commandFrame, sender, left, right, applied, now)));
            if (now >= nextFlush) { writer.Flush(); nextFlush = now + 1; }
        }
        catch (Exception error) when (error is IOException || error is UnauthorizedAccessException
            || error is JsonException)
        {
            disabled = true;
            Debug.LogWarning("[G1 MEASURED DIAGNOSTICS] disabled: " + error.Message);
            Dispose(); // Diagnostics failure must not change command/state-machine behavior.
        }
    }

    public void Dispose()
    {
        try { writer?.Dispose(); }
        catch (IOException) { }
        finally { writer = null; }
    }
}
