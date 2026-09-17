"""CPU sensitivity study on fixed recorded states; missing gyro is explicitly zero.

Both inputs use teacher-forced recorded prior actions, not closed-loop dynamics.
No SDK, robot transport, or command writer is used.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path


def Gyro(row):
    keys=('gyro_x_rad_s','gyro_y_rad_s','gyro_z_rad_s')
    present=[k in row for k in keys]
    if not any(present):return [0.,0.,0.], 'missing_assumed_zero'
    if not all(present):raise ValueError('partial_gyro_columns')
    values=[float(row[k]) for k in keys]
    if not all(math.isfinite(v) for v in values):raise ValueError('nonfinite_gyro')
    return [.25*v for v in values], 'recorded_policy_state'


def Run(csv_path, model_path):
    import torch
    data=model_path.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    if digest!='463be0376c2c1f551b996d0bf9ab97833854f2cc098b9d4fea735f17ec2e9015':
        raise ValueError('policy_hash')
    with csv_path.open(newline='') as stream:rows=list(csv.DictReader(stream))
    torch.set_num_threads(1)
    model=torch.jit.load(io.BytesIO(data),map_location='cpu').eval()
    default=[-.2,0,0,.4,-.2,0]*2+[0]*3+[0,.4,0,1.2,0,0,0]+[0,-.4,0,1.2,0,0,0]
    history={mode:[[0.]*127 for _ in range(10)] for mode in ('raw','applied')}
    previous={mode:[0.]*29 for mode in history}
    differences=[]
    residuals=[]
    gyro_sources=set()
    maximum_logged_action=0.
    with torch.inference_mode():
        for row in rows:
            mimic=[0,0,.8,0,0,0]+[float(row[f'mimic_target_{i}']) for i in range(29)]
            gyro,gyro_source=Gyro(row)
            gyro_sources.add(gyro_source)
            shared=mimic+gyro+[float(row['roll_rad']),float(row['pitch_rad'])]
            shared += [float(row[f'q_{i}'])-default[i] for i in range(29)]
            shared += [0 if i in (4,5,10,11) else .05*float(row[f'dq_{i}']) for i in range(29)]
            outputs={}
            for mode in history:
                current=shared+previous[mode]
                obs=current+[v for h in history[mode] for v in h]+mimic
                assert len(obs)==1432
                x=torch.tensor([obs],dtype=torch.float32).clamp(-100,100)
                output=model(x).reshape(-1)
                if output.numel()!=29 or not torch.isfinite(output).all():raise ValueError('policy_output')
                outputs[mode]=output.tolist()
                history[mode]=history[mode][1:]+[current]
            previous['raw']=[float(row[f'action_{i}']) for i in range(29)]
            maximum_logged_action=max(maximum_logged_action,max(abs(v) for v in previous['raw']))
            previous['applied']=[max(-2,min(2,(float(row[f'desired_target_{i}'])-default[i])/.5)) for i in range(29)]
            if float(row['alpha'])==1:
                differences.append([.5*abs(a-b) for a,b in zip(outputs['raw'][:12],outputs['applied'][:12])])
                residuals.append(max(abs(max(-2,min(2,p))-a) for p,a in zip(outputs['applied'],previous['raw'])))
    if not differences:raise ValueError('no_post_blend_samples')
    return dict(status='fixed_state_sensitivity_not_physical_validation',policy_sha256=digest,
        gyro_sources=sorted(gyro_sources),maximum_logged_action_abs=maximum_logged_action,
        applied_replay_action_residual_max=max(residuals),
        samples=len(differences),leg_target_difference_rad=[dict(joint=i,
        maximum=max(r[i] for r in differences),mean=sum(r[i] for r in differences)/len(differences)) for i in range(12)],
        limitations=['Missing gyro only is zero-filled; inspect gyro_sources',
        'Teacher-forced previous recorded actions, not closed-loop trajectories',
        'CSV action is native-clipped; inspect maximum_logged_action_abs for saturation',
        'Output difference is pre-writer policy target sensitivity, not robot motion',
        'No correctness verdict or permission to change physical feedback'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv',type=Path)
    parser.add_argument('model',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=Run(args.csv,args.model)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result))
