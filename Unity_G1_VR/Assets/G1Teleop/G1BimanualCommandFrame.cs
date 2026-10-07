using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Command-only kinematic references for alignment and input diagnostics.
/// Reuses the existing rig for FK, then restores the rendered pose immediately.
/// No second IK solver, robot renderer, transport, or measured-state feedback.
/// </summary>
public sealed class G1BimanualCommandFrame
{
    private readonly G1OfficialRig rig;
    private readonly G1JointNode[] nodes = new G1JointNode[29];
    private readonly Quaternion[] initialRotations = new Quaternion[29];
    private readonly Quaternion[] savedRotations = new Quaternion[29];
    private readonly string[] names = G1OfficialRig.GetFullBodyJointNames();
    private readonly float[] heldCommand = new float[14];
    private bool hasCommand;
    private readonly Transform sourceHead;

    public Transform HeadMount { get; }
    public Transform LeftWrist { get; }
    public Transform RightWrist { get; }
    public Vector3 RootPosition { get; private set; }
    public Quaternion RootRotation { get; private set; }
    public Vector3 ShoulderCenter { get; private set; }

    public G1BimanualCommandFrame(G1OfficialRig source, Transform parent)
    {
        if (source == null) throw new ArgumentNullException(nameof(source));
        rig = source;
        var byName = new Dictionary<string, G1JointNode>();
        foreach (var node in rig.GetComponentsInChildren<G1JointNode>(true))
            byName.Add(node.joint_name, node);
        for (int i = 0; i < names.Length; ++i)
        {
            if (!byName.TryGetValue(names[i] + "_joint", out nodes[i]))
                throw new InvalidOperationException("Missing command-frame joint: " + names[i]);
            // Capture the pre-LowState startup pose, including the fixed lower body.
            initialRotations[i] = nodes[i].transform.localRotation;
        }
        sourceHead = rig.head_camera_mount;
        if (sourceHead == null) throw new InvalidOperationException("Missing head mount");
        var root = new GameObject("G1 command references - not measured").transform;
        root.SetParent(parent, false);
        HeadMount = Reference(root, "Command head alignment");
        LeftWrist = Reference(root, "Left command engagement");
        RightWrist = Reference(root, "Right command engagement");
        Refresh(null, null);
    }

    private static Transform Reference(Transform parent, string name)
    {
        var value = new GameObject(name).transform;
        value.SetParent(parent, false);
        return value;
    }

    public bool Refresh(string[] jointNames, float[] positions)
    {
        if (jointNames != null || positions != null)
        {
            if (jointNames == null || positions == null
                || jointNames.Length != 14 || positions.Length != 14) return false;
            for (int i = 0; i < 14; ++i)
                if (jointNames[i] != names[15 + i] + "_joint"
                    || float.IsNaN(positions[i]) || float.IsInfinity(positions[i])) return false;
            Array.Copy(positions, heldCommand, 14);
            hasCommand = true;
        }
        for (int i = 0; i < nodes.Length; ++i)
            savedRotations[i] = nodes[i].transform.localRotation;
        try
        {
            ApplyCommandPose();
            RootPosition = rig.transform.position;
            RootRotation = rig.transform.rotation;
            ShoulderCenter = 0.5f * (nodes[15].transform.position + nodes[22].transform.position);
            LeftWrist.SetPositionAndRotation(nodes[21].transform.position, nodes[21].transform.rotation);
            RightWrist.SetPositionAndRotation(nodes[28].transform.position, nodes[28].transform.rotation);
            HeadMount.SetPositionAndRotation(sourceHead.position, sourceHead.rotation);
        }
        finally
        {
            // Merely evaluating command FK must never replace the measured display.
            for (int i = 0; i < nodes.Length; ++i)
                nodes[i].transform.localRotation = savedRotations[i];
        }
        return true;
    }

    public void ApplyCommandPose()
    {
        for (int i = 0; i < nodes.Length; ++i)
            nodes[i].transform.localRotation = initialRotations[i];
        if (hasCommand)
            for (int i = 0; i < 14; ++i) nodes[15 + i].SetJointPosition(heldCommand[i]);
    }
}
