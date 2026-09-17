"""Offline recorded-goal comparison. No live settings, UDP or robot commands."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'logs/diagnostics/mujoco_versions/3.12.0'))
import mujoco
import numpy as np
if mujoco.__version__!='3.12.0':raise RuntimeError('isolated MuJoCo 3.12.0 required')
from replay_upstream_mink import build,base
parser=argparse.ArgumentParser()
parser.add_argument('input',type=Path)
parser.add_argument('--ticks',type=int,default=600)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if args.ticks<1:parser.error('ticks must be positive')
rows=[json.loads(line) for line in args.input.read_text(encoding='utf-8').splitlines() if line.strip()]
results=[]
for orientation_cost in (2.,1.,.5):
 for index,row in enumerate(rows):
  model,planner,trajectory=build()
  # Fixed-cost historical comparison, independent of adaptive runtime mode.
  trajectory.orientation_priority_enabled=False
  trajectory._orientation_cost=np.full(3,orientation_cost)
  planner.wrist_task.set_orientation_cost(orientation_cost)
  q=np.asarray(row['current_q']);origin=q.copy();trajectory.Reset(q)
  goal=base._matrix_to_se3(np.asarray(row['goal_rotation']),np.asarray(row['goal_position']))
  previous=np.zeros(7);minimum=float('inf');maximum_a=0.;holds=0
  frozen=np.ones(len(q),dtype=bool);frozen[planner.qpos_ids]=False
  for _ in range(args.ticks):
   step=trajectory.Track(q,goal);q=step.q;holds+=not step.applied
   assert planner.CheckConfiguration(q),'pose check failed'
   np.testing.assert_allclose(q[frozen],origin[frozen],atol=1e-10)
   velocity=np.asarray(step.velocity_rad_s)
   acceleration=np.abs(velocity-previous)/trajectory.dt_s
   assert np.all(acceleration<=np.asarray(trajectory.acceleration_limits)+1e-6),'acceleration violated'
   assert np.all(np.abs(velocity)<=np.asarray(trajectory.velocity_limits)+1e-6),'speed violated'
   maximum_a=max(maximum_a,float(np.max(acceleration)));previous=velocity
   minimum=min(minimum,planner.GetClearance(q))
  planner.configuration.update(q)
  pose=planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link','body')
  results.append(dict(orientation_cost=orientation_cost,index=index,
   position_m=float(np.linalg.norm(pose.translation()-goal.translation())),
   orientation_deg=float(np.degrees(base._rotation_error_radians(goal.rotation().as_matrix(),pose.rotation().as_matrix()))),
   minimum_clearance_m=minimum,holds=holds,maximum_acceleration_rad_s2=maximum_a))
report=dict(offline_only=True,mujoco_version=mujoco.__version__,ticks=args.ticks,
 input=str(args.input),results=results,live_settings_changed=False,publisher_created=False)
args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
