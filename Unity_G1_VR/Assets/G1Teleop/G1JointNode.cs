using UnityEngine;

/// <summary>
/// G1 관절 이름과 Unity 회전축을 연결하고 라디안 관절값을 로컬 회전으로 표시한다.
/// 물리나 IK를 계산하지 않는 프리뷰 전용 노드다.
/// </summary>
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
