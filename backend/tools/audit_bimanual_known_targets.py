"""Generate known FK endpoints, then audit IK tracking offline. No transport."""
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
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from g1_bimanual_runtime import load_engine
    load_engine(args.engine_root)
    import numpy as np
    from g1_bimanual_sim import BimanualSimulation
    from g1_bimanual_limits import JOINT_ACCELERATION_LIMIT_RAD_S2

    # Declared before observing results. Not hardware acceptance criteria.
    criteria = dict(final_position_mm=5., final_rotation_deg=2., clearance_m=.005,
                    acceleration_rad_s2=JOINT_ACCELERATION_LIMIT_RAD_S2+1e-4)
    report = dict(data_kind='synthetic_fk_witness_targets', hardware_validated=False,
                  criteria=criteria, cases=[], source_sha256={})
    for name in ('g1_bimanual_sim.py', 'g1_bimanual_motion_policy.py'):
        report['source_sha256'][name] = hashlib.sha256(
            (ROOT/'MuJoCo_G1_Controller/scripts'/name).read_bytes()).hexdigest()
    motions = dict(wrist_pitch_minus=[0,0,0,0,0,-30,0],
                   wrist_pitch_plus=[0,0,0,0,0,30,0],
                   elbow_minus=[0,0,0,-15,0,0,0],
                   elbow_plus=[0,0,0,15,0,0,0],
                   reach=[-20,0,0,10,0,0,0])
    cases = [(side+'_'+name, (side,), delta) for side in ('left','right')
             for name,delta in motions.items()]
    cases += [('both_'+name, ('left','right'), motions[name])
              for name in ('reach','wrist_pitch_plus')]
    for name, sides, delta in cases:
        sim = BimanualSimulation()
        witness = sim.home.copy()
        for side in sides:
            witness[sim.motion[side].qpos_ids] += np.deg2rad(delta)
        q = witness[sim.qids]
        assert np.all(q>=sim.ranges[:,0]) and np.all(q<=sim.ranges[:,1])
        witness_clearance = float(sim.clearance(witness))
        # This sampled joint-space witness establishes a candidate route, not a
        # continuous collision certificate or the actual IK route.
        route_clearance = min(float(sim.clearance(sim.home+t*(witness-sim.home)))
                              for t in np.linspace(0,1,101))
        sim.config.update(witness)
        goals = {s:sim.config.get_transform_frame_to_world(s+'_wrist_yaw_link','body')
                 for s in ('left','right')}
        goal_matrices = {s:g.as_matrix().tolist() for s,g in goals.items()}
        sim.config.update(sim.home)
        row = dict(name=name, witness_q_rad=witness[sim.qids].tolist(),
                   target_pose_matrix=goal_matrices,
                   witness_clearance_m=witness_clearance,
                   sampled_witness_route_clearance_m=route_clearance,
                   target_position_shift_mm={s:float(np.linalg.norm(
                       goals[s].translation()-sim.home_targets[s].translation())*1000)
                       for s in sides}, checkpoints=[])
        if witness_clearance<.005 or route_clearance<.005:
            row['result']='invalid_fixture_collision'
            report['cases'].append(row)
            continue
        clearance_min=.2
        speed_ratio=acceleration_peak=0.
        blocked=projected=0
        for tick in range(1,601):
            sim.step(goals)
            clearance_min=min(clearance_min,float(sim.clearance(sim.config.q)))
            speed_ratio=max(speed_ratio,float(np.max(np.abs(sim.velocity[sim.dofs])/sim.caps)))
            acceleration_peak=max(acceleration_peak,float(np.max(np.abs(sim.acceleration[sim.dofs]))))
            blocked += sim.state=='blocked'
            projected += any(p.target_projected for p in sim.motion.values())
            if tick not in (180,360,600):
                continue
            checkpoint=dict(seconds=tick*sim.dt, state=sim.state, arms={})
            for side in ('left','right'):
                pose=sim.config.get_transform_frame_to_world(side+'_wrist_yaw_link','body')
                checkpoint['arms'][side]=dict(
                    position_mm=float(np.linalg.norm(pose.translation()-goals[side].translation())*1000),
                    rotation_deg=float(np.rad2deg(np.linalg.norm(
                        (pose.rotation().inverse() @ goals[side].rotation()).log()))))
            row['checkpoints'].append(checkpoint)
        row.update(min_clearance_m=clearance_min, speed_cap_ratio=speed_ratio,
                   peak_acceleration_rad_s2=acceleration_peak, blocked_ticks=blocked,
                   projected_ticks=projected)
        errors=row['checkpoints'][-1]['arms'].values()
        row['result']='pass' if (all(e['position_mm']<=5 and e['rotation_deg']<=2 for e in errors)
            and blocked==0 and clearance_min>=.005 and speed_ratio<=1+1e-6
            and acceleration_peak<=criteria['acceleration_rad_s2']) else 'criteria_not_met'
        report['cases'].append(row)
        print(json.dumps(dict(name=name,result=row['result'],final=row['checkpoints'][-1],
                              projected=projected)),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as output:
        json.dump(report,output,indent=2,allow_nan=False)
        output.write('\n')


if __name__=='__main__':
    main()
