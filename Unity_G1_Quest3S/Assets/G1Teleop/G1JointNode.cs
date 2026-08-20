using UnityEngine;

public class G1JointNode : MonoBehaviour
{
    public string joint_name;
    public Vector3 unity_joint_axis = Vector3.forward;
    public Quaternion neutral_local_rotation = Quaternion.identity;

    public void SetJointPosition(float joint_position)
    {
        transform.localRotation = neutral_local_rotation
            * Quaternion.AngleAxis(joint_position * Mathf.Rad2Deg, unity_joint_axis);
    }
}
