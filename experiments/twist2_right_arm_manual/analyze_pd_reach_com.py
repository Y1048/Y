"""Offline static whole-body COM audit of the fixed PD reach reference."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
os.environ['G1_USE_HARDWARE_INITIAL_STATE']='0'
sys.path.insert(0,str(ROOT/'MuJoCo_G1_Controller/scripts'))
import run_mink_g1_right_arm_prototype as base


def coefficients(path):
    text=Path(path).read_text(encoding='utf-8')
    block=text.split('coefficients={{',1)[1].split('}};',1)[0]
    values=[float(x) for x in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',block)]
    if len(values)!=56:raise ValueError(f'expected 56 coefficients, got {len(values)}')
    return np.asarray(values).reshape(7,8)


def analyze(reference):
    model,metadata=base.LoadMinkModelWithMetadata();data=base.mujoco.MjData(model)
    q0=base._initial_configuration(model)
    ids=[int(model.jnt_qposadr[base._joint_id(model,n)]) for n in base.g1.RIGHT_ARM_JOINTS]
    c=coefficients(reference);records=[]
    for u in np.linspace(0,1,201):
        q=q0.copy();q[ids]=np.array([sum(c[j,k]*u**k for k in range(8)) for j in range(7)])
        data.qpos[:]=q;base.mujoco.mj_forward(model,data)
        # Body 1 is the floating pelvis root in the checked 29-DoF model; its
        # subtree COM excludes the massless world/ground geometry.
        com=np.array(data.subtree_com[1],dtype=float)
        records.append((float(u),com))
    initial=records[0][1];deltas=np.asarray([x[1]-initial for x in records])
    final=records[-1][1]
    peak=np.max(np.abs(deltas),axis=0)
    distance=np.linalg.norm(deltas[:,:2],axis=1);index=int(np.argmax(distance))
    return {'schema':'g1.pd_reach.static_com.v1','offline_only':True,
      'model':metadata,'samples':len(records),'axis_convention':'MuJoCo world x/y/z; static FK with fixed pelvis and legs',
      'initial_com_m':initial.tolist(),'final_com_m':final.tolist(),
      'final_delta_m':(final-initial).tolist(),'peak_abs_delta_m':peak.tolist(),
      'peak_horizontal_delta_m':float(distance[index]),'peak_horizontal_at_u':records[index][0],
      'conclusion_boundary':'Static COM shift cannot reproduce TWIST2 balance feedback, foot pressure, momentum, support motion, or the observed backward lean. It is a trajectory-screening metric only.',
      'physical_execution_allowed':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,default=Path(__file__).with_name('pd_reach_reference.hpp'));p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();result=analyze(a.reference);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
