using UnityEngine;

public static class G1TeleopSceneBootstrap
{
    static bool initialized;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void CreateDefaultObjects()
    {
        if (initialized)
            return;

        initialized = true;

        GameObject rigObject = new GameObject("getcomponent_list");
        rigObject.AddComponent<G1TeleopRig>();
        Object.DontDestroyOnLoad(rigObject);

        Debug.Log("G1 teleop bootstrap created getcomponent_list.");
    }
}
