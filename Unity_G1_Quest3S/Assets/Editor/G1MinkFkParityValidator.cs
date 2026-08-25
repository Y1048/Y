using System;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class G1MinkFkParityValidator
{
    [Serializable]
    private class ReferenceSample
    {
        public string name;
        public float[] right_arm_q_rad;
        public float[] unity_wrist_delta_m;
    }

    [Serializable]
    private class ReferencePayload
    {
        public string frame;
        public float tolerance_m;
        public ReferenceSample[] samples;
    }

    private const string prefab_path =
        "Assets/Resources/G1Official/G1_29DoF_Official.prefab";

    public static void ValidateBatch()
    {
        string unity_project_root = Directory.GetParent(Application.dataPath).FullName;
        string workspace_root = Directory.GetParent(unity_project_root).FullName;
        string reference_path = Path.Combine(
            workspace_root,
            "logs",
            "runtime",
            "g1_mink_fk_reference.json");

        if (!File.Exists(reference_path))
        {
            throw new FileNotFoundException(
                "MuJoCo FK reference was not generated.",
                reference_path);
        }

        ReferencePayload payload = JsonUtility.FromJson<ReferencePayload>(
            File.ReadAllText(reference_path));
        if (payload == null
            || payload.samples == null
            || payload.samples.Length < 2
            || payload.frame != "right_wrist_yaw_link")
        {
            throw new InvalidDataException("Invalid MuJoCo wrist-yaw FK reference payload.");
        }

        GameObject prefab_value = AssetDatabase.LoadAssetAtPath<GameObject>(prefab_path);
        if (prefab_value == null)
        {
            throw new InvalidOperationException("Official G1 Unity prefab is missing.");
        }

        GameObject instance_value = PrefabUtility.InstantiatePrefab(prefab_value) as GameObject;
        if (instance_value == null)
        {
            throw new InvalidOperationException("Official G1 prefab could not be instantiated.");
        }

        try
        {
            G1OfficialRig rig = instance_value.GetComponent<G1OfficialRig>();
            if (rig == null)
            {
                throw new InvalidOperationException("G1OfficialRig is missing from prefab.");
            }

            Transform wrist = rig.GetRightWristPositionReference();
            if (wrist == null)
            {
                throw new InvalidOperationException("Unity right_wrist_yaw reference is missing.");
            }

            Vector3 unity_baseline = Vector3.zero;
            bool baseline_captured = false;
            float tolerance = Mathf.Max(0.0005f, payload.tolerance_m);

            foreach (ReferenceSample sample in payload.samples)
            {
                if (sample == null
                    || sample.right_arm_q_rad == null
                    || sample.right_arm_q_rad.Length != 7
                    || sample.unity_wrist_delta_m == null
                    || sample.unity_wrist_delta_m.Length != 3)
                {
                    throw new InvalidDataException("Invalid FK sample in reference payload.");
                }

                rig.ApplyRightArmJointPositions(sample.right_arm_q_rad);
                Vector3 current_position = wrist.position;
                if (!baseline_captured)
                {
                    unity_baseline = current_position;
                    baseline_captured = true;
                }

                Vector3 unity_delta = current_position - unity_baseline;
                Vector3 expected_delta = new Vector3(
                    sample.unity_wrist_delta_m[0],
                    sample.unity_wrist_delta_m[1],
                    sample.unity_wrist_delta_m[2]);
                float error = Vector3.Distance(unity_delta, expected_delta);

                Debug.Log(
                    "G1 FK parity " + sample.name
                    + " Unity=" + unity_delta.ToString("F5")
                    + " MuJoCo=" + expected_delta.ToString("F5")
                    + " error=" + (error * 1000.0f).ToString("F2") + " mm");

                if (error > tolerance)
                {
                    throw new InvalidOperationException(
                        "G1 FK parity FAILED at " + sample.name
                        + ": " + (error * 1000.0f).ToString("F2")
                        + " mm > " + (tolerance * 1000.0f).ToString("F2") + " mm");
                }
            }

            Debug.Log(
                "[PASS] Unity G1 FK matches MuJoCo right_wrist_yaw_link within "
                + (tolerance * 1000.0f).ToString("F1") + " mm.");
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(instance_value);
        }
    }
}
