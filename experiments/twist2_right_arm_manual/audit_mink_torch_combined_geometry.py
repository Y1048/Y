"""Post-generation full-body self-collision audit; no robot or dynamics simulation."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'logs/diagnostics/mujoco_versions/3.12.0'))
import mujoco
import numpy as np
from replay_upstream_mink import build,base
if mujoco.__version__!='3.12.0':raise RuntimeError('MuJoCo 3.12.0 required')
path=ROOT/'logs/test_results/mink_torch_combined_replay.json'
raw=path.read_bytes();trial=json.loads(raw)
assert trial['offline_only'] and trial['combined_arm_fixture'] and not trial['geometry_checked']
model,planner,trajectory=build()
names={model.body(i).name for i in range(1,model.nbody)}
_,pairs=base._build_collision_pairs(model,names)
assert len(pairs)>len(planner.geom_pairs),'not expanded beyond arm-only pairs'
ids=[int(model.joint(n).qposadr[0]) for n in base.g1.G1_29_JOINTS]
joints=[int(model.joint(n).id) for n in base.g1.G1_29_JOINTS]
origin=base._initial_configuration(model);origin[ids]=trial['initial_reference'];previous=origin.copy()
minimum=float('inf');failure=None;checked=0
trace=trial['trace'];prior_time=None
for index,output in enumerate(trace):
 if prior_time is not None:assert abs(output['time']-prior_time-.002)<1e-9,'missing output tick'
 prior_time=output['time'];candidate=origin.copy();candidate[ids]=output['q']
 assert np.isfinite(candidate).all()
 np.testing.assert_allclose(candidate[ids[12:22]],origin[ids[12:22]],atol=1e-12)
 for fraction in ([0.,.25,.5,.75,1.] if index==0 else [.25,.5,.75,1.]):
  q=previous+fraction*(candidate-previous)
  violations=[base.g1.G1_29_JOINTS[i] for i,j in enumerate(joints) if model.jnt_limited[j] and not model.jnt_range[j,0]-1e-7<=q[ids[i]]<=model.jnt_range[j,1]+1e-7]
  planner.configuration.update(q)
  near=base._nearest_pair_distance(model,planner.configuration.data,pairs)
  clearance=.2 if near is None else float(near[0]);minimum=min(minimum,clearance)
  if violations or clearance<.005-1e-7:
   failure=dict(index=index,time=output['time'],fraction=fraction,clearance_m=clearance,
    pair=None if near is None else [model.geom(i).name for i in near[1:]],joint_violations=violations,q=q.tolist());break
 if failure:
  data=planner.configuration.data
  mujoco.mj_forward(model,data)
  if near is not None:
   a,b=near[1:]
   failure['raw_distance_m']=float(mujoco.mj_geomDistance(model,data,a,b,.2,None))
   failure['contact_distances_m']=[float(c.dist) for c in data.contact if set(c.geom)=={a,b}]
  break
 previous=candidate;checked+=1
report=dict(offline_only=True,mujoco_version=mujoco.__version__,trace_sha256=hashlib.sha256(raw).hexdigest(),
 arm_fixture_sha256=trial['arm_fixture_sha256'],policy_sha256=trial['policy_sha256'],
 collision_pairs=len(pairs),checked_segments=checked,total_segments=len(trace),minimum_clearance_m=minimum,
 passed=failure is None,failure=failure,coverage='robot self-collision; existing structural/exempt pairs excluded; no ground/balance/dynamics',
 publisher_created=False,physical_safety_validated=False)
(ROOT/'logs/test_results/mink_torch_combined_geometry.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
if failure:sys.exit(1)
