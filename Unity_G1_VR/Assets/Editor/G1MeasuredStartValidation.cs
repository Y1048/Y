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

/// <summary>Real-rig idle initialization tests. No Play or transport activation.</summary>
public static class G1MeasuredStartValidation
{
    private static int checks;
    private const BindingFlags Private = BindingFlags.NonPublic | BindingFlags.Instance;
    private static void Assert(bool value, string message)
    { ++checks; if (!value) throw new InvalidOperationException(message); }
    private static void Set(object value, string field, object data)
        => value.GetType().GetField(field, Private).SetValue(value, data);
    private static void Property(object value, string name, object data)
        => value.GetType().GetProperty(name).SetValue(value, data);
    private static void Invoke(object value, string method)
        => value.GetType().GetMethod(method, Private).Invoke(value, null);

    private static G1MeasuredStartState.Acknowledgement DecodeAcknowledgement(string json)
    {
        var type = typeof(G1BimanualSimulationSender).GetNestedType("Feedback", BindingFlags.NonPublic);
        object feedback = JsonUtility.FromJson("{\"measured_start\":" + json + "}", type);
        return (G1MeasuredStartState.Acknowledgement)type.GetField("measured_start").GetValue(feedback);
    }

    private static void ValidateAcknowledgementWire()
    {
        // Unity 6000.5 normalizes explicit JSON null strings/arrays to empty
        // values. Test the real sender DTO and native JsonUtility path.
        const string wait = "{\"ready\":false,\"revision\":0,\"reason\":\"waiting_fresh_measurement\",";
        foreach (string tail in new[] {
            "\"session\":null,\"body_q_rad\":null}",
            "\"session\":\"\",\"body_q_rad\":[]}" })
        {
            var ack = DecodeAcknowledgement(wait + tail);
            Assert(G1MeasuredStartState.Valid(ack), "Serialized waiting ACK must be accepted as feedback");
            Assert(!G1MeasuredStartState.CanEngage(ack, 0, null, true),
                "Accepted waiting ACK must never authorize engage");
        }
        foreach (string tail in new[] {
            "\"session\":\"robot-A\",\"body_q_rad\":null}",
            "\"session\":null,\"body_q_rad\":[0]}" })
            Assert(!G1MeasuredStartState.Valid(DecodeAcknowledgement(wait + tail)),
                "Revision zero cannot carry a measured session or body pose");
        Assert(!G1MeasuredStartState.Valid(DecodeAcknowledgement(
            "{\"ready\":true,\"revision\":0,\"reason\":\"synchronized\",\"session\":null,\"body_q_rad\":null}")),
            "Revision-zero ready ACK must be rejected");
        Assert(!G1MeasuredStartState.Valid(DecodeAcknowledgement(
            "{\"ready\":false,\"revision\":1,\"reason\":\"synchronized\",\"session\":null,\"body_q_rad\":null}")),
            "Revision-one ACK still requires measured session and fifteen body joints");
    }

    public static void RunBatch()
    {
        string[] args = Environment.GetCommandLineArgs();
        int i = Array.IndexOf(args, "-g1MeasuredStartOutput");
        if (i < 0 || i + 1 >= args.Length) throw new InvalidOperationException("Output required");
        string output = args[i + 1];
        bool passed = false; object result;
        try
        {
            Assert(!EditorApplication.isPlayingOrWillChangePlaymode, "No Play allowed");
            var legacy = typeof(G1MeasuredDisplayValidation).GetMethod("Validate",
                BindingFlags.NonPublic | BindingFlags.Static).Invoke(null, null);
            result = new { passed = true, existing_display_validation = legacy,
                measured_start_validation = Validate(Path.GetDirectoryName(output)),
                play_mode = false, control_sockets_created = false,
                unity_version = Application.unityVersion, utc = DateTime.UtcNow.ToString("O") };
            passed = true;
        }
        catch (Exception error) { result = new { passed = false, checks, error = error.ToString() }; }
        Directory.CreateDirectory(Path.GetDirectoryName(output));
        File.WriteAllText(output, JsonConvert.SerializeObject(result, Formatting.Indented));
        Debug.Log("[MEASURED START VALIDATION] " + (passed ? "PASS" : "FAIL"));
        EditorApplication.Exit(passed ? 0 : 1);
    }

    private static object Validate(string output)
    {
        ValidateAcknowledgementWire();
        var scene = EditorSceneManager.NewPreviewScene();
        GameObject host = null, model = null;
        G1UnityRightArmPreview preview = null;
        try
        {
            host = new GameObject("Measured start test host"); host.SetActive(false);
            SceneManager.MoveGameObjectToScene(host, scene);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(
                "Assets/Resources/G1Official/G1_29DoF_Official.prefab");
            model = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
            model.SetActive(false);
            var rig = model.GetComponent<G1OfficialRig>(); rig.RebuildJointCache();
            string[] fullNames = G1OfficialRig.GetFullBodyJointNames();
            var fixture = JsonConvert.DeserializeObject<Dictionary<string, object>>(File.ReadAllText(
                Path.Combine(Application.dataPath, "../../backend/tests/fixtures/g1_measured_start_20261007.json")));
            float[] measured = JsonConvert.DeserializeObject<float[]>(fixture["q_rad"].ToString());
            float[] initial = new float[29];
            float[] home = { .17453293f,.38397244f,0,.9599311f,0,0,0,
                             .17453293f,-.38397244f,0,.9599311f,0,0,0 };
            Array.Copy(home,0,initial,15,14);rig.ApplyAllJointPositions(fullNames,initial);
            model.transform.SetPositionAndRotation(new Vector3(0,-.013f,0),Quaternion.Euler(0,37,0));
            var frame = new G1BimanualCommandFrame(rig,host.transform);
            var receiver = model.AddComponent<G1LowStateLegView>();
            var sender = host.AddComponent<G1BimanualSimulationSender>();sender.useExistingScene=true;
            preview=host.AddComponent<G1UnityRightArmPreview>();preview.bimanual_simulation=sender;
            Set(preview,"official_g1_object",model);Set(preview,"official_g1_rig",rig);
            Set(preview,"measured_view",receiver);Set(preview,"command_frame",frame);
            Set(preview,"robot_anchored",true);
            var nodes=rig.GetComponentsInChildren<G1JointNode>(true).ToDictionary(n=>n.joint_name);
            var left=nodes["left_wrist_yaw_joint"].transform;
            var right=nodes["right_wrist_yaw_joint"].transform;
            string[] armNames=fullNames.Skip(15).Select(n=>n+"_joint").ToArray();
            Property(sender,"LatestJointNames",armNames);Property(sender,"LatestJoints",home);
            Set(sender,"lastFeedback",Time.realtimeSinceStartupAsDouble);
            Vector3 headBefore=frame.HeadMount.position;Quaternion headRotationBefore=frame.HeadMount.rotation;
            var sample=new G1LowStateLegView.Frame {
                schema="g1.lowstate.view.v1",session="robot-A",sequence=20,source_monotonic_s=1,
                age_s=.01,crc_valid=true,joint_names=fullNames,q_rad=measured,
                dq_rad_s=new float[29],tau_est_nm=new float[29] };
            double now=Time.realtimeSinceStartupAsDouble;
            Assert(receiver.TryAcceptFrame(sample,now),"Receive real recorded pose");
            Invoke(preview,"UpdateOfficialRobotPose");
            double beforeLeft=Vector3.Distance(left.position,frame.LeftWrist.position);
            double beforeRight=Vector3.Distance(right.position,frame.RightWrist.position);
            Assert(beforeLeft>.05 && beforeRight>.05,"Fixture must reproduce visible misalignment");
            var snapshot=preview.CaptureMeasuredStart(Time.realtimeSinceStartupAsDouble);
            Assert(snapshot!=null,"Current measured state must be available");
            var ack=new G1MeasuredStartState.Acknowledgement {
                ready=true,revision=1,reason="synchronized",session="robot-A",body_q_rad=measured.Take(15).ToArray() };
            Assert(!G1MeasuredStartState.CanEngage(ack,-1,snapshot,true),"Unprepared frame cannot activate");
            Property(sender,"StartAcknowledgement",ack);
            Property(sender,"LatestJoints",measured.Skip(15).ToArray());
            Invoke(preview,"UpdateOfficialRobotPose");
            double afterLeft=Vector3.Distance(left.position,frame.LeftWrist.position);
            double afterRight=Vector3.Distance(right.position,frame.RightWrist.position);
            Assert(afterLeft<1e-6 && afterRight<1e-6,"Acknowledged wrist references must match both measured wrists");
            Assert(preview.PreparedStartRevision==1,"Renderer must acknowledge prepared revision");
            Assert(G1MeasuredStartState.CanEngage(ack,preview.PreparedStartRevision,snapshot,true),"Prepared fresh start allowed");
            Assert(Vector3.Distance(headBefore,frame.HeadMount.position)<1e-6
                && Quaternion.Angle(headRotationBefore,frame.HeadMount.rotation)<.01f,"HMD startup anchor moved");
            Assert(preview.IsShowingMeasuredPose,"Model must remain measured");
            Assert(!G1MeasuredStartState.CanEngage(ack,1,null,true),"No measurement cannot engage");
            Assert(!G1MeasuredStartState.CanEngage(ack,1,snapshot,false),"Stale backend cannot engage");
            Assert(!G1MeasuredStartState.CanEngage(ack,0,snapshot,true),"Old revision cannot engage");
            snapshot.receipt_age_s=.101;
            Assert(!G1MeasuredStartState.CanEngage(ack,1,snapshot,true),"Stale sample cannot engage");
            snapshot.receipt_age_s=.01;snapshot.session="robot-B";
            Assert(!G1MeasuredStartState.CanEngage(ack,1,snapshot,true),"Reconnected source needs a new seed");
            snapshot.session="robot-A";
            Type packetType=typeof(G1BimanualSimulationSender).GetNestedType("Packet",BindingFlags.NonPublic);
            var packet=Activator.CreateInstance(packetType);
            foreach(var entry in new Dictionary<string,object> {
                ["session"]="unity-edit-test",["start_state"]=snapshot,["start_aligned"]=true,
                ["start_state_available"]=true,["start_revision"]=1L })
                packetType.GetField(entry.Key).SetValue(packet,entry.Value);
            string withState=JsonUtility.ToJson(packet);
            Assert(System.Text.Encoding.UTF8.GetByteCount(withState)<8192,"Measured packet exceeds receiver bound");
            File.WriteAllText(Path.Combine(output,"unity_start_packet.json"),withState);
            packetType.GetField("start_state_available").SetValue(packet,false);
            packetType.GetField("start_state").SetValue(packet,null);
            File.WriteAllText(Path.Combine(output,"unity_start_packet_absent.json"),JsonUtility.ToJson(packet));
            Assert(!Application.isPlaying,"Validator entered Play");
            Assert(typeof(G1LowStateLegView).GetField("client",Private).GetValue(receiver)==null
                && typeof(G1BimanualSimulationSender).GetField("client",Private).GetValue(sender)==null,"Opened control socket");
            return new { passed=true,checks,before_left_gap_mm=beforeLeft*1000,before_right_gap_mm=beforeRight*1000,
                after_left_gap_mm=afterLeft*1000,after_right_gap_mm=afterRight*1000,
                original_head_anchor_preserved=true,serialized_packet_bytes=System.Text.Encoding.UTF8.GetByteCount(withState) };
        }
        finally
        {
            if(preview!=null)Set(preview,"preview_root",null);
            if(model!=null)UnityEngine.Object.DestroyImmediate(model);
            if(host!=null)UnityEngine.Object.DestroyImmediate(host);
            EditorSceneManager.ClosePreviewScene(scene);
        }
    }
}
