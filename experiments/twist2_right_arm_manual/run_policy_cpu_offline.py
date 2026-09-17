"""Verified local TorchScript CPU smoke test; synthetic observations, no robot IO."""
import argparse
import io
import json
from pathlib import Path
import time
from offline_policy_adapter import ReadVerifiedPolicy,AdaptOutput,EXPECTED_SHA256

ROOT=Path(__file__).resolve().parents[2]


def Smoke():
    import torch
    torch.set_num_threads(1)
    model_path=ROOT/'references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt'
    model=torch.jit.load(io.BytesIO(ReadVerifiedPolicy(model_path)),map_location='cpu').eval()
    default=[-.2,0,0,.4,-.2,0]*2+[0]*3+[0,.4,0,1.2,0,0,0]+[0,-.4,0,1.2,0,0,0]
    mimic=[0,0,.8,0,0,0]+default
    # Reference ordering: mimic35, gyro3, roll/pitch2, q-default29,
    # dq29 (ankles zero), previous action29; history1270; mimic35.
    current=mimic+[0]*3+[0]*2+[0]*29+[0]*29+[0]*29
    observations={'zeros':[0]*1432,'synthetic_home_empty_history':current+[0]*1270+mimic}
    reports=[]
    with torch.inference_mode():
        for name,values in observations.items():
            tensor=torch.tensor([values],dtype=torch.float32,device='cpu')
            if tensor.shape!=(1,1432) or not torch.isfinite(tensor).all(): raise ValueError('observation')
            outputs=[]; timings=[]
            for sequence in range(1,11):
                start=time.perf_counter(); raw=model(tensor); finish=time.perf_counter()
                if raw.shape!=(1,29) or raw.dtype!=torch.float32 or not torch.isfinite(raw).all():
                    raise ValueError('model_output')
                adapted=AdaptOutput(raw.tolist(),sequence=sequence,state_sequence=sequence,
                    created_at=finish,state_received_at=start,now=finish,maximum_age=.01)
                outputs.append(adapted['action']);timings.append((finish-start)*1000)
            if any(row!=outputs[0] for row in outputs): raise ValueError('repeatability')
            reports.append(dict(case=name,repeats=10,shape=list(raw.shape),action=outputs[0],
                inference_ms=timings,raw_max_abs=float(raw.abs().max()),exact_repeat=True))
    return dict(passed=True,torch_version=torch.__version__,device='cpu',policy_sha256=EXPECTED_SHA256,
        input_source='synthetic_observations_not_lowstate',history_feedback_tested=False,
        realtime_guaranteed=False,hardware_output_authorized=False,publisher_created=False,
        robot_safety_validated=False,cases=reports)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('new_output_required')
    report=Smoke()
    with args.output.open('x',encoding='utf-8') as f: json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
