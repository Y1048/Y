"""Offline endpoint search and QP inspection. Never produces a robot trajectory."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'MuJoCo_G1_Controller/scripts'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-root', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--position-only', action='store_true',
                        help='Offline diagnostic: omit orientation objective')
    args = parser.parse_args()
    from g1_bimanual_runtime import load_engine
    load_engine(args.engine_root)
    import numpy as np
    import qpsolvers
    import inspect
    from scipy.optimize import least_squares
    from g1_bimanual_sim import BimanualSimulation, mink

    baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
    report = dict(data_kind='synthetic_endpoint_search', hardware_validated=False,
                  seed=20260921, max_nfev=2000, position_only=args.position_only,
                  rotation_residual_scale_m=0. if args.position_only else .15,
                  acceptance=dict(position_m=.001, rotation_rad=None if args.position_only else float(np.deg2rad(1)),
                                  clearance_m=.005), cases=[],
                  limitation='Endpoint search is not a path planner. Failure to find a solution is not proof of impossibility.',
                  source_sha256={})
    for name in ('g1_bimanual_sim.py', 'g1_bimanual_motion_policy.py'):
        data = (ROOT/'MuJoCo_G1_Controller/scripts'/name).read_bytes()
        report['source_sha256'][name] = hashlib.sha256(data).hexdigest()
        if report['source_sha256'][name] != baseline['source_sha256'][name]:
            raise ValueError('Baseline controller source changed: '+name)
    cases = [('rotation_y_minus45', [0, 0, 0], [0, -np.pi/4, 0]),
             ('translation_y_minus50mm', [0, -.05, 0], [0, 0, 0]),
             ('translation_z_minus50mm', [0, 0, -.05], [0, 0, 0]),
             ('control_home', [0, 0, 0], [0, 0, 0]),
             ('control_translation_x_plus50mm', [.05, 0, 0], [0, 0, 0])]
    for name, shift, rotation in cases:
        sim = BimanualSimulation()
        policy = sim.motion['right']
        home = sim.home_targets['right']
        goal = mink.SE3.from_rotation_and_translation(
            home.rotation() @ mink.SO3.exp(np.array(rotation, dtype=float)), home.translation()+shift)
        lower, upper = sim.model.jnt_range[policy.joint_ids].T.copy()
        lower[2] = max(lower[2], sim.home[policy.qpos_ids[2]]-np.pi/2)
        upper[2] = min(upper[2], sim.home[policy.qpos_ids[2]]+np.pi/2)
        saved = next((x for x in baseline['cases'] if x['name']==name), None)
        rng = np.random.default_rng(report['seed'])
        starts = [sim.home[policy.qpos_ids].copy()]
        if saved:
            starts.append(np.deg2rad(saved['checkpoints'][-1]['joint_angles_deg']))
        starts += [rng.uniform(lower, upper) for _ in range(8)]

        def set_q(arm):
            q = sim.home.copy()
            q[policy.qpos_ids] = arm
            sim.config.update(q)

        def residual(arm):
            set_q(arm)
            pose = sim.config.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
            position = pose.translation()-goal.translation()
            if args.position_only:
                return position
            return np.r_[position, .15*(pose.rotation().inverse() @ goal.rotation()).log()]

        solutions = []
        for index, start in enumerate(starts):
            result = least_squares(residual, np.clip(start, lower+1e-9, upper-1e-9),
                bounds=(lower, upper), max_nfev=2000, ftol=1e-11, xtol=1e-11, gtol=1e-11)
            error = residual(result.x)
            clearance = float(sim.clearance(sim.config.q))
            pose = sim.config.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
            position = float(np.linalg.norm(error[:3]))
            angle = float(np.linalg.norm((pose.rotation().inverse() @ goal.rotation()).log()))
            solutions.append(dict(start=index, solver_success=bool(result.success),
                evaluations=result.nfev, position_error_m=position, rotation_error_rad=angle,
                clearance_m=clearance, joint_rad=result.x.tolist(),
                acceptable=position<=.001 and (args.position_only or angle<=np.deg2rad(1)) and clearance>=.005))
        row = dict(name=name, solutions=solutions, acceptable_endpoints=sum(x['acceptable'] for x in solutions))
        if saved and not args.position_only:
            set_q(np.deg2rad(saved['checkpoints'][-1]['joint_angles_deg']))
            # Inspect a new solve at the saved endpoint, explicitly at zero velocity.
            # This is not a reconstruction of the exact historical QP tick.
            original = qpsolvers.solve_problem

            def capture(problem, **kwargs):
                caller = inspect.currentframe().f_back.f_locals
                solution = original(problem, **kwargs)
                if solution.found:
                    count = len(caller['problem'].h)
                    nc = len(caller['ch'])
                    nd = len(sim.dofs)
                    nb = count-nc-4*nd-4
                    labels = (['configuration_or_velocity']*nb + ['collision']*nc
                              + ['acceleration']*(2*nd) + ['joint_braking']*(2*nd)
                              + ['yaw_envelope']*4)
                    indices = np.flatnonzero(caller['keep'])
                    slack = problem.h-problem.G@solution.x
                    row['endpoint_qp_zero_velocity'] = dict(
                        minimum_normalized_slack=float(np.min(slack)),
                        closest_constraints=[dict(original_row=int(indices[i]),
                            category=labels[indices[i]], slack_rad_s=float(slack[i]))
                            for i in np.argsort(slack)[:10]],
                        velocity_rad_s=solution.x.tolist(),
                        right_task_jacobian_singular_values=np.linalg.svd(
                            policy.wrist_task.compute_jacobian(sim.config)[:, policy.dofs],
                            compute_uv=False).tolist())
                return solution

            qpsolvers.solve_problem = capture
            try:
                sim.step(dict(sim.home_targets, right=goal))
            finally:
                qpsolvers.solve_problem = original
        report['cases'].append(row)
        best = min(solutions, key=lambda x:x['position_error_m']**2+
                   (report['rotation_residual_scale_m']*x['rotation_error_rad'])**2)
        print(json.dumps(dict(name=name, acceptable=row['acceptable_endpoints'], best=best,
                              qp=row.get('endpoint_qp_zero_velocity'))), flush=True)
    assert all(x['acceptable_endpoints']>0 for x in report['cases'] if x['name'].startswith('control_'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(report, out, indent=2, allow_nan=False)
        out.write('\n')


if __name__ == '__main__':
    main()
