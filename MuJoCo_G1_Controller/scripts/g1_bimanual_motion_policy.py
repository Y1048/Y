"""Side-independent motion preferences adapted from the proven right-arm path.

Only builds tasks/bounds: one shared bimanual QP owns both arms. These costs
never bypass the joint/velocity/acceleration/collision and checked-tail guards.
The original g1_upstream_mink_tracking.py remains an unchanged reference.
"""
import numpy as np
import mink
import mujoco
import g1_mink_shared as base
from g1_bimanual_profile import TRACKING as PROFILE

class ElbowClearanceTask(mink.Task):
    """World lateral/vertical elbow bias; FrameTask axes are body-local."""
    def __init__(self, model, side, gain):
        super().__init__(cost=np.full(2, PROFILE.elbow_clearance_cost), gain=gain, lm_damping=0.)
        self.body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, side + '_elbow_link')
        self.target_position = None
        self.world_to_base = np.eye(3)

    def set_target(self, transform):
        self.target_position = np.asarray(transform.translation()).copy()

    def compute_error(self, configuration):
        if self.target_position is None:
            raise ValueError('Elbow height target is not set')
        return (self.world_to_base @ (configuration.data.xpos[self.body_id]-self.target_position))[1:3]

    def compute_jacobian(self, configuration):
        jacobian = np.zeros((3, configuration.model.nv))
        mujoco.mj_jacBody(configuration.model, configuration.data, jacobian, None, self.body_id)
        return (self.world_to_base @ jacobian)[1:3]

class ShoulderComfortTask(mink.Task):
    """Soft roll/yaw excursion bands; does not create new joint limits."""
    def __init__(self, model, qpos_ids, dofs):
        super().__init__(cost=np.full(2, PROFILE.shoulder_comfort_cost), gain=1., lm_damping=0.)
        self.qpos_ids = np.asarray(qpos_ids)[1:3]
        self.dofs = np.asarray(dofs)[1:3]
        self.reference = np.zeros(2)
        self.band = np.array([PROFILE.shoulder_comfort_roll_band_rad,
                              PROFILE.shoulder_comfort_yaw_band_rad])

    def compute_error(self, configuration):
        delta = configuration.q[self.qpos_ids]-self.reference
        return delta-np.clip(delta, -self.band, self.band)

    def compute_jacobian(self, configuration):
        delta = configuration.q[self.qpos_ids]-self.reference
        jacobian = np.zeros((2, configuration.model.nv))
        jacobian[np.arange(2), self.dofs] = np.abs(delta) > self.band
        return jacobian


class ArmMotionPolicy:
    """Independent preference state for one arm in a shared configuration."""
    def __init__(self, model, configuration, side, reference, dt, clearance_m):
        if side not in ('left', 'right'):
            raise ValueError('Unknown arm side')
        self.model, self.configuration, self.side = model, configuration, side
        self.dt_s, self.clearance_m = dt, clearance_m
        names = getattr(base.g1, side.upper() + '_ARM_JOINTS')
        self.joint_ids = np.array([base._joint_id(model, name) for name in names])
        self.qpos_ids = model.jnt_qposadr[self.joint_ids]
        self.dofs = model.jnt_dofadr[self.joint_ids]
        self.acceleration_limits = np.full(7, PROFILE.joint_acceleration_limit_rad_s2)
        self.wrist_task = mink.FrameTask(side + '_wrist_yaw_link', 'body',
            PROFILE.position_cost, PROFILE.orientation_cost,
            gain=PROFILE.frame_gain, lm_damping=PROFILE.lm_damping)
        cost = np.zeros(model.nv)
        cost[self.dofs] = PROFILE.posture_cost
        self.posture_task = mink.PostureTask(model, cost=cost)
        damping = np.zeros(model.nv)
        damping[self.dofs[:4]] = PROFILE.proximal_damping_cost
        damping[self.dofs[4:]] = PROFILE.wrist_damping_cost
        self.damping_task = mink.DampingTask(model, cost=damping)
        self.wrist_priority_task = mink.DampingTask(model, cost=np.zeros(model.nv))
        self.shoulder_comfort_task = ShoulderComfortTask(model, self.qpos_ids, self.dofs)
        self.elbow_task = ElbowClearanceTask(
            model, side, gain=PROFILE.elbow_gain_per_second * dt)
        self.distance_probe_data = mujoco.MjData(model)
        self.torso_geom_ids = tuple(i for i in range(model.ngeom)
            if (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) or '').startswith('mink_collision_torso_link_'))
        radii = [float(np.min(model.geom_size[i])) for i in range(model.ngeom)
            if (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) or '').startswith('mink_collision_' + side + '_wrist_')]
        if not radii:
            raise ValueError('Missing wrist collision geometry: ' + side)
        self.wrist_target_radius_m = max(radii)
        self._orientation_cost = np.asarray(self.wrist_task.orientation_cost).copy()
        self.orientation_priority_enabled = True
        self.priority_shoulder_yaw_envelope_rad = PROFILE.shoulder_yaw_envelope_rad
        self.reset(reference)

    def reset(self, reference):
        self.posture_reference = np.asarray(reference).copy()
        self.posture_task.set_target(self.posture_reference)
        self._reset_orientation_priority()
        self.elbow_assist_active = False
        self._elbow_reference_q = None
        self.target_projected = False
        self.wrist_priority_weight = 0.
        self.wrist_priority_task.cost[:] = 0.
        self.target_projection_distance_m = 0.
        self.approach_rate_s = 0.
        self.raw_target_position = np.zeros(3)
        self.effective_target_position = np.zeros(3)

    def prepare(self, goal, clearance):
        current_q = self.configuration.q
        self.raw_target_position = goal.translation().copy()
        current_pose = self.configuration.get_transform_frame_to_world(
            self.side + '_wrist_yaw_link', 'body')
        # Preserve the operator wrist target exactly. Torso/body feasibility is
        # enforced by BimanualSafetyEnvelope instead of hidden target rewriting.
        self.target_projected = False
        self.target_projection_distance_m = 0.
        self.effective_target_position = goal.translation().copy()
        self.effective_target_rotation = goal.rotation().as_matrix().copy()
        self.wrist_task.set_target(goal)
        self._update_orientation_priority(current_q, goal, clearance)
        self._update_elbow_assist(current_q, current_pose, goal)
        self._update_wrist_priority(current_q, current_pose, goal, clearance)
        self.approach_rate_s = PROFILE.ik_tracking_rate_s
        self.wrist_task.gain = min(
            PROFILE.frame_gain, self.dt_s * PROFILE.ik_tracking_rate_s)
        # Same task/posture equilibrium as the single-arm controller (not .01).
        self.posture_task.gain = self.wrist_task.gain / PROFILE.frame_gain
        self.shoulder_comfort_task.reference = self.posture_reference[self.qpos_ids[1:3]].copy()
        self.shoulder_comfort_task.gain = self.wrist_task.gain
        tasks = [self.wrist_task, self.posture_task, self.damping_task,
                 self.wrist_priority_task, self.shoulder_comfort_task]
        if self.elbow_assist_active:
            tasks.append(self.elbow_task)
        return tasks

    def yaw_velocity_bounds(self):
        lower, upper = self.model.jnt_range[self.joint_ids[2]]
        reference = self.posture_reference[self.qpos_ids[2]]
        lower = max(lower, reference-self.priority_shoulder_yaw_envelope_rad)
        upper = min(upper, reference+self.priority_shoulder_yaw_envelope_rad)
        q = self.configuration.q[self.qpos_ids[2]]
        a, dt = self.acceleration_limits[2], self.dt_s
        speed = lambda d: PROFILE.shoulder_yaw_stop_scale * (
            np.sqrt((a*dt)**2 + 2*a*max(0., d)) - a*dt)
        row = np.zeros(self.model.nv)
        row[self.dofs[2]] = 1.
        return np.vstack((row, -row)), np.array([speed(upper-q), speed(q-lower)])

    def diagnostics(self):
        return dict(wrist_priority_weight=float(self.wrist_priority_weight),
                    orientation_cost_scale=float(self.orientation_priority_scale),
                    position_priority_active=bool(self.position_priority_active),
                    elbow_assist_active=bool(self.elbow_assist_active),
                    target_projected=bool(self.target_projected),
                    target_projection_distance_m=float(self.target_projection_distance_m),
                    approach_rate_s=float(self.approach_rate_s))

    def _reset_orientation_priority(self):
        self.position_priority_active = False
        self.orientation_priority_scale = 1.
        self._priority_dwell = 0.
        self.wrist_task.set_orientation_cost(self._orientation_cost)


    def _update_orientation_priority(self, current_q, goal, clearance):
        # Keep the original SE3 target. Only its orientation penalty changes;
        # returning to a reachable region can therefore recover the same rotation.
        p = self
        pose = p.configuration.get_transform_frame_to_world(
            self.side + '_wrist_yaw_link', 'body')
        error = float(np.linalg.norm(
            pose.translation() - goal.translation()))
        lower, upper = p.model.jnt_range[p.joint_ids].T
        arm = current_q[p.qpos_ids]
        margin = float(np.min(np.minimum(arm - lower, upper - arm)))
        collision_constrained = (
            clearance < PROFILE.orientation_collision_clearance_m)
        joint_constrained = (
            margin < PROFILE.orientation_joint_margin_rad)
        elbow_extension_constrained = (
            arm[3] - lower[3] < PROFILE.orientation_elbow_margin_rad)
        constrained = collision_constrained or joint_constrained
        if not self.orientation_priority_enabled:
            self._reset_orientation_priority()
            return
        if not self.position_priority_active:
            condition = (
                (error > PROFILE.orientation_error_elbow_m
                 and elbow_extension_constrained)
                or (error > PROFILE.orientation_error_constrained_m
                    and constrained)
            )
        else:
            condition = (
                error < PROFILE.orientation_release_error_m
                or (
                    clearance > PROFILE.orientation_release_clearance_m
                    and margin > PROFILE.orientation_release_joint_margin_rad
                )
            )
        self._priority_dwell = (
            self._priority_dwell + self.dt_s if condition else 0.)
        if self._priority_dwell >= PROFILE.orientation_priority_dwell_s:
            self.position_priority_active = not self.position_priority_active
            self._priority_dwell = 0.
        target = (
            PROFILE.orientation_position_priority_scale
            if self.position_priority_active else 1.)
        slew = self.dt_s * PROFILE.orientation_scale_slew_per_second
        self.orientation_priority_scale += float(np.clip(
            target - self.orientation_priority_scale, -slew, slew))
        p.wrist_task.set_orientation_cost(
            self._orientation_cost * self.orientation_priority_scale)


    def _update_wrist_priority(self, current_q, current_pose, goal, clearance):
        """Finite QP penalty, not motor damping or a proximal joint lock."""
        p = self
        error = float(np.linalg.norm(
            current_pose.translation() - goal.translation()))
        lower, upper = p.model.jnt_range[p.joint_ids[4:]].T
        wrist = current_q[p.qpos_ids[4:]]
        margin = float(np.min(np.minimum(wrist - lower, upper - wrist)))
        position_span = (
            PROFILE.wrist_priority_position_zero_m
            - PROFILE.wrist_priority_position_full_m)
        position_weight = float(np.clip(
            (PROFILE.wrist_priority_position_zero_m - error)
            / position_span, 0., 1.))
        rotation_error = base._rotation_error_radians(
            current_pose.rotation().as_matrix(), goal.rotation().as_matrix())
        rotation_weight = float(np.clip(
            rotation_error / PROFILE.wrist_priority_rotation_full_rad,
            0., 1.))
        margin_span = (
            PROFILE.wrist_priority_margin_full_rad
            - PROFILE.wrist_priority_margin_min_rad)
        margin_weight = float(np.clip(
            (margin - PROFILE.wrist_priority_margin_min_rad)
            / margin_span, 0., 1.))
        clearance_span = (
            PROFILE.wrist_priority_clearance_full_m
            - PROFILE.wrist_priority_clearance_min_m)
        clearance_weight = float(np.clip(
            (clearance - PROFILE.wrist_priority_clearance_min_m)
            / clearance_span, 0., 1.))
        self.wrist_priority_weight = (
            position_weight * rotation_weight
            * margin_weight * clearance_weight)
        self.wrist_priority_task.cost[:] = 0.
        self.wrist_priority_task.cost[p.dofs[:4]] = (
            PROFILE.wrist_priority_proximal_damping_scale
            * self.wrist_priority_weight)


    def _update_elbow_assist(self, current_q, current_pose, goal):
        p = self
        target = np.asarray(goal.translation())
        if self._elbow_reference_q is None or not np.array_equal(
                self._elbow_reference_q, p.posture_reference):
            reference_data = self.distance_probe_data
            reference_data.qpos[:] = p.posture_reference
            mujoco.mj_forward(p.model, reference_data)
            wrist_id = mujoco.mj_name2id(
                p.model, mujoco.mjtObj.mjOBJ_BODY,
                self.side + '_wrist_yaw_link')
            self._reference_wrist_position = (
                reference_data.xpos[wrist_id].copy())
            self._reference_elbow_position = (
                reference_data.xpos[self.elbow_task.body_id].copy())
            self._elbow_reference_q = p.posture_reference.copy()
        if np.linalg.norm(
                target - self._reference_wrist_position
        ) < PROFILE.elbow_reference_release_m:
            self.elbow_assist_active = False
            return
        front_near = False
        for geom_id in self.torso_geom_ids:
            rotation = p.configuration.data.geom_xmat[geom_id].reshape(3, 3)
            local = rotation.T @ (
                target - p.configuration.data.geom_xpos[geom_id])
            half = (
                p.model.geom_size[geom_id]
                + self.wrist_target_radius_m + p.clearance_m)
            if (
                half[0] - PROFILE.torso_front_inner_m
                <= local[0]
                <= half[0] + PROFILE.torso_front_outer_m
                and abs(local[1])
                <= half[1] + PROFILE.torso_front_lateral_margin_m
                and abs(local[2]) <= half[2]
            ):
                front_near = True
                break
        if self.elbow_assist_active and not front_near:
            self.elbow_assist_active = False
        error = np.linalg.norm(current_pose.translation() - target)
        needs_reposition = (
            front_near and error > PROFILE.elbow_assist_error_m)
        if (
            not self.elbow_assist_active
            and needs_reposition
            and current_q[p.qpos_ids[3]]
            < PROFILE.elbow_assist_start_max_rad
        ):
            elbow = p.configuration.get_transform_frame_to_world(
                self.side + '_elbow_link', 'body')
            shoulder = p.configuration.get_transform_frame_to_world(
                self.side + '_shoulder_pitch_link', 'body')
            position = elbow.translation().copy()
            lateral = self.elbow_task.world_to_base[1]
            position += lateral * np.dot(
                lateral, self._reference_elbow_position - position)
            position[2] = min(
                self._reference_elbow_position[2] + PROFILE.elbow_lift_m,
                shoulder.translation()[2] - PROFILE.elbow_below_shoulder_m)
            if (
                position[2]
                > elbow.translation()[2] + PROFILE.elbow_min_lift_m
            ):
                self.elbow_task.set_target(base._matrix_to_se3(
                    elbow.rotation().as_matrix(), position))
                self.elbow_assist_active = True
