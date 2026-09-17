"""Replay a saved blocked pose through upstream collision QP; no transport."""
import json
from collections import Counter
import sys
import tempfile
from pathlib import Path
import numpy as np
import mujoco
import mink
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'MuJoCo_G1_Controller/scripts'))
import run_mink_g1_right_arm_prototype as base
from g1_standard_mink_planner import StandardMinkPlanner
from g1_upstream_mink_tracking import UpstreamMinkTracking
from g1_mink_return_cycle import SimulationReturnCycle


def build():
    with tempfile.TemporaryDirectory() as d:
        path=base._prepare_mink_xml(output_path=Path(d)/'model.xml')
        model=mujoco.MjModel.from_xml_path(str(path))
    base._apply_operational_joint_limits(model)
    speeds=dict(zip(base.g1.RIGHT_ARM_JOINTS,np.deg2rad([90]*4+[180]*3)))
    pairs,_=base._build_collision_pairs(model)
    limits=[mink.ConfigurationLimit(model),mink.VelocityLimit(model,speeds),
            mink.CollisionAvoidanceLimit(model,geom_pairs=pairs,
                minimum_distance_from_collisions=.005,collision_detection_distance=.15)]
    constraints=[mink.DofFreezingTask(model=model,dof_indices=base._frozen_dof_indices(model,base._right_arm_dof_indices(model)))]
    p=StandardMinkPlanner(model,None,None,None,None,limits,constraints,base._select_solver(),.005,speeds)
    t=UpstreamMinkTracking(p,p.qpos_ids,list(speeds.values()),[np.deg2rad(60.)]*7,[1.28]*7,base.DT)
    return model,p,t


def main():
    rows=[json.loads(x) for x in Path(sys.argv[1]).read_text().splitlines()]
    m,p,t=build(); reports=[]
    ticks = int(sys.argv[3]) if len(sys.argv) > 3 else 500
    for index,row in enumerate(rows):
        q=np.array(row['current_q']);origin=q.copy();t.Reset(q);p.ResetDetour()
        goal=base._matrix_to_se3(np.array(row['goal_rotation']),np.array(row['goal_position']))
        holds=0;minimum=p.GetClearance(q); vmax=amax=0.
        statuses=Counter(); previous=np.zeros(7); observed_acceleration=0.
        for _ in range(ticks):
            step=t.Track(q,goal);q=step.q
            statuses[step.status]+=1
            velocity=np.array(step.velocity_rad_s)
            observed_acceleration=max(observed_acceleration,float(np.max(np.abs(velocity-previous)))/t.dt_s)
            previous=velocity
            assert p.CheckConfiguration(q), 'accepted pose violates exact geometry/joint limits'
            assert np.all(np.abs(step.velocity_rad_s) <= np.asarray(t.velocity_limits)+1e-6)
            holds+=not step.applied
            minimum=min(minimum,p.GetClearance(q))
            vmax=max(vmax,max(abs(v) for v in step.velocity_rad_s))
            amax=max(amax,max(abs(v) for v in step.acceleration_rad_s2))
        c=mink.Configuration(m);c.update(origin)
        before=float(np.linalg.norm(c.get_transform_frame_to_world('right_wrist_yaw_link','body').translation()-goal.translation()))
        c.update(q)
        after=float(np.linalg.norm(c.get_transform_frame_to_world('right_wrist_yaw_link','body').translation()-goal.translation()))
        frozen=np.ones(len(q),bool);frozen[p.qpos_ids]=False
        assert np.max(np.abs(q[frozen]-origin[frozen]))<1e-7
        assert vmax<=np.pi+1e-6 and amax<=np.deg2rad(60.)+1e-5
        reports.append(dict(index=index,holds=int(holds),minimum_clearance_m=minimum,
            statuses=dict(statuses),observed_acceleration_including_hard_stops_rad_s2=observed_acceleration,
            position_error_before_m=before,position_error_after_m=after,
            velocity_max_rad_s=vmax,acceleration_max_rad_s2=amax))
    Path(sys.argv[2]).write_text(json.dumps(reports,indent=2))
    print(json.dumps(dict(mujoco_version=mujoco.__version__, snapshots=len(reports),ticks_each=ticks,
        holds=sum(r['holds'] for r in reports),minimum_clearance_m=min(r['minimum_clearance_m'] for r in reports),
        improved=sum(r['position_error_after_m']<r['position_error_before_m'] for r in reports))))


if __name__=='__main__':main()
