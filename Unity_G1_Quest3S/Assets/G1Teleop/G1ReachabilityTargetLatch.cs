using UnityEngine;

/// <summary>
/// Keeps the visible operator target on the backend-feasible boundary while the
/// reachability gate is active. The blue tracked-hand marker may continue moving
/// outside the workspace, while the orange target follows changes in the actual
/// feasible target without jumping to the current G1 wrist.
/// </summary>
[DefaultExecutionOrder(10000)]
public sealed class G1ReachabilityTargetLatch : MonoBehaviour
{
    private const string TargetMarkerName = "operator_hand_target_marker";
    private const string TargetAxesName = "operator_hand_target_axes";
    private const float BackendDeltaRebaseThresholdM = 0.10f;

    private G1ExistingTargetUdpSender sender;
    private G1RobotStateUdpReceiver stateReceiver;
    private G1ExistingHandTargetBinder handBinder;
    private Transform targetMarker;
    private Transform targetAxes;

    private bool hasLastReachablePose;
    private Vector3 lastReachablePosition;
    private Quaternion lastReachableRotation = Quaternion.identity;
    private bool latchActive;
    private bool hasBackendTargetDelta;
    private Vector3 previousBackendTargetDelta;

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
            ResetLatch();
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
            hasBackendTargetDelta = false;
            return;
        }

        if (!latchActive)
        {
            // Enter the limited state exactly where the visible target last was.
            // Do not reconstruct an absolute backend target here: its clutch
            // reference may differ from Unity's calibration reference.
            if (!hasLastReachablePose)
            {
                lastReachablePosition = targetMarker.position;
                lastReachableRotation = targetMarker.rotation;
                hasLastReachablePose = true;
            }

            latchActive = true;
            if (stateReceiver.HasMotionDiagnostics)
            {
                previousBackendTargetDelta = stateReceiver.LatestTargetOperatorDelta;
                hasBackendTargetDelta = true;
            }
        }
        else if (stateReceiver.HasMotionDiagnostics)
        {
            Vector3 currentBackendTargetDelta = stateReceiver.LatestTargetOperatorDelta;
            if (hasBackendTargetDelta)
            {
                Vector3 deltaChange = currentBackendTargetDelta - previousBackendTargetDelta;

                // A large discontinuity means the backend clutch reference was
                // rebased. Use the new value as a baseline without moving the UI
                // marker so the target can never teleport to the robot wrist.
                if (deltaChange.magnitude <= BackendDeltaRebaseThresholdM)
                {
                    Quaternion operatorHeading = handBinder == null
                        ? Quaternion.identity
                        : handBinder.OperatorHeading;
                    lastReachablePosition += operatorHeading * deltaChange;
                }
            }

            previousBackendTargetDelta = currentBackendTargetDelta;
            hasBackendTargetDelta = true;
        }

        targetMarker.position = lastReachablePosition;
        targetMarker.rotation = lastReachableRotation;
        if (targetAxes != null)
        {
            targetAxes.position = lastReachablePosition;
            targetAxes.rotation = lastReachableRotation;
        }
    }

    private void ResetLatch()
    {
        latchActive = false;
        hasLastReachablePose = false;
        hasBackendTargetDelta = false;
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
        if (handBinder == null)
        {
            handBinder = FindObjectOfType<G1ExistingHandTargetBinder>();
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
