"""Small diagnostics helpers shared by the G1 Mink runtime."""


def orientation_diagnostics(target_rotation, wrist_rotation) -> dict:
    """Record target/current rotation matrices for offline reproduction."""
    return {
        "target_rotation_matrix_robot": target_rotation.tolist(),
        "wrist_rotation_matrix_robot": wrist_rotation.tolist(),
        "orientation_solver_policy": "exact_jacobian_weighted_posture_v1",
    }
