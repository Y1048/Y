using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Xml.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

public static class G1OfficialModelImporter
{
    private const string resource_root = "Assets/Resources/G1Official";
    private const string mesh_asset_root = resource_root + "/Meshes";
    private const string material_asset_root = resource_root + "/Materials";
    private const string prefab_asset_path = resource_root + "/G1_29DoF_Official.prefab";
    private const string notice_asset_root = "Assets/G1Teleop/OfficialG1";

    private static bool import_running;

    private struct VertexKey : IEquatable<VertexKey>
    {
        public Vector3 position;
        public Vector3 normal;

        public bool Equals(VertexKey other_value)
        {
            return position == other_value.position && normal == other_value.normal;
        }

        public override bool Equals(object object_value)
        {
            return object_value is VertexKey other_value && Equals(other_value);
        }

        public override int GetHashCode()
        {
            unchecked
            {
                return (position.GetHashCode() * 397) ^ normal.GetHashCode();
            }
        }
    }

    [MenuItem("G1 Teleop/Rebuild Official G1 Model")]
    public static void RebuildOfficialModel()
    {
        ImportOfficialModel(true);
    }

    private static void ImportOfficialModel(bool force_rebuild)
    {
        if (import_running || EditorApplication.isPlayingOrWillChangePlaymode)
        {
            return;
        }

        string source_root = GetG1SourceRoot();
        string xml_path = Path.Combine(source_root, "g1_29dof.xml");
        if (!File.Exists(xml_path))
        {
            Debug.LogError("Official Unitree G1 MJCF was not found: " + xml_path);
            return;
        }

        if (!force_rebuild
            && AssetDatabase.LoadAssetAtPath<GameObject>(prefab_asset_path) != null)
        {
            return;
        }

        import_running = true;
        GameObject prefab_root = null;
        try
        {
            if (force_rebuild)
            {
                AssetDatabase.DeleteAsset(resource_root);
            }

            CreateAssetDirectories();
            CopyUnitreeLicense(source_root);

            XDocument document_value = XDocument.Load(xml_path);
            XElement mujoco_element = document_value.Root;
            if (mujoco_element == null)
            {
                throw new InvalidDataException("The G1 MJCF has no root element.");
            }

            Dictionary<string, Mesh> mesh_values = ImportMeshes(
                source_root,
                mujoco_element);
            Dictionary<string, Material> material_values =
                new Dictionary<string, Material>();

            XElement worldbody_element = mujoco_element.Element("worldbody");
            XElement pelvis_element = worldbody_element == null
                ? null
                : worldbody_element.Elements("body")
                    .FirstOrDefault(element_value =>
                        element_value.Attribute("name")?.Value == "pelvis");
            if (pelvis_element == null)
            {
                throw new InvalidDataException("The official G1 pelvis body was not found.");
            }

            prefab_root = new GameObject("G1_29DoF_Official");
            G1OfficialRig rig_value = prefab_root.AddComponent<G1OfficialRig>();
            BuildBody(
                pelvis_element,
                prefab_root.transform,
                mesh_values,
                material_values);

            Transform wrist_transform = FindChild(
                prefab_root.transform,
                "right_wrist_yaw_link");
            Transform torso_transform = FindChild(
                prefab_root.transform,
                "torso_link");
            Transform head_visual_transform = FindChild(
                prefab_root.transform,
                "head_link_visual");
            if (wrist_transform == null)
            {
                throw new InvalidDataException("The official G1 right wrist-yaw body was not found.");
            }
            if (torso_transform == null || head_visual_transform == null)
            {
                throw new InvalidDataException("The official G1 head geometry was not found.");
            }

            GameObject grip_object = new GameObject("right_hand_grip_point");
            grip_object.transform.SetParent(wrist_transform, false);
            grip_object.transform.localPosition = MuJoCoToUnityVector(
                new Vector3(0.105f, 0.029f, 0.040f));
            grip_object.transform.localRotation = Quaternion.identity;
            rig_value.right_hand_grip_point = grip_object.transform;

            GameObject contact_object = new GameObject("right_hand_contact_point");
            contact_object.transform.SetParent(wrist_transform, false);
            contact_object.transform.localPosition = MuJoCoToUnityVector(
                new Vector3(0.105f, 0.029f, 0.200f));
            contact_object.transform.localRotation = Quaternion.identity;
            rig_value.right_hand_contact_point = contact_object.transform;

            // Mink controls right_wrist_yaw_link as one full 6D frame. Persist
            // that same body as Unity's position and orientation reference so a
            // prefab rebuild cannot silently reintroduce the old roll/yaw split.
            rig_value.right_wrist_position_reference = wrist_transform;
            rig_value.right_wrist_orientation_reference = wrist_transform;

            GameObject semantic_reference_object = new GameObject(
                "right_hand_semantic_reference");
            semantic_reference_object.transform.SetParent(wrist_transform, false);
            semantic_reference_object.transform.localPosition = Vector3.zero;
            // MuJoCoToUnityRotation already maps +X to Unity +Z and +Z to Unity +Y.
            semantic_reference_object.transform.localRotation = Quaternion.identity;
            rig_value.right_hand_semantic_reference = semantic_reference_object.transform;

            GameObject camera_mount_object = new GameObject("head_camera_mount");
            camera_mount_object.transform.SetParent(torso_transform, false);
            camera_mount_object.transform.localPosition = MuJoCoToUnityVector(
                new Vector3(0.088f, 0.0f, 0.405f));
            camera_mount_object.transform.localRotation = Quaternion.identity;
            rig_value.head_camera_mount = camera_mount_object.transform;
            rig_value.first_person_hidden_renderers = new[]
            {
                head_visual_transform.GetComponent<Renderer>()
            };
            rig_value.RebuildJointCache();

            PrefabUtility.SaveAsPrefabAsset(prefab_root, prefab_asset_path);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log(
                "Official Unitree G1 29DoF model imported from MJCF/STL: "
                + prefab_asset_path);
        }
        catch (Exception exception_value)
        {
            Debug.LogError("Official G1 model import failed: " + exception_value);
        }
        finally
        {
            if (prefab_root != null)
            {
                UnityEngine.Object.DestroyImmediate(prefab_root);
            }

            import_running = false;
        }
    }

    private static Dictionary<string, Mesh> ImportMeshes(
        string source_root,
        XElement mujoco_element)
    {
        Dictionary<string, Mesh> mesh_values = new Dictionary<string, Mesh>();
        XElement asset_element = mujoco_element.Element("asset");
        if (asset_element == null)
        {
            return mesh_values;
        }

        string source_mesh_root = Path.Combine(source_root, "meshes");
        foreach (XElement mesh_element in asset_element.Elements("mesh"))
        {
            string mesh_name = mesh_element.Attribute("name")?.Value;
            string file_name = mesh_element.Attribute("file")?.Value;
            if (string.IsNullOrEmpty(mesh_name) || string.IsNullOrEmpty(file_name))
            {
                continue;
            }

            string source_path = Path.Combine(source_mesh_root, file_name);
            string asset_path = mesh_asset_root + "/" + mesh_name + ".asset";
            Mesh mesh_value = AssetDatabase.LoadAssetAtPath<Mesh>(asset_path);
            if (mesh_value == null)
            {
                mesh_value = ReadBinaryStl(source_path, mesh_name);
                AssetDatabase.CreateAsset(mesh_value, asset_path);
            }

            mesh_values[mesh_name] = mesh_value;
        }

        return mesh_values;
    }

    private static Mesh ReadBinaryStl(string source_path, string mesh_name)
    {
        if (!File.Exists(source_path))
        {
            throw new FileNotFoundException("G1 STL mesh was not found.", source_path);
        }

        using (FileStream stream_value = File.OpenRead(source_path))
        using (BinaryReader reader_value = new BinaryReader(stream_value))
        {
            if (stream_value.Length < 84)
            {
                throw new InvalidDataException("Invalid binary STL: " + source_path);
            }

            reader_value.ReadBytes(80);
            uint triangle_count = reader_value.ReadUInt32();
            long expected_length = 84L + 50L * triangle_count;
            if (stream_value.Length < expected_length)
            {
                throw new InvalidDataException("Truncated binary STL: " + source_path);
            }

            List<Vector3> vertex_values = new List<Vector3>();
            List<Vector3> normal_values = new List<Vector3>();
            List<int> triangle_values = new List<int>((int)triangle_count * 3);
            Dictionary<VertexKey, int> vertex_indices =
                new Dictionary<VertexKey, int>();

            for (uint triangle_index = 0; triangle_index < triangle_count; triangle_index++)
            {
                Vector3 normal_value = MuJoCoToUnityVector(ReadVector3(reader_value));
                Vector3 first_vertex = MuJoCoToUnityVector(ReadVector3(reader_value));
                Vector3 second_vertex = MuJoCoToUnityVector(ReadVector3(reader_value));
                Vector3 third_vertex = MuJoCoToUnityVector(ReadVector3(reader_value));
                reader_value.ReadUInt16();

                if (normal_value.sqrMagnitude < 0.000001f)
                {
                    normal_value = Vector3.Cross(
                        second_vertex - first_vertex,
                        third_vertex - first_vertex).normalized;
                }
                else
                {
                    normal_value.Normalize();
                }

                if (Vector3.Dot(
                    Vector3.Cross(second_vertex - first_vertex, third_vertex - first_vertex),
                    normal_value) < 0.0f)
                {
                    Vector3 swap_value = second_vertex;
                    second_vertex = third_vertex;
                    third_vertex = swap_value;
                }

                triangle_values.Add(GetVertexIndex(
                    first_vertex,
                    normal_value,
                    vertex_values,
                    normal_values,
                    vertex_indices));
                triangle_values.Add(GetVertexIndex(
                    second_vertex,
                    normal_value,
                    vertex_values,
                    normal_values,
                    vertex_indices));
                triangle_values.Add(GetVertexIndex(
                    third_vertex,
                    normal_value,
                    vertex_values,
                    normal_values,
                    vertex_indices));
            }

            Mesh mesh_value = new Mesh();
            mesh_value.name = mesh_name;
            mesh_value.indexFormat = IndexFormat.UInt32;
            mesh_value.SetVertices(vertex_values);
            mesh_value.SetNormals(normal_values);
            mesh_value.SetTriangles(triangle_values, 0, true);
            mesh_value.RecalculateBounds();
            return mesh_value;
        }
    }

    private static int GetVertexIndex(
        Vector3 position_value,
        Vector3 normal_value,
        List<Vector3> vertex_values,
        List<Vector3> normal_values,
        Dictionary<VertexKey, int> vertex_indices)
    {
        VertexKey key_value = new VertexKey
        {
            position = position_value,
            normal = normal_value
        };
        if (vertex_indices.TryGetValue(key_value, out int vertex_index))
        {
            return vertex_index;
        }

        vertex_index = vertex_values.Count;
        vertex_values.Add(position_value);
        normal_values.Add(normal_value);
        vertex_indices.Add(key_value, vertex_index);
        return vertex_index;
    }

    private static Vector3 ReadVector3(BinaryReader reader_value)
    {
        return new Vector3(
            reader_value.ReadSingle(),
            reader_value.ReadSingle(),
            reader_value.ReadSingle());
    }

    private static void BuildBody(
        XElement body_element,
        Transform parent_transform,
        Dictionary<string, Mesh> mesh_values,
        Dictionary<string, Material> material_values)
    {
        string body_name = body_element.Attribute("name")?.Value ?? "g1_body";
        GameObject body_object = new GameObject(body_name);
        Transform body_transform = body_object.transform;
        body_transform.SetParent(parent_transform, false);
        body_transform.localPosition = MuJoCoToUnityVector(
            ParseVector(body_element.Attribute("pos")?.Value, Vector3.zero));
        body_transform.localRotation = MuJoCoToUnityRotation(
            ParseQuaternion(body_element.Attribute("quat")?.Value));

        XElement joint_element = body_element.Elements("joint")
            .FirstOrDefault(element_value =>
                element_value.Attribute("type")?.Value != "free");
        if (joint_element != null)
        {
            G1JointNode joint_node = body_object.AddComponent<G1JointNode>();
            joint_node.joint_name = joint_element.Attribute("name")?.Value;
            Vector3 mujoco_axis = ParseVector(
                joint_element.Attribute("axis")?.Value,
                Vector3.forward);
            joint_node.unity_joint_axis = -MuJoCoToUnityVector(mujoco_axis).normalized;
            joint_node.neutral_local_rotation = body_transform.localRotation;
        }

        foreach (XElement geom_element in body_element.Elements("geom"))
        {
            string mesh_name = geom_element.Attribute("mesh")?.Value;
            string group_name = geom_element.Attribute("group")?.Value;
            if (string.IsNullOrEmpty(mesh_name)
                || group_name != "1"
                || !mesh_values.TryGetValue(mesh_name, out Mesh mesh_value))
            {
                continue;
            }

            GameObject visual_object = new GameObject(mesh_name + "_visual");
            visual_object.transform.SetParent(body_transform, false);
            visual_object.transform.localPosition = MuJoCoToUnityVector(
                ParseVector(geom_element.Attribute("pos")?.Value, Vector3.zero));
            visual_object.transform.localRotation = MuJoCoToUnityRotation(
                ParseQuaternion(geom_element.Attribute("quat")?.Value));

            MeshFilter mesh_filter = visual_object.AddComponent<MeshFilter>();
            mesh_filter.sharedMesh = mesh_value;
            MeshRenderer mesh_renderer = visual_object.AddComponent<MeshRenderer>();
            Color color_value = ParseColor(geom_element.Attribute("rgba")?.Value);
            mesh_renderer.sharedMaterial = GetMaterial(color_value, material_values);
        }

        foreach (XElement child_element in body_element.Elements("body"))
        {
            BuildBody(child_element, body_transform, mesh_values, material_values);
        }
    }

    private static Material GetMaterial(
        Color color_value,
        Dictionary<string, Material> material_values)
    {
        string color_key = ColorUtility.ToHtmlStringRGBA(color_value);
        if (material_values.TryGetValue(color_key, out Material material_value))
        {
            return material_value;
        }

        string asset_path = material_asset_root + "/g1_" + color_key + ".mat";
        material_value = AssetDatabase.LoadAssetAtPath<Material>(asset_path);
        if (material_value == null)
        {
            Shader shader_value = Shader.Find("Standard");
            if (shader_value == null)
            {
                shader_value = Shader.Find("Universal Render Pipeline/Lit");
            }

            material_value = new Material(shader_value);
            material_value.name = "g1_" + color_key;
            material_value.color = color_value;
            if (material_value.HasProperty("_BaseColor"))
            {
                material_value.SetColor("_BaseColor", color_value);
            }

            AssetDatabase.CreateAsset(material_value, asset_path);
        }

        material_values[color_key] = material_value;
        return material_value;
    }

    private static Vector3 ParseVector(string source_value, Vector3 fallback_value)
    {
        float[] value_parts = ParseFloats(source_value);
        if (value_parts.Length < 3)
        {
            return fallback_value;
        }

        return new Vector3(value_parts[0], value_parts[1], value_parts[2]);
    }

    private static Quaternion ParseQuaternion(string source_value)
    {
        float[] value_parts = ParseFloats(source_value);
        if (value_parts.Length < 4)
        {
            return Quaternion.identity;
        }

        return new Quaternion(
            value_parts[1],
            value_parts[2],
            value_parts[3],
            value_parts[0]).normalized;
    }

    private static Color ParseColor(string source_value)
    {
        float[] value_parts = ParseFloats(source_value);
        if (value_parts.Length < 3)
        {
            return new Color(0.7f, 0.7f, 0.7f, 1.0f);
        }

        return new Color(
            value_parts[0],
            value_parts[1],
            value_parts[2],
            value_parts.Length >= 4 ? value_parts[3] : 1.0f);
    }

    private static float[] ParseFloats(string source_value)
    {
        if (string.IsNullOrWhiteSpace(source_value))
        {
            return Array.Empty<float>();
        }

        string[] token_values = source_value.Split(
            new[] { ' ', '\t', '\r', '\n' },
            StringSplitOptions.RemoveEmptyEntries);
        float[] float_values = new float[token_values.Length];
        for (int token_index = 0; token_index < token_values.Length; token_index++)
        {
            float_values[token_index] = float.Parse(
                token_values[token_index],
                CultureInfo.InvariantCulture);
        }

        return float_values;
    }

    private static Vector3 MuJoCoToUnityVector(Vector3 mujoco_vector)
    {
        return new Vector3(-mujoco_vector.y, mujoco_vector.z, mujoco_vector.x);
    }

    private static Quaternion MuJoCoToUnityRotation(Quaternion mujoco_rotation)
    {
        Vector3 mujoco_forward = RotateVector(mujoco_rotation, Vector3.right);
        Vector3 mujoco_up = RotateVector(mujoco_rotation, Vector3.forward);
        Vector3 unity_forward = MuJoCoToUnityVector(mujoco_forward);
        Vector3 unity_up = MuJoCoToUnityVector(mujoco_up);
        return Quaternion.LookRotation(unity_forward, unity_up);
    }

    private static Vector3 RotateVector(Quaternion rotation_value, Vector3 vector_value)
    {
        Vector3 quaternion_vector = new Vector3(
            rotation_value.x,
            rotation_value.y,
            rotation_value.z);
        Vector3 cross_value = Vector3.Cross(quaternion_vector, vector_value);
        return vector_value
            + 2.0f * rotation_value.w * cross_value
            + 2.0f * Vector3.Cross(quaternion_vector, cross_value);
    }

    private static Transform FindChild(Transform parent_transform, string object_name)
    {
        if (parent_transform.name == object_name)
        {
            return parent_transform;
        }

        for (int child_index = 0; child_index < parent_transform.childCount; child_index++)
        {
            Transform result_value = FindChild(
                parent_transform.GetChild(child_index),
                object_name);
            if (result_value != null)
            {
                return result_value;
            }
        }

        return null;
    }

    private static string GetG1SourceRoot()
    {
        string unity_root = Directory.GetParent(Application.dataPath).FullName;
        string workspace_root = Directory.GetParent(unity_root).FullName;
        return Path.Combine(
            workspace_root,
            "MuJoCo_G1_Controller",
            "external",
            "unitree_mujoco",
            "unitree_robots",
            "g1");
    }

    private static void CreateAssetDirectories()
    {
        Directory.CreateDirectory(Path.Combine(Application.dataPath, "Resources", "G1Official", "Meshes"));
        Directory.CreateDirectory(Path.Combine(Application.dataPath, "Resources", "G1Official", "Materials"));
        Directory.CreateDirectory(Path.Combine(Application.dataPath, "G1Teleop", "OfficialG1"));
        AssetDatabase.Refresh();
    }

    private static void CopyUnitreeLicense(string source_root)
    {
        string unitree_root = Directory.GetParent(
            Directory.GetParent(source_root).FullName).FullName;
        string source_path = Path.Combine(unitree_root, "LICENSE");
        string destination_path = Path.Combine(
            Application.dataPath,
            "G1Teleop",
            "OfficialG1",
            "Unitree_LICENSE.txt");
        File.Copy(source_path, destination_path, true);
        AssetDatabase.ImportAsset(notice_asset_root + "/Unitree_LICENSE.txt");
    }
}
