"""Offline comparison of policy intent, completed SDK write attempts and paired state."""
import argparse
import csv
import json
from pathlib import Path


def Compare(path):
    with Path(path).open(newline='') as stream:
        reader=csv.DictReader(stream)
        if 'writer_attempt_sequence' not in (reader.fieldnames or []):
            return dict(status='insufficient_evidence',reason='CSV has no writer telemetry',
                        reconstructed_commands=False)
        rows=list(reader)
    seen=set();active=[];rejected=0;damping=0
    for row in rows:
        sequence=int(row['writer_attempt_sequence'])
        if sequence==0 or sequence in seen:continue
        seen.add(sequence)
        if row['writer_sdk_accepted']!='1':rejected+=1;continue
        if row['writer_damping']=='1':damping+=1;continue
        active.append(row)
    joints=[]
    for i in range(29):
        metrics=[]
        for row in active:
            desired,target,q,dq,kp,kd,ff=(float(row[f'writer_{key}_{i}'])
                for key in ('desired','target','q','dq','kp','kd','ff'))
            metrics.append((abs(desired-target),abs(desired-q),abs(target-q),
                            abs(kp*(target-q)-kd*dq+ff)))
        joints.append(dict(joint=i,sampled_active_attempts=len(metrics),
            maximum_limiter_delta=max((m[0] for m in metrics),default=None),
            maximum_policy_state_error=max((m[1] for m in metrics),default=None),
            maximum_command_state_error=max((m[2] for m in metrics),default=None),
            maximum_predicted_pd_torque=max((m[3] for m in metrics),default=None)))
    return dict(status='sampled_write_attempts',unique_attempts=len(seen),
        rejected_attempts=rejected,damping_attempts=damping,joints=joints,
        full_500hz_trace=False,robot_receipt_verified=False,
        note='Uses writer-paired state and desired, not the newer policy row; SDK success is not motor acknowledgement')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=Compare(args.csv)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result))
