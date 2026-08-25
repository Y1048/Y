using UnityEngine;

/// <summary>
/// Keeps the visible operator target on the backend-feasible boundary while the
/// reachability gate is active. The blue tracked-hand marker may continue moving
/// outside the workspace, while the orange target follows the actual feasible
/// target without being reconstructed from the G1 wrist pose.
/// </summary>
[DefaultExecutionOrder(10000)]
public sealed class G1ReachabilityTargetLatch : MonoBehaviour
{
    private const string TargetMarkerName = "operator_hand_target_marker";
    private const string TargetAxesName = "operator_hand_target_axes";

    private G1ExistingTargetUdpSender sender;
    private G1RobotStateUdpReceiver stateReceiver;
    private G1ExistingHandTargetBinder handBinder;
    private Transform targetMarker;
    private Transform targetAxes;

    private bool hasLastReachablePosition;
    private Vector3 lastReachablePosition;
    private bool latchActive;
    private bool hasBoundaryTargetDelta;
    private Vector3 boundaryMarkerPosition;
    private Vector3 boundaryTargetDelta;

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
            hasLastReachablePosition = true;
            latchActive = false;
            hasBoundaryTargetDelta = false;
            return;
        }

        // Preview updates the requested orientation every frame. Only position is
        // clipped here, so keep that live orientation while the target slides on
        // the reachable boundary.
        Quaternion requestedRotation = targetMarker.rotation;

        if (!latchActive)
        {
            // Enter the limited state exactly at the last visibly reachable
            // position. Pair that visual anchor with the backend target delta from
            // the same entry frame. Subsequent positions are reconstructed from
            // their relative change, avoiding both wrist teleportation and drift.
            boundaryMarkerPosition = hasLastReachablePosition
                ? lastReachablePosition
                : targetMarker.position;
            if (stateReceiver.HasMotionDiagnostics)
            {
                boundaryTargetDelta = stateReceiver.LatestTargetOperatorDelta;
                hasBoundaryTargetDelta = true;
            }
            else
            {
                hasBoundaryTargetDelta = false;
            }
            latchActive = true;
        }

        Vector3 displayedPosition = boundaryMarkerPosition;
        if (stateReceiver.HasMotionDiagnostics)
        {
            Vector3 currentTargetDelta = stateReceiver.LatestTargetOperatorDelta;
            if (!hasBoundaryTargetDelta)
            {
                boundaryTargetDelta = currentTargetDelta;
                hasBoundaryTargetDelta = true;
            }

            Quaternion operatorHeading = handBinder == null
                ? Quaternion.identity
                : handBinder.OperatorHeading;
            displayedPosition = boundaryMarkerPosition
                + operatorHeading * (currentTargetDelta - boundaryTargetDelta);
        }

        targetMarker.position = displayedPosition;
        targetMarker.rotation = requestedRotation;
        if (targetAxes != null)
        {
            targetAxes.position = displayedPosition;
            targetAxes.rotation = requestedRotation;
        }
    }

    private void ResetLatch()
    {
        latchActive = false;
        hasLastReachablePosition = false;
        hasBoundaryTargetDelta = false;
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
