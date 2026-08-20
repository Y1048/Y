using UnityEngine;
using UnityEngine.XR;

public class G1XrHeadPoseDriver : MonoBehaviour
{
    public Vector3 trackingOrigin = new Vector3(0.0f, 1.55f, -1.2f);
    public bool applyPosition = true;
    public bool applyRotation = true;

    void LateUpdate()
    {
        if (applyPosition)
        {
            Vector3 headPosition = InputTracking.GetLocalPosition(XRNode.Head);
            if (headPosition.sqrMagnitude > 1e-6f)
                transform.position = trackingOrigin + headPosition;
        }

        if (applyRotation)
        {
            Quaternion headRotation = InputTracking.GetLocalRotation(XRNode.Head);
            if (headRotation != Quaternion.identity)
                transform.rotation = headRotation;
        }
    }
}
