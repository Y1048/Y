using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>Edit-mode regression using real Unity transforms. Never enters Play or opens control sockets.</summary>
[InitializeOnLoad]
public static class G1MeasuredDisplayValidation
{
    private const BindingFlags Private = BindingFlags.NonPublic | BindingFlags.Instance;
    private static double nextPoll;
    private static int checks;
    private static string RequestPath => Path.Combine(Application.dataPath, "../Library/G1MeasuredDisplayValidation.request");
    private static string ResultPath => Path.Combine(Application.dataPath, "../Library/G1MeasuredDisplayValidation.result.json");

    static G1MeasuredDisplayValidation() { EditorApplication.update += CheckRequest; }
    private static void CheckRequest()
    {
        if (EditorApplication.timeSinceStartup < nextPoll) return;
        nextPoll = EditorApplication.timeSinceStartup + 1;
        if (!File.Exists(RequestPath) || EditorApplication.isCompiling || EditorApplication.isUpdating) return;
        string token = File.ReadAllText(RequestPath).Trim();
        File.Delete(RequestPath);
        Execute(token, ResultPath, false);
    }

    [MenuItem("G1 Teleop/Validate Measured Display Isolation")]
    public static void RunMenu() { Execute("menu", ResultPath, false); }

    public static void RunBatch()
    {
        string[] args = Environment.GetCommandLineArgs();
        int index = Array.IndexOf(args, "-g1MeasuredValidationOutput");
        string output = index >= 0 && index + 1 < args.Length ? args[index + 1] : ResultPath;
        Execute("batch", output, true);
    }

    private static void Execute(string token, string output, bool exit)
    {
        bool passed = false;
        object report;
        try
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
                throw new InvalidOperationException("Validation refuses to run in Play mode.");
            var result = Validate();
            result["request"] = token;
            report = result;
            passed = true;
        }
        catch (Exception error)
        {
            report = new { passed = false, request = token, checks, error = error.ToString(),
                play_mode = EditorApplication.isPlaying };
        }
        Directory.CreateDirectory(Path.GetDirectoryName(output));
        File.WriteAllText(output, JsonConvert.SerializeObject(report, Formatting.Indented));
        Debug.Log("[G1 MEASURED DISPLAY VALIDATION] " + (passed ? "PASS" : "FAIL") + " " + output);
        if (exit) EditorApplication.Exit(passed ? 0 : 1);
    }

    private static void Assert(bool condition, string message)
    {
        ++checks;
        if (!condition) throw new InvalidOperationException(message);
    }
    private static void Set(object value, string field, object data)
        => value.GetType().GetField(field, Private).SetValue(value, data);
    private static object Get(object value, string field)
        => value.GetType().GetField(field, Private).GetValue(value);
    private static void Invoke(object value, string method)
        => value.GetType().GetMethod(method, Private).Invoke(value, null);
    private static void Property(object value, string name, object data)
        => value.GetType().GetProperty(name).SetValue(value, data);

    private static G1LowStateLegView.Frame Frame(string session, long sequence, float[] q)
        => new G1LowStateLegView.Frame {
            schema = "g1.lowstate.view.v1", session = session, sequence = sequence,
            source_monotonic_s = sequence, age_s = 0, crc_valid = true,
            joint_names = G1OfficialRig.GetFullBodyJointNames(), q_rad = (float[])q.Clone(),
            dq_rad_s = new float[29], tau_est_nm = new float[29]
        };

    private static void PoseEquals(G1OfficialRig rig, float[] q, string scope)
    {
        var expected = G1OfficialRig.GetFullBodyJointNames();
        var nodes = rig.GetComponentsInChildren<G1JointNode>(true).ToDictionary(x => x.joint_name);
        for (int i = 0; i < 29; ++i)
        {
            var node = nodes[expected[i] + "_joint"];
            Quaternion rotation = node.neutral_local_rotation
                * Quaternion.AngleAxis(q[i] * Mathf.Rad2Deg, node.unity_joint_axis);
            Assert(Quaternion.Angle(rotation, node.transform.localRotation) < .06f,
                scope + ": joint " + expected[i] + " is not from the chosen source");
        }
    }

    private static Dictionary<string, object> Validate()
    {
        checks = 0;
        var scene = EditorSceneManager.NewPreviewScene();
        var groups = new List<string>();
        GameObject host = null, model = null;
        G1UnityRightArmPreview preview = null;
        try
        {
            host = new GameObject("Measured display validation host");
            host.SetActive(false);
            SceneManager.MoveGameObjectToScene(host, scene);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(
                "Assets/Resources/G1Official/G1_29DoF_Official.prefab");
            Assert(prefab != null, "Official prefab missing");
            model = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
            model.SetActive(false);
            var rig = model.GetComponent<G1OfficialRig>();
            rig.RebuildJointCache();
            float[] initial = new float[29];
            float[] ready = { .17453293f, .38397244f, 0, .9599311f, 0, 0, 0,
                              .17453293f, -.38397244f, 0, .9599311f, 0, 0, 0 };
            Array.Copy(ready, 0, initial, 15, 14);
            Assert(rig.ApplyAllJointPositions(G1OfficialRig.GetFullBodyJointNames(), initial), "Initial rig contract");
            model.transform.SetPositionAndRotation(new Vector3(0, -.013f, 0), Quaternion.Euler(0, 37, 0));
            var frame = new G1BimanualCommandFrame(rig, host.transform);
            var receiver = model.AddComponent<G1LowStateLegView>();
            var sender = host.AddComponent<G1BimanualSimulationSender>();
            sender.useExistingScene = true;
            var names = G1OfficialRig.GetFullBodyJointNames().Skip(15).Select(x => x + "_joint").ToArray();
            float[] command = (float[])ready.Clone();
            command[0] = .35f; command[3] = 1.1f; command[5] = -.35f;
            command[7] = -.15f; command[12] = .3f;
            Property(sender, "LatestJoints", command);
            Property(sender, "LatestJointNames", names);
            Property(sender, "CommandBackendId", "edit-mode-backend");
            Property(sender, "CommandFeedbackSequence", 3L);
            Set(sender, "lastFeedback", Time.realtimeSinceStartupAsDouble);
            preview = host.AddComponent<G1UnityRightArmPreview>();
            preview.bimanual_simulation = sender;
            Set(preview, "official_g1_object", model);
            Set(preview, "official_g1_rig", rig);
            Set(preview, "measured_view", receiver);
            Set(preview, "command_frame", frame);
            Set(preview, "robot_anchored", true);
            var nodes = rig.GetComponentsInChildren<G1JointNode>(true).ToDictionary(x => x.joint_name);
            Transform left = nodes["left_wrist_yaw_joint"].transform;
            Transform right = nodes["right_wrist_yaw_joint"].transform;
            Set(preview, "left_wrist_reference", left);

            var alignment = host.AddComponent<G1HeadLockedCamera>();
            var head = new GameObject("Fake tracked head").transform;
            head.SetParent(host.transform, false);
            head.position = new Vector3(.01f, 1.4f, -.02f);
            alignment.xr_center_eye = head; alignment.robot_preview = preview;
            preview.head_camera_alignment = alignment;
            var binder = host.AddComponent<G1ExistingHandTargetBinder>();
            binder.head_camera_alignment = alignment;
            sender.rightBinder = binder;
            Type packetType = typeof(G1BimanualSimulationSender).GetNestedType("Packet", BindingFlags.NonPublic);
            Set(sender, "packet", Activator.CreateInstance(packetType));
            Invoke(preview, "UpdateOfficialRobotPose");
            float[] expectedCommand = (float[])initial.Clone();
            Array.Copy(command, 0, expectedCommand, 15, 14);
            PoseEquals(rig, expectedCommand, "Before first LowState: explicitly simulated");
            Assert(!preview.IsShowingMeasuredPose && preview.PoseSourceStatus.Contains("SIMULATION"), "False measured label before first state");
            groups.Add("no_measured_state_is_explicitly_simulated");

            Invoke(sender, "UpdateWorldDiagnostics");
            string beforePacket = JsonUtility.ToJson(Get(sender, "packet"));
            Vector3 beforeLeft = frame.LeftWrist.position, beforeRight = frame.RightWrist.position;
            Vector3 beforeShoulders = frame.ShoulderCenter;
            Quaternion beforeHead = preview.HeadCameraMount.rotation;
            float[] measured = (float[])initial.Clone();
            measured[3] = .5f; measured[9] = .65f; measured[12] = .2f;
            measured[13] = .1f; measured[14] = -.15f;
            measured[18] = 1.35f; measured[20] = .45f; measured[25] = .6f; measured[27] = -.4f;
            double now = Time.realtimeSinceStartupAsDouble;
            Assert(receiver.TryAcceptFrame(Frame("A", 1, measured), now), "Measured packet not accepted");
            Invoke(preview, "UpdateOfficialRobotPose");
            PoseEquals(rig, measured, "Measured render");
            Assert(preview.IsShowingMeasuredPose && receiver.AppliedSequence == 1, "Measured source not applied");
            Assert(preview.PoseSourceStatus.Contains("MEASURED"), "Measured label not tied to application");
            Assert(Vector3.Distance(left.position, frame.LeftWrist.position) > .01f, "Test did not separate measured and command FK");
            Assert(Vector3.Distance(right.position, frame.RightWrist.position) > .01f, "Right FK sources not separated");
            Assert(Vector3.Distance(frame.LeftWrist.position, beforeLeft) < 1e-6f
                && Vector3.Distance(frame.RightWrist.position, beforeRight) < 1e-6f
                && Vector3.Distance(frame.ShoulderCenter, beforeShoulders) < 1e-6f,
                "Measured waist/arm pose contaminated command alignment");
            Assert(Quaternion.Angle(preview.HeadCameraMount.rotation, beforeHead) < .01f,
                "Measured waist pose contaminated HMD alignment");
            Invoke(sender, "UpdateWorldDiagnostics");
            Assert(JsonUtility.ToJson(Get(sender, "packet")) == beforePacket,
                "Measured display changed outgoing control-frame diagnostics");
            Assert(sender.LatestJoints.SequenceEqual(command), "Measured state overwrote command joints");
            groups.Add("all_29_rendered_joints_follow_lowstate");
            groups.Add("command_frame_head_alignment_and_outgoing_packet_are_isolated");

            Set(sender, "lastFeedback", Time.realtimeSinceStartupAsDouble);
            var record = G1MeasuredTrackingDiagnostics.BuildRecord(receiver, frame, sender, left, right,
                preview.IsShowingMeasuredPose, Time.realtimeSinceStartupAsDouble);
            Assert((bool)record["comparison_valid"], "Fresh independent states not comparable");
            Assert(!(bool)record["absolute_transport_latency_available"], "False latency claim");
            Assert(!(bool)record["absolute_robot_world_pose_available"], "False world localization claim");
            Assert(((float[])record["q_measured_rad"]).SequenceEqual(measured), "Wrong measured diagnostic");
            Assert(((float[])record["q_command_rad"]).SequenceEqual(command), "Wrong command diagnostic");
            Assert((double)record["maximum_arm_joint_error_rad"] > .5, "Joint mismatch not diagnosed");
            JsonConvert.SerializeObject(record);
            groups.Add("separate_measured_command_diagnostics_without_feedback");

            Set(receiver, "received", Time.realtimeSinceStartupAsDouble - 1);
            float[] movedCommand = (float[])command.Clone(); movedCommand[3] += .1f;
            Property(sender, "LatestJoints", movedCommand);
            Invoke(preview, "UpdateOfficialRobotPose");
            PoseEquals(rig, measured, "Stale measured render holds");
            Assert(preview.IsShowingMeasuredPose && preview.PoseSourceStatus.Contains("STALE"), "Stale stream fell back to IK");
            record = G1MeasuredTrackingDiagnostics.BuildRecord(receiver, frame, sender, left, right, true, Time.realtimeSinceStartupAsDouble);
            Assert(!(bool)record["comparison_valid"] && record["maximum_arm_joint_error_rad"] == null,
                "Stale mismatch reported as fresh measurement");
            groups.Add("stale_measured_pose_never_substitutes_new_ik");

            float[] reconnected = (float[])measured.Clone(); reconnected[15] += .1f;
            Assert(receiver.TryAcceptFrame(Frame("B", 1, reconnected), Time.realtimeSinceStartupAsDouble), "Reconnect not accepted");
            Assert(!receiver.TryAcceptFrame(Frame("A", 100, measured), Time.realtimeSinceStartupAsDouble), "Retired session reused");
            Assert(!receiver.TryAcceptFrame(Frame("B", 1, measured), Time.realtimeSinceStartupAsDouble), "Duplicate accepted");
            Assert(!receiver.TryAcceptFrame(Frame("B", 0, measured), Time.realtimeSinceStartupAsDouble), "Reverse sequence accepted");
            Invoke(preview, "UpdateOfficialRobotPose");
            PoseEquals(rig, reconnected, "Reconnected measured render");
            Assert(sender.LatestJoints.SequenceEqual(movedCommand), "Reconnect resynchronized IK without authorization");
            groups.Add("reconnect_updates_display_only_and_rejects_retired_session");

            var bad = Frame("B", 2, measured); bad.q_rad[0] = float.NaN;
            Assert(!receiver.TryAcceptFrame(bad, Time.realtimeSinceStartupAsDouble), "NaN accepted");
            bad = Frame("B", 2, measured); bad.crc_valid = false;
            Assert(!receiver.TryAcceptFrame(bad, Time.realtimeSinceStartupAsDouble), "Bad CRC accepted");
            bad = Frame("B", 2, measured); bad.joint_names[0] = "wrong";
            Assert(!receiver.TryAcceptFrame(bad, Time.realtimeSinceStartupAsDouble), "Wrong joint contract accepted");
            bad = Frame("B", 2, measured); bad.age_s = .6;
            Assert(!receiver.TryAcceptFrame(bad, Time.realtimeSinceStartupAsDouble), "Stale source accepted");
            bad = Frame("B", 2, measured); bad.q_rad = new float[14];
            Assert(!receiver.TryAcceptFrame(bad, Time.realtimeSinceStartupAsDouble), "Short full-body packet accepted");
            Assert(!receiver.TryAcceptFrame(Frame("B", 2, measured), double.NaN), "Invalid local clock accepted");
            var copyTest = Frame("B", 2, reconnected);
            Assert(receiver.TryAcceptFrame(copyTest, Time.realtimeSinceStartupAsDouble), "Copy test accept");
            copyTest.q_rad[0] = 100;
            Assert(receiver.LatestState.q_rad[0] == reconnected[0], "External mutation changed accepted sample");
            groups.Add("invalid_input_and_aliasing_do_not_replace_valid_measurements");

            var ageFrame = Frame("B", 3, measured); ageFrame.age_s = .4;
            Assert(receiver.TryAcceptFrame(ageFrame, 10), "Age test accepted");
            Assert(receiver.IsFreshAt(10.09) && !receiver.IsFreshAt(10.11), "Receipt/excess-age freshness incorrect");
            Assert(!receiver.IsFreshAt(9), "Reversed local time marked fresh");
            groups.Add("freshness_uses_receipt_elapsed_plus_reported_excess_delay");
            Vector3 rootBefore = model.transform.position; Quaternion rotationBefore = model.transform.rotation;
            receiver.ApplyMeasuredPose();
            Assert(model.transform.position == rootBefore && model.transform.rotation == rotationBefore, "LowState joint application moved root");
            groups.Add("measured_joints_do_not_redefine_fixed_base_or_omni_yaw");
            Assert(Get(receiver, "client") == null && Get(sender, "client") == null, "Validation opened a network socket");
            Assert(!Application.isPlaying, "Validation entered Play");
            groups.Add("no_play_no_sockets_no_robot_commands");
            return new Dictionary<string, object> { ["passed"] = true, ["checks"] = checks,
                ["cases"] = groups, ["play_mode"] = false, ["control_sockets_created"] = false,
                ["unity_version"] = Application.unityVersion, ["utc"] = DateTime.UtcNow.ToString("O") };
        }
        finally
        {
            if (preview != null) Set(preview, "preview_root", null);
            if (model != null) UnityEngine.Object.DestroyImmediate(model);
            if (host != null) UnityEngine.Object.DestroyImmediate(host);
            EditorSceneManager.ClosePreviewScene(scene);
        }
    }
}
