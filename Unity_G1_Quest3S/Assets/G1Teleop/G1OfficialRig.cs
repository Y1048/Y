using System.Collections.Generic;
using UnityEngine;

public class G1OfficialRig : MonoBehaviour
{
    public Transform right_hand_contact_point;
    public Transform right_hand_grip_point;
    public Transform right_wrist_position_reference;
    public Transform right_wrist_orientation_reference;
    public Transform right_hand_semantic_reference;
    public Transform head_camera_mount;
    public Renderer[] first_person_hidden_renderers;
    public bool show_inspection_tool = true;

    private Transform inspection_tool_root;

    private readonly Dictionary<string, G1JointNode> joint_nodes =
        new Dictionary<string, G1JointNode>();

    private static readonly string[] right_arm_joint_names =
    {
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint",
        "right_elbow_joint",
        "right_wrist_roll_joint",
        "right_wrist_pitch_joint",
        "right_wrist_yaw_joint"
    };

    private void Awake()
    {
        RebuildJointCache();
        EnsureRightHandReferences();
        CreateInspectionTool();
    }

    public void RebuildJointCache()
    {
        joint_nodes.Clear();
        G1JointNode[] node_values = GetComponentsInChildren<G1JointNode>(true);
        foreach (G1JointNode node_value in node_values)
        {
            if (node_value != null && !string.IsNullOrEmpty(node_value.joint_name))
            {
                joint_nodes[node_value.joint_name] = node_value;

                if (node_value.joint_name == "right_wrist_yaw_joint")
                {
                    // Use one authoritative wrist frame for both position and
                    // orientation so Unity engagement/replay matches Mink's
                    // right_wrist_yaw_link 6D FrameTask exactly.
                    right_wrist_position_reference = node_value.transform;
                    right_wrist_orientation_reference = node_value.transform;
                }
            }
        }
    }

    private void CreateInspectionTool()
    {
        if (!show_inspection_tool || right_hand_grip_point == null)
        {
            return;
        }

        Transform existing_tool = right_hand_grip_point.Find(
            "inspection_tool");
        if (existing_tool != null)
        {
            inspection_tool_root = existing_tool;
            return;
        }

        inspection_tool_root = new GameObject("inspection_tool").transform;
        inspection_tool_root.SetParent(right_hand_grip_point, false);

        Material grip_material = CreateToolMaterial(
            "inspection_tool_grip_material",
            new Color(0.05f, 0.05f, 0.05f, 1.0f));
        Material probe_material = CreateToolMaterial(
            "inspection_tool_probe_material",
            new Color(0.18f, 0.20f, 0.22f, 1.0f));
        Material tip_material = CreateToolMaterial(
            "inspection_tool_tip_material",
            new Color(0.90f, 0.18f, 0.08f, 1.0f));

        GameObject grip_object = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        grip_object.name = "inspection_tool_grip";
        grip_object.transform.SetParent(inspection_tool_root, false);
        grip_object.transform.localPosition = Vector3.zero;
        grip_object.transform.localRotation = Quaternion.identity;
        grip_object.transform.localScale = new Vector3(0.017f, 0.05f, 0.017f);
        grip_object.GetComponent<Renderer>().sharedMaterial = grip_material;
        Destroy(grip_object.GetComponent<Collider>());

        GameObject probe_object = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        probe_object.name = "inspection_tool_probe";
        probe_object.transform.SetParent(inspection_tool_root, false);
        probe_object.transform.localPosition = new Vector3(0.0f, 0.105f, 0.0f);
        probe_object.transform.localRotation = Quaternion.identity;
        probe_object.transform.localScale = new Vector3(0.010f, 0.055f, 0.010f);
        probe_object.GetComponent<Renderer>().sharedMaterial = probe_material;
        Destroy(probe_object.GetComponent<Collider>());

        GameObject tip_object = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        tip_object.name = "inspection_tool_tip";
        tip_object.transform.SetParent(inspection_tool_root, false);
        tip_object.transform.localPosition = new Vector3(0.0f, 0.16f, 0.0f);
        tip_object.transform.localScale = Vector3.one * 0.07f;
        tip_object.GetComponent<Renderer>().sharedMaterial = tip_material;
        Destroy(tip_object.GetComponent<Collider>());
    }

    private void EnsureRightHandReferences()
    {
        if (right_wrist_orientation_reference == null)
        {
            return;
        }

        if (right_hand_semantic_reference == null)
        {
            Transform semantic_transform = right_wrist_orientation_reference.Find(
                "right_hand_semantic_reference");
            if (semantic_transform == null)
            {
                semantic_transform = new GameObject(
                    "right_hand_semantic_reference").transform;
                semantic_transform.SetParent(right_wrist_orientation_reference, false);
            }

            right_hand_semantic_reference = semantic_transform;
        }

        // The imported wrist already uses the teleoperation frame:
        // +Z follows the fingers and +Y is the palm normal.
        right_hand_semantic_reference.localPosition = Vector3.zero;
        right_hand_semantic_reference.localRotation = Quaternion.identity;

        if (right_hand_grip_point == null)
        {
            Transform grip_transform = right_wrist_orientation_reference.Find(
                "right_hand_grip_point");
            if (grip_transform == null)
            {
                grip_transform = new GameObject("right_hand_grip_point").transform;
                grip_transform.SetParent(right_wrist_orientation_reference, false);
            }

            right_hand_grip_point = grip_transform;
        }

        // Palm-side surface; the probe extends along wrist local +Z (Unity +Y).
        right_hand_grip_point.localPosition = new Vector3(-0.029f, 0.040f, 0.105f);
        right_hand_grip_point.localRotation = Quaternion.identity;

        if (right_hand_contact_point == null)
        {
            Transform contact_transform = right_wrist_orientation_reference.Find(
                "right_hand_contact_point");
            if (contact_transform == null)
            {
                contact_transform = new GameObject("right_hand_contact_point").transform;
                contact_transform.SetParent(right_wrist_orientation_reference, false);
            }

            right_hand_contact_point = contact_transform;
        }

        // Inspection tip: handle centered in the closing fingers, then 16 cm forward.
        right_hand_contact_point.localPosition = new Vector3(-0.029f, 0.200f, 0.105f);
        right_hand_contact_point.localRotation = Quaternion.identity;
    }

    private static Material CreateToolMaterial(string material_name, Color color_value)
    {
        Shader shader_value = Shader.Find("Universal Render Pipeline/Lit");
        if (shader_value == null)
        {
            shader_value = Shader.Find("Standard");
        }

        Material material_value = new Material(shader_value);
        material_value.name = material_name;
        material_value.color = color_value;
        if (material_value.HasProperty("_BaseColor"))
        {
            material_value.SetColor("_BaseColor", color_value);
        }

        return material_value;
    }

    public Transform GetRightWristPositionReference()
    {
        if (right_wrist_position_reference == null)
        {
            RebuildJointCache();
        }

        return right_wrist_position_reference;
    }

    public Transform GetRightWristOrientationReference()
    {
        if (right_wrist_orientation_reference == null)
        {
            RebuildJointCache();
        }

        return right_wrist_orientation_reference;
    }

    public Transform GetRightHandSemanticReference()
    {
        if (right_hand_semantic_reference == null)
        {
            RebuildJointCache();
            EnsureRightHandReferences();
        }

        return right_hand_semantic_reference;
    }

    public Transform GetRightHandGripPoint()
    {
        if (right_hand_grip_point == null)
        {
            RebuildJointCache();
            EnsureRightHandReferences();
        }

        return right_hand_grip_point;
    }

    public void ApplyRightArmJointPositions(float[] joint_positions)
    {
        if (joint_positions == null || joint_positions.Length < right_arm_joint_names.Length)
        {
            return;
        }

        for (int joint_index = 0; joint_index < right_arm_joint_names.Length; joint_index++)
        {
            ApplyJointPosition(right_arm_joint_names[joint_index], joint_positions[joint_index]);
        }
    }

    public void ApplyJointPosition(string joint_name, float joint_position)
    {
        if (joint_nodes.Count == 0)
        {
            RebuildJointCache();
        }

        if (joint_nodes.TryGetValue(joint_name, out G1JointNode joint_node))
        {
            joint_node.SetJointPosition(joint_position);
        }
    }

    public void SetFirstPersonView(bool first_person_active)
    {
        if (first_person_hidden_renderers == null)
        {
            return;
        }

        foreach (Renderer renderer_value in first_person_hidden_renderers)
        {
            if (renderer_value != null)
            {
                renderer_value.enabled = !first_person_active;
            }
        }
    }
}
