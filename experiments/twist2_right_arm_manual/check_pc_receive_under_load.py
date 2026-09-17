"""PC-only 50 Hz synthetic policy load plus optional read-only LowState capture.
Never creates a command publisher. This is not the native control loop.
"""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
TORCH_PYTHON='/home/user/.venvs/twist2-vr-build/bin/python'
SDK_PYTHON='/home/user/.venvs/g1-teleop/bin/python'

def Worker(output):
    import torch
    from offline_policy_adapter import ReadVerifiedPolicy
    torch.set_num_threads(1)
    model=torch.jit.load(io.BytesIO(ReadVerifiedPolicy(ROOT/'references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt')),map_location='cpu').eval()
    # Deliberately synthetic input: load probe, not measured-state policy validation.
    obs=torch.zeros((1,1432),dtype=torch.float32)
    timings=[]
    with torch.inference_mode():
        for _ in range(20):model(obs)
        print('READY',flush=True)
        if sys.stdin.readline().strip()!='GO':raise RuntimeError('missing start')
        start=time.monotonic();deadline=start
        for _ in range(800):
            time.sleep(max(0,deadline-time.monotonic()))
            before=time.monotonic();result=model(obs);after=time.monotonic()
            if result.shape!=(1,29) or not torch.isfinite(result).all():raise ValueError('policy output')
            timings.append({'started':before,'ended':after,'inference_ms':1000*(after-before),'lateness_ms':1000*max(0,before-deadline)})
            deadline+=.02
    output.write_text(json.dumps({'synthetic_input':True,'publisher_created':False,'samples':timings}))

def Main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--offline-only',action='store_true')
    args=parser.parse_args()
    if args.worker:Worker(args.output);return
    output=args.output.resolve();allowed=(ROOT/'logs/test_results').resolve()
    if not output.is_relative_to(allowed) or output==allowed:raise ValueError('PC result directory only')
    output.mkdir(exist_ok=False)
    worker=subprocess.Popen([TORCH_PYTHON,'-B',str(Path(__file__).resolve()),'--worker','--output',str(output/'policy_load.json')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        if worker.stdout.readline().strip()!='READY':raise RuntimeError('worker initialization failed')
        worker.stdin.write('GO\n');worker.stdin.flush()
        print('50 Hz synthetic policy load started; no motor output.',flush=True)
        if not args.offline_only:
            subprocess.run([SDK_PYTHON,'-B',str(ROOT/'experiments/twist2_right_arm_manual/capture_hg_readonly.py'),'--seconds','10','--sample-limit','12000','--output',str(output/'lowstate.jsonl')],check=True,timeout=30)
        if worker.wait(timeout=30)!=0:raise RuntimeError('policy load failed')
        report={'publisher_created':False,'synthetic_policy_load':True,'offline_only':args.offline_only}
        load=json.loads((output/'policy_load.json').read_text())['samples']
        report['inference_ms_max']=max(x['inference_ms'] for x in load)
        report['inference_over_20ms']=sum(x['inference_ms']>20 for x in load)
        if not args.offline_only:
            from review_hg_capture_offline import Review
            capture=Review(output/'lowstate.jsonl');report['capture']=capture
            samples=[json.loads(line) for line in (output/'lowstate.jsonl').read_text().splitlines() if json.loads(line)['event']=='sample']
            report['capture_inside_load_window']=load[0]['started']<=samples[0]['received_at_s'] and samples[-1]['received_at_s']<=load[-1]['ended']
        (output/'summary.json').write_text(json.dumps(report,indent=2))
        print(json.dumps({k:v for k,v in report.items() if k!='capture'}));print('Results:',output)
    finally:
        if worker.poll() is None:worker.terminate();worker.wait(timeout=5)

if __name__=='__main__':Main()
