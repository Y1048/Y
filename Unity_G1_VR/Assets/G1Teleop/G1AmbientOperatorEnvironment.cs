using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Creates a quiet, abstract interior around the teleoperation preview.
/// All generated objects are visual-only and have no colliders.
/// </summary>
public sealed class G1AmbientOperatorEnvironment : MonoBehaviour
{
    public const string ObjectName = "G1_Ambient_Operator_Environment";
    public const int ExpectedVisualElementCount = 15;

    private readonly List<Material> runtime_materials = new List<Material>();
    private Material previous_skybox;
    private AmbientMode previous_ambient_mode;
    private Color previous_ambient_light;
    private bool previous_fog;
    private FogMode previous_fog_mode;
    private Color previous_fog_color;
    private float previous_fog_start;
    private float previous_fog_end;
    private Renderer original_floor_renderer;
    private bool original_floor_enabled;
    private bool render_settings_captured;

    public int VisualElementCount { get; private set; }

    public static G1AmbientOperatorEnvironment Create()
    {
        GameObject existing = GameObject.Find(ObjectName);
        if (existing != null)
        {
            G1AmbientOperatorEnvironment existing_environment =
                existing.GetComponent<G1AmbientOperatorEnvironment>();
            if (existing_environment != null)
            {
                existing.SetActive(true);
                return existing_environment;
            }
        }

        GameObject environment_object = new GameObject(ObjectName);
        G1AmbientOperatorEnvironment environment =
            environment_object.AddComponent<G1AmbientOperatorEnvironment>();
        environment.Build();
        return environment;
    }

    private void Build()
    {
        CaptureAndApplyRenderSettings();

        GameObject simulation_floor = GameObject.Find("Simulation_Floor");
        if (simulation_floor != null)
        {
            original_floor_renderer = simulation_floor.GetComponent<Renderer>();
            if (original_floor_renderer != null)
            {
                original_floor_enabled = original_floor_renderer.enabled;
                original_floor_renderer.enabled = false;
            }
        }

        Material floor_material = CreateMaterial(
            "G1 Ambient Floor",
            new Color(0.055f, 0.075f, 0.090f, 1.0f),
            false);
        Material wall_material = CreateMaterial(
            "G1 Ambient Walls",
            new Color(0.035f, 0.050f, 0.065f, 1.0f),
            false);
        Material platform_material = CreateMaterial(
            "G1 Ambient Platform",
            new Color(0.085f, 0.115f, 0.135f, 1.0f),
            false);
        Material accent_material = CreateMaterial(
            "G1 Ambient Accents",
            new Color(0.15f, 0.72f, 0.76f, 1.0f),
            true);

        CreateVisual(
            PrimitiveType.Cube,
            "Floor",
            new Vector3(0.0f, -0.06f, 0.0f),
            new Vector3(24.0f, 0.10f, 24.0f),
            floor_material);
        CreateVisual(
            PrimitiveType.Cylinder,
            "Central_Platform",
            new Vector3(0.0f, 0.005f, 0.0f),
            new Vector3(2.6f, 0.015f, 2.6f),
            platform_material);

        CreateVisual(PrimitiveType.Cube, "Wall_North", new Vector3(0.0f, 3.0f, 12.0f), new Vector3(24.0f, 6.0f, 0.15f), wall_material);
        CreateVisual(PrimitiveType.Cube, "Wall_South", new Vector3(0.0f, 3.0f, -12.0f), new Vector3(24.0f, 6.0f, 0.15f), wall_material);
        CreateVisual(PrimitiveType.Cube, "Wall_East", new Vector3(12.0f, 3.0f, 0.0f), new Vector3(0.15f, 6.0f, 24.0f), wall_material);
        CreateVisual(PrimitiveType.Cube, "Wall_West", new Vector3(-12.0f, 3.0f, 0.0f), new Vector3(0.15f, 6.0f, 24.0f), wall_material);
        CreateVisual(PrimitiveType.Cube, "Ceiling", new Vector3(0.0f, 6.0f, 0.0f), new Vector3(24.0f, 0.10f, 24.0f), wall_material);

        CreateVisual(PrimitiveType.Cube, "North_Light_Band", new Vector3(0.0f, 3.8f, 11.90f), new Vector3(12.0f, 0.035f, 0.03f), accent_material);
        CreateVisual(PrimitiveType.Cube, "South_Light_Band", new Vector3(0.0f, 3.8f, -11.90f), new Vector3(12.0f, 0.035f, 0.03f), accent_material);
        CreateVisual(PrimitiveType.Cube, "East_Light_Band", new Vector3(11.90f, 3.8f, 0.0f), new Vector3(0.03f, 0.035f, 12.0f), accent_material);
        CreateVisual(PrimitiveType.Cube, "West_Light_Band", new Vector3(-11.90f, 3.8f, 0.0f), new Vector3(0.03f, 0.035f, 12.0f), accent_material);

        CreateVisual(PrimitiveType.Cube, "Pillar_NE", new Vector3(8.0f, 2.5f, 8.0f), new Vector3(0.08f, 5.0f, 0.08f), accent_material);
        CreateVisual(PrimitiveType.Cube, "Pillar_NW", new Vector3(-8.0f, 2.5f, 8.0f), new Vector3(0.08f, 5.0f, 0.08f), accent_material);
        CreateVisual(PrimitiveType.Cube, "Pillar_SE", new Vector3(8.0f, 2.5f, -8.0f), new Vector3(0.08f, 5.0f, 0.08f), accent_material);
        CreateVisual(PrimitiveType.Cube, "Pillar_SW", new Vector3(-8.0f, 2.5f, -8.0f), new Vector3(0.08f, 5.0f, 0.08f), accent_material);
    }

    private Material CreateMaterial(string material_name, Color color, bool unlit)
    {
        Shader shader = Shader.Find(unlit ? "Unlit/Color" : "Standard");
        if (shader == null)
        {
            shader = Shader.Find("Sprites/Default");
        }
        Material material = new Material(shader)
        {
            name = material_name,
            color = color,
            hideFlags = HideFlags.DontSave
        };
        if (!unlit && material.HasProperty("_Smoothness"))
        {
            material.SetFloat("_Smoothness", 0.15f);
        }
        runtime_materials.Add(material);
        return material;
    }

    private void CreateVisual(
        PrimitiveType primitive_type,
        string object_name,
        Vector3 position,
        Vector3 scale,
        Material material)
    {
        GameObject visual = GameObject.CreatePrimitive(primitive_type);
        visual.name = object_name;
        visual.transform.SetParent(transform, false);
        visual.transform.localPosition = position;
        visual.transform.localRotation = Quaternion.identity;
        visual.transform.localScale = scale;
        Collider collider_value = visual.GetComponent<Collider>();
        if (collider_value != null)
        {
            DestroyRuntimeObject(collider_value);
        }
        Renderer renderer_value = visual.GetComponent<Renderer>();
        if (renderer_value != null)
        {
            renderer_value.sharedMaterial = material;
            renderer_value.shadowCastingMode = ShadowCastingMode.Off;
            renderer_value.receiveShadows = false;
        }
        VisualElementCount++;
    }

    private void CaptureAndApplyRenderSettings()
    {
        previous_skybox = RenderSettings.skybox;
        previous_ambient_mode = RenderSettings.ambientMode;
        previous_ambient_light = RenderSettings.ambientLight;
        previous_fog = RenderSettings.fog;
        previous_fog_mode = RenderSettings.fogMode;
        previous_fog_color = RenderSettings.fogColor;
        previous_fog_start = RenderSettings.fogStartDistance;
        previous_fog_end = RenderSettings.fogEndDistance;
        render_settings_captured = true;

        RenderSettings.skybox = null;
        RenderSettings.ambientMode = AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(0.32f, 0.39f, 0.43f, 1.0f);
        RenderSettings.fog = true;
        RenderSettings.fogMode = FogMode.Linear;
        RenderSettings.fogColor = new Color(0.025f, 0.040f, 0.052f, 1.0f);
        RenderSettings.fogStartDistance = 10.0f;
        RenderSettings.fogEndDistance = 25.0f;
    }

    private void OnDestroy()
    {
        if (original_floor_renderer != null)
        {
            original_floor_renderer.enabled = original_floor_enabled;
        }
        if (render_settings_captured)
        {
            RenderSettings.skybox = previous_skybox;
            RenderSettings.ambientMode = previous_ambient_mode;
            RenderSettings.ambientLight = previous_ambient_light;
            RenderSettings.fog = previous_fog;
            RenderSettings.fogMode = previous_fog_mode;
            RenderSettings.fogColor = previous_fog_color;
            RenderSettings.fogStartDistance = previous_fog_start;
            RenderSettings.fogEndDistance = previous_fog_end;
        }
        foreach (Material material in runtime_materials)
        {
            DestroyRuntimeObject(material);
        }
        runtime_materials.Clear();
    }

    private static void DestroyRuntimeObject(Object object_value)
    {
        if (object_value == null)
        {
            return;
        }
        if (Application.isPlaying)
        {
            Object.Destroy(object_value);
        }
        else
        {
            Object.DestroyImmediate(object_value);
        }
    }
}
