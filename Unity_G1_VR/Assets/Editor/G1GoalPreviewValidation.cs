using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using Newtonsoft.Json;
using UnityEditor;
using UnityEngine;

/// <summary>Command-FK marker decoding/source/freshness tests. No Play or control sockets.</summary>
public static class G1GoalPreviewValidation
{
    private const BindingFlags Private = BindingFlags.NonPublic | BindingFlags.Instance;
    private static int checks;
    private static void Assert(bool value, string reason)
    { ++checks; if (!value) throw new InvalidOperationException(reason); }
    private static void Set(object value, string name, object data)
        => value.GetType().GetField(name, Private).SetValue(value, data);
    private static void Property(object value, string name, object data)
        => value.GetType().GetProperty(name).SetValue(value, data);

    private static void Reject(G1GoalPreviewState.Frame valid,
        Action<G1GoalPreviewState.Frame> mutate, string reason)
    {
        var candidate = JsonUtility.FromJson<G1GoalPreviewState.Frame>(JsonUtility.ToJson(valid));
        mutate(candidate);
        Assert(!G1GoalPreviewState.Valid(candidate), reason);
    }

    public static void RunBatch()
    {
        string[] args = Environment.GetCommandLineArgs();
        int index = Array.IndexOf(args, "-g1GoalPreviewOutput");
        if (index < 0 || index + 1 >= args.Length) throw new InvalidOperationException("Output required");
        string output = args[index + 1];
        object report; bool passed = false;
        try
        {
            checks = 0;
            Assert(!EditorApplication.isPlayingOrWillChangePlaymode, "No Play allowed");
            object measured = typeof(G1MeasuredDisplayValidation).GetMethod("Validate",
                BindingFlags.NonPublic | BindingFlags.Static).Invoke(null, null);
            object start = typeof(G1MeasuredStartValidation).GetMethod("Validate",
                BindingFlags.NonPublic | BindingFlags.Static).Invoke(null,
                    new object[] { Path.GetDirectoryName(output) });
            Validate(Path.Combine(Path.GetDirectoryName(output), "unity_command_target_packet.json"));
            report = new { passed = true, command_target_checks = checks,
                measured_display_validation = measured, measured_start_validation = start,
                play_mode = false, control_sockets_created = false,
                unity_version = Application.unityVersion, utc = DateTime.UtcNow.ToString("O") };
            passed = true;
        }
        catch (Exception error) { report = new { passed = false, checks, error = error.ToString() }; }
        Directory.CreateDirectory(Path.GetDirectoryName(output));
        File.WriteAllText(output, JsonConvert.SerializeObject(report, Formatting.Indented));
        Debug.Log("[COMMAND TARGET VALIDATION] " + (passed ? "PASS" : "FAIL"));
        EditorApplication.Exit(passed ? 0 : 1);
    }

    private static void Validate(string path)
    {
        var host = new GameObject("Command target validation host");
        host.SetActive(false);
        try
        {
            var sender = host.AddComponent<G1BimanualSimulationSender>();
            sender.useExistingScene = true;
            var left = new GameObject("left"); left.transform.SetParent(host.transform);
            var right = new GameObject("right"); right.transform.SetParent(host.transform);
            sender.leftBinder = left.AddComponent<G1ExistingHandTargetBinder>();
            sender.rightBinder = right.AddComponent<G1ExistingHandTargetBinder>();
            var feedbackType = typeof(G1BimanualSimulationSender).GetNestedType("Feedback", BindingFlags.NonPublic);
            var decoded = JsonUtility.FromJson(File.ReadAllText(path), feedbackType);
            var frame = (G1GoalPreviewState.Frame)feedbackType.GetField("command_target").GetValue(decoded);
            long sourceSequence = (long)feedbackType.GetField("sequence").GetValue(decoded);
            long commandSequence = (long)feedbackType.GetField("feedback_sequence").GetValue(decoded);
            Assert(G1GoalPreviewState.Valid(frame), "Python payload did not decode into the command FK frame");
            Assert(G1GoalPreviewState.ValidForFeedback(frame,sourceSequence,commandSequence), "Own command FK rejected");
            Assert(!G1GoalPreviewState.ValidForFeedback(frame,sourceSequence-1,commandSequence), "Different input source accepted");
            Assert(!G1GoalPreviewState.ValidForFeedback(frame,sourceSequence,commandSequence-1), "Different command frame accepted");
            float[] command = (float[])feedbackType.GetField("q_rad").GetValue(decoded);
            Property(sender, "LatestJoints", command);
            Property(sender, "CommandFeedbackSequence", commandSequence);
            Set(sender, "feedbackSequence", sourceSequence);
            Set(sender, "lastFeedback", Time.realtimeSinceStartupAsDouble);
            Set(sender, "active", true); Set(sender, "backendState", "tracking");
            Set(sender, "commandTarget", frame); Set(sender, "commandTargetReceived", Time.realtimeSinceStartupAsDouble);
            Set(sender, "leftWorldTarget", new Vector3(9,8,7));
            Set(sender, "rightWorldTarget", new Vector3(-9,-8,-7));
            var packetType = typeof(G1BimanualSimulationSender).GetNestedType("Packet", BindingFlags.NonPublic);
            var packet = Activator.CreateInstance(packetType); Set(sender, "packet", packet);
            string before = JsonUtility.ToJson(packet);
            Assert(sender.TryGetIkTarget(true, out Vector3 l)
                && Vector3.Distance(l, G1GoalPreviewState.Position(frame,true)) < 1e-6f, "Wrong left marker source");
            Assert(sender.TryGetIkTarget(false, out Vector3 r)
                && Vector3.Distance(r, G1GoalPreviewState.Position(frame,false)) < 1e-6f, "Wrong right marker source");
            Assert(sender.TryGetRightIkRotation(out Quaternion rotation)
                && Quaternion.Angle(rotation,G1GoalPreviewState.RightRotation(frame)) < .01f, "Command position/rotation source mismatch");
            Assert(JsonUtility.ToJson(packet) == before, "Goal display modified outgoing controls");
            Assert(ReferenceEquals(sender.LatestJoints,command), "Goal display replaced live joint command");
            Property(sender,"CommandFeedbackSequence",commandSequence+1);
            Assert(!sender.TryGetIkTarget(true,out _), "FK from another q frame was shown");
            Assert(!sender.TryGetRightIkRotation(out _), "Rotation from another q frame was shown");
            Property(sender,"CommandFeedbackSequence",commandSequence);
            Set(sender,"commandTargetReceived",Time.realtimeSinceStartupAsDouble-1);
            Assert(!sender.TryGetIkTarget(true,out _), "Expired marker was shown");
            Assert(!sender.TryGetRightIkRotation(out _), "Expired orientation was shown");
            Set(sender,"commandTarget",null);
            Assert(!sender.TryGetIkTarget(false,out _), "Missing goal fell back to a stop or raw target");
            Set(sender,"commandTarget",frame);Set(sender,"commandTargetReceived",Time.realtimeSinceStartupAsDouble);
            Set(sender,"active",false);
            Assert(!sender.TryGetIkTarget(true,out _), "Inactive cycle advertised a tracking target");
            Set(sender,"active",true);Set(sender,"backendState","returning");
            Assert(!sender.TryGetIkTarget(true,out _), "Return advertised a tracking goal");
            frame.age_s=.02;
            Assert(G1GoalPreviewState.Fresh(frame,10,10.07), "Fresh goal rejected");
            Assert(G1GoalPreviewState.Fresh(frame,10,10.179), "Display goal flickered before its lifetime");
            Assert(!G1GoalPreviewState.Fresh(frame,10,10.181), "Goal lifetime exceeded");
            Assert(!G1GoalPreviewState.Fresh(frame,10,9.99), "Reversed clock accepted");
            Reject(frame,x=>x.schema="g1.bimanual.goal.preview.v1", "Legacy prefix accepted as command FK");
            Reject(frame,x=>x.schema="g1.bimanual.goal.preview.v2", "Independent geometric goal accepted as command FK");
            Reject(frame,x=>x.status="checked_goal_prefix", "Legacy prefix status accepted");
            Reject(frame,x=>x.status="geometric_goal_converged", "Geometric convergence accepted as command FK");
            Reject(frame,x=>x.status="geometric_goal_partial", "Geometric partial accepted as command FK");
            Reject(frame,x=>x.status="inactive", "Inactive command accepted");
            Reject(frame,x=>x.valid=false, "Invalid result accepted");
            Reject(frame,x=>x.source_sequence=-1, "Negative source sequence accepted");
            Reject(frame,x=>x.source_sequence=9007199254740992L, "Unsafe integer sequence accepted");
            Reject(frame,x=>x.feedback_sequence=-1, "Negative feedback sequence accepted");
            Reject(frame,x=>x.feedback_sequence=9007199254740992L, "Unsafe feedback sequence accepted");
            Reject(frame,x=>x.age_s=double.NaN, "NaN age accepted");
            Reject(frame,x=>x.age_s=-.01, "Negative age accepted");
            Reject(frame,x=>x.age_s=.201, "Expired goal accepted");
            Reject(frame,x=>x.left_world_m[0]=float.NaN, "NaN position accepted");
            Reject(frame,x=>x.right_world_wxyz=new float[4], "Invalid orientation accepted");
            Assert(typeof(G1BimanualSimulationSender).GetField("client",Private).GetValue(sender)==null,
                "Validation opened a control socket");
            Assert(!Application.isPlaying,"Validation entered Play");
        }
        finally { UnityEngine.Object.DestroyImmediate(host); }
    }
}
