using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using Newtonsoft.Json;
using UnityEditor;
using UnityEngine;

/// <summary>Goal marker decoding/source/freshness tests. No Play or control sockets.</summary>
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
            Validate(Path.Combine(Path.GetDirectoryName(output), "unity_goal_preview_packet.json"));
            report = new { passed = true, goal_preview_checks = checks,
                measured_display_validation = measured, measured_start_validation = start,
                play_mode = false, control_sockets_created = false,
                unity_version = Application.unityVersion, utc = DateTime.UtcNow.ToString("O") };
            passed = true;
        }
        catch (Exception error) { report = new { passed = false, checks, error = error.ToString() }; }
        Directory.CreateDirectory(Path.GetDirectoryName(output));
        File.WriteAllText(output, JsonConvert.SerializeObject(report, Formatting.Indented));
        Debug.Log("[GOAL PREVIEW VALIDATION] " + (passed ? "PASS" : "FAIL"));
        EditorApplication.Exit(passed ? 0 : 1);
    }

    private static void Validate(string path)
    {
        var host = new GameObject("Goal preview validation host");
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
            var frame = (G1GoalPreviewState.Frame)feedbackType.GetField("goal_preview").GetValue(decoded);
            Assert(G1GoalPreviewState.Valid(frame), "Python payload did not decode into the checked goal frame");
            Assert(G1GoalPreviewState.ValidForSequence(frame,frame.source_sequence), "Own-source preview rejected");
            Assert(!G1GoalPreviewState.ValidForSequence(frame,frame.source_sequence-1), "Future-source preview accepted");
            float[] command = (float[])feedbackType.GetField("q_rad").GetValue(decoded);
            Property(sender, "LatestJoints", command);
            Set(sender, "lastFeedback", Time.realtimeSinceStartupAsDouble);
            Set(sender, "active", true); Set(sender, "backendState", "tracking");
            Set(sender, "goalPreview", frame); Set(sender, "goalPreviewReceived", Time.realtimeSinceStartupAsDouble);
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
                && Quaternion.Angle(rotation,G1GoalPreviewState.RightRotation(frame)) < .01f, "Preview position/rotation source mismatch");
            Assert(JsonUtility.ToJson(packet) == before, "Goal display modified outgoing controls");
            Assert(ReferenceEquals(sender.LatestJoints,command), "Goal display replaced live joint command");
            Set(sender,"goalPreviewReceived",Time.realtimeSinceStartupAsDouble-1);
            Assert(!sender.TryGetIkTarget(true,out _), "Expired marker was shown");
            Assert(!sender.TryGetRightIkRotation(out _), "Expired orientation was shown");
            Set(sender,"goalPreview",null);
            Assert(!sender.TryGetIkTarget(false,out _), "Missing goal fell back to a stop or raw target");
            Set(sender,"goalPreview",frame);Set(sender,"goalPreviewReceived",Time.realtimeSinceStartupAsDouble);
            Set(sender,"active",false);
            Assert(!sender.TryGetIkTarget(true,out _), "Inactive cycle advertised a tracking target");
            Set(sender,"active",true);Set(sender,"backendState","returning");
            Assert(!sender.TryGetIkTarget(true,out _), "Return advertised a goal prefix");
            frame.age_s=.02;
            Assert(G1GoalPreviewState.Fresh(frame,10,10.07), "Fresh prefix rejected");
            Assert(G1GoalPreviewState.Fresh(frame,10,10.179), "Display prefix flickered before its lifetime");
            Assert(!G1GoalPreviewState.Fresh(frame,10,10.181), "Prefix lifetime exceeded");
            Assert(!G1GoalPreviewState.Fresh(frame,10,9.99), "Reversed clock accepted");
            frame.age_s=double.NaN;Assert(!G1GoalPreviewState.Valid(frame), "NaN age accepted");
            frame.age_s=.02;frame.accepted_steps=2;
            Assert(!G1GoalPreviewState.Valid(frame), "Incomplete horizon accepted");
            frame.accepted_steps=3;frame.left_world_m[0]=float.NaN;
            Assert(!G1GoalPreviewState.Valid(frame), "NaN position accepted");
            frame.left_world_m[0]=0;frame.right_world_wxyz=new float[4];
            Assert(!G1GoalPreviewState.Valid(frame), "Invalid orientation accepted");
            Assert(typeof(G1BimanualSimulationSender).GetField("client",Private).GetValue(sender)==null,
                "Validation opened a control socket");
            Assert(!Application.isPlaying,"Validation entered Play");
        }
        finally { UnityEngine.Object.DestroyImmediate(host); }
    }
}
