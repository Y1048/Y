using UnityEngine;

/// <summary>
/// Keeps the visible operator target at the last reachable location while the
/// backend reachability gate is active. The blue tracked-hand marker may keep
/// moving beyond the reachable workspace, so the separation is obvious in VR.
/// </summary>
[DefaultExecutionOrder(10000)]
public sealed class G1ReachabilityTargetLatch : MonoBehaviour
{
    private const string TargetMarkerName = "operator_hand_target_marker";
    private const string TargetAxesName = "operator_hand_target_axes";

    private G1ExistingTargetUdpSender sender;
    private G1RobotStateUdpReceiver stateReceiver;
    private Transform targetMarker;
    private Transform targetAxes;

    private bool hasLastReachablePose;
    private Vector3 lastReachablePosition;
    private Quaternion lastReachableRotation = Quaternion.identity;
    private bool latchActive;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        if (FindObjectOfType<G1ReachabilityTargetLatch>() != null)
        {
            return;
        }

        GameObject runtimeObject = new GameObject("G1ReachabilityTargetLatch");
        DontDestroyOnLoad(runtimeObject);
        runtimeObject.AddComponent<G1ReachabilityTargetLatch>();
    }

    private void LateUpdate()
    {
        ResolveReferences();
        if (targetMarker == null || stateReceiver == null)
        {
            return;
        }

        bool commandActive = sender != null && sender.IsCommandValid;
        bool workspaceLimited = commandActive
            && stateReceiver.HasRecentState
            && stateReceiver.IsWorkspaceLimited;

        if (!commandActive)
        {
            latchActive = false;
            hasLastReachablePose = false;
            return;
        }

        if (!workspaceLimited)
        {
            // Preview has already placed the target at this frame's operator
            // command because this component executes after normal preview code.
            lastReachablePosition = targetMarker.position;
            lastReachableRotation = targetMarker.rotation;
            hasLastReachablePose = true;
            latchActive = false;
            return;
        }

        if (!latchActive)
        {
            // Never use the backend target delta here. It can be rebased and may
            // coincide with the current G1 wrist. Hold the last target that was
            // visibly reachable immediately before the limit became active.
            if (!hasLastReachablePose)
            {
                lastReachablePosition = targetMarker.position;
                lastReachableRotation = targetMarker.rotation;
                hasLastReachablePose = true;
            }
            latchActive = true;
        }

        targetMarker.position = lastReachablePosition;
        targetMarker.rotation = lastReachableRotation;
        if (targetAxes != null)
        {
            targetAxes.position = lastReachablePosition;
            targetAxes.rotation = lastReachableRotation;
        }
    }

    private void ResolveReferences()
    {
        if (sender == null)
        {
            sender = FindObjectOfType<G1ExistingTargetUdpSender>();
        }
        if (stateReceiver == null)
        {
            stateReceiver = FindObjectOfType<G1RobotStateUdpReceiver>();
        }
        if (targetMarker == null)
        {
            GameObject markerObject = GameObject.Find(TargetMarkerName);
            if (markerObject != null)
            {
                targetMarker = markerObject.transform;
            }
        }
        if (targetAxes == null)
        {
            GameObject axesObject = GameObject.Find(TargetAxesName);
            if (axesObject != null)
            {
                targetAxes = axesObject.transform;
            }
        }
    }
}
