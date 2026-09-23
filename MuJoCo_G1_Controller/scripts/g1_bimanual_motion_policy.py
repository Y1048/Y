"""Side-independent motion preferences adapted from the proven right-arm path.

Only builds tasks/bounds: one shared bimanual QP owns both arms. These costs
never bypass the joint/velocity/acceleration/collision and checked-tail guards.
The original g1_upstream_mink_tracking.py remains an unchanged reference.
"""
import numpy as np
import mink
import mujoco
import run_mink_g1_right_arm_prototype as base
from g1_bimanual_limits import JOINT_ACCELERATION_LIMIT_RAD_S2

class ElbowClearanceTask(mink.Task):
    """World lateral/vertical elbow bias; FrameTask axes are body-local."""
    def __init__(self, model, side, gain):
        super().__init__(cost=np.array([8., 8.]), gain=gain, lm_damping=0.)
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
        super().__init__(cost=np.full(2, .6), gain=1., lm_damping=0.)
        self.qpos_ids = np.asarray(qpos_ids)[1:3]
        self.dofs = np.asarray(dofs)[1:3]
        self.reference = np.zeros(2)
        self.band = np.deg2rad([20., 45.])

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
        self.acceleration_limits = np.full(7, JOINT_ACCELERATION_LIMIT_RAD_S2)
        self.wrist_task = mink.FrameTask(side + '_wrist_yaw_link', 'body',
            base.POSITION_COST, base.ORIENTATION_COST,
            gain=base.FRAME_GAIN, lm_damping=base.LM_DAMPING)
        cost = np.zeros(model.nv)
        cost[self.dofs] = base.POSTURE_COST
        self.posture_task = mink.PostureTask(model, cost=cost)
        damping = np.zeros(model.nv)
        damping[self.dofs[:4]] = base.PROXIMAL_DAMPING_COST
        damping[self.dofs[4:]] = base.WRIST_DAMPING_COST
        self.damping_task = mink.DampingTask(model, cost=damping)
        self.wrist_priority_task = mink.DampingTask(model, cost=np.zeros(model.nv))
        self.shoulder_comfort_task = ShoulderComfortTask(model, self.qpos_ids, self.dofs)
        self.elbow_task = ElbowClearanceTask(model, side, gain=.6*dt)
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
        self.priority_shoulder_yaw_envelope_rad = np.deg2rad(90.)
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
        current_pose = self.configuration.get_transform_frame_to_world(self.side + '_wrist_yaw_link', 'body')
        goal, self.target_projected = self._project_target_outside_torso(goal, current_pose.translation())
        self.effective_target_position = goal.translation().copy()
        self.effective_target_rotation = goal.rotation().as_matrix().copy()
        self.target_projection_distance_m = float(np.linalg.norm(self.effective_target_position-self.raw_target_position))
        self.wrist_task.set_target(goal)
        self._update_orientation_priority(current_q, goal, clearance)
        self._update_elbow_assist(current_q, current_pose, goal)
        self._update_wrist_priority(current_q, current_pose, goal, clearance)
        error = self.wrist_task.compute_error(self.configuration)
        jacobian = self.wrist_task.compute_jacobian(self.configuration)[:, self.dofs]
        correction = np.linalg.lstsq(jacobian, -error, rcond=1e-4)[0]
        rate = min(5., float(np.min(np.sqrt(self.acceleration_limits /
            (2.*np.maximum(np.abs(correction), 1e-6))))))
        self.approach_rate_s = rate
        self.wrist_task.gain = min(base.FRAME_GAIN, self.dt_s*rate)
        # Same task/posture equilibrium as the single-arm controller (not .01).
        self.posture_task.gain = self.wrist_task.gain/base.FRAME_GAIN
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
        speed = lambda d: .8*(np.sqrt((a*dt)**2 + 2*a*max(0., d))-a*dt)
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

    def _project_target_outside_torso(self, goal, reference_position):
        """Project a wrist origin out of model-derived torso exclusion boxes."""
        raw = np.asarray(goal.translation(), dtype=float)
        projected = raw.copy()
        reference = np.asarray(reference_position, dtype=float)
        margin = self.wrist_target_radius_m + float(self.clearance_m)
        changed = False
        # Torso mesh bounds can overlap, so repeat until the point is outside
        # every expanded oriented box. Keep the exit side consistent with the
        # current wrist to prevent a target near the center jumping sides.
        for _ in range(max(1, len(self.torso_geom_ids) * 2)):
            pass_changed = False
            for geom_id in self.torso_geom_ids:
                center = self.configuration.data.geom_xpos[geom_id]
                rotation = self.configuration.data.geom_xmat[geom_id].reshape(3, 3)
                half = np.asarray(self.model.geom_size[geom_id]) + margin
                local = rotation.T @ (projected - center)
                if np.any(np.abs(local) >= half):
                    continue
                reference_local = rotation.T @ (reference - center)
                outside = np.flatnonzero(np.abs(reference_local) >= half)
                if outside.size:
                    axis = int(outside[np.argmax(
                        np.abs(reference_local[outside]) / half[outside]
                    )])
                    sign = 1. if reference_local[axis] >= 0. else -1.
                else:
                    distance = half - np.abs(local)
                    axis = int(np.argmin(distance))
                    sign_source = local[axis] if abs(local[axis]) > 1e-9 else reference_local[axis]
                    sign = 1. if sign_source >= 0. else -1.
                local[axis] = sign * half[axis]
                projected = center + rotation @ local
                changed = pass_changed = True
            if not pass_changed:
                break
        effective = base._matrix_to_se3(goal.rotation().as_matrix(), projected)
        return effective, changed


    def _reset_orientation_priority(self):
        self.position_priority_active = False
        self.orientation_priority_scale = 1.
        self._priority_dwell = 0.
        self.wrist_task.set_orientation_cost(self._orientation_cost)


    def _update_orientation_priority(self, current_q, goal, clearance):
        # Keep the original SE3 target. Only its orientation penalty changes;
        # returning to a reachable region can therefore recover the same rotation.
        p = self
        pose = p.configuration.get_transform_frame_to_world(self.side + '_wrist_yaw_link', 'body')
        error = float(np.linalg.norm(pose.translation()-goal.translation()))
        lower, upper = p.model.jnt_range[p.joint_ids].T
        arm = current_q[p.qpos_ids]
        margin = float(np.min(np.minimum(arm-lower, upper-arm)))
        collision_constrained = clearance < .012
        joint_constrained = margin < np.deg2rad(5.)
        elbow_extension_constrained = (
            arm[3] - lower[3] < np.deg2rad(5.)
        )
        constrained = collision_constrained or joint_constrained
        if not self.orientation_priority_enabled:
            self._reset_orientation_priority()
            return
        # Torso projection changes only position. Keep the user's orientation
        # objective active: replacing it with the current rotation each frame
        # freezes persistent orientation error instead of correcting it.
        if self.target_projected:
            self._reset_orientation_priority()
            return
        if not self.position_priority_active:
            condition = ((error > .025 and elbow_extension_constrained)
                         or (error > .08 and constrained))
        else:
            condition = error < .01 or (clearance > .025 and margin > np.deg2rad(8.))
        self._priority_dwell = self._priority_dwell+self.dt_s if condition else 0.
        if self._priority_dwell >= .3:
            self.position_priority_active = not self.position_priority_active
            self._priority_dwell = 0.
        # Mink squares cost-weighted residuals. A 0.1 cost scale leaves only
        # 1% of the normal orientation objective; retain 25% instead, while
        # the position objective and geometric constraints remain active.
        target = .5 if self.position_priority_active else 1.
        self.orientation_priority_scale += float(np.clip(
            target-self.orientation_priority_scale, -self.dt_s, self.dt_s))
        p.wrist_task.set_orientation_cost(self._orientation_cost*self.orientation_priority_scale)


    def _update_wrist_priority(self, current_q, current_pose, goal, clearance):
        """Finite QP penalty, not motor damping or a proximal joint lock."""
        p = self
        error = float(np.linalg.norm(current_pose.translation()-goal.translation()))
        lower, upper = p.model.jnt_range[p.joint_ids[4:]].T
        wrist = current_q[p.qpos_ids[4:]]
        margin = float(np.min(np.minimum(wrist-lower, upper-wrist)))
        # Full position weight inside 2 mm, none beyond 8 mm. Rotation demand
        # gates the penalty so pure translation and final settling stay quick.
        position_weight = float(np.clip((.008-error)/.006, 0., 1.))
        rotation_error = base._rotation_error_radians(
            current_pose.rotation().as_matrix(), goal.rotation().as_matrix())
        rotation_weight = float(np.clip(rotation_error/np.deg2rad(3.), 0., 1.))
        margin_weight = float(np.clip((margin-np.deg2rad(5.))/np.deg2rad(23.), 0., 1.))
        clearance_weight = float(np.clip((clearance-.005)/.02, 0., 1.))
        self.wrist_priority_weight = position_weight * rotation_weight * margin_weight * clearance_weight
        self.wrist_priority_task.cost[:] = 0.
        self.wrist_priority_task.cost[p.dofs[:4]] = 5. * self.wrist_priority_weight


    def _update_elbow_assist(self, current_q, current_pose, goal):
        p = self
        target = np.asarray(goal.translation())
        if self._elbow_reference_q is None or not np.array_equal(
                self._elbow_reference_q, p.posture_reference):
            reference_data = self.distance_probe_data
            reference_data.qpos[:] = p.posture_reference
            mujoco.mj_forward(p.model, reference_data)
            wrist_id = mujoco.mj_name2id(p.model, mujoco.mjtObj.mjOBJ_BODY, self.side + '_wrist_yaw_link')
            self._reference_wrist_position = reference_data.xpos[wrist_id].copy()
            self._reference_elbow_position = reference_data.xpos[self.elbow_task.body_id].copy()
            self._elbow_reference_q = p.posture_reference.copy()
        # Returning to the captured wrist target must release the added pose
        # preference, even if that original reachable target is near the torso.
        if np.linalg.norm(target-self._reference_wrist_position) < .025:
            self.elbow_assist_active = False
            return
        front_near = False
        for geom_id in self.torso_geom_ids:
            rotation = p.configuration.data.geom_xmat[geom_id].reshape(3, 3)
            local = rotation.T @ (target-p.configuration.data.geom_xpos[geom_id])
            half = p.model.geom_size[geom_id] + self.wrist_target_radius_m + p.clearance_m
            if (half[0]-.015 <= local[0] <= half[0]+.06
                    and abs(local[1]) <= half[1]+.03
                    and abs(local[2]) <= half[2]):
                front_near = True
                break
        if self.elbow_assist_active and not front_near:
            self.elbow_assist_active = False
        error = np.linalg.norm(current_pose.translation()-target)
        needs_reposition = front_near and error > .02
        if (not self.elbow_assist_active and needs_reposition
                and current_q[p.qpos_ids[3]] < np.deg2rad(20.)):
            elbow = p.configuration.get_transform_frame_to_world(self.side + '_elbow_link', 'body')
            shoulder = p.configuration.get_transform_frame_to_world(self.side + '_shoulder_pitch_link', 'body')
            # Anchor the lift to the captured engage posture, not the latest
            # elbow height. Repeated activation must never ratchet it upward.
            position = elbow.translation().copy()
            lateral = self.elbow_task.world_to_base[1]
            position += lateral * np.dot(lateral, self._reference_elbow_position-position)
            position[2] = min(self._reference_elbow_position[2]+.08, shoulder.translation()[2]-.04)
            if position[2] > elbow.translation()[2]+.005:
                self.elbow_task.set_target(base._matrix_to_se3(elbow.rotation().as_matrix(), position))
                self.elbow_assist_active = True
