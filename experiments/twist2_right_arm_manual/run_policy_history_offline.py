"""Real CPU policy/history + C++ composition, frozen virtual state; no robot IO."""
import argparse
import io
import json
from pathlib import Path
import statistics
import struct
import subprocess
import time
from offline_policy_adapter import ReadVerifiedPolicy,AdaptOutput,EXPECTED_SHA256
from replay_cpp_receiver_log import Replay,ROOT


def F32(x): return struct.unpack('<f',struct.pack('<f',x))[0]


def Run(output):
    import torch
    output.mkdir(parents=True,exist_ok=False)
    capture=ROOT/'logs/test_results/twist2_cpp_quest_raw_20260907_152430/ticks.jsonl'
    Replay(capture)
    rows=[json.loads(x) for x in capture.read_text().splitlines()]
    baseline=next(r['baseline'] for r in rows if r.get('baseline') is not None)
    default=[-.2,0,0,.4,-.2,0]*2+[0]*3+[0,.4,0,1.2,0,0,0]+[0,-.4,0,1.2,0,0,0]
    torch.set_num_threads(1)
    model=torch.jit.load(io.BytesIO(ReadVerifiedPolicy(ROOT/'references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt')),map_location='cpu').eval()
    reports=[]
    for scenario in ('normal','tilt','blend_gate'):
        process=subprocess.Popen([str(ROOT/'logs/test_results/test_policy_history_loop.exe')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        expected_history=[0.0]*1270;expected_previous=[0.0]*29
        commits=active=0;started=False;pending=[];latencies=[];different_feedback=0
        trace=[];previous_candidate=baseline
        def Exchange(message):
            process.stdin.write(json.dumps(message)+'\n');process.stdin.flush()
            line=process.stdout.readline()
            if not line: raise RuntimeError('C++ loop exited: '+process.stderr.read())
            return json.loads(line)
        try:
            blend_start=next(r['now_s'] for r in rows if r.get('mode')=='active')-1 if scenario=='blend_gate' else 0
            process.stdin.write(json.dumps(dict(state_source='frozen_virtual_baseline_not_g1',baseline=baseline,blend_start_s=blend_start))+'\n');process.stdin.flush()
            with torch.inference_mode():
                for source in rows:
                    if source['event']=='packet': pending.append(dict(hex=source['payload_hex'],at=source['received_at_s']))
                    if source['event']!='tick': continue
                    tilt=scenario=='tilt' and started
                    frame=Exchange(dict(op='build',now=source['now_s'],packets=pending,tilt=tilt));pending=[]
                    if frame.get('mode')=='stopped':
                        if frame['commits']!=commits or frame['previous_action']!=expected_previous or frame['candidate'] is not None:
                            raise ValueError('prepare stop committed')
                        frame.update(now_s=source['now_s'],inference_skipped=True,state_source='frozen_virtual_baseline_not_g1')
                        trace.append(frame);break
                    obs=frame['observation']
                    if obs[18:35]!=[F32(x) for x in frame['prepared_upper'][12:]]:
                        raise ValueError('current upper absent from observation')
                    if len(obs)!=1432 or obs[127:1397]!=expected_history or obs[98:127]!=expected_previous or frame['commits']!=commits:
                        raise ValueError('history/previous-action mismatch')
                    if obs[1397:]!=obs[:35]: raise ValueError('mimic tail mismatch')
                    t0=time.perf_counter();raw=model(torch.tensor([obs],dtype=torch.float32));t1=time.perf_counter()
                    latencies.append((t1-t0)*1000)
                    policy=AdaptOutput(raw.tolist(),sequence=len(latencies),state_sequence=len(latencies),
                        created_at=t1,state_received_at=t0,now=t1,maximum_age=.01)
                    row=Exchange(dict(op='apply',action=policy['action']))
                    q=row['candidate']
                    if q is not None:
                        commits+=1
                        expected_history=expected_history[127:]+obs[:127]
                        expected_previous=[max(-2.,min(2.,F32(F32(F32(v)-F32(d))/.5))) for v,d in zip(q,default)]
                        if row['previous_action']!=expected_previous: raise ValueError('candidate feedback mismatch')
                        different_feedback+=row['previous_action']!=policy['action']
                        if q[12:22]!=[F32(v) for v in baseline[12:22]]: raise ValueError('held upper joints changed')
                        if scenario=='normal' and (row['hybrid'][12:]!=source['q'][12:] or q[12:]!=[F32(v) for v in source['q'][12:]]): raise ValueError('recorded upper mismatch')
                        previous_candidate=q
                    elif row['commits']!=commits or row['previous_action']!=expected_previous:
                        raise ValueError('commit without candidate')
                    if row['mode']=='active': active+=1;started=True
                    row.update(now_s=source['now_s'],inference_ms=latencies[-1],policy_action=policy['action'],
                        state_source='frozen_virtual_baseline_not_g1',publisher_created=False)
                    trace.append(row)
                    if row['mode']=='stopped': break
            process.stdin.close()
            if process.wait(timeout=5)!=0: raise RuntimeError(process.stderr.read())
            reason=trace[-1]['reason']
            if reason!=dict(normal='input_disengaged',tilt='attitude_limit',blend_gate='vr_before_blend_complete')[scenario]: raise ValueError('wrong stop')
            if scenario=='normal' and active!=240: raise ValueError('active count')
            if scenario!='blend_gate' and different_feedback==0: raise ValueError('raw action was not distinguished from feedback')
            report=dict(scenario=scenario,passed=True,active_ticks=active,commits=commits,reason=reason,
                inference_count=len(latencies),first_inference_ms=latencies[0],maximum_inference_ms=max(latencies),
                median_inference_ms=statistics.median(latencies),candidate_feedback_differed_from_raw=different_feedback,
                history_exact_checks=True,policy_sha256=EXPECTED_SHA256,torch_version=torch.__version__,
                state_source='frozen_virtual_baseline_not_g1',time_source='recorded_ticks_synthetic_state_policy_times',
                mimic_source='current_prepared_upper_and_blended_legs',blend_position_tested=True,writer_present=False,
                robot_dynamics_tested=False,hardware_output_authorized=False)
            reports.append(report)
            (output/(scenario+'.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in trace),encoding='utf-8')
        finally:
            if process.poll() is None: process.kill();process.wait()
            for stream in (process.stdin,process.stdout,process.stderr):
                if not stream.closed: stream.close()
    (output/'result.json').write_text(json.dumps(reports,indent=2)+'\n',encoding='utf-8')
    return reports

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(Run(p.parse_args().output),indent=2))
