"""Summarize measured state-only captures without fitting actuator dynamics."""
import argparse
import json
from pathlib import Path
import numpy as np
from sysid_capture import JOINT_NAMES
from sysid_readonly_parse import inspect,read


def summarize(paths):
    episodes=[];means=[]
    for path in paths:
        rows=read(path);q=np.array([r['measured_q'] for r in rows]);dq=np.array([r['measured_dq'] for r in rows]);tau=np.array([r['torque_estimate'] for r in rows]);temp=np.array([r['temperature'] for r in rows]);imu=np.array([r['imu_gyro'] for r in rows])
        info=inspect(path);means.append(q.mean(axis=0))
        info.update({'joint_q_std_rad':q.std(axis=0).tolist(),'joint_q_range_rad':np.ptp(q,axis=0).tolist(),
          'joint_dq_rms_rad_s':np.sqrt(np.mean(dq*dq,axis=0)).tolist(),'joint_dq_abs_p99_rad_s':np.quantile(np.abs(dq),.99,axis=0).tolist(),
          'joint_tau_est_std_nm':tau.std(axis=0).tolist(),'temperature_min_c':temp.min(axis=0).tolist(),'temperature_max_c':temp.max(axis=0).tolist(),
          'imu_gyro_std_rad_s':imu.std(axis=0).tolist()});episodes.append(info)
    mean_spread=np.ptp(np.array(means),axis=0).tolist()
    return {'schema':'g1.sysid.quiet-summary.v1','provenance':'actual measured G1 ZeroTorque read-only DDS captures',
      'joint_names':list(JOINT_NAMES),'episodes':episodes,'episode_mean_q_spread_rad':mean_spread,
      'fit_ready':False,'recommended_hardware_gains':None,
      'limitations':['no LowCmd was observed','ZeroTorque does not hold a repeatable commanded posture','state-only data cannot identify actuator delay, lag, friction, inertia, or PD gains']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('captures',nargs='+');a=p.parse_args()
    result=summarize(a.captures)
    with Path(a.output).open('x') as out:json.dump(result,out,indent=2)
