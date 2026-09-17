"""Offline geometry audit of saved C++ output. Never changes live runtimes."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--isolated-mujoco',action='store_true')
args=parser.parse_args()
if args.isolated_mujoco:
    runtime=ROOT/'logs/diagnostics/mujoco_versions/3.12.0'
    if not (runtime/'mujoco').is_dir():raise RuntimeError('isolated MuJoCo 3.12.0 missing')
    sys.path.insert(0,str(runtime))
import numpy as np
import mujoco
from replay_upstream_mink import build,base
if args.isolated_mujoco and mujoco.__version__!='3.12.0':raise RuntimeError('wrong isolated runtime')
model,planner,trajectory=build()
fixture=json.loads((ROOT/'logs/test_results/mink_resampler_generated_offline.json').read_text())
home=base._initial_configuration(model);previous=home.copy()
ids=[int(model.joint(n).qposadr[0]) for n in base.g1.G1_29_JOINTS]
np.testing.assert_allclose(home[ids],fixture['batch']['home'],atol=1e-12)
checked=0;failure=None;maximum_v=0.;maximum_a=0.
for output in fixture['generated']['outputs']:
    candidate=home.copy();candidate[ids]=output['q']
    if not trajectory._safe_path(previous,candidate):
        failure=dict(time=output['time'],clearance_m=planner.GetClearance(trajectory.rejected_sample),
                     rejected_q=trajectory.rejected_sample.tolist())
        break
    np.testing.assert_allclose(candidate[ids[:22]],home[ids[:22]],atol=0,rtol=0)
    maximum_v=max(maximum_v,float(np.max(np.abs(output['velocity']))))
    maximum_a=max(maximum_a,float(np.max(np.abs(output['acceleration']))))
    previous=candidate;checked+=1
if failure is None:np.testing.assert_allclose(previous,home,atol=1e-6)
report=dict(offline_only=True,mujoco_version=mujoco.__version__,mujoco_path=mujoco.__file__,
    output_hz=500,checked_segments=checked,total_segments=len(fixture['generated']['outputs']),
    all_geometry_passed=failure is None,failure=failure,max_velocity_rad_s=maximum_v,
    max_acceleration_rad_s2=maximum_a,publisher_created=False)
path=ROOT/f'logs/test_results/mink_resampler_geometry_{mujoco.__version__}.json'
path.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='failure'}))
if failure:print(json.dumps(failure));sys.exit(1)
