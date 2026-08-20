using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.Hands;

public class G1Quest3SXRHandsInput : MonoBehaviour
{
    public static G1Quest3SXRHandsInput Active { get; private set; }

    public Transform rightPalmTarget;
    public Transform leftPalmTarget;
    public bool useWristInsteadOfPalm = false;
    public bool SubsystemRunning { get; private set; }
    public bool RightTracked { get; private set; }
    public bool LeftTracked { get; private set; }
    public float LastRightTrackedTime { get; private set; }
    public float LastLeftTrackedTime { get; private set; }

    XRHandSubsystem subsystem;
    readonly List<XRHandSubsystem> subsystems = new List<XRHandSubsystem>();

    void OnEnable()
    {
        Active = this;
    }

    void OnDisable()
    {
        if (Active == this)
            Active = null;
    }

    void Update()
    {
        if (subsystem == null || !subsystem.running)
            FindSubsystem();

        if (subsystem == null || !subsystem.running)
        {
            SubsystemRunning = false;
            RightTracked = false;
            LeftTracked = false;
            return;
        }

        SubsystemRunning = true;
        RightTracked = UpdateHand(subsystem.rightHand, rightPalmTarget);
        LeftTracked = UpdateHand(subsystem.leftHand, leftPalmTarget);
        if (RightTracked)
            LastRightTrackedTime = Time.time;
        if (LeftTracked)
            LastLeftTrackedTime = Time.time;
    }

    void FindSubsystem()
    {
        SubsystemManager.GetSubsystems(subsystems);
        subsystem = null;
        foreach (XRHandSubsystem candidate in subsystems)
        {
            if (candidate != null && candidate.running)
            {
                subsystem = candidate;
                return;
            }
        }
    }

    bool UpdateHand(XRHand hand, Transform target)
    {
        if (target == null || !hand.isTracked)
            return false;

        XRHandJointID jointId = useWristInsteadOfPalm ? XRHandJointID.Wrist : XRHandJointID.Palm;
        XRHandJoint joint = hand.GetJoint(jointId);
        if (joint.TryGetPose(out Pose pose))
        {
            target.SetPositionAndRotation(pose.position, pose.rotation);
            return true;
        }

        return false;
    }
}
